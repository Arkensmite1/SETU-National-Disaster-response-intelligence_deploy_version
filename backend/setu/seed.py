"""Idempotent development seed (replaces mock_data.py's role for the new model).

DEMO DATA — clearly labelled. The disaster events created here come from the
seed ingestion adapter (Phase 9) which stands in for a real authorized
NDEM / disaster-information integration.
"""
import asyncio
from datetime import timedelta
from typing import Any, Dict, List

from . import db
from .auth import hash_password
from .models import (DisasterStatus, DisasterType, InfoTier, Location, LocationSource,
                     ResourceStatus, Role, Severity, ShelterStatus, TeamStatus, now_utc)

DEMO_PASSWORD = "Setu@1234"

DEMO_USERS: List[Dict[str, Any]] = [
    {"userId": "USR-CITIZEN-001", "name": "Anita Devi", "mobile": "9000000001",
     "role": Role.USER.value, "ageGroup": "26-45", "preferredLanguage": "hi",
     "emergencyContactName": "Ramesh Devi", "emergencyContactPhone": "9000000009",
     "groupSize": 4, "verified": True},
    {"userId": "USR-CITIZEN-002", "name": "Bikash Sharma", "mobile": "9000000002",
     "role": Role.USER.value, "ageGroup": "18-25", "preferredLanguage": "as",
     "groupSize": 1, "verified": True},
    {"userId": "USR-LEADER-001", "name": "Cmdr. R. Nair", "email": "leader@setu.gov.in",
     "role": Role.RESCUE_LEADER.value, "teamId": None, "verified": True},
    {"userId": "USR-MEMBER-001", "name": "Hav. S. Yadav", "email": "member@setu.gov.in",
     "role": Role.RESCUE_MEMBER.value, "teamId": "TEAM-NDRF01", "verified": True},
    {"userId": "USR-MEMBER-002", "name": "Hav. P. Kalita", "email": "member2@setu.gov.in",
     "role": Role.RESCUE_MEMBER.value, "teamId": "TEAM-NDRF02", "verified": True},
    {"userId": "USR-SHELTER-001", "name": "Shelter Admin — Dhemaji", "email": "shelter@setu.gov.in",
     "role": Role.SHELTER_ADMIN.value, "shelterId": "SH-S1", "verified": True},
    {"userId": "USR-NGO-001", "name": "Seva Bharati Relief", "email": "ngo@setu.gov.in",
     "role": Role.NGO_ADMIN.value, "ngoId": "NGO-001", "ngoName": "Seva Bharati Relief",
     "verified": True},
    {"userId": "USR-AUTH-001", "name": "District Magistrate (Authority)", "email": "authority@setu.gov.in",
     "role": Role.AUTHORITY.value, "verified": True},
    {"userId": "USR-ADMIN-001", "name": "SETU Super Admin", "email": "admin@setu.gov.in",
     "role": Role.SUPER_ADMIN.value, "verified": True},
]

DEMO_TEAMS: List[Dict[str, Any]] = [
    {"teamId": "TEAM-NDRF01", "name": "NDRF Team Alpha", "leaderUserId": "USR-LEADER-001",
     "memberUserIds": ["USR-MEMBER-001"], "memberNames": ["Hav. S. Yadav", "Sep. M. Das"],
     "vehicle": "BOAT", "equipment": ["Inflatable boat", "Life jackets", "Rope kit", "First aid"],
     "capabilities": ["WATER_RESCUE", "MEDICAL_FIRST_AID", "NIGHT_OPS"],
     "maxOperationalCapacity": 12, "region": "assam-dhemaji",
     "currentLocation": {"latitude": 27.48, "longitude": 94.57, "accuracy": 15.0,
                         "timestamp": None, "source": LocationSource.GPS.value}},
    {"teamId": "TEAM-NDRF02", "name": "NDRF Team Bravo", "leaderUserId": "USR-LEADER-001",
     "memberUserIds": ["USR-MEMBER-002"], "memberNames": ["Hav. P. Kalita"],
     "vehicle": "HIGH_CLEARANCE_VEHICLE", "equipment": ["Cutting tools", "Stretcher", "First aid"],
     "capabilities": ["COLLAPSE_RESCUE", "MEDICAL_FIRST_AID"], "maxOperationalCapacity": 8,
     "region": "assam-dhemaji",
     "currentLocation": {"latitude": 27.52, "longitude": 94.62, "accuracy": 25.0,
                         "timestamp": None, "source": LocationSource.GPS.value}},
    {"teamId": "TEAM-SDRF01", "name": "SDRF Team Charlie", "leaderUserId": "USR-LEADER-001",
     "memberUserIds": [], "memberNames": ["Const. A. Kumar"], "vehicle": "BOAT",
     "equipment": ["Boat", "Life jackets"], "capabilities": ["WATER_RESCUE"],
     "maxOperationalCapacity": 10, "region": "bihar-darbhanga",
     "currentLocation": {"latitude": 26.14, "longitude": 85.89, "accuracy": 30.0,
                         "timestamp": None, "source": LocationSource.NETWORK.value}},
    {"teamId": "TEAM-MED01", "name": "Medical Response Delta", "leaderUserId": "USR-LEADER-001",
     "memberUserIds": [], "memberNames": ["Dr. N. Bose", "Paramedic K. Roy"], "vehicle": "AMBULANCE",
     "equipment": ["Advanced medical kit", "Oxygen"], "capabilities": ["MEDICAL_CRITICAL", "MEDICAL_FIRST_AID"],
     "maxOperationalCapacity": 6, "region": "assam-dhemaji",
     "currentLocation": {"latitude": 27.46, "longitude": 94.60, "accuracy": 20.0,
                         "timestamp": None, "source": LocationSource.GPS.value}},
]

DEMO_SHELTERS: List[Dict[str, Any]] = [
    {"shelterId": "SH-S1", "name": "Dhemaji Community Hall", "adminUserId": "USR-SHELTER-001",
     "lat": 27.482, "lng": 94.58, "capacity": 800, "occupancy": 612, "region": "assam-dhemaji",
     "facilities": ["Food", "Medical", "Electricity"], "contactPhone": "1800-345-0001"},
    {"shelterId": "SH-S2", "name": "Darbhanga District School", "adminUserId": None,
     "lat": 26.15, "lng": 85.895, "capacity": 1200, "occupancy": 1140, "region": "bihar-darbhanga",
     "facilities": ["Food", "Medical"], "contactPhone": "1800-345-0002"},
    {"shelterId": "SH-S3", "name": "Majuli Relief Camp", "adminUserId": None,
     "lat": 26.95, "lng": 94.1667, "capacity": 500, "occupancy": 500, "region": "assam-dhemaji",
     "facilities": ["Food"], "contactPhone": "1800-345-0003"},
    {"shelterId": "SH-S4", "name": "Jorhat Govt. College", "adminUserId": None,
     "lat": 26.75, "lng": 94.22, "capacity": 650, "occupancy": 180, "region": "assam-dhemaji",
     "facilities": ["Food", "Medical", "Electricity", "Accessible"], "contactPhone": "1800-345-0004"},
]

DHEMAJI_POLYGON = {
    "type": "Polygon",
    "coordinates": [[[94.44, 27.38], [94.74, 27.38], [94.74, 27.60], [94.44, 27.60], [94.44, 27.38]]],
}
ODISHA_COAST_POLYGON = {
    "type": "Polygon",
    "coordinates": [[[86.30, 19.60], [87.10, 19.60], [87.10, 20.40], [86.30, 20.40], [86.30, 19.60]]],
}
UTTARAKHAND_POLYGON = {
    "type": "Polygon",
    "coordinates": [[[78.90, 30.20], [79.30, 30.20], [79.30, 30.60], [78.90, 30.60], [78.90, 30.20]]],
}


def _loc(lat: float, lng: float, acc: float = 15.0, source: str = LocationSource.GPS.value):
    return {"latitude": lat, "longitude": lng, "accuracy": acc,
            "timestamp": now_utc(), "source": source, "landmark": None}


def demo_events() -> List[Dict[str, Any]]:
    t = now_utc()
    return [
        {
            "eventId": "NDEM-EVENT-2026-00011", "source": "NDEM / authorized disaster-information integration",
            "sourceReference": "NRSC/NDEM/NRT-FLOOD/ASSAM/2026-00011",
            "disasterType": DisasterType.FLOOD.value, "severity": Severity.HIGH.value,
            "infoTier": InfoTier.DISASTER_ACTIVE.value, "status": DisasterStatus.ACTIVE.value,
            "title": "Active flooding — Dhemaji district, Assam", "region": "assam-dhemaji",
            "issuedAt": t - timedelta(hours=6), "updatedAt": t - timedelta(minutes=25),
            "validFrom": t - timedelta(hours=6), "validUntil": t + timedelta(hours=36),
            "affectedArea": DHEMAJI_POLYGON,
            "zones": [{"zone": "RED", "label": "Critical", "geometry": DHEMAJI_POLYGON}],
            "confidence": 0.92, "qualityMetadata": {"observationType": "NEAR_REAL_TIME", "latencyMinutes": 25},
            "instructions": ["Move to the nearest relief shelter immediately.",
                             "Do not attempt to cross flowing water.",
                             "Keep mobile phones charged and SOS available."],
            "version": 3, "experimental": False, "history": [],
        },
        {
            "eventId": "NDEM-EVENT-2026-00024", "source": "NDEM / authorized disaster-information integration",
            "sourceReference": "IMD/CYCLONE-TRACK/BOB-04",
            "disasterType": DisasterType.CYCLONE.value, "severity": Severity.EXTREME.value,
            "infoTier": InfoTier.WARNING_ACTIVE.value, "status": DisasterStatus.WARNING.value,
            "title": "Cyclone warning — Odisha coastal districts", "region": "odisha-coast",
            "issuedAt": t - timedelta(hours=3), "updatedAt": t - timedelta(minutes=40),
            "validFrom": t - timedelta(hours=3), "validUntil": t + timedelta(hours=48),
            "affectedArea": ODISHA_COAST_POLYGON, "zones": [],
            "confidence": 0.81, "qualityMetadata": {"observationType": "FORECAST_TRACK"},
            "instructions": ["Prepare an emergency kit and documents.",
                             "Identify your nearest cyclone shelter now.",
                             "Await evacuation instructions from local authorities."],
            "version": 2, "experimental": False, "history": [],
        },
        {
            "eventId": "NDEM-EVENT-2026-00031", "source": "NDEM / authorized disaster-information integration",
            "sourceReference": "GSI/LANDSLIDE-FORECAST/UK-EXP",
            "disasterType": DisasterType.LANDSLIDE.value, "severity": Severity.MODERATE.value,
            "infoTier": InfoTier.FORECAST.value, "status": DisasterStatus.MONITORING.value,
            "title": "Experimental landslide forecast — Chamoli, Uttarakhand", "region": "uttarakhand-chamoli",
            "issuedAt": t - timedelta(hours=12), "updatedAt": t - timedelta(hours=2),
            "validFrom": t - timedelta(hours=12), "validUntil": t + timedelta(hours=24),
            "affectedArea": UTTARAKHAND_POLYGON, "zones": [],
            "confidence": 0.44,
            "qualityMetadata": {"observationType": "EXPERIMENTAL_FORECAST",
                                "disclaimer": "Experimental product — not a certainty"},
            "instructions": ["Forecast only — no evacuation is being ordered.",
                             "Avoid unnecessary travel on hill roads during heavy rain."],
            "version": 1, "experimental": True, "history": [],
        },
    ]


async def seed(reset: bool = False) -> Dict[str, Any]:
    if reset:
        for coll in (db.users, db.teams, db.shelters, db.disaster_events,
                     db.sos_records, db.resource_requests, db.audit_log,
                     db.search_operations, db.field_incidents, db.road_incidents):
            await coll.delete_many({})

    await db.ensure_indexes()
    pw = hash_password(DEMO_PASSWORD)

    for u in DEMO_USERS:
        doc = dict(u)
        if doc.get("email"):
            doc["passwordHash"] = pw
        doc.setdefault("createdAt", now_utc())
        doc.setdefault("preferredLanguage", "en")
        doc.setdefault("accessibilityRequirements", [])
        doc.setdefault("groupSize", 1)
        await db.users.update_one({"userId": doc["userId"]}, {"$setOnInsert": doc}, upsert=True)

    for t in DEMO_TEAMS:
        doc = dict(t)
        cl = doc.get("currentLocation") or {}
        if cl:
            cl["timestamp"] = now_utc()
            cl.setdefault("landmark", None)
        doc["status"] = TeamStatus.AVAILABLE.value
        doc["activeSosId"] = None
        doc["workload"] = 0
        doc["communicationStatus"] = "ONLINE"
        doc["updatedAt"] = now_utc()
        await db.teams.update_one({"teamId": doc["teamId"]}, {"$setOnInsert": doc}, upsert=True)

    for s in DEMO_SHELTERS:
        cap, occ = s["capacity"], s["occupancy"]
        status = (ShelterStatus.FULL.value if occ >= cap else
                  ShelterStatus.NEAR_CAPACITY.value if occ / cap >= 0.85 else ShelterStatus.OPEN.value)
        doc = {
            "shelterId": s["shelterId"], "name": s["name"], "adminUserId": s["adminUserId"],
            "location": _loc(s["lat"], s["lng"], 10.0), "capacity": cap, "occupancy": occ,
            "foodStatus": "ADEQUATE", "waterStatus": "ADEQUATE", "medicalStatus": "BASIC",
            "status": status, "facilities": s["facilities"], "contactPhone": s["contactPhone"],
            "region": s["region"], "lastUpdated": now_utc(), "occupancyConflict": None,
        }
        await db.shelters.update_one({"shelterId": doc["shelterId"]}, {"$setOnInsert": doc}, upsert=True)

    for e in demo_events():
        await db.disaster_events.update_one({"eventId": e["eventId"]}, {"$setOnInsert": e}, upsert=True)

    demo_requests = [
        {"requestId": "REQ-DEMO001", "shelterId": "SH-S1", "eventId": "NDEM-EVENT-2026-00011",
         "category": "FOOD", "unit": "meal packets", "requestedQuantity": 1800,
         "approvedQuantity": 0, "allocatedQuantity": 0, "sentQuantity": 0, "receivedQuantity": 0,
         "status": ResourceStatus.REQUESTED.value, "ngoId": None, "ngoName": None,
         "createdAt": now_utc(), "updatedAt": now_utc(), "discrepancy": None},
        {"requestId": "REQ-DEMO002", "shelterId": "SH-S3", "eventId": "NDEM-EVENT-2026-00011",
         "category": "DRINKING_WATER", "unit": "litres", "requestedQuantity": 5000,
         "approvedQuantity": 5000, "allocatedQuantity": 5000, "sentQuantity": 4200,
         "receivedQuantity": 0, "status": ResourceStatus.IN_TRANSIT.value,
         "ngoId": "NGO-001", "ngoName": "Seva Bharati Relief",
         "createdAt": now_utc(), "updatedAt": now_utc(), "discrepancy": None},
    ]
    for r in demo_requests:
        await db.resource_requests.update_one({"requestId": r["requestId"]}, {"$setOnInsert": r}, upsert=True)

    return {
        "users": await db.users.count_documents({}),
        "teams": await db.teams.count_documents({}),
        "shelters": await db.shelters.count_documents({}),
        "events": await db.disaster_events.count_documents({}),
        "resourceRequests": await db.resource_requests.count_documents({}),
        "note": "DEMO seed data — disaster events supplied by the seed ingestion adapter",
    }


if __name__ == "__main__":
    print(asyncio.get_event_loop().run_until_complete(seed(reset=False)))
