import React from "react";
import { AlertTriangle, Bot, Clock, Wifi, WifiOff } from "lucide-react";

export const SOS_STAGES = [
  "CREATED", "RECEIVED", "VERIFIED", "PENDING", "ASSIGNED", "ACCEPTED",
  "EN_ROUTE", "ARRIVED", "RESCUING", "RESCUED", "COMPLETED",
];

export const STAGE_MEANING = {
  CREATED: "You pressed SOS on your device",
  QUEUED_OFFLINE: "Saved on your device — network unavailable, not yet sent",
  RECEIVED: "SETU has acknowledged receipt — no team assigned yet",
  VERIFIED: "Validated and de-duplicated",
  PENDING: "In the rescue queue, awaiting team assignment",
  ASSIGNED: "A team has been selected — waiting for the team to accept",
  ACCEPTED: "Team confirmed and preparing to move",
  EN_ROUTE: "Team is travelling to you",
  ARRIVED: "Team is on site",
  RESCUING: "Rescue in progress",
  SEARCHING: "Team is searching the area",
  USER_NOT_FOUND: "Not located yet — search and verification is running",
  NOT_FOUND: "Search closed without locating — escalated for verification",
  RESCUED: "Reported safe by the rescue team",
  COMPLETED: "Case closed with a rescue report",
  CANCELLED_BY_USER: "Cancelled by you — record and audit trail retained",
  DUPLICATE: "Merged into your existing active case",
  FALSE_ALARM: "Team reported no emergency found — recorded, not deleted",
  ALREADY_RESCUED: "Already rescued by another team",
  TIMEOUT: "Team did not respond — flagged for reassignment",
};

const PRIORITY_COLOR = { P1: "#C62828", P2: "#EF6C00", P3: "#0A2B4E" };

export function PriorityBadge({ priority }) {
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold uppercase tracking-wide text-white"
      style={{ backgroundColor: PRIORITY_COLOR[priority] || "#64748B" }}
      data-testid={`priority-badge-${priority}`}
    >
      {priority} {priority === "P1" ? "Critical" : priority === "P2" ? "High" : "Normal"}
    </span>
  );
}

const STATUS_COLOR = {
  CREATED: "#64748B", QUEUED_OFFLINE: "#F9A825", RECEIVED: "#0A2B4E", VERIFIED: "#0A2B4E",
  PENDING: "#EF6C00", ASSIGNED: "#F9A825", ACCEPTED: "#2E7D32", EN_ROUTE: "#2E7D32",
  ARRIVED: "#2E7D32", RESCUING: "#2E7D32", SEARCHING: "#EF6C00", RESCUED: "#138808",
  COMPLETED: "#455A64", CANCELLED_BY_USER: "#78909C", DUPLICATE: "#78909C",
  FALSE_ALARM: "#78909C", USER_NOT_FOUND: "#C62828", NOT_FOUND: "#C62828",
  ALREADY_RESCUED: "#455A64", TIMEOUT: "#C62828",
};

export function StateBadge({ status }) {
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold uppercase tracking-wide text-white"
      style={{ backgroundColor: STATUS_COLOR[status] || "#64748B" }}
      data-testid={`state-badge-${status}`}
    >
      {String(status || "").replace(/_/g, " ")}
    </span>
  );
}

export function StateTracker({ status }) {
  const idx = SOS_STAGES.indexOf(status);
  const branch = idx === -1;
  return (
    <div data-testid="sos-state-tracker">
      <div className="flex flex-wrap gap-1.5">
        {SOS_STAGES.map((s, i) => {
          const done = !branch && i < idx;
          const active = !branch && i === idx;
          return (
            <span
              key={s}
              className={`px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wide border ${
                active
                  ? "bg-national text-white border-national"
                  : done
                  ? "bg-slate-200 text-slate-700 border-slate-300"
                  : "bg-white text-slate-400 border-slate-200"
              }`}
            >
              {s.replace(/_/g, " ")}
            </span>
          );
        })}
      </div>
      <p className="text-xs text-slate-600 mt-2">
        <strong>{String(status || "").replace(/_/g, " ")}</strong> — {STAGE_MEANING[status] || "Status update"}
      </p>
      {branch && status && (
        <p className="text-[11px] text-slate-500 mt-1">
          This case followed an alternative branch of the SOS state machine. The record is retained in full.
        </p>
      )}
    </div>
  );
}

export function AdvisoryNote({ children, title = "AI advisory — human confirmation required" }) {
  return (
    <div
      className="flex gap-3 p-3 rounded-md border border-slate-200 bg-slate-50"
      data-testid="ai-advisory-note"
    >
      <Bot size={16} className="text-national mt-0.5 shrink-0" />
      <div>
        <div className="text-[11px] font-bold uppercase tracking-widest text-slate-500">{title}</div>
        <div className="text-sm text-slate-700 whitespace-pre-wrap mt-1">{children}</div>
        <div className="text-[11px] text-slate-500 mt-2">
          AI never declares, confirms or overrides a disaster or a safety-critical decision.
        </div>
      </div>
    </div>
  );
}

export function StalenessNote({ notice, stale }) {
  if (!notice) return null;
  return (
    <div
      className={`flex items-center gap-2 text-[11px] font-semibold ${stale ? "text-status-critical" : "text-slate-500"}`}
      style={stale ? { color: "#C62828" } : undefined}
      data-testid="staleness-note"
    >
      <Clock size={12} /> {notice}
    </div>
  );
}

export function NetworkBadge({ mode, queued = 0 }) {
  const map = {
    FULL: { label: "Network: Full", color: "#2E7D32", Icon: Wifi },
    DEGRADED: { label: "Network: Degraded", color: "#F9A825", Icon: Wifi },
    OFFLINE: { label: "Network: Offline", color: "#C62828", Icon: WifiOff },
  };
  const { label, color, Icon } = map[mode] || map.FULL;
  return (
    <span
      className="inline-flex items-center gap-1.5 px-2 py-1 rounded text-[11px] font-bold uppercase tracking-wide text-white"
      style={{ backgroundColor: color }}
      data-testid="network-mode-badge"
    >
      <Icon size={12} /> {label}
      {queued > 0 ? ` • ${queued} queued` : ""}
    </span>
  );
}

export function LocationQuality({ quality }) {
  if (!quality) return null;
  return (
    <div className="text-[11px] text-slate-600" data-testid="location-quality">
      <strong>{quality.label}</strong>
      {quality.source ? ` • source ${quality.source}` : ""}
      {quality.accuracyMetres ? ` • ±${Math.round(quality.accuracyMetres)} m` : " • accuracy unknown"}
    </div>
  );
}

export function SafetyNote({ children }) {
  return (
    <div
      className="flex gap-2 p-3 rounded-md border border-amber-200 bg-amber-50 text-[12px] text-slate-700"
      data-testid="safety-note"
    >
      <AlertTriangle size={14} className="mt-0.5 shrink-0" style={{ color: "#EF6C00" }} />
      <div>{children}</div>
    </div>
  );
}
