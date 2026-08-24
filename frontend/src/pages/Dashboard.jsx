import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, endpoints } from "@/lib/api";
import { StatCard, SectionHeading, Panel, StatusBadge } from "@/components/common/GovUI";
import { Users, ShieldAlert, Waves, Package, Radio, Siren, Bird, Cpu } from "lucide-react";
import FloodMap from "@/components/map/FloodMap";

export default function Dashboard() {
  const [stats, setStats] = useState({});
  const [mapData, setMapData] = useState({ villages: [], shelters: [], road_closures: [] });
  const [predictions, setPredictions] = useState([]);
  const [incidents, setIncidents] = useState([]);

  useEffect(() => {
    api.get(endpoints.overview).then(r => setStats(r.data.stats)).catch(() => {});
    api.get(endpoints.map).then(r => setMapData(r.data)).catch(() => {});
    api.get(endpoints.predictionsAll).then(r => setPredictions(r.data.items || [])).catch(() => {});
    api.get(endpoints.incidents).then(r => setIncidents(r.data.incidents || [])).catch(() => {});
  }, []);

  return (
    <div className="max-w-[1600px] mx-auto px-4 py-6">
      <SectionHeading
        eyebrow="Command Centre"
        title="National Disaster Operations — Live"
        description="A single pane-of-glass across all active flood incidents, resource deployments and AI predictions."
      />

      {/* Stats grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard label="People Evacuated" value={(stats.people_evacuated || 0).toLocaleString()} icon={Users} />
        <StatCard label="Shelters Active" value={stats.shelters_active || 0} icon={Waves} />
        <StatCard label="Rescue Teams" value={stats.rescue_teams_deployed || 0} icon={ShieldAlert} accent="saffron" />
        <StatCard label="Villages Affected" value={stats.villages_affected || 0} icon={Radio} accent="red" />
        <StatCard label="Boats Deployed" value={stats.boats_operational || 0} icon={Package} />
        <StatCard label="Helicopters" value={stats.helicopters_operational || 0} icon={Bird} />
        <StatCard label="Predictions" value={(stats.predictions_generated || 0).toLocaleString()} icon={Cpu} />
        <StatCard label="Broadcasts" value={stats.alerts_broadcast || 0} icon={Siren} accent="saffron" />
      </div>

      {/* Map + Priority Panel */}
      <div className="grid lg:grid-cols-12 gap-4 mb-6">
        <div className="lg:col-span-8">
          <Panel title="Live Flood Situation Map" action={<Link to="/map" className="text-xs font-semibold text-saffron">Open full map →</Link>}>
            <FloodMap villages={mapData.villages} shelters={mapData.shelters} roadClosures={mapData.road_closures} height="480px" />
          </Panel>
        </div>
        <div className="lg:col-span-4 space-y-4">
          <Panel title="Top Priority Incidents" action={<Link to="/incidents" className="text-xs font-semibold text-saffron">View all →</Link>}>
            <ul className="space-y-3">
              {incidents.slice(0, 5).map((i) => (
                <li key={i.id} className="border-l-4 pl-3 py-1" style={{ borderColor: i.priority === "critical" ? "#C62828" : i.priority === "high" ? "#EF6C00" : "#F9A825" }}>
                  <div className="flex items-center justify-between">
                    <div className="text-sm font-semibold text-national">{i.type}</div>
                    <StatusBadge status={i.priority} />
                  </div>
                  <div className="text-xs text-slate-600">{i.location} • ETA {i.eta_min}m</div>
                  <div className="text-xs text-slate-500 mt-0.5">{i.details}</div>
                </li>
              ))}
            </ul>
          </Panel>

          <Panel title="AI Predictions — Top Risk">
            <ul className="space-y-2">
              {predictions.sort((a, b) => (b.prediction?.probability || 0) - (a.prediction?.probability || 0)).slice(0, 5).map((p) => (
                <li key={p.region.id} className="flex items-center justify-between py-1 border-b border-slate-100 last:border-0">
                  <div>
                    <div className="text-sm font-semibold text-national">{p.region.name}</div>
                    <div className="text-xs text-slate-500">{p.region.river} • pop {(p.region.population/1e6).toFixed(1)}M</div>
                  </div>
                  <div className="text-right">
                    <div className={`text-lg font-heading font-extrabold ${p.prediction.probability > 80 ? "text-status-critical" : p.prediction.probability > 60 ? "text-status-warning" : "text-national"}`} style={{ color: p.prediction.probability > 80 ? "#C62828" : p.prediction.probability > 60 ? "#EF6C00" : "#0A2B4E" }}>
                      {p.prediction.probability}%
                    </div>
                    <div className="text-[10px] uppercase tracking-widest text-slate-500">in {p.prediction.time_remaining_hr}h</div>
                  </div>
                </li>
              ))}
            </ul>
          </Panel>
        </div>
      </div>

      {/* Quick modules */}
      <SectionHeading eyebrow="Modules" title="Quick access" />
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        {[
          { to: "/prediction", label: "AI Prediction" },
          { to: "/damage", label: "Damage Estimation" },
          { to: "/simulation", label: "Flood Simulation" },
          { to: "/rescue", label: "Rescue Router" },
          { to: "/chatbot", label: "AI Assistant" },
          { to: "/social", label: "Social Intel" },
          { to: "/volunteers", label: "Volunteers" },
          { to: "/shelters", label: "Shelters" },
          { to: "/medical", label: "Health Outlook" },
          { to: "/economic", label: "Economic Loss" },
          { to: "/preparedness", label: "Preparedness" },
          { to: "/drones", label: "Drone Ops" },
        ].map((m) => (
          <Link
            key={m.to}
            to={m.to}
            data-testid={`quick-${m.label.toLowerCase().replace(/\s+/g, "-")}`}
            className="bg-white border border-slate-200 rounded-md p-3 text-sm font-semibold text-national hover:border-national text-center"
          >
            {m.label}
          </Link>
        ))}
      </div>
    </div>
  );
}
