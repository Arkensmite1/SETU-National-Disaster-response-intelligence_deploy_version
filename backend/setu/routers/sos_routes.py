"""SOS system \u2014 Section 11 end to end + assignment lifecycle (12.7/12.8).

Guarantees encoded here:
* "sent" != "acknowledged" != "rescued": distinct states, and the API never
  claims a rescue team was notified until a leader actually assigns one.
* Location fallback chain is respected; poor accuracy is surfaced, never hidden.
* Duplicate SOS updates the existing case (retryCount++) instead of creating a
  second case; cancellations and false alarms keep the full audit trail.
* One SOS may represent many people (peopleCount / injuredCount / composition).
* Team claim + assignment are atomic so two leaders cannot claim one team.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .. import db
from ..audit import record_audit
from ..auth import current_user, is_admin, require_roles
from ..geo import haversine_km, point_in_polygon
from ..models import (DisasterType, Location, NetworkMode, Role, SOSRecord, SOSStatus,
                      TeamStatus, clean, loc_doc, now_utc)
from ..priority import PRIORITY_ORDER, classify_priority, recommended_team_size
from ..state_machines import (IllegalTransition, SOS, SOS_ACTIVE_STATES, SOS_TO_TEAM_STATE,
                              TEAM, TEAM_SETTABLE_SOS_STATES)

router = APIRouter(prefix="/api/sos", tags=["sos"])

DUP_RADIUS_KM = 0.2
DUP_WINDOW_MINUTES = 15
ASSIGNMENT_TIMEOUT_MINUTES = 5

REJECTION_REASONS = {"EQUIPMENT_UNAVAILABLE", "ALREADY_ENGAGED", "ROUTE_INACCESSIBLE",
                     "TOO_FAR", "UNSAFE_CONDITIONS", "OTHER"}


# ---------------------------------------------------------------- payloads
class SOSCreate(BaseModel):
    location: Location
    eventId: Optional[str] = None
    disasterType: Optional[DisasterType] = None
    peopleCount: int = 1
    injuredCount: int = 0
    childrenCount: int = 0
    elderlyCount: int = 0
    emergencyType: str = "TRAPPED"
    description: Optional[str] = None
    networkStatus: NetworkMode = NetworkMode.FULL
    batteryStatus: Optional[int] = None
    photoBase64: Optional[str] = None
    voiceNoteBase64: Optional[str] = None
    landmark: Optional[str] = None
    accessibilityRequirement: Optional[str] = None
    contactName: Optional[str] = None
    contactPhone: Optional[str] = None
    clientCreatedAt: Optional[datetime] = None      # offline queue: original press time
    clientRef: Optional[str] = None                 # local queue id for idempotency


class SOSSyncBatch(BaseModel):
    items: List[SOSCreate] = Field(default_factory=list)


class StatusUpdate(BaseModel):
    status: SOSStatus
    note: Optional[str] = None
    location: Optional[Location] = None


class AssignRequest(BaseModel):
    teamId: str
    note: Optional[str] = None
    overrideRecommendation: bool = False


class RejectRequest(BaseModel):
    reason: str
    note: Optional[str] = None


class CompletionReport(BaseModel):
    peopleRescued: int = 0
    injuredTransported: int = 0
    fatalities: int = 0
    handedOverTo: Optional[str] = None          # shelter / hospital / authority
    shelterId: Optional[str] = None
    victimConfirmation: bool = True             # false for unconscious victims (11.9)
    victimConfirmationWaivedReason: Optional[str] = None
    equipmentUsed: List[str] = Field(default_factory=list)
    observations: Optional[str] = None


class LocationUpdate(BaseModel):
    location: Location


# ---------------------------------------------------------------- helpers
def _sos_view(doc: Dict[str, Any]) -> Dict[str, Any]:
    d = clean(doc)
    origin = d.get("origin") or {}
    acc = origin.get("accuracy")
    src = origin.get("source")
    approximate = src in ("NETWORK", "LAST_KNOWN", "MANUAL", "LANDMARK") or acc is None or acc > 100
    d["locationQuality"] = {
        "source": src,
        "accuracyMetres": acc,
        "approximate": approximate,
        "label": "Approximate location" if approximate else "Precise GPS location",
    }
    d["acknowledged"] = bool(d.get("acknowledgedAt"))
    d["rescueTeamNotified"] = bool(d.get("assignedTeamId"))
    d["allowedNextStates"] = sorted(SOS.allowed_from(d.get("status", "CREATED")))
    return d


async def _load(sos_id: str) -> Dict[str, Any]:
    doc = await db.sos_records.find_one({"sosId": sos_id})
    if not doc:
        raise HTTPException(status_code=404, detail="SOS record not found")
    return doc


async def _can_view(user: Dict[str, Any], sos: Dict[str, Any]) -> bool:
    role = user.get("role")
    if is_admin(user) or role == Role.RESCUE_LEADER.value:
        return True
    if role == Role.USER.value:
        return sos.get("userId") == user.get("userId")
    if role == Role.RESCUE_MEMBER.value:
        return bool(user.get("teamId")) and sos.get("assignedTeamId") == user.get("teamId")
    return False


async def _transition(sos: Dict[str, Any], target: str, user: Dict[str, Any],
                      request: Optional[Request] = None, note: Optional[str] = None,
                      extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    current = sos.get("status")
    try:
        SOS.assert_transition(current, target)
    except IllegalTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    updates: Dict[str, Any] = {"status": target, "updatedAt": now_utc()}
    if extra:
        updates.update(extra)
    if target == SOSStatus.RECEIVED.value and not sos.get("acknowledgedAt"):
        updates["acknowledgedAt"] = now_utc()
    if target == SOSStatus.COMPLETED.value:
        updates["liveLocationSharing"] = False       # 21.2 stop live sharing on closure
    await db.sos_records.update_one({"sosId": sos["sosId"]}, {"$set": updates})
    await record_audit("SOS_STATUS", "SOS", sos["sosId"], {"status": current},
                       {"status": target}, user=user, request=request, note=note)
    doc = await db.sos_records.find_one({"sosId": sos["sosId"]})
    return doc


async def _sync_team_state(team_id: Optional[str], sos_status: str, user: Dict[str, Any],
                           request: Optional[Request] = None, release: bool = False):
    if not team_id:
        return
    team = await db.teams.find_one({"teamId": team_id})
    if not team:
        return
    target = TeamStatus.AVAILABLE.value if release else SOS_TO_TEAM_STATE.get(sos_status)
    if not target or target == team.get("status"):
        return
    if not TEAM.can(team.get("status"), target):
        return
    updates: Dict[str, Any] = {"status": target, "updatedAt": now_utc()}
    if target == TeamStatus.AVAILABLE.value:
        updates["activeSosId"] = None
    await db.teams.update_one({"teamId": team_id}, {"$set": updates})
    await record_audit("TEAM_STATUS", "TEAM", team_id, {"status": team.get("status")},
                       {"status": target}, user=user, request=request)


async def _match_event(loc: Location) -> Optional[Dict[str, Any]]:
    """Attach the SOS to an active event whose polygon contains the location.
    No matching event never blocks an SOS (rule #1)."""
    cur = db.disaster_events.find({"status": {"$in": ["CONFIRMED", "ACTIVE", "RESPONSE", "WARNING"]}})
    fallback = None
    async for doc in cur:
        if point_in_polygon(loc.latitude, loc.longitude, doc.get("affectedArea")):
            if doc.get("infoTier") == "DISASTER_ACTIVE":
                return doc
            fallback = fallback or doc
    return fallback


async def _find_duplicate(user_id: str, event_id: Optional[str], loc: Location) -> Optional[Dict[str, Any]]:
    """Section 11.4 \u2014 same user + same event + same location + short interval."""
    since = now_utc() - timedelta(minutes=DUP_WINDOW_MINUTES)
    q = {"userId": user_id, "status": {"$in": SOS_ACTIVE_STATES}}
    cur = db.sos_records.find(q).sort("createdAt", -1).limit(10)
    async for doc in cur:
        created = doc.get("createdAt")
        if isinstance(created, datetime):
            created = created if created.tzinfo else created.replace(tzinfo=timezone.utc)
            if created < since:
                continue
        if event_id and doc.get("eventId") and doc.get("eventId") != event_id:
            continue
        o = doc.get("origin") or {}
        if o and haversine_km(loc.latitude, loc.longitude, o["latitude"], o["longitude"]) <= DUP_RADIUS_KM:
            return doc
    return None


async def _create_sos(payload: SOSCreate, user: Dict[str, Any], request: Optional[Request],
                      offline: bool = False) -> Dict[str, Any]:
    event = None
    if payload.eventId:
        event = await db.disaster_events.find_one({"eventId": payload.eventId})
    if not event:
        event = await _match_event(payload.location)

    # ---- duplicate detection (11.4)
    existing = await _find_duplicate(user["userId"], event["eventId"] if event else None, payload.location)
    if existing:
        await db.sos_records.update_one(
            {"sosId": existing["sosId"]},
            {"$inc": {"retryCount": 1},
             "$set": {"lastKnown": loc_doc(payload.location), "updatedAt": now_utc()}},
        )
        await record_audit("SOS_DUPLICATE_MERGED", "SOS", existing["sosId"],
                           {"retryCount": existing.get("retryCount", 0)},
                           {"retryCount": existing.get("retryCount", 0) + 1},
                           user=user, request=request,
                           note="Repeat SOS from same user/location within window \u2014 existing case updated")
        doc = await db.sos_records.find_one({"sosId": existing["sosId"]})
        out = _sos_view(doc)
        out["duplicateOfExisting"] = True
        out["message"] = ("You already have an active SOS for this location. We have updated it "
                          "with your latest location instead of creating a second case.")
        return out

    priority_input = payload.model_dump()
    priority_input["eventSeverity"] = event.get("severity") if event else None
    priority, reasons = classify_priority(priority_input)

    record = SOSRecord(
        userId=user["userId"],
        eventId=event["eventId"] if event else None,
        disasterType=(payload.disasterType or
                      (DisasterType(event["disasterType"]) if event else DisasterType.OTHER)),
        clientCreatedAt=payload.clientCreatedAt,
        uploadedAt=now_utc() if offline else None,
        origin=payload.location,
        lastKnown=payload.location,
        peopleCount=payload.peopleCount, injuredCount=payload.injuredCount,
        childrenCount=payload.childrenCount, elderlyCount=payload.elderlyCount,
        emergencyType=payload.emergencyType, description=payload.description,
        networkStatus=NetworkMode.OFFLINE if offline else payload.networkStatus,
        batteryStatus=payload.batteryStatus, priority=priority, priorityReasons=reasons,
        photoBase64=payload.photoBase64, voiceNoteBase64=payload.voiceNoteBase64,
        landmark=payload.landmark or payload.location.landmark,
        accessibilityRequirement=payload.accessibilityRequirement,
        contactName=payload.contactName or user.get("name"),
        contactPhone=payload.contactPhone or user.get("mobile"),
        status=SOSStatus.CREATED,
    )
    doc = record.model_dump()
    doc["status"] = SOSStatus.CREATED.value
    doc["disasterType"] = doc["disasterType"].value if hasattr(doc["disasterType"], "value") else doc["disasterType"]
    doc["networkStatus"] = str(doc["networkStatus"].value if hasattr(doc["networkStatus"], "value") else doc["networkStatus"])
    doc["origin"] = loc_doc(payload.location)
    doc["lastKnown"] = loc_doc(payload.location)
    doc["clientRef"] = payload.clientRef
    await db.sos_records.insert_one(doc)
    await record_audit("SOS_CREATE", "SOS", doc["sosId"], None,
                       {"priority": priority, "eventId": doc.get("eventId"),
                        "peopleCount": doc["peopleCount"], "offline": offline},
                       user=user, request=request)

    # CREATED -> (QUEUED_OFFLINE) -> RECEIVED -> VERIFIED -> PENDING
    if offline:
        doc = await _transition(doc, SOSStatus.QUEUED_OFFLINE.value, user, request,
                                note="Created while offline; original creation time retained")
    doc = await _transition(doc, SOSStatus.RECEIVED.value, user, request,
                            note="Server acknowledged receipt")
    doc = await _transition(doc, SOSStatus.VERIFIED.value, user, request,
                            note="Deduplication and validation passed")
    doc = await _transition(doc, SOSStatus.PENDING.value, user, request,
                            note="Queued for rescue-leader assignment")

    out = _sos_view(doc)
    out["duplicateOfExisting"] = False
    out["recommendedTeamSize"] = recommended_team_size(payload.model_dump())
    out["message"] = ("SOS RECEIVED by SETU and queued for assignment. "
                      "A rescue team has NOT been assigned yet \u2014 you will be updated when a "
                      "team accepts. You can cancel within the next 30 seconds if this was accidental.")
    out["cancelWindowSeconds"] = 30
    return out


# ---------------------------------------------------------------- citizen endpoints
@router.post("")
async def create_sos(payload: SOSCreate, request: Request,
                     user: Dict[str, Any] = Depends(current_user)):
    return await _create_sos(payload, user, request, offline=False)


@router.post("/sync")
async def sync_offline(batch: SOSSyncBatch, request: Request,
                       user: Dict[str, Any] = Depends(current_user)):
    """Section 11.6/11.7 \u2014 offline queue drain. Original creation time and upload
    time are both transmitted and stored."""
    results = []
    for item in batch.items:
        try:
            results.append({"clientRef": item.clientRef, "ok": True,
                            "sos": await _create_sos(item, user, request, offline=True)})
        except HTTPException as exc:
            results.append({"clientRef": item.clientRef, "ok": False, "error": exc.detail})
    return {"synced": sum(1 for r in results if r["ok"]), "results": results}


@router.get("/mine")
async def my_sos(user: Dict[str, Any] = Depends(current_user)):
    cur = db.sos_records.find({"userId": user["userId"]}).sort("createdAt", -1)
    return {"sos": [_sos_view(d) async for d in cur]}


@router.get("/queue")
async def queue(status: Optional[str] = None, priority: Optional[str] = None,
                eventId: Optional[str] = None, unassignedOnly: bool = False,
                user: Dict[str, Any] = Depends(require_roles(Role.RESCUE_LEADER, Role.AUTHORITY,
                                                             Role.SUPER_ADMIN))):
    q: Dict[str, Any] = {}
    q["status"] = status if status else {"$in": SOS_ACTIVE_STATES}
    if priority:
        q["priority"] = priority
    if eventId:
        q["eventId"] = eventId
    if unassignedOnly:
        q["assignedTeamId"] = None
    docs = [d async for d in db.sos_records.find(q)]
    docs.sort(key=lambda d: (PRIORITY_ORDER.get(d.get("priority"), 3), d.get("createdAt")))
    return {"count": len(docs), "sos": [_sos_view(d) for d in docs]}


@router.get("/assigned-to-me")
async def assigned_to_me(user: Dict[str, Any] = Depends(require_roles(Role.RESCUE_MEMBER,
                                                                     Role.RESCUE_LEADER))):
    team_id = user.get("teamId")
    if not team_id:
        team = await db.teams.find_one({"$or": [{"leaderUserId": user["userId"]},
                                                {"memberUserIds": user["userId"]}]})
        team_id = team.get("teamId") if team else None
    if not team_id:
        return {"teamId": None, "sos": [],
                "note": "No team is linked to this account \u2014 ask your leader to add you to a team."}
    cur = db.sos_records.find({"assignedTeamId": team_id, "status": {"$in": SOS_ACTIVE_STATES}})
    docs = [_sos_view(d) async for d in cur]
    return {"teamId": team_id, "sos": docs}


@router.get("/{sos_id}")
async def get_sos(sos_id: str, user: Dict[str, Any] = Depends(current_user)):
    doc = await _load(sos_id)
    if not await _can_view(user, doc):
        raise HTTPException(status_code=403, detail="Not permitted to view this SOS record")
    out = _sos_view(doc)
    if doc.get("assignedTeamId"):
        team = await db.teams.find_one({"teamId": doc["assignedTeamId"]})
        if team:
            out["team"] = {"teamId": team["teamId"], "name": team.get("name"),
                           "status": team.get("status"), "vehicle": team.get("vehicle")}
    return out


@router.get("/{sos_id}/timeline")
async def sos_timeline(sos_id: str, user: Dict[str, Any] = Depends(current_user)):
    doc = await _load(sos_id)
    if not await _can_view(user, doc):
        raise HTTPException(status_code=403, detail="Not permitted to view this SOS record")
    from ..audit import timeline as audit_timeline
    return {"sosId": sos_id, "timeline": await audit_timeline("SOS", sos_id)}


@router.post("/{sos_id}/cancel")
async def cancel_sos(sos_id: str, request: Request, note: Optional[str] = None,
                     user: Dict[str, Any] = Depends(current_user)):
    doc = await _load(sos_id)
    if doc.get("userId") != user.get("userId") and not is_admin(user):
        raise HTTPException(status_code=403, detail="Only the citizen who raised this SOS can cancel it")
    team_id = doc.get("assignedTeamId")
    updated = await _transition(doc, SOSStatus.CANCELLED_BY_USER.value, user, request,
                                note=note or "Cancelled by citizen (accidental SOS window)")
    await _sync_team_state(team_id, "", user, request, release=True)
    out = _sos_view(updated)
    out["message"] = ("SOS cancelled. The record and its full audit trail are retained \u2014 "
                      "nothing is deleted.")
    return out


@router.patch("/{sos_id}/location")
async def update_last_known(sos_id: str, payload: LocationUpdate, request: Request,
                            user: Dict[str, Any] = Depends(current_user)):
    doc = await _load(sos_id)
    if doc.get("userId") != user.get("userId") and not await _can_view(user, doc):
        raise HTTPException(status_code=403, detail="Not permitted")
    if doc.get("status") == SOSStatus.COMPLETED.value or not doc.get("liveLocationSharing", True):
        raise HTTPException(status_code=409,
                            detail="Live location sharing has stopped for this closed case (privacy lifecycle 21.2)")
    new_loc = loc_doc(payload.location)
    await db.sos_records.update_one({"sosId": sos_id},
                                    {"$set": {"lastKnown": new_loc, "updatedAt": now_utc()}})
    await record_audit("SOS_LOCATION_UPDATE", "SOS", sos_id, doc.get("lastKnown"), new_loc,
                       user=user, request=request)
    out = _sos_view(await _load(sos_id))
    out["note"] = "Origin location is preserved separately from last-known location."
    return out


# ---------------------------------------------------------------- leader endpoints
@router.post("/{sos_id}/assign")
async def assign_team(sos_id: str, payload: AssignRequest, request: Request,
                      user: Dict[str, Any] = Depends(require_roles(Role.RESCUE_LEADER, Role.AUTHORITY,
                                                                   Role.SUPER_ADMIN))):
    doc = await _load(sos_id)
    if doc.get("status") not in (SOSStatus.PENDING.value, SOSStatus.TIMEOUT.value,
                                 SOSStatus.VERIFIED.value):
        raise HTTPException(status_code=409,
                            detail=f"SOS is {doc.get('status')} \u2014 only PENDING/TIMEOUT cases can be assigned")
    # Atomic team claim (Section 20.6): two leaders cannot claim the same team.
    claimed = await db.teams.find_one_and_update(
        {"teamId": payload.teamId, "status": TeamStatus.AVAILABLE.value},
        {"$set": {"status": TeamStatus.ASSIGNED.value, "activeSosId": sos_id, "updatedAt": now_utc()}},
        return_document=True,
    )
    if not claimed:
        team = await db.teams.find_one({"teamId": payload.teamId})
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        raise HTTPException(status_code=409,
                            detail=f"Team {payload.teamId} is no longer AVAILABLE (currently {team.get('status')}). "
                                   "Pick another team \u2014 this assignment was not applied.")
    timeout_at = now_utc() + timedelta(minutes=ASSIGNMENT_TIMEOUT_MINUTES)
    history_entry = {"teamId": payload.teamId, "assignedBy": user["userId"],
                     "assignedAt": now_utc(), "timeoutAt": timeout_at,
                     "outcome": "PENDING_ACCEPTANCE", "note": payload.note,
                     "authorityOverride": bool(payload.overrideRecommendation)}
    await db.sos_records.update_one({"sosId": sos_id},
                                    {"$push": {"assignmentHistory": history_entry}})
    updated = await _transition(await _load(sos_id), SOSStatus.ASSIGNED.value, user, request,
                                note=f"Assigned to {payload.teamId}",
                                extra={"assignedTeamId": payload.teamId,
                                       "assignmentTimeoutAt": timeout_at})
    await record_audit("TEAM_STATUS", "TEAM", payload.teamId,
                       {"status": TeamStatus.AVAILABLE.value},
                       {"status": TeamStatus.ASSIGNED.value, "activeSosId": sos_id},
                       user=user, request=request)
    out = _sos_view(updated)
    out["timeoutAt"] = timeout_at
    out["message"] = (f"Team {claimed.get('name')} assigned. Awaiting team acceptance \u2014 "
                      f"if not accepted within {ASSIGNMENT_TIMEOUT_MINUTES} minutes the case is "
                      "flagged for reassignment.")
    return out


@router.post("/timeout-scan")
async def timeout_scan(request: Request,
                       user: Dict[str, Any] = Depends(require_roles(Role.RESCUE_LEADER, Role.AUTHORITY,
                                                                    Role.SUPER_ADMIN))):
    """ASSIGNED -> TIMEOUT -> leader alert -> reassign (Section 12.7)."""
    now = now_utc()
    flagged = []
    cur = db.sos_records.find({"status": SOSStatus.ASSIGNED.value})
    async for doc in cur:
        t = doc.get("assignmentTimeoutAt")
        if not isinstance(t, datetime):
            continue
        t = t if t.tzinfo else t.replace(tzinfo=timezone.utc)
        if t > now:
            continue
        team_id = doc.get("assignedTeamId")
        upd = await _transition(doc, SOSStatus.TIMEOUT.value, user, request,
                                note="Team did not respond within the acceptance window")
        await _sync_team_state(team_id, "", user, request, release=True)
        upd = await _transition(upd, SOSStatus.PENDING.value, user, request,
                                note="Returned to queue for reassignment",
                                extra={"assignedTeamId": None})
        flagged.append(_sos_view(upd))
    return {"timedOut": len(flagged), "sos": flagged,
            "leaderAlert": bool(flagged) and "Assignment timeout \u2014 reassignment required"}


# ---------------------------------------------------------------- team endpoints
async def _team_of(user: Dict[str, Any]) -> Optional[str]:
    if user.get("teamId"):
        return user["teamId"]
    team = await db.teams.find_one({"$or": [{"leaderUserId": user["userId"]},
                                            {"memberUserIds": user["userId"]}]})
    return team.get("teamId") if team else None


async def _assert_team_scope(user: Dict[str, Any], doc: Dict[str, Any]):
    if is_admin(user) or user.get("role") == Role.RESCUE_LEADER.value:
        return
    team_id = await _team_of(user)
    if not team_id or doc.get("assignedTeamId") != team_id:
        raise HTTPException(status_code=403, detail="This SOS is not assigned to your team")


@router.post("/{sos_id}/accept")
async def accept(sos_id: str, request: Request,
                 user: Dict[str, Any] = Depends(require_roles(Role.RESCUE_MEMBER, Role.RESCUE_LEADER,
                                                              Role.AUTHORITY, Role.SUPER_ADMIN))):
    doc = await _load(sos_id)
    await _assert_team_scope(user, doc)
    updated = await _transition(doc, SOSStatus.ACCEPTED.value, user, request, note="Team accepted")
    await _sync_team_state(doc.get("assignedTeamId"), SOSStatus.ACCEPTED.value, user, request)
    await db.sos_records.update_one(
        {"sosId": sos_id},
        {"$push": {"assignmentHistory": {"teamId": doc.get("assignedTeamId"),
                                         "outcome": "ACCEPTED", "at": now_utc(),
                                         "by": user["userId"]}}},
    )
    return _sos_view(updated)


@router.post("/{sos_id}/reject")
async def reject(sos_id: str, payload: RejectRequest, request: Request,
                 user: Dict[str, Any] = Depends(require_roles(Role.RESCUE_MEMBER, Role.RESCUE_LEADER,
                                                              Role.AUTHORITY, Role.SUPER_ADMIN))):
    if payload.reason not in REJECTION_REASONS:
        raise HTTPException(status_code=400,
                            detail=f"reason must be one of {sorted(REJECTION_REASONS)}")
    doc = await _load(sos_id)
    await _assert_team_scope(user, doc)
    team_id = doc.get("assignedTeamId")
    updated = await _transition(doc, SOSStatus.PENDING.value, user, request,
                                note=f"Assignment rejected: {payload.reason}",
                                extra={"assignedTeamId": None})
    await _sync_team_state(team_id, "", user, request, release=True)
    await db.sos_records.update_one({"sosId": sos_id},
                                    {"$push": {"assignmentHistory": {
                                        "teamId": team_id, "outcome": "REJECTED",
                                        "reason": payload.reason, "note": payload.note,
                                        "at": now_utc()}}})
    out = _sos_view(updated)
    out["message"] = "Assignment rejected and case returned to the queue for reassignment."
    return out


@router.post("/{sos_id}/status")
async def set_status(sos_id: str, payload: StatusUpdate, request: Request,
                     user: Dict[str, Any] = Depends(require_roles(Role.RESCUE_MEMBER, Role.RESCUE_LEADER,
                                                                  Role.AUTHORITY, Role.SUPER_ADMIN))):
    doc = await _load(sos_id)
    await _assert_team_scope(user, doc)
    target = payload.status.value
    if target not in TEAM_SETTABLE_SOS_STATES:
        raise HTTPException(status_code=400,
                            detail=f"{target} cannot be set by a rescue team. Allowed: "
                                   f"{sorted(TEAM_SETTABLE_SOS_STATES)}")
    extra: Dict[str, Any] = {}
    if payload.location:
        extra["lastKnown"] = loc_doc(payload.location)
    updated = await _transition(doc, target, user, request, note=payload.note, extra=extra)
    await _sync_team_state(doc.get("assignedTeamId"), target, user, request)
    out = _sos_view(updated)
    if target in (SOSStatus.USER_NOT_FOUND.value, SOSStatus.SEARCHING.value):
        from .search_routes import open_search_for_sos
        search = await open_search_for_sos(updated, user, request)
        out["searchOperation"] = search
    if target == SOSStatus.USER_NOT_FOUND.value:
        out["nextAction"] = ("USER_NOT_FOUND triggers Search & Verification \u2014 this is never "
                             "treated as 'user is safe'.")
    if target == SOSStatus.FALSE_ALARM.value:
        false_count = await db.sos_records.count_documents(
            {"userId": doc.get("userId"), "status": SOSStatus.FALSE_ALARM.value})
        out["falseAlarmCountForUser"] = false_count
        out["adminReviewFlagged"] = false_count >= 3
        out["note"] = "False SOS is recorded and reported, never deleted."
    return out


@router.post("/{sos_id}/complete")
async def complete(sos_id: str, report: CompletionReport, request: Request,
                   user: Dict[str, Any] = Depends(require_roles(Role.RESCUE_MEMBER, Role.RESCUE_LEADER,
                                                                Role.AUTHORITY, Role.SUPER_ADMIN))):
    doc = await _load(sos_id)
    await _assert_team_scope(user, doc)
    rep = report.model_dump()
    rep["submittedBy"] = user["userId"]
    rep["submittedAt"] = now_utc()
    team_id = doc.get("assignedTeamId")
    updated = await _transition(doc, SOSStatus.COMPLETED.value, user, request,
                               note="Completion report submitted",
                               extra={"completionReport": rep})
    if team_id:
        await db.teams.update_one({"teamId": team_id},
                                  {"$set": {"status": TeamStatus.AVAILABLE.value,
                                            "activeSosId": None, "updatedAt": now_utc()},
                                   "$inc": {"workload": 1}})
        await record_audit("TEAM_STATUS", "TEAM", team_id, None,
                           {"status": TeamStatus.AVAILABLE.value}, user=user, request=request)
    out = _sos_view(updated)
    out["liveLocationSharingStopped"] = True
    out["note"] = ("Case closed with a structured report. Live location sharing has stopped "
                   "(privacy lifecycle 21.2).")
    return out
