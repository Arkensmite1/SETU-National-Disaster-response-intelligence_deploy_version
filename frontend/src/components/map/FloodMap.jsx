import React, { useEffect } from "react";
import { MapContainer, TileLayer, Marker, Popup, CircleMarker, LayersControl, Polyline } from "react-leaflet";
import L from "leaflet";

// Fix default marker icon paths (leaflet + webpack)
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

const colorFor = (status) => ({
  safe: "#2E7D32",
  watch: "#F9A825",
  warning: "#EF6C00",
  critical: "#C62828",
}[status] || "#0A2B4E");

export default function FloodMap({
  center = [22.5, 80.5],
  zoom = 5,
  villages = [],
  shelters = [],
  roadClosures = [],
  routeCoords = null,
  height = "560px",
}) {
  return (
    <div style={{ height }} className="rounded-md overflow-hidden border border-slate-200" data-testid="flood-map">
      <MapContainer center={center} zoom={zoom} scrollWheelZoom={true} style={{ height: "100%", width: "100%" }}>
        <LayersControl position="topright">
          <LayersControl.BaseLayer checked name="Standard">
            <TileLayer
              attribution='© OpenStreetMap contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="Terrain">
            <TileLayer
              attribution='© OpenTopoMap'
              url="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png"
            />
          </LayersControl.BaseLayer>

          <LayersControl.Overlay checked name="Flood-affected villages">
            <React.Fragment>
              {villages.map((v) => (
                <CircleMarker
                  key={v.id}
                  center={[v.lat, v.lng]}
                  radius={10 + (v.flood_depth || 0) * 3}
                  pathOptions={{ color: colorFor(v.status), fillColor: colorFor(v.status), fillOpacity: 0.55, weight: 2 }}
                >
                  <Popup>
                    <div className="text-sm">
                      <div className="font-bold text-national">{v.name}</div>
                      <div className="text-xs text-slate-500">{v.district}</div>
                      <div className="mt-1 text-xs">Status: <b style={{ color: colorFor(v.status) }}>{v.status?.toUpperCase()}</b></div>
                      <div className="text-xs">Depth: {v.flood_depth} m</div>
                      <div className="text-xs">Population: {v.population?.toLocaleString()}</div>
                      <div className="text-xs">Trapped: {v.trapped}</div>
                    </div>
                  </Popup>
                </CircleMarker>
              ))}
            </React.Fragment>
          </LayersControl.Overlay>

          <LayersControl.Overlay checked name="Relief shelters">
            <React.Fragment>
              {shelters.map((s) => (
                <Marker key={s.id} position={[s.lat, s.lng]}>
                  <Popup>
                    <div className="text-sm">
                      <div className="font-bold text-national">{s.name}</div>
                      <div className="text-xs">Capacity: {s.capacity}, Occupied: {s.occupied}</div>
                      <div className="text-xs">Free beds: {s.capacity - s.occupied}</div>
                      <div className="text-xs">
                        {s.food ? "🍚 Food" : ""} {s.medical ? "⚕ Medical" : ""} {s.electricity ? "⚡ Power" : ""}
                      </div>
                    </div>
                  </Popup>
                </Marker>
              ))}
            </React.Fragment>
          </LayersControl.Overlay>

          <LayersControl.Overlay checked name="Blocked roads">
            <React.Fragment>
              {roadClosures.map((r) => (
                <CircleMarker
                  key={r.id}
                  center={[r.lat, r.lng]}
                  radius={7}
                  pathOptions={{ color: "#111827", fillColor: "#F97316", fillOpacity: 0.85, weight: 2 }}
                >
                  <Popup>
                    <div className="text-sm">
                      <div className="font-bold">{r.name}</div>
                      <div className="text-xs">{r.reason}</div>
                      <div className="text-xs text-slate-500">Since {r.since}</div>
                    </div>
                  </Popup>
                </CircleMarker>
              ))}
            </React.Fragment>
          </LayersControl.Overlay>
        </LayersControl>

        {routeCoords && routeCoords.length > 1 && (
          <Polyline positions={routeCoords} pathOptions={{ color: "#FF9933", weight: 5, dashArray: "8 6" }} />
        )}
      </MapContainer>
    </div>
  );
}
