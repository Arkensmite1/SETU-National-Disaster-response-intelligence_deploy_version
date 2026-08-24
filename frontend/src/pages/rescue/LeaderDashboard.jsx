import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { AlertOctagon, Bot, Layers, RefreshCw, Timer, Users2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Panel, SectionHeading, StatCard } from "@/components/common/GovUI";
import { AdvisoryNote, LocationQuality, PriorityBadge, SafetyNote, StateBadge } from "@/components/setu/SetuBits";
import { apiError, setuApi, setuEndpoints } from "@/lib/setuApi";

export default function LeaderDashboard() {
  const [dash, setDash] = useState(null);
  const [queue, setQueue] = useState([]);
  const [teams, setTeams] = useState([]);
  const [clusters, setClusters] = useState(null);
  const [roads, setRoads] = useState([]);
  const [selected, setSelected] = useState(null);
  const [recs, setRecs] = useState(null);
  const [advisory, setAdvisory] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [d, q, t, c, r] = await Promise.all([
        setuApi.get(setuEndpoints.rescueDashboard),
        setuApi.get(setuEndpoints.sosQueue),
        setuApi.get(setuEndpoints.rescueTeams),
        setuApi.get(setuEndpoints.clusters),
        setuApi.get(setuEndpoints.blockedRoads),
      ]);
      setDash(d.data);
      setQueue(q.data.sos || []);
      setTeams(t.data.teams || []);
      setClusters(c.data);
      setRoads(r.data.incidents || []);
    } catch (e) {
      toast.error(apiError(e, "Could not load the command centre"));
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [load]);

  const openRecommendations = async (sos) => {
    setSelected(sos);
    setRecs(null);
    try {
      const { data } = await setuApi.get(setuEndpoints.recommendations(sos.sosId));
      setRecs(data);
    } catch (e) {
      toast.error(apiError(e, "Could not load recommendations"));
    }
  };

  const assign = async (teamId, isTopRanked) => {
    setBusy(true);
    try {
      const { data } = await setuApi.post(setuEndpoints.sosAssign(selected.sosId), {
        teamId, overrideRecommendation: !isTopRanked,
      });
      toast.success(data.message || "Team assigned");
      setSelected(null);
      setRecs(null);
      load();
    } catch (e) {
      toast.error(apiError(e, "Assignment failed"));
      load();
    } finally {
      setBusy(false);
    }
  };

  const runTimeoutScan = async () => {
    try {
      const { data } = await setuApi.post(setuEndpoints.timeoutScan);
      toast[data.timedOut ? "warning" : "success"](
        data.timedOut
          ? `${data.timedOut} assignment(s) timed out and returned to the queue for reassignment`
          : "No assignment timeouts"
      );
      load();
    } catch (e) {
      toast.error(apiError(e, "Timeout scan failed"));
    }
  };

  const getAdvisory = async () => {
    setBusy(true);
    try {
      const { data } = await setuApi.get(setuEndpoints.aiSummary);
      setAdvisory(data);
    } catch (e) {
      toast.error(apiError(e, "Advisory unavailable"));
    } finally {
      setBusy(false);
    }
  };

  const c = dash?.counts || {};
  const t = dash?.teams || {};

  return (
    <div className="max-w-[1600px] mx-auto px-4 py-6 space-y-6">
      <SectionHeading
        eyebrow="Rescue command centre"
        title="Rescue Leader dashboard"
        description="Assign, monitor, reassign and escalate. Every recommendation here is advisory — you confirm every assignment."
        action={
          <div className="flex flex-wrap gap-2">
            <Button onClick={runTimeoutScan} data-testid="timeout-scan-button"
                    className="bg-white border border-slate-300 text-slate-700 gap-2 h-9 text-xs">
              <Timer size={14} /> Check assignment timeouts
            </Button>
            <Button onClick={load} data-testid="leader-refresh-button"
                    className="bg-national text-white gap-2 h-9 text-xs">
              <RefreshCw size={14} /> Refresh
            </Button>
          </div>
        }
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 xl:grid-cols-7 gap-3">
        <StatCard label="Active SOS" value={c.totalActiveSos ?? "—"} accent="national" />
        <StatCard label="P1 Critical" value={c.critical_P1 ?? "—"} accent="red" />
        <StatCard label="P2 High" value={c.high_P2 ?? "—"} accent="saffron" />
        <StatCard label="P3 Normal" value={c.normal_P3 ?? "—"} accent="national" />
        <StatCard label="Unassigned" value={c.unassigned ?? "—"} accent="red" />
        <StatCard label="People waiting" value={c.peopleAwaitingRescue ?? "—"} accent="national" />
        <StatCard label="Teams available" value={`${t.available ?? "—"} / ${t.total ?? "—"}`} accent="green" />
      </div>

      <SafetyNote>{dash?.note}</SafetyNote>

      <div className="grid xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2 space-y-6">
          <Panel title={`SOS queue (${queue.length})`}>
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="sos-queue-table">
                <thead>
                  <tr className="text-left text-[11px] uppercase tracking-widest text-slate-500 border-b border-slate-200">
                    <th className="py-2 pr-3">SOS</th>
                    <th className="py-2 pr-3">Priority</th>
                    <th className="py-2 pr-3">Status</th>
                    <th className="py-2 pr-3">Emergency</th>
                    <th className="py-2 pr-3">People</th>
                    <th className="py-2 pr-3">Team</th>
                    <th className="py-2">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {queue.map((s) => (
                    <tr key={s.sosId} className="border-b border-slate-100 align-top"
                        data-testid={`queue-row-${s.sosId}`}>
                      <td className="py-2 pr-3 font-mono text-xs">
                        {s.sosId}
                        <div className="mt-1"><LocationQuality quality={s.locationQuality} /></div>
                      </td>
                      <td className="py-2 pr-3"><PriorityBadge priority={s.priority} /></td>
                      <td className="py-2 pr-3"><StateBadge status={s.status} /></td>
                      <td className="py-2 pr-3 text-xs">{s.emergencyType}</td>
                      <td className="py-2 pr-3 text-xs">
                        {s.peopleCount} ({s.injuredCount} inj)
                      </td>
                      <td className="py-2 pr-3 text-xs">{s.assignedTeamId || "—"}</td>
                      <td className="py-2">
                        {["PENDING", "TIMEOUT", "VERIFIED"].includes(s.status) ? (
                          <Button onClick={() => openRecommendations(s)}
                                  data-testid={`assign-button-${s.sosId}`}
                                  className="h-8 text-xs bg-national text-white">
                            Assign team
                          </Button>
                        ) : (
                          <span className="text-[11px] text-slate-500">in progress</span>
                        )}
                      </td>
                    </tr>
                  ))}
                  {!queue.length && (
                    <tr><td colSpan={7} className="py-4 text-slate-500 text-sm">
                      No active SOS in the queue. This reflects data received so far and is not a
                      confirmation that no emergency exists.
                    </td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </Panel>

          {selected && (
            <Panel title={`Assignment recommendation — ${selected.sosId}`}
                   action={
                     <button className="text-xs text-slate-500 underline"
                             onClick={() => { setSelected(null); setRecs(null); }}>
                       Close
                     </button>
                   }>
              {!recs ? (
                <p className="text-sm text-slate-500">Ranking teams…</p>
              ) : (
                <div className="space-y-3" data-testid="recommendation-panel">
                  <SafetyNote>{recs.note}</SafetyNote>
                  <div className="text-xs text-slate-600">
                    Recommended team size: <strong>{recs.recommendedTeamSize}</strong> (advisory)
                  </div>
                  {recs.recommendations.map((r, i) => (
                    <div key={r.teamId} className="border border-slate-200 rounded-md p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div>
                          <div className="font-semibold text-national text-sm">
                            {i === 0 && <span className="text-[10px] uppercase text-saffron mr-2">top suggestion</span>}
                            {r.name} <span className="font-mono text-xs text-slate-500">{r.teamId}</span>
                          </div>
                          <div className="text-[11px] text-slate-500">
                            {r.status} • {r.vehicle} • score {r.score}
                            {r.distanceKm !== null ? ` • ${r.distanceKm} km` : ""}
                          </div>
                        </div>
                        <Button disabled={busy || !r.assignable}
                                onClick={() => assign(r.teamId, i === 0)}
                                data-testid={`confirm-assign-${r.teamId}`}
                                className={`h-8 text-xs ${r.assignable ? "bg-national text-white" : "bg-slate-200 text-slate-500"}`}>
                          {r.assignable ? (i === 0 ? "Confirm assignment" : "Assign anyway (override)") : "Not available"}
                        </Button>
                      </div>
                      <ul className="list-disc ml-5 mt-2 text-[11px] text-slate-600">
                        {r.factors.map((f) => <li key={f}>{f}</li>)}
                      </ul>
                    </div>
                  ))}
                </div>
              )}
            </Panel>
          )}
        </div>

        <div className="space-y-6">
          <Panel title="SOS clusters" action={<Layers size={14} className="text-national" />}>
            {!clusters?.clusters?.length ? (
              <p className="text-sm text-slate-600">No clusters — no active SOS with a location.</p>
            ) : (
              <div className="space-y-2" data-testid="clusters-panel">
                {clusters.clusters.map((cl) => (
                  <div key={cl.clusterId} className="border border-slate-200 rounded-md p-2.5">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-national text-sm">{cl.clusterId}</span>
                      <PriorityBadge priority={cl.topPriority} />
                    </div>
                    <div className="text-[11px] text-slate-600 mt-1">
                      {cl.sosCount} SOS • {cl.peopleCount} people • {cl.injuredCount} injured •{" "}
                      {cl.unassigned} unassigned
                    </div>
                    <div className="text-[11px] text-slate-500">
                      centre {cl.centre.latitude}, {cl.centre.longitude}
                    </div>
                  </div>
                ))}
                <p className="text-[11px] text-slate-500">{clusters.note}</p>
              </div>
            )}
          </Panel>

          <Panel title="AI operational summary"
                 action={
                   <Button onClick={getAdvisory} disabled={busy} data-testid="ai-summary-button"
                           className="h-8 text-xs bg-national text-white gap-2">
                     <Bot size={13} /> Generate
                   </Button>
                 }>
            {advisory ? (
              <AdvisoryNote>
                {advisory.text}
                {advisory.fallbackUsed && (
                  <div className="text-[11px] text-slate-500 mt-2">
                    AI was unavailable — a deterministic summary is shown instead. Operations are
                    never blocked by an AI failure.
                  </div>
                )}
              </AdvisoryNote>
            ) : (
              <p className="text-sm text-slate-600">
                Generate an advisory shift summary. It is a recommendation only — nothing is applied
                automatically.
              </p>
            )}
          </Panel>

          <Panel title="Teams" action={<Users2 size={14} className="text-national" />}>
            <div className="space-y-2" data-testid="teams-panel">
              {teams.map((tm) => (
                <div key={tm.teamId} className="flex items-center justify-between border border-slate-200 rounded-md p-2">
                  <div>
                    <div className="text-sm font-semibold text-national">{tm.name}</div>
                    <div className="text-[11px] text-slate-500">
                      {tm.vehicle} • {(tm.capabilities || []).join(", ") || "no capabilities listed"}
                    </div>
                  </div>
                  <StateBadge status={tm.status} />
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="Blocked roads" action={<AlertOctagon size={14} style={{ color: "#C62828" }} />}>
            {!roads.length ? (
              <p className="text-sm text-slate-600">No blocked roads reported.</p>
            ) : (
              <ul className="space-y-2 text-xs text-slate-700" data-testid="blocked-roads-list">
                {roads.map((r) => (
                  <li key={r.incidentId} className="border border-slate-200 rounded-md p-2">
                    <strong>{r.description}</strong>
                    <div className="text-[11px] text-slate-500">
                      {r.location?.latitude?.toFixed(4)}, {r.location?.longitude?.toFixed(4)} • {r.severity}
                    </div>
                  </li>
                ))}
              </ul>
            )}
            <p className="text-[11px] text-slate-500 mt-2">
              Routes are advisory. SETU never claims a route is guaranteed safe.
            </p>
          </Panel>
        </div>
      </div>
    </div>
  );
}
