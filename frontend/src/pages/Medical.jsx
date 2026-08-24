import React, { useEffect, useState } from "react";
import { api, endpoints } from "@/lib/api";
import { SectionHeading, Panel } from "@/components/common/GovUI";

export default function Medical() {
  const [items, setItems] = useState([]);
  useEffect(() => { api.get(endpoints.medical).then(r => setItems(r.data.predictions || [])).catch(() => {}); }, []);

  return (
    <div className="max-w-[1600px] mx-auto px-4 py-6">
      <SectionHeading eyebrow="Module 13" title="Post-Flood Health Outbreak Prediction" description="Historical + current-condition modelling of dengue, cholera, malaria and leptospirosis risk after floods." />

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {items.map((it) => (
          <Panel key={it.disease} title={it.disease}>
            <div className="text-4xl font-heading font-extrabold" style={{ color: it.risk_pct > 70 ? "#C62828" : it.risk_pct > 50 ? "#EF6C00" : "#0A2B4E" }}>
              {it.risk_pct}%
            </div>
            <div className="h-2 bg-slate-100 rounded mt-2 mb-3">
              <div className="h-full rounded" style={{ width: `${it.risk_pct}%`, backgroundColor: it.risk_pct > 70 ? "#C62828" : it.risk_pct > 50 ? "#EF6C00" : "#0A2B4E" }} />
            </div>
            <div className="text-xs text-slate-600 leading-relaxed">{it.reason}</div>
            <div className="mt-3 flex flex-wrap gap-1">
              {it.regions.map(r => (
                <span key={r} className="text-[11px] px-2 py-0.5 bg-slate-100 rounded font-semibold text-national">{r}</span>
              ))}
            </div>
          </Panel>
        ))}
      </div>
    </div>
  );
}
