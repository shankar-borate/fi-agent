"""
Geo-verification service.

Collects every captured lat/long from a session, computes the geographic
centroid, and checks whether each point lies within a configurable radius.
Uses the Haversine formula for accurate great-circle distances.
"""

import asyncio
import json as _json
import logging
import urllib.request
from math import atan2, cos, radians, sin, sqrt
from typing import Any, Dict, List, Optional, Tuple

from models.fi_session import GeoPoint, SessionMetadata

logger = logging.getLogger(__name__)


# ── Haversine ─────────────────────────────────────────────────────────────────

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in metres between two WGS-84 points."""
    R = 6_371_000.0
    φ1, φ2 = radians(lat1), radians(lat2)
    Δφ = radians(lat2 - lat1)
    Δλ = radians(lon2 - lon1)
    a = sin(Δφ / 2) ** 2 + cos(φ1) * cos(φ2) * sin(Δλ / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def _centroid(pts: List[Tuple[float, float]]) -> Tuple[float, float]:
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


# ── Point collection ──────────────────────────────────────────────────────────

def collect_geo_points(meta: SessionMetadata) -> List[Dict[str, Any]]:
    """
    Extract all geo-tagged events from a completed session.
    Returns list of dicts: {label, latitude, longitude, timestamp}.
    """
    points: List[Dict[str, Any]] = []

    for qa in meta.questions:
        if qa.geo:
            points.append({
                "label": f"Q: {qa.question[:40]}",
                "latitude": qa.geo.latitude,
                "longitude": qa.geo.longitude,
                "timestamp": qa.geo.timestamp,
            })

    for ph in meta.photos:
        if ph.geo:
            points.append({
                "label": f"Photo: {ph.prompt[:40]}",
                "latitude": ph.geo.latitude,
                "longitude": ph.geo.longitude,
                "timestamp": ph.geo.timestamp,
            })

    logger.info("[Geo] Collected %d geo points from session %s", len(points), meta.session_id)
    return points


# ── Verification ──────────────────────────────────────────────────────────────

def verify_location(
    points: List[Dict[str, Any]],
    radius_m: float = 500.0,
) -> Dict[str, Any]:
    """
    Check that every captured geo point lies within *radius_m* metres of the
    session centroid (mean lat/lon of all valid points).

    Returns a rich result dict consumed by the report generator.
    """
    valid = [p for p in points if p.get("latitude") and p.get("longitude")]

    if not valid:
        logger.warning("[Geo] No valid geo points to verify")
        return {
            "verified": False,
            "reason": "No location data captured during session.",
            "points_checked": 0,
            "radius_m": radius_m,
        }

    c_lat, c_lon = _centroid([(p["latitude"], p["longitude"]) for p in valid])
    logger.info("[Geo] Centroid: (%.6f, %.6f) — radius=%.0fm", c_lat, c_lon, radius_m)

    details: List[Dict[str, Any]] = []
    outliers: List[str] = []
    max_dist = 0.0

    for p in valid:
        dist = haversine_m(c_lat, c_lon, p["latitude"], p["longitude"])
        within = dist <= radius_m
        if not within:
            outliers.append(p["label"])
            logger.warning("[Geo] OUTLIER — %s is %.0fm from centroid (limit %.0fm)",
                           p["label"], dist, radius_m)
        else:
            logger.debug("[Geo] OK — %s is %.0fm from centroid", p["label"], dist)
        max_dist = max(max_dist, dist)
        details.append({
            "label": p["label"],
            "latitude": round(p["latitude"], 6),
            "longitude": round(p["longitude"], 6),
            "timestamp": p.get("timestamp", ""),
            "distance_from_centroid_m": round(dist, 1),
            "within_radius": within,
        })

    # Maximum pairwise distance (diameter of the point set)
    max_pairwise = 0.0
    for i in range(len(valid)):
        for j in range(i + 1, len(valid)):
            d = haversine_m(
                valid[i]["latitude"], valid[i]["longitude"],
                valid[j]["latitude"], valid[j]["longitude"],
            )
            max_pairwise = max(max_pairwise, d)

    verified = len(outliers) == 0
    result = {
        "verified": verified,
        "centroid_lat": round(c_lat, 6),
        "centroid_lon": round(c_lon, 6),
        "radius_m": radius_m,
        "points_checked": len(details),
        "max_distance_m": round(max_dist, 1),
        "max_pairwise_distance_m": round(max_pairwise, 1),
        "outliers": outliers,
        "details": details,
    }
    logger.info(
        "[Geo] Verification %s — %d/%d within %.0fm  (centroid_max=%.0fm  pairwise_max=%.0fm)",
        "PASSED" if verified else "FAILED",
        len(details) - len(outliers), len(details), radius_m, max_dist, max_pairwise,
    )
    return result


# ── Reverse geocoding ─────────────────────────────────────────────────────────

async def reverse_geocode(latitude: float, longitude: float, api_key: str) -> str:
    """
    Return a formatted address for the given coordinates via Google Geocoding API.
    Falls back to a descriptive string if the API key is missing or the call fails.
    """
    if not api_key:
        logger.warning("[Geo] Google Maps API key not set — skipping reverse geocode")
        return "Address lookup not available (API key not configured)"

    url = (
        f"https://maps.googleapis.com/maps/api/geocode/json"
        f"?latlng={latitude},{longitude}&key={api_key}"
    )

    def _fetch() -> dict:
        with urllib.request.urlopen(url, timeout=8) as resp:  # noqa: S310
            return _json.loads(resp.read())

    try:
        data = await asyncio.to_thread(_fetch)
        status = data.get("status")
        results = data.get("results", [])
        if status == "OK" and results:
            address = results[0].get("formatted_address", "")
            logger.info("[Geo] Reverse geocode (%.5f, %.5f) → %s", latitude, longitude, address)
            return address
        logger.warning("[Geo] Geocode status=%s for (%.5f, %.5f)", status, latitude, longitude)
        return f"Address not found ({latitude:.5f}, {longitude:.5f})"
    except Exception as exc:
        logger.error("[Geo] Reverse geocode failed: %s", exc)
        return f"Address lookup failed: {exc}"
