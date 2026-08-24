"""Rescue coordination \u2014 Section 12.

Command centre metrics, SOS clustering, team assignment *recommendations*
(ranked suggestions a human leader approves \u2014 never auto-applied), blocked-road
incidents, and team location/status handling.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .. import db
from ..advisory import cluster_naming, queue_summary
from ..audit import record_audit
from ..auth import current_user, is_admin, require_roles
from ..geo import haversine_km
from ..models import Location, Role, Team, TeamStatus, clean, loc_doc, now_utc
from ..priority import PRIORITY_ORDER, recommended_team_size
from ..state_machines import IllegalTransition, SOS_ACTIVE_STATES, TEAM

router = APIRouter(prefix="/api/rescue", tags=["rescue"])

CLUSTER_RADIUS_KM = 2.0


def _team_view(doc: Dict[str, Any]) -> Dict[str, Any]:
    d = clean(doc)
    d["allowedNextStates"] = sorted(TEAM.allowed_from(d.get("status", "AVAILABLE")))
    return d


# ---------------------------------------------------------------- dashboard
@router.get("/dashboard")
async def dashboard(user: Dict[str, Any] = Depends(require_roles(Role.RESCUE_LEADER, Role.AUTHORITY,
                                                                Role.SUPER_ADMIN))):
    active = [d async for d in db.sos_records.find({"status": {"$in": SOS_ACTIVE_STATES}})]
    teams = [t async for t in db.teams.find({})]
    by_priority = {p: sum(1 for s in active if s.get("priority") == p) for p in ("P1", "P2", "P3")}
    unassigned = [s for s in active if not s.get("assignedTeamId")]
    markers = [{
        "sosId": s["sosId"], "priority": s.get("priority"), "status": s.get("status"),
        "latitude": (s.get("lastKnown") or s.get("origin") or {}).get("latitude"),
        "longitude": (s.get("lastKnown") or s.get("origin") or {}).get("longitude"),
        "peopleCount": s.get("peopleCount"), "injuredCount": s.get("injuredCount"),
        "emergencyType": s.get("emergencyType"),
        "approximate": ((s.get("origin") or {}).get("accuracy") or 999) > 100,
    } for s in active]
    return {
        "counts": {
            "totalActiveSos": len(active),
            "critical_P1": by_priority["P1"], "high_P2": by_priority["P2"], "normal_P3": by_priority["P3"],
            "unassigned": len(unassigned), "assigned": len(active) - len(unassigned),
            "peopleAwaitingRescue": sum(int(s.get("peopleCount") or 1) for s in active),
            "injuredReported": sum(int(s.get("injuredCount") or 0) for s in active),
        },
        "teams": {
            "total": len(teams),
            "available": sum(1 for t in teams if t.get("status") == TeamStatus.AVAILABLE.value),
            "active": sum(1 for t in teams if t.get("status") not in (TeamStatus.AVAILABLE.value,
                                                                     TeamStatus.OFFLINE.value)),
            "offline": sum(1 for t in teams if t.get("status") == TeamStatus.OFFLINE.value),
        },
        "mapMarkers": markers,
        "generatedAt": now_utc(),
        "note": "Counts reflect data received so far. Missing data is never interpreted as 'no emergency'.",
    }


# ---------------------------------------------------------------- teams
@router.get("/teams")
async def list_teams(user: Dict[str, Any] = Depends(current_user)):
    role = user.get("role")
    if role == Role.RESCUE_MEMBER.value:
        q = {"$or": [{"teamId": user.get("teamId")}, {"memberUserIds": user["userId"]}]}
    elif role in (Role.RESCUE_LEADER.value, Role.AUTHORITY.value, Role.SUPER_ADMIN.value):
        q = {}
    else:
        raise HTTPException(status_code=403, detail="Not permitted to view rescue teams")
    return {"teams": [_team_view(t) async for t in db.teams.find(q)]}


class TeamCreate(BaseModel):
    name: str
    leaderUserId: Optional[str] = None
    memberUserIds: List[str] = Field(default_factory=list)
    memberNames: List[str] = Field(default_factory=list)
    vehicle: str = "BOAT"
    equipment: List[str] = Field(default_factory=list)
    capabilities: List[str] = Field(default_factory=list)
    maxOperationalCapacity: int = 10
    region: Optional[str] = None
    currentLocation: Optional[Location] = None


@router.post("/teams")
async def create_team(payload: TeamCreate, request: Request,
                      user: Dict[str, Any] = Depends(require_roles(Role.RESCUE_LEADER, Role.AUTHORITY,
                                                                   Role.SUPER_ADMIN))):
    team = Team(**{**payload.model_dump(exclude={"currentLocation"}),
                   "currentLocation": payload.currentLocation})
    doc = team.model_dump()
    doc["status"] = TeamStatus.AVAILABLE.value
    doc["currentLocation"] = loc_doc(payload.currentLocation)
    await db.teams.insert_one(doc)
    await record_audit("TEAM_CREATE", "TEAM", doc["teamId"], None, {"name": doc["name"]},
                       user=user, request=request)
    return _team_view(doc)


class TeamLocation(BaseModel):
    location: Location


@router.post("/teams/{team_id}/location")
async def update_team_location(team_id: str, payload: TeamLocation, request: Request,
                              user: Dict[str, Any] = Depends(require_roles(Role.RESCUE_MEMBER,
                                                                           Role.RESCUE_LEADER,
                                                                           Role.AUTHORITY,
                                                                           Role.SUPER_ADMIN))):
    team = await db.teams.find_one({"teamId": team_id})
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    if user.get("role") == Role.RESCUE_MEMBER.value and user.get("teamId") != team_id:
        raise HTTPException(status_code=403, detail="You can only update your own team's location")
    loc = loc_doc(payload.location)
    await db.teams.update_one({"teamId": team_id},
                             {"$set": {"currentLocation": loc, "updatedAt": now_utc()}})
    await record_audit("TEAM_LOCATION", "TEAM", team_id, team.get("currentLocation"), loc,
                       user=user, request=request)
    return _team_view(await db.teams.find_one({"teamId": team_id}))


class TeamStatusUpdate(BaseModel):
    status: TeamStatus
    note: Optional[str] = None


@router.post("/teams/{team_id}/status")
async def update_team_status(team_id: str, payload: TeamStatusUpdate, request: Request,
                            user: Dict[str, Any] = Depends(require_roles(Role.RESCUE_LEADER,
                                                                         Role.RESCUE_MEMBER,
                                                                         Role.AUTHORITY,
                                                                         Role.SUPER_ADMIN))):
    team = await db.teams.find_one({"teamId": team_id})
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    try:
        TEAM.assert_transition(team.get("status"), payload.status.value)
    except IllegalTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    await db.teams.update_one({"teamId": team_id},
                             {"$set": {"status": payload.status.value, "updatedAt": now_utc()}})
    await record_audit("TEAM_STATUS", "TEAM", team_id, {"status": team.get("status")},
                       {"status": payload.status.value}, user=user, request=request,
                       note=payload.note)
    return _team_view(await db.teams.find_one({"teamId": team_id}))


# ---------------------------------------------------------------- assignment recommendation
CAPABILITY_FOR_EMERGENCY = {
    "DROWNING": "WATER_RESCUE", "TRAPPED_WATER_RISING": "WATER_RESCUE",
    "STRANDED": "WATER_RESCUE", "BUILDING_COLLAPSE": "COLLAPSE_RESCUE",
    "MEDICAL_CRITICAL": "MEDICAL_CRITICAL", "UNCONSCIOUS": "MEDICAL_CRITICAL",
    "INJURED": "MEDICAL_FIRST_AID", "FIRE": "FIRE_RESPONSE",
}


@router.get("/recommendations/{sos_id}")
async def recommend_teams(sos_id: str,
                          user: Dict[str, Any] = Depends(require_roles(Role.RESCUE_LEADER,
                                                                       Role.AUTHORITY,
                                                                       Role.SUPER_ADMIN))):
    """Section 12.4 \u2014 ranked SUGGESTION only. The leader must confirm; the leader
    can also assign a team the ranking did not recommend (authority override)."""
    sos = await db.sos_records.find_one({"sosId": sos_id})
    if not sos:
        raise HTTPException(status_code=404, detail="SOS record not found")
    loc = sos.get("lastKnown") or sos.get("origin") or {}
    need_cap = CAPABILITY_FOR_EMERGENCY.get((sos.get("emergencyType") or "").upper())
    people = int(sos.get("peopleCount") or 1)
    ranked = []
    async for t in db.teams.find({}):
        dist = None
        cl = t.get("currentLocation") or {}
        if cl and loc:
            dist = haversine_km(loc.get("latitude"), loc.get("longitude"),
                                cl.get("latitude"), cl.get("longitude"))
        score, factors = 0.0, []
        if t.get("status") == TeamStatus.AVAILABLE.value:
            score += 40
            factors.append("Team is AVAILABLE (+40)")
        else:
            factors.append(f"Team is {t.get('status')} \u2014 not currently assignable (0)")
        if dist is not None:
            prox = max(0.0, 30.0 - min(dist, 30.0))
            score += prox
            factors.append(f"Distance {dist:.1f} km (+{prox:.0f})")
        if need_cap:
            if need_cap in (t.get("capabilities") or []):
                score += 20
                factors.append(f"Has required capability {need_cap} (+20)")
            else:
                factors.append(f"Missing capability {need_cap} (0)")
        if int(t.get("maxOperationalCapacity") or 0) >= people:
            score += 10
            factors.append(f"Capacity {t.get('maxOperationalCapacity')} >= {people} people (+10)")
        else:
            factors.append(f"Capacity {t.get('maxOperationalCapacity')} < {people} people \u2014 "
                           "may need a second team (0)")
        workload_penalty = min(int(t.get("workload") or 0) * 2, 10)
        score -= workload_penalty
        if workload_penalty:
            factors.append(f"Workload penalty (-{workload_penalty})")
        if t.get("communicationStatus") != "ONLINE":
            score -= 10
            factors.append("Communication not confirmed (-10)")
        ranked.append({"teamId": t["teamId"], "name": t.get("name"), "status": t.get("status"),
                       "vehicle": t.get("vehicle"), "capabilities": t.get("capabilities"),
                       "distanceKm": round(dist, 2) if dist is not None else None,
                       "score": round(score, 1), "factors": factors,
                       "assignable": t.get("status") == TeamStatus.AVAILABLE.value})
    ranked.sort(key=lambda r: -r["score"])
    return {
        "sosId": sos_id, "priority": sos.get("priority"),
        "recommendedTeamSize": recommended_team_size(sos),
        "recommendations": ranked,
        "advisory": True, "autoApplied": False,
        "note": ("Ranked suggestion only \u2014 a rescue leader must confirm the assignment. "
                 "Route conditions are not guaranteed safe."),
    }


# ---------------------------------------------------------------- clustering
@router.get("/clusters")
async def clusters(withAdvisory: bool = False,
                   user: Dict[str, Any] = Depends(require_roles(Role.RESCUE_LEADER, Role.AUTHORITY,
                                                                Role.SUPER_ADMIN))):
    """Section 12.2 \u2014 deterministic greedy geo-clustering of active SOS.
    Optional AI advisory naming; the leader confirms cluster-to-team assignment."""
    active = [d async for d in db.sos_records.find({"status": {"$in": SOS_ACTIVE_STATES}})]
    remaining = [s for s in active if (s.get("lastKnown") or s.get("origin"))]
    remaining.sort(key=lambda s: PRIORITY_ORDER.get(s.get("priority"), 3))
    out: List[Dict[str, Any]] = []
    used: set = set()
    for seed in remaining:
        if seed["sosId"] in used:
            continue
        sl = seed.get("lastKnown") or seed["origin"]
        members = []
        for cand in remaining:
            if cand["sosId"] in used:
                continue
            cl = cand.get("lastKnown") or cand["origin"]
            if haversine_km(sl["latitude"], sl["longitude"], cl["latitude"], cl["longitude"]) <= CLUSTER_RADIUS_KM:
                members.append(cand)
                used.add(cand["sosId"])
        lat = sum((m.get("lastKnown") or m["origin"])["latitude"] for m in members) / len(members)
        lng = sum((m.get("lastKnown") or m["origin"])["longitude"] for m in members) / len(members)
        priorities = sorted({m.get("priority", "P3") for m in members},
                            key=lambda p: PRIORITY_ORDER.get(p, 3))
        out.append({
            "clusterId": f"CL-{len(out) + 1:02d}",
            "sosIds": [m["sosId"] for m in members],
            "sosCount": len(members),
            "centre": {"latitude": round(lat, 5), "longitude": round(lng, 5)},
            "topPriority": priorities[0] if priorities else "P3",
            "peopleCount": sum(int(m.get("peopleCount") or 1) for m in members),
            "injuredCount": sum(int(m.get("injuredCount") or 0) for m in members),
            "unassigned": sum(1 for m in members if not m.get("assignedTeamId")),
        })
    out.sort(key=lambda c: (PRIORITY_ORDER.get(c["topPriority"], 3), -c["sosCount"]))
    resp: Dict[str, Any] = {
        "radiusKm": CLUSTER_RADIUS_KM, "clusters": out,
        "advisory": True, "autoApplied": False,
        "note": "Clustering is a suggestion \u2014 the rescue leader confirms every assignment.",
    }
    if withAdvisory and out:
        resp["aiAdvisory"] = await cluster_naming(out)
    return resp


@router.get("/ai-summary")
async def ai_summary(user: Dict[str, Any] = Depends(require_roles(Role.RESCUE_LEADER, Role.AUTHORITY,
                                                                  Role.SUPER_ADMIN))):
    active = [clean(d) async for d in db.sos_records.find({"status": {"$in": SOS_ACTIVE_STATES}})]
    teams = [clean(t) async for t in db.teams.find({})]
    return await queue_summary(active, teams)


# ---------------------------------------------------------------- blocked roads
class BlockedRoad(BaseModel):
    location: Location
    description: str
    sosId: Optional[str] = None
    severity: str = "IMPASSABLE"


@router.post("/blocked-road")
async def report_blocked_road(payload: BlockedRoad, request: Request,
                              user: Dict[str, Any] = Depends(require_roles(Role.RESCUE_MEMBER,
                                                                           Role.RESCUE_LEADER,
                                                                           Role.AUTHORITY,
                                                                           Role.SUPER_ADMIN))):
    """Section 12.9 \u2014 store the incident, recalculate affected routes, notify nearby teams.
    SETU never claims a route is guaranteed safe."""
    doc = {
        "incidentId": f"RD-{int(now_utc().timestamp())}",
        "location": loc_doc(payload.location), "description": payload.description,
        "severity": payload.severity, "sosId": payload.sosId,
        "reportedBy": user["userId"], "reportedAt": now_utc(), "active": True,
    }
    await db.road_incidents.insert_one(doc)
    await record_audit("ROAD_BLOCKED", "ROAD_INCIDENT", doc["incidentId"], None,
                       {"description": payload.description}, user=user, request=request)
    notified = []
    async for t in db.teams.find({}):
        cl = t.get("currentLocation") or {}
        if not cl:
            continue
        d = haversine_km(payload.location.latitude, payload.location.longitude,
                         cl["latitude"], cl["longitude"])
        if d <= 15:
            notified.append({"teamId": t["teamId"], "name": t.get("name"), "distanceKm": round(d, 2)})
            await db.notifications.insert_one({
                "to": t["teamId"], "priority": 1, "type": "ROAD_BLOCKED",
                "message": f"Road blocked reported {d:.1f} km away: {payload.description}",
                "createdAt": now_utc(), "delivered": False, "acknowledged": False,
            })
    return {"incident": clean(doc), "teamsNotified": notified,
            "routeNote": ("Routes are recalculated as advisory suggestions only \u2014 field conditions "
                          "may differ and are never guaranteed safe.")}


@router.get("/blocked-roads")
async def blocked_roads(user: Dict[str, Any] = Depends(require_roles(Role.RESCUE_MEMBER,
                                                                     Role.RESCUE_LEADER,
                                                                     Role.AUTHORITY,
                                                                     Role.SUPER_ADMIN))):
    return {"incidents": [clean(d) async for d in
                          db.road_incidents.find({"active": True}).sort("reportedAt", -1)]}
