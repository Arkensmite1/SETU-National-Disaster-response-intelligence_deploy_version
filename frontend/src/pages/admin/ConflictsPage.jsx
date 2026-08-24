import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, RefreshCw, Scale } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Panel, SectionHeading, StatCard } from "@/components/common/GovUI";
import { SafetyNote, StateBadge } from "@/components/setu/SetuBits";
import { apiError, setuApi } from "@/lib/setuApi";

export default function ConflictsPage() {
  const [data, setData] = useState(null);
  const [quality, setQuality] = useState(null);

  const load = useCallback(async () => {
    try {
      const [c, q] = await Promise.all([
        setuApi.get("/integrity/conflicts"),
        setuApi.get("/integrity/data-quality"),
      ]);
      setData(c.data);
      setQuality(q.data);
    } catch (e) {
      toast.error(apiError(e, "Could not load the integrity board"));
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const resolve = async (c) => {
    const options = (c.values || []).map((v, i) => `${i + 1}: ${JSON.stringify(v.value)}`).join("\n");
    const pick = window.prompt(`Which value is correct?\n${options}\n\nEnter the number:`);
    if (!pick) return;
    const chosen = (c.values || [])[Number(pick) - 1];
    if (!chosen) return toast.error("Invalid choice");
    const reason = window.prompt("Reason for this decision (recorded in the audit log)");
    if (!reason) return;
    try {
      const { data: res } = await setuApi.post(`/integrity/conflicts/${c.conflictId}/resolve`, {
        chosenValue: chosen.value, reason, applyToRecord: true,
      });
      toast.success(res.note);
      load();
    } catch (e) {
      toast.error(apiError(e, "Could not resolve"));
    }
  };

  return (
    <div className="max-w-[1400px] mx-auto px-4 py-6 space-y-6">
      <SectionHeading
        eyebrow="Data integrity"
        title="Conflicts and data quality"
        description="Contradictory reports are kept side by side with reporter, time and confidence. SETU never picks a winner automatically."
        action={
          <Button onClick={load} data-testid="conflicts-refresh" className="bg-national text-white gap-2 h-9 text-xs">
            <RefreshCw size={14} /> Refresh
          </Button>
        }
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard label="Open conflicts" value={data?.conflicts?.length ?? "—"} accent="red" />
        <StatCard label="Shelter occupancy conflicts" value={data?.shelterOccupancyConflicts?.length ?? "—"} accent="saffron" />
        <StatCard label="Resource discrepancies" value={data?.resourceDiscrepancies?.length ?? "—"} accent="red" />
        <StatCard label="Stale shelter records" value={quality?.staleShelterRecords?.length ?? "—"} />
      </div>

      <Panel title="Conflicting reports" action={<Scale size={14} className="text-national" />}>
        {!data?.conflicts?.length ? (
          <p className="text-sm text-slate-600">No open conflicts.</p>
        ) : (
          <div className="space-y-3" data-testid="conflicts-list">
            {data.conflicts.map((c) => (
              <div key={c.conflictId} className="border border-slate-200 rounded-md p-3"
                   data-testid={`conflict-${c.conflictId}`}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <span className="font-mono text-[11px] text-slate-500">{c.conflictId}</span>
                    <div className="text-sm font-semibold text-national">
                      {c.objectType} {c.objectId} — field “{c.field}”
                    </div>
                  </div>
                  <Button onClick={() => resolve(c)} data-testid={`resolve-conflict-${c.conflictId}`}
                          className="h-8 text-xs bg-national text-white">Decide</Button>
                </div>
                <table className="w-full text-xs mt-2">
                  <thead>
                    <tr className="text-left text-[10px] uppercase tracking-widest text-slate-500">
                      <th className="py-1">Reported value</th><th className="py-1">Reporter</th>
                      <th className="py-1">Role</th><th className="py-1">Confidence</th><th className="py-1">When</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(c.values || []).map((v, i) => (
                      <tr key={i} className="border-t border-slate-100">
                        <td className="py-1 font-semibold">{JSON.stringify(v.value)}</td>
                        <td className="py-1">{v.reportedBy}</td>
                        <td className="py-1">{v.reporterRole || v.label || "—"}</td>
                        <td className="py-1">{v.confidence || "—"}</td>
                        <td className="py-1 text-slate-500">
                          {v.at ? new Date(v.at).toLocaleTimeString() : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {c.note && <p className="text-[11px] text-slate-500 mt-2">{c.note}</p>}
              </div>
            ))}
          </div>
        )}
      </Panel>

      <div className="grid lg:grid-cols-2 gap-6">
        <Panel title="Resource discrepancies">
          {!data?.resourceDiscrepancies?.length ? (
            <p className="text-sm text-slate-600">No open discrepancies.</p>
          ) : (
            <div className="space-y-2" data-testid="discrepancy-list">
              {data.resourceDiscrepancies.map((r) => (
                <div key={r.requestId} className="border border-slate-200 rounded-md p-2">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[11px]">{r.requestId}</span>
                    <StateBadge status={r.status} />
                  </div>
                  <div className="text-[11px] text-slate-600 mt-1">
                    {r.category}: sent {r.discrepancy?.sent} • received {r.discrepancy?.received} •
                    difference {r.discrepancy?.difference}
                  </div>
                  <Button className="mt-2 h-7 text-[11px] bg-national text-white"
                          data-testid={`resolve-discrepancy-${r.requestId}`}
                          onClick={async () => {
                            const q = window.prompt("Final agreed quantity", r.discrepancy?.received);
                            if (q === null) return;
                            const reason = window.prompt("Resolution note");
                            if (!reason) return;
                            try {
                              await setuApi.post(`/relief/requests/${r.requestId}/resolve-discrepancy`,
                                                 { finalQuantity: Number(q), resolution: reason });
                              toast.success("Resolved — both original figures retained");
                              load();
                            } catch (e) { toast.error(apiError(e, "Could not resolve")); }
                          }}>
                    Resolve
                  </Button>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="What SETU does not know" action={<AlertTriangle size={14} style={{ color: "#EF6C00" }} />}>
          {quality && (
            <div className="space-y-3 text-xs text-slate-700" data-testid="data-quality-panel">
              <ul className="list-disc ml-5 space-y-1">
                {quality.knownUnknowns.map((k) => <li key={k}>{k}</li>)}
              </ul>
              {!!quality.staleEvents?.length && (
                <div>
                  <strong>Stale events:</strong>
                  <ul className="list-disc ml-5">
                    {quality.staleEvents.map((e) => <li key={e.eventId}>{e.title} — {e.notice}</li>)}
                  </ul>
                </div>
              )}
              {!!quality.activeSosWithApproximateLocation?.length && (
                <div>
                  <strong>Active SOS with approximate location:</strong>
                  <ul className="list-disc ml-5">
                    {quality.activeSosWithApproximateLocation.map((s) => (
                      <li key={s.sosId}>{s.sosId} — {s.source} (±{s.accuracy ?? "unknown"} m)</li>
                    ))}
                  </ul>
                </div>
              )}
              {!!quality.teamsWithoutLocation?.length && (
                <div>
                  <strong>Teams without a reported location:</strong>{" "}
                  {quality.teamsWithoutLocation.map((t) => t.name).join(", ")}
                </div>
              )}
            </div>
          )}
          <SafetyNote>
            Absence of data is reported as unknown. It is never displayed as safety or as zero need.
          </SafetyNote>
        </Panel>
      </div>
    </div>
  );
}
