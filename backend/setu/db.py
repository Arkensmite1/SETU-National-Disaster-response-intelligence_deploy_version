"""Mongo access layer for SETU (spec Section 22 collections).

Uses MONGO_URL / DB_NAME from backend/.env only — never hardcoded.
"""
import os
from motor.motor_asyncio import AsyncIOMotorClient

_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = _client[os.environ["DB_NAME"]]

# Section 22 collections
users = db["users"]
otp_codes = db["otp_codes"]
disaster_events = db["disaster_events"]
sos_records = db["sos_records"]
teams = db["teams"]
shelters = db["shelters"]
resource_requests = db["resource_requests"]
audit_log = db["audit_log"]
search_operations = db["search_operations"]
field_incidents = db["field_incidents"]
road_incidents = db["road_incidents"]
notifications = db["notifications"]
missing_register = db["missing_register"]
arrival_logs = db["arrival_logs"]
ngo_inventory = db["ngo_inventory"]
field_reports = db["field_reports"]
conflicts = db["conflicts"]
ingestion_state = db["ingestion_state"]
situation_reports = db["situation_reports"]


async def ensure_indexes():
    await users.create_index("userId", unique=True)
    await users.create_index("mobile", sparse=True)
    await users.create_index("email", sparse=True)
    await disaster_events.create_index("eventId", unique=True)
    await sos_records.create_index("sosId", unique=True)
    await sos_records.create_index([("userId", 1), ("status", 1)])
    await sos_records.create_index("eventId")
    await teams.create_index("teamId", unique=True)
    await shelters.create_index("shelterId", unique=True)
    await resource_requests.create_index("requestId", unique=True)
    await audit_log.create_index([("objectType", 1), ("objectId", 1), ("timestamp", 1)])
