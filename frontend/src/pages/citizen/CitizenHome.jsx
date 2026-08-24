import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { MapPin, RefreshCw, Siren, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Panel, SectionHeading } from "@/components/common/GovUI";
import {
  AdvisoryNote, LocationQuality, NetworkBadge, PriorityBadge, SafetyNote,
  StateBadge, StateTracker,
} from "@/components/setu/SetuBits";
import { useAuth } from "@/context/AuthContext";
import { apiError, setuApi, setuEndpoints } from "@/lib/setuApi";
import { acquireLocation, listQueue, networkMode, syncQueue } from "@/lib/offlineQueue";

export default function CitizenHome() {
  const { user } = useAuth();
  const [alerts, setAlerts] = useState([]);
  const [areaCheck, setAreaCheck] = useState(null);
  const [mySos, setMySos] = useState([]);
  const [mode, setMode] = useState(networkMode());
  const [queued, setQueued] = useState(listQueue().length);
  const [busy, setBusy] = useState(false);

  const loadAlerts = useCallback(async () => {
    try {
      const { data } = await setuApi.get(setuEndpoints.myAlerts);
      setAlerts(data.alerts || []);
    } catch (e) {
      /* absence of alerts is never an all-clear — surfaced in the UI below */
    }
  }, []);

  const loadSos = useCallback(async () => {
    try {
      const { data } = await setuApi.get(setuEndpoints.mySos);
      setMySos(data.sos || []);
    } catch (e) {
      /* ignore */
    }
  }, []);

  const checkArea = useCallback(async () => {
    setBusy(true);
    try {
      const loc = await acquireLocation();
      if (!loc) {
        toast.error("Location unavailable — you can still send an SOS with a landmark");
        return;
      }
      const { data } = await setuApi.post(setuEndpoints.checkLocation, { location: loc });
      setAreaCheck(data);
      await setuApi.post(setuEndpoints.myLocation, { location: loc }).catch(() => {});
      await loadAlerts();
    } catch (e) {
      toast.error(apiError(e, "Could not check your area"));
    } finally {
      setBusy(false);
    }
  }, [loadAlerts]);

  useEffect(() => {
    loadAlerts();
    loadSos();
    const onNet = () => setMode(networkMode());
    window.addEventListener("online", onNet);
    window.addEventListener("offline", onNet);
    const t = setInterval(() => { setMode(networkMode()); setQueued(listQueue().length); loadSos(); }, 20000);
    return () => {
      window.removeEventListener("online", onNet);
      window.removeEventListener("offline", onNet);
      clearInterval(t);
    };
  }, [loadAlerts, loadSos]);

  const drainQueue = async () => {
    try {
      const r = await syncQueue();
      setQueued(listQueue().length);
      toast.success(`${r.synced} queued SOS uploaded — original creation time preserved`);
      loadSos();
    } catch (e) {
      toast.error(apiError(e, "Sync failed — items are still saved on your device"));
    }
  };

  const cancel = async (sosId) => {
    try {
      await setuApi.post(setuEndpoints.sosCancel(sosId));
      toast.success("SOS cancelled — the record and audit trail are retained");
      loadSos();
    } catch (e) {
      toast.error(apiError(e, "Could not cancel"));
    }
  };

  return (
    <div className="max-w-[1600px] mx-auto px-4 py-6 space-y-6">
      <SectionHeading
        eyebrow="Citizen view"
        title={`Namaste, ${user?.name || "citizen"}`}
        description="Your alerts, your area status and your own SOS cases. You only ever see your own emergency data."
        action={
          <div className="flex items-center gap-2">
            <NetworkBadge mode={mode} queued={queued} />
            <Link to="/citizen/sos" data-testid="citizen-sos-cta">
              <Button className="text-white font-bold gap-2" style={{ backgroundColor: "#C62828" }}>
                <Siren size={16} /> Send SOS
              </Button>
            </Link>
          </div>
        }
      />

      {queued > 0 && (
        <div className="flex items-center justify-between gap-3 p-3 rounded-md border border-amber-200 bg-amber-50"
             data-testid="offline-queue-banner">
          <div className="text-sm text-slate-700">
            <strong>{queued} SOS saved on this device</strong> — network unavailable when it was created.
            It has <strong>not</strong> been received by SETU yet.
          </div>
          <Button onClick={drainQueue} data-testid="offline-queue-sync-button"
                  className="bg-national text-white gap-2">
            <Upload size={14} /> Upload now
          </Button>
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Panel
            title="My area status"
            action={
              <Button onClick={checkArea} disabled={busy} data-testid="check-area-button"
                      className="bg-national text-white gap-2 h-8 text-xs">
                <MapPin size={13} /> {busy ? "Checking…" : "Check my location"}
              </Button>
            }
          >
            {!areaCheck ? (
              <SafetyNote>
                Your area has not been checked in this session. No data does <strong>not</strong> mean
                you are safe — tap “Check my location” to match your position against active
                disaster events from the authorized disaster-information integration.
              </SafetyNote>
            ) : (
              <div className="space-y-3" data-testid="area-check-result">
                {areaCheck.matches?.length ? (
                  areaCheck.matches.map((m) => (
                    <div key={m.eventId} className="border border-slate-200 rounded-md p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <StateBadge status={m.classification} />
                        <span className="text-[11px] font-bold uppercase tracking-widest text-slate-500">
                          {m.disasterType} • {m.infoTier?.replace(/_/g, " ")} • {m.severity}
                        </span>
                        {m.experimental && (
                          <span className="text-[10px] font-bold uppercase text-amber-700">
                            Experimental product — not a certainty
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-slate-700 mt-2">{m.message}</p>
                      {m.rescueWorkflowsEnabled === false && (
                        <p className="text-[11px] text-slate-500 mt-1">
                          This is a forecast/warning — no rescue operation is triggered by it.
                        </p>
                      )}
                      {!!m.instructions?.length && (
                        <ul className="list-disc ml-5 mt-2 text-xs text-slate-600 space-y-0.5">
                          {m.instructions.map((i) => <li key={i}>{i}</li>)}
                        </ul>
                      )}
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-slate-600">No active event records were matched.</p>
                )}
                <SafetyNote>{areaCheck.safetyNote}</SafetyNote>
                {areaCheck.overlappingZones && (
                  <p className="text-xs text-slate-600">
                    You are inside more than one active disaster zone. Both remain active — neither
                    overrides the other.
                  </p>
                )}
              </div>
            )}
          </Panel>

          <Panel
            title="My SOS cases"
            action={
              <button onClick={loadSos} className="text-xs text-national font-semibold flex items-center gap-1"
                      data-testid="refresh-my-sos">
                <RefreshCw size={12} /> Refresh
              </button>
            }
          >
            {!mySos.length ? (
              <p className="text-sm text-slate-600">You have not raised any SOS.</p>
            ) : (
              <div className="space-y-4">
                {mySos.map((s) => (
                  <div key={s.sosId} className="border border-slate-200 rounded-md p-3"
                       data-testid={`my-sos-${s.sosId}`}>
                    <div className="flex flex-wrap items-center gap-2 justify-between">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-xs text-slate-500">{s.sosId}</span>
                        <PriorityBadge priority={s.priority} />
                        <StateBadge status={s.status} />
                        {s.retryCount > 0 && (
                          <span className="text-[10px] font-bold uppercase text-slate-500">
                            {s.retryCount} repeat press(es) merged
                          </span>
                        )}
                      </div>
                      {["CREATED", "RECEIVED", "VERIFIED", "PENDING", "ASSIGNED"].includes(s.status) && (
                        <Button onClick={() => cancel(s.sosId)} data-testid={`cancel-sos-${s.sosId}`}
                                className="h-8 text-xs bg-white border border-slate-300 text-slate-700 hover:bg-slate-50">
                          Cancel — sent by mistake
                        </Button>
                      )}
                    </div>
                    <div className="mt-3"><StateTracker status={s.status} /></div>
                    <div className="mt-2 grid sm:grid-cols-2 gap-1 text-xs text-slate-600">
                      <div>People: <strong>{s.peopleCount}</strong> • injured <strong>{s.injuredCount}</strong></div>
                      <div>Emergency: <strong>{s.emergencyType}</strong></div>
                      <div>Team assigned: <strong>{s.rescueTeamNotified ? s.assignedTeamId : "not yet"}</strong></div>
                      <div>Acknowledged by SETU: <strong>{s.acknowledged ? "yes" : "no"}</strong></div>
                    </div>
                    <div className="mt-2"><LocationQuality quality={s.locationQuality} /></div>
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </div>

        <div className="space-y-6">
          <Panel title="Alerts for me">
            {!alerts.length ? (
              <SafetyNote>
                No alert has been issued for your saved location. Absence of an alert is not an
                all-clear — keep following official instructions.
              </SafetyNote>
            ) : (
              <div className="space-y-3" data-testid="my-alerts">
                {alerts.map((a) => (
                  <div key={a.eventId} className="border border-slate-200 rounded-md p-3">
                    <div className="flex items-center gap-2 flex-wrap">
                      <StateBadge status={a.status} />
                      <span className="text-[11px] font-bold uppercase tracking-widest text-slate-500">
                        {a.infoTier?.replace(/_/g, " ")}
                      </span>
                    </div>
                    <div className="font-semibold text-national text-sm mt-1">{a.title}</div>
                    <p className="text-xs text-slate-600 mt-1">{a.message}</p>
                    {!!a.actions?.length && (
                      <ul className="list-disc ml-5 mt-2 text-xs text-slate-600">
                        {a.actions.map((x) => <li key={x}>{x}</li>)}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <Panel title="How SETU handles your data">
            <ul className="text-xs text-slate-600 space-y-2">
              <li>Your precise location is shared only while a rescue case is active, and live
                sharing stops when the case is closed.</li>
              <li>Rescue teams see only the emergencies assigned to them.</li>
              <li>Every status change on your case is written to an audit log you can request.</li>
            </ul>
            <div className="mt-3">
              <AdvisoryNote title="About AI in SETU">
                AI is used only for summaries, translation, prioritisation hints and duplicate
                detection. It never declares a disaster or decides a rescue outcome.
              </AdvisoryNote>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
