import React, { useEffect, useState } from "react";
import { api, endpoints } from "@/lib/api";
import { SectionHeading, Panel } from "@/components/common/GovUI";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { Loader2, Waves } from "lucide-react";
import FloodMap from "@/components/map/FloodMap";

export default function Simulation() {
  const [regions, setRegions] = useState([]);
  const [regionId, setRegionId] = useState("assam-dhemaji");
  const [rainfall, setRainfall] = useState(150);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.get(endpoints.regions).then(r => setRegions(r.data.regions || [])).catch(() => {}); }, []);

  const run = async () => {
    setBusy(true);
    try {
      const r = await api.post(endpoints.simulation, { rainfall_mm: rainfall, region_id: regionId });
      setResult(r.data);
    } finally { setBusy(false); }
  };

  useEffect(() => { run(); }, []); // initial
  const region = regions.find(r => r.id === regionId);

  return (
    <div className="max-w-[1600px] mx-auto px-4 py-6">
      <SectionHeading eyebrow="Module 09 · Digital Twin" title="AI Flood Simulation" description="Move the rainfall slider — see the model predict how far the flood will spread, how deep, and how many people it will affect." />

      <div className="grid lg:grid-cols-12 gap-4">
        <div className="lg:col-span-5">
          <Panel title="Scenario Controls">
            <label className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-1 block">Region</label>
            <select
              value={regionId}
              onChange={(e) => setRegionId(e.target.value)}
              data-testid="sim-region"
              className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm mb-4"
            >
              {regions.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>

            <label className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-1 block">Rainfall (mm)</label>
            <div className="flex items-center gap-4 mb-4">
              <Slider
                value={[rainfall]}
                onValueChange={(v) => setRainfall(v[0])}
                min={20}
                max={400}
                step={10}
                data-testid="sim-rainfall-slider"
                className="flex-1"
              />
              <span className="text-2xl font-heading font-extrabold text-national w-20 text-right">{rainfall}<span className="text-sm">mm</span></span>
            </div>

            <Button onClick={run} disabled={busy} className="w-full bg-national text-white gap-1" data-testid="btn-simulate">
              {busy ? <Loader2 size={14} className="animate-spin" /> : <Waves size={14} />} Run simulation
            </Button>

            {result && (
              <div className="mt-5 grid grid-cols-2 gap-3">
                <div>
                  <div className="text-[11px] uppercase tracking-widest text-slate-500 font-bold">Expected depth</div>
                  <div className="text-2xl font-heading font-extrabold text-national">{result.expected_depth_m} m</div>
                </div>
                <div>
                  <div className="text-[11px] uppercase tracking-widest text-slate-500 font-bold">Affected villages</div>
                  <div className="text-2xl font-heading font-extrabold text-national">{result.affected_villages}</div>
                </div>
                <div>
                  <div className="text-[11px] uppercase tracking-widest text-slate-500 font-bold">Pop. at risk</div>
                  <div className="text-2xl font-heading font-extrabold text-status-critical" style={{ color: "#C62828" }}>{(result.population_at_risk / 1000).toFixed(1)}K</div>
                </div>
                <div>
                  <div className="text-[11px] uppercase tracking-widest text-slate-500 font-bold">Spread</div>
                  <div className="text-2xl font-heading font-extrabold text-national">{result.spread_km2} km²</div>
                </div>
              </div>
            )}
          </Panel>
        </div>

        <div className="lg:col-span-7">
          <Panel title="Digital Twin — District View">
            {region && (
              <FloodMap
                center={[region.lat, region.lng]}
                zoom={9}
                villages={[
                  { id: "sim1", name: region.name, lat: region.lat, lng: region.lng, status: result && result.expected_depth_m > 1.5 ? "critical" : result && result.expected_depth_m > 0.8 ? "warning" : "watch", flood_depth: result?.expected_depth_m || 0, population: region.population, trapped: 0, district: region.state },
                ]}
                shelters={[]}
                roadClosures={[]}
                height="500px"
              />
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
