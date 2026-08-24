"""Admin / Authority portal endpoints — Section 17 (+ audit surface for Section 16.4).

Override controls: wherever SETU has an algorithmic recommendation, an AUTHORITY
user can record an explicit override that always wins over the automated
suggestion, and the override itself is audited.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from .. import db
from ..audit import record_audit, recent, timeline
from ..auth import require_roles
from ..models import Role, clean, now_utc, shelter_view
from ..state_machines import SOS_ACTIVE_STATES

router = APIRouter(prefix="/api/admin", tags=["admin"])

ADMIN = require_roles(Role.AUTHORITY, Role.SUPER_ADMIN)


@router.get("/overview")
async def overview(user: Dict[str, Any] = Depends(ADMIN)):
    active_sos = [d async for d in db.sos_records.find({"status": {"$in": SOS_ACTIVE_STATES}})]
    shelters = [shelter_view(d) async for d in db.shelters.find({})]
    return {
        "events": {
            "total": await db.disaster_events.count_documents({}),
            "open": await db.disaster_events.count_documents(
                {"status": {"$nin": ["CLOSED", "CANCELLED"]}}),
            "activeTierC": await db.disaster_events.count_documents(
                {"infoTier": "DISASTER_ACTIVE", "status": {"$in": ["CONFIRMED", "ACTIVE", "RESPONSE"]}}),
        },
        "sos": {
            "active": len(active_sos),
            "p1": sum(1 for s in active_sos if s.get("priority") == "P1"),
            "unassigned": sum(1 for s in active_sos if not s.get("assignedTeamId")),
            "completed": await db.sos_records.count_documents({"status": "COMPLETED"}),
            "cancelled": await db.sos_records.count_documents({"status": "CANCELLED_BY_USER"}),
            "falseAlarm": await db.sos_records.count_documents({"status": "FALSE_ALARM"}),
        },
        "teams": {
            "total": await db.teams.count_documents({}),
            "available": await db.teams.count_documents({"status": "AVAILABLE"}),
        },
        "shelters": {
            "total": len(shelters),
            "capacity": sum(s.get("capacity", 0) for s in shelters),
            "occupancy": sum(s.get("occupancy", 0) for s in shelters),
            "available": sum(s.get("available", 0) for s in shelters),
            "full": sum(1 for s in shelters if s.get("status") in ("FULL", "OVER_CAPACITY")),
            "stale": sum(1 for s in shelters if s.get("stale")),
        },
        "resourceRequests": {
            "total": await db.resource_requests.count_documents({}),
            "discrepancy": await db.resource_requests.count_documents({"status": "DISCREPANCY"}),
        },
        "auditEntries": await db.audit_log.count_documents({}),
        "generatedAt": now_utc(),
    }


@router.get("/audit")
async def audit_feed(limit: int = 100, objectType: Optional[str] = None,
                     action: Optional[str] = None, userId: Optional[str] = None,
                     user: Dict[str, Any] = Depends(ADMIN)):
    return {"entries": await recent(limit=min(limit, 500), object_type=objectType,
                                    action=action, user_id=userId)}


@router.get("/audit/{object_type}/{object_id}")
async def audit_object(object_type: str, object_id: str,
                       user: Dict[str, Any] = Depends(ADMIN)):
    return {"objectType": object_type, "objectId": object_id,
            "timeline": await timeline(object_type.upper(), object_id)}


class Override(BaseModel):
    objectType: str          # SOS | SHELTER | TEAM | RESOURCE_REQUEST | DISASTER_EVENT
    objectId: str
    field: str
    newValue: Any
    reason: str


COLLECTION_FOR = {
    "SOS": (lambda: db.sos_records, "sosId"),
    "SHELTER": (lambda: db.shelters, "shelterId"),
    "TEAM": (lambda: db.teams, "teamId"),
    "RESOURCE_REQUEST": (lambda: db.resource_requests, "requestId"),
    "DISASTER_EVENT": (lambda: db.disaster_events, "eventId"),
}


@router.post("/override")
async def authority_override(payload: Override, request: Request,
                             user: Dict[str, Any] = Depends(ADMIN)):
    """Section 17.3 — an explicit human override always wins over an automated
    recommendation, and is recorded as such."""
    entry = COLLECTION_FOR.get(payload.objectType.upper())
    if not entry:
        raise HTTPException(status_code=400,
                            detail=f"objectType must be one of {sorted(COLLECTION_FOR)}")
    coll_getter, key = entry
    coll = coll_getter()
    doc = await coll.find_one({key: payload.objectId})
    if not doc:
        raise HTTPException(status_code=404, detail=f"{payload.objectType} {payload.objectId} not found")
    old = doc.get(payload.field)
    await coll.update_one({key: payload.objectId},
                          {"$set": {payload.field: payload.newValue,
                                    "authorityOverride": {"by": user["userId"], "at": now_utc(),
                                                          "field": payload.field,
                                                          "reason": payload.reason},
                                    "updatedAt": now_utc()}})
    await record_audit("AUTHORITY_OVERRIDE", payload.objectType.upper(), payload.objectId,
                       {payload.field: old}, {payload.field: payload.newValue},
                       user=user, request=request, note=payload.reason)
    return {"object": clean(await coll.find_one({key: payload.objectId})),
            "overrideApplied": True,
            "note": "Authority override recorded — it takes precedence over automated recommendations."}


@router.get("/false-alarm-review")
async def false_alarm_review(user: Dict[str, Any] = Depends(ADMIN)):
    """Repeated false SOS from one user is flagged for review, never deleted."""
    pipeline = [
        {"$match": {"status": "FALSE_ALARM"}},
        {"$group": {"_id": "$userId", "count": {"$sum": 1}, "sosIds": {"$push": "$sosId"}}},
        {"$sort": {"count": -1}},
    ]
    rows: List[Dict[str, Any]] = []
    async for r in db.audit_log.database["sos_records"].aggregate(pipeline):
        rows.append({"userId": r["_id"], "falseAlarmCount": r["count"], "sosIds": r["sosIds"],
                     "flaggedForReview": r["count"] >= 3})
    return {"users": rows,
            "note": "False SOS records are retained and reported — they are never deleted."}
