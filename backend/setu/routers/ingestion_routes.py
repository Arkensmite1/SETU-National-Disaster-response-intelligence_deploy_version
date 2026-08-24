"""Phase 9 (part 2) — ingestion + notification routes (Sections 6, 9, 10).

Notification rules encoded here:
* Priority queue: P1 life-safety, P2 operational, P3 informational. P1 is never
  queued behind P3.
* Role-appropriate content: the same event produces different text per role.
* Delivery and acknowledgement are tracked separately — "sent" is not "seen".
* Unacknowledged P1 notifications escalate to the next level instead of dying.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .. import db
from ..audit import record_audit
from ..auth import current_user, require_roles
from ..geo import classify_against_event
from ..models import Role, clean, now_utc
from .. import ingestion

router = APIRouter(prefix="/api", tags=["ingestion-notifications"])

ADMIN_ONLY = require_roles(Role.AUTHORITY, Role.SUPER_ADMIN)
ESCALATION_MINUTES = {1: 5, 2: 20, 3: 120}


# ---------------------------------------------------------------- ingestion
@router.post("/ingestion/poll")
async def run_poll(request: Request, user: Dict[str, Any] = Depends(ADMIN_ONLY)):
    return await ingestion.poll(user)


@router.get("/ingestion/status")
async def ingestion_status(user: Dict[str, Any] = Depends(current_user)):
    return await ingestion.status()


class SimulateFeed(BaseModel):
    mode: str = "UPDATE_SEVERITY"
    eventId: Optional[str] = None


DEMO_POLYGON = {"type": "Polygon",
                "coordinates": [[[85.70, 26.00], [86.10, 26.00], [86.10, 26.35],
                                 [85.70, 26.35], [85.70, 26.00]]]}


@router.post("/ingestion/simulate")
async def simulate(payload: SimulateFeed, request: Request,
                   user: Dict[str, Any] = Depends(ADMIN_ONLY)):
    """DEMO ONLY — places items on the incoming source feed so the ingestion rules
    (new / update / contradiction / silence) can be exercised end to end."""
    mode = payload.mode.upper()
    if mode == "NEW_EVENT":
        items = [{
            "sourceReference": f"IMD/DEMO-FEED/{int(now_utc().timestamp())}",
            "disasterType": "FLOOD", "severity": "HIGH", "status": "WARNING",
            "title": "DEMO feed: rising water levels — Darbhanga belt", "region": "bihar-darbhanga",
            "affectedArea": DEMO_POLYGON, "confidence": 0.72, "version": 1,
            "qualityMetadata": {"observationType": "NEAR_REAL_TIME", "latencyMinutes": 15},
            "instructions": ["Move valuables and livestock to higher ground.",
                             "Identify your nearest relief shelter now."],
        }]
    elif mode == "UPDATE_SEVERITY":
        ev = await db.disaster_events.find_one({"eventId": payload.eventId} if payload.eventId
                                               else {"infoTier": "WARNING_ACTIVE"})
        if not ev:
            raise HTTPException(status_code=404, detail="No event available to update")
        items = [{"sourceReference": ev.get("sourceReference"), "severity": "EXTREME",
                  "status": "CONFIRMED", "version": int(ev.get("version", 1)) + 1,
                  "title": f"{ev.get('title')} — escalated by source",
                  "instructions": ["Evacuate low-lying areas immediately.",
                                   "Follow instructions from local authorities."]}]
    elif mode == "CONTRADICTORY_UPDATE":
        ev = await db.disaster_events.find_one({"eventId": payload.eventId} if payload.eventId
                                               else {"infoTier": "DISASTER_ACTIVE"})
        if not ev:
            raise HTTPException(status_code=404, detail="No event available")
        items = [{"sourceReference": ev.get("sourceReference"), "severity": "LOW",
                  "version": int(ev.get("version", 1)),
                  "title": f"{ev.get('title')} — conflicting downgrade"}]
    elif mode == "ILLEGAL_JUMP":
        ev = await db.disaster_events.find_one({"eventId": payload.eventId} if payload.eventId
                                               else {"infoTier": "DISASTER_ACTIVE"})
        if not ev:
            raise HTTPException(status_code=404, detail="No event available")
        items = [{"sourceReference": ev.get("sourceReference"), "status": "DETECTED",
                  "version": int(ev.get("version", 1)) + 1}]
    elif mode == "SOURCE_SILENCE":
        items = []
    else:
        raise HTTPException(status_code=400,
                            detail="mode must be NEW_EVENT, UPDATE_SEVERITY, CONTRADICTORY_UPDATE, "
                                   "ILLEGAL_JUMP or SOURCE_SILENCE")
    await ingestion.queue_feed_items(items)
    await record_audit("INGESTION_SIMULATED", "INGESTION", mode, None, {"items": len(items)},
                       user=user, request=request, note="DEMO feed injection")
    return {"queued": len(items), "mode": mode,
            "next": "POST /api/ingestion/poll to consume the feed",
            "demoData": True}


# ---------------------------------------------------------------- notifications
ROLE_TEMPLATES = {
    Role.USER.value: "{headline} Follow official instructions and keep SOS available.",
    Role.RESCUE_LEADER.value: "{headline} Review the command queue and confirm team readiness.",
    Role.RESCUE_MEMBER.value: "{headline} Standby for assignment; keep your status and location current.",
    Role.SHELTER_ADMIN.value: "{headline} Expect arrivals — keep occupancy and requirements current.",
    Role.NGO_ADMIN.value: "{headline} Review outstanding shelter requirements in the affected region.",
    Role.AUTHORITY.value: "{headline} Full oversight view available in the authority portal.",
    Role.SUPER_ADMIN.value: "{headline} System-wide view available.",
}


class Dispatch(BaseModel):
    priority: int = 2                      # 1 = life safety, 2 = operational, 3 = informational
    roles: List[Role] = Field(default_factory=list)
    eventId: Optional[str] = None
    sosId: Optional[str] = None
    headline: str
    region: Optional[str] = None
    locationScoped: bool = True


@router.post("/notifications/dispatch")
async def dispatch_notification(payload: Dispatch, request: Request,
                                user: Dict[str, Any] = Depends(ADMIN_ONLY)):
    if payload.priority not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="priority must be 1, 2 or 3")
    event = await db.disaster_events.find_one({"eventId": payload.eventId}) if payload.eventId else None
    target_roles = [r.value for r in payload.roles] or list(ROLE_TEMPLATES.keys())
    created, skipped = 0, 0
    async for u in db.users.find({"role": {"$in": target_roles}}):
        relevance = None
        if event and payload.locationScoped and u.get("role") == Role.USER.value:
            loc = u.get("lastKnownLocation") or u.get("homeLocation")
            if loc:
                relevance = classify_against_event(loc["latitude"], loc["longitude"], event)
                if relevance["classification"] == "OUTSIDE_KNOWN_AREA" and payload.priority == 1:
                    skipped += 1
                    continue
        template = ROLE_TEMPLATES.get(u.get("role"), "{headline}")
        await db.notifications.insert_one({
            "notificationId": f"NT-{int(now_utc().timestamp() * 1000)}-{created}",
            "to": u["userId"], "toRole": u.get("role"), "priority": payload.priority,
            "type": "EVENT_ALERT" if payload.eventId else "OPERATIONAL",
            "message": template.format(headline=payload.headline),
            "language": u.get("preferredLanguage", "en"),
            "objectType": "DISASTER_EVENT" if payload.eventId else ("SOS" if payload.sosId else None),
            "objectId": payload.eventId or payload.sosId,
            "relevance": relevance, "createdAt": now_utc(),
            "delivered": False, "deliveredAt": None,
            "acknowledged": False, "acknowledgedAt": None, "escalated": False,
        })
        created += 1
    await record_audit("NOTIFICATION_DISPATCH", "NOTIFICATION", payload.eventId or "BROADCAST",
                       None, {"priority": payload.priority, "recipients": created},
                       user=user, request=request, note=payload.headline)
    return {"created": created, "skippedOutsideArea": skipped,
            "priority": payload.priority,
            "note": ("Content is role-specific. Delivery and acknowledgement are tracked "
                     "separately — dispatched is not the same as seen.")}


@router.get("/notifications/mine")
async def my_notifications(unreadOnly: bool = False,
                           user: Dict[str, Any] = Depends(current_user)):
    q: Dict[str, Any] = {"$or": [{"to": user["userId"]},
                                 {"to": user.get("teamId")},
                                 {"to": user.get("shelterId")}]}
    if unreadOnly:
        q["acknowledged"] = False
    rows = [clean(d) async for d in db.notifications.find(q)]
    rows.sort(key=lambda n: (n.get("priority", 3), -(n.get("createdAt").timestamp()
                                                      if isinstance(n.get("createdAt"), datetime) else 0)))
    ids = [r.get("notificationId") for r in rows if r.get("notificationId") and not r.get("delivered")]
    if ids:
        await db.notifications.update_many({"notificationId": {"$in": ids}},
                                           {"$set": {"delivered": True, "deliveredAt": now_utc()}})
    return {"notifications": rows,
            "unacknowledged": sum(1 for r in rows if not r.get("acknowledged")),
            "note": "Priority 1 messages are always listed above lower priorities."}


@router.post("/notifications/{notification_id}/ack")
async def acknowledge(notification_id: str, request: Request,
                      user: Dict[str, Any] = Depends(current_user)):
    doc = await db.notifications.find_one({"notificationId": notification_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Notification not found")
    if doc.get("to") not in (user["userId"], user.get("teamId"), user.get("shelterId")):
        raise HTTPException(status_code=403, detail="This notification is not addressed to you")
    await db.notifications.update_one({"notificationId": notification_id},
                                      {"$set": {"acknowledged": True, "acknowledgedAt": now_utc(),
                                                "delivered": True}})
    await record_audit("NOTIFICATION_ACK", "NOTIFICATION", notification_id, None,
                       {"acknowledged": True}, user=user, request=request)
    return clean(await db.notifications.find_one({"notificationId": notification_id}))


@router.get("/notifications/monitor")
async def monitor(user: Dict[str, Any] = Depends(ADMIN_ONLY)):
    total = await db.notifications.count_documents({})
    return {
        "total": total,
        "undelivered": await db.notifications.count_documents({"delivered": False}),
        "unacknowledged": await db.notifications.count_documents({"acknowledged": False}),
        "p1Unacknowledged": await db.notifications.count_documents({"priority": 1,
                                                                    "acknowledged": False}),
        "escalated": await db.notifications.count_documents({"escalated": True}),
        "note": ("Unacknowledged life-safety messages are escalated, never silently dropped."),
    }


@router.post("/notifications/escalate-scan")
async def escalate_scan(request: Request, user: Dict[str, Any] = Depends(ADMIN_ONLY)):
    escalated = []
    now = now_utc()
    async for n in db.notifications.find({"acknowledged": False, "escalated": False}):
        created = n.get("createdAt")
        if not isinstance(created, datetime):
            continue
        created = created if created.tzinfo else created.replace(tzinfo=timezone.utc)
        limit = ESCALATION_MINUTES.get(n.get("priority", 3), 120)
        if (now - created) < timedelta(minutes=limit):
            continue
        await db.notifications.update_one({"_id": n["_id"]},
                                          {"$set": {"escalated": True, "escalatedAt": now}})
        await db.notifications.insert_one({
            "notificationId": f"NT-ESC-{int(now.timestamp() * 1000)}",
            "to": "USR-AUTH-001", "toRole": Role.AUTHORITY.value, "priority": 1,
            "type": "ESCALATION",
            "message": (f"Unacknowledged P{n.get('priority')} notification to "
                        f"{n.get('toRole')} after {limit} min: {n.get('message')[:120]}"),
            "objectType": n.get("objectType"), "objectId": n.get("objectId"),
            "createdAt": now, "delivered": False, "acknowledged": False, "escalated": False,
        })
        escalated.append(n.get("notificationId"))
    await record_audit("NOTIFICATION_ESCALATION_SCAN", "NOTIFICATION", "SCAN", None,
                       {"escalated": len(escalated)}, user=user, request=request)
    return {"escalated": len(escalated), "notificationIds": escalated,
            "note": "Escalation adds a higher-priority message for the authority; nothing is deleted."}
