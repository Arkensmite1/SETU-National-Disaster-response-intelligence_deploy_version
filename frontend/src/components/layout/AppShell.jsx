import React, { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  ShieldAlert, Menu, X, Phone, Waves, Map as MapIcon, Brain, Package,
  Home as HomeIcon, MessagesSquare, Camera, Users2, Radio, HeartPulse,
  IndianRupee, BookOpen, Bird, Cpu, ClipboardList, Siren, Search, GaugeCircle,
  LogIn, LogOut, ShieldCheck, Truck, Tent, UserCircle2,
} from "lucide-react";
import AlertTicker from "./AlertTicker";
import { Button } from "../ui/button";
import { ROLE_LABEL, useAuth } from "@/context/AuthContext";

const PUBLIC_NAV = [
  { to: "/", label: "Home", icon: HomeIcon },
  { to: "/shelters", label: "Shelters", icon: Waves },
  { to: "/preparedness", label: "Preparedness", icon: BookOpen },
  { to: "/chatbot", label: "AI Assistant", icon: MessagesSquare },
];

const CITIZEN_NAV = [
  { to: "/citizen", label: "My Dashboard", icon: HomeIcon },
  { to: "/citizen/sos", label: "Send SOS", icon: Siren },
  { to: "/citizen/shelters", label: "Find Shelter", icon: Waves },
  { to: "/notifications", label: "Alerts", icon: Radio },
  { to: "/preparedness", label: "Preparedness", icon: BookOpen },
  { to: "/chatbot", label: "AI Assistant", icon: MessagesSquare },
];

const LEADER_NAV = [
  { to: "/rescue/leader", label: "Command Centre", icon: Siren },
  { to: "/rescue/member", label: "Field View", icon: Users2 },
  { to: "/rescue/search", label: "Search Ops", icon: Search },
  { to: "/notifications", label: "Alerts", icon: Radio },
  { to: "/map", label: "Live Map", icon: MapIcon },
  { to: "/prediction", label: "Risk Advisory", icon: Brain },
  { to: "/rescue-routes", label: "Route Advisory", icon: MapIcon },
  { to: "/incidents", label: "Incident Feed", icon: ClipboardList },
  { to: "/chatbot", label: "AI Assistant", icon: MessagesSquare },
];

const MEMBER_NAV = [
  { to: "/rescue/member", label: "My Assignments", icon: Siren },
  { to: "/rescue/search", label: "Search Ops", icon: Search },
  { to: "/notifications", label: "Alerts", icon: Radio },
  { to: "/map", label: "Live Map", icon: MapIcon },
  { to: "/chatbot", label: "AI Assistant", icon: MessagesSquare },
];

const SHELTER_NAV = [
  { to: "/shelter-admin", label: "Shelter Portal", icon: Tent },
  { to: "/notifications", label: "Alerts", icon: Radio },
  { to: "/shelters", label: "Shelter Directory", icon: Waves },
];

const NGO_NAV = [
  { to: "/ngo", label: "NGO Portal", icon: Truck },
  { to: "/notifications", label: "Alerts", icon: Radio },
  { to: "/resources", label: "Relief Resources", icon: Package },
];

const ADMIN_NAV = [
  { to: "/admin", label: "Authority Portal", icon: ShieldCheck },
  { to: "/admin/situation-report", label: "Situation Report", icon: ClipboardList },
  { to: "/admin/ingestion", label: "Source & Alerts", icon: Radio },
  { to: "/admin/conflicts", label: "Conflicts", icon: GaugeCircle },
  { to: "/rescue/search", label: "Search Ops", icon: Search },
  { to: "/shelter-admin", label: "Shelters Admin", icon: Tent },
  { to: "/ngo", label: "Relief", icon: Truck },
  { to: "/notifications", label: "Alerts", icon: Radio },
  { to: "/dashboard", label: "Dashboard", icon: GaugeCircle },
  { to: "/map", label: "Live Map", icon: MapIcon },
  { to: "/rescue/leader", label: "Rescue Command", icon: Siren },
  { to: "/prediction", label: "Risk Advisory", icon: Brain },
  { to: "/resources", label: "Resources", icon: Package },
  { to: "/shelters", label: "Shelters", icon: Waves },
  { to: "/damage", label: "Damage & Vision", icon: Camera },
  { to: "/simulation", label: "Simulation", icon: Cpu },
  { to: "/incidents", label: "Incidents", icon: ClipboardList },
  { to: "/volunteers", label: "Volunteers", icon: Users2 },
  { to: "/social", label: "Social Intel", icon: Radio },
  { to: "/medical", label: "Health Outlook", icon: HeartPulse },
  { to: "/economic", label: "Economic Loss", icon: IndianRupee },
  { to: "/drones", label: "Drone Ops", icon: Bird },
  { to: "/chatbot", label: "AI Assistant", icon: MessagesSquare },
];

const NAV_FOR_ROLE = {
  USER: CITIZEN_NAV,
  RESCUE_LEADER: LEADER_NAV,
  RESCUE_MEMBER: MEMBER_NAV,
  SHELTER_ADMIN: SHELTER_NAV,
  NGO_ADMIN: NGO_NAV,
  AUTHORITY: ADMIN_NAV,
  SUPER_ADMIN: ADMIN_NAV,
};

export default function AppShell() {
  const [open, setOpen] = useState(false);
  const [lang, setLang] = useState("EN");
  const loc = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  useEffect(() => { setOpen(false); }, [loc.pathname]);

  const NAV = user ? NAV_FOR_ROLE[user.role] || PUBLIC_NAV : PUBLIC_NAV;
  const showSos = !user || user.role === "USER";

  const doLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#F4F6FA]">
      {/* Tricolour strip */}
      <div className="gov-strip" data-testid="gov-tricolour-strip" />

      {/* Meta bar */}
      <div className="bg-national text-white text-xs">
        <div className="max-w-[1600px] mx-auto px-4 py-1.5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="opacity-90">भारत सरकार | Government of India</span>
            <span className="opacity-60">•</span>
            <span className="opacity-90 hidden sm:inline">Ministry of Home Affairs — NDMA</span>
          </div>
          <div className="flex items-center gap-4">
            <button
              data-testid="lang-toggle-btn"
              onClick={() => setLang(lang === "EN" ? "हिं" : "EN")}
              className="hover:text-saffron transition-colors"
            >
              A- | A | A+ &nbsp; • &nbsp; {lang === "EN" ? "English | हिन्दी" : "हिन्दी | English"}
            </button>
            <a href="#skip" className="hidden md:inline hover:text-saffron">Skip to main content</a>
          </div>
        </div>
      </div>

      {/* Main header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30">
        <div className="max-w-[1600px] mx-auto px-4 py-3 flex items-center gap-4">
          <Link to="/" data-testid="brand-home-link" className="flex items-center gap-3 shrink-0">
            <div className="w-11 h-11 rounded-full bg-national flex items-center justify-center border-2 border-saffron">
              <ShieldAlert size={22} className="text-white" />
            </div>
            <div className="leading-tight">
              <div className="font-heading font-extrabold text-national text-lg">SETU</div>
              <div className="text-[10px] uppercase tracking-widest text-slate-500 font-semibold">
                National Disaster Response Intelligence
              </div>
            </div>
          </Link>

          <div className="flex-1 hidden xl:flex items-center max-w-sm ml-6">
            <div className="w-full relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                data-testid="header-search"
                className="w-full pl-9 pr-3 py-2 text-sm border border-slate-200 rounded-md focus:outline-none focus:border-national bg-slate-50"
                placeholder="Search villages, rivers, alerts…"
              />
            </div>
          </div>

          <div className="ml-auto flex items-center gap-2">
            <a
              href="tel:1078"
              data-testid="helpline-1078-link"
              className="hidden md:flex items-center gap-2 px-3 py-2 rounded-md border border-slate-200 hover:border-national text-sm text-national font-semibold"
            >
              <Phone size={14} /> 1078
            </a>

            {showSos && (
              <Link to={user ? "/citizen/sos" : "/login"} data-testid="sos-header-btn">
                <Button className="text-white gap-2 font-bold" style={{ backgroundColor: "#C62828" }}>
                  <Siren size={16} /> SOS
                </Button>
              </Link>
            )}

            {user ? (
              <div className="flex items-center gap-2">
                <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-md border border-slate-200"
                     data-testid="user-chip">
                  <UserCircle2 size={16} className="text-national" />
                  <div className="leading-tight">
                    <div className="text-[12px] font-bold text-national">{user.name || user.mobile}</div>
                    <div className="text-[10px] uppercase tracking-widest text-slate-500">
                      {ROLE_LABEL[user.role] || user.role}
                    </div>
                  </div>
                </div>
                <Button onClick={doLogout} data-testid="logout-button"
                        className="bg-white border border-slate-300 text-slate-700 hover:bg-slate-50 gap-2">
                  <LogOut size={15} /> <span className="hidden sm:inline">Sign out</span>
                </Button>
              </div>
            ) : (
              <Link to="/login" data-testid="header-login-link">
                <Button className="bg-national text-white gap-2 font-semibold">
                  <LogIn size={15} /> Sign in
                </Button>
              </Link>
            )}

            <button
              data-testid="mobile-menu-toggle"
              className="lg:hidden p-2 rounded-md border border-slate-200"
              onClick={() => setOpen(v => !v)}
            >
              {open ? <X size={18} /> : <Menu size={18} />}
            </button>
          </div>
        </div>

        {/* Sub-nav */}
        <nav className="border-t border-slate-100 bg-white hidden lg:block">
          <div className="max-w-[1600px] mx-auto px-4">
            <ul className="flex items-center gap-1 overflow-x-auto">
              {NAV.map(({ to, label, icon: Icon }) => (
                <li key={to}>
                  <NavLink
                    to={to}
                    end={to === "/"}
                    data-testid={`nav-${label.toLowerCase().replace(/\s+/g, "-")}`}
                    className={({ isActive }) =>
                      `flex items-center gap-2 px-3 py-2.5 text-[13px] font-semibold whitespace-nowrap border-b-2 transition-colors ${
                        isActive
                          ? "border-saffron text-national"
                          : "border-transparent text-slate-600 hover:text-national hover:border-slate-300"
                      }`
                    }
                  >
                    <Icon size={14} />
                    {label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        </nav>

        {/* Mobile menu */}
        {open && (
          <nav className="lg:hidden border-t border-slate-100 bg-white max-h-[70vh] overflow-y-auto" data-testid="mobile-nav">
            <ul className="px-2 py-2">
              {NAV.map(({ to, label, icon: Icon }) => (
                <li key={to}>
                  <NavLink
                    to={to}
                    end={to === "/"}
                    className={({ isActive }) =>
                      `flex items-center gap-3 px-3 py-2.5 text-sm rounded-md ${
                        isActive ? "bg-national text-white" : "text-slate-700 hover:bg-slate-100"
                      }`
                    }
                  >
                    <Icon size={16} /> {label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        )}
      </header>

      <AlertTicker />

      <main id="skip" className="flex-1">
        <Outlet />
      </main>

      <footer className="mt-8 border-t border-slate-200 bg-white">
        <div className="max-w-[1600px] mx-auto px-4 py-8 grid md:grid-cols-4 gap-6 text-sm text-slate-600">
          <div>
            <div className="font-heading font-bold text-national mb-2">SETU</div>
            <p className="leading-relaxed">
              Last-mile disaster response and coordination platform. Authoritative disaster
              information is consumed from an NDEM / authorized disaster-information integration —
              SETU coordinates the response, it does not predict disasters.
            </p>
          </div>
          <div>
            <div className="font-semibold text-national mb-2">Helplines</div>
            <ul className="space-y-1">
              <li>NDMA — 1078</li>
              <li>Ambulance — 108</li>
              <li>Police — 100</li>
              <li>Women — 181</li>
            </ul>
          </div>
          <div>
            <div className="font-semibold text-national mb-2">Related</div>
            <ul className="space-y-1">
              <li>ndma.gov.in</li>
              <li>mausam.imd.gov.in</li>
              <li>cwc.gov.in</li>
              <li>mygov.in</li>
            </ul>
          </div>
          <div>
            <div className="font-semibold text-national mb-2">Statement</div>
            <p className="text-xs leading-relaxed">
              This is a demonstration prototype for public safety innovation. All data shown
              is illustrative. In a real emergency call 1078.
            </p>
          </div>
        </div>
        <div className="border-t border-slate-100 py-3 text-xs text-slate-500 text-center">
          © {new Date().getFullYear()} SETU • Emergent Hackathon Prototype
        </div>
      </footer>
    </div>
  );
}
