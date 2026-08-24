import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { BellRing, Radio, RefreshCw, Satellite } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Panel, SectionHeading, StatCard } from "@/components/common/GovUI";
import { SafetyNote, StalenessNote, StateBadge } from "@/components/setu/SetuBits";
import { apiError, setuApi } from "@/lib/setuApi";

const field = "w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:border-national";

const MODES = [
  ["NEW_EVENT", "New event from source"],
  ["UPDATE_SEVERITY", "Source escalates severity"],
  ["CONTRADICTORY_UPDATE", "Source contradicts itself"],
  ["ILLEGAL_JUMP", "Source proposes an illegal lifecycle jump"],
  ["SOURCE_SILENCE", "Source sends nothing"],
];

export default function IngestionConsole() {
  const [status, setStatus] = useState(null);
  const [events, setEvents] = useState([]);
  const [monitor, setMonitor] = useState(null);
  const [lastPoll, setLastPoll] = useState(null);
  const [mode, setMode] = useState("NEW_EVENT");
  const [eventId, setEventId] = useState("");
  const [dispatch, setDispatch] = useState({
    priority: 2, headline: "", eventId: "", roles: ["USER", "RESCUE_LEADER", "SHELTER_ADMIN", "NGO_ADMIN"],
    locationScoped: false,
  });

  const load = useCallback(async () => {
    try {
      const [s, e, m] = await Promise.all([
        setuApi.get("/ingestion/status"),
        setuApi.get("/events?include_closed=true"),
        setuApi.get("/notifications/monitor"),
      ]);
      setStatus(s.data);
      setEvents(e.data.events || []);
      setMonitor(m.data);
    } catch (err) {
      toast.error(apiError(err, "Could not load the ingestion console"));
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const simulate = async () => {
    try {
      const { data } = await setuApi.post("/ingestion/simulate", { mode, eventId: eventId || null });
      toast.success(`${data.queued} DEMO feed item(s) queued — now run the poll`);
      load();
    } catch (e) {
      toast.error(apiError(e, "Could not queue the feed item"));
    }
  };

  const poll = async () => {
    try {
      const { data } = await setuApi.post("/ingestion/poll");
      setLastPoll(data);
      const bits = [];
      if (data.created.length) bits.push(`${data.created.length} created`);
      if (data.updated.length) bits.push(`${data.updated.length} updated`);
      if (data.conflicts.length) bits.push(`${data.conflicts.length} held as conflicts`);
      toast[data.conflicts.length ? "warning" : "success"](
        bits.length ? bits.join(", ") : "Source sent nothing — recorded as a data gap");
      load();
    } catch (e) {
      toast.error(apiError(e, "Poll failed"));
    }
  };

  const send = async () => {
    if (!dispatch.headline) return toast.error("Write the headline");
    try {
      const { data } = await setuApi.post("/notifications/dispatch", {
        ...dispatch, priority: Number(dispatch.priority), eventId: dispatch.eventId || null,
      });
      toast.success(`${data.created} notification(s) created (${data.skippedOutsideArea} skipped outside area)`);
      load();
    } catch (e) {
      toast.error(apiError(e, "Dispatch failed"));
    }
  };

  const escalate = async () => {
    try {
      const { data } = await setuApi.post("/notifications/escalate-scan");
      toast[data.escalated ? "warning" : "success"](
        data.escalated ? `${data.escalated} unacknowledged message(s) escalated` : "Nothing needs escalation yet");
      load();
    } catch (e) {
      toast.error(apiError(e, "Escalation scan failed"));
    }
  };

  return (
    <div className="max-w-[1500px] mx-auto px-4 py-6 space-y-6">
      <SectionHeading
        eyebrow="Source ingestion & alerting"
        title="Disaster information pipeline"
        description="SETU consumes authoritative disaster information; it never invents it. Updates, contradictions and silence are all handled explicitly."
        action={
          <div className="flex gap-2">
            <Button onClick={poll} data-testid="ingestion-poll-button"
                    className="bg-national text-white gap-2 h-9 text-xs">
              <Satellite size={14} /> Poll source now
            </Button>
            <Button onClick={load} data-testid="ingestion-refresh"
                    className="bg-white border border-slate-300 text-slate-700 gap-2 h-9 text-xs">
              <RefreshCw size={14} /> Refresh
            </Button>
          </div>
        }
      />

      <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
        <StatCard label="Polls" value={status?.polls ?? "—"} />
        <StatCard label="Events created" value={status?.eventsCreated ?? "—"} accent="green" />
        <StatCard label="Events updated" value={status?.eventsUpdated ?? "—"} accent="saffron" />
        <StatCard label="Conflicts held" value={status?.conflicts ?? "—"} accent="red" />
        <StatCard label="Pending feed items" value={status?.pendingFeedItems ?? "—"} />
        <StatCard label="Source health" value={status?.sourceHealth ?? "—"} />
      </div>

      {status?.silenceWarning && <SafetyNote>{status.silenceWarning}</SafetyNote>}

      <div className="grid xl:grid-cols-3 gap-6">
        <Panel title="Simulate an incoming feed (DEMO)">
          <div className="space-y-2">
            <select className={field} value={mode} data-testid="simulate-mode"
                    onChange={(e) => setMode(e.target.value)}>
              {MODES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
            <select className={field} value={eventId} data-testid="simulate-event"
                    onChange={(e) => setEventId(e.target.value)}>
              <option value="">Auto-select event</option>
              {events.map((e) => <option key={e.eventId} value={e.eventId}>{e.title}</option>)}
            </select>
            <Button onClick={simulate} data-testid="simulate-button"
                    className="w-full bg-national text-white">Queue feed item</Button>
            <p className="text-[11px] text-slate-500">
              DEMO ONLY — this stands in for the authorized NDEM integration so the ingestion rules
              can be exercised end to end.
            </p>
          </div>
          {lastPoll && (
            <div className="mt-3 text-[11px] text-slate-700 border-t border-slate-200 pt-2"
                 data-testid="last-poll-result">
              <div>Feed items: {lastPoll.feedItems}</div>
              <div>Created: {lastPoll.created.join(", ") || "none"}</div>
              <div>Updated: {lastPoll.updated.join(", ") || "none"}</div>
              <div>Conflicts held: {lastPoll.conflicts.join(", ") || "none"}</div>
              <div className="text-slate-500 mt-1">{lastPoll.note}</div>
            </div>
          )}
        </Panel>

        <Panel title="Events from the source">
          <div className="space-y-2 max-h-[420px] overflow-y-auto" data-testid="ingested-events">
            {events.map((e) => (
              <div key={e.eventId} className="border border-slate-200 rounded-md p-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[12px] font-semibold text-national">{e.title}</span>
                  <StateBadge status={e.status} />
                </div>
                <div className="text-[11px] text-slate-600 mt-1">
                  {e.infoTier?.replace(/_/g, " ")} • {e.severity} • v{e.version}
                  {e.history?.length ? ` • ${e.history.length} previous version(s)` : ""}
                </div>
                <div className="text-[10px] font-mono text-slate-500">{e.sourceReference}</div>
                <StalenessNote notice={e.stalenessNotice} stale={e.stale} />
                {e.experimental && (
                  <div className="text-[10px] font-bold uppercase text-amber-700">{e.experimentalNotice}</div>
                )}
              </div>
            ))}
          </div>
        </Panel>

        <div className="space-y-6">
          <Panel title="Dispatch a notification" action={<Radio size={14} className="text-national" />}>
            <div className="space-y-2">
              <select className={field} value={dispatch.priority} data-testid="dispatch-priority"
                      onChange={(e) => setDispatch({ ...dispatch, priority: e.target.value })}>
                <option value={1}>P1 — life safety</option>
                <option value={2}>P2 — operational</option>
                <option value={3}>P3 — informational</option>
              </select>
              <select className={field} value={dispatch.eventId} data-testid="dispatch-event"
                      onChange={(e) => setDispatch({ ...dispatch, eventId: e.target.value })}>
                <option value="">No linked event</option>
                {events.map((e) => <option key={e.eventId} value={e.eventId}>{e.title}</option>)}
              </select>
              <input className={field} placeholder="Headline (role-specific text is added per role)"
                     data-testid="dispatch-headline" value={dispatch.headline}
                     onChange={(e) => setDispatch({ ...dispatch, headline: e.target.value })} />
              <label className="flex items-center gap-2 text-xs text-slate-600">
                <input type="checkbox" checked={dispatch.locationScoped}
                       onChange={(e) => setDispatch({ ...dispatch, locationScoped: e.target.checked })} />
                Only citizens inside or near the affected area
              </label>
              <Button onClick={send} data-testid="dispatch-button"
                      className="w-full bg-national text-white">Dispatch</Button>
            </div>
          </Panel>

          <Panel title="Delivery & acknowledgement" action={<BellRing size={14} className="text-national" />}>
            {monitor && (
              <ul className="text-xs text-slate-700 space-y-1" data-testid="notification-monitor">
                <li>Total: <strong>{monitor.total}</strong></li>
                <li>Undelivered: <strong>{monitor.undelivered}</strong></li>
                <li>Unacknowledged: <strong>{monitor.unacknowledged}</strong></li>
                <li>P1 unacknowledged: <strong>{monitor.p1Unacknowledged}</strong></li>
                <li>Escalated: <strong>{monitor.escalated}</strong></li>
              </ul>
            )}
            <Button onClick={escalate} data-testid="escalate-scan-button"
                    className="mt-3 w-full bg-white border border-slate-300 text-slate-700 text-xs">
              Run escalation scan
            </Button>
            <p className="text-[11px] text-slate-500 mt-2">
              Dispatched is not the same as seen. Unacknowledged life-safety messages escalate to the
              next level instead of being dropped.
            </p>
          </Panel>
        </div>
      </div>
    </div>
  );
}
