import React, { useState } from "react";
import { api, endpoints } from "@/lib/api";
import { SectionHeading, Panel } from "@/components/common/GovUI";
import { Button } from "@/components/ui/button";
import { Siren, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

export default function SOS() {
  const [form, setForm] = useState({ name: "", phone: "", location: "", situation: "", people_count: 1, lat: null, lng: null });
  const [ticket, setTicket] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!form.name || !form.phone || !form.location || !form.situation) return toast.error("Please fill all required fields.");
    setBusy(true);
    try {
      const r = await api.post(endpoints.sosCreate, form);
      setTicket(r.data);
      toast.success("SOS registered. Rescue team dispatched.");
    } catch { toast.error("Unable to reach servers. Call 1078 immediately."); }
    finally { setBusy(false); }
  };

  const useLocation = () => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition((pos) => {
      setForm(f => ({ ...f, lat: pos.coords.latitude, lng: pos.coords.longitude, location: f.location || `${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}` }));
      toast.success("Location captured");
    });
  };

  if (ticket) {
    return (
      <div className="max-w-[900px] mx-auto px-4 py-10">
        <div className="bg-white border border-indiagreen rounded-md p-8 text-center" data-testid="sos-success">
          <CheckCircle2 size={56} className="text-indiagreen mx-auto" />
          <h2 className="mt-4 text-2xl font-heading font-extrabold text-national">SOS ticket registered</h2>
          <p className="text-sm text-slate-600 mt-1">Ticket ID: <span className="font-mono">{ticket.ticket_id}</span></p>
          <p className="text-sm text-slate-600 mt-1">Rescue team dispatched. Estimated arrival: <b>{ticket.eta_min} minutes</b></p>
          <p className="text-xs text-slate-500 mt-3">
            Stay put on the highest safe ground. Keep your phone on. If you must move, follow local NDRF instructions. Call 1078 for updates.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-[900px] mx-auto px-4 py-8">
      <div className="bg-status-critical text-white rounded-md p-4 mb-6 flex items-center gap-3" style={{ backgroundColor: "#C62828" }}>
        <Siren size={24} className="animate-blink" />
        <div>
          <div className="font-heading font-extrabold text-xl">Emergency SOS</div>
          <div className="text-sm text-white/90">This will alert the nearest NDRF / SDRF team. Only for genuine emergencies.</div>
        </div>
      </div>

      <Panel title="Your details">
        {["name", "phone", "location", "situation"].map((k) => (
          <div key={k} className="mb-3">
            <label className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-1 block capitalize">{k}{k !== "location" ? " *" : ""}</label>
            {k === "situation" ? (
              <textarea
                rows={3}
                value={form[k]}
                onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                data-testid={`sos-${k}`}
                className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm"
                placeholder="What's happening? Water level? People stranded?"
              />
            ) : (
              <input
                value={form[k]}
                onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                data-testid={`sos-${k}`}
                className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm"
              />
            )}
          </div>
        ))}

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-1 block">People with you</label>
            <input
              type="number"
              min={1}
              value={form.people_count}
              onChange={(e) => setForm({ ...form, people_count: parseInt(e.target.value) || 1 })}
              data-testid="sos-people-count"
              className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm"
            />
          </div>
          <div className="flex items-end">
            <Button variant="outline" onClick={useLocation} className="w-full" data-testid="btn-sos-gps">
              Share GPS Location
            </Button>
          </div>
        </div>

        <div className="mt-4 flex items-center gap-3">
          <Button onClick={submit} disabled={busy} className="text-white gap-2 font-bold" style={{ backgroundColor: "#C62828" }} data-testid="btn-sos-submit">
            <Siren size={16} /> Send SOS Alert
          </Button>
          <a href="tel:1078" className="text-sm font-semibold text-national">Or dial 1078 now →</a>
        </div>
      </Panel>
    </div>
  );
}
