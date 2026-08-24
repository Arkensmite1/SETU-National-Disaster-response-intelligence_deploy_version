"""Phase 8 — Data integrity & conflict handling (Section 16).

Rules encoded here:
* Two contradictory field reports are stored SIDE BY SIDE with reporter, time and
  confidence. SETU never silently picks a winner.
* Stale data is labelled with its age everywhere it is shown.
* Concurrent edits are rejected with both values returned, never merged blindly.
* A human resolution is recorded as a decision, and the discarded values are kept.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .. import db
from ..audit import record_audit
from ..auth import current_user, require_roles
from ..models import Location, Role, clean, loc_doc, now_utc, shelter_view

router = APIRouter(prefix="/api/integrity", tags=["integrity"])

REPORTERS = require_roles(Role.RESCUE_MEMBER, Role.RESCUE_LEADER, Role.SHELTER_ADMIN,
                          Role.NGO_ADMIN, Role.AUTHORITY, Role.SUPER_ADMIN)
ADMIN_ONLY = require_roles(Role.AUTHORITY, Role.SUPER_ADMIN)

STALE_MINUTES = {"SHELTER": 60, "SOS": 30, "DISASTER_EVENT": 180, "TEAM": 20,
                 "RESOURCE_REQUEST": 240}


def staleness(ts: Optional[datetime], object_type: str) -> Dict[str, Any]:
    if not isinstance(ts, datetime):
        return {"ageMinutes": None, "stale": True,
                "notice": "No update timestamp available — treat this value as unverified"}
    ts = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    mins = (now_utc() - ts).total_seconds() / 60
    limit = STALE_MINUTES.get(object_type, 60)
    return {"ageMinutes": round(mins, 1), "stale": mins > limit, "thresholdMinutes": limit,
            "notice": (f"DATA STALE — last updated {int(mins)} min ago (threshold {limit} min)"
                       if mins > limit else f"Last updated {int(mins)} min ago")}


class FieldReport(BaseModel):
    objectType: str            # SHELTER | SOS | DISASTER_EVENT | ROAD | AREA
    objectId: str
    field: str
    value: Any
    confidence: str = "MEDIUM"   # LOW | MEDIUM | HIGH
    location: Optional[Location] = None
    note: Optional[str] = None


@router.post("/field-reports")
async def submit_field_report(payload: FieldReport, request: Request,
                              user: Dict[str, Any] = Depends(REPORTERS)):
    doc = {
        "reportId": f"FR-{int(now_utc().timestamp() * 1000)}",
        "objectType": payload.objectType.upper(), "objectId": payload.objectId,
        "field": payload.field, "value": payload.value, "confidence": payload.confidence,
        "location": loc_doc(payload.location), "note": payload.note,
        "reportedBy": user["userId"], "reporterRole": user.get("role"),
        "reportedAt": now_utc(), "superseded": False,
    }
    await db.field_reports.insert_one(doc)
    await record_audit("FIELD_REPORT", payload.objectType.upper(), payload.objectId, None,
                       {payload.field: payload.value, "confidence": payload.confidence},
                       user=user, request=request, note=payload.note)

    siblings = [clean(d) async for d in db.field_reports.find(
        {"objectType": payload.objectType.upper(), "objectId": payload.objectId,
         "field": payload.field}).sort("reportedAt", -1)]
    distinct = {str(s["value"]) for s in siblings}
    conflict = None
    if len(distinct) > 1:
        conflict_doc = {
            "conflictId": f"CF-{payload.objectType.upper()}-{payload.objectId}-{payload.field}",
            "objectType": payload.objectType.upper(), "objectId": payload.objectId,
            "field": payload.field,
            "values": [{"value": s["value"], "reportedBy": s["reportedBy"],
                        "reporterRole": s.get("reporterRole"), "confidence": s.get("confidence"),
                        "at": s["reportedAt"]} for s in siblings],
            "status": "OPEN", "createdAt": now_utc(),
        }
        await db.conflicts.update_one({"conflictId": conflict_doc["conflictId"]},
                                      {"$set": conflict_doc}, upsert=True)
        conflict = clean(conflict_doc)
    return {
        "report": clean(doc),
        "allReportsForField": siblings,
        "conflict": conflict,
        "note": ("Contradictory reports are kept side by side with reporter and time. SETU does not "
                 "pick a winner — a human resolves it.") if conflict else
                "Report recorded. Existing reports for this field agree.",
    }


@router.get("/field-reports")
async def list_field_reports(objectType: Optional[str] = None, objectId: Optional[str] = None,
                             user: Dict[str, Any] = Depends(REPORTERS)):
    q: Dict[str, Any] = {}
    if objectType:
        q["objectType"] = objectType.upper()
    if objectId:
        q["objectId"] = objectId
    cur = db.field_reports.find(q).sort("reportedAt", -1).limit(200)
    return {"reports": [clean(d) async for d in cur]}


@router.get("/conflicts")
async def list_conflicts(status: Optional[str] = "OPEN",
                         user: Dict[str, Any] = Depends(REPORTERS)):
    q = {"status": status} if status else {}
    rows = [clean(d) async for d in db.conflicts.find(q).sort("createdAt", -1)]
    shelter_conflicts = [shelter_view(d) async for d in
                         db.shelters.find({"occupancyConflict.resolved": False})]
    discrepancies = [clean(d) async for d in db.resource_requests.find({"status": "DISCREPANCY"})]
    return {
        "conflicts": rows,
        "shelterOccupancyConflicts": shelter_conflicts,
        "resourceDiscrepancies": discrepancies,
        "totalOpen": len(rows) + len(shelter_conflicts) + len(discrepancies),
        "note": "Every conflicting value is retained. Nothing is overwritten automatically.",
    }


class ResolveConflict(BaseModel):
    chosenValue: Any
    reason: str
    applyToRecord: bool = False


COLLECTION_FOR = {
    "SHELTER": (lambda: db.shelters, "shelterId"),
    "SOS": (lambda: db.sos_records, "sosId"),
    "TEAM": (lambda: db.teams, "teamId"),
    "DISASTER_EVENT": (lambda: db.disaster_events, "eventId"),
    "RESOURCE_REQUEST": (lambda: db.resource_requests, "requestId"),
}


@router.post("/conflicts/{conflict_id}/resolve")
async def resolve_conflict(conflict_id: str, payload: ResolveConflict, request: Request,
                           user: Dict[str, Any] = Depends(ADMIN_ONLY)):
    doc = await db.conflicts.find_one({"conflictId": conflict_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Conflict not found")
    await db.conflicts.update_one(
        {"conflictId": conflict_id},
        {"$set": {"status": "RESOLVED", "chosenValue": payload.chosenValue,
                  "resolution": payload.reason, "resolvedBy": user["userId"],
                  "resolvedAt": now_utc(),
                  "discardedValues": [v for v in doc.get("values", [])
                                      if str(v.get("value")) != str(payload.chosenValue)]}})
    applied = False
    if payload.applyToRecord:
        entry = COLLECTION_FOR.get(doc.get("objectType"))
        if entry:
            coll_getter, key = entry
            await coll_getter().update_one({key: doc["objectId"]},
                                           {"$set": {doc["field"]: payload.chosenValue,
                                                     "updatedAt": now_utc()}})
            applied = True
    if doc.get("objectType") == "SHELTER":
        await db.shelters.update_one({"shelterId": doc["objectId"]},
                                     {"$set": {"occupancyConflict.resolved": True}})
    await record_audit("CONFLICT_RESOLVED", doc.get("objectType"), doc.get("objectId"),
                       {"values": doc.get("values")},
                       {"chosenValue": payload.chosenValue, "appliedToRecord": applied},
                       user=user, request=request, note=payload.reason)
    return {"conflict": clean(await db.conflicts.find_one({"conflictId": conflict_id})),
            "appliedToRecord": applied,
            "note": "Human decision recorded. Discarded values are retained for the audit trail."}


@router.get("/data-quality")
async def data_quality(user: Dict[str, Any] = Depends(REPORTERS)):
    """Section 16.1/16.5 — what SETU does NOT know is stated explicitly."""
    shelters = [shelter_view(d) async for d in db.shelters.find({})]
    stale_shelters = [s for s in shelters if s.get("stale")]
    teams_no_location = [clean(t) async for t in db.teams.find({"currentLocation": None})]
    approx_sos = [clean(s) async for s in db.sos_records.find(
        {"origin.source": {"$in": ["NETWORK", "LAST_KNOWN", "MANUAL", "LANDMARK"]},
         "status": {"$nin": ["COMPLETED", "CANCELLED_BY_USER", "DUPLICATE"]}})]
    events_stale = []
    async for e in db.disaster_events.find({"status": {"$nin": ["CLOSED", "CANCELLED"]}}):
        st = staleness(e.get("updatedAt"), "DISASTER_EVENT")
        if st["stale"]:
            events_stale.append({"eventId": e["eventId"], "title": e.get("title"), **st})
    return {
        "staleShelterRecords": [{"shelterId": s["shelterId"], "name": s["name"],
                                 "notice": s.get("stalenessNotice")} for s in stale_shelters],
        "staleEvents": events_stale,
        "teamsWithoutLocation": [{"teamId": t["teamId"], "name": t.get("name")} for t in teams_no_location],
        "activeSosWithApproximateLocation": [
            {"sosId": s["sosId"], "source": (s.get("origin") or {}).get("source"),
             "accuracy": (s.get("origin") or {}).get("accuracy")} for s in approx_sos],
        "openConflicts": await db.conflicts.count_documents({"status": "OPEN"}),
        "knownUnknowns": [
            "Areas with no SOS and no team report are UNKNOWN, not safe.",
            "Shelter figures older than 60 minutes are treated as unverified.",
            "Approximate locations are shown as approximate to every rescue user.",
        ],
    }
