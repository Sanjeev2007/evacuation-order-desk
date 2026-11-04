"""The site check: is a site in the saved flood layer, and does it have room?

The wording here is deliberate. A site is only ever "cleared for this drill",
never called safe, and it is only ever named by its letter.
"""
from eod.scenario import EodError, data_dir, demand_for, find_release, load_json, load_scenario


def point_in_ring(lon, lat, ring):
    """Ray casting: go east from the point and count edges crossed. Odd means inside."""
    inside = False
    previous = ring[-1]
    for current in ring:
        x1, y1 = previous[0], previous[1]
        x2, y2 = current[0], current[1]
        if (y1 > lat) != (y2 > lat):
            crossing_lon = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
            if lon < crossing_lon:
                inside = not inside
        previous = current
    return inside


def point_in_polygon(lon, lat, polygon):
    """GeoJSON polygon: the first ring is the outline, any others are holes."""
    outline, holes = polygon[0], polygon[1:]
    if not point_in_ring(lon, lat, outline):
        return False
    return not any(point_in_ring(lon, lat, hole) for hole in holes)


def check_lon_lat(position, label):
    """Catches a layer saved in metres, which would otherwise miss every site."""
    if not (-180 <= position[0] <= 180 and -90 <= position[1] <= 90):
        raise EodError(f"{label} is not in lon/lat")


def features_in(path):
    collection = load_json(path)
    features = collection.get("features") if isinstance(collection, dict) else None
    if not isinstance(features, list):
        raise EodError(f"{path} is not a GeoJSON FeatureCollection")
    return features


def load_flood_polygons():
    """Return every polygon. Empty or broken polygons are errors, so they can't clear a site."""
    polygons = []
    for feature in features_in(data_dir() / "flood-zone.geojson"):
        geometry = feature.get("geometry") or {}
        if geometry.get("type") == "Polygon":
            polygons.append(geometry["coordinates"])
        elif geometry.get("type") == "MultiPolygon":
            polygons.extend(geometry["coordinates"])
        else:
            raise EodError("flood-zone.geojson may only hold Polygon and MultiPolygon features")
    if not polygons:
        raise EodError("flood-zone.geojson holds no polygons")
    for polygon in polygons:
        if not polygon or not all(polygon):
            raise EodError("flood-zone.geojson has an empty polygon")
        for ring in polygon:
            if len(ring) < 4:
                raise EodError("flood-zone.geojson has a ring with too few points")
            for position in ring:
                check_lon_lat(position, "flood-zone.geojson")
    return polygons


def find_site_location(site_id):
    for feature in features_in(data_dir() / "sites.geojson"):
        if (feature.get("properties") or {}).get("site_id") == site_id:
            geometry = feature.get("geometry") or {}
            if geometry.get("type") != "Point":
                raise EodError(f"Site {site_id} in sites.geojson is not a Point")
            position = geometry.get("coordinates")
            check_lon_lat(position, f"Site {site_id} in sites.geojson")
            return position[0], position[1]
    raise EodError(f"Site {site_id} has no location in sites.geojson")


def check_site(site_id, stage, release_id):
    """Return {site, status, reasons, demand}. Raises EodError for unknown or bad input."""
    scenario = load_scenario()
    release = find_release(scenario, stage, release_id)
    if not isinstance(site_id, str) or site_id not in scenario["sites"]:
        raise EodError(f"unknown site {site_id!r}, use one of {', '.join(sorted(scenario['sites']))}")

    capacity = scenario["sites"][site_id]["capacity"]
    demand = demand_for(scenario, release["release_m3s"])
    try:
        lon, lat = find_site_location(site_id)
        polygons = load_flood_polygons()
    except (AttributeError, IndexError, KeyError, TypeError):
        raise EodError("sites.geojson or flood-zone.geojson is malformed")

    reasons = []
    if any(point_in_polygon(lon, lat, polygon) for polygon in polygons):
        reasons.append(f"Site {site_id} is inside the saved 100-year layer, not cleared for this drill")
    if capacity < demand:
        reasons.append(f"Site {site_id} capacity {capacity} is below demand {demand} in this synthetic drill, not cleared")

    if reasons:
        status = "fail"
    else:
        status = "pass"
        reasons.append(f"Site {site_id} cleared for this drill against synthetic data only")
    return {"site": site_id, "status": status, "reasons": reasons, "demand": demand}
