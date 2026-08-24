import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { FileText, Globe2, RefreshCw, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Panel, SectionHeading, StatCard } from "@/components/common/GovUI";
import { SafetyNote } from "@/components/setu/SetuBits";
import { apiError, setuApi } from "@/lib/setuApi";

export default function SituationReport() {
  const [report, setReport] = useState(null);
  const [cross, setCross] = useState(null);
  const [decisions, setDecisions] = useState([]);
  const [requests, setRequests] = useState([]);
  const [shelters, setShelters] = useState([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const [r, c, d, q, s] = await Promise.all([
        setuApi.get("/authority/situation-report"),
        setuApi.get("/authority/cross-district"),
        setuApi.get("/authority/decision-log"),
        setuApi.get("/relief/requests"),
        setuApi.get("/shelters/list"),
      ]);
      setReport(r.data);
      setCross(c.data);
      setDecisions(d.data.decisions || []);
      setRequests(q.data.requests || []);
      setShelters(s.data.shelters || []);
    } catch (e) {
      toast.error(apiError(e, "Could not build the situation report"));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const reallocate = async () => {
    const movable = requests.filter((r) => (r.allocatedQuantity || 0) > (r.sentQuantity || 0));
    if (!movable.length) return toast.error("No unshipped allocation is available to reallocate");
    const from = window.prompt(
      `Reallocate from which request?\n${movable.map((r) => `${r.requestId} (${r.category}, ${r.allocatedQuantity - r.sentQuantity} unshipped)`).join("\n")}`,
      movable[0].requestId);
    if (!from) return;
    const to = window.prompt(`To which shelter?\n${shelters.map((s) => `${s.shelterId} — ${s.name}`).join("\n")}`);
    if (!to) return;
    const qty = window.prompt("Quantity to move");
    if (!qty) return;
    const reason = window.prompt("Reason for the reallocation (recorded)");
    if (!reason) return;
    try {
      const { data } = await setuApi.post("/authority/reallocate", {
        fromRequestId: from, toShelterId: to, quantity: Number(qty), reason,
      });
      toast.success(`Created ${data.newRequest.requestId} — ${data.note}`);
      load();
    } catch (e) {
      const d = e?.response?.data?.detail;
      toast.error(typeof d === "object" ? d.message : apiError(e, "Reallocation failed"));
    }
  };

  const escalate = async () => {
    const objectType = window.prompt("Object type (SOS / SHELTER / DISASTER_EVENT)", "DISASTER_EVENT");
    if (!objectType) return;
    const objectId = window.prompt("Object id");
    if (!objectId) return;
    const level = window.prompt("Level (DISTRICT / STATE / NATIONAL)", "STATE");
    if (!level) return;
    const reason = window.prompt("Reason");
    if (!reason) return;
    try {
      const { data } = await setuApi.post("/authority/escalate", { objectType, objectId, level, reason });
      toast.success(data.note);
      load();
    } catch (e) {
      toast.error(apiError(e, "Escalation failed"));
    }
  };

  const r = report || {};

  return (
    <div className="max-w-[1500px] mx-auto px-4 py-6 space-y-6">
      <SectionHeading
        eyebrow="Authority reporting"
        title="Situation report"
        description="What is known, and — just as importantly — what is not known. Missing data is printed, never rounded to zero."
        action={
          <div className="flex gap-2">
            <Button onClick={reallocate} data-testid="reallocate-button"
                    className="bg-white border border-slate-300 text-slate-700 gap-2 h-9 text-xs">
              Reallocate relief
            </Button>
            <Button onClick={escalate} data-testid="escalate-button"
                    className="text-white gap-2 h-9 text-xs" style={{ backgroundColor: "#C62828" }}>
              <ShieldAlert size={14} /> Escalate
            </Button>
            <Button onClick={load} disabled={busy} data-testid="sitrep-refresh"
                    className="bg-national text-white gap-2 h-9 text-xs">
              <RefreshCw size={14} /> Regenerate
            </Button>
          </div>
        }
      />

      {report && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
            <StatCard label="Active SOS" value={r.rescue.sosActive} accent="saffron" />
            <StatCard label="P1 critical" value={r.rescue.byPriority.P1} accent="red" />
            <StatCard label="People rescued" value={r.rescue.peopleRescued} accent="green" />
            <StatCard label="Open missing entries" value={r.search.openMissingEntries} accent="red" />
            <StatCard label="Shelter places free" value={r.shelters.available} accent="green" />
            <StatCard label="Relief discrepancies" value={r.relief.openDiscrepancies} accent="red" />
          </div>

          <Panel title="Data gaps — what SETU does not know" action={<FileText size={14} className="text-national" />}>
            <ul className="list-disc ml-5 text-sm text-slate-700 space-y-1" data-testid="sitrep-data-gaps">
              {r.dataGaps.map((g) => <li key={g}>{g}</li>)}
              {!r.dataGaps.length && <li>No data gaps detected in this scope.</li>}
            </ul>
            <SafetyNote>{r.integrityNote}</SafetyNote>
          </Panel>

          <div className="grid xl:grid-cols-3 gap-6">
            <Panel title="Rescue">
              <ul className="text-xs text-slate-700 space-y-1" data-testid="sitrep-rescue">
                <li>SOS total: <strong>{r.rescue.sosTotal}</strong></li>
                <li>Active: <strong>{r.rescue.sosActive}</strong> (unassigned {r.rescue.unassigned})</li>
                <li>Completed: <strong>{r.rescue.sosCompleted}</strong></li>
                <li>People rescued: <strong>{r.rescue.peopleRescued}</strong></li>
                <li>Fatalities reported: <strong>{r.rescue.fatalitiesReported}</strong></li>
                <li>Cancelled by citizens: <strong>{r.rescue.cancelledByUser}</strong></li>
                <li>False alarms recorded: <strong>{r.rescue.falseAlarms}</strong></li>
                <li>Duplicate presses merged: <strong>{r.rescue.duplicatesMerged}</strong></li>
              </ul>
            </Panel>
            <Panel title="Search & verification">
              <ul className="text-xs text-slate-700 space-y-1" data-testid="sitrep-search">
                <li>Search operations: <strong>{r.search.operations}</strong></li>
                <li>In progress: <strong>{r.search.inProgress}</strong></li>
                <li>Closed without locating: <strong>{r.search.closedNotFound}</strong></li>
                <li>Open missing entries: <strong>{r.search.openMissingEntries}</strong></li>
                <li>People found without an SOS: <strong>{r.search.unknownPersonsFoundInField}</strong></li>
              </ul>
            </Panel>
            <Panel title="Shelters & relief">
              <ul className="text-xs text-slate-700 space-y-1" data-testid="sitrep-shelters">
                <li>Capacity: <strong>{r.shelters.capacity}</strong></li>
                <li>Occupancy: <strong>{r.shelters.occupancy}</strong></li>
                <li>Available (derived): <strong>{r.shelters.available}</strong></li>
                <li>Full / over capacity: <strong>{r.shelters.full}</strong></li>
                <li>Closed: <strong>{r.shelters.closed}</strong></li>
                <li>Stale records: <strong>{r.shelters.staleRecords}</strong></li>
                <li>Relief requests: <strong>{r.relief.requests}</strong></li>
              </ul>
            </Panel>
          </div>
        </>
      )}

      <div className="grid xl:grid-cols-2 gap-6">
        <Panel title="Cross-district coordination" action={<Globe2 size={14} className="text-national" />}>
          {cross && (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-xs" data-testid="cross-district-table">
                  <thead>
                    <tr className="text-left text-[10px] uppercase tracking-widest text-slate-500 border-b border-slate-200">
                      <th className="py-2 pr-2">Region</th><th className="py-2 pr-2">Active SOS</th>
                      <th className="py-2 pr-2">P1</th><th className="py-2 pr-2">Teams free</th>
                      <th className="py-2 pr-2">Shelter free</th><th className="py-2">Open needs</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cross.regions.map((g) => (
                      <tr key={g.region} className="border-b border-slate-100">
                        <td className="py-2 pr-2 font-semibold text-national">{g.region}</td>
                        <td className="py-2 pr-2">{g.activeSos}</td>
                        <td className="py-2 pr-2">{g.p1}</td>
                        <td className="py-2 pr-2">{g.teamsAvailable}/{g.teamsTotal}</td>
                        <td className="py-2 pr-2">{g.shelterAvailable}</td>
                        <td className="py-2">{g.openRequirements}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!!cross.mutualAidSuggestions.length && (
                <div className="mt-3 space-y-2" data-testid="mutual-aid">
                  {cross.mutualAidSuggestions.map((s, i) => (
                    <div key={i} className="border border-slate-200 rounded-md p-2 text-[11px] text-slate-700">
                      <strong>{s.type.replace(/_/g, " ")}:</strong> {s.detail}
                      <div className="text-[10px] text-slate-500 mt-0.5">
                        Advisory — requires an authority decision before any movement.
                      </div>
                    </div>
                  ))}
                </div>
              )}
              <p className="text-[11px] text-slate-500 mt-2">{cross.note}</p>
            </>
          )}
        </Panel>

        <Panel title="Decision log — human decisions only">
          <div className="max-h-[420px] overflow-y-auto" data-testid="decision-log">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-[10px] uppercase tracking-widest text-slate-500 border-b border-slate-200">
                  <th className="py-2 pr-2">When</th><th className="py-2 pr-2">Role</th>
                  <th className="py-2 pr-2">Decision</th><th className="py-2">Reason / object</th>
                </tr>
              </thead>
              <tbody>
                {decisions.map((d) => (
                  <tr key={d.auditId} className="border-b border-slate-100">
                    <td className="py-1.5 pr-2 text-slate-500 whitespace-nowrap">
                      {new Date(d.timestamp).toLocaleTimeString()}
                    </td>
                    <td className="py-1.5 pr-2">{d.userRole || "system"}</td>
                    <td className="py-1.5 pr-2 font-semibold text-national">{d.action}</td>
                    <td className="py-1.5 text-slate-600">
                      {d.objectType}/{d.objectId}{d.note ? ` — ${d.note}` : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>
    </div>
  );
}
