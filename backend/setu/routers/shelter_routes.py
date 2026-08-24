"""Phase 6 \u2014 Shelter management (Section 14).

Rules encoded here:
* `available` is ALWAYS derived (capacity \u2212 occupancy), never stored.
* The last slot cannot be double allocated: occupancy increments are atomic and
  conditional on capacity, so two concurrent arrivals cannot both take one place.
* Two conflicting occupancy reports are never silently overwritten \u2014 the conflict
  is recorded on the shelter and surfaced for human resolution.
* A FULL shelter always returns alternatives; a citizen is never left with a dead end.
* Every shelter figure carries its data age; stale data is labelled, not hidden.
* Offline arrival/departure logs replay with their original timestamps.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .. import db
from ..audit import record_audit
from ..auth import current_user, is_admin, require_roles
from ..geo import haversine_km
from ..models import (Location, ResourceRequest, ResourceStatus, Role, Shelter, ShelterStatus,
                      clean, loc_doc, now_utc, shelter_view)
from ..state_machines import IllegalTransition, SHELTER, derive_shelter_status

router = APIRouter(prefix="/api/shelters", tags=["shelters"])

SHELTER_MANAGER = require_roles(Role.SHELTER_ADMIN, Role.AUTHORITY, Role.SUPER_ADMIN)
ADMIN_ONLY = require_roles(Role.AUTHORITY, Role.SUPER_ADMIN)


def _distance(shelter: Dict[str, Any], lat: Optional[float], lng: Optional[float]):
    loc = shelter.get("location") or {}
    if lat is None or lng is None or not loc:
        return None
    return round(haversine_km(lat, lng, loc["latitude"], loc["longitude"]), 2)


async def _load(shelter_id: str) -> Dict[str, Any]:
    doc = await db.shelters.find_one({"shelterId": shelter_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Shelter not found")
    return doc


def _assert_scope(user: Dict[str, Any], shelter: Dict[str, Any]):
    if is_admin(user):
        return
    if user.get("role") == Role.SHELTER_ADMIN.value:
        if user.get("shelterId") and user["shelterId"] != shelter["shelterId"]:
            raise HTTPException(status_code=403, detail="You can only manage your own shelter")
        return
    raise HTTPException(status_code=403, detail="Not permitted to manage shelters")


async def _alternatives(shelter: Dict[str, Any], needed: int = 1, limit: int = 3) -> List[Dict[str, Any]]:
    """Section 14.3 \u2014 a full shelter must always offer somewhere else to go."""
    loc = shelter.get("location") or {}
    out: List[Dict[str, Any]] = []
    async for other in db.shelters.find({"shelterId": {"$ne": shelter["shelterId"]},
                                         "status": {"$ne": ShelterStatus.CLOSED.value}}):
        v = shelter_view(other)
        if v["available"] >= max(needed, 1):
            v["distanceKm"] = _distance(other, loc.get("latitude"), loc.get("longitude"))
            out.append({k: v[k] for k in ("shelterId", "name", "available", "capacity",
                                          "occupancy", "status", "distanceKm", "contactPhone",
                                          "stalenessNotice")})
    out.sort(key=lambda s: (s["distanceKm"] is None, s["distanceKm"] or 0))
    return out[:limit]


# ------------------------------------------------------------------ read
@router.get("/list")
async def list_shelters(lat: Optional[float] = None, lng: Optional[float] = None,
                        region: Optional[str] = None, needed: int = 1,
                        user: Optional[Dict[str, Any]] = Depends(current_user)):
    q: Dict[str, Any] = {}
    if region:
        q["region"] = region
    rows = []
    async for doc in db.shelters.find(q):
        v = shelter_view(doc)
        v["distanceKm"] = _distance(doc, lat, lng)
        v["acceptingArrivals"] = v["status"] not in (ShelterStatus.CLOSED.value,) and v["available"] >= needed
        rows.append(v)
    rows.sort(key=lambda s: (s["distanceKm"] is None, s["distanceKm"] or 0))
    return {
        "shelters": rows,
        "totals": {
            "capacity": sum(s["capacity"] for s in rows),
            "occupancy": sum(s["occupancy"] for s in rows),
            "available": sum(s["available"] for s in rows),
        },
        "note": ("Availability is derived from capacity minus occupancy at read time. "
                 "Each record shows how old its last update is."),
    }


@router.get("/{shelter_id}")
async def get_shelter(shelter_id: str, user: Dict[str, Any] = Depends(current_user)):
    doc = await _load(shelter_id)
    v = shelter_view(doc)
    if v["available"] <= 0:
        v["alternatives"] = await _alternatives(doc, 1)
        v["fullNotice"] = ("This shelter is full. Alternatives with space are listed \u2014 do not "
                           "travel here without confirming.")
    v["openRequests"] = [clean(r) async for r in db.resource_requests.find(
        {"shelterId": shelter_id, "status": {"$nin": ["DISTRIBUTED", "REJECTED", "CANCELLED"]}})]
    return v


@router.get("/{shelter_id}/alternatives")
async def shelter_alternatives(shelter_id: str, needed: int = 1,
                               user: Dict[str, Any] = Depends(current_user)):
    doc = await _load(shelter_id)
    return {"shelterId": shelter_id, "needed": needed,
            "alternatives": await _alternatives(doc, needed, limit=5)}


# ------------------------------------------------------------------ write
class ShelterCreate(BaseModel):
    name: str
    location: Location
    capacity: int = 100
    occupancy: int = 0
    facilities: List[str] = Field(default_factory=list)
    contactPhone: Optional[str] = None
    region: Optional[str] = None
    adminUserId: Optional[str] = None


@router.post("")
async def create_shelter(payload: ShelterCreate, request: Request,
                         user: Dict[str, Any] = Depends(ADMIN_ONLY)):
    sh = Shelter(**payload.model_dump(exclude={"location"}), location=payload.location)
    doc = sh.model_dump()
    doc["location"] = loc_doc(payload.location)
    doc["status"] = derive_shelter_status(doc["capacity"], doc["occupancy"], ShelterStatus.OPEN.value)
    await db.shelters.insert_one(doc)
    await record_audit("SHELTER_CREATE", "SHELTER", doc["shelterId"], None,
                       {"name": doc["name"], "capacity": doc["capacity"]},
                       user=user, request=request)
    return shelter_view(doc)


class OccupancyChange(BaseModel):
    count: int                                  # positive = arrivals, negative = departures
    expectedOccupancy: Optional[int] = None     # optimistic concurrency (Section 16.3)
    allowOverflow: bool = False
    note: Optional[str] = None
    names: List[str] = Field(default_factory=list)
    occurredAt: Optional[datetime] = None       # offline log replay keeps the original time


async def _apply_occupancy(shelter_id: str, payload: OccupancyChange, user: Dict[str, Any],
                           request: Optional[Request], action: str) -> Dict[str, Any]:
    doc = await _load(shelter_id)
    _assert_scope(user, doc)
    if payload.count == 0:
        raise HTTPException(status_code=400, detail="count must not be zero")

    # Optimistic concurrency: a stale client value is never silently applied.
    if payload.expectedOccupancy is not None and payload.expectedOccupancy != doc.get("occupancy"):
        conflict = {"reportedBy": user["userId"], "at": now_utc(),
                    "expectedOccupancy": payload.expectedOccupancy,
                    "actualOccupancy": doc.get("occupancy"),
                    "attemptedChange": payload.count, "resolved": False}
        await db.shelters.update_one({"shelterId": shelter_id},
                                     {"$set": {"occupancyConflict": conflict}})
        await db.conflicts.insert_one({
            "conflictId": f"CF-{shelter_id}-{int(now_utc().timestamp())}",
            "objectType": "SHELTER", "objectId": shelter_id, "field": "occupancy",
            "values": [{"value": payload.expectedOccupancy + payload.count,
                        "reportedBy": user["userId"], "at": now_utc()},
                       {"value": doc.get("occupancy"), "reportedBy": "current record",
                        "at": doc.get("lastUpdated")}],
            "status": "OPEN", "createdAt": now_utc(),
        })
        await record_audit("SHELTER_OCCUPANCY_CONFLICT", "SHELTER", shelter_id,
                           {"occupancy": doc.get("occupancy")},
                           {"expected": payload.expectedOccupancy}, user=user, request=request,
                           note="Concurrent update rejected \u2014 both values retained for human resolution")
        raise HTTPException(status_code=409, detail={
            "message": ("Someone else updated this shelter first. Nothing was overwritten \u2014 both "
                        "values are recorded for review."),
            "yourExpectedOccupancy": payload.expectedOccupancy,
            "currentOccupancy": doc.get("occupancy"),
            "conflictRecorded": True,
        })

    if payload.count > 0 and not payload.allowOverflow:
        # Atomic, capacity-guarded increment: the last slot can only go to one arrival.
        updated = await db.shelters.find_one_and_update(
            {"shelterId": shelter_id,
             "$expr": {"$lte": [{"$add": ["$occupancy", payload.count]}, "$capacity"]}},
            {"$inc": {"occupancy": payload.count}, "$set": {"lastUpdated": now_utc()}},
            return_document=True,
        )
        if not updated:
            fresh = await _load(shelter_id)
            v = shelter_view(fresh)
            raise HTTPException(status_code=409, detail={
                "message": (f"Only {v['available']} place(s) remain \u2014 {payload.count} arrivals cannot "
                            "be accepted. No partial update was applied."),
                "available": v["available"], "capacity": v["capacity"], "occupancy": v["occupancy"],
                "alternatives": await _alternatives(fresh, payload.count),
                "overrideHint": "Set allowOverflow=true to record an over-capacity intake explicitly.",
            })
    else:
        new_occ = max((doc.get("occupancy") or 0) + payload.count, 0)
        updated = await db.shelters.find_one_and_update(
            {"shelterId": shelter_id},
            {"$set": {"occupancy": new_occ, "lastUpdated": now_utc()}},
            return_document=True,
        )

    status = derive_shelter_status(updated["capacity"], updated["occupancy"], updated.get("status"))
    if status != updated.get("status") and SHELTER.can(updated.get("status"), status):
        await db.shelters.update_one({"shelterId": shelter_id}, {"$set": {"status": status}})

    await db.arrival_logs.insert_one({
        "logId": f"AL-{int(now_utc().timestamp() * 1000)}",
        "shelterId": shelter_id, "count": payload.count, "names": payload.names,
        "note": payload.note, "by": user["userId"],
        "occurredAt": payload.occurredAt or now_utc(), "recordedAt": now_utc(),
        "offlineReplay": bool(payload.occurredAt), "overflow": payload.allowOverflow,
    })
    await record_audit(action, "SHELTER", shelter_id,
                       {"occupancy": doc.get("occupancy"), "status": doc.get("status")},
                       {"occupancy": updated["occupancy"], "status": status},
                       user=user, request=request, note=payload.note)
    out = shelter_view(await _load(shelter_id))
    if out["available"] <= 0:
        out["alternatives"] = await _alternatives(await _load(shelter_id), 1)
    return out


@router.post("/{shelter_id}/arrivals")
async def arrivals(shelter_id: str, payload: OccupancyChange, request: Request,
                   user: Dict[str, Any] = Depends(SHELTER_MANAGER)):
    if payload.count < 0:
        raise HTTPException(status_code=400, detail="Use /departures for people leaving")
    return await _apply_occupancy(shelter_id, payload, user, request, "SHELTER_ARRIVAL")


@router.post("/{shelter_id}/departures")
async def departures(shelter_id: str, payload: OccupancyChange, request: Request,
                     user: Dict[str, Any] = Depends(SHELTER_MANAGER)):
    body = payload.model_copy(update={"count": -abs(payload.count)})
    return await _apply_occupancy(shelter_id, body, user, request, "SHELTER_DEPARTURE")


class OfflineLogs(BaseModel):
    entries: List[OccupancyChange] = Field(default_factory=list)


@router.post("/{shelter_id}/sync-offline")
async def sync_offline(shelter_id: str, payload: OfflineLogs, request: Request,
                       user: Dict[str, Any] = Depends(SHELTER_MANAGER)):
    """Section 14.6 \u2014 offline arrival/departure logs replay with their original times."""
    applied, rejected = 0, []
    for entry in payload.entries:
        try:
            await _apply_occupancy(shelter_id, entry, user, request, "SHELTER_OFFLINE_SYNC")
            applied += 1
        except HTTPException as exc:
            rejected.append({"count": entry.count, "reason": exc.detail})
    return {"applied": applied, "rejected": rejected,
            "shelter": shelter_view(await _load(shelter_id)),
            "note": "Original timestamps are preserved; rejected entries are reported, not dropped."}


class ShelterStatusUpdate(BaseModel):
    status: ShelterStatus
    reason: Optional[str] = None


@router.post("/{shelter_id}/status")
async def set_status(shelter_id: str, payload: ShelterStatusUpdate, request: Request,
                     user: Dict[str, Any] = Depends(SHELTER_MANAGER)):
    doc = await _load(shelter_id)
    _assert_scope(user, doc)
    try:
        SHELTER.assert_transition(doc.get("status"), payload.status.value)
    except IllegalTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if payload.status == ShelterStatus.CLOSED and not payload.reason:
        raise HTTPException(status_code=400,
                            detail="A closure reason is required so displaced people can be redirected")
    await db.shelters.update_one({"shelterId": shelter_id},
                                 {"$set": {"status": payload.status.value,
                                           "closureReason": payload.reason,
                                           "lastUpdated": now_utc()}})
    await record_audit("SHELTER_STATUS", "SHELTER", shelter_id, {"status": doc.get("status")},
                       {"status": payload.status.value}, user=user, request=request,
                       note=payload.reason)
    out = shelter_view(await _load(shelter_id))
    if payload.status in (ShelterStatus.CLOSED, ShelterStatus.FULL, ShelterStatus.OVER_CAPACITY):
        out["alternatives"] = await _alternatives(doc, 1, limit=5)
        out["note"] = "Occupants and inbound arrivals must be redirected to the listed alternatives."
    return out


class ShelterResourceUpdate(BaseModel):
    foodStatus: Optional[str] = None
    waterStatus: Optional[str] = None
    medicalStatus: Optional[str] = None
    facilities: Optional[List[str]] = None
    contactPhone: Optional[str] = None


@router.patch("/{shelter_id}")
async def update_shelter(shelter_id: str, payload: ShelterResourceUpdate, request: Request,
                         user: Dict[str, Any] = Depends(SHELTER_MANAGER)):
    doc = await _load(shelter_id)
    _assert_scope(user, doc)
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        return shelter_view(doc)
    updates["lastUpdated"] = now_utc()
    await db.shelters.update_one({"shelterId": shelter_id}, {"$set": updates})
    await record_audit("SHELTER_UPDATE", "SHELTER", shelter_id,
                       {k: doc.get(k) for k in updates}, updates, user=user, request=request)
    return shelter_view(await _load(shelter_id))


class RequirementCreate(BaseModel):
    category: str = "FOOD"
    unit: str = "packets"
    requestedQuantity: int
    note: Optional[str] = None


@router.post("/{shelter_id}/requirements")
async def raise_requirement(shelter_id: str, payload: RequirementCreate, request: Request,
                            user: Dict[str, Any] = Depends(SHELTER_MANAGER)):
    """Section 15.1 \u2014 a shelter raises a requirement; approval and fulfilment are separate."""
    doc = await _load(shelter_id)
    _assert_scope(user, doc)
    if payload.requestedQuantity <= 0:
        raise HTTPException(status_code=400, detail="requestedQuantity must be positive")
    req = ResourceRequest(shelterId=shelter_id, eventId=doc.get("eventId"),
                          category=payload.category, unit=payload.unit,
                          requestedQuantity=payload.requestedQuantity)
    rdoc = req.model_dump()
    rdoc["status"] = ResourceStatus.REQUESTED.value
    rdoc["raisedBy"] = user["userId"]
    rdoc["note"] = payload.note
    await db.resource_requests.insert_one(rdoc)
    await record_audit("REQUIREMENT_RAISED", "RESOURCE_REQUEST", rdoc["requestId"], None,
                       {"shelterId": shelter_id, "category": payload.category,
                        "requestedQuantity": payload.requestedQuantity},
                       user=user, request=request, note=payload.note)
    return clean(rdoc)


@router.get("/{shelter_id}/requirements")
async def shelter_requirements(shelter_id: str, user: Dict[str, Any] = Depends(current_user)):
    cur = db.resource_requests.find({"shelterId": shelter_id}).sort("createdAt", -1)
    rows = [clean(d) async for d in cur]
    for r in rows:
        r["outstanding"] = max(int(r.get("requestedQuantity") or 0) - int(r.get("receivedQuantity") or 0), 0)
    return {"requests": rows,
            "note": "requested / approved / allocated / sent / received are tracked separately."}


class Transfer(BaseModel):
    toShelterId: str
    count: int
    reason: str


@router.post("/{shelter_id}/transfer")
async def transfer(shelter_id: str, payload: Transfer, request: Request,
                   user: Dict[str, Any] = Depends(SHELTER_MANAGER)):
    """Section 14.5 \u2014 shelter-to-shelter transfer is one audited operation."""
    src = await _load(shelter_id)
    _assert_scope(user, src)
    dst = await _load(payload.toShelterId)
    if payload.count <= 0:
        raise HTTPException(status_code=400, detail="count must be positive")
    if (src.get("occupancy") or 0) < payload.count:
        raise HTTPException(status_code=409, detail="Source shelter does not have that many occupants recorded")
    reserved = await db.shelters.find_one_and_update(
        {"shelterId": payload.toShelterId,
         "$expr": {"$lte": [{"$add": ["$occupancy", payload.count]}, "$capacity"]}},
        {"$inc": {"occupancy": payload.count}, "$set": {"lastUpdated": now_utc()}},
        return_document=True,
    )
    if not reserved:
        raise HTTPException(status_code=409, detail={
            "message": "Destination shelter cannot accept that many people. Nothing was moved.",
            "alternatives": await _alternatives(dst, payload.count, limit=5),
        })
    await db.shelters.update_one({"shelterId": shelter_id},
                                {"$inc": {"occupancy": -payload.count},
                                 "$set": {"lastUpdated": now_utc()}})
    for sid in (shelter_id, payload.toShelterId):
        fresh = await _load(sid)
        new_status = derive_shelter_status(fresh["capacity"], fresh["occupancy"], fresh.get("status"))
        if new_status != fresh.get("status") and SHELTER.can(fresh.get("status"), new_status):
            await db.shelters.update_one({"shelterId": sid}, {"$set": {"status": new_status}})
    await record_audit("SHELTER_TRANSFER", "SHELTER", shelter_id,
                       {"occupancy": src.get("occupancy")},
                       {"transferred": payload.count, "toShelterId": payload.toShelterId},
                       user=user, request=request, note=payload.reason)
    return {"from": shelter_view(await _load(shelter_id)),
            "to": shelter_view(await _load(payload.toShelterId)),
            "transferred": payload.count,
            "note": "Both shelters were updated in one audited transfer operation."}
