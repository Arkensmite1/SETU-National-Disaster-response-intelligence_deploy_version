import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { BellRing, Check, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Panel, SectionHeading } from "@/components/common/GovUI";
import { SafetyNote } from "@/components/setu/SetuBits";
import { apiError, setuApi } from "@/lib/setuApi";

const PRIORITY_LABEL = { 1: "P1 — life safety", 2: "P2 — operational", 3: "P3 — informational" };
const PRIORITY_COLOR = { 1: "#C62828", 2: "#EF6C00", 3: "#0A2B4E" };

export default function Notifications() {
  const [rows, setRows] = useState([]);
  const [unack, setUnack] = useState(0);

  const load = useCallback(async () => {
    try {
      const { data } = await setuApi.get("/notifications/mine");
      setRows(data.notifications || []);
      setUnack(data.unacknowledged || 0);
    } catch (e) {
      toast.error(apiError(e, "Could not load notifications"));
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [load]);

  const ack = async (id) => {
    try {
      await setuApi.post(`/notifications/${id}/ack`);
      toast.success("Acknowledged");
      load();
    } catch (e) {
      toast.error(apiError(e, "Could not acknowledge"));
    }
  };

  return (
    <div className="max-w-[1000px] mx-auto px-4 py-6 space-y-6">
      <SectionHeading
        eyebrow="Alerts & notifications"
        title={`My notifications${unack ? ` — ${unack} unacknowledged` : ""}`}
        description="Life-safety messages always appear above lower-priority ones. Acknowledging tells the sender the message was seen."
        action={
          <Button onClick={load} data-testid="notifications-refresh"
                  className="bg-national text-white gap-2 h-9 text-xs">
            <RefreshCw size={14} /> Refresh
          </Button>
        }
      />

      {!rows.length ? (
        <SafetyNote>
          You have no notifications. An empty inbox is not an all-clear — keep following official
          instructions and check your area status.
        </SafetyNote>
      ) : (
        <Panel title="Inbox" action={<BellRing size={14} className="text-national" />}>
          <div className="space-y-2" data-testid="notifications-list">
            {rows.map((n) => (
              <div key={n.notificationId}
                   data-testid={`notification-${n.notificationId}`}
                   className={`border rounded-md p-3 ${n.acknowledged ? "border-slate-200" : "border-slate-300 bg-slate-50"}`}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase text-white"
                          style={{ backgroundColor: PRIORITY_COLOR[n.priority] || "#64748B" }}>
                      {PRIORITY_LABEL[n.priority] || "P3"}
                    </span>
                    <span className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">
                      {n.type?.replace(/_/g, " ")}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-slate-500">
                      {n.delivered ? "delivered" : "not delivered"}
                      {n.acknowledged ? " • acknowledged" : ""}
                      {n.escalated ? " • escalated" : ""}
                    </span>
                    {!n.acknowledged && (
                      <Button onClick={() => ack(n.notificationId)}
                              data-testid={`ack-${n.notificationId}`}
                              className="h-7 text-[11px] bg-national text-white gap-1">
                        <Check size={12} /> Acknowledge
                      </Button>
                    )}
                  </div>
                </div>
                <p className="text-sm text-slate-700 mt-2">{n.message}</p>
                {n.relevance && (
                  <p className="text-[11px] text-slate-500 mt-1">{n.relevance.message}</p>
                )}
                <div className="text-[10px] text-slate-400 mt-1">
                  {n.createdAt ? new Date(n.createdAt).toLocaleString() : ""}
                  {n.objectId ? ` • ${n.objectType} ${n.objectId}` : ""}
                </div>
              </div>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}
