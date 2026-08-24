import React, { useEffect, useState } from "react";
import { api, endpoints } from "@/lib/api";
import { SectionHeading, Panel, StatusBadge } from "@/components/common/GovUI";
import { PhoneCall } from "lucide-react";

export default function Incidents() {
  const [items, setItems] = useState([]);
  const [sos, setSos] = useState([]);
  useEffect(() => {
    api.get(endpoints.incidents).then(r => setItems(r.data.incidents || [])).catch(() => {});
    api.get(endpoints.sosList).then(r => setSos(r.data.items || [])).catch(() => {});
  }, []);

  return (
    <div className="max-w-[1600px] mx-auto px-4 py-6">
      <SectionHeading eyebrow="Module 10" title="AI Incident Prioritisation" description="Hundreds of citizen requests are automatically prioritised. Pregnant women and trapped families jump to the top." />

      <div className="grid lg:grid-cols-12 gap-4">
        <div className="lg:col-span-8">
          <Panel title="Prioritised queue">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-slate-50 text-slate-500 uppercase text-[11px] tracking-widest">
                    <th className="p-2 text-left">Priority</th>
                    <th className="p-2 text-left">Type</th>
                    <th className="p-2 text-left">Location</th>
                    <th className="p-2 text-left">Reporter</th>
                    <th className="p-2 text-right">ETA (min)</th>
                    <th className="p-2 text-left">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((i, idx) => (
                    <tr key={i.id} className="border-t border-slate-100 hover:bg-slate-50" data-testid={`incident-row-${idx}`}>
                      <td className="p-2"><StatusBadge status={i.priority} /></td>
                      <td className="p-2 font-semibold text-national">{i.type}<div className="text-[11px] text-slate-500 font-normal">{i.details}</div></td>
                      <td className="p-2">{i.location}</td>
                      <td className="p-2">{i.reporter}</td>
                      <td className="p-2 text-right font-mono">{i.eta_min}</td>
                      <td className="p-2 uppercase text-[11px] tracking-widest text-slate-600">{i.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>
        <div className="lg:col-span-4">
          <Panel title="Live citizen SOS reports">
            {sos.length === 0 ? (
              <p className="text-sm text-slate-500">No live SOS reports. When citizens tap the SOS button, they appear here in real-time.</p>
            ) : (
              <ul className="space-y-2">
                {sos.map((s) => (
                  <li key={s.id} className="border-l-4 border-status-critical bg-slate-50 p-3" style={{ borderColor: "#C62828" }}>
                    <div className="flex items-center justify-between">
                      <div className="font-semibold text-national">{s.name}</div>
                      <a href={`tel:${s.phone}`} className="text-xs text-national inline-flex items-center gap-1"><PhoneCall size={12} /> {s.phone}</a>
                    </div>
                    <div className="text-xs text-slate-600">{s.location} • {s.people_count} people</div>
                    <div className="text-xs text-slate-500 mt-1">{s.situation}</div>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
