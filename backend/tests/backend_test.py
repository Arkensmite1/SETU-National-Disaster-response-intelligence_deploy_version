"""Backend API tests for Setu Disaster Response Platform."""
import os
import base64
import io
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback: read frontend .env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

API = f"{BASE_URL}/api"
AI_TIMEOUT = 90


# ----------------- Fixtures -----------------
@pytest.fixture(scope="session")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def real_image_b64():
    """Create a real JPEG with visual features (gradient + shapes)."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (320, 240), color=(70, 130, 180))
    d = ImageDraw.Draw(img)
    # Add features
    for i in range(0, 240, 20):
        d.line([(0, i), (320, i)], fill=(90 + i % 100, 80, 60), width=2)
    d.rectangle([50, 80, 200, 200], fill=(139, 69, 19), outline=(0, 0, 0), width=3)
    d.ellipse([220, 60, 300, 140], fill=(255, 255, 255), outline=(0, 0, 0), width=2)
    d.polygon([(30, 220), (100, 150), (170, 220)], fill=(34, 139, 34))
    d.text((10, 10), "FLOOD SCENE", fill=(255, 255, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


# ----------------- Basic endpoints -----------------
class TestBasic:
    def test_root(self, client):
        r = client.get(f"{API}/")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "operational"
        assert d["platform"] == "Setu"

    def test_overview_stats(self, client):
        r = client.get(f"{API}/overview/stats")
        assert r.status_code == 200
        s = r.json()["stats"]
        for k in ["people_evacuated", "shelters_active", "rescue_teams_deployed",
                  "villages_affected", "boats_operational", "helicopters_operational",
                  "predictions_generated", "alerts_broadcast"]:
            assert k in s, f"Missing key: {k}"

    def test_alerts_ticker(self, client):
        r = client.get(f"{API}/alerts/ticker")
        assert r.status_code == 200
        alerts = r.json()["alerts"]
        assert isinstance(alerts, list) and len(alerts) > 0
        assert "level" in alerts[0] and "text" in alerts[0]

    def test_regions(self, client):
        r = client.get(f"{API}/regions")
        assert r.status_code == 200
        regs = r.json()["regions"]
        assert len(regs) > 0
        assert all("lat" in x and "lng" in x and "river" in x and "population" in x for x in regs)

    def test_map_data(self, client):
        r = client.get(f"{API}/monitoring/map-data")
        assert r.status_code == 200
        d = r.json()
        for k in ["villages", "shelters", "road_closures", "reservoirs"]:
            assert k in d and isinstance(d[k], list)


# ----------------- Predictions -----------------
class TestPredictions:
    def test_prediction_region(self, client):
        r = client.get(f"{API}/prediction/assam-dhemaji")
        assert r.status_code == 200
        d = r.json()
        p = d["prediction"]
        for k in ["probability", "expected_depth_m", "time_remaining_hr",
                  "population_at_risk", "affected_villages"]:
            assert k in p
        assert isinstance(d["factors"], list)
        assert "name" in d["region"]

    def test_predictions_all(self, client):
        r = client.get(f"{API}/predictions/all")
        assert r.status_code == 200
        assert isinstance(r.json()["items"], list)

    def test_prediction_explain_ai(self, client):
        r = client.post(f"{API}/prediction/explain",
                        json={"region_id": "assam-dhemaji"}, timeout=AI_TIMEOUT)
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d.get("explanation"), str) and len(d["explanation"]) > 30

    def test_warning_generate_ai(self, client):
        r = client.post(f"{API}/warning/generate",
                        json={"region_id": "assam-dhemaji"}, timeout=AI_TIMEOUT)
        assert r.status_code == 200
        raw = r.json()["raw"]
        assert isinstance(raw, str) and len(raw) > 10


# ----------------- Resources -----------------
class TestResources:
    def test_resources_list(self, client):
        r = client.get(f"{API}/resources")
        assert r.status_code == 200
        d = r.json()
        assert "inventory" in d and "allocations" in d

    def test_resources_optimize_ai(self, client):
        r = client.post(f"{API}/resources/optimize", json={}, timeout=AI_TIMEOUT)
        assert r.status_code == 200
        assert isinstance(r.json().get("suggestion"), str)


# ----------------- Shelter / Rescue / Simulation -----------------
class TestOps:
    def test_shelter_recommend(self, client):
        r = client.post(f"{API}/shelter/recommend",
                        json={"lat": 28.5355, "lng": 77.3910, "needs_medical": False})
        assert r.status_code == 200
        recs = r.json()["recommendations"]
        assert len(recs) == 5
        # ranked by score desc
        scores = [x["score"] for x in recs]
        assert scores == sorted(scores, reverse=True)

    def test_rescue_route(self, client):
        r = client.post(f"{API}/rescue/route",
                        json={"from_lat": 27.5, "from_lng": 94.0,
                              "to_lat": 27.6, "to_lng": 94.1, "boat": True})
        assert r.status_code == 200
        d = r.json()
        assert d["distance_km"] > 0
        assert d["eta_min"] >= 0
        assert len(d["waypoints"]) >= 2
        assert isinstance(d["avoided"], list)

    def test_simulation_flood(self, client):
        r = client.post(f"{API}/simulation/flood",
                        json={"rainfall_mm": 200, "region_id": "assam-dhemaji"})
        assert r.status_code == 200
        d = r.json()
        for k in ["expected_depth_m", "affected_villages", "population_at_risk", "spread_km2"]:
            assert k in d


# ----------------- Incidents & SOS -----------------
class TestIncidents:
    def test_incidents_sorted(self, client):
        r = client.get(f"{API}/incidents")
        assert r.status_code == 200
        inc = r.json()["incidents"]
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        priorities = [order.get(x["priority"], 9) for x in inc]
        assert priorities == sorted(priorities)

    def test_sos_create_and_list(self, client):
        payload = {"name": "TEST_User", "phone": "9999999999",
                   "location": "TEST loc", "situation": "trapped",
                   "people_count": 3}
        r = client.post(f"{API}/incidents/sos", json=payload)
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] and "ticket_id" in d and "eta_min" in d
        # Verify persisted
        r2 = client.get(f"{API}/incidents/sos")
        assert r2.status_code == 200
        items = r2.json()["items"]
        assert any(x.get("name") == "TEST_User" for x in items)


# ----------------- Volunteers -----------------
class TestVolunteers:
    def test_get_volunteers(self, client):
        r = client.get(f"{API}/volunteers")
        assert r.status_code == 200
        assert isinstance(r.json()["volunteers"], list)

    def test_register_volunteer(self, client):
        r = client.post(f"{API}/volunteers",
                        json={"name": "TEST_Vol", "phone": "8888888888",
                              "skill": "medic", "location": "Delhi"})
        assert r.status_code == 200
        assert r.json()["ok"]
        # verify listed
        r2 = client.get(f"{API}/volunteers")
        assert any(v.get("name") == "TEST_Vol" for v in r2.json()["volunteers"])


# ----------------- Simple info endpoints -----------------
class TestInfo:
    @pytest.mark.parametrize("path,key", [
        ("/social/monitor", "posts"),
        ("/weather", "weather"),
        ("/medical/outbreak", "predictions"),
        ("/economic-loss", "loss"),
        ("/preparedness", "guide"),
        ("/emergency-contacts", "contacts"),
        ("/drones", "drones"),
        ("/family-registry", "registry"),
    ])
    def test_info_endpoints(self, client, path, key):
        r = client.get(f"{API}{path}")
        assert r.status_code == 200, f"{path} -> {r.status_code}"
        assert key in r.json()


# ----------------- AI Vision endpoints -----------------
class TestAIVision:
    def test_damage_estimate(self, client, real_image_b64):
        r = client.post(f"{API}/damage/estimate",
                        json={"image_base64": real_image_b64, "context": "flooded village"},
                        timeout=AI_TIMEOUT)
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:400]}"
        raw = r.json()["raw"]
        assert isinstance(raw, str) and len(raw) > 20

    def test_water_depth(self, client, real_image_b64):
        r = client.post(f"{API}/water-depth/estimate",
                        json={"image_base64": real_image_b64}, timeout=AI_TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        assert len(r.json()["raw"]) > 10

    def test_image_classify(self, client, real_image_b64):
        r = client.post(f"{API}/image/classify",
                        json={"image_base64": real_image_b64}, timeout=AI_TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        assert len(r.json()["raw"]) > 10


# ----------------- Fake news & Chat -----------------
class TestChatAndFake:
    def test_fakenews(self, client):
        r = client.post(f"{API}/fakenews/check",
                        json={"text": "Assam dam has broken and 1000 dead",
                              "source": "whatsapp forward"}, timeout=AI_TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        assert len(r.json()["raw"]) > 10

    def test_chat_message(self, client):
        r = client.post(f"{API}/chat/message",
                        json={"session_id": "test-session-1",
                              "message": "What is the nearest safe shelter if I am in Noida?"},
                        timeout=AI_TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert isinstance(d.get("response"), str) and len(d["response"]) > 10
