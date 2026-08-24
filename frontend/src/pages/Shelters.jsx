import React, { useEffect, useState } from "react";
import { api, endpoints } from "@/lib/api";
import { SectionHeading, Panel } from "@/components/common/GovUI";
import { Button } from "@/components/ui/button";
import { Loader2, MapPin } from "lucide-react";

export default function Shelters() {
  const [lat, setLat] = useState(28.5355);
  const [lng, setLng] = useState(77.3910);
  const [medical, setMedical] = useState(false);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  const find = async () => {
    setBusy(true);
    try {
      const r = await api.post(endpoints.shelterRecommend, { lat: parseFloat(lat), lng: parseFloat(lng), needs_medical: medical });
      setResult(r.data);
    } finally { setBusy(false); }
  };

  const useMyLocation = () => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition((pos) => { setLat(pos.coords.latitude); setLng(pos.coords.longitude); });
  };

  useEffect(() => { find(); }, []); // initial

  return (
    <div className="max-w-[1600px] mx-auto px-4 py-6">
      <SectionHeading eyebrow="Module 04" title="AI Shelter Recommendation" description="Given your location, find the safest, closest shelter — factoring free capacity, medical facilities, food and power." />

      <div className="grid lg:grid-cols-12 gap-4">
        <div className="lg:col-span-4">
          <Panel title="Your location">
            <label className="block text-xs font-bold uppercase tracking-widest text-slate-500 mb-1">Latitude</label>
            <input value={lat} onChange={(e) => setLat(e.target.value)} data-testid="shelter-lat" className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm mb-3" />
            <label className="block text-xs font-bold uppercase tracking-widest text-slate-500 mb-1">Longitude</label>
            <input value={lng} onChange={(e) => setLng(e.target.value)} data-testid="shelter-lng" className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm mb-3" />
            <label className="flex items-center gap-2 text-sm mb-4">
              <input type="checkbox" checked={medical} onChange={(e) => setMedical(e.target.checked)} data-testid="shelter-medical" /> Requires medical facility
            </label>
            <div className="flex gap-2">
              <Button onClick={find} disabled={busy} className="bg-national text-white gap-1" data-testid="btn-find-shelter">
                {busy ? <Loader2 size={14} className="animate-spin" /> : <MapPin size={14} />} Find nearest
              </Button>
              <Button variant="outline" onClick={useMyLocation} data-testid="btn-use-my-location">Use GPS</Button>
            </div>
          </Panel>
        </div>

        <div className="lg:col-span-8">
          <Panel title="Recommendations (ranked)">
            {!result ? (
              <p className="text-sm text-slate-500">Set a location and search.</p>
            ) : (
              <>
                <div className="border-l-4 border-saffron bg-slate-50 p-3 text-sm mb-4">{result.reasoning}</div>
                <ul className="space-y-3">
                  {result.recommendations.map((s, i) => (
                    <li key={s.id} className="border border-slate-200 rounded-md p-3 flex items-start justify-between" data-testid={`shelter-rec-${i}`}>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold text-saffron">#{i + 1}</span>
                          <div className="font-heading font-bold text-national">{s.name}</div>
                        </div>
                        <div className="text-xs text-slate-500 mt-0.5">
                          {s.distance_km} km • {s.free} beds free of {s.capacity}
                        </div>
                        <div className="text-xs mt-1 space-x-2">
                          {s.food && <span className="text-indiagreen">● Food</span>}
                          {s.medical && <span className="text-national">● Medical</span>}
                          {s.electricity && <span className="text-saffron">● Power</span>}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-2xl font-heading font-extrabold text-national">{s.score}</div>
                        <div className="text-[10px] uppercase tracking-widest text-slate-500">Score</div>
                      </div>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
