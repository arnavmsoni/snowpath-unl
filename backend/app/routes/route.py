from fastapi import APIRouter, Depends
from datetime import datetime, timezone
from typing import Optional
from app.config import CAMPUS_LAT, CAMPUS_LON, BBOX
from app.services.weather import fetch_hourly_weather, get_current_hour_bucket, compute_winter_penalty
from app.services.osm_graph import fetch_walkways_overpass, build_graph_from_overpass, fetch_buildings_and_entrances_overpass, fallback_demo_graph, approx_meters
from app.services.routing import compute_route
from app.db.session import get_db
from sqlalchemy.orm import Session
from app.models.building_pass_through import BuildingPassThrough

router = APIRouter()

GRAPH_CACHE = {"G": None, "loaded": False}


def get_graph(db: Optional[Session] = None):
    if GRAPH_CACHE["loaded"] and GRAPH_CACHE["G"] is not None:
        return GRAPH_CACHE["G"]
    try:
        data = fetch_walkways_overpass(BBOX)
        G = build_graph_from_overpass(data)
        # add entrances and indoor connectors
        bdata = fetch_buildings_and_entrances_overpass(BBOX)
        nodes = [el for el in bdata.get("elements", []) if el.get("type") == "node"]
        ways = [el for el in bdata.get("elements", []) if el.get("type") in ("way", "relation") and el.get("tags", {}).get("building")]

        # map building id -> list of entrance coords
        building_entrances = {}
        for n in nodes:
            lat = n.get("lat")
            lon = n.get("lon")
            coord = (lat, lon)
            G.add_node(coord)
            # connect entrance to nearest walkway node within 30m
            best = None
            best_d = 1e18
            for node in list(G.nodes):
                if node == coord:
                    continue
                d = approx_meters(node, coord)
                if d < best_d:
                    best_d = d
                    best = node
            if best and best_d < 30:
                G.add_edge(coord, best, meters=best_d, outdoors=True)

            bid = n.get("tags", {}).get("building:part") or n.get("tags", {}).get("building") or None
            if bid:
                building_entrances.setdefault(str(bid), []).append(coord)

        # indoor connectors for buildings marked in DB as pass-through
        enabled_set = set()
        if db is not None:
            try:
                rows = db.query(BuildingPassThrough).filter(BuildingPassThrough.enabled == True).all()
                for r in rows:
                    enabled_set.add(str(r.building_osm_id))
            except Exception:
                enabled_set = set()

        # fallback small seed: allow common pass-throughs like Student Union by name check
        if not enabled_set:
            # try to enable common ones by slug
            for w in ways:
                name = w.get("tags", {}).get("name", "").lower()
                if any(x in name for x in ["union", "library", "student"]):
                    enabled_set.add(str(w.get("id")))

        for bid, ent_list in building_entrances.items():
            if str(bid) in enabled_set:
                # connect all pairs inside building with sheltered edges
                for i in range(len(ent_list)):
                    for j in range(i + 1, len(ent_list)):
                        a = ent_list[i]
                        b = ent_list[j]
                        d = approx_meters(a, b)
                        G.add_edge(a, b, meters=max(3.0, d * 0.2), outdoors=False, building_osm_id=bid)

        if len(G.nodes) < 10:
            G = fallback_demo_graph()
    except Exception:
        G = fallback_demo_graph()
    GRAPH_CACHE["G"] = G
    GRAPH_CACHE["loaded"] = True
    return G


@router.get("/route")
def route(start_lat: float, start_lon: float, end_lat: float, end_lon: float):
    weather = fetch_hourly_weather(CAMPUS_LAT, CAMPUS_LON)
    hour = get_current_hour_bucket(weather)
    penalty = compute_winter_penalty(hour)

    G = get_graph()
    result = compute_route(G, start_lat, start_lon, end_lat, end_lon, outdoor_penalty=penalty)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "weather_hour": hour,
        "outdoor_penalty": penalty,
        "route": result,
    }


@router.get("/route/advanced")
def route_advanced(start_lat: float, start_lon: float, end_lat: float, end_lon: float, mode: str = "shortest", db: Session = Depends(get_db)):
    """Advanced route endpoint supporting mode=shortest|sheltered|cleared"""
    weather = fetch_hourly_weather(CAMPUS_LAT, CAMPUS_LON)
    hour = get_current_hour_bucket(weather)
    penalty = compute_winter_penalty(hour)

    # load reports in bbox around campus (simple)
    from app.models.user_report import UserReport
    reports = db.query(UserReport).order_by(UserReport.created_at.desc()).limit(1000).all()
    rep_list = []
    for r in reports:
        rep_list.append({"lat": r.lat, "lon": r.lon, "report_type": r.report_type, "rating": r.rating})

    G = get_graph(db)
    # pass set of enabled pass-through building ids
    from app.models.building_pass_through import BuildingPassThrough
    rows = db.query(BuildingPassThrough).filter(BuildingPassThrough.enabled == True).all()
    enabled = set([str(r.building_osm_id) for r in rows])

    result = compute_route(G, start_lat, start_lon, end_lat, end_lon, mode=mode, outdoor_penalty=penalty, reports=rep_list, pass_through_enabled=enabled)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "weather_hour": hour,
        "outdoor_penalty": penalty,
        "mode": mode,
        "route": result,
    }