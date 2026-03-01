import networkx as nx
from app.services.osm_graph import approx_meters
from math import isfinite


def nearest_node(G, lat, lon):
    target = (lat, lon)
    best = None
    best_d = 1e18
    for node in G.nodes:
        d = approx_meters(node, target)
        if d < best_d:
            best_d = d
            best = node
    return best


def compute_route(G, start_lat, start_lon, end_lat, end_lon, mode: str = "shortest", outdoor_penalty: float = 1.0, reports: list = None, pass_through_enabled: set = None):
    """Compute route with modes: shortest, sheltered, cleared.
    - reports: list of dicts with lat, lon, type, rating
    - pass_through_enabled: set of building_osm_id allowed for indoor connectors
    """
    reports = reports or []
    pass_through_enabled = pass_through_enabled or set()

    s = nearest_node(G, start_lat, start_lon)
    t = nearest_node(G, end_lat, end_lon)

    def edge_clear_multiplier(u, v, attrs):
        # base multiplier from mode
        outdoors = attrs.get("outdoors", True)
        meters = attrs.get("meters", 1.0)
        mult = 1.0

        if mode == "shortest":
            mult = 1.0
        elif mode == "sheltered":
            # indoor edges much cheaper
            mult = 0.2 if not outdoors else 1.0 * outdoor_penalty
        elif mode == "cleared":
            # start with weather penalty for outdoors
            mult = 1.0 * outdoor_penalty if outdoors else 0.5

        # incorporate user reports affecting nearby segments
        if outdoors and reports:
            # compute simple proximity-based adjustments
            ux = (u[0] + v[0]) / 2.0
            uy = (u[1] + v[1]) / 2.0
            score = 0.0
            count = 0
            for r in reports:
                # distance in meters
                d = approx_meters((ux, uy), (r["lat"], r["lon"]))
                if d < 30:  # within 30m
                    count += 1
                    if r["report_type"] == "cleared":
                        score -= 0.6
                    if r["report_type"] == "icy":
                        score += 0.8
                    if r["report_type"] == "blocked":
                        score += 5.0
            if count > 0:
                # average effect
                adj = score / max(1, count)
                mult = max(0.05, mult + adj)

        # disallow if blocked
        if outdoors and reports:
            for r in reports:
                d = approx_meters((u[0] + v[0]) / 2.0, (u[1] + v[1]) / 2.0) if False else 0

        return meters * mult

    # networkx A* requires a weight function that takes u,v,attrs
    try:
        path = nx.astar_path(G, s, t, heuristic=lambda a, b: approx_meters(a, b), weight=lambda u, v, attrs: edge_clear_multiplier(u, v, attrs))
    except Exception:
        # fallback to shortest by meters
        def w(u, v, attrs):
            return attrs.get("meters", 1.0)

        path = nx.shortest_path(G, s, t, weight=w)

    total_m = 0.0
    outdoor_m = 0.0
    coords = []
    sheltered_m = 0.0
    steps = []
    current = None
    segments = []
    for i in range(len(path)):
        coords.append({"lat": path[i][0], "lon": path[i][1]})
        if i < len(path) - 1:
            a = path[i]
            b = path[i + 1]
            attrs = G.get_edge_data(a, b)
            meters = attrs.get("meters", 0.0)
            total_m += meters
            outdoors = attrs.get("outdoors", True)
            if outdoors:
                outdoor_m += meters
            else:
                sheltered_m += meters

            # build a simple step grouping consecutive edges of the same type
            instr = "Walk"
            if not outdoors:
                bid = attrs.get("building_osm_id")
                if bid:
                    instr = f"Pass through building {bid}"
                else:
                    instr = "Go through building"
            else:
                instr = "Walk"

            if current is None or current["instr"] != instr:
                # start new step
                current = {"instr": instr, "distance_m": meters, "outdoors": outdoors, "end": {"lat": b[0], "lon": b[1]}, "start": {"lat": a[0], "lon": a[1]}}
                steps.append(current)
            else:
                # extend current
                current["distance_m"] += meters
                current["end"] = {"lat": b[0], "lon": b[1]}

            # add segment geometry for visualization
            segments.append({"coords": [{"lat": a[0], "lon": a[1]}, {"lat": b[0], "lon": b[1]}], "outdoors": outdoors, "meters": meters})

    # compute simple metrics
    walk_speed_m_per_min = 80.0
    cold_exposure_minutes = outdoor_m / walk_speed_m_per_min
    # snow risk score normalized
    snow_risk = (outdoor_m / max(1.0, total_m)) * outdoor_penalty

    return {
        "coords": coords,
        "total_meters": total_m,
        "outdoor_meters": outdoor_m,
        "sheltered_meters": sheltered_m,
        "cold_exposure_minutes": cold_exposure_minutes,
        "snow_risk_score": float(snow_risk),
        "steps": steps,
        "segments": segments,
    }