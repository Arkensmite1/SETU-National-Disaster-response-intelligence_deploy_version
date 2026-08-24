"""Phase 9 (part 1) — disaster-information ingestion pipeline (Sections 6, 9, 10, 20.7).

SETU never invents disaster information. This module is the single boundary where
authoritative data enters the platform, and it enforces:
* Source of record: every event keeps `source` + `sourceReference` + version history.
* Update, not duplicate: a repeated feed item updates the existing event (version++).
* Contradiction: a feed item that conflicts with the stored record is kept as a
  CONFLICT for human review — the newer value does not silently win.
* Quality metadata: observation type, latency and confidence travel with the event.
* Source silence: "no update received" is reported as a data gap, never as safety.

The demo adapter below stands in for the real NDEM / authorized integration.
"""
import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

from . import db
from .audit import record_audit
from .models import DisasterStatus, InfoTier, now_utc
from .state_machines import DISASTER

log = logging.getLogger("setu.ingestion")

SOURCE_NAME = "NDEM / authorized disaster-information integration"
SILENCE_WARNING_MINUTES = 60

TIER_FOR_STATUS = {
    DisasterStatus.DETECTED.value: InfoTier.FORECAST.value,
    DisasterStatus.MONITORING.value: InfoTier.FORECAST.value,
    DisasterStatus.WARNING.value: InfoTier.WARNING_ACTIVE.value,
    DisasterStatus.CONFIRMED.value: InfoTier.DISASTER_ACTIVE.value,
    DisasterStatus.ACTIVE.value: InfoTier.DISASTER_ACTIVE.value,
    DisasterStatus.RESPONSE.value: InfoTier.DISASTER_ACTIVE.value,
}


async def _state() -> Dict[str, Any]:
    doc = await db.ingestion_state.find_one({"_id": "source"})
    return doc or {"_id": "source", "lastPollAt": None, "lastChangeAt": None,
                   "polls": 0, "created": 0, "updated": 0, "conflicts": 0,
                   "pendingFeed": [], "sourceHealth": "UNKNOWN"}


async def queue_feed_items(items: List[Dict[str, Any]]):
    """Used by the simulate endpoint to place items on the incoming feed."""
    st = await _state()
    pending = (st.get("pendingFeed") or []) + items
    await db.ingestion_state.update_one({"_id": "source"},
                                       {"$set": {"pendingFeed": pending}}, upsert=True)


async def poll(user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Consume everything currently on the feed and reconcile it with stored events."""
    st = await _state()
    feed: List[Dict[str, Any]] = list(st.get("pendingFeed") or [])
    created, updated, unchanged, conflicts = [], [], [], []

    for item in feed:
        ref = item.get("sourceReference")
        existing = await db.disaster_events.find_one({"sourceReference": ref}) if ref else None
        if not existing:
            status = item.get("status") or DisasterStatus.DETECTED.value
            doc = {
                "eventId": item.get("eventId") or f"NDEM-EVENT-{int(now_utc().timestamp())}",
                "source": SOURCE_NAME, "sourceReference": ref,
                "disasterType": item.get("disasterType", "FLOOD"),
                "severity": item.get("severity", "MODERATE"),
                "infoTier": item.get("infoTier") or TIER_FOR_STATUS.get(status, InfoTier.FORECAST.value),
                "status": status, "title": item.get("title", "Incoming disaster information"),
                "region": item.get("region"), "issuedAt": now_utc(), "updatedAt": now_utc(),
                "validFrom": now_utc(), "validUntil": now_utc() + timedelta(hours=24),
                "affectedArea": item.get("affectedArea"), "zones": item.get("zones", []),
                "confidence": item.get("confidence"),
                "qualityMetadata": {**(item.get("qualityMetadata") or {}),
                                    "ingestedAt": now_utc(), "sourceVersion": item.get("version", 1)},
                "instructions": item.get("instructions", []),
                "version": 1, "experimental": bool(item.get("experimental")), "history": [],
            }
            await db.disaster_events.insert_one(doc)
            await record_audit("EVENT_INGESTED", "DISASTER_EVENT", doc["eventId"], None,
                               {"sourceReference": ref, "status": status}, user=user,
                               note="New authoritative record received from the source feed")
            created.append(doc["eventId"])
            continue

        incoming_version = int(item.get("version") or 0)
        stored_version = int(existing.get("version") or 1)
        changed_fields = {k: v for k, v in item.items()
                          if k in ("severity", "status", "infoTier", "title", "affectedArea",
                                   "instructions", "confidence")
                          and v is not None and v != existing.get(k)}

        if incoming_version and incoming_version <= stored_version and changed_fields:
            # Same/older version but different content — a genuine contradiction.
            conflict = {
                "conflictId": f"CF-INGEST-{existing['eventId']}-{int(now_utc().timestamp())}",
                "objectType": "DISASTER_EVENT", "objectId": existing["eventId"],
                "field": ",".join(sorted(changed_fields)),
                "values": [
                    {"value": {k: existing.get(k) for k in changed_fields},
                     "reportedBy": "stored record", "version": stored_version,
                     "at": existing.get("updatedAt")},
                    {"value": changed_fields, "reportedBy": SOURCE_NAME,
                     "version": incoming_version, "at": now_utc()},
                ],
                "status": "OPEN", "createdAt": now_utc(),
                "note": "Source sent a conflicting value at the same or older version. Both retained.",
            }
            await db.conflicts.insert_one(conflict)
            await record_audit("EVENT_INGEST_CONFLICT", "DISASTER_EVENT", existing["eventId"],
                               {k: existing.get(k) for k in changed_fields}, changed_fields,
                               user=user, note="Conflicting source update held for human review")
            conflicts.append(conflict["conflictId"])
            continue

        if not changed_fields:
            await db.disaster_events.update_one({"eventId": existing["eventId"]},
                                                {"$set": {"qualityMetadata.lastSeenAt": now_utc()}})
            unchanged.append(existing["eventId"])
            continue

        # Legal forward update — version history retained (20.7)
        target_status = changed_fields.get("status", existing.get("status"))
        if target_status != existing.get("status") and not DISASTER.can(existing.get("status"), target_status):
            await db.conflicts.insert_one({
                "conflictId": f"CF-INGEST-STATUS-{existing['eventId']}-{int(now_utc().timestamp())}",
                "objectType": "DISASTER_EVENT", "objectId": existing["eventId"], "field": "status",
                "values": [{"value": existing.get("status"), "reportedBy": "stored record"},
                           {"value": target_status, "reportedBy": SOURCE_NAME}],
                "status": "OPEN", "createdAt": now_utc(),
                "note": ("Source proposed an illegal lifecycle jump. It was NOT applied; an "
                         "authority must decide."),
            })
            conflicts.append(existing["eventId"])
            continue

        history = existing.get("history") or []
        history.append({"version": stored_version, "status": existing.get("status"),
                        "severity": existing.get("severity"), "at": existing.get("updatedAt")})
        new_tier = changed_fields.get("infoTier") or TIER_FOR_STATUS.get(target_status,
                                                                        existing.get("infoTier"))
        await db.disaster_events.update_one(
            {"eventId": existing["eventId"]},
            {"$set": {**changed_fields, "infoTier": new_tier, "updatedAt": now_utc(),
                      "history": history,
                      "qualityMetadata.sourceVersion": incoming_version or stored_version + 1,
                      "qualityMetadata.lastSeenAt": now_utc()},
             "$inc": {"version": 1}})
        await record_audit("EVENT_UPDATED_FROM_SOURCE", "DISASTER_EVENT", existing["eventId"],
                           {k: existing.get(k) for k in changed_fields}, changed_fields,
                           user=user, note="Authoritative update applied; previous version retained")
        updated.append(existing["eventId"])

    await db.ingestion_state.update_one(
        {"_id": "source"},
        {"$set": {"lastPollAt": now_utc(), "pendingFeed": [],
                  "lastChangeAt": now_utc() if (created or updated) else st.get("lastChangeAt"),
                  "sourceHealth": "RECEIVING" if feed else "SILENT"},
         "$inc": {"polls": 1, "created": len(created), "updated": len(updated),
                  "conflicts": len(conflicts)}},
        upsert=True)

    return {"polledAt": now_utc(), "feedItems": len(feed), "created": created,
            "updated": updated, "unchanged": unchanged, "conflicts": conflicts,
            "note": ("Zero feed items means the source sent nothing — that is a data gap, not an "
                     "all-clear.")}


async def status() -> Dict[str, Any]:
    st = await _state()
    last = st.get("lastPollAt")
    change = st.get("lastChangeAt")
    silence_min = None
    if change:
        c = change if change.tzinfo else change.replace(tzinfo=None)
        try:
            silence_min = round((now_utc() - change).total_seconds() / 60, 1)
        except TypeError:
            silence_min = None
    warning = None
    if silence_min is not None and silence_min > SILENCE_WARNING_MINUTES:
        warning = (f"No authoritative update received for {int(silence_min)} minutes. "
                   "This is a data gap — it does not mean the situation has improved.")
    elif silence_min is None:
        warning = ("No authoritative update has been recorded yet in this session. Absence of data "
                   "is never an all-clear.")
    return {
        "source": SOURCE_NAME,
        "lastPollAt": last, "lastChangeAt": change,
        "minutesSinceLastChange": silence_min,
        "polls": st.get("polls", 0), "eventsCreated": st.get("created", 0),
        "eventsUpdated": st.get("updated", 0), "conflicts": st.get("conflicts", 0),
        "pendingFeedItems": len(st.get("pendingFeed") or []),
        "sourceHealth": st.get("sourceHealth", "UNKNOWN"),
        "silenceWarning": warning,
    }
