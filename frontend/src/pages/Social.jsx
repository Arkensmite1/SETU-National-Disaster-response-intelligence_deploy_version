import React, { useEffect, useState } from "react";
import { api, endpoints } from "@/lib/api";
import { SectionHeading, Panel, StatusBadge } from "@/components/common/GovUI";
import { CheckCircle2, AlertCircle } from "lucide-react";

export default function Social() {
  const [posts, setPosts] = useState([]);
  useEffect(() => { api.get(endpoints.social).then(r => setPosts(r.data.posts || [])).catch(() => {}); }, []);

  return (
    <div className="max-w-[1600px] mx-auto px-4 py-6">
      <SectionHeading eyebrow="Module 12" title="AI Social Media Monitoring" description="Twitter/X, Facebook and News feeds — auto-clustered by topic and location, verified against official sources." />

      <Panel title="Live signal feed">
        <ul className="space-y-3">
          {posts.map((p) => (
            <li key={p.id} className="border-l-4 pl-3 py-1" style={{ borderColor: p.priority === "critical" ? "#C62828" : p.priority === "high" ? "#EF6C00" : "#0A2B4E" }} data-testid={`social-${p.id}`}>
              <div className="flex items-center justify-between">
                <div className="text-xs text-slate-500">
                  <b className="text-national">{p.handle}</b> • {p.source} • {p.time} • {p.location}
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge status={p.priority} />
                  {p.verified ? (
                    <span className="text-xs text-indiagreen flex items-center gap-1"><CheckCircle2 size={12} /> Verified</span>
                  ) : (
                    <span className="text-xs text-status-warning flex items-center gap-1" style={{ color: "#EF6C00" }}><AlertCircle size={12} /> Unverified</span>
                  )}
                </div>
              </div>
              <p className="text-sm mt-1">{p.text}</p>
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}
