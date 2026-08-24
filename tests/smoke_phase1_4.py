"""Smoke test: Phase 1-4 SOS + rescue lifecycle against the running backend."""
import requests

B = "http://localhost:8001/api"


def hdr(t):
    return {"Authorization": f"Bearer {t}"}


def check(label, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + label + ((" | " + str(extra)[:300]) if not cond else ""))
    return cond


# --- citizen OTP login
r = requests.post(f"{B}/auth/otp/request", json={"mobile": "9000000001"}).json()
otp = r["devOtp"]
cz = requests.post(f"{B}/auth/otp/verify", json={"mobile": "9000000001", "code": otp}).json()
check("citizen otp login", "token" in cz, cz)
ct = cz["token"]

# --- staff logins
def login(email):
    return requests.post(f"{B}/auth/login", json={"email": email, "password": "Setu@1234"}).json()

ld = login("leader@setu.gov.in"); lt = ld.get("token")
mb = login("member@setu.gov.in"); mt = mb.get("token")
au = login("authority@setu.gov.in"); at = au.get("token")
check("staff logins", all([lt, mt, at]), [ld, mb, au])

# --- RBAC: citizen cannot see queue
q = requests.get(f"{B}/sos/queue", headers=hdr(ct))
check("citizen blocked from rescue queue (403)", q.status_code == 403, q.text)
check("unauthenticated blocked (401)", requests.get(f"{B}/sos/queue").status_code == 401)

# --- create SOS inside Dhemaji polygon
payload = {
    "location": {"latitude": 27.48, "longitude": 94.58, "accuracy": 12, "source": "GPS"},
    "peopleCount": 5, "injuredCount": 1, "childrenCount": 2,
    "emergencyType": "TRAPPED_WATER_RISING", "description": "Water rising on ground floor",
    "batteryStatus": 8,
}
s = requests.post(f"{B}/sos", headers=hdr(ct), json=payload).json()
check("sos created + auto event match", s.get("eventId") == "NDEM-EVENT-2026-00011", s)
check("sos reaches PENDING", s.get("status") == "PENDING", s.get("status"))
check("priority P1", s.get("priority") == "P1", s.get("priority"))
check("not claiming team notified", s.get("rescueTeamNotified") is False, s)
sid = s["sosId"]

# --- duplicate detection
d = requests.post(f"{B}/sos", headers=hdr(ct), json=payload).json()
check("duplicate merged not new case", d.get("sosId") == sid and d.get("duplicateOfExisting"), d)
check("retry counter incremented", d.get("retryCount", 0) >= 1, d.get("retryCount"))

# --- leader queue + recommendations
qq = requests.get(f"{B}/sos/queue", headers=hdr(lt)).json()
check("leader sees queue", any(x["sosId"] == sid for x in qq.get("sos", [])), qq)
rec = requests.get(f"{B}/rescue/recommendations/{sid}", headers=hdr(lt)).json()
check("ranked recommendation advisory", rec.get("advisory") and rec.get("autoApplied") is False, rec)
top = rec["recommendations"][0]
check("water rescue team ranked top", top["teamId"] == "TEAM-NDRF01", top)

# --- assign (atomic claim) + double-claim rejected
a = requests.post(f"{B}/sos/{sid}/assign", headers=hdr(lt), json={"teamId": "TEAM-NDRF01"})
check("assign ok", a.status_code == 200 and a.json().get("status") == "ASSIGNED", a.text)

s2 = requests.post(f"{B}/sos", headers=hdr(ct), json={**payload, "location": {
    "latitude": 27.51, "longitude": 94.61, "accuracy": 400, "source": "NETWORK"},
    "emergencyType": "STRANDED", "peopleCount": 2, "injuredCount": 0}).json()
sid2 = s2["sosId"]
check("second sos approximate location surfaced", s2["locationQuality"]["approximate"] is True, s2["locationQuality"])
dbl = requests.post(f"{B}/sos/{sid2}/assign", headers=hdr(lt), json={"teamId": "TEAM-NDRF01"})
check("double team claim rejected (409)", dbl.status_code == 409, dbl.text)

# --- member accept -> en route -> arrived -> rescuing -> rescued -> complete
mine = requests.get(f"{B}/sos/assigned-to-me", headers=hdr(mt)).json()
check("member sees own assignment", any(x["sosId"] == sid for x in mine.get("sos", [])), mine)
acc = requests.post(f"{B}/sos/{sid}/accept", headers=hdr(mt))
check("accept", acc.status_code == 200 and acc.json()["status"] == "ACCEPTED", acc.text)
bad = requests.post(f"{B}/sos/{sid}/status", headers=hdr(mt), json={"status": "RESCUED"})
check("illegal skip to RESCUED rejected (409)", bad.status_code == 409, bad.text)
for st in ("EN_ROUTE", "ARRIVED", "RESCUING", "RESCUED"):
    rr = requests.post(f"{B}/sos/{sid}/status", headers=hdr(mt), json={"status": st})
    check(f"status {st}", rr.status_code == 200, rr.text)
comp = requests.post(f"{B}/sos/{sid}/complete", headers=hdr(mt), json={
    "peopleRescued": 5, "injuredTransported": 1, "handedOverTo": "SH-S1",
    "victimConfirmation": False, "victimConfirmationWaivedReason": "Victim unconscious",
    "observations": "All 5 moved to shelter"})
cj = comp.json()
check("completed + live sharing stopped", comp.status_code == 200 and cj.get("liveLocationSharing") is False, cj)

tl = requests.get(f"{B}/sos/{sid}/timeline", headers=hdr(ct)).json()
check("audit timeline reconstructable", len(tl.get("timeline", [])) >= 8, len(tl.get("timeline", [])))

# --- reject flow on sid2
requests.post(f"{B}/sos/{sid2}/assign", headers=hdr(lt), json={"teamId": "TEAM-NDRF02"})
rj = requests.post(f"{B}/sos/{sid2}/reject", headers=hdr(lt), json={"reason": "ROUTE_INACCESSIBLE"})
check("reject returns case to queue", rj.status_code == 200 and rj.json()["status"] == "PENDING", rj.text)

# --- cancel flow (new sos by other citizen)
o = requests.post(f"{B}/auth/otp/request", json={"mobile": "9000000002"}).json()
c2 = requests.post(f"{B}/auth/otp/verify", json={"mobile": "9000000002", "code": o["devOtp"]}).json()["token"]
s3 = requests.post(f"{B}/sos", headers=hdr(c2), json={
    "location": {"latitude": 27.49, "longitude": 94.59, "accuracy": 20, "source": "GPS"},
    "emergencyType": "INFO_REQUEST"}).json()
can = requests.post(f"{B}/sos/{s3['sosId']}/cancel", headers=hdr(c2))
check("citizen cancel", can.status_code == 200 and can.json()["status"] == "CANCELLED_BY_USER", can.text)
check("cancelled record retained", requests.get(f"{B}/sos/{s3['sosId']}", headers=hdr(c2)).status_code == 200)

# --- cross-citizen access blocked
check("cross-citizen access blocked (403)",
      requests.get(f"{B}/sos/{sid}", headers=hdr(c2)).status_code == 403)

# --- offline sync
sync = requests.post(f"{B}/sos/sync", headers=hdr(c2), json={"items": [{
    "location": {"latitude": 27.44, "longitude": 94.50, "accuracy": 800, "source": "LAST_KNOWN"},
    "emergencyType": "STRANDED", "peopleCount": 3,
    "clientCreatedAt": "2026-07-01T10:00:00Z", "clientRef": "local-1",
    "networkStatus": "OFFLINE"}]}).json()
check("offline queue sync", sync.get("synced") == 1, sync)

# --- dashboard + clusters
dash = requests.get(f"{B}/rescue/dashboard", headers=hdr(lt)).json()
check("dashboard counts", "counts" in dash and dash["counts"]["totalActiveSos"] >= 1, dash)
cl = requests.get(f"{B}/rescue/clusters", headers=hdr(lt)).json()
check("clusters advisory", cl.get("advisory") is True and isinstance(cl.get("clusters"), list), cl)

# --- blocked road
br = requests.post(f"{B}/rescue/blocked-road", headers=hdr(mt), json={
    "location": {"latitude": 27.50, "longitude": 94.60, "accuracy": 20, "source": "GPS"},
    "description": "Bridge submerged"})
check("blocked road stored + teams notified", br.status_code == 200 and br.json()["teamsNotified"], br.text)

# --- event lifecycle independence
tr = requests.post(f"{B}/events/NDEM-EVENT-2026-00011/transition", headers=hdr(at),
                   json={"status": "RESPONSE"})
check("authority event transition", tr.status_code == 200, tr.text)
check("children untouched note", tr.json().get("childrenUntouched") is True, tr.text[:200])
bad_tr = requests.post(f"{B}/events/NDEM-EVENT-2026-00011/transition", headers=hdr(at),
                       json={"status": "DETECTED"})
check("illegal event transition rejected (409)", bad_tr.status_code == 409, bad_tr.text)
check("leader cannot transition event (403)",
      requests.post(f"{B}/events/NDEM-EVENT-2026-00011/transition", headers=hdr(lt),
                    json={"status": "RELIEF"}).status_code == 403)

# --- affected-area check + tiers
chk = requests.post(f"{B}/events/check-location", json={"location": {
    "latitude": 27.48, "longitude": 94.58, "accuracy": 10, "source": "GPS"}}).json()
check("affected area matched", any(m["classification"] == "AFFECTED" for m in chk["matches"]), chk)
check("never says safe", "never an all-clear" in chk["safetyNote"], chk["safetyNote"])
al = requests.get(f"{B}/events/alerts/for-me", headers=hdr(ct)).json()
check("role-scoped alerts", isinstance(al.get("alerts"), list), al)
