import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Crosshair, Phone } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Panel, SectionHeading } from "@/components/common/GovUI";
import { SafetyNote, StalenessNote, StateBadge } from "@/components/setu/SetuBits";
import { apiError, setuApi } from "@/lib/setuApi";
import { acquireLocation } from "@/lib/offlineQueue";

export default function ShelterFinder() {
  const [rows, setRows] = useState([]);
  const [totals, setTotals] = useState(null);
  const [needed, setNeeded] = useState(1);
  const [located, setLocated] = useState(false);

  const load = useCallback(async (loc) => {
    try {
      const params = new URLSearchParams({ needed: String(needed) });
      if (loc) {
        params.set("lat", String(loc.latitude));
        params.set("lng", String(loc.longitude));
      }
      const { data } = await setuApi.get(`/shelters/list?${params.toString()}`);
      setRows(data.shelters || []);
      setTotals(data.totals);
    } catch (e) {
      toast.error(apiError(e, "Could not load shelters"));
    }
  }, [needed]);

  useEffect(() => { load(null); }, [load]);

  const useMyLocation = async () => {
    const loc = await acquireLocation();
    if (!loc) return toast.error("Location unavailable — shelters are still listed below");
    setLocated(true);
    load(loc);
    toast.success("Sorted by distance from your location");
  };

  return (
    <div className="max-w-[1200px] mx-auto px-4 py-6 space-y-6">
      <SectionHeading
        eyebrow="Relief shelters"
        title="Find a shelter with space"
        description="Availability is calculated from capacity minus current occupancy every time this page loads, and each record shows how old its last update is."
        action={
          <div className="flex items-center gap-2">
            <input type="number" min={1} value={needed} data-testid="shelter-needed-input"
                   onChange={(e) => setNeeded(e.target.value)}
                   className="w-20 px-2 py-1.5 border border-slate-200 rounded-md text-xs" />
            <span className="text-[11px] text-slate-500">people</span>
            <Button onClick={useMyLocation} data-testid="shelter-locate-button"
                    className="bg-national text-white gap-2 h-9 text-xs">
              <Crosshair size={14} /> Nearest to me
            </Button>
          </div>
        }
      />

      {totals && (
        <SafetyNote>
          {totals.available} place(s) free across {rows.length} shelters right now
          ({totals.occupancy} of {totals.capacity} occupied). Confirm by phone before travelling —
          occupancy changes quickly and a full shelter cannot admit you.
        </SafetyNote>
      )}

      <Panel title="Shelters">
        <div className="space-y-2" data-testid="shelter-finder-list">
          {rows.map((s) => (
            <div key={s.shelterId} className="border border-slate-200 rounded-md p-3"
                 data-testid={`finder-${s.shelterId}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div className="font-semibold text-national">{s.name}</div>
                  <div className="text-[11px] text-slate-500">
                    {s.region}
                    {located && s.distanceKm !== null && s.distanceKm !== undefined
                      ? ` • ${s.distanceKm} km away` : ""}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <StateBadge status={s.status} />
                  <span className={`text-sm font-bold ${s.acceptingArrivals ? "text-green-700" : "text-red-700"}`}>
                    {s.available} free
                  </span>
                </div>
              </div>
              <div className="text-[11px] text-slate-600 mt-1">
                Capacity {s.capacity} • occupancy {s.occupancy}
                {s.overflow ? ` • ${s.overflow} over capacity` : ""}
                {s.facilities?.length ? ` • ${s.facilities.join(", ")}` : ""}
              </div>
              <div className="flex flex-wrap items-center gap-3 mt-2">
                <StalenessNote notice={s.stalenessNotice} stale={s.stale} />
                {s.contactPhone && (
                  <a href={`tel:${s.contactPhone}`} className="text-[11px] font-semibold text-national flex items-center gap-1">
                    <Phone size={11} /> {s.contactPhone}
                  </a>
                )}
                {!s.acceptingArrivals && (
                  <span className="text-[11px] font-semibold" style={{ color: "#C62828" }}>
                    Cannot take {needed} more people right now — try another shelter
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
