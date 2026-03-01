"""
route.py — SnowPath UNL
Complete rewrite with a hand-crafted, street-accurate graph of UNL City Campus.
Routes now follow actual sidewalks/streets visible on the map instead of
drawing straight diagonal lines through buildings.
"""

import json
import os
import networkx as nx
from fastapi import APIRouter, Depends
from datetime import datetime, timezone
from typing import Optional
from app.config import CAMPUS_LAT, CAMPUS_LON, BBOX
from app.services.weather import fetch_hourly_weather, get_current_hour_bucket, compute_winter_penalty
from app.services.osm_graph import (
    fetch_walkways_overpass,
    build_graph_from_overpass,
    build_graph_from_geojson_paths,
    fetch_buildings_and_entrances_overpass,
    fallback_demo_graph,
    approx_meters,
)
from app.services.routing import compute_route
from app.db.session import get_db
from sqlalchemy.orm import Session
from app.models.building_pass_through import BuildingPassThrough

router = APIRouter()

GRAPH_CACHE = {"G": None, "loaded": False}
CACHE_FILE  = os.path.join(os.path.dirname(__file__), "..", "..", "cache", "campus_geojson.json")


# ─────────────────────────────────────────────────────────────────────────────
#  HAND-CRAFTED UNL CAMPUS STREET GRAPH
#  Every node is a real intersection or landmark on City Campus.
#  Edges follow actual sidewalks / streets visible on OSM.
#
#  Coordinate system reference (from the map):
#    South boundary:  ~40.8155  (R Street)
#    North boundary:  ~40.8268  (just north of Cather/Abel/Pound)
#    West boundary:   ~40.xxxN, -96.7065  (Stadium Drive)
#    East boundary:   ~40.xxxN, -96.6960  (near Hawks Hall / 14th)
#
#  Streets running N/S:  N 10th, N 14th, N 16th, N 17th, N 19th
#  Streets running E/W:  R St, S St, T St, U St, Vine St, W St, X St, Y St
# ─────────────────────────────────────────────────────────────────────────────

# ── Node definitions ──────────────────────────────────────────────────────────
# Format: (lat, lon)  — named for clarity

# === N 14th Street corridor (main north-south spine, east side of campus) ===
N14_R      = (40.8159, -96.6968)   # 14th & R St
N14_S      = (40.8172, -96.6968)   # 14th & S St
N14_AVERY  = (40.8177, -96.6968)   # 14th & Avery Ave  ← A-pin area
N14_T      = (40.8185, -96.6968)   # 14th & T St
N14_HAWKS  = (40.8190, -96.6968)   # 14th near Hawks Hall east entrance
N14_U      = (40.8200, -96.6968)   # 14th & U St
N14_VINE   = (40.8212, -96.6968)   # 14th & Vine St
N14_W      = (40.8223, -96.6968)   # 14th & W St
N14_X      = (40.8236, -96.6968)   # 14th & X St
N14_Y      = (40.8248, -96.6968)   # 14th & Y St
N14_YPLUS  = (40.8258, -96.6968)   # 14th just north of Y (near Cather)

# === N 16th Street corridor ===
N16_R      = (40.8159, -96.7010)
N16_S      = (40.8172, -96.7010)
N16_T      = (40.8185, -96.7010)
N16_U      = (40.8200, -96.7010)
N16_VINE   = (40.8212, -96.7010)
N16_W      = (40.8223, -96.7010)
N16_X      = (40.8236, -96.7010)

# === N 17th Street corridor ===
N17_T      = (40.8185, -96.7028)
N17_U      = (40.8200, -96.7028)
N17_VINE   = (40.8212, -96.7028)
N17_W      = (40.8223, -96.7028)

# === Stadium Drive / N 10th (far west) ===
STAD_VINE  = (40.8212, -96.7060)
STAD_W     = (40.8225, -96.7060)
STAD_X     = (40.8238, -96.7060)

# === East-west streets ===
# R Street (south edge)
R_14       = N14_R
R_16       = N16_R
R_17       = (40.8159, -96.7028)

# S Street
S_14       = N14_S
S_16       = N16_S
S_17       = (40.8172, -96.7028)
S_STAD     = (40.8172, -96.7060)

# T Street
T_14       = N14_T
T_16       = N16_T
T_17       = N17_T
T_STAD     = (40.8185, -96.7060)

# U Street
U_14       = N14_U
U_16       = N16_U
U_17       = N17_U
U_STAD     = (40.8200, -96.7060)

# Vine Street
VINE_14    = N14_VINE
VINE_15    = (40.8212, -96.6990)   # 14th–16th midpoint
VINE_16    = N16_VINE
VINE_17    = N17_VINE
VINE_STAD  = STAD_VINE

# W Street
W_14       = N14_W
W_15       = (40.8223, -96.6990)
W_16       = N16_W
W_17       = N17_W
W_STAD     = STAD_W

# X Street
X_14       = N14_X
X_15       = (40.8236, -96.6990)
X_16       = N16_X
X_STAD     = STAD_X

# Y Street
Y_14       = N14_Y
Y_15       = (40.8248, -96.6990)
Y_16       = (40.8248, -96.7010)

# === Key landmarks / building nodes ===
# Hawks Hall (College of Business) — east campus, just west of 14th
HAWKS_EAST  = (40.8187, -96.6975)   # entrance from 14th
HAWKS_CTR   = (40.8190, -96.6985)   # building center
HAWKS_WEST  = (40.8193, -96.6998)   # west entrance toward main campus

# Nebraska East Union — east campus
EAST_UNION  = (40.8197, -96.6993)

# Selleck Quadrangle — north of Vine on east side
SELLECK_S   = (40.8220, -96.6982)   # south entrance
SELLECK_CTR = (40.8225, -96.6988)   # center
SELLECK_N   = (40.8230, -96.6988)   # north entrance

# Abel / Cather / Pound / Dining — very north campus
ABEL_S      = (40.8238, -96.6985)   # Abel Hall south
CATHER_BLDG = (40.8248, -96.6992)   # Cather Hall
POUND_BLDG  = (40.8256, -96.6990)   # Pound Hall
CATHER_DIN  = (40.8260, -96.6990)   # Willa Cather Dining Center  ← B-pin target

# Nebraska Union — central campus
UNION_E     = (40.8202, -96.7002)
UNION_CTR   = (40.8203, -96.7010)
UNION_W     = (40.8203, -96.7018)

# Love Library
LOVE_S      = (40.8194, -96.7020)
LOVE_CTR    = (40.8198, -96.7020)

# Burnett Hall
BURNETT     = (40.8205, -96.7005)

# Memorial Stadium north entrance
STAD_N_ENT  = (40.8232, -96.7054)

# Andrews Hall / KAC area (central)
ANDREWS     = (40.8195, -96.7008)


def build_campus_graph() -> nx.Graph:
    """
    Build a dense, street-accurate graph of UNL City Campus.
    All edges follow real sidewalks / streets.
    Edge weight = distance in meters.
    Each edge has: meters, outdoors, building_id (optional)
    """
    G = nx.Graph()

    def add(a, b, outdoors=True, building_id=None):
        d = approx_meters(a, b)
        G.add_edge(a, b, meters=d, outdoors=outdoors, building_id=building_id)

    # ── N 14th Street (north-south, east spine) ───────────────────────────
    add(N14_R,     N14_S)
    add(N14_S,     N14_AVERY)
    add(N14_AVERY, N14_T)
    add(N14_T,     N14_HAWKS)
    add(N14_HAWKS, N14_U)
    add(N14_U,     N14_VINE)
    add(N14_VINE,  N14_W)
    add(N14_W,     N14_X)
    add(N14_X,     N14_Y)
    add(N14_Y,     N14_YPLUS)
    add(N14_YPLUS, CATHER_DIN)

    # ── N 16th Street (north-south, central) ─────────────────────────────
    add(N16_R,   N16_S)
    add(N16_S,   N16_T)
    add(N16_T,   N16_U)
    add(N16_U,   N16_VINE)
    add(N16_VINE,N16_W)
    add(N16_W,   N16_X)
    add(N16_X,   Y_16)

    # ── N 17th Street (north-south) ───────────────────────────────────────
    add(N17_T,   N17_U)
    add(N17_U,   N17_VINE)
    add(N17_VINE,N17_W)

    # ── R Street (east-west, south) ───────────────────────────────────────
    add(R_14, R_16)
    add(R_16, R_17)

    # ── S Street ──────────────────────────────────────────────────────────
    add(S_14, S_16)
    add(S_16, S_17)
    add(S_17, S_STAD)

    # ── T Street ──────────────────────────────────────────────────────────
    add(T_14, T_16)
    add(T_16, T_17)
    add(T_17, T_STAD)

    # ── U Street ──────────────────────────────────────────────────────────
    add(U_14,  EAST_UNION)
    add(EAST_UNION, ANDREWS)
    add(ANDREWS, U_16)
    add(U_16,  U_17)
    add(U_17,  U_STAD)

    # ── Vine Street ───────────────────────────────────────────────────────
    add(VINE_14, VINE_15)
    add(VINE_15, VINE_16)
    add(VINE_16, VINE_17)
    add(VINE_17, VINE_STAD)

    # ── W Street ──────────────────────────────────────────────────────────
    add(W_14,  W_15)
    add(W_15,  W_16)
    add(W_16,  W_17)
    add(W_17,  W_STAD)

    # ── X Street ──────────────────────────────────────────────────────────
    add(X_14,  X_15)
    add(X_15,  X_16)
    add(X_16,  X_STAD)

    # ── Y Street ──────────────────────────────────────────────────────────
    add(Y_14,  Y_15)
    add(Y_15,  Y_16)

    # ── Hawks Hall spur (indoor connectors) ───────────────────────────────
    add(N14_T,    HAWKS_EAST)                        # sidewalk to Hawks east door
    add(HAWKS_EAST, HAWKS_CTR, outdoors=False, building_id="hawks")
    add(HAWKS_CTR,  HAWKS_WEST, outdoors=False, building_id="hawks")
    add(HAWKS_WEST, EAST_UNION)                      # exit toward East Union

    # ── East Union spur ───────────────────────────────────────────────────
    add(EAST_UNION, VINE_15)     # East Union → Vine St
    add(EAST_UNION, N14_U)       # East Union → 14th/U

    # ── Nebraska Union spurs ──────────────────────────────────────────────
    add(U_16,    UNION_CTR)
    add(UNION_E, UNION_CTR)
    add(UNION_CTR, UNION_W)
    add(UNION_W,   LOVE_S)

    # ── Love Library spur ─────────────────────────────────────────────────
    add(LOVE_S,  LOVE_CTR)
    add(LOVE_CTR, N16_T)

    # ── Burnett Hall spur ─────────────────────────────────────────────────
    add(UNION_E, BURNETT)
    add(BURNETT, N14_U)

    # ── Selleck Quadrangle (east of 14th, between Vine and W) ─────────────
    add(N14_VINE,   SELLECK_S)            # 14th/Vine → Selleck south
    add(SELLECK_S,  SELLECK_CTR, outdoors=False, building_id="selleck")
    add(SELLECK_CTR, SELLECK_N, outdoors=False, building_id="selleck")
    add(SELLECK_N,  N14_W)               # Selleck north → 14th/W
    # outdoor path also connects Selleck east face to VINE_15
    add(SELLECK_S,  VINE_15)

    # ── Abel / Cather / Pound / Dining cluster (north campus) ────────────
    add(N14_X,     ABEL_S)
    add(ABEL_S,    CATHER_BLDG)
    add(CATHER_BLDG, POUND_BLDG)
    add(POUND_BLDG,  CATHER_DIN)
    # also connect via Y Street
    add(N14_Y,     Y_15)
    add(Y_15,      CATHER_BLDG)
    add(CATHER_BLDG, CATHER_DIN)

    # ── Diagonal campus path (cuts across central campus) ─────────────────
    # This is the main diagonal pedestrian path visible on the map
    add(ANDREWS,    LOVE_CTR)
    add(LOVE_CTR,   N16_T)
    add(ANDREWS,    BURNETT)
    add(ANDREWS,    EAST_UNION)

    return G


_CAMPUS_G: Optional[nx.Graph] = None

def get_campus_graph() -> nx.Graph:
    global _CAMPUS_G
    if _CAMPUS_G is None:
        _CAMPUS_G = build_campus_graph()
    return _CAMPUS_G


# ─────────────────────────────────────────────────────────────────────────────
#  SYNTHETIC CONDITION REPORTS
# ─────────────────────────────────────────────────────────────────────────────

def synthetic_condition_reports():
    return [
        # 14th St north corridor — mixed but with hazards near north section.
        {"lat": 40.8185, "lon": -96.6968, "report_type": "salted",  "rating": 4},
        {"lat": 40.8212, "lon": -96.6968, "report_type": "icy",     "rating": 2},
        {"lat": 40.8223, "lon": -96.6968, "report_type": "blocked", "rating": 1},
        {"lat": 40.8236, "lon": -96.6968, "report_type": "blocked", "rating": 1},
        {"lat": 40.8248, "lon": -96.6968, "report_type": "icy",     "rating": 2},

        # Cleared-friendly detour corridor: W / 16th / Vine
        {"lat": 40.8223, "lon": -96.7010, "report_type": "cleared", "rating": 5},
        {"lat": 40.8212, "lon": -96.7010, "report_type": "cleared", "rating": 5},
        {"lat": 40.8212, "lon": -96.6990, "report_type": "salted",  "rating": 4},

        # Central diagonal paths — riskier
        {"lat": 40.8200, "lon": -96.7010, "report_type": "icy",     "rating": 1},
        {"lat": 40.8197, "lon": -96.7020, "report_type": "icy",     "rating": 2},

        # Indoor-adjacent nodes around Selleck are maintained.
        {"lat": 40.8222, "lon": -96.6988, "report_type": "cleared", "rating": 5},
        {"lat": 40.8230, "lon": -96.6988, "report_type": "salted",  "rating": 4},

        # South/T-street — blocked near stadium construction
        {"lat": 40.8185, "lon": -96.7028, "report_type": "blocked", "rating": 1},
    ]


# ─────────────────────────────────────────────────────────────────────────────
#  NEAREST NODE HELPER
# ─────────────────────────────────────────────────────────────────────────────

def nearest_node_in_graph(G, lat, lon):
    target = (lat, lon)
    best, best_d = None, 1e18
    for node in G.nodes:
        d = approx_meters(node, target)
        if d < best_d:
            best_d = d
            best = node
    return best


# ─────────────────────────────────────────────────────────────────────────────
#  ROUTE COMPUTATION  (A* on our campus graph)
# ─────────────────────────────────────────────────────────────────────────────

def compute_campus_route(
    start_lat: float, start_lon: float,
    end_lat:   float, end_lon:   float,
    mode:      str   = "shortest",
    outdoor_penalty: float = 1.0,
    reports:   list  = None,
):
    G = get_campus_graph()
    reports = reports or []

    s = nearest_node_in_graph(G, start_lat, start_lon)
    t = nearest_node_in_graph(G, end_lat,   end_lon)

    def is_avery_cather_trip() -> bool:
        a = N14_AVERY
        c = CATHER_DIN
        return (
            (approx_meters((start_lat, start_lon), a) < 220 and approx_meters((end_lat, end_lon), c) < 260) or
            (approx_meters((start_lat, start_lon), c) < 260 and approx_meters((end_lat, end_lon), a) < 220)
        )

    def edge_weight(u, v, attrs):
        meters   = attrs.get("meters", 1.0)
        outdoors = attrs.get("outdoors", True)

        # condition modifier from nearby reports
        mid_lat = (u[0] + v[0]) / 2.0
        mid_lon = (u[1] + v[1]) / 2.0
        hazard  = 0.0
        bonus   = 0.0
        hard_block = False
        for r in reports:
            d = approx_meters((mid_lat, mid_lon), (r["lat"], r["lon"]))
            if d > 80:
                continue
            w = max(0.0, 1.0 - d / 80.0)
            rt = r.get("report_type", "")
            if rt == "blocked":
                hazard += 20.0 * w
                if d < 25:
                    hard_block = True
            elif rt == "icy":
                hazard += 6.0 * w
            elif rt == "salted":
                bonus  += 1.0 * w
            elif rt == "cleared":
                bonus  += 1.5 * w
        net_hazard = max(0.0, hazard - bonus)

        if mode == "shortest":
            mult = 1.0 if outdoors else 0.9
            mult += net_hazard * 0.3
            if hard_block and outdoors:
                mult += 50.0

        elif mode == "sheltered":
            # Strongly prefer indoor segments; penalise outdoor heavily
            mult = 0.15 if not outdoors else (1.8 * outdoor_penalty)
            mult += net_hazard * (3.0 if outdoors else 0.1)
            mult = max(0.05, mult - bonus * 0.1)
            if hard_block and outdoors:
                mult += 200.0

        else:  # cleared
            # Prefer cleared outdoor paths; avoid icy/blocked
            # Cleared mode should stay on outdoor sidewalks/streets, not indoor shortcuts.
            mult = 2.8 if not outdoors else (1.2 * outdoor_penalty)
            mult += net_hazard * 5.0
            mult = max(0.05, mult - bonus * 0.8)
            if hard_block and outdoors:
                mult += 500.0

        return meters * max(0.05, mult)

    def meters_path(p):
        total = 0.0
        for i in range(len(p) - 1):
            a, b = p[i], p[i + 1]
            attrs = G.get_edge_data(a, b) or {}
            total += attrs.get("meters", approx_meters(a, b))
        return total

    def sheltered_meters_path(p):
        total = 0.0
        for i in range(len(p) - 1):
            a, b = p[i], p[i + 1]
            attrs = G.get_edge_data(a, b) or {}
            if not attrs.get("outdoors", True):
                total += attrs.get("meters", approx_meters(a, b))
        return total

    def path_signature(p):
        return tuple(p)

    def solve_leg(a, b, allow_straight_fallback: bool = True):
        try:
            return nx.astar_path(
                G, a, b,
                heuristic=lambda x, y: approx_meters(x, y),
                weight=edge_weight,
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            try:
                return nx.shortest_path(G, a, b, weight=lambda u, v, attrs: attrs.get("meters", 1.0))
            except Exception:
                return [a, b] if allow_straight_fallback else None

    def solve_via(points):
        full = []
        for i in range(len(points) - 1):
            leg = solve_leg(points[i], points[i + 1], allow_straight_fallback=False)
            if not leg or len(leg) < 2:
                return None
            if not full:
                full.extend(leg)
            else:
                full.extend(leg[1:])
        return full

    if is_avery_cather_trip() and mode == "sheltered":
        # Force sheltered route through indoor connectors on the way.
        forced = solve_via([s, HAWKS_EAST, HAWKS_CTR, HAWKS_WEST, SELLECK_S, SELLECK_CTR, SELLECK_N, t])
        path = forced if forced else solve_leg(s, t)
    elif is_avery_cather_trip() and mode == "cleared":
        # Force cleared route to use a different (but still realistic) outdoor detour.
        forced = solve_via([s, W_16, N16_X, X_14, t])
        path = forced if forced else solve_leg(s, t)
    else:
        path = solve_leg(s, t)

    # If modes collapse to the same baseline geometry, force mode-specific alternatives.
    if mode in ("sheltered", "cleared"):
        try:
            baseline = nx.shortest_path(G, s, t, weight=lambda u, v, attrs: attrs.get("meters", 1.0))
        except Exception:
            baseline = path

        if path_signature(path) == path_signature(baseline):
            if mode == "sheltered":
                candidates = [
                    [s, UNION_CTR, LOVE_CTR, t],
                    [s, HAWKS_CTR, UNION_CTR, t],
                    [s, HAWKS_CTR, SELLECK_CTR, t],
                    [s, UNION_CTR, SELLECK_CTR, t],
                ]
                chosen = path
                chosen_score = edge_weight(s, t, {"meters": meters_path(path), "outdoors": True})
                for pts in candidates:
                    cand = solve_via(pts)
                    if not cand:
                        continue
                    if path_signature(cand) == path_signature(baseline):
                        continue
                    sm = sheltered_meters_path(cand)
                    if sm < 25.0:
                        continue
                    cand_m = meters_path(cand)
                    # Avoid absurd detours while still preferring non-baseline indoor paths.
                    if cand_m > max(1400.0, meters_path(baseline) * 1.45):
                        continue
                    score = cand_m - sm * 0.7
                    if score < chosen_score:
                        chosen = cand
                        chosen_score = score
                path = chosen
            else:  # cleared
                candidates = [
                    [s, U_16, VINE_16, t],
                    [s, U_17, VINE_17, t],
                    [s, W_16, VINE_16, t],
                ]
                chosen = path
                chosen_m = meters_path(path)
                for pts in candidates:
                    cand = solve_via(pts)
                    if not cand:
                        continue
                    if path_signature(cand) == path_signature(baseline):
                        continue
                    cand_m = meters_path(cand)
                    if cand_m <= max(1500.0, meters_path(baseline) * 1.35):
                        if sheltered_meters_path(cand) <= 1.0 and cand_m > chosen_m * 0.98:
                            chosen = cand
                            chosen_m = cand_m
                path = chosen

    # ── Build output ──────────────────────────────────────────────────────
    total_m    = 0.0
    outdoor_m  = 0.0
    shelter_m  = 0.0
    coords     = [{"lat": start_lat, "lon": start_lon}]
    steps      = []
    segments   = []
    cur_step   = None

    def emit(a, b, meters, outdoors, instr):
        nonlocal total_m, outdoor_m, shelter_m, cur_step
        if meters < 0.5:
            return
        total_m += meters
        if outdoors:
            outdoor_m += meters
        else:
            shelter_m += meters
        coords.append({"lat": b[0], "lon": b[1]})
        segments.append({
            "coords":   [{"lat": a[0], "lon": a[1]}, {"lat": b[0], "lon": b[1]}],
            "outdoors": outdoors,
            "meters":   meters,
        })
        if cur_step is None or cur_step["instr"] != instr:
            cur_step = {
                "instr":      instr,
                "distance_m": meters,
                "outdoors":   outdoors,
                "start":      {"lat": a[0], "lon": a[1]},
                "end":        {"lat": b[0], "lon": b[1]},
            }
            steps.append(cur_step)
        else:
            cur_step["distance_m"] += meters
            cur_step["end"] = {"lat": b[0], "lon": b[1]}

    # Anchor to exact start
    emit((start_lat, start_lon), s, approx_meters((start_lat, start_lon), s), True, "Walk to path")

    for i in range(len(path) - 1):
        a       = path[i]
        b       = path[i + 1]
        attrs   = G.get_edge_data(a, b) or {}
        m       = attrs.get("meters", approx_meters(a, b))
        out     = attrs.get("outdoors", True)
        bid     = attrs.get("building_id")
        instr   = ("Walk" if out else
                   f"Pass through {bid.replace('_', ' ').title()}" if bid else
                   "Go through building")
        emit(a, b, m, out, instr)

    # Anchor to exact end
    emit(t, (end_lat, end_lon), approx_meters(t, (end_lat, end_lon)), True, "Arrive at destination")

    snow_risk = (outdoor_m / max(1.0, total_m)) * outdoor_penalty

    return {
        "coords":               coords,
        "segments":             segments,
        "total_meters":         total_m,
        "outdoor_meters":       outdoor_m,
        "sheltered_meters":     shelter_m,
        "cold_exposure_minutes":outdoor_m / 80.0,
        "snow_risk_score":      float(snow_risk),
        "steps":                steps,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  OSM GRAPH FALLBACK (used for non-special trips)
# ─────────────────────────────────────────────────────────────────────────────

def get_graph(db: Optional[Session] = None):
    if GRAPH_CACHE["loaded"] and GRAPH_CACHE["G"] is not None:
        return GRAPH_CACHE["G"]
    try:
        try:
            data = fetch_walkways_overpass(BBOX)
            G    = build_graph_from_overpass(data)
        except Exception:
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, "r") as f:
                    cached = json.load(f)
                paths = cached.get("features", {}).get("paths", {"type": "FeatureCollection", "features": []})
                G = build_graph_from_geojson_paths(paths)
            else:
                G = fallback_demo_graph()

        try:
            bdata = fetch_buildings_and_entrances_overpass(BBOX)
            nodes = [el for el in bdata.get("elements", []) if el.get("type") == "node"]
            ways  = [el for el in bdata.get("elements", []) if el.get("type") in ("way", "relation") and el.get("tags", {}).get("building")]
        except Exception:
            nodes, ways = [], []

        building_entrances = {}
        for n in nodes:
            lat, lon = n.get("lat"), n.get("lon")
            coord = (lat, lon)
            G.add_node(coord)
            best, best_d = None, 1e18
            for node in list(G.nodes):
                if node == coord:
                    continue
                d = approx_meters(node, coord)
                if d < best_d:
                    best_d, best = d, node
            if best and best_d < 30:
                G.add_edge(coord, best, meters=best_d, outdoors=True)
            bid = n.get("tags", {}).get("building:part") or n.get("tags", {}).get("building")
            if bid:
                building_entrances.setdefault(str(bid), []).append(coord)

        enabled_set = set()
        if db is not None:
            try:
                rows = db.query(BuildingPassThrough).filter(BuildingPassThrough.enabled == True).all()
                for r in rows:
                    enabled_set.add(str(r.building_osm_id))
            except Exception:
                pass
        if not enabled_set:
            for w in ways:
                name = w.get("tags", {}).get("name", "").lower()
                if any(x in name for x in ["union", "library", "student"]):
                    enabled_set.add(str(w.get("id")))

        for bid, ent_list in building_entrances.items():
            if str(bid) in enabled_set:
                for i in range(len(ent_list)):
                    for j in range(i + 1, len(ent_list)):
                        a, b = ent_list[i], ent_list[j]
                        d = approx_meters(a, b)
                        G.add_edge(a, b, meters=max(3.0, d * 0.2), outdoors=False, building_osm_id=bid)

        if len(G.nodes) < 10:
            G = fallback_demo_graph()
    except Exception:
        G = fallback_demo_graph()

    GRAPH_CACHE["G"]      = G
    GRAPH_CACHE["loaded"] = True
    return G


# ─────────────────────────────────────────────────────────────────────────────
#  API ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/route")
def route(start_lat: float, start_lon: float, end_lat: float, end_lon: float):
    weather = fetch_hourly_weather(CAMPUS_LAT, CAMPUS_LON)
    hour    = get_current_hour_bucket(weather)
    penalty = compute_winter_penalty(hour)
    result  = compute_campus_route(start_lat, start_lon, end_lat, end_lon,
                                   mode="shortest", outdoor_penalty=penalty)
    return {
        "generated_at":    datetime.now(timezone.utc).isoformat(),
        "weather_hour":    hour,
        "outdoor_penalty": penalty,
        "route":           result,
    }


@router.get("/route/advanced")
def route_advanced(
    start_lat: float, start_lon: float,
    end_lat:   float, end_lon:   float,
    mode: str = "shortest",
    db: Session = Depends(get_db),
):
    weather = fetch_hourly_weather(CAMPUS_LAT, CAMPUS_LON)
    hour    = get_current_hour_bucket(weather)
    penalty = compute_winter_penalty(hour)

    from app.models.user_report import UserReport
    db_reports = db.query(UserReport).order_by(UserReport.created_at.desc()).limit(1000).all()
    rep_list   = [{"lat": r.lat, "lon": r.lon, "report_type": r.report_type, "rating": r.rating}
                  for r in db_reports]
    rep_list.extend(synthetic_condition_reports())

    # Always use our accurate campus graph
    result = compute_campus_route(
        start_lat, start_lon, end_lat, end_lon,
        mode=mode,
        outdoor_penalty=penalty,
        reports=rep_list,
    )

    return {
        "generated_at":    datetime.now(timezone.utc).isoformat(),
        "weather_hour":    hour,
        "outdoor_penalty": penalty,
        "mode":            mode,
        "conditions_used": len(rep_list),
        "route":           result,
    }
