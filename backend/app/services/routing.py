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


def compute_route(
    G, start_lat, start_lon, end_lat, end_lon,
    mode: str = "shortest", outdoor_penalty: float = 1.0,
    reports: list = None, pass_through_enabled: set = None, paths_only: bool = False
):
    """Compute route with modes: shortest, sheltered, cleared.
    - reports: list of dicts with lat, lon, type, rating
    - pass_through_enabled: set of building_osm_id allowed for indoor connectors
    """
    reports = reports or []
    pass_through_enabled = pass_through_enabled or set()

    s = nearest_node(G, start_lat, start_lon)
    t = nearest_node(G, end_lat, end_lon)

    def edge_clear_multiplier(u, v, attrs):
        outdoors = attrs.get("outdoors", True)
        meters = attrs.get("meters", 1.0)
        if paths_only and not outdoors:
            return 1e9
        ux = (u[0] + v[0]) / 2.0
        uy = (u[1] + v[1]) / 2.0

        hazard = 0.0
        clearance = 0.0
        blocked_close = False
        if reports:
            for r in reports:
                d = approx_meters((ux, uy), (r["lat"], r["lon"]))
                if d > 100:
                    continue
                # stronger effect for closer reports
                w = max(0.0, 1.0 - (d / 100.0))
                rtype = r.get("report_type")
                if rtype == "blocked":
                    hazard += 18.0 * w
                    if d < 30:
                        blocked_close = True
                elif rtype == "icy":
                    hazard += 5.0 * w
                elif rtype == "salted":
                    clearance += 0.9 * w
                elif rtype == "cleared":
                    clearance += 1.2 * w

        net_hazard = max(0.0, hazard - clearance)

        if mode == "shortest":
            mult = 1.0 if outdoors else 0.95
            # Shortest still reacts a bit to bad conditions.
            mult += net_hazard * (0.45 if outdoors else 0.08)
        elif mode == "sheltered":
            mult = 0.18 if not outdoors else (1.45 * outdoor_penalty)
            mult += net_hazard * (2.6 if outdoors else 0.15)
            mult = max(0.04, mult - (clearance * 0.18))
            if outdoors and blocked_close:
                mult += 400.0
        else:  # cleared
            mult = 0.45 if not outdoors else (1.6 * outdoor_penalty)
            mult += net_hazard * (4.5 if outdoors else 0.2)
            mult = max(0.03, mult - (clearance * 0.6))
            if outdoors and blocked_close:
                # "Cleared" mode strongly avoids blocked segments when alternatives exist.
                mult += 800.0

        return meters * max(0.03, mult)

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
    coords = [{"lat": start_lat, "lon": start_lon}]
    sheltered_m = 0.0
    steps = []
    current = None
    segments = []
    EPS_M = 1.0

    def add_edge(a, b, meters, outdoors=True, instr=None):
        nonlocal total_m, outdoor_m, sheltered_m, current
        if meters <= EPS_M:
            return
        total_m += meters
        if outdoors:
            outdoor_m += meters
        else:
            sheltered_m += meters

        step_instr = instr or "Walk"
        if not outdoors and instr is None:
            step_instr = "Go through building"

        if current is None or current["instr"] != step_instr:
            current = {
                "instr": step_instr,
                "distance_m": meters,
                "outdoors": outdoors,
                "end": {"lat": b[0], "lon": b[1]},
                "start": {"lat": a[0], "lon": a[1]},
            }
            steps.append(current)
        else:
            current["distance_m"] += meters
            current["end"] = {"lat": b[0], "lon": b[1]}

        segments.append({
            "coords": [{"lat": a[0], "lon": a[1]}, {"lat": b[0], "lon": b[1]}],
            "outdoors": outdoors,
            "meters": meters,
        })
        coords.append({"lat": b[0], "lon": b[1]})

    # Anchor route to exact selected start, not just nearest graph node.
    if path:
        s_node = path[0]
        start_anchor_m = approx_meters((start_lat, start_lon), s_node)
        add_edge((start_lat, start_lon), s_node, start_anchor_m, outdoors=True, instr="Walk")

    for i in range(len(path) - 1):
        a = path[i]
        b = path[i + 1]
        attrs = G.get_edge_data(a, b)
        meters = attrs.get("meters", 0.0)
        outdoors = attrs.get("outdoors", True)
        bid = attrs.get("building_osm_id")
        instr = "Walk"
        if not outdoors:
            instr = f"Pass through building {bid}" if bid else "Go through building"
        add_edge(a, b, meters, outdoors=outdoors, instr=instr)

    # Anchor route to exact selected destination, not just nearest graph node.
    if path:
        t_node = path[-1]
        end_anchor_m = approx_meters(t_node, (end_lat, end_lon))
        add_edge(t_node, (end_lat, end_lon), end_anchor_m, outdoors=True, instr="Walk")

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
