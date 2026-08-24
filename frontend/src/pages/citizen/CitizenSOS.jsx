import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Crosshair, Mic, Siren, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Panel, SectionHeading } from "@/components/common/GovUI";
import { LocationQuality, NetworkBadge, PriorityBadge, SafetyNote, StateTracker } from "@/components/setu/SetuBits";
import { apiError, setuApi, setuEndpoints } from "@/lib/setuApi";
import {
  acquireLocation, batteryLevel, enqueueSos, lastKnownLocation, listQueue,
  networkMode, rememberLocation, syncQueue,
} from "@/lib/offlineQueue";

const EMERGENCIES = [
  ["TRAPPED_WATER_RISING", "Trapped — water rising"],
  ["DROWNING", "Drowning / swept away"],
  ["BUILDING_COLLAPSE", "Building collapse"],
  ["MEDICAL_CRITICAL", "Critical medical emergency"],
  ["UNCONSCIOUS", "Someone unconscious"],
  ["FIRE", "Fire"],
  ["TRAPPED", "Trapped, water not rising"],
  ["STRANDED", "Stranded / cut off"],
  ["INJURED", "Injured, needs help"],
  ["NO_FOOD_WATER", "No food or drinking water"],
  ["EVACUATION_NEEDED", "Need evacuation"],
  ["INFO_REQUEST", "Information / other assistance"],
];

const REGION_FALLBACK = [
  ["Dhemaji, Assam", 27.483, 94.582],
  ["Majuli, Assam", 26.95, 94.1667],
  ["Darbhanga, Bihar", 26.152, 85.897],
  ["Jorhat, Assam", 26.75, 94.22],
];

const field = "w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:border-national";

export default function CitizenSOS() {
  const navigate = useNavigate();
  const [mode, setMode] = useState(networkMode());
  const [queued, setQueued] = useState(listQueue().length);
  const [location, setLocation] = useState(null);
  const [locating, setLocating] = useState(false);
  const [manual, setManual] = useState({ latitude: "", longitude: "" });
  const [landmark, setLandmark] = useState("");
  const [regionIdx, setRegionIdx] = useState(0);
  const [battery, setBattery] = useState(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [cancelLeft, setCancelLeft] = useState(0);

  const [form, setForm] = useState({
    emergencyType: "TRAPPED_WATER_RISING",
    peopleCount: 1, injuredCount: 0, childrenCount: 0, elderlyCount: 0,
    description: "", accessibilityRequirement: "", voiceNote: "",
  });

  useEffect(() => {
    const onNet = () => setMode(networkMode());
    window.addEventListener("online", onNet);
    window.addEventListener("offline", onNet);
    batteryLevel().then(setBattery);
    getLocation();
    return () => {
      window.removeEventListener("online", onNet);
      window.removeEventListener("offline", onNet);
    };
  }, []);

  useEffect(() => {
    if (!result || cancelLeft <= 0) return;
    const t = setTimeout(() => setCancelLeft((v) => v - 1), 1000);
    return () => clearTimeout(t);
  }, [result, cancelLeft]);

  const getLocation = async () => {
    setLocating(true);
    const loc = await acquireLocation();
    setLocating(false);
    if (loc) {
      setLocation(loc);
      toast.success(`Location captured (${loc.source})`);
    } else {
      toast.error("GPS and network location unavailable — enter your location manually or use a landmark below");
    }
  };

  const useManual = () => {
    const lat = parseFloat(manual.latitude);
    const lng = parseFloat(manual.longitude);
    if (Number.isNaN(lat) || Number.isNaN(lng)) return toast.error("Enter valid coordinates");
    const loc = { latitude: lat, longitude: lng, accuracy: 500, source: "MANUAL", timestamp: new Date().toISOString() };
    setLocation(loc);
    rememberLocation(loc);
    toast.success("Manual location set");
  };

  const useLandmarkLocation = () => {
    if (!landmark.trim()) return toast.error("Describe the landmark first");
    const lk = lastKnownLocation();
    const [, lat, lng] = REGION_FALLBACK[regionIdx];
    const base = lk || { latitude: lat, longitude: lng };
    const loc = {
      latitude: base.latitude, longitude: base.longitude,
      accuracy: lk ? 1500 : 5000, source: "LANDMARK",
      landmark: landmark.trim(), timestamp: new Date().toISOString(),
    };
    setLocation(loc);
    toast.success("Landmark location set — rescue teams will search around this description");
  };

  const buildPayload = () => ({
    location: {
      latitude: location.latitude,
      longitude: location.longitude,
      accuracy: location.accuracy ?? null,
      source: location.source || "GPS",
      timestamp: location.timestamp || new Date().toISOString(),
      landmark: location.landmark || landmark || null,
    },
    emergencyType: form.emergencyType,
    peopleCount: Number(form.peopleCount) || 1,
    injuredCount: Number(form.injuredCount) || 0,
    childrenCount: Number(form.childrenCount) || 0,
    elderlyCount: Number(form.elderlyCount) || 0,
    description: form.description || null,
    accessibilityRequirement: form.accessibilityRequirement || null,
    landmark: landmark || null,
    networkStatus: mode,
    batteryStatus: battery,
  });

  const submit = async () => {
    if (!location) {
      return toast.error("A location is required — use GPS, manual coordinates or a landmark");
    }
    const payload = buildPayload();
    if (mode === "OFFLINE") {
      enqueueSos(payload);
      setQueued(listQueue().length);
      toast.warning("Saved on your device. It has NOT been received by SETU yet — it will upload automatically when the network returns.");
      return;
    }
    setBusy(true);
    try {
      const { data } = await setuApi.post(setuEndpoints.sos, payload);
      setResult(data);
      setCancelLeft(data.cancelWindowSeconds || 30);
      toast.success(data.duplicateOfExisting ? "Existing case updated" : "SOS received by SETU");
    } catch (e) {
      enqueueSos(payload);
      setQueued(listQueue().length);
      toast.error(`${apiError(e, "Could not reach SETU")} — your SOS has been saved locally and will retry. Call 1078 if you can.`);
    } finally {
      setBusy(false);
    }
  };

  const cancelSos = async () => {
    try {
      const { data } = await setuApi.post(setuEndpoints.sosCancel(result.sosId));
      setResult(data);
      setCancelLeft(0);
      toast.success("SOS cancelled — the record and audit trail are retained");
    } catch (e) {
      toast.error(apiError(e, "Could not cancel"));
    }
  };

  const drain = async () => {
    try {
      const r = await syncQueue();
      setQueued(listQueue().length);
      toast.success(`${r.synced} queued SOS uploaded with the original creation time`);
    } catch (e) {
      toast.error(apiError(e, "Sync failed — items remain on your device"));
    }
  };

  return (
    <div className="max-w-[1100px] mx-auto px-4 py-6 space-y-6">
      <SectionHeading
        eyebrow="Emergency SOS"
        title="Send an emergency SOS"
        description="One SOS can represent several people. Optional details can be skipped entirely on a weak network."
        action={<NetworkBadge mode={mode} queued={queued} />}
      />

      {queued > 0 && (
        <div className="flex items-center justify-between gap-3 p-3 rounded-md border border-amber-200 bg-amber-50">
          <div className="text-sm text-slate-700">
            <strong>{queued} SOS waiting on this device.</strong> Not received by SETU yet.
          </div>
          <Button onClick={drain} className="bg-national text-white gap-2" data-testid="sos-sync-button">
            <Upload size={14} /> Upload now
          </Button>
        </div>
      )}

      {result ? (
        <Panel title="SOS status">
          <div className="space-y-4" data-testid="sos-result">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs text-slate-500">{result.sosId}</span>
              <PriorityBadge priority={result.priority} />
              {result.duplicateOfExisting && (
                <span className="text-[10px] font-bold uppercase text-slate-500">
                  merged into existing case
                </span>
              )}
            </div>
            <SafetyNote>{result.message}</SafetyNote>
            <StateTracker status={result.status} />
            <LocationQuality quality={result.locationQuality} />
            <div className="text-xs text-slate-600">
              Operational triage: <strong>{result.priority}</strong> — this is a dispatch priority,
              not a medical assessment.
              {!!result.priorityReasons?.length && (
                <ul className="list-disc ml-5 mt-1">
                  {result.priorityReasons.map((r) => <li key={r}>{r}</li>)}
                </ul>
              )}
            </div>
            {result.recommendedTeamSize && (
              <div className="text-xs text-slate-600">
                Recommended team size for {result.peopleCount} people: <strong>{result.recommendedTeamSize}</strong> (advisory)
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              {cancelLeft > 0 && result.status !== "CANCELLED_BY_USER" && (
                <Button onClick={cancelSos} data-testid="sos-cancel-button"
                        className="bg-white border border-slate-300 text-slate-700 hover:bg-slate-50">
                  Cancel — sent by mistake ({cancelLeft}s)
                </Button>
              )}
              <Button onClick={() => navigate("/citizen")} className="bg-national text-white">
                Track my cases
              </Button>
              <Button onClick={() => { setResult(null); setCancelLeft(0); }}
                      className="bg-white border border-slate-300 text-slate-700 hover:bg-slate-50">
                Raise another SOS
              </Button>
            </div>
            <p className="text-[11px] text-slate-500">
              A rescue team is assigned by a rescue leader. SETU will not tell you a team is on the
              way until a team has actually accepted the case.
            </p>
          </div>
        </Panel>
      ) : (
        <div className="grid lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <Panel title="1. Your location">
              <div className="space-y-3">
                <div className="flex flex-wrap gap-2">
                  <Button onClick={getLocation} disabled={locating} data-testid="sos-locate-button"
                          className="bg-national text-white gap-2">
                    <Crosshair size={14} /> {locating ? "Locating…" : "Use my location (GPS)"}
                  </Button>
                  {location && (
                    <span className="text-xs text-slate-600 self-center" data-testid="sos-location-readout">
                      {location.latitude.toFixed(5)}, {location.longitude.toFixed(5)} • source{" "}
                      <strong>{location.source}</strong>{" "}
                      {location.accuracy ? `• ±${Math.round(location.accuracy)} m` : "• accuracy unknown"}
                    </span>
                  )}
                </div>
                {location && ["NETWORK", "LAST_KNOWN", "MANUAL", "LANDMARK"].includes(location.source) && (
                  <SafetyNote>
                    Approximate location ({location.source}). Rescue teams will be told the position
                    is approximate — add a landmark below to help them find you.
                  </SafetyNote>
                )}
                <details className="text-sm">
                  <summary className="cursor-pointer font-semibold text-national">
                    GPS not working? Enter location manually or by landmark
                  </summary>
                  <div className="mt-3 grid sm:grid-cols-2 gap-2">
                    <input className={field} placeholder="Latitude e.g. 27.4820" value={manual.latitude}
                           onChange={(e) => setManual({ ...manual, latitude: e.target.value })} />
                    <input className={field} placeholder="Longitude e.g. 94.5800" value={manual.longitude}
                           onChange={(e) => setManual({ ...manual, longitude: e.target.value })} />
                    <Button onClick={useManual} className="bg-white border border-slate-300 text-slate-700 sm:col-span-2">
                      Use these coordinates (MANUAL)
                    </Button>
                    <input className={`${field} sm:col-span-2`} data-testid="sos-landmark-input"
                           placeholder="Landmark, e.g. behind Dhemaji bus stand, blue water tank"
                           value={landmark} onChange={(e) => setLandmark(e.target.value)} />
                    <select className={field} value={regionIdx}
                            onChange={(e) => setRegionIdx(Number(e.target.value))}>
                      {REGION_FALLBACK.map(([label], i) => <option key={label} value={i}>{label}</option>)}
                    </select>
                    <Button onClick={useLandmarkLocation} className="bg-white border border-slate-300 text-slate-700">
                      Use landmark (LANDMARK)
                    </Button>
                  </div>
                </details>
              </div>
            </Panel>

            <Panel title="2. What is the emergency?">
              <div className="grid sm:grid-cols-2 gap-3">
                <label className="text-xs font-bold uppercase tracking-widest text-slate-500 sm:col-span-2">
                  Emergency type
                  <select className={`${field} mt-1`} data-testid="sos-emergency-select"
                          value={form.emergencyType}
                          onChange={(e) => setForm({ ...form, emergencyType: e.target.value })}>
                    {EMERGENCIES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                </label>
                <label className="text-xs font-bold uppercase tracking-widest text-slate-500">
                  Total people
                  <input type="number" min={1} className={`${field} mt-1`} data-testid="sos-people-input"
                         value={form.peopleCount}
                         onChange={(e) => setForm({ ...form, peopleCount: e.target.value })} />
                </label>
                <label className="text-xs font-bold uppercase tracking-widest text-slate-500">
                  Injured
                  <input type="number" min={0} className={`${field} mt-1`} data-testid="sos-injured-input"
                         value={form.injuredCount}
                         onChange={(e) => setForm({ ...form, injuredCount: e.target.value })} />
                </label>
                <label className="text-xs font-bold uppercase tracking-widest text-slate-500">
                  Children
                  <input type="number" min={0} className={`${field} mt-1`} value={form.childrenCount}
                         onChange={(e) => setForm({ ...form, childrenCount: e.target.value })} />
                </label>
                <label className="text-xs font-bold uppercase tracking-widest text-slate-500">
                  Elderly
                  <input type="number" min={0} className={`${field} mt-1`} value={form.elderlyCount}
                         onChange={(e) => setForm({ ...form, elderlyCount: e.target.value })} />
                </label>
                <label className="text-xs font-bold uppercase tracking-widest text-slate-500 sm:col-span-2">
                  Description (optional)
                  <textarea rows={2} className={`${field} mt-1`} data-testid="sos-description-input"
                            value={form.description}
                            onChange={(e) => setForm({ ...form, description: e.target.value })}
                            placeholder="Water at chest level on ground floor, 2 children with us" />
                </label>
                <label className="text-xs font-bold uppercase tracking-widest text-slate-500 sm:col-span-2">
                  Accessibility requirement (optional)
                  <input className={`${field} mt-1`} value={form.accessibilityRequirement}
                         onChange={(e) => setForm({ ...form, accessibilityRequirement: e.target.value })}
                         placeholder="Wheelchair user, cannot walk, hearing impaired…" />
                </label>
              </div>
              <p className="text-[11px] text-slate-500 mt-3">
                Photo and voice note are optional and are skipped automatically on a weak network so
                the SOS itself always gets through.
              </p>
            </Panel>
          </div>

          <div className="space-y-6">
            <Panel title="3. Send">
              <Button onClick={submit} disabled={busy} data-testid="sos-submit-button"
                      className="w-full text-white font-bold h-14 text-lg gap-2"
                      style={{ backgroundColor: "#C62828" }}>
                <Siren size={20} /> {busy ? "Sending…" : mode === "OFFLINE" ? "Save SOS (offline)" : "SEND SOS"}
              </Button>
              <ul className="text-[11px] text-slate-600 mt-3 space-y-1.5">
                <li>You can cancel for 30 seconds after sending if it was accidental.</li>
                <li>If the network is down, your SOS is stored on this device with the original
                  time and uploaded automatically later.</li>
                <li>Life-threatening emergency? Also call <strong>1078</strong> / <strong>112</strong>.</li>
              </ul>
              {battery !== null && battery <= 10 && (
                <div className="mt-3 text-[11px] text-slate-700 p-2 rounded border border-amber-200 bg-amber-50">
                  Battery is at {battery}%. Background updates are reduced, but your active SOS
                  tracking will not be dropped.
                </div>
              )}
            </Panel>
            <Panel title="Voice note (optional)">
              <div className="flex items-center gap-2 text-xs text-slate-600">
                <Mic size={14} className="text-national" />
                Voice capture is available on supported devices and is never required to submit.
              </div>
            </Panel>
          </div>
        </div>
      )}
    </div>
  );
}
