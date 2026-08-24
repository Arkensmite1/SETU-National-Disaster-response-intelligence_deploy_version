"""Phase 10 \u2014 Authority controls and reporting (Section 17).

Rules encoded here:
* A situation report states what is KNOWN and what is UNKNOWN. Data gaps are
  printed explicitly instead of being rounded to zero.
* Resource reallocation between shelters is one audited decision with a reason.
* Cross-district coordination surfaces mutual-aid options as advisory options for
  a human to act on.
* Escalations are recorded with level, reason and actor.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from .. import db
from ..audit import record_audit, recent
from ..auth import require_roles
from ..models import Role, clean, now_utc, shelter_view
from ..state_machines import SOS_ACTIVE_STATES

router = APIRouter(prefix="/api/authority", tags=["authority"])

ADMIN_ONLY = require_roles(Role.AUTHORITY, Role.SUPER_ADMIN)


@router.get("/situation-report")
async def situation_report(eventId: Optional[str] = None,
                           user: Dict[str, Any] = Depends(ADMIN_ONLY)):
    sos_q: Dict[str, Any] = {"eventId": eventId} if eventId else {}
    all_sos = [clean(d) async for d in db.sos_records.find(sos_q)]
    active = [s for s in all_sos if s.get("status") in SOS_ACTIVE_STATES]
    completed = [s for s in all_sos if s.get("status") == "COMPLETED"]
    rescued_people = sum(int((s.get("completionReport") or {}).get("peopleRescued") or 0)
                         for s in completed)
    fatalities = sum(int((s.get("completionReport") or {}).get("fatalities") or 0)
                     for s in completed)
    shelters = [shelter_view(d) async for d in db.shelters.find({})]
    events = [clean(d) async for d in db.disaster_events.find(
        {"eventId": eventId} if eventId else {"status": {"$nin": ["CLOSED", "CANCELLED"]}})]
    teams = [clean(t) async for t in db.teams.find({})]
    searches = [clean(s) async for s in db.search_operations.find({})]
    open_missing = await db.missing_register.count_documents({"status": "OPEN"})
    field_incidents = [clean(f) async for f in db.field_incidents.find({})]
    open_conflicts = await db.conflicts.count_documents({"status": "OPEN"})
    discrepancies = await db.resource_requests.count_documents({"status": "DISCREPANCY"})

    unknowns: List[str] = []
    if any(s.get("stale") for s in shelters):
        unknowns.append(f"{sum(1 for s in shelters if s.get('stale'))} shelter record(s) are older "
                        "than the freshness threshold \u2014 occupancy figures are unverified.")
    approx = [s for s in active if (s.get("origin") or {}).get("source") in
              ("NETWORK", "LAST_KNOWN", "MANUAL", "LANDMARK")]
    if approx:
        unknowns.append(f"{len(approx)} active SOS have approximate locations only.")
    if open_missing:
        unknowns.append(f"{open_missing} missing-person entry(ies) remain unresolved \u2014 not located "
                        "is not the same as safe.")
    no_loc_teams = [t for t in teams if not t.get("currentLocation")]
    if no_loc_teams:
        unknowns.append(f"{len(no_loc_teams)} team(s) have no current location reported.")
    if open_conflicts:
        unknowns.append(f"{open_conflicts} unresolved data conflict(s) awaiting an authority decision.")
    if not all_sos:
        unknowns.append("No SOS has been received for this scope. Areas with no reports are "
                        "UNKNOWN, not confirmed safe.")

    report = {
        "reportId": f"SITREP-{int(now_utc().timestamp())}",
        "generatedAt": now_utc(),
        "scope": {"eventId": eventId or "ALL_OPEN_EVENTS"},
        "events": [{"eventId": e["eventId"], "title": e.get("title"), "status": e.get("status"),
                    "infoTier": e.get("infoTier"), "severity": e.get("severity"),
                    "version": e.get("version"), "source": e.get("source")} for e in events],
        "rescue": {
            "sosTotal": len(all_sos), "sosActive": len(active), "sosCompleted": len(completed),
            "byPriority": {p: sum(1 for s in active if s.get("priority") == p)
                           for p in ("P1", "P2", "P3")},
            "unassigned": sum(1 for s in active if not s.get("assignedTeamId")),
            "peopleRescued": rescued_people, "fatalitiesReported": fatalities,
            "cancelledByUser": sum(1 for s in all_sos if s.get("status") == "CANCELLED_BY_USER"),
            "falseAlarms": sum(1 for s in all_sos if s.get("status") == "FALSE_ALARM"),
            "duplicatesMerged": sum(int(s.get("retryCount") or 0) for s in all_sos),
        },
        "search": {
            "operations": len(searches),
            "inProgress": sum(1 for s in searches if s.get("status") == "IN_PROGRESS"),
            "closedNotFound": sum(1 for s in searches if s.get("status") == "CLOSED_NOT_FOUND"),
            "openMissingEntries": open_missing,
            "unknownPersonsFoundInField": sum(int(f.get("unknownPersons") or 0)
                                              for f in field_incidents),
        },
        "teams": {"total": len(teams),
                  "available": sum(1 for t in teams if t.get("status") == "AVAILABLE"),
                  "engaged": sum(1 for t in teams if t.get("status") not in ("AVAILABLE", "OFFLINE"))},
        "shelters": {
            "count": len(shelters),
            "capacity": sum(s["capacity"] for s in shelters),
            "occupancy": sum(s["occupancy"] for s in shelters),
            "available": sum(s["available"] for s in shelters),
            "full": sum(1 for s in shelters if s["status"] in ("FULL", "OVER_CAPACITY")),
            "closed": sum(1 for s in shelters if s["status"] == "CLOSED"),
            "staleRecords": sum(1 for s in shelters if s.get("stale")),
        },
        "relief": {
            "requests": await db.resource_requests.count_documents({}),
            "openDiscrepancies": discrepancies,
        },
        "dataGaps": unknowns,
        "integrityNote": ("Figures reflect data received so far. Missing data is reported as "
                          "unknown \u2014 never as zero need or as safety."),
    }
    await db.situation_reports.insert_one({**report, "generatedBy": user["userId"]})
    await record_audit("SITREP_GENERATED", "SITUATION_REPORT", report["reportId"], None,
                       {"eventId": eventId}, user=user)
    return report


@router.get("/situation-reports")
async def list_sitreps(limit: int = 20, user: Dict[str, Any] = Depends(ADMIN_ONLY)):
    cur = db.situation_reports.find({}).sort("generatedAt", -1).limit(min(limit, 100))
    return {"reports": [clean(d) async for d in cur]}


class Reallocate(BaseModel):
    fromRequestId: str
    toShelterId: str
    quantity: int
    reason: str


@router.post("/reallocate")
async def reallocate(payload: Reallocate, request: Request,
                     user: Dict[str, Any] = Depends(ADMIN_ONLY)):
    """Section 17.2 \u2014 move committed relief to a higher-need shelter as one audited act."""
    src = await db.resource_requests.find_one({"requestId": payload.fromRequestId})
    if not src:
        raise HTTPException(status_code=404, detail="Source request not found")
    dst_shelter = await db.shelters.find_one({"shelterId": payload.toShelterId})
    if not dst_shelter:
        raise HTTPException(status_code=404, detail="Destination shelter not found")
    available = int(src.get("allocatedQuantity") or 0) - int(src.get("sentQuantity") or 0)
    if payload.quantity <= 0 or payload.quantity > max(available, 0):
        raise HTTPException(status_code=409, detail={
            "message": (f"Only {max(available, 0)} unit(s) of this allocation are still "
                        "unshipped and can be reallocated."),
            "allocated": src.get("allocatedQuantity"), "sent": src.get("sentQuantity")})
    new_req = {
        "requestId": f"REQ-RA-{int(now_utc().timestamp())}",
        "shelterId": payload.toShelterId, "eventId": src.get("eventId"),
        "category": src.get("category"), "unit": src.get("unit"),
        "requestedQuantity": payload.quantity, "approvedQuantity": payload.quantity,
        "allocatedQuantity": payload.quantity, "sentQuantity": 0, "receivedQuantity": 0,
        "status": "ALLOCATED", "ngoId": src.get("ngoId"), "ngoName": src.get("ngoName"),
        "createdAt": now_utc(), "updatedAt": now_utc(), "discrepancy": None,
        "reallocatedFrom": payload.fromRequestId, "reallocationReason": payload.reason,
        "authorityDecision": {"by": user["userId"], "at": now_utc(), "reason": payload.reason},
    }
    await db.resource_requests.insert_one(new_req)
    await db.resource_requests.update_one(
        {"requestId": payload.fromRequestId},
        {"$inc": {"allocatedQuantity": -payload.quantity},
         "$set": {"updatedAt": now_utc(),
                  "reallocationNote": (f"{payload.quantity} {src.get('unit')} reallocated to "
                                       f"{payload.toShelterId} by authority: {payload.reason}")}})
    await record_audit("RESOURCE_REALLOCATED", "RESOURCE_REQUEST", payload.fromRequestId,
                       {"allocatedQuantity": src.get("allocatedQuantity")},
                       {"movedQuantity": payload.quantity, "toShelterId": payload.toShelterId,
                        "newRequestId": new_req["requestId"]},
                       user=user, request=request, note=payload.reason)
    await db.notifications.insert_one({
        "notificationId": f"NT-RA-{int(now_utc().timestamp() * 1000)}",
        "to": payload.toShelterId, "toRole": Role.SHELTER_ADMIN.value, "priority": 2,
        "type": "RESOURCE_REALLOCATION",
        "message": (f"{payload.quantity} {src.get('unit')} of {src.get('category')} reallocated to "
                    f"your shelter by authority decision: {payload.reason}"),
        "objectType": "RESOURCE_REQUEST", "objectId": new_req["requestId"],
        "createdAt": now_utc(), "delivered": False, "acknowledged": False, "escalated": False,
    })
    return {"newRequest": clean(new_req),
            "sourceRequest": clean(await db.resource_requests.find_one({"requestId": payload.fromRequestId})),
            "note": "Both records retain the full history of the reallocation."}


@router.get("/cross-district")
async def cross_district(user: Dict[str, Any] = Depends(ADMIN_ONLY)):
    """Section 17.4 \u2014 regional rollup with advisory mutual-aid options."""
    regions: Dict[str, Dict[str, Any]] = {}

    def bucket(name: Optional[str]) -> Dict[str, Any]:
        key = name or "UNASSIGNED_REGION"
        return regions.setdefault(key, {"region": key, "activeSos": 0, "p1": 0, "teamsTotal": 0,
                                        "teamsAvailable": 0, "shelterCapacity": 0,
                                        "shelterOccupancy": 0, "shelterAvailable": 0,
                                        "openRequirements": 0})

    events_by_region: Dict[str, List[str]] = {}
    async for e in db.disaster_events.find({"status": {"$nin": ["CLOSED", "CANCELLED"]}}):
        events_by_region.setdefault(e.get("region") or "UNASSIGNED_REGION", []).append(e["eventId"])
        bucket(e.get("region"))

    event_region = {}
    for region, ids in events_by_region.items():
        for i in ids:
            event_region[i] = region
    async for s in db.sos_records.find({"status": {"$in": SOS_ACTIVE_STATES}}):
        b = bucket(event_region.get(s.get("eventId")))
        b["activeSos"] += 1
        if s.get("priority") == "P1":
            b["p1"] += 1
    async for t in db.teams.find({}):
        b = bucket(t.get("region"))
        b["teamsTotal"] += 1
        if t.get("status") == "AVAILABLE":
            b["teamsAvailable"] += 1
    async for sh in db.shelters.find({}):
        v = shelter_view(sh)
        b = bucket(sh.get("region"))
        b["shelterCapacity"] += v["capacity"]
        b["shelterOccupancy"] += v["occupancy"]
        b["shelterAvailable"] += v["available"]
    async for r in db.resource_requests.find({"status": {"$in": ["REQUESTED", "APPROVED"]}}):
        sh = await db.shelters.find_one({"shelterId": r.get("shelterId")})
        bucket((sh or {}).get("region"))["openRequirements"] += 1

    rows = list(regions.values())
    suggestions = []
    strained = [r for r in rows if r["activeSos"] > 0 and r["teamsAvailable"] == 0]
    donors = [r for r in rows if r["teamsAvailable"] > 0 and r["activeSos"] == 0]
    for s in strained:
        for d in donors:
            suggestions.append({
                "type": "TEAM_MUTUAL_AID",
                "fromRegion": d["region"], "toRegion": s["region"],
                "detail": (f"{d['region']} has {d['teamsAvailable']} available team(s) with no active "
                           f"SOS; {s['region']} has {s['activeSos']} active SOS and no available team."),
                "advisory": True, "requiresHumanConfirmation": True,
            })
    for s in rows:
        if s["shelterAvailable"] <= 0 and s["shelterCapacity"] > 0:
            for d in rows:
                if d["region"] != s["region"] and d["shelterAvailable"] > 0:
                    suggestions.append({
                        "type": "SHELTER_MUTUAL_AID",
                        "fromRegion": d["region"], "toRegion": s["region"],
                        "detail": (f"{s['region']} shelters are full; {d['region']} has "
                                   f"{d['shelterAvailable']} place(s) available."),
                        "advisory": True, "requiresHumanConfirmation": True,
                    })
    return {"regions": rows, "mutualAidSuggestions": suggestions[:10],
            "note": ("Suggestions are advisory. Cross-district movement is an authority decision "
                     "and is audited when executed.")}


class Escalation(BaseModel):
    objectType: str
    objectId: str
    level: str            # DISTRICT | STATE | NATIONAL
    reason: str


@router.post("/escalate")
async def escalate(payload: Escalation, request: Request,
                   user: Dict[str, Any] = Depends(ADMIN_ONLY)):
    if payload.level not in ("DISTRICT", "STATE", "NATIONAL"):
        raise HTTPException(status_code=400, detail="level must be DISTRICT, STATE or NATIONAL")
    doc = {
        "escalationId": f"ESC-{int(now_utc().timestamp())}",
        "objectType": payload.objectType.upper(), "objectId": payload.objectId,
        "level": payload.level, "reason": payload.reason,
        "raisedBy": user["userId"], "raisedAt": now_utc(), "status": "OPEN",
    }
    await db.notifications.insert_one({
        "notificationId": f"NT-{doc['escalationId']}",
        "to": "USR-ADMIN-001", "toRole": Role.SUPER_ADMIN.value, "priority": 1,
        "type": "ESCALATION",
        "message": (f"{payload.level} escalation raised for {payload.objectType} "
                    f"{payload.objectId}: {payload.reason}"),
        "objectType": payload.objectType.upper(), "objectId": payload.objectId,
        "createdAt": now_utc(), "delivered": False, "acknowledged": False, "escalated": False,
    })
    await record_audit("ESCALATION_RAISED", payload.objectType.upper(), payload.objectId, None,
                       {"level": payload.level}, user=user, request=request, note=payload.reason)
    return {"escalation": doc,
            "note": "Escalation recorded and routed to the next level with full context."}


@router.get("/decision-log")
async def decision_log(limit: int = 100, user: Dict[str, Any] = Depends(ADMIN_ONLY)):
    """Only human decisions and overrides \u2014 the accountability view (Section 17.5)."""
    actions = {"AUTHORITY_OVERRIDE", "EVENT_TRANSITION", "CONFLICT_RESOLVED",
               "RESOURCE_REALLOCATED", "ESCALATION_RAISED", "RESOURCE_APPROVED",
               "RESOURCE_REJECTED", "RESOURCE_DISCREPANCY_RESOLVED", "SITREP_GENERATED",
               "MISSING_REGISTER_RESOLVED"}
    entries = [e for e in await recent(limit=500) if e.get("action") in actions][:limit]
    return {"decisions": entries,
            "note": "Every entry names the human who made the decision and the reason recorded."}
