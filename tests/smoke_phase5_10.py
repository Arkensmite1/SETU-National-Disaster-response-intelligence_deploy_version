"""Smoke test: Phases 5-10 (search, shelters, relief, integrity, ingestion, authority)."""
import requests

B = "http://localhost:8001/api"
P = 0
F = 0


def hdr(t):
    return {"Authorization": f"Bearer {t}"}


def check(label, cond, extra=""):
    global P, F
    if cond:
        P += 1
        print("PASS " + label)
    else:
        F += 1
        print("FAIL " + label + " | " + str(extra)[:400])
    return cond


def login(email):
    return requests.post(f"{B}/auth/login", json={"email": email, "password": "Setu@1234"}).json()["token"]


lt = login("leader@setu.gov.in")
mt = login("member@setu.gov.in")
at = login("authority@setu.gov.in")
sh = login("shelter@setu.gov.in")
ng = login("ngo@setu.gov.in")
o = requests.post(f"{B}/auth/otp/request", json={"mobile": "9000000001"}).json()
ct = requests.post(f"{B}/auth/otp/verify", json={"mobile": "9000000001", "code": o["devOtp"]}).json()["token"]

# =========================== PHASE 5: search & verification
sos = requests.post(f"{B}/sos", headers=hdr(ct), json={
    "location": {"latitude": 27.4771, "longitude": 94.5712, "accuracy": 15, "source": "GPS"},
    "emergencyType": "TRAPPED", "peopleCount": 3, "injuredCount": 1}).json()
sid = sos["sosId"]
requests.post(f"{B}/sos/{sid}/assign", headers=hdr(lt), json={"teamId": "TEAM-NDRF01"})
requests.post(f"{B}/sos/{sid}/accept", headers=hdr(mt))
requests.post(f"{B}/sos/{sid}/status", headers=hdr(mt), json={"status": "EN_ROUTE"})
requests.post(f"{B}/sos/{sid}/status", headers=hdr(mt), json={"status": "ARRIVED"})
nf = requests.post(f"{B}/sos/{sid}/status", headers=hdr(mt), json={"status": "USER_NOT_FOUND"}).json()
check("USER_NOT_FOUND auto-opens a search operation", bool(nf.get("searchOperation")), nf)
check("not-found is never reported as safe", "never" in (nf.get("nextAction") or ""), nf.get("nextAction"))
search_id = (nf.get("searchOperation") or {}).get("searchId")
op = requests.get(f"{B}/search/operations/{search_id}", headers=hdr(mt)).json()
check("search grid built with cells", op["coverage"]["totalCells"] > 4, op.get("coverage"))
cell = op["gridCells"][0]["cellId"]
cu = requests.post(f"{B}/search/operations/{search_id}/cells/{cell}", headers=hdr(mt),
                   json={"result": "NOTHING_FOUND"}).json()
check("cell coverage tracked", cu["coverage"]["searchedCells"] == 1, cu.get("coverage"))
cell2 = op["gridCells"][1]["cellId"]
requests.post(f"{B}/search/operations/{search_id}/cells/{cell2}", headers=hdr(mt),
              json={"result": "PEOPLE_FOUND", "peopleFound": 2})
cl = requests.post(f"{B}/search/operations/{search_id}/close", headers=hdr(mt), json={
    "outcome": "NOT_FOUND", "peopleFound": 2, "peopleMissing": 1,
    "observations": "Two rescued, one unaccounted"}).json()
check("closing a not-found search opens a missing-person entry", bool(cl.get("missingRegisterEntry")), cl)
entry = cl["missingRegisterEntry"]["entryId"]
reg = requests.get(f"{B}/search/missing-register", headers=hdr(lt)).json()
check("missing register lists the open entry", any(e["entryId"] == entry for e in reg["entries"]), reg)
res = requests.post(f"{B}/search/missing-register/{entry}/resolve", headers=hdr(lt),
                    json={"resolution": "LOCATED_SAFE", "evidence": "Found at SH-S1 by shelter admin"})
check("register entry resolvable with evidence", res.status_code == 200 and res.json()["status"] == "RESOLVED", res.text)
fi = requests.post(f"{B}/search/incidents", headers=hdr(mt), json={
    "location": {"latitude": 27.46, "longitude": 94.55, "accuracy": 20, "source": "GPS"},
    "unknownPersons": 4, "condition": "STABLE", "transportRequired": True,
    "notes": "Family on rooftop, never sent an SOS"})
check("people found without an SOS are recorded", fi.status_code == 200 and fi.json()["unknownPersons"] == 4, fi.text)
ss = requests.get(f"{B}/search/summary", headers=hdr(lt)).json()
check("search summary counts unknown persons", ss["unknownPersonsRecorded"] >= 4, ss)
check("member cannot resolve register (403)",
      requests.post(f"{B}/search/missing-register/{entry}/resolve", headers=hdr(mt),
                    json={"resolution": "CLOSED_UNRESOLVED", "evidence": "x"}).status_code == 403)

# =========================== PHASE 6: shelters
ls = requests.get(f"{B}/shelters/list?lat=27.48&lng=94.58", headers=hdr(ct)).json()
check("shelter availability is derived", all("available" in s for s in ls["shelters"]), ls["shelters"][:1])
check("shelter records carry data age", all("stalenessNotice" in s for s in ls["shelters"]), ls["shelters"][:1])
occ_before = requests.get(f"{B}/shelters/SH-S1", headers=hdr(sh)).json()["occupancy"]
arr = requests.post(f"{B}/shelters/SH-S1/arrivals", headers=hdr(sh),
                    json={"count": 5, "note": "family group"})
check("arrivals update occupancy",
      arr.status_code == 200 and arr.json()["occupancy"] == occ_before + 5, arr.text)
full = requests.post(f"{B}/shelters/SH-S3/arrivals", headers=hdr(at), json={"count": 3})
check("full shelter rejects intake with alternatives (409)",
      full.status_code == 409 and full.json()["detail"].get("alternatives"), full.text)
over = requests.post(f"{B}/shelters/SH-S3/arrivals", headers=hdr(at),
                     json={"count": 3, "allowOverflow": True})
check("explicit over-capacity intake allowed and flagged",
      over.status_code == 200 and over.json()["status"] == "OVER_CAPACITY", over.text)
conf = requests.post(f"{B}/shelters/SH-S1/arrivals", headers=hdr(sh),
                     json={"count": 2, "expectedOccupancy": 1})
check("concurrent edit rejected, both values retained (409)",
      conf.status_code == 409 and conf.json()["detail"].get("conflictRecorded"), conf.text)
occ_now = requests.get(f"{B}/shelters/SH-S1", headers=hdr(sh)).json()["occupancy"]
dep = requests.post(f"{B}/shelters/SH-S1/departures", headers=hdr(sh), json={"count": 2})
check("departures reduce occupancy",
      dep.status_code == 200 and dep.json()["occupancy"] == occ_now - 2, dep.text)
scope = requests.post(f"{B}/shelters/SH-S4/arrivals", headers=hdr(sh), json={"count": 1})
check("shelter admin scoped to own shelter (403)", scope.status_code == 403, scope.text)
dst_before = requests.get(f"{B}/shelters/SH-S4", headers=hdr(sh)).json()["occupancy"]
src_before = requests.get(f"{B}/shelters/SH-S1", headers=hdr(sh)).json()["occupancy"]
tr = requests.post(f"{B}/shelters/SH-S1/transfer", headers=hdr(sh),
                   json={"toShelterId": "SH-S4", "count": 10, "reason": "Load balancing"})
check("shelter transfer moves both sides atomically",
      tr.status_code == 200 and tr.json()["to"]["occupancy"] == dst_before + 10
      and tr.json()["from"]["occupancy"] == src_before - 10, tr.text)
sync = requests.post(f"{B}/shelters/SH-S1/sync-offline", headers=hdr(sh), json={"entries": [
    {"count": 4, "occurredAt": "2026-07-01T09:00:00Z", "note": "offline log"},
    {"count": 2, "occurredAt": "2026-07-01T09:30:00Z"}]}).json()
check("offline shelter logs replay", sync["applied"] == 2, sync)
cls = requests.post(f"{B}/shelters/SH-S4/status", headers=hdr(at), json={"status": "CLOSED"})
check("closure requires a reason (400)", cls.status_code == 400, cls.text)
cls2 = requests.post(f"{B}/shelters/SH-S4/status", headers=hdr(at),
                     json={"status": "CLOSED", "reason": "Structural damage"})
check("closure with reason returns alternatives",
      cls2.status_code == 200 and cls2.json().get("alternatives") is not None, cls2.text)
requests.post(f"{B}/shelters/SH-S4/status", headers=hdr(at), json={"status": "OPEN"})
req = requests.post(f"{B}/shelters/SH-S1/requirements", headers=hdr(sh),
                    json={"category": "DRINKING_WATER", "unit": "litres", "requestedQuantity": 2000})
check("shelter raises a requirement", req.status_code == 200 and req.json()["status"] == "REQUESTED", req.text)
rid = req.json()["requestId"]

# =========================== PHASE 7: relief
board = requests.get(f"{B}/relief/requirements", headers=hdr(ng)).json()
check("NGO sees requirement board with commitments",
      any(r["requestId"] == rid for r in board["requirements"]), board)
ap = requests.post(f"{B}/relief/requests/{rid}/approve", headers=hdr(at), json={"approvedQuantity": 1500})
check("authority approves (partial approval retains request figure)",
      ap.status_code == 200 and ap.json()["quantities"]["requested"] == 2000
      and ap.json()["quantities"]["approved"] == 1500, ap.text)
check("NGO cannot approve (403)",
      requests.post(f"{B}/relief/requests/{rid}/approve", headers=hdr(ng),
                    json={"approvedQuantity": 10}).status_code in (403, 409))
over_commit = requests.post(f"{B}/relief/requests/{rid}/commit", headers=hdr(ng),
                            json={"allocatedQuantity": 5000})
check("over-commitment needs explicit confirmation (409)", over_commit.status_code == 409, over_commit.text)
cm = requests.post(f"{B}/relief/requests/{rid}/commit", headers=hdr(ng),
                   json={"allocatedQuantity": 1500, "eta": "2026-07-02T10:00:00Z"})
check("NGO commits stock", cm.status_code == 200 and cm.json()["status"] == "ALLOCATED", cm.text)
bad = requests.post(f"{B}/relief/requests/{rid}/receive", headers=hdr(sh), json={"receivedQuantity": 10})
check("cannot receive before dispatch (409)", bad.status_code == 409, bad.text)
dp = requests.post(f"{B}/relief/requests/{rid}/dispatch", headers=hdr(ng), json={"sentQuantity": 1500})
check("dispatch stores sent quantity separately",
      dp.status_code == 200 and dp.json()["quantities"]["sent"] == 1500
      and dp.json()["quantities"]["received"] == 0, dp.text)
requests.post(f"{B}/relief/requests/{rid}/in-transit", headers=hdr(ng))
dl = requests.post(f"{B}/relief/requests/{rid}/delay", headers=hdr(ng),
                   json={"reason": "Road submerged at Silapathar", "newEta": "2026-07-02T18:00:00Z"})
check("delay records reason, new ETA and notifies the shelter",
      dl.status_code == 200 and dl.json()["shelterNotified"], dl.text)
requests.post(f"{B}/relief/requests/{rid}/deliver", headers=hdr(ng))
rc = requests.post(f"{B}/relief/requests/{rid}/receive", headers=hdr(sh), json={"receivedQuantity": 1350})
check("sent != received raises DISCREPANCY, keeps both figures",
      rc.status_code == 200 and rc.json()["status"] == "DISCREPANCY"
      and rc.json()["quantityMismatch"]["difference"] == 150, rc.text)
check("shelter admin cannot resolve its own discrepancy (403)",
      requests.post(f"{B}/relief/requests/{rid}/resolve-discrepancy", headers=hdr(sh),
                    json={"finalQuantity": 1350, "resolution": "x"}).status_code == 403)
rs = requests.post(f"{B}/relief/requests/{rid}/resolve-discrepancy", headers=hdr(at),
                   json={"finalQuantity": 1350, "resolution": "150 litres damaged in transit"})
check("authority resolves discrepancy, originals retained",
      rs.status_code == 200 and rs.json()["discrepancy"]["resolved"]
      and rs.json()["quantities"]["sent"] == 1500, rs.text)
ds = requests.post(f"{B}/relief/requests/{rid}/distribute", headers=hdr(sh), json={})
check("distribution closes the pipeline", ds.status_code == 200 and ds.json()["status"] == "DISTRIBUTED", ds.text)
inv = requests.post(f"{B}/relief/inventory", headers=hdr(ng),
                    json={"category": "DRINKING_WATER", "unit": "litres", "quantity": 8000})
check("NGO inventory recorded", inv.status_code == 200, inv.text)
iv = requests.get(f"{B}/relief/inventory", headers=hdr(ng)).json()
check("inventory separates committed stock", "committed" in iv["inventory"][0], iv)
pl = requests.get(f"{B}/relief/pipeline", headers=hdr(at)).json()
check("pipeline keeps five independent quantities", set(pl["quantities"]) ==
      {"requested", "approved", "allocated", "sent", "received"}, pl)

# =========================== PHASE 8: integrity & conflicts
fr1 = requests.post(f"{B}/integrity/field-reports", headers=hdr(mt), json={
    "objectType": "SHELTER", "objectId": "SH-S1", "field": "occupancy", "value": 600,
    "confidence": "MEDIUM", "note": "Head count at gate"}).json()
fr2 = requests.post(f"{B}/integrity/field-reports", headers=hdr(sh), json={
    "objectType": "SHELTER", "objectId": "SH-S1", "field": "occupancy", "value": 640,
    "confidence": "HIGH", "note": "Register count"}).json()
check("contradictory reports kept side by side", fr2.get("conflict") and
      len(fr2["conflict"]["values"]) >= 2, fr2)
cf = requests.get(f"{B}/integrity/conflicts", headers=hdr(at)).json()
check("conflict board lists open conflicts", cf["totalOpen"] >= 1, cf["totalOpen"])
cid = fr2["conflict"]["conflictId"]
rv = requests.post(f"{B}/integrity/conflicts/{cid}/resolve", headers=hdr(at),
                   json={"chosenValue": 640, "reason": "Register count verified at gate",
                         "applyToRecord": True})
check("human resolves conflict, discarded values retained",
      rv.status_code == 200 and rv.json()["conflict"]["discardedValues"], rv.text)
check("non-admin cannot resolve conflicts (403)",
      requests.post(f"{B}/integrity/conflicts/{cid}/resolve", headers=hdr(mt),
                    json={"chosenValue": 1, "reason": "x"}).status_code == 403)
dq = requests.get(f"{B}/integrity/data-quality", headers=hdr(at)).json()
check("data quality states known unknowns", len(dq["knownUnknowns"]) >= 3, dq)

# =========================== PHASE 9: ingestion + notifications
requests.post(f"{B}/ingestion/simulate", headers=hdr(at), json={"mode": "NEW_EVENT"})
p1 = requests.post(f"{B}/ingestion/poll", headers=hdr(at)).json()
check("new source event ingested", len(p1["created"]) == 1, p1)
new_event = p1["created"][0]
requests.post(f"{B}/ingestion/simulate", headers=hdr(at),
              json={"mode": "UPDATE_SEVERITY", "eventId": new_event})
p2 = requests.post(f"{B}/ingestion/poll", headers=hdr(at)).json()
check("source update applied as a new version", len(p2["updated"]) == 1, p2)
ev = requests.get(f"{B}/events/{new_event}").json()
check("version history retained", ev["version"] >= 2 and len(ev["history"]) >= 1, ev.get("version"))
check("tier promoted to DISASTER_ACTIVE on confirmation", ev["infoTier"] == "DISASTER_ACTIVE", ev["infoTier"])
requests.post(f"{B}/ingestion/simulate", headers=hdr(at),
              json={"mode": "CONTRADICTORY_UPDATE", "eventId": new_event})
p3 = requests.post(f"{B}/ingestion/poll", headers=hdr(at)).json()
check("contradictory source update held as a conflict", len(p3["conflicts"]) == 1, p3)
requests.post(f"{B}/ingestion/simulate", headers=hdr(at),
              json={"mode": "ILLEGAL_JUMP", "eventId": new_event})
p4 = requests.post(f"{B}/ingestion/poll", headers=hdr(at)).json()
check("illegal lifecycle jump from source not applied", len(p4["conflicts"]) == 1, p4)
st = requests.get(f"{B}/ingestion/status", headers=hdr(at)).json()
check("ingestion status exposes source health", st["polls"] >= 4 and st["source"], st)
empty = requests.post(f"{B}/ingestion/poll", headers=hdr(at)).json()
check("empty poll reported as a data gap, not an all-clear",
      "all-clear" in empty["note"], empty["note"])
check("non-admin cannot poll the source (403)",
      requests.post(f"{B}/ingestion/poll", headers=hdr(lt)).status_code == 403)

nd = requests.post(f"{B}/notifications/dispatch", headers=hdr(at), json={
    "priority": 1, "roles": ["USER", "RESCUE_LEADER", "SHELTER_ADMIN"],
    "eventId": "NDEM-EVENT-2026-00011",
    "headline": "Flood escalated in Dhemaji district.", "locationScoped": False}).json()
check("notification fan-out created per user", nd["created"] >= 3, nd)
mine = requests.get(f"{B}/notifications/mine", headers=hdr(lt)).json()
check("leader receives role-specific content",
      any("command queue" in n["message"] for n in mine["notifications"]), mine)
citizen_mine = requests.get(f"{B}/notifications/mine", headers=hdr(ct)).json()
check("citizen receives citizen-specific content",
      any("SOS available" in n["message"] for n in citizen_mine["notifications"]), citizen_mine)
nid = mine["notifications"][0]["notificationId"]
ack = requests.post(f"{B}/notifications/{nid}/ack", headers=hdr(lt))
check("acknowledgement tracked separately from delivery",
      ack.status_code == 200 and ack.json()["acknowledged"] and ack.json()["delivered"], ack.text)
check("cannot acknowledge someone else's notification (403)",
      requests.post(f"{B}/notifications/{nid}/ack", headers=hdr(mt)).status_code == 403)
mon = requests.get(f"{B}/notifications/monitor", headers=hdr(at)).json()
check("notification monitor separates delivered and acknowledged",
      mon["total"] >= 3 and "p1Unacknowledged" in mon, mon)
esc = requests.post(f"{B}/notifications/escalate-scan", headers=hdr(at)).json()
check("escalation scan runs", "escalated" in esc, esc)

# =========================== PHASE 10: authority controls
sr = requests.get(f"{B}/authority/situation-report", headers=hdr(at)).json()
check("situation report lists data gaps explicitly", len(sr["dataGaps"]) >= 1, sr.get("dataGaps"))
check("situation report separates rescued from active",
      "peopleRescued" in sr["rescue"] and "sosActive" in sr["rescue"], sr["rescue"])
check("situation report includes search and missing figures",
      "openMissingEntries" in sr["search"], sr["search"])
req2 = requests.post(f"{B}/shelters/SH-S1/requirements", headers=hdr(sh),
                     json={"category": "FOOD", "unit": "packets", "requestedQuantity": 900}).json()
rid2 = req2["requestId"]
requests.post(f"{B}/relief/requests/{rid2}/approve", headers=hdr(at), json={"approvedQuantity": 900})
requests.post(f"{B}/relief/requests/{rid2}/commit", headers=hdr(ng), json={"allocatedQuantity": 900})
ra = requests.post(f"{B}/authority/reallocate", headers=hdr(at), json={
    "fromRequestId": rid2, "toShelterId": "SH-S3", "quantity": 300,
    "reason": "SH-S3 over capacity and unserved"})
check("authority reallocation creates a new audited allocation",
      ra.status_code == 200 and ra.json()["newRequest"]["allocatedQuantity"] == 300, ra.text)
bad_ra = requests.post(f"{B}/authority/reallocate", headers=hdr(at), json={
    "fromRequestId": rid2, "toShelterId": "SH-S3", "quantity": 9999, "reason": "too much"})
check("cannot reallocate more than is unshipped (409)", bad_ra.status_code == 409, bad_ra.text)
cd = requests.get(f"{B}/authority/cross-district", headers=hdr(at)).json()
check("cross-district rollup with advisory mutual aid",
      isinstance(cd["regions"], list) and all(s["advisory"] for s in cd["mutualAidSuggestions"]), cd)
es = requests.post(f"{B}/authority/escalate", headers=hdr(at), json={
    "objectType": "SOS", "objectId": sid, "level": "STATE", "reason": "Beyond district capacity"})
check("escalation recorded", es.status_code == 200 and es.json()["escalation"]["level"] == "STATE", es.text)
dlog = requests.get(f"{B}/authority/decision-log", headers=hdr(at)).json()
check("decision log holds only human decisions",
      len(dlog["decisions"]) >= 5 and all("action" in d for d in dlog["decisions"]), len(dlog["decisions"]))
check("leader cannot read the decision log (403)",
      requests.get(f"{B}/authority/decision-log", headers=hdr(lt)).status_code == 403)

# =========================== regressions
check("legacy endpoints still work",
      requests.get(f"{B}/overview/stats").status_code == 200)
check("phase 1-4 queue still works", requests.get(f"{B}/sos/queue", headers=hdr(lt)).status_code == 200)

print(f"\n==== {P} passed, {F} failed ====")
