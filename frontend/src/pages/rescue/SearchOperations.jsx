import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Grid3x3, MapPinned, RefreshCw, UserSearch } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Panel, SectionHeading, StatCard } from "@/components/common/GovUI";
import { SafetyNote, StateBadge } from "@/components/setu/SetuBits";
import { apiError, setuApi } from "@/lib/setuApi";
import { acquireLocation } from "@/lib/offlineQueue";
import { useAuth } from "@/context/AuthContext";

const field = "w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:border-national";

const CELL_COLOR = {
  NOT_SEARCHED: "bg-slate-100 text-slate-400 border-slate-200",
  NOTHING_FOUND: "bg-slate-300 text-slate-700 border-slate-400",
  PEOPLE_FOUND: "bg-green-600 text-white border-green-700",
  SIGNS_FOUND: "bg-amber-400 text-slate-900 border-amber-500",
  INACCESSIBLE: "bg-red-600 text-white border-red-700",
};

export default function SearchOperations() {
  const { user } = useAuth();
  const [ops, setOps] = useState([]);
  const [active, setActive] = useState(null);
  const [summary, setSummary] = useState(null);
  const [register, setRegister] = useState([]);
  const [incidents, setIncidents] = useState([]);
  const [result, setResult] = useState("NOTHING_FOUND");
  const [people, setPeople] = useState(0);
  const [inc, setInc] = useState({ unknownPersons: 1, condition: "STABLE", transportRequired: false, notes: "" });

  const isLeader = ["RESCUE_LEADER", "AUTHORITY", "SUPER_ADMIN"].includes(user?.role);

  const load = useCallback(async () => {
    try {
      const [o, r, i] = await Promise.all([
        setuApi.get("/search/operations"),
        setuApi.get("/search/missing-register"),
        setuApi.get("/search/incidents"),
      ]);
      setOps(o.data.operations || []);
      setRegister(r.data.entries || []);
      setIncidents(i.data.incidents || []);
      if (isLeader) {
        const s = await setuApi.get("/search/summary");
        setSummary(s.data);
      }
      if (active) {
        const fresh = (o.data.operations || []).find((x) => x.searchId === active.searchId);
        if (fresh) setActive(fresh);
      }
    } catch (e) {
      toast.error(apiError(e, "Could not load search operations"));
    }
  }, [isLeader]);

  useEffect(() => { load(); }, [load]);

  const startAreaSearch = async () => {
    const desc = window.prompt("Describe the area to search");
    if (!desc) return;
    const loc = await acquireLocation();
    if (!loc) return toast.error("Location unavailable — cannot anchor the search grid");
    try {
      const { data } = await setuApi.post("/search/operations", {
        centre: { latitude: loc.latitude, longitude: loc.longitude, accuracy: loc.accuracy,
                  source: loc.source, timestamp: loc.timestamp },
        areaDescription: desc, radiusMetres: 500, cellMetres: 250, reason: "AREA_SWEEP",
      });
      setActive(data);
      toast.success(`Search opened with ${data.coverage.totalCells} grid cells`);
      load();
    } catch (e) {
      toast.error(apiError(e, "Could not open the search"));
    }
  };

  const markCell = async (cellId) => {
    try {
      const { data } = await setuApi.post(`/search/operations/${active.searchId}/cells/${cellId}`, {
        result, peopleFound: result === "PEOPLE_FOUND" ? Number(people) || 1 : 0,
      });
      setActive(data);
      load();
    } catch (e) {
      toast.error(apiError(e, "Could not record the cell"));
    }
  };

  const closeSearch = async (outcome) => {
    const missing = outcome === "NOT_FOUND"
      ? Number(window.prompt("How many people remain unaccounted for?", "1")) : 0;
    const obs = window.prompt("Observations (recorded in the audit trail)") || "";
    try {
      const { data } = await setuApi.post(`/search/operations/${active.searchId}/close`, {
        outcome, peopleFound: active.peopleFound || 0, peopleMissing: missing || 0, observations: obs,
      });
      setActive(data);
      toast[data.missingRegisterEntry ? "warning" : "success"](data.note);
      load();
    } catch (e) {
      toast.error(apiError(e, "Could not close the search"));
    }
  };

  const recordIncident = async () => {
    const loc = await acquireLocation();
    if (!loc) return toast.error("Location unavailable");
    try {
      const { data } = await setuApi.post("/search/incidents", {
        location: { latitude: loc.latitude, longitude: loc.longitude, accuracy: loc.accuracy,
                    source: loc.source, timestamp: loc.timestamp },
        unknownPersons: Number(inc.unknownPersons) || 1, condition: inc.condition,
        transportRequired: inc.transportRequired, notes: inc.notes || null,
      });
      toast.success(data.note);
      setInc({ unknownPersons: 1, condition: "STABLE", transportRequired: false, notes: "" });
      load();
    } catch (e) {
      toast.error(apiError(e, "Could not record the incident"));
    }
  };

  const resolveEntry = async (entryId) => {
    const resolution = window.prompt(
      "Resolution: LOCATED_SAFE | LOCATED_DECEASED | TRANSFERRED | CLOSED_UNRESOLVED", "LOCATED_SAFE");
    if (!resolution) return;
    const evidence = window.prompt("Evidence for this resolution (required)");
    if (!evidence) return;
    try {
      await setuApi.post(`/search/missing-register/${entryId}/resolve`, { resolution, evidence });
      toast.success("Register entry resolved with recorded evidence");
      load();
    } catch (e) {
      toast.error(apiError(e, "Could not resolve the entry"));
    }
  };

  return (
    <div className="max-w-[1500px] mx-auto px-4 py-6 space-y-6">
      <SectionHeading
        eyebrow="Search & verification"
        title="Search operations"
        description="Systematic grid search for people who could not be located. 'Not found' is never recorded as 'safe'."
        action={
          <div className="flex gap-2">
            <Button onClick={startAreaSearch} data-testid="start-search-button"
                    className="bg-national text-white gap-2 h-9 text-xs">
              <Grid3x3 size={14} /> Start area search
            </Button>
            <Button onClick={load} data-testid="search-refresh"
                    className="bg-white border border-slate-300 text-slate-700 gap-2 h-9 text-xs">
              <RefreshCw size={14} /> Refresh
            </Button>
          </div>
        }
      />

      {summary && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          <StatCard label="Searches in progress" value={summary.operations.inProgress} accent="saffron" />
          <StatCard label="Closed — found" value={summary.operations.closedFound} accent="green" />
          <StatCard label="Closed — not found" value={summary.operations.closedNotFound} accent="red" />
          <StatCard label="Open missing entries" value={summary.openMissingEntries} accent="red" />
          <StatCard label="People found without SOS" value={summary.unknownPersonsRecorded} accent="national" />
        </div>
      )}

      <div className="grid xl:grid-cols-3 gap-6">
        <Panel title={`Operations (${ops.length})`}>
          <div className="space-y-2 max-h-[420px] overflow-y-auto" data-testid="search-operations-list">
            {ops.map((o) => (
              <button key={o.searchId} onClick={() => setActive(o)}
                      data-testid={`search-op-${o.searchId}`}
                      className={`w-full text-left border rounded-md p-2 ${
                        active?.searchId === o.searchId ? "border-national bg-slate-50" : "border-slate-200"}`}>
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-[11px]">{o.searchId}</span>
                  <StateBadge status={o.status} />
                </div>
                <div className="text-[11px] text-slate-600 mt-1">{o.areaDescription}</div>
                <div className="text-[11px] text-slate-500">
                  {o.coverage.percent}% coverage • {o.peopleFound} found • {o.peopleMissing} missing
                  {o.sosId ? ` • ${o.sosId}` : ""}
                </div>
              </button>
            ))}
            {!ops.length && <p className="text-sm text-slate-600">No search operations yet.</p>}
          </div>
        </Panel>

        <Panel title={active ? `Grid — ${active.searchId}` : "Grid"}
               action={<MapPinned size={14} className="text-national" />}>
          {!active ? (
            <p className="text-sm text-slate-600">Select a search operation to record coverage.</p>
          ) : (
            <div className="space-y-3" data-testid="search-grid">
              <SafetyNote>{active.coverageNote}</SafetyNote>
              <div className="flex flex-wrap items-center gap-2">
                <select className="px-2 py-1.5 border border-slate-200 rounded-md text-xs"
                        value={result} data-testid="cell-result-select"
                        onChange={(e) => setResult(e.target.value)}>
                  {Object.keys(CELL_COLOR).filter((c) => c !== "NOT_SEARCHED").map((c) => (
                    <option key={c} value={c}>{c.replace(/_/g, " ")}</option>
                  ))}
                </select>
                {result === "PEOPLE_FOUND" && (
                  <input type="number" min={1} className="w-24 px-2 py-1.5 border border-slate-200 rounded-md text-xs"
                         value={people} data-testid="cell-people-input"
                         onChange={(e) => setPeople(e.target.value)} placeholder="people" />
                )}
                <span className="text-[11px] text-slate-500">then tap a cell</span>
              </div>
              <div className="grid gap-1"
                   style={{ gridTemplateColumns: `repeat(${Math.sqrt(active.gridCells.length) || 3}, minmax(0, 1fr))` }}>
                {active.gridCells.map((c) => (
                  <button key={c.cellId} onClick={() => markCell(c.cellId)}
                          disabled={active.status !== "IN_PROGRESS"}
                          data-testid={`cell-${c.cellId}`}
                          className={`aspect-square text-[9px] font-bold border rounded ${CELL_COLOR[c.result]}`}
                          title={`${c.cellId} — ${c.result}${c.peopleFound ? ` (${c.peopleFound})` : ""}`}>
                    {c.result === "PEOPLE_FOUND" ? c.peopleFound : c.result === "NOT_SEARCHED" ? "?" : "✓"}
                  </button>
                ))}
              </div>
              {active.status === "IN_PROGRESS" && (
                <div className="flex flex-wrap gap-2">
                  <Button onClick={() => closeSearch("FOUND")} data-testid="close-search-found"
                          className="text-white text-xs" style={{ backgroundColor: "#138808" }}>
                    Close — people located
                  </Button>
                  <Button onClick={() => closeSearch("NOT_FOUND")} data-testid="close-search-not-found"
                          className="text-white text-xs" style={{ backgroundColor: "#C62828" }}>
                    Close — not found
                  </Button>
                  <Button onClick={() => closeSearch("SUSPENDED")} data-testid="close-search-suspend"
                          className="bg-white border border-slate-300 text-slate-700 text-xs">
                    Suspend (unsafe conditions)
                  </Button>
                </div>
              )}
            </div>
          )}
        </Panel>

        <div className="space-y-6">
          <Panel title="People found without an SOS" action={<UserSearch size={14} className="text-national" />}>
            <div className="space-y-2">
              <input type="number" min={1} className={field} data-testid="incident-count"
                     value={inc.unknownPersons}
                     onChange={(e) => setInc({ ...inc, unknownPersons: e.target.value })} />
              <select className={field} value={inc.condition} data-testid="incident-condition"
                      onChange={(e) => setInc({ ...inc, condition: e.target.value })}>
                {["STABLE", "INJURED", "CRITICAL", "DECEASED", "UNKNOWN"].map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
              <label className="flex items-center gap-2 text-xs text-slate-600">
                <input type="checkbox" checked={inc.transportRequired}
                       onChange={(e) => setInc({ ...inc, transportRequired: e.target.checked })} />
                Transport required
              </label>
              <input className={field} placeholder="Notes" value={inc.notes}
                     onChange={(e) => setInc({ ...inc, notes: e.target.value })} />
              <Button onClick={recordIncident} data-testid="record-incident-button"
                      className="w-full bg-national text-white">Record people found</Button>
              <p className="text-[11px] text-slate-500">
                People who never reached the app still count in SETU&apos;s rescue numbers.
              </p>
            </div>
            {!!incidents.length && (
              <ul className="mt-3 space-y-1 text-[11px] text-slate-700 max-h-40 overflow-y-auto">
                {incidents.map((i) => (
                  <li key={i.incidentId} className="border border-slate-200 rounded p-1.5">
                    {i.unknownPersons} person(s) • {i.condition}
                    {i.transportRequired ? " • transport required" : ""}
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel title="Missing-person register">
            {!register.length ? (
              <p className="text-sm text-slate-600">No open entries.</p>
            ) : (
              <ul className="space-y-2" data-testid="missing-register">
                {register.map((e) => (
                  <li key={e.entryId} className="border border-slate-200 rounded-md p-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-[11px]">{e.entryId}</span>
                      <StateBadge status={e.status} />
                    </div>
                    <div className="text-[11px] text-slate-600 mt-1">
                      {e.peopleMissing} unaccounted • {e.sosId || "no linked SOS"}
                    </div>
                    <div className="text-[11px] text-slate-500">{e.note}</div>
                    {isLeader && e.status === "OPEN" && (
                      <Button onClick={() => resolveEntry(e.entryId)}
                              data-testid={`resolve-entry-${e.entryId}`}
                              className="mt-2 h-7 text-[11px] bg-national text-white">
                        Resolve with evidence
                      </Button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
