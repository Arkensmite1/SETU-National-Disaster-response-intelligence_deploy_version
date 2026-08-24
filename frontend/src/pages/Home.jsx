import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, ShieldCheck, Waves, Cpu, Users2, Siren, Phone } from "lucide-react";
import { api, endpoints } from "@/lib/api";
import { StatCard, SectionHeading } from "@/components/common/GovUI";
import { Button } from "@/components/ui/button";

const HERO_IMG = "https://images.unsplash.com/photo-1690149372906-8dedeb6496ea?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2NDF8MHwxfHNlYXJjaHw0fHxmbG9vZCUyMHJlc2N1ZSUyMGJvYXR8ZW58MHx8fHwxNzg1MzMwNzE0fDA&ixlib=rb-4.1.0&q=85";

export default function Home() {
  const [stats, setStats] = useState({});
  useEffect(() => { api.get(endpoints.overview).then(r => setStats(r.data.stats || {})).catch(() => {}); }, []);

  const FEATURES = [
    { icon: Waves, title: "Live Flood Monitoring", desc: "Interactive GIS map layering rainfall, river levels, reservoirs, blocked roads and flood-affected villages across India.", to: "/map" },
    { icon: Cpu, title: "Explainable AI Prediction", desc: "Not just 'flood likely'. See probability, expected water depth, timeline, population at risk — with the reasoning behind every forecast.", to: "/prediction" },
    { icon: Siren, title: "AI Rescue & Allocation", desc: "Optimised rescue routes avoiding submerged roads, and AI-driven allocation of boats, ambulances and medical teams.", to: "/rescue" },
    { icon: Users2, title: "Citizens, Volunteers, NGOs", desc: "SOS button, family safety check-in, volunteer matching and QR-verified relief distribution — one integrated stack.", to: "/volunteers" },
  ];

  return (
    <div>
      {/* Hero */}
      <section className="relative bg-national text-white overflow-hidden">
        <div className="absolute inset-0 ashoka-motif opacity-30" />
        <div className="max-w-[1600px] mx-auto px-4 py-14 md:py-20 grid md:grid-cols-2 gap-10 items-center relative">
          <div>
            <div className="inline-flex items-center gap-2 text-[11px] font-bold uppercase tracking-widest bg-white/10 border border-white/20 px-3 py-1 rounded">
              <ShieldCheck size={14} className="text-saffron" />
              A National Digital Public Good • Smart India Hackathon
            </div>
            <h1 className="mt-4 font-heading text-4xl md:text-5xl lg:text-6xl font-extrabold leading-[1.05]">
              Disaster Response,
              <br />
              <span className="text-saffron">powered by intelligence.</span>
            </h1>
            <p className="mt-5 text-white/80 max-w-xl text-[15px] leading-relaxed">
              SETU is a nation-wide platform that predicts floods before they happen, coordinates rescue
              in real time, and puts life-saving guidance in the hands of every citizen — in the language
              they speak.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link to="/dashboard" data-testid="home-cta-dashboard">
                <Button className="bg-saffron hover:bg-orange-500 text-national font-bold gap-2">
                  Open Command Dashboard <ArrowRight size={16} />
                </Button>
              </Link>
              <Link to="/sos" data-testid="home-cta-sos">
                <Button variant="outline" className="border-white/40 text-white hover:bg-white/10 bg-transparent gap-2">
                  <Siren size={16} /> Raise an SOS
                </Button>
              </Link>
              <a href="tel:1078" data-testid="home-helpline">
                <Button variant="outline" className="border-white/40 text-white hover:bg-white/10 bg-transparent gap-2">
                  <Phone size={16} /> Helpline 1078
                </Button>
              </a>
            </div>

            <div className="mt-8 grid grid-cols-3 gap-4 max-w-lg">
              <div>
                <div className="text-3xl font-heading font-extrabold text-saffron">{(stats.people_evacuated || 0).toLocaleString()}</div>
                <div className="text-[11px] uppercase tracking-widest text-white/70">People evacuated</div>
              </div>
              <div>
                <div className="text-3xl font-heading font-extrabold text-white">{stats.shelters_active || 0}</div>
                <div className="text-[11px] uppercase tracking-widest text-white/70">Shelters active</div>
              </div>
              <div>
                <div className="text-3xl font-heading font-extrabold text-white">{stats.rescue_teams_deployed || 0}</div>
                <div className="text-[11px] uppercase tracking-widest text-white/70">Rescue teams</div>
              </div>
            </div>
          </div>

          <div className="relative hidden md:block">
            <img
              src={HERO_IMG}
              alt="Rescue operation"
              className="rounded-md border-4 border-white/10 shadow-2xl w-full h-[420px] object-cover"
            />
            <div className="absolute -bottom-4 -left-4 bg-white text-national rounded-md p-4 shadow-lg border border-slate-200 max-w-[260px]">
              <div className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Explainable AI</div>
              <div className="text-sm font-semibold mt-1">Flood probability 92% — Dhemaji</div>
              <div className="text-xs text-slate-600 mt-1">Rainfall +160% • Brahmaputra rising • Similar to 2013 pattern.</div>
            </div>
          </div>
        </div>
      </section>

      {/* Features grid */}
      <section className="max-w-[1600px] mx-auto px-4 py-14">
        <SectionHeading
          eyebrow="Platform Capabilities"
          title="One command centre. Twenty AI capabilities."
          description="Every module works with real-time data streams, works offline in the field, and is designed for India's linguistic and geographic diversity."
        />
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
          {FEATURES.map((f) => (
            <Link
              key={f.title}
              to={f.to}
              data-testid={`feature-${f.title.toLowerCase().replace(/\s+/g, "-")}`}
              className="group bg-white border border-slate-200 rounded-md p-5 hover:border-national hover:shadow-sm transition-all"
            >
              <div className="w-11 h-11 rounded-md bg-national text-white flex items-center justify-center">
                <f.icon size={20} />
              </div>
              <div className="mt-4 font-heading font-bold text-national text-lg">{f.title}</div>
              <p className="text-sm text-slate-600 mt-1.5 leading-relaxed">{f.desc}</p>
              <div className="mt-3 text-sm font-semibold text-saffron flex items-center gap-1 group-hover:gap-2 transition-all">
                Open module <ArrowRight size={14} />
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* Statistics band */}
      <section className="bg-white border-y border-slate-200">
        <div className="max-w-[1600px] mx-auto px-4 py-10 grid md:grid-cols-4 gap-4">
          <StatCard label="Villages affected" value={(stats.villages_affected || 0)} sub="Across 8 states" />
          <StatCard label="Boats operational" value={stats.boats_operational || 0} sub="NDRF + State + Local" />
          <StatCard label="Predictions today" value={(stats.predictions_generated || 0).toLocaleString()} sub="Auto-generated" />
          <StatCard label="Alerts broadcast" value={stats.alerts_broadcast || 0} sub="SMS / Radio / App" accent="saffron" />
        </div>
      </section>

      {/* Trust band */}
      <section className="max-w-[1600px] mx-auto px-4 py-14">
        <div className="grid md:grid-cols-3 gap-6">
          {[
            { title: "Transparent by design", body: "Every AI prediction shows its reasoning. Every alert cites its source. Every allocation is auditable." },
            { title: "Multilingual accessibility", body: "Hindi, English and regional languages. Voice-first for low-literacy users, accessibility mode for screen readers." },
            { title: "Interoperable with the state", body: "Feeds from IMD, CWC, NDMA, state disaster authorities. Exports to SDRF dashboards over open APIs." },
          ].map((c) => (
            <div key={c.title} className="border-l-4 border-saffron pl-4 py-1">
              <div className="font-heading font-bold text-national">{c.title}</div>
              <p className="text-sm text-slate-600 mt-1 leading-relaxed">{c.body}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
