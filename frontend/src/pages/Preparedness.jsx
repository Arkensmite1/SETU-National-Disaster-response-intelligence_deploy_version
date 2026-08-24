import React, { useEffect, useState } from "react";
import { api, endpoints } from "@/lib/api";
import { SectionHeading, Panel } from "@/components/common/GovUI";
import { Phone } from "lucide-react";

export default function Preparedness() {
  const [guide, setGuide] = useState({ before: [], during: [], after: [] });
  const [contacts, setContacts] = useState([]);
  useEffect(() => {
    api.get(endpoints.prepare).then(r => setGuide(r.data.guide || {})).catch(() => {});
    api.get(endpoints.contacts).then(r => setContacts(r.data.contacts || [])).catch(() => {});
  }, []);

  return (
    <div className="max-w-[1600px] mx-auto px-4 py-6">
      <SectionHeading eyebrow="Learning Centre" title="Disaster Preparedness" description="What to do before, during and after a flood — plus every emergency number you'll ever need." />

      <div className="grid lg:grid-cols-3 gap-4">
        {[
          { title: "Before a flood", key: "before", tint: "#138808" },
          { title: "During a flood", key: "during", tint: "#EF6C00" },
          { title: "After a flood", key: "after", tint: "#0A2B4E" },
        ].map((s) => (
          <Panel key={s.key} title={s.title}>
            <ul className="space-y-2 text-sm">
              {(guide[s.key] || []).map((item, i) => (
                <li key={i} className="flex gap-2">
                  <span className="w-5 h-5 shrink-0 rounded-full text-white text-[11px] flex items-center justify-center font-bold" style={{ backgroundColor: s.tint }}>{i + 1}</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </Panel>
        ))}
      </div>

      <div className="mt-6">
        <Panel title="Emergency Contacts">
          <div className="grid md:grid-cols-3 lg:grid-cols-5 gap-3">
            {contacts.map((c) => (
              <a key={c.name} href={`tel:${c.number}`} className="border border-slate-200 rounded-md p-3 hover:border-national" data-testid={`contact-${c.name.replace(/\s+/g, '-')}`}>
                <div className="text-[11px] font-bold uppercase tracking-widest text-slate-500">{c.category}</div>
                <div className="font-semibold text-national mt-0.5 text-sm">{c.name}</div>
                <div className="text-national font-heading font-extrabold text-lg flex items-center gap-1"><Phone size={14} /> {c.number}</div>
              </a>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}
