"""Phase 7 — NGO & relief management (Section 15).

Rules encoded here:
* requested / approved / allocated / sent / received are five independent
  quantities. A later stage NEVER overwrites an earlier one.
* sent != received. A mismatch raises DISCREPANCY for a human to resolve; the
  system never quietly adopts the newer number.
* Duplicate commitment is prevented by surfacing outstanding demand vs. what is
  already committed by every NGO, per shelter and category.
* A delayed delivery must carry a reason and a new ETA, and the dependent shelter
  is told — silence is not acceptable.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .. import db
from ..audit import record_audit
from ..auth import current_user, is_admin, require_roles
from ..models import ResourceStatus, Role, clean, now_utc, shelter_view
from ..state_machines import IllegalTransition, RESOURCE

router = APIRouter(prefix="/api/relief", tags=["relief"])

NGO = require_roles(Role.NGO_ADMIN, Role.AUTHORITY, Role.SUPER_ADMIN)
ADMIN_ONLY = require_roles(Role.AUTHORITY, Role.SUPER_ADMIN)
SHELTER_SIDE = require_roles(Role.SHELTER_ADMIN, Role.AUTHORITY, Role.SUPER_ADMIN)
ANY_RELIEF = require_roles(Role.NGO_ADMIN, Role.SHELTER_ADMIN, Role.AUTHORITY, Role.SUPER_ADMIN)

OPEN_STATES = [s for s in RESOURCE.states() if s not in ("DISTRIBUTED", "REJECTED", "CANCELLED")]


async def _load(request_id: str) -> Dict[str, Any]:
    doc = await db.resource_requests.find_one({"requestId": request_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Resource request not found")
    return doc


def _view(doc: Dict[str, Any]) -> Dict[str, Any]:
    d = clean(doc)
    d["quantities"] = {
        "requested": d.get("requestedQuantity", 0), "approved": d.get("approvedQuantity", 0),
        "allocated": d.get("allocatedQuantity", 0), "sent": d.get("sentQuantity", 0),
        "received": d.get("receivedQuantity", 0),
    }
    d["outstanding"] = max(d.get("requestedQuantity", 0) - d.get("receivedQuantity", 0), 0)
    d["allowedNextStates"] = sorted(RESOURCE.allowed_from(d.get("status", "REQUESTED")))
    if d.get("sentQuantity") and d.get("receivedQuantity") and \
            d["sentQuantity"] != d["receivedQuantity"]:
        d["quantityMismatch"] = {"sent": d["sentQuantity"], "received": d["receivedQuantity"],
                                 "difference": d["sentQuantity"] - d["receivedQuantity"]}
    return d


async def _transition(doc: Dict[str, Any], target: str, updates: Dict[str, Any],
                      user: Dict[str, Any], request: Optional[Request], action: str,
                      note: Optional[str] = None) -> Dict[str, Any]:
    try:
        RESOURCE.assert_transition(doc.get("status"), target)
    except IllegalTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    payload = {**updates, "status": target, "updatedAt": now_utc()}
    await db.resource_requests.update_one({"requestId": doc["requestId"]}, {"$set": payload})
    await record_audit(action, "RESOURCE_REQUEST", doc["requestId"],
                       {"status": doc.get("status"), **{k: doc.get(k) for k in updates}},
                       payload, user=user, request=request, note=note)
    return await _load(doc["requestId"])


# ------------------------------------------------------------------ boards
@router.get("/requirements")
async def requirements(user: Dict[str, Any] = Depends(ANY_RELIEF)):
    """Section 15.4 — demand vs. commitment, so two NGOs do not both send the same load."""
    rows: List[Dict[str, Any]] = []
    shelters = {s["shelterId"]: shelter_view(s) async for s in db.shelters.find({})}
    async for r in db.resource_requests.find({"status": {"$in": OPEN_STATES}}):
        v = _view(r)
        sh = shelters.get(r.get("shelterId")) or {}
        v["shelterName"] = sh.get("name")
        v["shelterOccupancy"] = sh.get("occupancy")
        v["shelterStalenessNotice"] = sh.get("stalenessNotice")
        v["committedByOthers"] = 0
        rows.append(v)
    # aggregate commitments per shelter+category so duplicates are visible
    for r in rows:
        r["committedByOthers"] = sum(
            int(o.get("allocatedQuantity") or 0) for o in rows
            if o["requestId"] != r["requestId"] and o.get("shelterId") == r.get("shelterId")
            and o.get("category") == r.get("category"))
        r["remainingNeed"] = max(int(r.get("requestedQuantity") or 0)
                                 - int(r.get("allocatedQuantity") or 0)
                                 - r["committedByOthers"], 0)
        if r["remainingNeed"] == 0 and r.get("status") == ResourceStatus.REQUESTED.value:
            r["duplicateCommitmentWarning"] = (
                "This requirement already appears to be covered by existing commitments — confirm "
                "before committing more stock.")
    rows.sort(key=lambda r: -(r.get("remainingNeed") or 0))
    return {"requirements": rows,
            "note": "Commitments from all NGOs are shown so the same need is not served twice."}


@router.get("/requests")
async def list_requests(status: Optional[str] = None, shelterId: Optional[str] = None,
                       ngoId: Optional[str] = None,
                       user: Dict[str, Any] = Depends(ANY_RELIEF)):
    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    if shelterId:
        q["shelterId"] = shelterId
    if ngoId:
        q["ngoId"] = ngoId
    if user.get("role") == Role.SHELTER_ADMIN.value and user.get("shelterId"):
        q["shelterId"] = user["shelterId"]
    cur = db.resource_requests.find(q).sort("updatedAt", -1)
    return {"requests": [_view(d) async for d in cur]}


@router.get("/requests/{request_id}")
async def get_request(request_id: str, user: Dict[str, Any] = Depends(ANY_RELIEF)):
    from ..audit import timeline
    doc = await _load(request_id)
    out = _view(doc)
    out["timeline"] = await timeline("RESOURCE_REQUEST", request_id)
    return out


# ------------------------------------------------------------------ lifecycle
class Approve(BaseModel):
    approvedQuantity: int
    note: Optional[str] = None


@router.post("/requests/{request_id}/approve")
async def approve(request_id: str, payload: Approve, request: Request,
                  user: Dict[str, Any] = Depends(ADMIN_ONLY)):
    doc = await _load(request_id)
    if payload.approvedQuantity <= 0:
        raise HTTPException(status_code=400, detail="approvedQuantity must be positive")
    updated = await _transition(doc, ResourceStatus.APPROVED.value,
                                {"approvedQuantity": payload.approvedQuantity},
                                user, request, "RESOURCE_APPROVED", payload.note)
    out = _view(updated)
    if payload.approvedQuantity < doc.get("requestedQuantity", 0):
        out["partialApprovalNotice"] = (
            f"Approved {payload.approvedQuantity} of {doc.get('requestedQuantity')} requested — "
            "the original requested figure is retained for the record.")
    return out


class Reject(BaseModel):
    reason: str


@router.post("/requests/{request_id}/reject")
async def reject(request_id: str, payload: Reject, request: Request,
                 user: Dict[str, Any] = Depends(ADMIN_ONLY)):
    doc = await _load(request_id)
    updated = await _transition(doc, ResourceStatus.REJECTED.value, {"rejectionReason": payload.reason},
                                user, request, "RESOURCE_REJECTED", payload.reason)
    return _view(updated)


class Commit(BaseModel):
    allocatedQuantity: int
    eta: Optional[datetime] = None
    note: Optional[str] = None
    acknowledgeDuplicate: bool = False


@router.post("/requests/{request_id}/commit")
async def commit(request_id: str, payload: Commit, request: Request,
                 user: Dict[str, Any] = Depends(NGO)):
    doc = await _load(request_id)
    if payload.allocatedQuantity <= 0:
        raise HTTPException(status_code=400, detail="allocatedQuantity must be positive")
    approved = int(doc.get("approvedQuantity") or 0)
    if approved and payload.allocatedQuantity > approved and not payload.acknowledgeDuplicate:
        raise HTTPException(status_code=409, detail={
            "message": (f"You are committing {payload.allocatedQuantity} against an approved "
                        f"quantity of {approved}. Confirm explicitly to proceed."),
            "approvedQuantity": approved,
            "hint": "Resend with acknowledgeDuplicate=true if the surplus is intentional.",
        })
    updated = await _transition(doc, ResourceStatus.ALLOCATED.value,
                                {"allocatedQuantity": payload.allocatedQuantity,
                                 "ngoId": user.get("ngoId") or doc.get("ngoId"),
                                 "ngoName": user.get("ngoName") or user.get("name"),
                                 "eta": payload.eta},
                                user, request, "RESOURCE_ALLOCATED", payload.note)
    return _view(updated)


class Dispatch(BaseModel):
    sentQuantity: int
    eta: Optional[datetime] = None
    vehicle: Optional[str] = None
    note: Optional[str] = None


@router.post("/requests/{request_id}/dispatch")
async def dispatch(request_id: str, payload: Dispatch, request: Request,
                   user: Dict[str, Any] = Depends(NGO)):
    doc = await _load(request_id)
    if payload.sentQuantity <= 0:
        raise HTTPException(status_code=400, detail="sentQuantity must be positive")
    updated = await _transition(doc, ResourceStatus.DISPATCHED.value,
                                {"sentQuantity": payload.sentQuantity, "eta": payload.eta,
                                 "vehicle": payload.vehicle},
                                user, request, "RESOURCE_DISPATCHED", payload.note)
    out = _view(updated)
    out["note"] = ("Dispatched quantity is stored separately from the received quantity — the "
                   "shelter confirms receipt independently.")
    return out


@router.post("/requests/{request_id}/in-transit")
async def in_transit(request_id: str, request: Request, user: Dict[str, Any] = Depends(NGO)):
    doc = await _load(request_id)
    return _view(await _transition(doc, ResourceStatus.IN_TRANSIT.value, {}, user, request,
                                   "RESOURCE_IN_TRANSIT"))


class Delay(BaseModel):
    reason: str
    newEta: Optional[datetime] = None


@router.post("/requests/{request_id}/delay")
async def delay(request_id: str, payload: Delay, request: Request,
                user: Dict[str, Any] = Depends(NGO)):
    """Section 15.6 — a delay must be communicated with a reason and a new ETA."""
    doc = await _load(request_id)
    updated = await _transition(doc, ResourceStatus.DELAYED.value,
                                {"delayReason": payload.reason, "eta": payload.newEta},
                                user, request, "RESOURCE_DELAYED", payload.reason)
    if doc.get("shelterId"):
        await db.notifications.insert_one({
            "to": doc["shelterId"], "toRole": Role.SHELTER_ADMIN.value, "priority": 2,
            "type": "RESOURCE_DELAY",
            "message": (f"{doc.get('category')} delivery delayed: {payload.reason}. "
                        f"New ETA: {payload.newEta.isoformat() if payload.newEta else 'unknown'}"),
            "objectType": "RESOURCE_REQUEST", "objectId": request_id,
            "createdAt": now_utc(), "delivered": False, "acknowledged": False,
        })
    out = _view(updated)
    out["shelterNotified"] = bool(doc.get("shelterId"))
    out["alternativesHint"] = ("If the shelter cannot wait, raise a fresh requirement so another "
                               "NGO can cover the gap.")
    return out


@router.post("/requests/{request_id}/deliver")
async def deliver(request_id: str, request: Request, user: Dict[str, Any] = Depends(NGO)):
    doc = await _load(request_id)
    return _view(await _transition(doc, ResourceStatus.DELIVERED.value, {}, user, request,
                                   "RESOURCE_DELIVERED"))


class Receive(BaseModel):
    receivedQuantity: int
    note: Optional[str] = None


@router.post("/requests/{request_id}/receive")
async def receive(request_id: str, payload: Receive, request: Request,
                  user: Dict[str, Any] = Depends(SHELTER_SIDE)):
    """Section 16.2 — sent vs received mismatch becomes a DISCREPANCY, not an overwrite."""
    doc = await _load(request_id)
    if user.get("role") == Role.SHELTER_ADMIN.value and user.get("shelterId") and \
            doc.get("shelterId") != user["shelterId"]:
        raise HTTPException(status_code=403, detail="This delivery is for another shelter")
    sent = int(doc.get("sentQuantity") or 0)
    mismatch = sent and payload.receivedQuantity != sent
    target = ResourceStatus.DISCREPANCY.value if mismatch else ResourceStatus.RECEIVED.value
    updates: Dict[str, Any] = {"receivedQuantity": payload.receivedQuantity}
    if mismatch:
        updates["discrepancy"] = {
            "sent": sent, "received": payload.receivedQuantity,
            "difference": sent - payload.receivedQuantity,
            "reportedBy": user["userId"], "reportedAt": now_utc(), "resolved": False,
            "note": payload.note,
        }
    updated = await _transition(doc, target, updates, user, request,
                                "RESOURCE_DISCREPANCY" if mismatch else "RESOURCE_RECEIVED",
                                payload.note)
    out = _view(updated)
    if mismatch:
        await db.conflicts.insert_one({
            "conflictId": f"CF-{request_id}-{int(now_utc().timestamp())}",
            "objectType": "RESOURCE_REQUEST", "objectId": request_id, "field": "quantity",
            "values": [{"value": sent, "reportedBy": doc.get("ngoName") or "NGO", "label": "sent"},
                       {"value": payload.receivedQuantity, "reportedBy": user["userId"],
                        "label": "received"}],
            "status": "OPEN", "createdAt": now_utc(),
        })
        out["discrepancyNotice"] = (
            f"Sent {sent} but received {payload.receivedQuantity}. Both figures are kept and an "
            "admin must resolve the difference — neither number is overwritten.")
    return out


class ResolveDiscrepancy(BaseModel):
    finalQuantity: int
    resolution: str


@router.post("/requests/{request_id}/resolve-discrepancy")
async def resolve_discrepancy(request_id: str, payload: ResolveDiscrepancy, request: Request,
                              user: Dict[str, Any] = Depends(ADMIN_ONLY)):
    doc = await _load(request_id)
    if doc.get("status") != ResourceStatus.DISCREPANCY.value:
        raise HTTPException(status_code=409, detail="This request has no open discrepancy")
    disc = dict(doc.get("discrepancy") or {})
    disc.update({"resolved": True, "resolvedBy": user["userId"], "resolvedAt": now_utc(),
                 "resolution": payload.resolution, "finalQuantity": payload.finalQuantity})
    updated = await _transition(doc, ResourceStatus.RECEIVED.value,
                                {"discrepancy": disc, "reconciledQuantity": payload.finalQuantity},
                                user, request, "RESOURCE_DISCREPANCY_RESOLVED", payload.resolution)
    await db.conflicts.update_many({"objectId": request_id, "status": "OPEN"},
                                   {"$set": {"status": "RESOLVED", "resolvedBy": user["userId"],
                                             "resolvedAt": now_utc(),
                                             "resolution": payload.resolution}})
    out = _view(updated)
    out["note"] = ("Discrepancy resolved by a human decision. The original sent and received "
                   "figures remain in the record and the audit log.")
    return out


class Distribute(BaseModel):
    note: Optional[str] = None


@router.post("/requests/{request_id}/distribute")
async def distribute(request_id: str, payload: Distribute, request: Request,
                     user: Dict[str, Any] = Depends(SHELTER_SIDE)):
    doc = await _load(request_id)
    return _view(await _transition(doc, ResourceStatus.DISTRIBUTED.value, {}, user, request,
                                   "RESOURCE_DISTRIBUTED", payload.note))


# ------------------------------------------------------------------ inventory
class InventoryItem(BaseModel):
    category: str
    unit: str = "units"
    quantity: int
    location: Optional[str] = None


@router.get("/inventory")
async def inventory(user: Dict[str, Any] = Depends(NGO)):
    ngo_id = user.get("ngoId") or user["userId"]
    q = {} if is_admin(user) else {"ngoId": ngo_id}
    items = [clean(d) async for d in db.ngo_inventory.find(q)]
    committed: Dict[str, int] = {}
    async for r in db.resource_requests.find({"ngoId": ngo_id, "status": {"$in": OPEN_STATES}}):
        committed[r.get("category")] = committed.get(r.get("category"), 0) + int(r.get("allocatedQuantity") or 0)
    for it in items:
        it["committed"] = committed.get(it.get("category"), 0)
        it["uncommitted"] = max(int(it.get("quantity") or 0) - it["committed"], 0)
    return {"inventory": items,
            "note": "Committed stock is shown separately so the same load is not promised twice."}


@router.post("/inventory")
async def upsert_inventory(payload: InventoryItem, request: Request,
                           user: Dict[str, Any] = Depends(NGO)):
    ngo_id = user.get("ngoId") or user["userId"]
    key = {"ngoId": ngo_id, "category": payload.category}
    before = await db.ngo_inventory.find_one(key)
    await db.ngo_inventory.update_one(
        key,
        {"$set": {**key, "unit": payload.unit, "quantity": payload.quantity,
                  "location": payload.location, "ngoName": user.get("ngoName") or user.get("name"),
                  "updatedAt": now_utc()}},
        upsert=True)
    await record_audit("NGO_INVENTORY_UPDATE", "NGO_INVENTORY", f"{ngo_id}:{payload.category}",
                       {"quantity": (before or {}).get("quantity")},
                       {"quantity": payload.quantity}, user=user, request=request)
    return clean(await db.ngo_inventory.find_one(key))


@router.get("/pipeline")
async def pipeline(user: Dict[str, Any] = Depends(ANY_RELIEF)):
    counts: Dict[str, int] = {}
    totals = {"requested": 0, "approved": 0, "allocated": 0, "sent": 0, "received": 0}
    async for r in db.resource_requests.find({}):
        counts[r.get("status")] = counts.get(r.get("status"), 0) + 1
        totals["requested"] += int(r.get("requestedQuantity") or 0)
        totals["approved"] += int(r.get("approvedQuantity") or 0)
        totals["allocated"] += int(r.get("allocatedQuantity") or 0)
        totals["sent"] += int(r.get("sentQuantity") or 0)
        totals["received"] += int(r.get("receivedQuantity") or 0)
    return {"byStatus": counts, "quantities": totals,
            "openDiscrepancies": await db.resource_requests.count_documents({"status": "DISCREPANCY"}),
            "note": "Quantities never overwrite each other — gaps between them are real signals."}
