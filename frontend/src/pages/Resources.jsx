import React, { useEffect, useState } from "react";
import { api, endpoints } from "@/lib/api";
import { SectionHeading, Panel, StatusBadge } from "@/components/common/GovUI";
import { Button } from "@/components/ui/button";
import { Loader2, Sparkles, Package, Ambulance, LifeBuoy, Utensils, Stethoscope, PlaneTakeoff, Bird } from "lucide-react";

const ICONS = { boats: LifeBuoy, ambulances: Ambulance, food_kits: Utensils, blankets: Package, medical_teams: Stethoscope, helicopters: PlaneTakeoff, drones: Bird };

export default function Resources() {
  const [data, setData] = useState({ inventory: {}, allocations: [] });
  const [suggestion, setSuggestion] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.get(endpoints.resources).then(r => setData(r.data)).catch(() => {}); }, []);

  const optimise = async () => {
    setBusy(true); setSuggestion("");
    try { const r = await api.post(endpoints.optimize); setSuggestion(r.data.suggestion); }
    finally { setBusy(false); }
  };

  return (
    <div className="max-w-[1600px] mx-auto px-4 py-6">
      <SectionHeading eyebrow="Module 03" title="AI Resource Allocation" description="Live inventory of boats, ambulances, medical teams and relief kits — with an AI optimiser that reasons over demand, priority and geography." />

      <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        {Object.entries(data.inventory).map(([k, v]) => {
          const Icon = ICONS[k] || Package;
          const pct = v.total ? (v.deployed / v.total) * 100 : 0;
          return (
            <div key={k} className="bg-white border border-slate-200 rounded-md p-4" data-testid={`inv-${k}`}>
              <div className="flex items-center gap-2">
                <Icon size={16} className="text-national" />
                <div className="text-[11px] font-bold uppercase tracking-widest text-slate-500 capitalize">{k.replace("_", " ")}</div>
              </div>
              <div className="text-3xl font-heading font-extrabold text-national mt-1">{v.total}</div>
              <div className="text-xs text-slate-500">Deployed {v.deployed} • Free {v.available}</div>
              <div className="h-1.5 bg-slate-100 rounded mt-2">
                <div className="h-full rounded" style={{ width: `${pct}%`, backgroundColor: pct > 85 ? "#C62828" : "#0A2B4E" }} />
              </div>
            </div>
          );
        })}
      </div>

      <Panel
        title="Village-wise allocation"
        action={
          <Button size="sm" onClick={optimise} disabled={busy} className="bg-national text-white gap-1" data-testid="btn-optimize-resources">
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />} Ask AI to optimise
          </Button>
        }
      >
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-slate-500 uppercase text-[11px] tracking-widest">
                <th className="p-2 text-left">Village</th>
                <th className="p-2 text-right">Boats</th>
                <th className="p-2 text-right">Ambulances</th>
                <th className="p-2 text-right">Food Kits</th>
                <th className="p-2 text-right">Medical Teams</th>
                <th className="p-2 text-left">Priority</th>
              </tr>
            </thead>
            <tbody>
              {data.allocations.map((a) => (
                <tr key={a.village} className="border-t border-slate-100">
                  <td className="p-2 font-semibold text-national">{a.village}</td>
                  <td className="p-2 text-right">{a.boats}</td>
                  <td className="p-2 text-right">{a.ambulances}</td>
                  <td className="p-2 text-right">{a.food_kits}</td>
                  <td className="p-2 text-right">{a.medical_teams}</td>
                  <td className="p-2"><StatusBadge status={a.priority} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {suggestion && (
          <div className="mt-4 border-l-4 border-saffron bg-slate-50 p-3 text-sm whitespace-pre-wrap" data-testid="ai-optimize-output">
            <div className="text-[10px] font-bold uppercase tracking-widest text-saffron mb-1">AI recommendation</div>
            {suggestion}
          </div>
        )}
      </Panel>
    </div>
  );
}
