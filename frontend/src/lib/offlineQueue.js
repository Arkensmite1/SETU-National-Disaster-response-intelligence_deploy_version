// Section 19.1 — Full / Degraded / Offline network modes + offline SOS queue.
// An SOS created without connectivity is stored locally with its ORIGINAL
// creation time and replayed on reconnect; the server receives both the original
// time and the upload time. Nothing here ever tells the user a rescue team was
// notified.
import { setuApi, setuEndpoints } from "@/lib/setuApi";

const QUEUE_KEY = "setu.sosQueue";
const LAST_KNOWN_KEY = "setu.lastKnownLocation";

export function networkMode() {
  if (typeof navigator !== "undefined" && navigator.onLine === false) return "OFFLINE";
  const conn = typeof navigator !== "undefined" ? navigator.connection : null;
  if (conn && ["slow-2g", "2g"].includes(conn.effectiveType)) return "DEGRADED";
  return "FULL";
}

export function listQueue() {
  try {
    return JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]");
  } catch {
    return [];
  }
}

function writeQueue(items) {
  localStorage.setItem(QUEUE_KEY, JSON.stringify(items));
}

export function enqueueSos(payload) {
  const item = {
    ...payload,
    clientRef: `local-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    clientCreatedAt: new Date().toISOString(),
    networkStatus: "OFFLINE",
  };
  writeQueue([...listQueue(), item]);
  return item;
}

export function removeQueued(clientRef) {
  writeQueue(listQueue().filter((i) => i.clientRef !== clientRef));
}

export async function syncQueue() {
  const items = listQueue();
  if (!items.length) return { synced: 0, results: [] };
  const { data } = await setuApi.post(setuEndpoints.sosSync, { items });
  (data.results || []).forEach((r) => {
    if (r.ok) removeQueued(r.clientRef);
  });
  return data;
}

export function rememberLocation(location) {
  localStorage.setItem(LAST_KNOWN_KEY, JSON.stringify({ ...location, storedAt: new Date().toISOString() }));
}

export function lastKnownLocation() {
  try {
    const v = JSON.parse(localStorage.getItem(LAST_KNOWN_KEY) || "null");
    return v ? { ...v, source: "LAST_KNOWN" } : null;
  } catch {
    return null;
  }
}

// Section 11.5 — GPS unavailable != user unavailable.
// Chain: GPS -> Network Location -> Last Known -> (caller falls back to Manual / Landmark)
export function acquireLocation() {
  return new Promise((resolve) => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      const lk = lastKnownLocation();
      return resolve(lk || null);
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const loc = {
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          accuracy: pos.coords.accuracy || null,
          source: (pos.coords.accuracy || 0) > 150 ? "NETWORK" : "GPS",
          timestamp: new Date().toISOString(),
        };
        rememberLocation(loc);
        resolve(loc);
      },
      () => {
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            const loc = {
              latitude: pos.coords.latitude,
              longitude: pos.coords.longitude,
              accuracy: pos.coords.accuracy || 1000,
              source: "NETWORK",
              timestamp: new Date().toISOString(),
            };
            rememberLocation(loc);
            resolve(loc);
          },
          () => resolve(lastKnownLocation()),
          { enableHighAccuracy: false, timeout: 8000, maximumAge: 600000 }
        );
      },
      { enableHighAccuracy: true, timeout: 8000, maximumAge: 0 }
    );
  });
}

export function batteryLevel() {
  // Section 19.2 — battery aware, but active SOS tracking is never silently dropped.
  if (typeof navigator === "undefined" || !navigator.getBattery) return Promise.resolve(null);
  return navigator.getBattery().then((b) => Math.round((b.level || 0) * 100)).catch(() => null);
}
