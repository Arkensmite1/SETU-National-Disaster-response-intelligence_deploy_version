"""Phase 5 — Search & verification (Section 13).

Core rules encoded here:
* "Not found" is NEVER treated as "safe". A closed search with no result creates a
  missing-person register entry that stays open for follow-up.
* Search is systematic: an area is divided into grid cells and each cell carries
  its own searched/unsearched state, searcher and timestamp — so coverage gaps
  are visible instead of assumed.
* People found in the field who never sent an SOS are first-class records.
* Every verification step is audited.
"""
import math
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .. import db
from ..audit import record_audit
from ..auth import current_user, is_admin, require_roles
from ..models import (FieldIncident, Location, Role, SearchOperation, clean, loc_doc,
                      now_utc)

router = APIRouter(prefix="/api/search", tags=["search"])

RESCUE_ANY = require_roles(Role.RESCUE_MEMBER, Role.RESCUE_LEADER, Role.AUTHORITY, Role.SUPER_ADMIN)
LEADER_UP = require_roles(Role.RESCUE_LEADER, Role.AUTHORITY, Role.SUPER_ADMIN)

CELL_RESULTS = {"NOT_SEARCHED", "NOTHING_FOUND", "PEOPLE_FOUND", "SIGNS_FOUND", "INACCESSIBLE"}


def build_grid(centre: Location, radius_m: int = 500, cell_m: int = 250) -> List[Dict[str, Any]]:
    """Section 13.2 — deterministic grid so coverage is measurable."""
    deg_lat = cell_m / 111_320
    deg_lng = cell_m / (111_320 * max(math.cos(math.radians(centre.latitude)), 0.01))
    steps = max(int(radius_m / cell_m), 1)
    cells = []
    for i in range(-steps, steps + 1):
        for j in range(-steps, steps + 1):
            cells.append({
                "cellId": f"C{i + steps}-{j + steps}",
                "centre": {"latitude": round(centre.latitude + i * deg_lat, 6),
                           "longitude": round(centre.longitude + j * deg_lng, 6)},
                "sizeMetres": cell_m,
                "result": "NOT_SEARCHED",
                "searchedBy": None,
                "searchedAt": None,
                "peopleFound": 0,
                "note": None,
            })
    return cells


class SearchStart(BaseModel):
    centre: Location
    sosId: Optional[str] = None
    eventId: Optional[str] = None
    teamId: Optional[str] = None
    areaDescription: str = ""
    radiusMetres: int = 500
    cellMetres: int = 250
    reason: str = "USER_NOT_FOUND"


class CellUpdate(BaseModel):
    result: str
    peopleFound: int = 0
    note: Optional[str] = None


class SearchClose(BaseModel):
    outcome: str            # FOUND | NOT_FOUND | SUSPENDED
    peopleFound: int = 0
    peopleMissing: int = 0
    observations: Optional[str] = None
    suspendReason: Optional[str] = None


class IncidentCreate(BaseModel):
    location: Location
    unknownPersons: int = 1
    condition: str = "UNKNOWN"          # STABLE | INJURED | CRITICAL | DECEASED | UNKNOWN
    transportRequired: bool = False
    notes: Optional[str] = None
    eventId: Optional[str] = None
    handedOverToShelterId: Optional[str] = None


async def open_search_for_sos(sos: Dict[str, Any], user: Dict[str, Any],
                             request: Optional[Request] = None) -> Optional[Dict[str, Any]]:
    """Called from the SOS router when a case moves to USER_NOT_FOUND / SEARCHING."""
    existing = await db.search_operations.find_one({"sosId": sos["sosId"], "status": "IN_PROGRESS"})
    if existing:
        return _view(existing)
    src = sos.get("lastKnown") or sos.get("origin") or {}
    if not src:
        return None
    centre = Location(latitude=src["latitude"], longitude=src["longitude"],
                      accuracy=src.get("accuracy"), source=src.get("source", "GPS"))
    op = SearchOperation(
        eventId=sos.get("eventId"), sosId=sos["sosId"], teamId=sos.get("assignedTeamId"),
        areaDescription=f"Auto-opened search around last known location of {sos['sosId']}",
        gridCells=build_grid(centre, 500, 250), peopleMissing=int(sos.get("peopleCount") or 1),
    )
    doc = op.model_dump()
    doc["centre"] = loc_doc(centre)
    doc["reason"] = "USER_NOT_FOUND"
    doc["autoOpened"] = True
    await db.search_operations.insert_one(doc)
    await record_audit("SEARCH_OPENED", "SEARCH_OPERATION", doc["searchId"], None,
                       {"sosId": sos["sosId"], "cells": len(doc["gridCells"]), "auto": True},
                       user=user, request=request,
                       note="'Not found' is not 'safe' — systematic search opened automatically")
    return _view(doc)


@router.post("/operations")
async def start_search(payload: SearchStart, request: Request,
                       user: Dict[str, Any] = Depends(RESCUE_ANY)):
    op = SearchOperation(
        eventId=payload.eventId, sosId=payload.sosId,
        teamId=payload.teamId or user.get("teamId"),
        areaDescription=payload.areaDescription or "Area search",
        gridCells=build_grid(payload.centre, payload.radiusMetres, payload.cellMetres),
    )
    doc = op.model_dump()
    doc["centre"] = loc_doc(payload.centre)
    doc["reason"] = payload.reason
    doc["autoOpened"] = False
    await db.search_operations.insert_one(doc)
    await record_audit("SEARCH_OPENED", "SEARCH_OPERATION", doc["searchId"], None,
                       {"cells": len(doc["gridCells"]), "sosId": payload.sosId},
                       user=user, request=request)
    return _view(doc)


def _view(doc: Dict[str, Any]) -> Dict[str, Any]:
    d = clean(doc)
    cells = d.get("gridCells") or []
    searched = [c for c in cells if c.get("result") != "NOT_SEARCHED"]
    d["coverage"] = {
        "totalCells": len(cells),
        "searchedCells": len(searched),
        "percent": round(100 * len(searched) / len(cells), 1) if cells else 0,
        "inaccessibleCells": sum(1 for c in cells if c.get("result") == "INACCESSIBLE"),
        "cellsWithPeople": sum(1 for c in cells if c.get("result") == "PEOPLE_FOUND"),
    }
    d["coverageNote"] = (
        f"{d['coverage']['searchedCells']} of {d['coverage']['totalCells']} cells searched — "
        "unsearched cells are shown as unknown, never as clear."
    )
    return d


@router.get("/operations")
async def list_searches(status: Optional[str] = None, sosId: Optional[str] = None,
                        user: Dict[str, Any] = Depends(RESCUE_ANY)):
    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    if sosId:
        q["sosId"] = sosId
    if user.get("role") == Role.RESCUE_MEMBER.value and user.get("teamId"):
        q["teamId"] = user["teamId"]
    cur = db.search_operations.find(q).sort("startedAt", -1)
    return {"operations": [_view(d) async for d in cur]}


@router.get("/operations/{search_id}")
async def get_search(search_id: str, user: Dict[str, Any] = Depends(RESCUE_ANY)):
    doc = await db.search_operations.find_one({"searchId": search_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Search operation not found")
    return _view(doc)


@router.post("/operations/{search_id}/cells/{cell_id}")
async def update_cell(search_id: str, cell_id: str, payload: CellUpdate, request: Request,
                      user: Dict[str, Any] = Depends(RESCUE_ANY)):
    if payload.result not in CELL_RESULTS:
        raise HTTPException(status_code=400, detail=f"result must be one of {sorted(CELL_RESULTS)}")
    doc = await db.search_operations.find_one({"searchId": search_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Search operation not found")
    if doc.get("status") != "IN_PROGRESS":
        raise HTTPException(status_code=409, detail=f"Search is {doc.get('status')} — reopen it before recording cells")
    cells = doc.get("gridCells") or []
    target = next((c for c in cells if c["cellId"] == cell_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Grid cell not found")
    old = dict(target)
    target.update({"result": payload.result, "peopleFound": payload.peopleFound,
                   "note": payload.note, "searchedBy": user["userId"], "searchedAt": now_utc()})
    found_total = sum(int(c.get("peopleFound") or 0) for c in cells)
    await db.search_operations.update_one(
        {"searchId": search_id},
        {"$set": {"gridCells": cells, "peopleFound": found_total}})
    await record_audit("SEARCH_CELL", "SEARCH_OPERATION", search_id,
                       {"cellId": cell_id, "result": old.get("result")},
                       {"cellId": cell_id, "result": payload.result,
                        "peopleFound": payload.peopleFound},
                       user=user, request=request, note=payload.note)
    return _view(await db.search_operations.find_one({"searchId": search_id}))


@router.post("/operations/{search_id}/close")
async def close_search(search_id: str, payload: SearchClose, request: Request,
                       user: Dict[str, Any] = Depends(RESCUE_ANY)):
    if payload.outcome not in ("FOUND", "NOT_FOUND", "SUSPENDED"):
        raise HTTPException(status_code=400, detail="outcome must be FOUND, NOT_FOUND or SUSPENDED")
    doc = await db.search_operations.find_one({"searchId": search_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Search operation not found")
    status = {"FOUND": "CLOSED_FOUND", "NOT_FOUND": "CLOSED_NOT_FOUND", "SUSPENDED": "SUSPENDED"}[payload.outcome]
    await db.search_operations.update_one(
        {"searchId": search_id},
        {"$set": {"status": status, "endedAt": now_utc(), "peopleFound": payload.peopleFound,
                  "peopleMissing": payload.peopleMissing, "observations": payload.observations,
                  "suspendReason": payload.suspendReason}})
    await record_audit("SEARCH_CLOSED", "SEARCH_OPERATION", search_id,
                       {"status": doc.get("status")},
                       {"status": status, "peopleFound": payload.peopleFound,
                        "peopleMissing": payload.peopleMissing},
                       user=user, request=request, note=payload.observations)

    register_entry = None
    if payload.outcome in ("NOT_FOUND", "SUSPENDED") and payload.peopleMissing > 0:
        register_entry = {
            "entryId": f"MIS-{search_id[-6:]}-{int(now_utc().timestamp())}",
            "searchId": search_id, "sosId": doc.get("sosId"), "eventId": doc.get("eventId"),
            "peopleMissing": payload.peopleMissing, "lastKnownLocation": doc.get("centre"),
            "status": "OPEN", "createdAt": now_utc(), "createdBy": user["userId"],
            "observations": payload.observations,
            "note": "Search closed without locating the person(s). This is NOT a confirmation of safety.",
        }
        await db.missing_register.insert_one(register_entry)
        await record_audit("MISSING_REGISTER_OPENED", "MISSING_ENTRY", register_entry["entryId"],
                           None, {"peopleMissing": payload.peopleMissing},
                           user=user, request=request)
        register_entry = clean(register_entry)

    out = _view(await db.search_operations.find_one({"searchId": search_id}))
    out["missingRegisterEntry"] = register_entry
    out["note"] = ("Search closed. A 'not found' outcome is recorded as unresolved and escalated — "
                   "it is never recorded as the person being safe.")
    return out


@router.get("/missing-register")
async def missing_register(status: Optional[str] = "OPEN",
                           user: Dict[str, Any] = Depends(RESCUE_ANY)):
    q = {"status": status} if status else {}
    cur = db.missing_register.find(q).sort("createdAt", -1)
    return {"entries": [clean(d) async for d in cur],
            "note": "Unresolved cases remain open until a human closes them with evidence."}


class RegisterResolve(BaseModel):
    resolution: str          # LOCATED_SAFE | LOCATED_DECEASED | TRANSFERRED | CLOSED_UNRESOLVED
    evidence: str


@router.post("/missing-register/{entry_id}/resolve")
async def resolve_register(entry_id: str, payload: RegisterResolve, request: Request,
                           user: Dict[str, Any] = Depends(LEADER_UP)):
    doc = await db.missing_register.find_one({"entryId": entry_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Register entry not found")
    await db.missing_register.update_one(
        {"entryId": entry_id},
        {"$set": {"status": "RESOLVED", "resolution": payload.resolution,
                  "evidence": payload.evidence, "resolvedAt": now_utc(),
                  "resolvedBy": user["userId"]}})
    await record_audit("MISSING_REGISTER_RESOLVED", "MISSING_ENTRY", entry_id,
                       {"status": doc.get("status")},
                       {"status": "RESOLVED", "resolution": payload.resolution},
                       user=user, request=request, note=payload.evidence)
    return clean(await db.missing_register.find_one({"entryId": entry_id}))


@router.post("/incidents")
async def create_incident(payload: IncidentCreate, request: Request,
                          user: Dict[str, Any] = Depends(RESCUE_ANY)):
    """Section 13.4 — people found in the field who never sent an SOS."""
    inc = FieldIncident(
        eventId=payload.eventId, teamId=user.get("teamId"), location=payload.location,
        unknownPersons=payload.unknownPersons, condition=payload.condition,
        transportRequired=payload.transportRequired, notes=payload.notes,
    )
    doc = inc.model_dump()
    doc["location"] = loc_doc(payload.location)
    doc["handedOverToShelterId"] = payload.handedOverToShelterId
    doc["reportedBy"] = user["userId"]
    doc["status"] = "RECORDED"
    await db.field_incidents.insert_one(doc)
    await record_audit("FIELD_INCIDENT", "FIELD_INCIDENT", doc["incidentId"], None,
                       {"unknownPersons": payload.unknownPersons, "condition": payload.condition},
                       user=user, request=request, note=payload.notes)
    out = clean(doc)
    out["note"] = ("Recorded as a rescue outcome even though no SOS exists — people who cannot "
                   "reach the app still appear in SETU's numbers.")
    return out


@router.get("/incidents")
async def list_incidents(user: Dict[str, Any] = Depends(RESCUE_ANY)):
    q: Dict[str, Any] = {}
    if user.get("role") == Role.RESCUE_MEMBER.value and user.get("teamId"):
        q["teamId"] = user["teamId"]
    cur = db.field_incidents.find(q).sort("createdAt", -1)
    return {"incidents": [clean(d) async for d in cur]}


@router.get("/summary")
async def search_summary(user: Dict[str, Any] = Depends(LEADER_UP)):
    ops = [_view(d) async for d in db.search_operations.find({})]
    return {
        "operations": {
            "total": len(ops),
            "inProgress": sum(1 for o in ops if o.get("status") == "IN_PROGRESS"),
            "closedFound": sum(1 for o in ops if o.get("status") == "CLOSED_FOUND"),
            "closedNotFound": sum(1 for o in ops if o.get("status") == "CLOSED_NOT_FOUND"),
            "suspended": sum(1 for o in ops if o.get("status") == "SUSPENDED"),
        },
        "peopleFoundInSearches": sum(int(o.get("peopleFound") or 0) for o in ops),
        "openMissingEntries": await db.missing_register.count_documents({"status": "OPEN"}),
        "fieldIncidents": await db.field_incidents.count_documents({}),
        "unknownPersonsRecorded": sum([int(d.get("unknownPersons") or 0)
                                       async for d in db.field_incidents.find({})] or [0]),
        "note": "Unsearched area is reported as unknown coverage, never as cleared.",
    }
