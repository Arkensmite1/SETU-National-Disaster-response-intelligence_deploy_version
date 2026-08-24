import React, { useEffect, useState } from "react";
import { api, endpoints } from "@/lib/api";
import { SectionHeading, Panel, StatusBadge } from "@/components/common/GovUI";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Sparkles, Loader2, Radio } from "lucide-react";
import { toast } from "sonner";

export default function Prediction() {
  const [regions, setRegions] = useState([]);
  const [selected, setSelected] = useState("assam-dhemaji");
  const [pred, setPred] = useState(null);
  const [explanation, setExplanation] = useState("");
  const [warning, setWarning] = useState("");
  const [busyX, setBusyX] = useState(false);
  const [busyW, setBusyW] = useState(false);

  useEffect(() => { api.get(endpoints.regions).then(r => setRegions(r.data.regions || [])).catch(() => {}); }, []);
  useEffect(() => {
    if (!selected) return;
    setExplanation("");
    setWarning("");
    api.get(endpoints.prediction(selected)).then(r => setPred(r.data)).catch(() => {});
  }, [selected]);

  const explain = async () => {
    setBusyX(true); setExplanation("");
    try {
      const r = await api.post(endpoints.explain, { region_id: selected });
      setExplanation(r.data.explanation);
    } catch (e) { toast.error("AI explanation failed"); }
    finally { setBusyX(false); }
  };

  const genWarning = async () => {
    setBusyW(true); setWarning("");
    try {
      const r = await api.post(endpoints.warning, { region_id: selected });
      setWarning(r.data.raw);
    } catch (e) { toast.error("Warning generation failed"); }
    finally { setBusyW(false); }
  };

  const p = pred?.prediction;
  const r = pred?.region;

  return (
    <div className="max-w-[1600px] mx-auto px-4 py-6">
      <SectionHeading eyebrow="Module 02" title="AI Flood Prediction — with Explainable AI" description="Beyond 'flood likely'. See probability, water depth, time remaining, population at risk — and the reasons the model believes so." />

      <div className="grid lg:grid-cols-12 gap-4">
        <div className="lg:col-span-4">
          <Panel title="Regions">
            <ul className="max-h-[520px] overflow-y-auto space-y-1">
              {regions.map((reg) => (
                <li key={reg.id}>
                  <button
                    data-testid={`region-${reg.id}`}
                    onClick={() => setSelected(reg.id)}
                    className={`w-full text-left px-3 py-2 rounded-md text-sm border ${selected === reg.id ? "border-national bg-slate-50" : "border-transparent hover:bg-slate-50"}`}
                  >
                    <div className="font-semibold text-national">{reg.name}</div>
                    <div className="text-xs text-slate-500">{reg.river} • pop {(reg.population/1e6).toFixed(2)}M</div>
                  </button>
                </li>
              ))}
            </ul>
          </Panel>
        </div>

        <div className="lg:col-span-8 space-y-4">
          {p && r && (
            <>
              <Panel title={`Prediction — ${r.name}`}>
                <div className="grid md:grid-cols-4 gap-4">
                  <div>
                    <div className="text-[11px] uppercase tracking-widest text-slate-500 font-bold">Flood Probability</div>
                    <div className="text-4xl font-heading font-extrabold" style={{ color: p.probability > 80 ? "#C62828" : p.probability > 60 ? "#EF6C00" : "#0A2B4E" }}>
                      {p.probability}%
                    </div>
                    <Progress value={p.probability} className="mt-2 h-2" />
                  </div>
                  <div>
                    <div className="text-[11px] uppercase tracking-widest text-slate-500 font-bold">Expected Water Depth</div>
                    <div className="text-4xl font-heading font-extrabold text-national">{p.expected_depth_m}m</div>
                    <div className="text-xs text-slate-500 mt-1">Peak within {p.time_remaining_hr}h</div>
                  </div>
                  <div>
                    <div className="text-[11px] uppercase tracking-widest text-slate-500 font-bold">Time Remaining</div>
                    <div className="text-4xl font-heading font-extrabold text-national">{p.time_remaining_hr}<span className="text-lg">h</span></div>
                  </div>
                  <div>
                    <div className="text-[11px] uppercase tracking-widest text-slate-500 font-bold">Population at Risk</div>
                    <div className="text-4xl font-heading font-extrabold text-national">{(p.population_at_risk/1000).toFixed(1)}<span className="text-lg">K</span></div>
                    <div className="text-xs text-slate-500 mt-1">{p.affected_villages} villages</div>
                  </div>
                </div>
              </Panel>

              <Panel
                title="Explainable AI (XAI) — Why this prediction?"
                action={
                  <Button size="sm" onClick={explain} disabled={busyX} data-testid="btn-explain-ai" className="bg-national text-white gap-1">
                    {busyX ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />} Ask AI
                  </Button>
                }
              >
                <ul className="space-y-3 mb-4">
                  {pred.factors?.map((f, i) => (
                    <li key={i}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm text-slate-800">{f.factor}</span>
                        <span className="text-xs font-mono text-slate-500">{Math.round(f.impact * 100)}%</span>
                      </div>
                      <div className="h-1.5 bg-slate-100 rounded">
                        <div className="h-full rounded" style={{ width: `${f.impact * 100}%`, backgroundColor: "#0A2B4E" }} />
                      </div>
                    </li>
                  ))}
                </ul>
                {explanation && (
                  <div className="border-l-4 border-saffron bg-slate-50 p-3 text-sm leading-relaxed" data-testid="ai-explanation">
                    <div className="text-[10px] font-bold uppercase tracking-widest text-saffron mb-1">AI-generated explanation</div>
                    {explanation}
                  </div>
                )}
              </Panel>

              <Panel
                title="Early Warning — Bilingual"
                action={
                  <Button size="sm" onClick={genWarning} disabled={busyW} className="bg-saffron hover:bg-orange-500 text-national gap-1" data-testid="btn-generate-warning">
                    {busyW ? <Loader2 size={14} className="animate-spin" /> : <Radio size={14} />} Generate SMS text
                  </Button>
                }
              >
                {warning ? (
                  <pre className="text-xs bg-slate-50 border border-slate-200 rounded p-3 whitespace-pre-wrap font-mono">{warning}</pre>
                ) : (
                  <p className="text-sm text-slate-500">Click "Generate SMS text" — the AI will draft an official-tone alert in Hindi and English (max 60 words) suitable for SMS 51969 broadcast.</p>
                )}
              </Panel>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
