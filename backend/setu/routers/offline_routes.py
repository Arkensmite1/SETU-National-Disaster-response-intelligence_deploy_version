"""Phase 11 — Offline and degraded operation (Section 19).

Rules encoded here:
* The SOS core payload is never dropped. Under bandwidth pressure the optional
  extras (photo, voice note, map tiles) are shed first — in a documented order.
* Anything created offline keeps its ORIGINAL creation time and is uploaded with
  a separate upload time, so the timeline stays honest.
* Sync conflicts are resolved by the server state machine, but the offline record
  is never discarded — it is reported back to the client.
* An offline bundle lets a citizen keep shelter details and instructions with no
  network. It is stamped so its age is always visible.
* SMS fallback is a documented ingest format. No SMS provider is integrated in
  this build (MOCKED inbound), so it is exposed as an authenticated endpoint.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .. import db
from ..audit import record_audit
from ..auth import current_user
from ..geo import haversine_km
from ..models import Location, Role, clean, now_utc, shelter_view

router = APIRouter(prefix="/api/offline", tags=["offline"])

DEGRADED_POLICY = {
    "modes": {
        "FULL": "All features. Photos, voice notes and live tracking enabled.",
        "DEGRADED": ("Text-first. Photos and voice notes are skipped, map tiles are not fetched, "
                     "polling slows down. SOS core payload is unchanged."),
        "OFFLINE": ("Local queue only. SOS is stored on the device with its original time and "
                    "replayed on reconnect. The user is told clearly that it has NOT been "
                    "received yet."),
    },
    "shedOrder": ["map tiles", "photo attachment", "voice note", "live location interval",
                  "advisory AI calls"],
    "neverDropped": ["SOS location", "people count", "emergency type", "timestamp", "user id"],
    "batteryPolicy": {
        "below20": "Background polling reduced; active SOS tracking continues.",
        "below10": ("Only life-safety traffic. Battery status is sent with the SOS so the rescue "
                    "leader knows contact may be lost."),
        "never": "An active SOS is never silently dropped to save battery.",
    },
    "smsFallback": {
        "format": "SETU SOS <lat> <lng> <people> <emergencyType> [landmark]",
        "status": "MOCKED — no SMS gateway is integrated in this build",
        "note": "A real deployment would point an operator gateway at POST /api/offline/sms-fallback",
    },
    "syncRules": [
        "Server state machine wins on conflict; the offline record is retained and reported.",
        "A late offline SOS for an already-closed case is stored as a linked record, not merged.",
        "Duplicate offline items are detected by clientRef so a retry cannot create two cases.",
    ],
}


@router.get("/policy")
async def policy():
    return DEGRADED_POLICY


@router.get("/bundle")
async def bundle(lat: Optional[float] = None, lng: Optional[float] = None,
                 user: Dict[str, Any] = Depends(current_user)):
    """Compact payload a citizen device caches for use with no network."""
    shelters = []
    async for doc in db.shelters.find({"status": {"$ne": "CLOSED"}}):
        v = shelter_view(doc)
        d = None
        loc = doc.get("location") or {}
        if lat is not None and lng is not None and loc:
            d = round(haversine_km(lat, lng, loc["latitude"], loc["longitude"]), 2)
        shelters.append({"shelterId": v["shelterId"], "name": v["name"],
                         "latitude": loc.get("latitude"), "longitude": loc.get("longitude"),
                         "available": v["available"], "capacity": v["capacity"],
                         "status": v["status"], "contactPhone": v.get("contactPhone"),
                         "distanceKm": d, "asOf": v.get("lastUpdated")})
    shelters.sort(key=lambda s: (s["distanceKm"] is None, s["distanceKm"] or 0))
    events = []
    async for e in db.disaster_events.find({"status": {"$nin": ["CLOSED", "CANCELLED"]}}):
        events.append({"eventId": e["eventId"], "title": e.get("title"),
                       "disasterType": e.get("disasterType"), "severity": e.get("severity"),
                       "infoTier": e.get("infoTier"), "status": e.get("status"),
                       "instructions": e.get("instructions", []),
                       "updatedAt": e.get("updatedAt")})
    return {
        "generatedAt": now_utc(),
        "validityNote": ("Cached copy. Everything here is a snapshot — its age is shown and it may "
                         "be out of date. Absence of an alert is never an all-clear."),
        "shelters": shelters[:10],
        "events": events,
        "helplines": [{"label": "NDMA", "number": "1078"}, {"label": "Emergency", "number": "112"},
                      {"label": "Ambulance", "number": "108"}, {"label": "Police", "number": "100"}],
        "offlineInstructions": [
            "Pressing SOS with no network stores it on this device with the time you pressed it.",
            "It is uploaded automatically when a network is available — you will see it change to RECEIVED.",
            "If you can, also call 1078 or 112.",
        ],
        "degradedPolicy": DEGRADED_POLICY["modes"],
        "profile": {"name": user.get("name"), "emergencyContactPhone": user.get("emergencyContactPhone"),
                    "preferredLanguage": user.get("preferredLanguage", "en")},
    }


class QueuedItem(BaseModel):
    kind: str                       # SOS | SHELTER_LOG | SOS_STATUS | FIELD_REPORT
    clientRef: str
    clientCreatedAt: Optional[datetime] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class SyncBatch(BaseModel):
    items: List[QueuedItem] = Field(default_factory=list)


@router.post("/sync")
async def unified_sync(batch: SyncBatch, request: Request,
                       user: Dict[str, Any] = Depends(current_user)):
    """One drain endpoint for every offline queue on the device."""
    results: List[Dict[str, Any]] = []
    for item in batch.items:
        already = await db.audit_log.find_one({"action": "OFFLINE_SYNC",
                                              "newValue.clientRef": item.clientRef})
        if already:
            results.append({"clientRef": item.clientRef, "status": "ALREADY_SYNCED",
                            "note": "Duplicate replay ignored — no second record was created"})
            continue
        try:
            if item.kind == "SOS":
                from .sos_routes import SOSCreate, _create_sos
                payload = SOSCreate(**{**item.payload, "clientRef": item.clientRef,
                                       "clientCreatedAt": item.clientCreatedAt})
                out = await _create_sos(payload, user, request, offline=True)
                results.append({"clientRef": item.clientRef, "status": "APPLIED",
                                "kind": "SOS", "sosId": out.get("sosId"),
                                "mergedIntoExisting": out.get("duplicateOfExisting", False)})
            elif item.kind == "SHELTER_LOG":
                shelter_id = item.payload.get("shelterId")
                count = int(item.payload.get("count") or 0)
                if user.get("role") not in (Role.SHELTER_ADMIN.value, Role.AUTHORITY.value,
                                            Role.SUPER_ADMIN.value):
                    raise HTTPException(status_code=403, detail="Shelter logs require a shelter role")
                sh = await db.shelters.find_one({"shelterId": shelter_id})
                if not sh:
                    raise HTTPException(status_code=404, detail="Shelter not found")
                new_occ = max((sh.get("occupancy") or 0) + count, 0)
                capped = min(new_occ, sh.get("capacity", new_occ)) if count > 0 else new_occ
                await db.shelters.update_one({"shelterId": shelter_id},
                                             {"$set": {"occupancy": capped, "lastUpdated": now_utc()}})
                await db.arrival_logs.insert_one({
                    "logId": f"AL-{item.clientRef}", "shelterId": shelter_id, "count": count,
                    "by": user["userId"], "occurredAt": item.clientCreatedAt or now_utc(),
                    "recordedAt": now_utc(), "offlineReplay": True})
                results.append({"clientRef": item.clientRef, "status": "APPLIED",
                                "kind": "SHELTER_LOG", "occupancy": capped,
                                "clampedToCapacity": capped != new_occ})
            elif item.kind == "SOS_STATUS":
                from .sos_routes import StatusUpdate, set_status
                sos_id = item.payload.get("sosId")
                doc = await db.sos_records.find_one({"sosId": sos_id})
                if not doc:
                    raise HTTPException(status_code=404, detail="SOS not found")
                if doc.get("status") in ("COMPLETED", "CANCELLED_BY_USER", "DUPLICATE"):
                    results.append({"clientRef": item.clientRef, "status": "RETAINED_NOT_APPLIED",
                                    "kind": "SOS_STATUS",
                                    "note": (f"Case is already {doc.get('status')}. The offline update "
                                             "is kept as a field record but did not change the case.")})
                    await db.field_reports.insert_one({
                        "reportId": f"FR-LATE-{item.clientRef}", "objectType": "SOS",
                        "objectId": sos_id, "field": "status",
                        "value": item.payload.get("status"), "confidence": "MEDIUM",
                        "reportedBy": user["userId"], "reporterRole": user.get("role"),
                        "reportedAt": item.clientCreatedAt or now_utc(),
                        "lateOfflineArrival": True, "superseded": True})
                else:
                    await set_status(sos_id, StatusUpdate(status=item.payload.get("status"),
                                                          note="Offline field update replayed"),
                                     request, user)
                    results.append({"clientRef": item.clientRef, "status": "APPLIED",
                                    "kind": "SOS_STATUS"})
            elif item.kind == "FIELD_REPORT":
                await db.field_reports.insert_one({
                    "reportId": f"FR-{item.clientRef}",
                    "objectType": (item.payload.get("objectType") or "AREA").upper(),
                    "objectId": item.payload.get("objectId"), "field": item.payload.get("field"),
                    "value": item.payload.get("value"),
                    "confidence": item.payload.get("confidence", "MEDIUM"),
                    "reportedBy": user["userId"], "reporterRole": user.get("role"),
                    "reportedAt": item.clientCreatedAt or now_utc(), "superseded": False,
                    "offlineReplay": True})
                results.append({"clientRef": item.clientRef, "status": "APPLIED",
                                "kind": "FIELD_REPORT"})
            else:
                results.append({"clientRef": item.clientRef, "status": "REJECTED",
                                "note": f"Unknown kind {item.kind}"})
                continue
            await record_audit("OFFLINE_SYNC", item.kind, item.clientRef, None,
                               {"clientRef": item.clientRef, "kind": item.kind,
                                "clientCreatedAt": item.clientCreatedAt},
                               user=user, request=request,
                               note="Offline record replayed with its original creation time")
        except HTTPException as exc:
            results.append({"clientRef": item.clientRef, "status": "REJECTED",
                            "error": exc.detail,
                            "note": "Item stays on the device — nothing was silently dropped"})
    return {
        "applied": sum(1 for r in results if r["status"] == "APPLIED"),
        "retained": sum(1 for r in results if r["status"] == "RETAINED_NOT_APPLIED"),
        "rejected": sum(1 for r in results if r["status"] == "REJECTED"),
        "duplicates": sum(1 for r in results if r["status"] == "ALREADY_SYNCED"),
        "results": results, "syncedAt": now_utc(),
        "note": "Original creation times are preserved; the server clock records the upload time.",
    }


class SmsFallback(BaseModel):
    text: str


@router.post("/sms-fallback")
async def sms_fallback(payload: SmsFallback, request: Request,
                       user: Dict[str, Any] = Depends(current_user)):
    """Parse the documented SMS body into an SOS. MOCKED inbound: no SMS gateway
    is connected in this build, so the same format is accepted over HTTP."""
    parts = payload.text.strip().split()
    if len(parts) < 4 or parts[0].upper() != "SETU" or parts[1].upper() != "SOS":
        raise HTTPException(status_code=400, detail={
            "message": "Unrecognised SMS body",
            "expectedFormat": DEGRADED_POLICY["smsFallback"]["format"]})
    try:
        lat, lng = float(parts[2]), float(parts[3])
    except ValueError:
        raise HTTPException(status_code=400, detail="Latitude and longitude must be numbers")
    people = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 1
    etype = parts[5].upper() if len(parts) > 5 else "TRAPPED"
    landmark = " ".join(parts[6:]) or None
    from .sos_routes import SOSCreate, _create_sos
    out = await _create_sos(SOSCreate(
        location=Location(latitude=lat, longitude=lng, accuracy=2000, source="MANUAL"),
        peopleCount=people, emergencyType=etype, landmark=landmark,
        networkStatus="DEGRADED", description="Received via SMS fallback channel",
    ), user, request, offline=False)
    out["channel"] = "SMS_FALLBACK (MOCKED — no gateway integrated)"
    out["locationQualityNote"] = ("SMS coordinates are treated as approximate and shown as such to "
                                  "rescue teams.")
    return out
