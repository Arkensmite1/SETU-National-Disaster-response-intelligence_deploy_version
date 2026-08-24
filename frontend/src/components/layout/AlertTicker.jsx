import React, { useEffect, useState } from "react";
import { api, endpoints } from "../../lib/api";
import { AlertTriangle, Info } from "lucide-react";

const colorFor = (level) =>
  level === "critical" ? "bg-status-critical text-white" :
  level === "warning" ? "bg-status-warning text-white" :
  level === "watch" ? "bg-status-watch text-slate-900" :
  "bg-national text-white";

export default function AlertTicker() {
  const [alerts, setAlerts] = useState([]);

  useEffect(() => {
    api.get(endpoints.ticker).then((r) => setAlerts(r.data.alerts || [])).catch(() => {});
  }, []);

  if (!alerts.length) return null;

  const critical = alerts.find(a => a.level === "critical") || alerts[0];

  return (
    <div className="ticker-wrap flex items-stretch" data-testid="alert-ticker" style={{ backgroundColor: "#C62828" }}>
      <div className="flex items-center gap-2 px-4 py-2 bg-[#7f1d1d] text-white font-bold text-xs uppercase tracking-widest shrink-0">
        <AlertTriangle size={14} className="animate-blink" /> Live Alerts
      </div>
      <div className="ticker-wrap flex-1 py-2 text-white text-sm">
        <div className="ticker-track">
          {[...alerts, ...alerts].map((a, i) => (
            <span key={i} className="inline-flex items-center gap-2">
              <span className={`inline-block w-2 h-2 rounded-full ${a.level === "critical" ? "bg-white animate-blink" : "bg-white/70"}`} />
              {a.text}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
