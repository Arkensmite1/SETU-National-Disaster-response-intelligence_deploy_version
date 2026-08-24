"""Phase 13 \u2014 Section 20 scenario tests.

25 end-to-end scenarios run against the live backend. Each test asserts the
SPECIFIED behaviour, not just a 200 response.

Run:  cd /app && python -m pytest tests/test_scenarios.py -q
"""
import uuid

import pytest
import requests

B = "http://localhost:8001/api"
PW = "Setu@1234"


def hdr(t):
    return {"Authorization": f"Bearer {t}"}


def staff(email):
    r = requests.post(f"{B}/auth/login", json={"email": email, "password": PW})
    r.raise_for_status()
    return r.json()["token"]


def citizen(mobile):
    o = requests.post(f"{B}/auth/otp/request", json={"mobile": mobile}).json()
    return requests.post(f"{B}/auth/otp/verify",
                         json={"mobile": mobile, "code": o["devOtp"],
                               "name": f"Test {mobile[-4:]}"}).json()["token"]


def new_citizen():
    return citizen(f"9{uuid.uuid4().int % 10**9:09d}")


@pytest.fixture(scope="module")
def actors():
    a = {
        "leader": staff("leader@setu.gov.in"),
        "member": staff("member@setu.gov.in"),
        "authority": staff("authority@setu.gov.in"),
        "shelter": staff("shelter@setu.gov.in"),
        "ngo": staff("ngo@setu.gov.in"),
    }
    # Release any team left engaged by an earlier run so scenarios are re-runnable.
    teams = requests.get(f"{B}/rescue/teams", headers=hdr(a["leader"])).json()["teams"]
    for t in teams:
        if t["status"] != "AVAILABLE":
            for fld, val in (("status", "AVAILABLE"), ("activeSosId", None)):
                requests.post(f"{B}/admin/override", headers=hdr(a["authority"]), json={
                    "objectType": "TEAM", "objectId": t["teamId"], "field": fld,
                    "newValue": val, "reason": "Scenario test environment reset"})
    return a


def raise_sos(token, lat=27.48, lng=94.58, **kw):
    body = {"location": {"latitude": lat, "longitude": lng, "accuracy": 12, "source": "GPS"},
            "emergencyType": "TRAPPED", "peopleCount": 2, **kw}
    r = requests.post(f"{B}/sos", headers=hdr(token), json=body)
    assert r.status_code == 200, r.text
    return r.json()


def free_team(actors):
    teams = requests.get(f"{B}/rescue/teams", headers=hdr(actors["leader"])).json()["teams"]
    for t in teams:
        if t["status"] == "AVAILABLE":
            return t["teamId"]
    pytest.skip("no team available in this environment run")


# ---------------------------------------------------------------- 1-5
def test_01_sos_created_offline_keeps_original_time(actors):
    ct = new_citizen()
    r = requests.post(f"{B}/sos/sync", headers=hdr(ct), json={"items": [{
        "location": {"latitude": 27.47, "longitude": 94.57, "accuracy": 900, "source": "LAST_KNOWN"},
        "emergencyType": "STRANDED", "peopleCount": 4,
        "clientCreatedAt": "2026-07-01T04:30:00Z", "clientRef": f"cr-{uuid.uuid4().hex[:6]}",
        "networkStatus": "OFFLINE"}]})
    data = r.json()
    assert data["synced"] == 1, data
    sos = data["results"][0]["sos"]
    assert sos["clientCreatedAt"].startswith("2026-07-01T04:30"), sos["clientCreatedAt"]
    assert sos["uploadedAt"] and sos["status"] == "PENDING"


def test_02_duplicate_press_updates_existing_case(actors):
    ct = new_citizen()
    first = raise_sos(ct, 27.481, 94.581)
    second = raise_sos(ct, 27.481, 94.581)
    assert second["sosId"] == first["sosId"]
    assert second["duplicateOfExisting"] is True and second["retryCount"] >= 1


def test_03_gps_unavailable_is_not_user_unavailable(actors):
    ct = new_citizen()
    sos = requests.post(f"{B}/sos", headers=hdr(ct), json={
        "location": {"latitude": 27.49, "longitude": 94.59, "accuracy": None, "source": "LANDMARK",
                     "landmark": "Behind the blue water tank"},
        "emergencyType": "TRAPPED", "peopleCount": 1}).json()
    assert sos["status"] == "PENDING"
    assert sos["locationQuality"]["approximate"] is True
    assert "Approximate" in sos["locationQuality"]["label"]


def test_04_acknowledgement_is_not_a_dispatched_team(actors):
    ct = new_citizen()
    sos = raise_sos(ct, 27.4805, 94.5805)
    assert sos["acknowledged"] is True
    assert sos["rescueTeamNotified"] is False
    assert "NOT been assigned" in sos["message"] or "not been assigned" in sos["message"].lower()


def test_05_team_rejection_returns_case_to_queue(actors):
    ct = new_citizen()
    sos = raise_sos(ct, 27.4712, 94.5712)
    team = free_team(actors)
    requests.post(f"{B}/sos/{sos['sosId']}/assign", headers=hdr(actors["leader"]),
                  json={"teamId": team})
    r = requests.post(f"{B}/sos/{sos['sosId']}/reject", headers=hdr(actors["leader"]),
                      json={"reason": "ROUTE_INACCESSIBLE"})
    assert r.status_code == 200 and r.json()["status"] == "PENDING"
    assert r.json()["assignedTeamId"] is None
    t = requests.get(f"{B}/rescue/teams", headers=hdr(actors["leader"])).json()["teams"]
    assert next(x for x in t if x["teamId"] == team)["status"] == "AVAILABLE"


# ---------------------------------------------------------------- 6-10
def test_06_two_leaders_cannot_claim_the_same_team(actors):
    ct = new_citizen()
    a = raise_sos(ct, 27.4722, 94.5722)
    b = raise_sos(new_citizen(), 27.4922, 94.5922)
    team = free_team(actors)
    r1 = requests.post(f"{B}/sos/{a['sosId']}/assign", headers=hdr(actors["leader"]),
                       json={"teamId": team})
    r2 = requests.post(f"{B}/sos/{b['sosId']}/assign", headers=hdr(actors["leader"]),
                       json={"teamId": team})
    assert r1.status_code == 200 and r2.status_code == 409
    assert "no longer AVAILABLE" in r2.json()["detail"]
    requests.post(f"{B}/sos/{a['sosId']}/reject", headers=hdr(actors["leader"]),
                  json={"reason": "OTHER"})


def test_07_illegal_state_jump_is_rejected(actors):
    ct = new_citizen()
    sos = raise_sos(ct, 27.4733, 94.5733)
    team = free_team(actors)
    requests.post(f"{B}/sos/{sos['sosId']}/assign", headers=hdr(actors["leader"]),
                  json={"teamId": team})
    r = requests.post(f"{B}/sos/{sos['sosId']}/status", headers=hdr(actors["leader"]),
                      json={"status": "RESCUED"})
    assert r.status_code == 409 and "Illegal SOS transition" in r.json()["detail"]
    requests.post(f"{B}/sos/{sos['sosId']}/reject", headers=hdr(actors["leader"]),
                  json={"reason": "OTHER"})


def test_08_not_found_opens_a_search_and_never_says_safe(actors):
    ct = new_citizen()
    sos = raise_sos(ct, 27.4744, 94.5744)
    team = free_team(actors)
    requests.post(f"{B}/sos/{sos['sosId']}/assign", headers=hdr(actors["leader"]), json={"teamId": team})
    requests.post(f"{B}/sos/{sos['sosId']}/accept", headers=hdr(actors["leader"]))
    for st in ("EN_ROUTE", "ARRIVED"):
        requests.post(f"{B}/sos/{sos['sosId']}/status", headers=hdr(actors["leader"]), json={"status": st})
    r = requests.post(f"{B}/sos/{sos['sosId']}/status", headers=hdr(actors["leader"]),
                      json={"status": "USER_NOT_FOUND"}).json()
    assert r["searchOperation"] and r["searchOperation"]["coverage"]["totalCells"] > 1
    assert "never" in r["nextAction"] and "safe" in r["nextAction"]
    close = requests.post(f"{B}/search/operations/{r['searchOperation']['searchId']}/close",
                          headers=hdr(actors["leader"]),
                          json={"outcome": "NOT_FOUND", "peopleMissing": 1}).json()
    assert close["missingRegisterEntry"]["status"] == "OPEN"
    assert "NOT a confirmation of safety" in close["missingRegisterEntry"]["note"]


def test_09_false_sos_is_recorded_not_deleted(actors):
    ct = new_citizen()
    sos = raise_sos(ct, 27.4755, 94.5755)
    team = free_team(actors)
    requests.post(f"{B}/sos/{sos['sosId']}/assign", headers=hdr(actors["leader"]), json={"teamId": team})
    requests.post(f"{B}/sos/{sos['sosId']}/accept", headers=hdr(actors["leader"]))
    requests.post(f"{B}/sos/{sos['sosId']}/status", headers=hdr(actors["leader"]), json={"status": "EN_ROUTE"})
    requests.post(f"{B}/sos/{sos['sosId']}/status", headers=hdr(actors["leader"]), json={"status": "ARRIVED"})
    r = requests.post(f"{B}/sos/{sos['sosId']}/status", headers=hdr(actors["leader"]),
                      json={"status": "FALSE_ALARM"}).json()
    assert r["status"] == "FALSE_ALARM" and "never deleted" in r["note"]
    assert requests.get(f"{B}/sos/{sos['sosId']}", headers=hdr(ct)).status_code == 200


def test_10_citizen_cancellation_keeps_the_audit_trail(actors):
    ct = new_citizen()
    sos = raise_sos(ct, 27.4766, 94.5766)
    r = requests.post(f"{B}/sos/{sos['sosId']}/cancel", headers=hdr(ct)).json()
    assert r["status"] == "CANCELLED_BY_USER" and "nothing is deleted" in r["message"]
    tl = requests.get(f"{B}/sos/{sos['sosId']}/timeline", headers=hdr(ct)).json()["timeline"]
    assert len(tl) >= 5


# ---------------------------------------------------------------- 11-15
def test_11_live_location_sharing_stops_when_a_case_closes(actors):
    ct = new_citizen()
    sos = raise_sos(ct, 27.4777, 94.5777)
    team = free_team(actors)
    requests.post(f"{B}/sos/{sos['sosId']}/assign", headers=hdr(actors["leader"]), json={"teamId": team})
    requests.post(f"{B}/sos/{sos['sosId']}/accept", headers=hdr(actors["leader"]))
    for st in ("EN_ROUTE", "ARRIVED", "RESCUING", "RESCUED"):
        requests.post(f"{B}/sos/{sos['sosId']}/status", headers=hdr(actors["leader"]), json={"status": st})
    done = requests.post(f"{B}/sos/{sos['sosId']}/complete", headers=hdr(actors["leader"]),
                         json={"peopleRescued": 2, "victimConfirmation": True}).json()
    assert done["liveLocationSharing"] is False
    late = requests.patch(f"{B}/sos/{sos['sosId']}/location", headers=hdr(ct), json={
        "location": {"latitude": 27.4, "longitude": 94.5, "accuracy": 10, "source": "GPS"}})
    assert late.status_code == 409


def test_12_role_scoping_is_enforced_by_the_api(actors):
    ct = new_citizen()
    other = new_citizen()
    sos = raise_sos(ct, 27.4788, 94.5788)
    assert requests.get(f"{B}/sos/{sos['sosId']}", headers=hdr(other)).status_code == 403
    assert requests.get(f"{B}/sos/queue", headers=hdr(ct)).status_code == 403
    assert requests.get(f"{B}/sos/queue").status_code == 401
    assert requests.get(f"{B}/authority/decision-log", headers=hdr(actors["leader"])).status_code == 403


def test_13_shelter_last_place_cannot_be_double_allocated(actors):
    sid = "SH-S3"
    requests.post(f"{B}/shelters/{sid}/status", headers=hdr(actors["authority"]), json={"status": "OPEN"})
    r = requests.post(f"{B}/shelters/{sid}/arrivals", headers=hdr(actors["authority"]), json={"count": 50})
    assert r.status_code == 409
    assert r.json()["detail"]["alternatives"], r.text
    assert "No partial update" in r.json()["detail"]["message"]


def test_14_conflicting_occupancy_is_not_overwritten(actors):
    r = requests.post(f"{B}/shelters/SH-S1/arrivals", headers=hdr(actors["shelter"]),
                      json={"count": 1, "expectedOccupancy": 1})
    assert r.status_code == 409 and r.json()["detail"]["conflictRecorded"] is True
    conflicts = requests.get(f"{B}/integrity/conflicts", headers=hdr(actors["authority"])).json()
    assert conflicts["totalOpen"] >= 1


def test_15_shelter_availability_is_always_derived(actors):
    rows = requests.get(f"{B}/shelters/list", headers=hdr(actors["shelter"])).json()["shelters"]
    for s in rows:
        assert s["available"] == max(s["capacity"] - s["occupancy"], 0)
        assert "stalenessNotice" in s


# ---------------------------------------------------------------- 16-20
def test_16_relief_quantities_never_overwrite_each_other(actors):
    req = requests.post(f"{B}/shelters/SH-S1/requirements", headers=hdr(actors["shelter"]),
                        json={"category": "FOOD", "unit": "packets", "requestedQuantity": 400}).json()
    rid = req["requestId"]
    requests.post(f"{B}/relief/requests/{rid}/approve", headers=hdr(actors["authority"]),
                  json={"approvedQuantity": 300})
    requests.post(f"{B}/relief/requests/{rid}/commit", headers=hdr(actors["ngo"]),
                  json={"allocatedQuantity": 300})
    d = requests.post(f"{B}/relief/requests/{rid}/dispatch", headers=hdr(actors["ngo"]),
                      json={"sentQuantity": 280}).json()
    q = d["quantities"]
    assert (q["requested"], q["approved"], q["allocated"], q["sent"], q["received"]) == (400, 300, 300, 280, 0)


def test_17_sent_received_mismatch_becomes_a_discrepancy(actors):
    req = requests.post(f"{B}/shelters/SH-S1/requirements", headers=hdr(actors["shelter"]),
                        json={"category": "BLANKETS", "unit": "pieces", "requestedQuantity": 100}).json()
    rid = req["requestId"]
    requests.post(f"{B}/relief/requests/{rid}/approve", headers=hdr(actors["authority"]),
                  json={"approvedQuantity": 100})
    requests.post(f"{B}/relief/requests/{rid}/commit", headers=hdr(actors["ngo"]),
                  json={"allocatedQuantity": 100})
    requests.post(f"{B}/relief/requests/{rid}/dispatch", headers=hdr(actors["ngo"]),
                  json={"sentQuantity": 100})
    requests.post(f"{B}/relief/requests/{rid}/in-transit", headers=hdr(actors["ngo"]))
    requests.post(f"{B}/relief/requests/{rid}/deliver", headers=hdr(actors["ngo"]))
    r = requests.post(f"{B}/relief/requests/{rid}/receive", headers=hdr(actors["shelter"]),
                      json={"receivedQuantity": 80}).json()
    assert r["status"] == "DISCREPANCY" and r["quantityMismatch"]["difference"] == 20
    assert requests.post(f"{B}/relief/requests/{rid}/resolve-discrepancy",
                         headers=hdr(actors["shelter"]),
                         json={"finalQuantity": 80, "resolution": "x"}).status_code == 403
    fixed = requests.post(f"{B}/relief/requests/{rid}/resolve-discrepancy",
                          headers=hdr(actors["authority"]),
                          json={"finalQuantity": 80, "resolution": "20 damaged"}).json()
    assert fixed["quantities"]["sent"] == 100 and fixed["quantities"]["received"] == 80


def test_18_delivery_delay_must_carry_reason_and_new_eta(actors):
    req = requests.post(f"{B}/shelters/SH-S1/requirements", headers=hdr(actors["shelter"]),
                        json={"category": "MEDICINE", "unit": "kits", "requestedQuantity": 50}).json()
    rid = req["requestId"]
    requests.post(f"{B}/relief/requests/{rid}/approve", headers=hdr(actors["authority"]),
                  json={"approvedQuantity": 50})
    requests.post(f"{B}/relief/requests/{rid}/commit", headers=hdr(actors["ngo"]),
                  json={"allocatedQuantity": 50})
    requests.post(f"{B}/relief/requests/{rid}/dispatch", headers=hdr(actors["ngo"]),
                  json={"sentQuantity": 50})
    r = requests.post(f"{B}/relief/requests/{rid}/delay", headers=hdr(actors["ngo"]),
                      json={"reason": "Bridge closed", "newEta": "2026-07-03T08:00:00Z"}).json()
    assert r["status"] == "DELAYED" and r["delayReason"] == "Bridge closed" and r["shelterNotified"]


def test_19_duplicate_commitment_is_surfaced(actors):
    board = requests.get(f"{B}/relief/requirements", headers=hdr(actors["ngo"])).json()["requirements"]
    assert board, "expected open requirements"
    assert all("committedByOthers" in r and "remainingNeed" in r for r in board)


def test_20_forecast_tier_never_triggers_rescue(actors):
    events = requests.get(f"{B}/events").json()["events"]
    forecasts = [e for e in events if e["infoTier"] == "FORECAST"]
    assert forecasts, "seed should include a forecast-tier event"
    assert all(e["rescueWorkflowsEnabled"] is False for e in forecasts)
    assert any(e.get("experimental") for e in events)


# ---------------------------------------------------------------- 21-25
def test_21_no_matching_event_is_not_reported_as_safe(actors):
    r = requests.post(f"{B}/events/check-location", json={
        "location": {"latitude": 12.9716, "longitude": 77.5946, "accuracy": 10, "source": "GPS"}}).json()
    assert all(m["classification"] != "AFFECTED" for m in r["matches"])
    assert "never an all-clear" in r["safetyNote"]
    assert all("not a confirmation of safety" in m["message"] for m in r["matches"]
               if m["classification"] == "OUTSIDE_KNOWN_AREA")


NEXT_EVENT_STATE = {"DETECTED": "MONITORING", "MONITORING": "WARNING", "WARNING": "CONFIRMED",
                    "CONFIRMED": "ACTIVE", "ACTIVE": "RESPONSE", "RESPONSE": "RELIEF",
                    "RELIEF": "RECOVERY", "RECOVERY": "CLOSED"}


def test_22_closing_an_event_does_not_touch_child_records(actors):
    ct = new_citizen()
    sos = raise_sos(ct, 27.4799, 94.5799)
    before = requests.get(f"{B}/sos/{sos['sosId']}", headers=hdr(ct)).json()["status"]
    ev = sos["eventId"]
    if not ev:
        # The SOS was accepted with no matching active event (rule #1: no event never
        # blocks an SOS). Advance any advanceable event instead.
        candidates = [e for e in requests.get(f"{B}/events").json()["events"]
                      if NEXT_EVENT_STATE.get(e["status"])]
        if not candidates:
            pytest.skip("no advanceable event in this environment run")
        ev = candidates[0]["eventId"]
    current = requests.get(f"{B}/events/{ev}").json()["status"]
    target = NEXT_EVENT_STATE.get(current)
    if not target:
        pytest.skip(f"event {ev} is in terminal state {current}")
    r = requests.post(f"{B}/events/{ev}/transition", headers=hdr(actors["authority"]),
                      json={"status": target})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["childrenUntouched"] is True
    if sos["eventId"] == ev:
        assert body["openChildSosCount"] >= 1
    assert requests.get(f"{B}/sos/{sos['sosId']}", headers=hdr(ct)).json()["status"] == before


def test_23_source_contradiction_is_held_not_applied(actors):
    at = actors["authority"]
    requests.post(f"{B}/ingestion/simulate", headers=hdr(at), json={"mode": "NEW_EVENT"})
    created = requests.post(f"{B}/ingestion/poll", headers=hdr(at)).json()["created"]
    assert created
    eid = created[0]
    before = requests.get(f"{B}/events/{eid}").json()
    requests.post(f"{B}/ingestion/simulate", headers=hdr(at),
                  json={"mode": "CONTRADICTORY_UPDATE", "eventId": eid})
    poll = requests.post(f"{B}/ingestion/poll", headers=hdr(at)).json()
    assert len(poll["conflicts"]) == 1
    after = requests.get(f"{B}/events/{eid}").json()
    assert after["severity"] == before["severity"], "contradictory value must not be applied"


def test_24_unacknowledged_p1_escalates_and_ai_stays_advisory(actors):
    at = actors["authority"]
    nd = requests.post(f"{B}/notifications/dispatch", headers=hdr(at), json={
        "priority": 1, "roles": ["RESCUE_LEADER"], "headline": "Scenario test alert.",
        "locationScoped": False}).json()
    assert nd["created"] >= 1
    mine = requests.get(f"{B}/notifications/mine", headers=hdr(actors["leader"])).json()
    assert mine["notifications"][0]["priority"] == 1
    assert any("command queue" in n["message"] for n in mine["notifications"])
    rec = requests.get(f"{B}/rescue/clusters", headers=hdr(actors["leader"])).json()
    assert rec["advisory"] is True and rec["autoApplied"] is False
    reg = requests.get(f"{B}/governance/advisory-registry").json()
    assert "Tell a citizen they are safe" in reg["neverPermitted"]


def test_25_offline_bundle_sms_fallback_and_compliance(actors):
    ct = new_citizen()
    bundle = requests.get(f"{B}/offline/bundle?lat=27.48&lng=94.58", headers=hdr(ct)).json()
    assert bundle["shelters"] and bundle["helplines"] and "never an all-clear" in bundle["validityNote"]
    sms = requests.post(f"{B}/offline/sms-fallback", headers=hdr(ct), json={
        "text": "SETU SOS 27.4801 94.5801 3 TRAPPED near school"}).json()
    assert sms["status"] == "PENDING" and sms["locationQuality"]["approximate"] is True
    late = requests.post(f"{B}/offline/sync", headers=hdr(ct), json={"items": [{
        "kind": "FIELD_REPORT", "clientRef": f"fr-{uuid.uuid4().hex[:6]}",
        "clientCreatedAt": "2026-07-01T05:00:00Z",
        "payload": {"objectType": "AREA", "objectId": "assam-dhemaji", "field": "waterLevel",
                    "value": "chest deep"}}]}).json()
    assert late["applied"] == 1
    report = requests.get(f"{B}/governance/compliance-report", headers=hdr(actors["authority"])).json()
    assert report["failed"] == 0, report["checks"]
