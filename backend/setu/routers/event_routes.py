"""DisasterEvent routes — Section 5.2 tiers, 6.4 affected-area matching, 23.1/23.6
lifecycle, 9.6 role-appropriate fan-out.

Hard rules honoured here:
* Closing an event never cascade-closes child SOS / shelters / resource requests.
* Only DISASTER_ACTIVE (tier C) events enable rescue workflows.
* Every response carries data-age metadata; nothing is ever labelled "safe".
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from .. import db
from ..audit import record_audit
from ..auth import current_user, optional_user, require_roles
from ..geo import classify_against_event
from ..models import (DisasterStatus, InfoTier, Location, Role, clean, loc_doc, now_utc)
from ..state_machines import DISASTER, EMERGENCY_STATES, IllegalTransition, MACHINES

router = APIRouter(prefix="/api", tags=["disaster-events"])

OPEN_EVENT_STATES = [s for s in DISASTER.states() if s not in ("CLOSED", "CANCELLED")]


def _age(doc: Dict[str, Any]) -> Dict[str, Any]:
    d = clean(doc)
    upd = d.get("updatedAt")
    if isinstance(upd, datetime):
        upd = upd if upd.tzinfo else upd.replace(tzinfo=timezone.utc)
        mins = (now_utc() - upd).total_seconds() / 60
        d["dataAgeMinutes"] = round(mins, 1)
        d["stale"] = mins > 180
        d["stalenessNotice"] = (
            f"Source last updated {int(mins)} min ago — DATA STALE, information may be outdated"
            if mins > 180 else f"Source last updated {int(mins)} min ago"
        )
    d["rescueWorkflowsEnabled"] = (
        d.get("infoTier") == InfoTier.DISASTER_ACTIVE.value and d.get("status") in EMERGENCY_STATES
    )
    if d.get("experimental"):
        d["experimentalNotice"] = "Experimental product — treat as indicative only, not a certainty"
    return d


@router.get("/events")
async def list_events(status: Optional[str] = None, tier: Optional[str] = None,
                     region: Optional[str] = None, include_closed: bool = False):
    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    elif not include_closed:
        q["status"] = {"$in": OPEN_EVENT_STATES}
    if tier:
        q["infoTier"] = tier
    if region:
        q["region"] = region
    cur = db.disaster_events.find(q).sort("updatedAt", -1)
    events = [_age(d) async for d in cur]
    return {
        "events": events,
        "tierLegend": {
            "FORECAST": "Something may happen — no rescue workflow is triggered",
            "WARNING_ACTIVE": "Significant risk — preparation instructions only",
            "DISASTER_ACTIVE": "Occurring / confirmed by an authoritative source — emergency workflows active",
        },
        "sourceNote": "NDEM / authorized disaster-information integration",
    }


@router.get("/events/{event_id}")
async def get_event(event_id: str):
    doc = await db.disaster_events.find_one({"eventId": event_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Event not found")
    ev = _age(doc)
    ev["childCounts"] = {
        "sos": await db.sos_records.count_documents({"eventId": event_id}),
        "openSos": await db.sos_records.count_documents(
            {"eventId": event_id, "status": {"$nin": ["COMPLETED", "CANCELLED_BY_USER", "DUPLICATE"]}}),
        "resourceRequests": await db.resource_requests.count_documents({"eventId": event_id}),
    }
    return ev


class EventTransition(BaseModel):
    status: DisasterStatus
    note: Optional[str] = None


@router.post("/events/{event_id}/transition")
async def transition_event(event_id: str, payload: EventTransition, request: Request,
                           user: Dict[str, Any] = Depends(require_roles(Role.AUTHORITY, Role.SUPER_ADMIN))):
    doc = await db.disaster_events.find_one({"eventId": event_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Event not found")
    current = doc.get("status")
    try:
        DISASTER.assert_transition(current, payload.status.value)
    except IllegalTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    history = doc.get("history") or []
    history.append({"version": doc.get("version", 1), "status": current, "at": now_utc()})
    tier = doc.get("infoTier")
    if payload.status.value in ("CONFIRMED", "ACTIVE", "RESPONSE"):
        tier = InfoTier.DISASTER_ACTIVE.value
    elif payload.status.value == "WARNING":
        tier = InfoTier.WARNING_ACTIVE.value
    await db.disaster_events.update_one(
        {"eventId": event_id},
        {"$set": {"status": payload.status.value, "infoTier": tier, "updatedAt": now_utc(),
                  "history": history},
         "$inc": {"version": 1}},
    )
    await record_audit("EVENT_TRANSITION", "DISASTER_EVENT", event_id,
                       {"status": current}, {"status": payload.status.value},
                       user=user, request=request, note=payload.note)
    open_children = await db.sos_records.count_documents(
        {"eventId": event_id, "status": {"$nin": ["COMPLETED", "CANCELLED_BY_USER", "DUPLICATE"]}})
    return {
        "event": _age(await db.disaster_events.find_one({"eventId": event_id})),
        "childrenUntouched": True,
        "openChildSosCount": open_children,
        "note": ("Disaster status and child SOS/shelter/resource status are independent — "
                 f"{open_children} child SOS record(s) remain open and unchanged."),
    }


class LocationCheck(BaseModel):
    location: Location


@router.post("/events/check-location")
async def check_location(payload: LocationCheck, user=Depends(optional_user)):
    cur = db.disaster_events.find({"status": {"$in": OPEN_EVENT_STATES}})
    matches: List[Dict[str, Any]] = []
    async for doc in cur:
        res = classify_against_event(payload.location.latitude, payload.location.longitude, doc)
        res.update({
            "disasterType": doc.get("disasterType"), "severity": doc.get("severity"),
            "infoTier": doc.get("infoTier"), "status": doc.get("status"),
            "title": doc.get("title"), "instructions": doc.get("instructions"),
            "experimental": doc.get("experimental", False),
            "rescueWorkflowsEnabled": doc.get("infoTier") == InfoTier.DISASTER_ACTIVE.value,
        })
        matches.append(res)
    affected = [m for m in matches if m["classification"] in ("AFFECTED", "NEAR_BOUNDARY")]
    # Overlapping zones (18.9): every matching event is kept, none overrides another.
    return {
        "checkedAt": now_utc(),
        "matches": matches,
        "affectedEvents": affected,
        "overlappingZones": len([m for m in matches if m["classification"] == "AFFECTED"]) > 1,
        "safetyNote": ("No matching active event does NOT mean you are safe. Absence of data is "
                       "never an all-clear — keep following official instructions."),
    }


@router.get("/events/alerts/for-me")
async def alerts_for_me(user: Dict[str, Any] = Depends(current_user)):
    """Section 9.6 — same event, role-appropriate message content."""
    loc = user.get("lastKnownLocation") or user.get("homeLocation")
    role = user.get("role")
    out: List[Dict[str, Any]] = []
    cur = db.disaster_events.find({"status": {"$in": OPEN_EVENT_STATES}})
    async for doc in cur:
        relevance = None
        if loc:
            relevance = classify_against_event(loc["latitude"], loc["longitude"], doc)
        if role == Role.USER.value:
            if relevance and relevance["classification"] == "OUTSIDE_KNOWN_AREA":
                continue
            body = relevance["message"] if relevance else doc.get("title")
            actions = doc.get("instructions", [])
        elif role in (Role.RESCUE_LEADER.value, Role.RESCUE_MEMBER.value):
            open_sos = await db.sos_records.count_documents(
                {"eventId": doc["eventId"], "status": {"$nin": ["COMPLETED", "CANCELLED_BY_USER", "DUPLICATE"]}})
            body = (f"{doc.get('disasterType')} {doc.get('status')} — {doc.get('title')}. "
                    f"{open_sos} open SOS in this event.")
            actions = ["Review command queue", "Confirm team readiness"]
        elif role == Role.SHELTER_ADMIN.value:
            body = (f"{doc.get('disasterType')} {doc.get('status')} — expect inbound arrivals. "
                    f"Keep occupancy and resource requirements current.")
            actions = ["Update occupancy", "Raise resource requirements"]
        elif role == Role.NGO_ADMIN.value:
            body = (f"{doc.get('disasterType')} {doc.get('status')} — relief demand expected in "
                    f"{doc.get('region')}. Review open shelter requirements.")
            actions = ["Review requirements", "Commit inventory"]
        else:
            body = f"{doc.get('disasterType')} {doc.get('status')} — {doc.get('title')}"
            actions = ["Full oversight view"]
        out.append({
            "eventId": doc["eventId"], "title": doc.get("title"), "severity": doc.get("severity"),
            "infoTier": doc.get("infoTier"), "status": doc.get("status"),
            "role": role, "message": body, "actions": actions,
            "relevance": relevance,
            "language": user.get("preferredLanguage", "en"),
            "experimental": doc.get("experimental", False),
            "updatedAt": doc.get("updatedAt"),
        })
    return {"alerts": out, "locationKnown": bool(loc),
            "note": "Alert content is role-scoped; identical broadcasts are never sent to all roles."}


@router.get("/state-machines")
async def state_machines():
    return {
        name: {
            "states": sorted(m.states()),
            "transitions": {k: sorted(v) for k, v in m.transitions.items()},
            "alwaysAllowed": sorted(m.always_allowed),
            "terminal": sorted(m.terminal),
        } for name, m in MACHINES.items()
    }
