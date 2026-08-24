import React, { useEffect, useState } from "react";
import { api, endpoints } from "@/lib/api";
import FloodMap from "@/components/map/FloodMap";
import { SectionHeading, Panel, StatusBadge } from "@/components/common/GovUI";

export default function LiveMap() {
  const [data, setData] = useState({ villages: [], shelters: [], road_closures: [], reservoirs: [] });
  useEffect(() => { api.get(endpoints.map).then(r => setData(r.data)).catch(() => {}); }, []);

  const counts = {
    critical: data.villages.filter(v => v.status === "critical").length,
    warning: data.villages.filter(v => v.status === "warning").length,
    watch: data.villages.filter(v => v.status === "watch").length,
    safe: data.villages.filter(v => v.status === "safe").length,
  };

  return (
    <div className="max-w-[1600px] mx-auto px-4 py-6">
      <SectionHeading eyebrow="Module 01" title="Live Flood Monitoring" description="Interactive GIS map with rainfall, river levels, reservoirs, flooded villages, shelters and blocked roads. Toggle layers from the top-right of the map." />

      <div className="grid lg:grid-cols-12 gap-4">
        <div className="lg:col-span-9">
          <Panel title="India Flood Map">
            <FloodMap villages={data.villages} shelters={data.shelters} roadClosures={data.road_closures} height="620px" />
          </Panel>
        </div>

        <div className="lg:col-span-3 space-y-4">
          <Panel title="Status Summary">
            <ul className="space-y-2">
              {[["critical", counts.critical, "#C62828"], ["warning", counts.warning, "#EF6C00"], ["watch", counts.watch, "#F9A825"], ["safe", counts.safe, "#2E7D32"]].map(([k, v, c]) => (
                <li key={k} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full" style={{ backgroundColor: c }} />
                    <span className="text-sm capitalize">{k}</span>
                  </div>
                  <span className="font-heading font-bold text-national">{v}</span>
                </li>
              ))}
            </ul>
          </Panel>

          <Panel title="Reservoirs">
            <ul className="space-y-2">
              {data.reservoirs.map((r) => (
                <li key={r.id} className="text-sm">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-national">{r.name}</span>
                    <StatusBadge status={r.status} />
                  </div>
                  <div className="mt-1 h-2 bg-slate-100 rounded overflow-hidden">
                    <div
                      className="h-full"
                      style={{ width: `${r.level_pct}%`, backgroundColor: r.level_pct > 90 ? "#C62828" : r.level_pct > 75 ? "#EF6C00" : "#0F4C5C" }}
                    />
                  </div>
                  <div className="text-[11px] text-slate-500 mt-0.5">{r.state} • {r.level_pct}% • Outflow {r.outflow}</div>
                </li>
              ))}
            </ul>
          </Panel>
        </div>
      </div>
    </div>
  );
}
