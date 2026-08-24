import React from "react";

export function StatusBadge({ status }) {
  const map = {
    safe: { bg: "#2E7D32", label: "Safe" },
    watch: { bg: "#F9A825", label: "Watch" },
    warning: { bg: "#EF6C00", label: "Warning" },
    critical: { bg: "#C62828", label: "Critical" },
    high: { bg: "#EF6C00", label: "High" },
    medium: { bg: "#F9A825", label: "Medium" },
    low: { bg: "#64748B", label: "Low" },
    info: { bg: "#0A2B4E", label: "Info" },
    verified: { bg: "#2E7D32", label: "Verified" },
    unverified: { bg: "#F9A825", label: "Unverified" },
  };
  const s = map[status] || { bg: "#64748B", label: status };
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold uppercase tracking-wide"
      style={{ backgroundColor: s.bg, color: s.bg === "#F9A825" ? "#0F172A" : "#fff" }}
      data-testid={`status-badge-${status}`}
    >
      {s.label}
    </span>
  );
}

export function StatCard({ label, value, sub, icon: Icon, accent = "national" }) {
  const accents = {
    national: "text-national",
    saffron: "text-saffron",
    green: "text-indiagreen",
    red: "text-status-critical",
  };
  return (
    <div className="bg-white border border-slate-200 rounded-md p-4" data-testid={`stat-${label.toLowerCase().replace(/\s+/g, "-")}`}>
      <div className="flex items-start justify-between">
        <div>
          <div className="text-[11px] font-bold uppercase tracking-widest text-slate-500">{label}</div>
          <div className={`text-3xl font-heading font-extrabold mt-1 ${accents[accent] || "text-national"}`}>{value}</div>
          {sub && <div className="text-xs text-slate-500 mt-1">{sub}</div>}
        </div>
        {Icon && (
          <div className="w-9 h-9 rounded-md bg-slate-100 flex items-center justify-center">
            <Icon size={18} className="text-national" />
          </div>
        )}
      </div>
    </div>
  );
}

export function SectionHeading({ eyebrow, title, description, action }) {
  return (
    <div className="flex flex-col md:flex-row md:items-end justify-between gap-3 mb-4">
      <div>
        {eyebrow && (
          <div className="text-[11px] font-bold uppercase tracking-widest text-saffron mb-1">
            {eyebrow}
          </div>
        )}
        <h2 className="text-2xl md:text-3xl font-heading font-extrabold text-national tracking-tight">
          {title}
        </h2>
        {description && <p className="text-sm text-slate-600 mt-1 max-w-2xl">{description}</p>}
      </div>
      {action}
    </div>
  );
}

export function Panel({ title, action, children, className = "" }) {
  return (
    <div className={`bg-white border border-slate-200 rounded-md ${className}`}>
      {(title || action) && (
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
          <h3 className="font-heading font-bold text-national text-sm uppercase tracking-wider">{title}</h3>
          {action}
        </div>
      )}
      <div className="p-4">{children}</div>
    </div>
  );
}
