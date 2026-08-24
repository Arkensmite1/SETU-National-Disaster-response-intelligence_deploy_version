import React, { useEffect, useState } from "react";
import { api, endpoints } from "@/lib/api";
import { SectionHeading, Panel } from "@/components/common/GovUI";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { UserPlus } from "lucide-react";

export default function Volunteers() {
  const [list, setList] = useState([]);
  const [form, setForm] = useState({ name: "", phone: "", skill: "Doctor", location: "" });

  const load = () => api.get(endpoints.volunteers).then(r => setList(r.data.volunteers || [])).catch(() => {});
  useEffect(() => { load(); }, []);

  const submit = async () => {
    if (!form.name || !form.phone || !form.location) return toast.error("Fill all fields");
    try {
      await api.post(endpoints.volunteers, form);
      toast.success("Registered — assignment will be sent by SMS.");
      setForm({ name: "", phone: "", skill: "Doctor", location: "" });
      load();
    } catch { toast.error("Failed to register"); }
  };

  return (
    <div className="max-w-[1600px] mx-auto px-4 py-6">
      <SectionHeading eyebrow="Module 11" title="Volunteers & NGOs" description="Register your skills. AI matches you to the nearest incident based on need." />

      <div className="grid lg:grid-cols-12 gap-4">
        <div className="lg:col-span-4">
          <Panel title="Register as a volunteer">
            {["name", "phone", "location"].map((k) => (
              <div key={k} className="mb-3">
                <label className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-1 block capitalize">{k}</label>
                <input
                  data-testid={`vol-${k}`}
                  value={form[k]}
                  onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                  className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm"
                />
              </div>
            ))}
            <label className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-1 block">Skill</label>
            <select
              data-testid="vol-skill"
              value={form.skill}
              onChange={(e) => setForm({ ...form, skill: e.target.value })}
              className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm mb-4"
            >
              {["Doctor", "Nurse", "Boat Operator", "Driver", "Cook", "Translator", "Rescue", "Logistics"].map(s => <option key={s}>{s}</option>)}
            </select>
            <Button onClick={submit} className="w-full bg-national text-white gap-1" data-testid="btn-register-volunteer">
              <UserPlus size={14} /> Register
            </Button>
          </Panel>
        </div>

        <div className="lg:col-span-8">
          <Panel title="Volunteer roster">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-slate-50 text-slate-500 uppercase text-[11px] tracking-widest">
                    <th className="p-2 text-left">Name</th>
                    <th className="p-2 text-left">Skill</th>
                    <th className="p-2 text-left">Location</th>
                    <th className="p-2 text-left">Assigned to</th>
                    <th className="p-2 text-left">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {list.map((v) => (
                    <tr key={v.id} className="border-t border-slate-100" data-testid={`vol-row-${v.id}`}>
                      <td className="p-2 font-semibold text-national">{v.name}</td>
                      <td className="p-2">{v.skill}</td>
                      <td className="p-2">{v.location}</td>
                      <td className="p-2 text-slate-600">{v.assigned_to || "—"}</td>
                      <td className="p-2 text-[11px] uppercase tracking-widest font-bold" style={{ color: v.available ? "#2E7D32" : "#EF6C00" }}>
                        {v.available ? "Available" : "Deployed"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
