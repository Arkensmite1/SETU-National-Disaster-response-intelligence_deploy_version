import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Boxes, RefreshCw, Truck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Panel, SectionHeading, StatCard } from "@/components/common/GovUI";
import { SafetyNote, StalenessNote, StateBadge } from "@/components/setu/SetuBits";
import { apiError, setuApi } from "@/lib/setuApi";

const field = "w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:border-national";

export default function NgoPortal() {
  const [board, setBoard] = useState([]);
  const [mine, setMine] = useState([]);
  const [inventory, setInventory] = useState([]);
  const [pipeline, setPipeline] = useState(null);
  const [item, setItem] = useState({ category: "FOOD", unit: "packets", quantity: 1000, location: "" });

  const load = useCallback(async () => {
    try {
      const [b, r, i, p] = await Promise.all([
        setuApi.get("/relief/requirements"),
        setuApi.get("/relief/requests"),
        setuApi.get("/relief/inventory"),
        setuApi.get("/relief/pipeline"),
      ]);
      setBoard(b.data.requirements || []);
      setMine(r.data.requests || []);
      setInventory(i.data.inventory || []);
      setPipeline(p.data);
    } catch (e) {
      toast.error(apiError(e, "Could not load the relief board"));
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const act = async (fn, msg) => {
    try {
      const { data } = await fn();
      toast.success(data?.discrepancyNotice || data?.note || msg);
      load();
    } catch (e) {
      const d = e?.response?.data?.detail;
      toast.error(typeof d === "object" ? d.message : apiError(e, "Action failed"));
    }
  };

  const commit = (r) => {
    const q = window.prompt(`Commit how many ${r.unit}? (approved ${r.approvedQuantity})`,
                            r.approvedQuantity || r.requestedQuantity);
    if (q === null) return;
    const eta = window.prompt("ETA (ISO date-time, optional)", "");
    return act(() => setuApi.post(`/relief/requests/${r.requestId}/commit`, {
      allocatedQuantity: Number(q), eta: eta || null,
    }), "Stock committed");
  };

  const dispatch = (r) => {
    const q = window.prompt(`How many ${r.unit} are being sent?`, r.allocatedQuantity);
    if (q === null) return;
    return act(() => setuApi.post(`/relief/requests/${r.requestId}/dispatch`, {
      sentQuantity: Number(q),
    }), "Dispatched — the shelter confirms receipt separately");
  };

  const delay = (r) => {
    const reason = window.prompt("Reason for the delay (required)");
    if (!reason) return;
    const eta = window.prompt("New ETA (ISO date-time)", "");
    return act(() => setuApi.post(`/relief/requests/${r.requestId}/delay`, {
      reason, newEta: eta || null,
    }), "Delay recorded and the shelter has been notified");
  };

  const saveInventory = () =>
    act(() => setuApi.post("/relief/inventory", { ...item, quantity: Number(item.quantity) || 0 }),
        "Inventory updated");

  const q = pipeline?.quantities || {};

  return (
    <div className="max-w-[1500px] mx-auto px-4 py-6 space-y-6">
      <SectionHeading
        eyebrow="Relief coordination"
        title="NGO portal"
        description="Outstanding shelter requirements, your commitments and dispatches. Existing commitments from other NGOs are always visible so the same need is not served twice."
        action={
          <Button onClick={load} data-testid="ngo-refresh" className="bg-national text-white gap-2 h-9 text-xs">
            <RefreshCw size={14} /> Refresh
          </Button>
        }
      />

      <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
        <StatCard label="Requested" value={q.requested ?? "—"} />
        <StatCard label="Approved" value={q.approved ?? "—"} />
        <StatCard label="Allocated" value={q.allocated ?? "—"} accent="saffron" />
        <StatCard label="Sent" value={q.sent ?? "—"} accent="national" />
        <StatCard label="Received" value={q.received ?? "—"} accent="green" />
        <StatCard label="Open discrepancies" value={pipeline?.openDiscrepancies ?? "—"} accent="red" />
      </div>

      <Panel title="Requirement board" action={<Truck size={14} className="text-national" />}>
        <div className="overflow-x-auto">
          <table className="w-full text-xs" data-testid="requirement-board">
            <thead>
              <tr className="text-left text-[10px] uppercase tracking-widest text-slate-500 border-b border-slate-200">
                <th className="py-2 pr-2">Shelter</th>
                <th className="py-2 pr-2">Item</th>
                <th className="py-2 pr-2">Requested</th>
                <th className="py-2 pr-2">Approved</th>
                <th className="py-2 pr-2">Committed by others</th>
                <th className="py-2 pr-2">Remaining need</th>
                <th className="py-2 pr-2">Status</th>
                <th className="py-2">Action</th>
              </tr>
            </thead>
            <tbody>
              {board.map((r) => (
                <tr key={r.requestId} className="border-b border-slate-100 align-top"
                    data-testid={`requirement-${r.requestId}`}>
                  <td className="py-2 pr-2">
                    <div className="font-semibold text-national">{r.shelterName || r.shelterId}</div>
                    <StalenessNote notice={r.shelterStalenessNotice} />
                  </td>
                  <td className="py-2 pr-2">{r.category} ({r.unit})</td>
                  <td className="py-2 pr-2">{r.requestedQuantity}</td>
                  <td className="py-2 pr-2">{r.approvedQuantity}</td>
                  <td className="py-2 pr-2">{r.committedByOthers}</td>
                  <td className="py-2 pr-2 font-bold">{r.remainingNeed}</td>
                  <td className="py-2 pr-2"><StateBadge status={r.status} /></td>
                  <td className="py-2 space-y-1">
                    {r.status === "APPROVED" && (
                      <Button onClick={() => commit(r)} data-testid={`commit-${r.requestId}`}
                              className="h-7 text-[11px] bg-national text-white w-full">Commit stock</Button>
                    )}
                    {r.status === "ALLOCATED" && (
                      <Button onClick={() => dispatch(r)} data-testid={`dispatch-${r.requestId}`}
                              className="h-7 text-[11px] bg-national text-white w-full">Dispatch</Button>
                    )}
                    {r.status === "DISPATCHED" && (
                      <Button onClick={() => act(() => setuApi.post(`/relief/requests/${r.requestId}/in-transit`), "Marked in transit")}
                              data-testid={`transit-${r.requestId}`}
                              className="h-7 text-[11px] bg-national text-white w-full">In transit</Button>
                    )}
                    {["IN_TRANSIT", "DELAYED"].includes(r.status) && (
                      <>
                        <Button onClick={() => act(() => setuApi.post(`/relief/requests/${r.requestId}/deliver`), "Marked delivered")}
                                data-testid={`deliver-${r.requestId}`}
                                className="h-7 text-[11px] bg-white border border-slate-300 text-slate-700 w-full">
                          Delivered
                        </Button>
                        <Button onClick={() => delay(r)} data-testid={`delay-${r.requestId}`}
                                className="h-7 text-[11px] text-white w-full" style={{ backgroundColor: "#EF6C00" }}>
                          Report delay
                        </Button>
                      </>
                    )}
                    {r.status === "REQUESTED" && (
                      <span className="text-[10px] text-slate-500">awaiting authority approval</span>
                    )}
                    {r.duplicateCommitmentWarning && (
                      <div className="text-[10px] font-semibold" style={{ color: "#EF6C00" }}>
                        {r.duplicateCommitmentWarning}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
              {!board.length && (
                <tr><td colSpan={8} className="py-3 text-slate-500">
                  No open requirements. This reflects requirements raised so far — it does not mean
                  there is no need in the field.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </Panel>

      <div className="grid lg:grid-cols-2 gap-6">
        <Panel title="My inventory" action={<Boxes size={14} className="text-national" />}>
          <div className="grid sm:grid-cols-4 gap-2 mb-3">
            <select className={field} value={item.category} data-testid="inventory-category"
                    onChange={(e) => setItem({ ...item, category: e.target.value })}>
              {["FOOD", "DRINKING_WATER", "MEDICINE", "BLANKETS", "HYGIENE_KITS", "BABY_FOOD"].map((c) => (
                <option key={c} value={c}>{c.replace(/_/g, " ")}</option>
              ))}
            </select>
            <input className={field} placeholder="Unit" value={item.unit}
                   onChange={(e) => setItem({ ...item, unit: e.target.value })} />
            <input type="number" className={field} value={item.quantity} data-testid="inventory-quantity"
                   onChange={(e) => setItem({ ...item, quantity: e.target.value })} />
            <Button onClick={saveInventory} data-testid="inventory-save"
                    className="bg-national text-white">Save</Button>
          </div>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-[10px] uppercase tracking-widest text-slate-500 border-b border-slate-200">
                <th className="py-2">Item</th><th className="py-2">Stock</th>
                <th className="py-2">Committed</th><th className="py-2">Uncommitted</th>
              </tr>
            </thead>
            <tbody>
              {inventory.map((i) => (
                <tr key={i.category} className="border-b border-slate-100">
                  <td className="py-2">{i.category} ({i.unit})</td>
                  <td className="py-2">{i.quantity}</td>
                  <td className="py-2">{i.committed}</td>
                  <td className="py-2 font-bold">{i.uncommitted}</td>
                </tr>
              ))}
              {!inventory.length && (
                <tr><td colSpan={4} className="py-3 text-slate-500">No stock declared yet.</td></tr>
              )}
            </tbody>
          </table>
        </Panel>

        <Panel title="My consignments">
          <div className="space-y-2 max-h-[360px] overflow-y-auto" data-testid="ngo-consignments">
            {mine.filter((r) => r.ngoId).map((r) => (
              <div key={r.requestId} className="border border-slate-200 rounded-md p-2">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[11px]">{r.requestId}</span>
                  <StateBadge status={r.status} />
                </div>
                <div className="text-[11px] text-slate-600 mt-1">
                  {r.category}: allocated {r.allocatedQuantity} • sent {r.sentQuantity} • received{" "}
                  {r.receivedQuantity}
                </div>
                {r.quantityMismatch && (
                  <div className="text-[11px] font-semibold" style={{ color: "#C62828" }}>
                    Discrepancy of {r.quantityMismatch.difference} — awaiting authority resolution
                  </div>
                )}
                {r.delayReason && (
                  <div className="text-[11px] text-slate-600">Delay: {r.delayReason}</div>
                )}
              </div>
            ))}
            {!mine.filter((r) => r.ngoId).length && (
              <p className="text-sm text-slate-600">No consignments yet.</p>
            )}
          </div>
        </Panel>
      </div>

      <SafetyNote>
        A dispatch is not a delivery and a delivery is not a receipt. Each quantity is stored
        separately, and any mismatch is escalated to an admin rather than corrected silently.
      </SafetyNote>
    </div>
  );
}
