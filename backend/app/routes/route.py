from fastapi import APIRouter
from datetime import datetime, timezone
from app.config import CAMPUS_LAT, CAMPUS_LON, BBOX
from app.services.weather import fetch_hourly_weather, get_current_hour_bucket, compute_winter_penalty
from app.services.osm_graph import fetch_walkways_overpass, build_graph_from_overpass, fallback_demo_graph
from app.services.routing import compute_route

router = APIRouter()

GRAPH_CACHE = {"G": None, "loaded": False}

def get_graph():
    if GRAPH_CACHE["loaded"] and GRAPH_CACHE["G"] is not None:
        return GRAPH_CACHE["G"]
    try:
        data = fetch_walkways_overpass(BBOX)
        G = build_graph_from_overpass(data)
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