import React, { useState } from "react";
import { api, endpoints } from "@/lib/api";
import { SectionHeading, Panel } from "@/components/common/GovUI";
import { Button } from "@/components/ui/button";
import FloodMap from "@/components/map/FloodMap";
import { Loader2, Route } from "lucide-react";

const PRESETS = [
  { name: "NDRF Base Guwahati → Majuli Island", from: [26.1445, 91.7362], to: [26.9500, 94.1667] },
  { name: "Darbhanga Base → Bahadurpur", from: [26.1520, 85.8970], to: [26.1670, 85.9020] },
  { name: "Alappuzha Base → Kuttanad", from: [9.4981, 76.3388], to: [9.5350, 76.4000] },
  { name: "Kolkata Base → Gosaba", from: [22.5726, 88.3639], to: [22.1667, 88.8000] },
];

export default function Rescue() {
  const [route, setRoute] = useState(null);
  const [busy, setBusy] = useState(false);
  const [selection, setSelection] = useState(PRESETS[0]);
  const [boat, setBoat] = useState(true);

  const compute = async (p) => {
    setBusy(true);
    try {
      const r = await api.post(endpoints.rescueRoute, {
        from_lat: p.from[0], from_lng: p.from[1], to_lat: p.to[0], to_lng: p.to[1], boat,
      });
      setRoute({ ...r.data, preset: p });
    } finally { setBusy(false); }
  };

  return (
    <div className="max-w-[1600px] mx-auto px-4 py-6">
      <SectionHeading eyebrow="Module 05" title="AI Rescue Route Planner" description="Fastest safe route for rescue teams — avoids submerged roads, damaged bridges and traffic. Adapts for boat vs vehicle." />

      <div className="grid lg:grid-cols-12 gap-4">
        <div className="lg:col-span-4">
          <Panel title="Choose scenario">
            <ul className="space-y-2">
              {PRESETS.map((p, i) => (
                <li key={i}>
                  <button
                    data-testid={`rescue-preset-${i}`}
                    onClick={() => setSelection(p)}
                    className={`w-full text-left px-3 py-2 rounded-md border text-sm ${selection === p ? "border-national bg-slate-50" : "border-slate-200 hover:bg-slate-50"}`}
                  >{p.name}</button>
                </li>
              ))}
            </ul>
            <div className="mt-4 flex items-center justify-between">
              <span className="text-sm">Vehicle type</span>
              <div className="flex border border-slate-200 rounded-md overflow-hidden text-xs">
                <button onClick={() => setBoat(true)} className={`px-3 py-1 ${boat ? "bg-national text-white" : "bg-white"}`} data-testid="btn-vehicle-boat">Boat</button>
                <button onClick={() => setBoat(false)} className={`px-3 py-1 ${!boat ? "bg-national text-white" : "bg-white"}`} data-testid="btn-vehicle-vehicle">Vehicle</button>
              </div>
            </div>
            <Button onClick={() => compute(selection)} disabled={busy} className="mt-4 w-full bg-national text-white gap-1" data-testid="btn-compute-route">
              {busy ? <Loader2 size={14} className="animate-spin" /> : <Route size={14} />} Compute route
            </Button>
            {route && (
              <div className="mt-4 space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-slate-500">Distance</span><span className="font-heading font-bold">{route.distance_km} km</span></div>
                <div className="flex justify-between"><span className="text-slate-500">ETA</span><span className="font-heading font-bold text-saffron">{route.eta_min} min</span></div>
                <div className="pt-2 border-t border-slate-100">
                  <div className="text-[11px] uppercase tracking-widest text-slate-500 font-bold mb-1">AI avoided</div>
                  <ul className="text-xs space-y-0.5">{route.avoided.map((a, i) => <li key={i}>✕ {a}</li>)}</ul>
                </div>
              </div>
            )}
          </Panel>
        </div>

        <div className="lg:col-span-8">
          <Panel title="Route visualisation">
            <FloodMap
              center={selection.from}
              zoom={9}
              routeCoords={route ? route.waypoints.map(w => [w.lat, w.lng]) : null}
              villages={[
                { id: "from", name: "Start", lat: selection.from[0], lng: selection.from[1], status: "safe", flood_depth: 0, population: 0, trapped: 0, district: "" },
                { id: "to", name: "Destination", lat: selection.to[0], lng: selection.to[1], status: "critical", flood_depth: 2, population: 0, trapped: 0, district: "" },
              ]}
              height="560px"
            />
          </Panel>
        </div>
      </div>
    </div>
  );
}
