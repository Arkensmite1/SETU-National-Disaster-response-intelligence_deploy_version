import React, { useEffect, useState } from "react";
import { api, endpoints } from "@/lib/api";
import { SectionHeading, Panel } from "@/components/common/GovUI";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell } from "recharts";

export default function Economic() {
  const [loss, setLoss] = useState({});
  useEffect(() => { api.get(endpoints.economic).then(r => setLoss(r.data.loss || {})).catch(() => {}); }, []);

  const chart = [
    { name: "Crop", value: loss.crop_damage_cr, color: "#138808" },
    { name: "Roads", value: loss.road_damage_cr, color: "#0A2B4E" },
    { name: "Houses", value: loss.house_damage_cr, color: "#C62828" },
    { name: "Livestock", value: loss.livestock_loss_cr, color: "#0F4C5C" },
    { name: "Commercial", value: loss.commercial_loss_cr, color: "#FF9933" },
  ];

  return (
    <div className="max-w-[1600px] mx-auto px-4 py-6">
      <SectionHeading eyebrow="Module 14" title="AI Economic Loss Estimation" description="Sector-wise damage estimates fed to the State Disaster Response Fund (SDRF) and insurance workflows." />

      <div className="grid lg:grid-cols-12 gap-4">
        <div className="lg:col-span-4">
          <Panel title="Total estimated loss">
            <div className="text-5xl font-heading font-extrabold text-national">
              ₹{(loss.total_cr || 0).toFixed(1)} <span className="text-lg">Cr</span>
            </div>
            <ul className="mt-4 space-y-2 text-sm">
              {chart.map((c) => (
                <li key={c.name} className="flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded" style={{ backgroundColor: c.color }} />
                    {c.name}
                  </span>
                  <span className="font-heading font-bold">₹{c.value || 0} Cr</span>
                </li>
              ))}
            </ul>
          </Panel>
        </div>
        <div className="lg:col-span-8">
          <Panel title="Sector-wise breakdown">
            <div style={{ height: 340 }}>
              <ResponsiveContainer>
                <BarChart data={chart} margin={{ top: 20, right: 20, left: 0, bottom: 10 }}>
                  <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" stroke="#64748B" fontSize={12} />
                  <YAxis stroke="#64748B" fontSize={12} label={{ value: "₹ Crore", angle: -90, position: "insideLeft", fontSize: 12, fill: "#64748B" }} />
                  <Tooltip formatter={(v) => `₹${v} Cr`} />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                    {chart.map((c, i) => <Cell key={i} fill={c.color} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
