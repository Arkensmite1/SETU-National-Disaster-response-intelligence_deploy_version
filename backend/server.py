from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import uuid
import json
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from mock_data import (  # noqa: E402
    REGIONS, VILLAGES, SHELTERS, ROAD_CLOSURES, RESERVOIRS, RESOURCES,
    ALLOCATIONS, INCIDENTS, VOLUNTEERS, SOCIAL_POSTS, WEATHER,
    PREDICTIONS, XAI_FACTORS, ALERTS, MEDICAL_OUTBREAK, ECONOMIC_LOSS,
    PREPAREDNESS, EMERGENCY_CONTACTS, DRONES, FAMILY_REGISTRY, OVERVIEW_STATS,
)
import ai_service  # noqa: E402

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="Setu — National Disaster Response Intelligence")
api_router = APIRouter(prefix="/api")


# ---------- Pydantic models ----------
class ChatRequest(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    message: str
    lang: Optional[str] = "en"


class SOSRequest(BaseModel):
    name: str
    phone: str
    location: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    situation: str
    people_count: int = 1


class VolunteerRegister(BaseModel):
    name: str
    phone: str
    skill: str
    location: str


class FamilyCheckIn(BaseModel):
    name: str
    age: int
    last_seen: str
    contact: Optional[str] = None
    status: str = "safe"  # safe | missing | found


class ImagePayload(BaseModel):
    image_base64: str
    context: Optional[str] = ""


class FakeNewsPayload(BaseModel):
    text: str
    source: Optional[str] = ""


class ExplainRequest(BaseModel):
    region_id: str


class RescueRouteRequest(BaseModel):
    from_lat: float
    from_lng: float
    to_lat: float
    to_lng: float
    boat: bool = True


class ShelterRequest(BaseModel):
    lat: float
    lng: float
    needs_medical: bool = False


class SimulationRequest(BaseModel):
    rainfall_mm: int
    region_id: str


# ---------- Basic ----------
@api_router.get("/")
async def root():
    return {"platform": "Setu", "version": "1.0.0", "status": "operational"}


@api_router.get("/overview/stats")
async def overview():
    return {"stats": OVERVIEW_STATS, "generated_at": datetime.now(timezone.utc).isoformat()}


@api_router.get("/alerts/ticker")
async def ticker():
    return {"alerts": ALERTS}


@api_router.get("/regions")
async def regions():
    return {"regions": REGIONS}


@api_router.get("/monitoring/map-data")
async def map_data():
    return {
        "villages": VILLAGES,
        "shelters": SHELTERS,
        "road_closures": ROAD_CLOSURES,
        "reservoirs": RESERVOIRS,
    }


# ---------- Predictions & XAI ----------
@api_router.get("/prediction/{region_id}")
async def prediction(region_id: str):
    p = PREDICTIONS.get(region_id)
    r = next((x for x in REGIONS if x["id"] == region_id), None)
    if not p or not r:
        raise HTTPException(404, "Region not found")
    factors = XAI_FACTORS.get(region_id, XAI_FACTORS["default"])
    return {"region": r, "prediction": p, "factors": factors}


@api_router.get("/predictions/all")
async def predictions_all():
    out = []
    for r in REGIONS:
        p = PREDICTIONS.get(r["id"])
        if p:
            out.append({"region": r, "prediction": p})
    return {"items": out}


@api_router.post("/prediction/explain")
async def explain_prediction(req: ExplainRequest):
    p = PREDICTIONS.get(req.region_id)
    r = next((x for x in REGIONS if x["id"] == req.region_id), None)
    if not p or not r:
        raise HTTPException(404, "Region not found")
    factors = XAI_FACTORS.get(req.region_id, XAI_FACTORS["default"])
    prompt = (
        f"You are the Explainable-AI module of a flood forecasting system. "
        f"For {r['name']} (river: {r['river']}, population: {r['population']:,}), "
        f"the model predicts {p['probability']}% flood probability with expected "
        f"water depth {p['expected_depth_m']} m within {p['time_remaining_hr']} hours. "
        f"Key contributing factors detected: "
        + "; ".join(f"{f['factor']} (weight {int(f['impact']*100)}%)" for f in factors)
        + ". Write a 4-6 sentence transparent explanation for a district magistrate, "
        "including one immediate recommended action. Plain English, no jargon."
    )
    try:
        explanation = await ai_service.generate_text(prompt)
    except Exception as e:
        logging.exception("XAI failure")
        explanation = (
            f"Model outputs {p['probability']}% probability primarily because "
            + "; ".join(f["factor"] for f in factors[:3])
            + ". Recommend pre-positioning NDRF teams and issuing evacuation orders "
            "for low-lying wards immediately."
        )
    return {"explanation": explanation, "factors": factors, "prediction": p, "region": r}


# ---------- Resources & Allocation ----------
@api_router.get("/resources")
async def resources():
    return {"inventory": RESOURCES, "allocations": ALLOCATIONS}


@api_router.post("/resources/optimize")
async def optimize_resources():
    prompt = (
        "You are the AI Resource Allocation optimiser for Indian flood response. "
        f"Available inventory: {json.dumps(RESOURCES)}. "
        f"Current allocations: {json.dumps(ALLOCATIONS)}. "
        "Suggest 3 concrete re-allocation actions to reduce response time and "
        "prioritise critical villages. Format as short numbered bullets."
    )
    try:
        suggestion = await ai_service.generate_text(prompt)
    except Exception:
        suggestion = (
            "1. Shift 2 boats from Bahadurpur to Majuli Island (higher trapped count).\n"
            "2. Move 1 medical team from Kuttanad to Gosaba (embankment risk).\n"
            "3. Dispatch 200 additional food kits from Kolkata warehouse to Sundarbans."
        )
    return {"suggestion": suggestion, "allocations": ALLOCATIONS}


# ---------- Shelter ----------
def _hav(lat1, lng1, lat2, lng2):
    from math import radians, sin, cos, asin, sqrt
    lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
    return 6371 * 2 * asin(sqrt(a))


@api_router.post("/shelter/recommend")
async def recommend_shelter(req: ShelterRequest):
    ranked = []
    for s in SHELTERS:
        dist_km = _hav(req.lat, req.lng, s["lat"], s["lng"])
        free = s["capacity"] - s["occupied"]
        score = free / max(dist_km, 0.5)
        if req.needs_medical and not s["medical"]:
            score *= 0.4
        ranked.append({**s, "distance_km": round(dist_km, 2), "free": free, "score": round(score, 2)})
    ranked.sort(key=lambda x: (-x["score"], x["distance_km"]))
    top = ranked[:5]
    reason = (
        f"Top pick: {top[0]['name']} — {top[0]['distance_km']} km away, "
        f"{top[0]['free']} beds free"
        + (", medical team on-site." if top[0]["medical"] else ", no on-site medical.")
    )
    return {"recommendations": top, "reasoning": reason}


# ---------- Image analysis (Damage / Water Depth / Classification) ----------
@api_router.post("/damage/estimate")
async def damage_estimate(payload: ImagePayload):
    prompt = (
        "You are an AI damage-assessment analyst for flood response. Analyse this "
        "image (satellite / drone / street). Return a concise report in this exact "
        "JSON structure inside a code block:\n"
        "{\"submerged_buildings_estimate\": <int>, \"damaged_roads_estimate\": <int>, "
        "\"crop_damage_hectares\": <float>, \"bridge_damage\": \"none|partial|severe\", "
        "\"economic_loss_lakh_inr\": <int>, \"summary\": \"<2-line summary>\"}\n"
        f"Context provided by user: {payload.context or 'none'}"
    )
    try:
        raw = await ai_service.analyze_image(prompt, payload.image_base64)
    except Exception as e:
        logging.exception("Damage estimate failed")
        raise HTTPException(500, f"AI vision failed: {e}")
    return {"raw": raw}


@api_router.post("/water-depth/estimate")
async def water_depth_estimate(payload: ImagePayload):
    prompt = (
        "You are a computer-vision flood water-depth estimator. Given this photograph, "
        "estimate visible water depth using reference objects (person, car tyre, door, "
        "bike wheel). Reply in JSON only:\n"
        "{\"depth_cm\": <int>, \"confidence\": \"low|medium|high\", "
        "\"reference_used\": \"<object>\", \"advice\": \"<one line>\"}"
    )
    try:
        raw = await ai_service.analyze_image(prompt, payload.image_base64)
    except Exception as e:
        raise HTTPException(500, f"AI vision failed: {e}")
    return {"raw": raw}


@api_router.post("/image/classify")
async def image_classify(payload: ImagePayload):
    prompt = (
        "Classify this flood-related image. Reply in JSON only:\n"
        "{\"tags\": [\"road_blocked\"|\"bridge_collapse\"|\"fallen_tree\"|"
        "\"stranded_people\"|\"submerged_vehicle\"|\"waterlogged_street\"|"
        "\"rescue_boat\"|\"clear\"], \"severity\": \"low|medium|high|critical\", "
        "\"one_line\": \"<description>\"}"
    )
    try:
        raw = await ai_service.analyze_image(prompt, payload.image_base64)
    except Exception as e:
        raise HTTPException(500, f"AI vision failed: {e}")
    return {"raw": raw}


# ---------- Fake news / rumor ----------
@api_router.post("/fakenews/check")
async def fakenews_check(payload: FakeNewsPayload):
    prompt = (
        "You are the AI Rumor-Verification module for the national flood platform. "
        f"Text to verify: \"{payload.text}\"\n"
        f"Source: {payload.source or 'unknown'}\n\n"
        "Reply STRICTLY in JSON:\n"
        "{\"verdict\": \"verified|likely_false|unverified|needs_review\", "
        "\"confidence\": <0-100>, \"reasons\": [\"<r1>\", \"<r2>\", \"<r3>\"], "
        "\"official_check\": \"<what to check on PIB / IMD / NDMA>\"}"
    )
    try:
        raw = await ai_service.generate_text(prompt)
    except Exception as e:
        raise HTTPException(500, f"AI failed: {e}")
    return {"raw": raw}


# ---------- Chatbot (streaming SSE) ----------
@api_router.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    async def gen():
        try:
            async for token in ai_service.stream_chat(req.session_id, req.message):
                yield f"data: {json.dumps({'delta': token})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@api_router.post("/chat/message")
async def chat_message(req: ChatRequest):
    """Non-streaming fallback (for testing / lower bandwidth)."""
    try:
        text = await ai_service.generate_text(req.message)
    except Exception as e:
        raise HTTPException(500, f"AI failed: {e}")
    return {"response": text, "session_id": req.session_id}


# ---------- Incidents / SOS / Prioritization ----------
@api_router.get("/incidents")
async def get_incidents():
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    sorted_inc = sorted(INCIDENTS, key=lambda x: order.get(x["priority"], 9))
    return {"incidents": sorted_inc}


@api_router.post("/incidents/sos")
async def create_sos(sos: SOSRequest):
    doc = {
        "id": str(uuid.uuid4()),
        "type": "SOS",
        "priority": "critical",
        "created_at": datetime.now(timezone.utc).isoformat(),
        **sos.model_dump(),
    }
    await db.sos_reports.insert_one({**doc})
    return {"ok": True, "ticket_id": doc["id"], "eta_min": 25}


@api_router.get("/incidents/sos")
async def list_sos():
    docs = await db.sos_reports.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return {"items": docs}


# ---------- Volunteers ----------
@api_router.get("/volunteers")
async def get_volunteers():
    seeded = list(VOLUNTEERS)
    dyn = await db.volunteers.find({}, {"_id": 0}).to_list(200)
    return {"volunteers": seeded + dyn}


@api_router.post("/volunteers")
async def register_volunteer(v: VolunteerRegister):
    doc = {"id": str(uuid.uuid4()), "available": True, "assigned_to": None, **v.model_dump()}
    await db.volunteers.insert_one({**doc})
    return {"ok": True, "volunteer": doc}


# ---------- Social monitoring ----------
@api_router.get("/social/monitor")
async def social_monitor():
    return {"posts": SOCIAL_POSTS}


# ---------- Weather / Reservoirs ----------
@api_router.get("/weather")
async def weather():
    return {"weather": WEATHER}


# ---------- Simulation / Digital Twin ----------
@api_router.post("/simulation/flood")
async def simulate_flood(req: SimulationRequest):
    base = PREDICTIONS.get(req.region_id, {"expected_depth_m": 0.5, "affected_villages": 3, "population_at_risk": 5000})
    # Simple linear model based on rainfall
    factor = req.rainfall_mm / 100
    return {
        "rainfall_mm": req.rainfall_mm,
        "region_id": req.region_id,
        "expected_depth_m": round(base["expected_depth_m"] * (0.5 + factor), 2),
        "affected_villages": int(base["affected_villages"] * (0.5 + factor)),
        "population_at_risk": int(base["population_at_risk"] * (0.5 + factor)),
        "spread_km2": round(4.2 * factor, 1),
    }


@api_router.post("/rescue/route")
async def rescue_route(req: RescueRouteRequest):
    dist = _hav(req.from_lat, req.from_lng, req.to_lat, req.to_lng)
    speed = 18 if req.boat else 35  # km/h
    eta_min = int((dist / speed) * 60)
    # generate two intermediate waypoints
    mid1 = {"lat": (req.from_lat * 2 + req.to_lat) / 3, "lng": (req.from_lng * 2 + req.to_lng) / 3 + 0.005}
    mid2 = {"lat": (req.from_lat + req.to_lat * 2) / 3 - 0.003, "lng": (req.from_lng + req.to_lng * 2) / 3}
    return {
        "distance_km": round(dist, 2),
        "eta_min": eta_min,
        "waypoints": [
            {"lat": req.from_lat, "lng": req.from_lng, "note": "Start"},
            {**mid1, "note": "Avoid submerged NH-27 section"},
            {**mid2, "note": "Cross via reinforced bridge"},
            {"lat": req.to_lat, "lng": req.to_lng, "note": "Destination"},
        ],
        "avoided": ["Flooded road (1.2m depth)", "Damaged culvert", "High-traffic diversion"],
    }


# ---------- Medical outbreak / Economic loss / Preparedness / Contacts ----------
@api_router.get("/medical/outbreak")
async def medical_outbreak():
    return {"predictions": MEDICAL_OUTBREAK}


@api_router.get("/economic-loss")
async def economic_loss():
    return {"loss": ECONOMIC_LOSS}


@api_router.get("/preparedness")
async def preparedness():
    return {"guide": PREPAREDNESS}


@api_router.get("/emergency-contacts")
async def emergency_contacts():
    return {"contacts": EMERGENCY_CONTACTS}


@api_router.get("/drones")
async def drones_list():
    return {"drones": DRONES}


@api_router.get("/family-registry")
async def family_registry():
    seeded = list(FAMILY_REGISTRY)
    dyn = await db.family_checkins.find({}, {"_id": 0}).to_list(200)
    return {"registry": seeded + dyn}


@api_router.post("/family-registry")
async def family_add(entry: FamilyCheckIn):
    doc = {"id": str(uuid.uuid4()), **entry.model_dump()}
    await db.family_checkins.insert_one({**doc})
    return {"ok": True, "entry": doc}


# ---------- Early warning generator ----------
@api_router.post("/warning/generate")
async def warning_generate(req: ExplainRequest):
    p = PREDICTIONS.get(req.region_id)
    r = next((x for x in REGIONS if x["id"] == req.region_id), None)
    if not p or not r:
        raise HTTPException(404, "Region not found")
    prompt = (
        f"Draft an official early-warning message (max 60 words) in Hindi and English "
        f"for {r['name']} residents. Flood probability {p['probability']}%, expected "
        f"water depth {p['expected_depth_m']}m in {p['time_remaining_hr']} hours. "
        f"Include the nearest shelter action and helpline 1078. "
        "Return JSON: {\"hindi\": \"...\", \"english\": \"...\"}"
    )
    try:
        raw = await ai_service.generate_text(prompt)
    except Exception:
        raw = json.dumps({
            "hindi": f"चेतावनी: {r['name']} में {p['time_remaining_hr']} घंटे में {p['expected_depth_m']}m बाढ़ की {p['probability']}% संभावना। कृपया निकटतम आश्रय स्थल जाएँ। हेल्पलाइन 1078.",
            "english": f"WARNING: {r['name']} — {p['probability']}% flood probability, {p['expected_depth_m']}m water depth expected within {p['time_remaining_hr']} hours. Move to nearest shelter. Helpline 1078.",
        })
    return {"raw": raw}


# ---------- Mount ----------
app.include_router(api_router)

# ---------- SETU spec-compliant subsystem (Sections 4-23) ----------
from setu.routers import (admin_routes, authority_routes, auth_routes, event_routes,
                          governance_routes, ingestion_routes, integrity_routes, offline_routes,
                          relief_routes, rescue_routes, search_routes, shelter_routes,
                          sos_routes)  # noqa: E402
from setu import seed as setu_seed  # noqa: E402

app.include_router(auth_routes.router)
app.include_router(event_routes.router)
app.include_router(sos_routes.router)
app.include_router(rescue_routes.router)
app.include_router(search_routes.router)
app.include_router(shelter_routes.router)
app.include_router(relief_routes.router)
app.include_router(integrity_routes.router)
app.include_router(ingestion_routes.router)
app.include_router(authority_routes.router)
app.include_router(offline_routes.router)
app.include_router(governance_routes.router)
app.include_router(admin_routes.router)


@app.on_event("startup")
async def setu_startup():
    try:
        result = await setu_seed.seed(reset=False)
        logging.getLogger("setu").info("SETU seed ready: %s", result)
    except Exception as exc:  # never block startup on seed issues
        logging.getLogger("setu").error("SETU seed failed: %s", exc)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
