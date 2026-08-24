import React, { useEffect, useState } from "react";
import { api, endpoints } from "@/lib/api";
import { SectionHeading, Panel } from "@/components/common/GovUI";
import { Battery, Radio, Play, Pause } from "lucide-react";

export default function Drones() {
  const [drones, setDrones] = useState([]);
  useEffect(() => { api.get(endpoints.drones).then(r => setDrones(r.data.drones || [])).catch(() => {}); }, []);

  return (
    <div className="max-w-[1600px] mx-auto px-4 py-6">
      <SectionHeading eyebrow="Module 17" title="Drone Operations Centre" description="Live status of survey drones. Feed streaming, battery, altitude and coverage region." />

      <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
        {drones.map((d) => (
          <Panel key={d.id} title={d.name}>
            <div className="aspect-video bg-slate-900 rounded-md mb-3 relative overflow-hidden">
              <img alt="drone feed" src="https://images.unsplash.com/photo-1661704908184-7da1eb92a4cb?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzMjd8MHwxfHNlYXJjaHwxfHxkcm9uZSUyMHZpZXclMjByaXZlcnxlbnwwfHx8fDE3ODUzMzA3Mjh8MA&ixlib=rb-4.1.0&q=85" className="w-full h-full object-cover opacity-90" />
              <div className="absolute top-2 left-2 bg-status-critical text-white text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded" style={{ backgroundColor: "#C62828" }}>● Live</div>
              <div className="absolute bottom-2 right-2 bg-black/60 text-white text-[10px] px-2 py-0.5 rounded">{d.region}</div>
            </div>
            <div className="grid grid-cols-3 gap-2 text-xs">
              <div>
                <div className="text-slate-500 uppercase tracking-widest text-[10px] font-bold">Battery</div>
                <div className="font-heading font-bold text-national flex items-center gap-1"><Battery size={12} />{d.battery}%</div>
              </div>
              <div>
                <div className="text-slate-500 uppercase tracking-widest text-[10px] font-bold">Altitude</div>
                <div className="font-heading font-bold text-national">{d.altitude_m}m</div>
              </div>
              <div>
                <div className="text-slate-500 uppercase tracking-widest text-[10px] font-bold">Status</div>
                <div className="font-heading font-bold text-national capitalize flex items-center gap-1">
                  {d.status === "surveying" ? <Play size={12} /> : <Pause size={12} />} {d.status}
                </div>
              </div>
            </div>
          </Panel>
        ))}
      </div>
    </div>
  );
}
