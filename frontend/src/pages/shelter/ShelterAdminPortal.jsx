import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, ArrowRightLeft, PackagePlus, RefreshCw, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Panel, SectionHeading, StatCard } from "@/components/common/GovUI";
import { NetworkBadge, SafetyNote, StalenessNote, StateBadge } from "@/components/setu/SetuBits";
import { apiError, setuApi } from "@/lib/setuApi";
import { networkMode } from "@/lib/offlineQueue";
import { useAuth } from "@/context/AuthContext";

const field = "w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:border-national";
const QUEUE_KEY = "setu.shelterLogQueue";

const readQueue = () => {
  try { return JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]"); } catch { return []; }
};
const writeQueue = (v) => localStorage.setItem(QUEUE_KEY, JSON.stringify(v));

export default function ShelterAdminPortal() {
  const { user } = useAuth();
  const [shelters, setShelters] = useState([]);
  const [shelterId, setShelterId] = useState(user?.shelterId || "");
  const [shelter, setShelter] = useState(null);
  const [requirements, setRequirements] = useState([]);
  const [alternatives, setAlternatives] = useState([]);
  const [count, setCount] = useState(1);
  const [note, setNote] = useState("");
  const [mode, setMode] = useState(networkMode());
  const [queued, setQueued] = useState(readQueue().length);
  const [req, setReq] = useState({ category: "FOOD", unit: "packets", requestedQuantity: 500 });
  const [transfer, setTransfer] = useState({ toShelterId: "", count: 1, reason: "" });
  const [busy, setBusy] = useState(false);

  const loadList = useCallback(async () => {
    try {
      const { data } = await setuApi.get("/shelters/list");
      setShelters(data.shelters || []);
      if (!shelterId && data.shelters?.length) setShelterId(user?.shelterId || data.shelters[0].shelterId);
    } catch (e) {
      toast.error(apiError(e, "Could not load shelters"));
    }
  }, [shelterId, user]);

  const loadOne = useCallback(async () => {
    if (!shelterId) return;
    try {
      const { data } = await setuApi.get(`/shelters/${shelterId}`);
      setShelter(data);
      setAlternatives(data.alternatives || []);
      const r = await setuApi.get(`/shelters/${shelterId}/requirements`);
      setRequirements(r.data.requests || []);
    } catch (e) {
      toast.error(apiError(e, "Could not load shelter"));
    }
  }, [shelterId]);

  useEffect(() => { loadList(); }, [loadList]);
  useEffect(() => { loadOne(); }, [loadOne]);
  useEffect(() => {
    const onNet = () => setMode(networkMode());
    window.addEventListener("online", onNet);
    window.addEventListener("offline", onNet);
    return () => {
      window.removeEventListener("online", onNet);
      window.removeEventListener("offline", onNet);
    };
  }, []);

  const move = async (direction) => {
    const n = Math.abs(Number(count) || 0);
    if (!n) return toast.error("Enter how many people");
    if (mode === "OFFLINE") {
      const q = [...readQueue(), { shelterId, count: direction === "in" ? n : -n,
                                   note, occurredAt: new Date().toISOString() }];
      writeQueue(q);
      setQueued(q.length);
      return toast.warning("Saved on this device with its original time — not yet recorded at SETU");
    }
    setBusy(true);
    try {
      const path = direction === "in" ? "arrivals" : "departures";
      const { data } = await setuApi.post(`/shelters/${shelterId}/${path}`, {
        count: n, note: note || null, expectedOccupancy: shelter?.occupancy ?? null,
      });
      setShelter(data);
      setAlternatives(data.alternatives || []);
      setNote("");
      toast.success(`Recorded — occupancy now ${data.occupancy}/${data.capacity}`);
      loadList();
    } catch (e) {
      const d = e?.response?.data?.detail;
      if (d && typeof d === "object") {
        toast.error(d.message || "Update rejected");
        if (d.alternatives) setAlternatives(d.alternatives);
        loadOne();
      } else {
        toast.error(apiError(e, "Update failed"));
      }
    } finally {
      setBusy(false);
    }
  };

  const forceOverflow = async () => {
    try {
      const { data } = await setuApi.post(`/shelters/${shelterId}/arrivals`, {
        count: Math.abs(Number(count) || 1), allowOverflow: true,
        note: note || "Explicit over-capacity intake",
      });
      setShelter(data);
      toast.warning("Recorded as OVER_CAPACITY — this is visible to the authority");
      loadList();
    } catch (e) {
      toast.error(apiError(e, "Could not record over-capacity intake"));
    }
  };

  const syncQueued = async () => {
    const q = readQueue().filter((i) => i.shelterId === shelterId);
    if (!q.length) return;
    try {
      const { data } = await setuApi.post(`/shelters/${shelterId}/sync-offline`, { entries: q });
      writeQueue(readQueue().filter((i) => i.shelterId !== shelterId));
      setQueued(readQueue().length);
      setShelter(data.shelter);
      toast.success(`${data.applied} offline log(s) applied, ${data.rejected.length} rejected`);
    } catch (e) {
      toast.error(apiError(e, "Sync failed — logs are still on this device"));
    }
  };

  const setStatus = async (status) => {
    const reason = status === "CLOSED"
      ? window.prompt("Closure reason (required so people can be redirected)") : null;
    if (status === "CLOSED" && !reason) return;
    try {
      const { data } = await setuApi.post(`/shelters/${shelterId}/status`, { status, reason });
      setShelter(data);
      setAlternatives(data.alternatives || []);
      toast.success(`Status set to ${status}`);
      loadList();
    } catch (e) {
      toast.error(apiError(e, "Status change rejected"));
    }
  };

  const raiseRequirement = async () => {
    try {
      await setuApi.post(`/shelters/${shelterId}/requirements`, {
        ...req, requestedQuantity: Number(req.requestedQuantity) || 0,
      });
      toast.success("Requirement raised — awaiting authority approval");
      loadOne();
    } catch (e) {
      toast.error(apiError(e, "Could not raise requirement"));
    }
  };

  const doTransfer = async () => {
    if (!transfer.toShelterId || !transfer.reason) return toast.error("Choose a destination and give a reason");
    try {
      const { data } = await setuApi.post(`/shelters/${shelterId}/transfer`, {
        ...transfer, count: Number(transfer.count) || 1,
      });
      setShelter(data.from);
      toast.success(`${data.transferred} people transferred to ${transfer.toShelterId}`);
      loadList();
    } catch (e) {
      const d = e?.response?.data?.detail;
      toast.error(typeof d === "object" ? d.message : apiError(e, "Transfer failed"));
      if (typeof d === "object" && d.alternatives) setAlternatives(d.alternatives);
    }
  };

  return (
    <div className="max-w-[1500px] mx-auto px-4 py-6 space-y-6">
      <SectionHeading
        eyebrow="Shelter management"
        title={shelter ? shelter.name : "Shelter portal"}
        description="Occupancy, capacity, resource requirements and transfers. Availability is always derived, never stored."
        action={
          <div className="flex flex-wrap items-center gap-2">
            <NetworkBadge mode={mode} queued={queued} />
            <select className="px-2 py-1.5 border border-slate-200 rounded-md text-xs"
                    data-testid="shelter-select" value={shelterId}
                    onChange={(e) => setShelterId(e.target.value)}>
              {shelters.map((s) => <option key={s.shelterId} value={s.shelterId}>{s.name}</option>)}
            </select>
            <Button onClick={() => { loadOne(); loadList(); }} data-testid="shelter-refresh"
                    className="bg-national text-white gap-2 h-9 text-xs">
              <RefreshCw size={14} /> Refresh
            </Button>
          </div>
        }
      />

      {queued > 0 && (
        <div className="flex items-center justify-between gap-3 p-3 rounded-md border border-amber-200 bg-amber-50">
          <div className="text-sm text-slate-700">
            <strong>{queued} offline log(s)</strong> saved on this device with their original times.
          </div>
          <Button onClick={syncQueued} className="bg-national text-white gap-2" data-testid="shelter-sync-button">
            <Upload size={14} /> Upload logs
          </Button>
        </div>
      )}

      {shelter && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
            <StatCard label="Capacity" value={shelter.capacity} />
            <StatCard label="Occupancy" value={shelter.occupancy} accent="saffron" />
            <StatCard label="Available (derived)" value={shelter.available} accent="green" />
            <StatCard label="Overflow" value={shelter.overflow} accent="red" />
            <StatCard label="Open requirements"
                      value={requirements.filter((r) => !"DISTRIBUTED REJECTED CANCELLED".includes(r.status)).length} />
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <StateBadge status={shelter.status} />
            <StalenessNote notice={shelter.stalenessNotice} stale={shelter.stale} />
            {shelter.occupancyConflict && !shelter.occupancyConflict.resolved && (
              <span className="flex items-center gap-1 text-[11px] font-bold uppercase" style={{ color: "#C62828" }}>
                <AlertTriangle size={12} /> occupancy conflict awaiting resolution
              </span>
            )}
          </div>

          <div className="grid xl:grid-cols-3 gap-6">
            <Panel title="Record arrivals and departures">
              <div className="space-y-2">
                <input type="number" min={1} className={field} data-testid="occupancy-count-input"
                       value={count} onChange={(e) => setCount(e.target.value)} />
                <input className={field} placeholder="Note (optional)" value={note}
                       onChange={(e) => setNote(e.target.value)} />
                <div className="flex gap-2">
                  <Button disabled={busy} onClick={() => move("in")} data-testid="arrivals-button"
                          className="flex-1 bg-national text-white">People arrived</Button>
                  <Button disabled={busy} onClick={() => move("out")} data-testid="departures-button"
                          className="flex-1 bg-white border border-slate-300 text-slate-700">People left</Button>
                </div>
                {shelter.available <= 0 && (
                  <Button onClick={forceOverflow} data-testid="overflow-button"
                          className="w-full text-white text-xs" style={{ backgroundColor: "#EF6C00" }}>
                    Record over-capacity intake explicitly
                  </Button>
                )}
                <p className="text-[11px] text-slate-500">
                  The last place can only be given once — concurrent updates are rejected and both
                  values are kept for review.
                </p>
              </div>
            </Panel>

            <Panel title="Shelter status">
              <div className="grid grid-cols-2 gap-2">
                {["OPEN", "NEAR_CAPACITY", "FULL", "OVER_CAPACITY", "CLOSED"].map((s) => (
                  <Button key={s} onClick={() => setStatus(s)} data-testid={`shelter-status-${s}`}
                          className={`text-xs ${shelter.status === s
                            ? "bg-national text-white" : "bg-white border border-slate-300 text-slate-700"}`}>
                    {s.replace(/_/g, " ")}
                  </Button>
                ))}
              </div>
              {!!alternatives.length && (
                <div className="mt-3" data-testid="shelter-alternatives">
                  <div className="text-[11px] font-bold uppercase tracking-widest text-slate-500 mb-1">
                    Alternatives with space
                  </div>
                  <ul className="text-xs space-y-1">
                    {alternatives.map((a) => (
                      <li key={a.shelterId} className="border border-slate-200 rounded p-2">
                        <strong>{a.name}</strong> — {a.available} place(s) free
                        {a.distanceKm !== null && a.distanceKm !== undefined ? ` • ${a.distanceKm} km` : ""}
                        <div className="text-[10px] text-slate-500">{a.stalenessNotice}</div>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </Panel>

            <Panel title="Transfer occupants" action={<ArrowRightLeft size={14} className="text-national" />}>
              <div className="space-y-2">
                <select className={field} data-testid="transfer-destination"
                        value={transfer.toShelterId}
                        onChange={(e) => setTransfer({ ...transfer, toShelterId: e.target.value })}>
                  <option value="">Select destination shelter…</option>
                  {shelters.filter((s) => s.shelterId !== shelterId).map((s) => (
                    <option key={s.shelterId} value={s.shelterId}>
                      {s.name} ({s.available} free)
                    </option>
                  ))}
                </select>
                <input type="number" min={1} className={field} value={transfer.count}
                       onChange={(e) => setTransfer({ ...transfer, count: e.target.value })} />
                <input className={field} placeholder="Reason for transfer" value={transfer.reason}
                       onChange={(e) => setTransfer({ ...transfer, reason: e.target.value })} />
                <Button onClick={doTransfer} data-testid="transfer-button"
                        className="w-full bg-national text-white">Transfer people</Button>
              </div>
            </Panel>
          </div>

          <Panel title="Resource requirements" action={<PackagePlus size={14} className="text-national" />}>
            <div className="grid sm:grid-cols-4 gap-2 mb-4">
              <select className={field} value={req.category} data-testid="requirement-category"
                      onChange={(e) => setReq({ ...req, category: e.target.value })}>
                {["FOOD", "DRINKING_WATER", "MEDICINE", "BLANKETS", "HYGIENE_KITS", "BABY_FOOD"].map((c) => (
                  <option key={c} value={c}>{c.replace(/_/g, " ")}</option>
                ))}
              </select>
              <input className={field} placeholder="Unit" value={req.unit}
                     onChange={(e) => setReq({ ...req, unit: e.target.value })} />
              <input type="number" min={1} className={field} data-testid="requirement-quantity"
                     value={req.requestedQuantity}
                     onChange={(e) => setReq({ ...req, requestedQuantity: e.target.value })} />
              <Button onClick={raiseRequirement} data-testid="raise-requirement-button"
                      className="bg-national text-white">Raise requirement</Button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs" data-testid="requirements-table">
                <thead>
                  <tr className="text-left text-[10px] uppercase tracking-widest text-slate-500 border-b border-slate-200">
                    <th className="py-2 pr-2">Request</th>
                    <th className="py-2 pr-2">Item</th>
                    <th className="py-2 pr-2">Requested</th>
                    <th className="py-2 pr-2">Approved</th>
                    <th className="py-2 pr-2">Allocated</th>
                    <th className="py-2 pr-2">Sent</th>
                    <th className="py-2 pr-2">Received</th>
                    <th className="py-2 pr-2">Status</th>
                    <th className="py-2">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {requirements.map((r) => (
                    <tr key={r.requestId} className="border-b border-slate-100">
                      <td className="py-2 pr-2 font-mono">{r.requestId}</td>
                      <td className="py-2 pr-2">{r.category} ({r.unit})</td>
                      <td className="py-2 pr-2">{r.requestedQuantity}</td>
                      <td className="py-2 pr-2">{r.approvedQuantity}</td>
                      <td className="py-2 pr-2">{r.allocatedQuantity}</td>
                      <td className="py-2 pr-2">{r.sentQuantity}</td>
                      <td className="py-2 pr-2">{r.receivedQuantity}</td>
                      <td className="py-2 pr-2"><StateBadge status={r.status} /></td>
                      <td className="py-2">
                        {["DELIVERED", "ARRIVED", "IN_TRANSIT", "DELAYED"].includes(r.status) && (
                          <Button data-testid={`receive-${r.requestId}`}
                                  className="h-7 text-[11px] bg-national text-white"
                                  onClick={async () => {
                                    const v = window.prompt(`How many ${r.unit} actually received?`, r.sentQuantity);
                                    if (v === null) return;
                                    try {
                                      const { data } = await setuApi.post(
                                        `/relief/requests/${r.requestId}/receive`,
                                        { receivedQuantity: Number(v) });
                                      toast[data.status === "DISCREPANCY" ? "warning" : "success"](
                                        data.discrepancyNotice || "Receipt recorded");
                                      loadOne();
                                    } catch (e) { toast.error(apiError(e, "Could not record receipt")); }
                                  }}>
                            Confirm receipt
                          </Button>
                        )}
                        {r.status === "RECEIVED" && (
                          <Button data-testid={`distribute-${r.requestId}`}
                                  className="h-7 text-[11px] bg-white border border-slate-300 text-slate-700"
                                  onClick={async () => {
                                    try {
                                      await setuApi.post(`/relief/requests/${r.requestId}/distribute`, {});
                                      toast.success("Marked as distributed");
                                      loadOne();
                                    } catch (e) { toast.error(apiError(e, "Failed")); }
                                  }}>
                            Mark distributed
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                  {!requirements.length && (
                    <tr><td colSpan={9} className="py-3 text-slate-500">No requirements raised yet.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
            <SafetyNote>
              Requested, approved, allocated, sent and received are tracked separately. If the
              received quantity differs from what was sent, the case becomes a discrepancy for an
              admin — no number is silently overwritten.
            </SafetyNote>
          </Panel>
        </>
      )}
    </div>
  );
}
