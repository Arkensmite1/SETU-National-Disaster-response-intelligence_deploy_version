"""Geospatial helpers — Section 6.4 affected-area matching, 6.5 zones.

Pure-python point-in-polygon (ray casting) so no extra native dependency is
required. Severity thresholds come from the authoritative event data, never
from AI (design rule #8).
"""
import math
from typing import Any, Dict, List, Optional, Tuple

EARTH_R_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R_KM * math.asin(math.sqrt(a))


def _rings(geojson: Optional[Dict[str, Any]]) -> List[List[Tuple[float, float]]]:
    if not geojson:
        return []
    gtype = geojson.get("type")
    coords = geojson.get("coordinates") or []
    if gtype == "Polygon":
        return [[(c[0], c[1]) for c in ring] for ring in coords]
    if gtype == "MultiPolygon":
        out = []
        for poly in coords:
            for ring in poly:
                out.append([(c[0], c[1]) for c in ring])
        return out
    return []


def point_in_polygon(lat: float, lng: float, geojson: Optional[Dict[str, Any]]) -> bool:
    rings = _rings(geojson)
    inside = False
    for ring in rings:
        cnt = False
        n = len(ring)
        for i in range(n):
            x1, y1 = ring[i]
            x2, y2 = ring[(i + 1) % n]
            if ((y1 > lat) != (y2 > lat)):
                xint = (x2 - x1) * (lat - y1) / ((y2 - y1) or 1e-12) + x1
                if lng < xint:
                    cnt = not cnt
        inside = inside or cnt
    return inside


def distance_to_polygon_km(lat: float, lng: float, geojson: Optional[Dict[str, Any]]) -> Optional[float]:
    rings = _rings(geojson)
    if not rings:
        return None
    best = None
    for ring in rings:
        for (lng_v, lat_v) in ring:
            d = haversine_km(lat, lng, lat_v, lng_v)
            best = d if best is None else min(best, d)
    return best


BOUNDARY_CAUTION_KM = 5.0


def classify_against_event(lat: float, lng: float, event: Dict[str, Any]) -> Dict[str, Any]:
    """Section 6.4: Affected / Near-boundary caution / Unaffected.

    Absence of a match is NEVER reported as 'safe' (design rule #1) — the caller
    receives 'NO_MATCH' wording, not 'safe'.
    """
    area = event.get("affectedArea")
    inside = point_in_polygon(lat, lng, area)
    dist = distance_to_polygon_km(lat, lng, area)
    zone = None
    for z in event.get("zones") or []:
        if point_in_polygon(lat, lng, z.get("geometry")):
            zone = z.get("zone")
            break
    if inside:
        classification = "AFFECTED"
        message = (
            f"You are inside the {event.get('severity', '')} {event.get('disasterType', '')} "
            f"affected area. Follow official instructions."
        )
    elif dist is not None and dist <= BOUNDARY_CAUTION_KM:
        classification = "NEAR_BOUNDARY"
        message = (
            f"Caution: {event.get('disasterType', '')} risk reported approximately "
            f"{dist:.1f} km from your location. Avoid travel toward the affected zone."
        )
    else:
        classification = "OUTSIDE_KNOWN_AREA"
        message = (
            "Your location is outside the currently reported affected area. "
            "This is not a confirmation of safety — keep following official updates."
        )
    return {
        "eventId": event.get("eventId"),
        "classification": classification,
        "zone": zone,
        "distanceKm": round(dist, 2) if dist is not None else None,
        "message": message,
    }
