import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { RefreshCw, ScrollText, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Panel, SectionHeading, StatCard } from "@/components/common/GovUI";
import { SafetyNote, StalenessNote, StateBadge } from "@/components/setu/SetuBits";
import { apiError, setuApi, setuEndpoints } from "@/lib/setuApi";

const ADVISORY_TOOLS = [
  ["/dashboard", "Command dashboard"],
  ["/map", "Live map"],
  ["/prediction", "Flood risk advisory"],
  ["/simulation", "Scenario simulation"],
  ["/damage", "Damage & vision advisory"],
  ["/medical", "Health outlook advisory"],
  ["/economic", "Economic loss advisory"],
  ["/social", "Social media signal advisory"],
  ["/drones", "Drone operations"],
  ["/incidents", "Legacy incident feed"],
  ["/volunteers", "Volunteer roster"],
  ["/resources", "Relief resources"],
  ["/shelters", "Shelter directory"],
];

export default function AdminPortal() {
  const [overview, setOverview] = useState(null);
  const [events, setEvents] = useState([]);
  const [audit, setAudit] = useState([]);
  const [falseAlarms, setFalseAlarms] = useState([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [o, e, a, f] = await Promise.all([
        setuApi.get("/admin/overview"),
        setuApi.get(`${setuEndpoints.events}?include_closed=true`),
        setuApi.get("/admin/audit?limit=60"),
        setuApi.get("/admin/false-alarm-review"),
      ]);
      setOverview(o.data);
      setEvents(e.data.events || []);
      setAudit(a.data.entries || []);
      setFalseAlarms(f.data.users || []);
    } catch (err) {
      toast.error(apiError(err, "Could not load the authority portal"));
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const transition = async (eventId, status) => {
    if (!status) return;
    setBusy(true);
    try {
      const { data } = await setuApi.post(setuEndpoints.eventTransition(eventId), { status });
      toast.success(data.note || `Event moved to ${status}`);
      load();
    } catch (e) {
      toast.error(apiError(e, "Transition rejected"));
    } finally {
      setBusy(false);
    }
  };

  const NEXT = {
    DETECTED: ["MONITORING", "WARNING", "CONFIRMED", "CANCELLED"],
    MONITORING: ["WARNING", "CONFIRMED", "CANCELLED", "CLOSED"],
    WARNING: ["CONFIRMED", "ACTIVE", "CANCELLED"],
    CONFIRMED: ["ACTIVE", "RESPONSE", "CANCELLED"],
    ACTIVE: ["RESPONSE", "RELIEF"],
    RESPONSE: ["RELIEF", "RECOVERY"],
    RELIEF: ["RECOVERY"],
    RECOVERY: ["CLOSED"],
    CLOSED: [],
    CANCELLED: [],
  };

  const s = overview || {};

  return (
    <div className="max-w-[1600px] mx-auto px-4 py-6 space-y-6">
      <SectionHeading
        eyebrow="Admin / Authority portal"
        title="Oversight, overrides and audit"
        description="Full system visibility. Authority decisions always take precedence over automated recommendations."
        action={
          <Button onClick={load} data-testid="admin-refresh" className="bg-national text-white gap-2 h-9 text-xs">
            <RefreshCw size={14} /> Refresh
          </Button>
        }
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 xl:grid-cols-6 gap-3">
        <StatCard label="Open events" value={s.events?.open ?? "—"} />
        <StatCard label="Active (confirmed)" value={s.events?.activeTierC ?? "—"} accent="red" />
        <StatCard label="Active SOS" value={s.sos?.active ?? "—"} accent="saffron" />
        <StatCard label="Unassigned SOS" value={s.sos?.unassigned ?? "—"} accent="red" />
        <StatCard label="Shelter places free" value={s.shelters?.available ?? "—"} accent="green" />
        <StatCard label="Audit entries" value={s.auditEntries ?? "—"} />
      </div>

      <div className="grid xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2 space-y-6">
          <Panel title="Disaster events — lifecycle control">
            <SafetyNote>
              Closing or advancing an event never changes its child SOS, shelter or resource
              records. Those lifecycles are independent by design.
            </SafetyNote>
            <div className="overflow-x-auto mt-3">
              <table className="w-full text-sm" data-testid="admin-events-table">
                <thead>
                  <tr className="text-left text-[11px] uppercase tracking-widest text-slate-500 border-b border-slate-200">
                    <th className="py-2 pr-3">Event</th>
                    <th className="py-2 pr-3">Tier</th>
                    <th className="py-2 pr-3">Status</th>
                    <th className="py-2 pr-3">Severity</th>
                    <th className="py-2">Move to</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((e) => (
                    <tr key={e.eventId} className="border-b border-slate-100 align-top"
                        data-testid={`admin-event-${e.eventId}`}>
                      <td className="py-2 pr-3">
                        <div className="font-semibold text-national text-[13px]">{e.title}</div>
                        <div className="font-mono text-[11px] text-slate-500">{e.eventId} • v{e.version}</div>
                        <StalenessNote notice={e.stalenessNotice} stale={e.stale} />
                        {e.experimental && (
                          <div className="text-[10px] font-bold uppercase text-amber-700 mt-1">
                            {e.experimentalNotice}
                          </div>
                        )}
                      </td>
                      <td className="py-2 pr-3 text-[11px] font-semibold">
                        {e.infoTier?.replace(/_/g, " ")}
                        <div className="text-[10px] text-slate-500">
                          {e.rescueWorkflowsEnabled ? "rescue enabled" : "no rescue trigger"}
                        </div>
                      </td>
                      <td className="py-2 pr-3"><StateBadge status={e.status} /></td>
                      <td className="py-2 pr-3 text-xs">{e.severity}</td>
                      <td className="py-2">
                        <select
                          disabled={busy || !(NEXT[e.status] || []).length}
                          data-testid={`event-transition-select-${e.eventId}`}
                          className="px-2 py-1.5 border border-slate-200 rounded-md text-xs"
                          defaultValue=""
                          onChange={(ev) => transition(e.eventId, ev.target.value)}
                        >
                          <option value="">
                            {(NEXT[e.status] || []).length ? "Select…" : "Terminal state"}
                          </option>
                          {(NEXT[e.status] || []).map((n) => <option key={n} value={n}>{n}</option>)}
                        </select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>

          <Panel title="Audit trail" action={<ScrollText size={14} className="text-national" />}>
            <div className="max-h-[420px] overflow-y-auto" data-testid="admin-audit-feed">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-[10px] uppercase tracking-widest text-slate-500 border-b border-slate-200">
                    <th className="py-2 pr-2">When</th>
                    <th className="py-2 pr-2">Actor</th>
                    <th className="py-2 pr-2">Action</th>
                    <th className="py-2 pr-2">Object</th>
                    <th className="py-2">Change</th>
                  </tr>
                </thead>
                <tbody>
                  {audit.map((a) => (
                    <tr key={a.auditId} className="border-b border-slate-100">
                      <td className="py-1.5 pr-2 whitespace-nowrap text-slate-500">
                        {new Date(a.timestamp).toLocaleTimeString()}
                      </td>
                      <td className="py-1.5 pr-2">{a.userRole || "system"}</td>
                      <td className="py-1.5 pr-2 font-semibold text-national">{a.action}</td>
                      <td className="py-1.5 pr-2 font-mono">{a.objectType}/{a.objectId}</td>
                      <td className="py-1.5 text-slate-600">
                        {a.oldValue ? `${JSON.stringify(a.oldValue)} → ` : ""}
                        {a.newValue ? JSON.stringify(a.newValue) : ""}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>

        <div className="space-y-6">
          <Panel title="Repeated false SOS — review" action={<ShieldCheck size={14} className="text-national" />}>
            {!falseAlarms.length ? (
              <p className="text-sm text-slate-600">No false SOS reported.</p>
            ) : (
              <ul className="space-y-2 text-xs" data-testid="false-alarm-review">
                {falseAlarms.map((u) => (
                  <li key={u.userId} className="border border-slate-200 rounded-md p-2">
                    <span className="font-mono">{u.userId}</span> — {u.falseAlarmCount} false SOS
                    {u.flaggedForReview && (
                      <span className="ml-2 text-[10px] font-bold uppercase" style={{ color: "#C62828" }}>
                        flagged for review
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
            <p className="text-[11px] text-slate-500 mt-2">
              False SOS records are retained and reported — never deleted.
            </p>
          </Panel>

          <Panel title="Shelter & relief snapshot">
            <ul className="text-xs text-slate-700 space-y-1.5">
              <li>Capacity: <strong>{s.shelters?.capacity ?? "—"}</strong></li>
              <li>Occupancy: <strong>{s.shelters?.occupancy ?? "—"}</strong></li>
              <li>Derived available: <strong>{s.shelters?.available ?? "—"}</strong></li>
              <li>Full / over capacity: <strong>{s.shelters?.full ?? "—"}</strong></li>
              <li>Stale shelter records: <strong>{s.shelters?.stale ?? "—"}</strong></li>
              <li>Resource requests: <strong>{s.resourceRequests?.total ?? "—"}</strong>{" "}
                (discrepancy: {s.resourceRequests?.discrepancy ?? 0})</li>
            </ul>
            <p className="text-[11px] text-slate-500 mt-2">
              Shelter availability is always derived as capacity − occupancy, never stored.
            </p>
          </Panel>

          <Panel title="Advisory analytics tools">
            <p className="text-xs text-slate-600 mb-2">
              These modules produce advisory inputs into the disaster-event, SOS, shelter and relief
              workflows. They never declare or confirm an event.
            </p>
            <div className="grid grid-cols-2 gap-2">
              {ADVISORY_TOOLS.map(([to, label]) => (
                <Link key={to} to={to}
                      data-testid={`advisory-link-${to.replace(/\//g, "")}`}
                      className="text-[12px] font-semibold text-national border border-slate-200 rounded-md px-2 py-1.5 hover:border-national">
                  {label}
                </Link>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
