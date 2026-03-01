import os
import json
import re
from fastapi import APIRouter, HTTPException, Depends, Body
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from app.services.osm_graph import fetch_buildings_and_entrances_overpass, fetch_walkways_overpass
from app.config import CAMPUS_LAT, CAMPUS_LON
from app.db.session import get_db
from sqlalchemy.orm import Session
from app.models.user_report import UserReport
from app.models.building_pass_through import BuildingPassThrough

router = APIRouter()


class RouteModeDescriptor(BaseModel):
    mode: str
    title: str
    behavior: str


class PredictionDescriptor(BaseModel):
    name: str
    signals: List[str]
    output: str
    where_used: str


class FeatureDescriptor(BaseModel):
    name: str
    summary: str


class DemoScriptLine(BaseModel):
    order: int
    text: str


class PlatformCapabilitiesResponse(BaseModel):
    product_name: str
    one_liner: str
    route_modes: List[RouteModeDescriptor]
    predictive_components: List[PredictionDescriptor]
    visible_metrics: List[FeatureDescriptor]
    demo_forecasting: List[FeatureDescriptor]
    narrative_script: List[DemoScriptLine]


ROUTE_MODE_DESCRIPTORS = [
    RouteModeDescriptor(
        mode="shortest",
        title="Fastest",
        behavior="Prioritizes travel time and direct path efficiency.",
    ),
    RouteModeDescriptor(
        mode="sheltered",
        title="Sheltered",
        behavior="Prioritizes indoor connectors to reduce outdoor cold exposure.",
    ),
    RouteModeDescriptor(
        mode="cleared",
        title="Cleared",
        behavior="Prioritizes safer outdoor segments using condition reports.",
    ),
]

PREDICTIVE_COMPONENTS = [
    PredictionDescriptor(
        name="Near-term weather risk prediction",
        signals=["snowfall", "wind_speed_10m", "temperature_2m", "precipitation"],
        output="outdoor_penalty and snow_risk_score",
        where_used="route and route/advanced scoring",
    ),
    PredictionDescriptor(
        name="Path-condition risk prediction",
        signals=["blocked reports", "icy reports", "salted reports", "cleared reports"],
        output="segment-level hazard/bonus adjustment",
        where_used="mode-aware edge weighting",
    ),
    PredictionDescriptor(
        name="Foot-traffic hotspot forecasting",
        signals=["time-of-day", "campus event patterns"],
        output="synthetic traffic intensity points",
        where_used="/traffic endpoint for demo and evaluation",
    ),
]

VISIBLE_METRICS = [
    FeatureDescriptor(name="Distance", summary="Total route distance in kilometers/meters."),
    FeatureDescriptor(name="Outdoor exposure", summary="Outdoor vs sheltered meters and cold exposure minutes."),
    FeatureDescriptor(name="Snow risk score", summary="Weather-adjusted route risk indicator."),
    FeatureDescriptor(name="Turn-by-turn", summary="Step list with direction and segment type."),
]

FORECASTING_FEATURES = [
    FeatureDescriptor(name="Synthetic event feed", summary="Likely event clusters generated near campus landmarks."),
    FeatureDescriptor(name="Synthetic traffic feed", summary="Predicted hotspot points with intensity and optional DB storage."),
]

NARRATIVE_SCRIPT = [
    DemoScriptLine(order=1, text="This is an average winter day at UNL with SnowPath."),
    DemoScriptLine(order=2, text="You enter a start and end destination, and the app generates three route options."),
    DemoScriptLine(order=3, text="Fastest prioritizes travel time, Sheltered prioritizes indoor connectors, and Cleared prioritizes safer reported outdoor paths."),
    DemoScriptLine(order=4, text="Under the hood, SnowPath predicts near-term walking risk using live weather signals like snowfall, wind, and freezing conditions."),
    DemoScriptLine(order=5, text="It combines those signals with path-condition reports such as blocked, icy, salted, and cleared segments."),
    DemoScriptLine(order=6, text="You can see distance, outdoor exposure, snow-risk metrics, and turn-by-turn instructions."),
    DemoScriptLine(order=7, text="For demo forecasting, SnowPath also generates likely foot-traffic hotspots from time-of-day and event patterns."),
    DemoScriptLine(order=8, text="So this is not just map directions; it is predictive risk routing for real winter walking decisions."),
]

CACHE_DIR  = os.path.join(os.path.dirname(__file__), "..", "..", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_FILE = os.path.join(CACHE_DIR, "campus_geojson.json")

# ─── CORRECTED Building Coordinates ─────────────────────────────────────────
# Key fixes:
# - Willa Cather Dining is at the NORTH end of campus (~40.8253) near Abel/Cather residence halls
# - 14th & Avery is the SW corner near Hawks Hall (~40.8174, -96.6969)
# - Hawks Hall (Business) is just east of 14th St on the south side

CURATED_LANDMARKS = [
    # Intersections
    {"name": "14th and Avery",      "lat": 40.8177, "lon": -96.6968, "type": "landmark"},
    {"name": "14th & Avery",            "lat": 40.8174, "lon": -96.6969, "type": "landmark"},

    # Dining
    {"name": "Cather Dining Hall",      "lat": 40.8260, "lon": -96.6990, "type": "landmark"},
    {"name": "Cather Dining",           "lat": 40.8260, "lon": -96.6990, "type": "landmark"},
    {"name": "Willa Cather Dining",     "lat": 40.8260, "lon": -96.6990, "type": "landmark"},
    {"name": "Cather-Pound Dining",     "lat": 40.8253, "lon": -96.6990, "type": "landmark"},

    # Residence Halls
    {"name": "Cather Hall",             "lat": 40.8249, "lon": -96.6992, "type": "landmark"},
    {"name": "Abel Hall",               "lat": 40.8240, "lon": -96.6985, "type": "landmark"},
    {"name": "Selleck Quadrangle",      "lat": 40.8222, "lon": -96.6988, "type": "landmark"},
    {"name": "Pound Hall",              "lat": 40.8255, "lon": -96.6990, "type": "landmark"},
    {"name": "Gaylord Hall",            "lat": 40.8245, "lon": -96.6988, "type": "landmark"},
    {"name": "Thunderbird Hall",        "lat": 40.8242, "lon": -96.6985, "type": "landmark"},

    # Academic Buildings
    {"name": "Avery Hall",              "lat": 40.8180, "lon": -96.7015, "type": "landmark"},
    {"name": "Hawks Hall",              "lat": 40.8186, "lon": -96.6968, "type": "landmark"},
    {"name": "Howard L. Hawks Hall",    "lat": 40.8186, "lon": -96.6968, "type": "landmark"},
    {"name": "College of Business",     "lat": 40.8186, "lon": -96.6972, "type": "landmark"},
    {"name": "Memorial Stadium",        "lat": 40.8231, "lon": -96.7054, "type": "landmark"},
    {"name": "Nebraska Union",          "lat": 40.8202, "lon": -96.7009, "type": "landmark"},
    {"name": "Nebraska East Union",     "lat": 40.8196, "lon": -96.6990, "type": "landmark"},
    {"name": "Love Library",            "lat": 40.8197, "lon": -96.7019, "type": "landmark"},
    {"name": "Scott Engineering Center","lat": 40.8183, "lon": -96.7005, "type": "landmark"},
    {"name": "Student Rec Center",      "lat": 40.8207, "lon": -96.7042, "type": "landmark"},
    {"name": "Morrill Hall",            "lat": 40.8204, "lon": -96.7030, "type": "landmark"},
    {"name": "Burnett Hall",            "lat": 40.8205, "lon": -96.7005, "type": "landmark"},
    {"name": "Bessey Hall",             "lat": 40.8196, "lon": -96.7032, "type": "landmark"},
    {"name": "Sheldon Museum of Art",   "lat": 40.8197, "lon": -96.7003, "type": "landmark"},
]

EXACT_QUERY_OVERRIDES = {
    "14th and avery":       {"name": "14th and Avery",      "lat": 40.8177, "lon": -96.6968, "type": "landmark"},
    "14th avery":           {"name": "14th and Avery",      "lat": 40.8177, "lon": -96.6968, "type": "landmark"},
    "14th & avery":         {"name": "14th and Avery",      "lat": 40.8177, "lon": -96.6968, "type": "landmark"},
    "avery hall":           {"name": "Avery Hall",           "lat": 40.8180, "lon": -96.7015, "type": "landmark"},
    "cather hall":          {"name": "Cather Hall",          "lat": 40.8249, "lon": -96.6992, "type": "landmark"},
    "cather dining hall":   {"name": "Cather Dining Hall",      "lat": 40.8260, "lon": -96.6990, "type": "landmark"},
    "cather dining":        {"name": "Cather Dining Hall",      "lat": 40.8260, "lon": -96.6990, "type": "landmark"},
    "willa cather dining":  {"name": "Willa Cather Dining",     "lat": 40.8260, "lon": -96.6990, "type": "landmark"},
    "cather pound dining":  {"name": "Cather-Pound Dining",  "lat": 40.8253, "lon": -96.6990, "type": "landmark"},
    "college of business":  {"name": "College of Business",  "lat": 40.8186, "lon": -96.6972, "type": "landmark"},
    "hawks hall":           {"name": "Hawks Hall",           "lat": 40.8186, "lon": -96.6968, "type": "landmark"},
    "selleck":              {"name": "Selleck Quadrangle",   "lat": 40.8222, "lon": -96.6988, "type": "landmark"},
    "selleck quadrangle":   {"name": "Selleck Quadrangle",   "lat": 40.8222, "lon": -96.6988, "type": "landmark"},
    "abel hall":            {"name": "Abel Hall",            "lat": 40.8240, "lon": -96.6985, "type": "landmark"},
    "memorial stadium":     {"name": "Memorial Stadium",     "lat": 40.8231, "lon": -96.7054, "type": "landmark"},
    "nebraska union":       {"name": "Nebraska Union",       "lat": 40.8202, "lon": -96.7009, "type": "landmark"},
    "love library":         {"name": "Love Library",         "lat": 40.8197, "lon": -96.7019, "type": "landmark"},
}

CANONICAL_BUILDING_COORDS = {
    # Dining (NORTH campus — key fix)
    "willa cather dining":              (40.8253, -96.6990),
    "willa s cather dining center":     (40.8253, -96.6990),
    "willa s. cather dining center":    (40.8253, -96.6990),
    "cather pound dining":              (40.8253, -96.6990),
    "cather pound dining hall":         (40.8253, -96.6990),
    "cather dining":                    (40.8253, -96.6990),
    "cather dining hall":               (40.8253, -96.6990),

    # Residence halls (north campus)
    "cather hall":                      (40.8249, -96.6992),
    "abel hall":                        (40.8240, -96.6985),
    "gaylord hall":                     (40.8245, -96.6988),
    "thunderbird hall":                 (40.8242, -96.6985),
    "pound hall":                       (40.8255, -96.6990),
    "selleck quadrangle":               (40.8222, -96.6988),
    "selleck":                          (40.8222, -96.6988),

    # South/central campus
    "avery hall":                       (40.8180, -96.7015),
    "college of business":              (40.8186, -96.6972),
    "hawks hall":                       (40.8186, -96.6968),
    "howard l hawks hall":              (40.8186, -96.6968),
    "howard l. hawks hall":             (40.8186, -96.6968),
    "nebraska union":                   (40.8202, -96.7009),
    "nebraska east union":              (40.8196, -96.6990),
    "memorial stadium":                 (40.8231, -96.7054),
    "love library":                     (40.8197, -96.7019),
    "love memorial hall":               (40.8197, -96.7019),
    "student rec center":               (40.8207, -96.7042),
    "scott engineering center":         (40.8183, -96.7005),
    "walter scott engineering center":  (40.8183, -96.7005),
    "sheldon museum of art":            (40.8197, -96.7003),
    "morrill hall":                     (40.8204, -96.7030),
}


def _elements_to_building_feature(el):
    props = {
        "osm_id": el.get("id"),
        "name":   el.get("tags", {}).get("name"),
        "type":   el.get("type"),
    }
    geom   = el.get("geometry") or []
    coords = [[p["lon"], p["lat"]] for p in geom]
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])
    return {"type": "Feature", "properties": props, "geometry": {"type": "Polygon", "coordinates": [coords]}}


def _way_to_line_feature(el):
    props  = {"osm_id": el.get("id"), "tags": el.get("tags", {})}
    geom   = el.get("geometry") or []
    coords = [[p["lon"], p["lat"]] for p in geom]
    return {"type": "Feature", "properties": props, "geometry": {"type": "LineString", "coordinates": coords}}


def _node_to_point_feature(el):
    props = {"osm_id": el.get("id"), "tags": el.get("tags", {})}
    lat   = el.get("lat")
    lon   = el.get("lon")
    return {"type": "Feature", "properties": props, "geometry": {"type": "Point", "coordinates": [lon, lat]}}


@router.get("/campus/geojson")
def campus_geojson(bbox: Optional[str] = None):
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)

    from app.config import BBOX
    b = bbox or BBOX

    try:
        bdata = fetch_buildings_and_entrances_overpass(b)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Overpass buildings request failed: {e}")

    try:
        wdata = fetch_walkways_overpass(b)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Overpass ways request failed: {e}")

    buildings = [el for el in bdata.get("elements", []) if el.get("type") in ("way", "relation") and el.get("tags", {}).get("building")]
    nodes     = [el for el in bdata.get("elements", []) if el.get("type") == "node"]
    ways      = [el for el in wdata.get("elements", []) if el.get("type") == "way"]

    features = {
        "buildings": {"type": "FeatureCollection", "features": []},
        "paths":     {"type": "FeatureCollection", "features": []},
        "entrances": {"type": "FeatureCollection", "features": []},
    }

    for b in buildings:
        try:
            features["buildings"]["features"].append(_elements_to_building_feature(b))
        except Exception:
            continue

    for w in ways:
        try:
            features["paths"]["features"].append(_way_to_line_feature(w))
        except Exception:
            continue

    for n in nodes:
        try:
            features["entrances"]["features"].append(_node_to_point_feature(n))
        except Exception:
            continue

    out = {"generated_at": __import__("datetime").datetime.utcnow().isoformat(), "bbox": b, "features": features}

    with open(CACHE_FILE, "w") as f:
        json.dump(out, f)

    return out


@router.get("/campus/search")
def campus_search(q: str):
    query = (q or "").strip()
    if not query:
        return {"results": []}

    data      = campus_geojson()
    buildings = data.get("features", {}).get("buildings", {}).get("features", [])
    q_norm    = re.sub(r"[^a-z0-9]+", " ", query.lower()).strip()
    q_tokens  = [t for t in q_norm.split(" ") if t]
    seen      = set()
    results   = []

    # Exact query overrides always win
    exact = EXACT_QUERY_OVERRIDES.get(q_norm)
    if exact:
        results.append({
            "name":   exact["name"],
            "lat":    exact["lat"],
            "lon":    exact["lon"],
            "osm_id": None,
            "type":   exact["type"],
            "score":  5000,
        })
        seen.add((exact["name"].lower(), round(exact["lat"], 4), round(exact["lon"], 4)))

    for feat in buildings:
        props = feat.get("properties", {})
        name  = (props.get("name") or "").strip()
        if not name:
            continue
        name_l = name.lower()
        if ("garage" in name_l or "parking" in name_l) and "garage" not in q_norm and "parking" not in q_norm:
            continue

        geom   = feat.get("geometry", {})
        coords = ((geom.get("coordinates") or [[]])[0]) if geom.get("type") == "Polygon" else []
        if not coords:
            continue
        lon = sum(p[0] for p in coords) / len(coords)
        lat = sum(p[1] for p in coords) / len(coords)
        if abs(lat - CAMPUS_LAT) > 0.02 or abs(lon - CAMPUS_LON) > 0.025:
            continue

        name_norm = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()

        # Apply canonical coords correction
        if name_norm in CANONICAL_BUILDING_COORDS:
            lat, lon = CANONICAL_BUILDING_COORDS[name_norm]

        score = 0
        if name_norm == q_norm:           score = 1000
        elif name_norm.startswith(q_norm): score = 900
        elif q_norm in name_norm:          score = 700
        elif q_tokens and all(tok in name_norm for tok in q_tokens): score = 600
        elif q_tokens and any(tok in name_norm for tok in q_tokens): score = 450
        if score < 600 and len(q_norm) >= 4 and q_norm not in name_norm:
            continue
        if name_norm in CANONICAL_BUILDING_COORDS:
            score += 250

        if score > 0:
            if q_tokens:
                name_tokens = set(t for t in name_norm.split(" ") if t)
                overlap = sum(1 for t in q_tokens if t in name_tokens)
                extras  = max(0, len(name_tokens - set(q_tokens)))
                score  += overlap * 40 - extras * 8
            key = (name.lower(), round(lat, 4), round(lon, 4))
            if key not in seen:
                seen.add(key)
                results.append({
                    "name":   name,
                    "lat":    lat,
                    "lon":    lon,
                    "osm_id": props.get("osm_id"),
                    "type":   "building",
                    "score":  score,
                })

    for lm in CURATED_LANDMARKS:
        name_norm = re.sub(r"[^a-z0-9]+", " ", lm["name"].lower()).strip()
        score = 0
        if name_norm == q_norm:                                          score = 1100
        elif name_norm.startswith(q_norm):                               score = 980
        elif q_norm in name_norm:                                        score = 820
        elif q_tokens and all(tok in name_norm for tok in q_tokens):     score = 760
        if score == 0:
            continue
        key = (lm["name"].lower(), round(lm["lat"], 4), round(lm["lon"], 4))
        if key in seen:
            continue
        results.append({
            "name":   lm["name"],
            "lat":    lm["lat"],
            "lon":    lm["lon"],
            "osm_id": None,
            "type":   lm["type"],
            "score":  score,
        })

    best_by_name = {}
    for r in results:
        key = r["name"].strip().lower()
        if key not in best_by_name or r["score"] > best_by_name[key]["score"]:
            best_by_name[key] = r

    ranked = sorted(best_by_name.values(), key=lambda r: (-r["score"], r["name"]))
    return {"results": [{k: v for k, v in r.items() if k != "score"} for r in ranked[:20]]}


@router.get("/platform/capabilities", response_model=PlatformCapabilitiesResponse)
def platform_capabilities():
    """
    Competition/demo metadata endpoint.
    This documents product capabilities without changing routing logic.
    """
    return PlatformCapabilitiesResponse(
        product_name="SnowPath UNL",
        one_liner="Winter-aware predictive campus routing with weather and condition-informed path scoring.",
        route_modes=ROUTE_MODE_DESCRIPTORS,
        predictive_components=PREDICTIVE_COMPONENTS,
        visible_metrics=VISIBLE_METRICS,
        demo_forecasting=FORECASTING_FEATURES,
        narrative_script=NARRATIVE_SCRIPT,
    )


@router.post("/reports")
def create_report(report: Dict[str, Any] = Body(...), db: Session = Depends(get_db)):
    lat         = report.get("lat")
    lon         = report.get("lon")
    report_type = report.get("report_type")
    if not lat or not lon or not report_type:
        raise HTTPException(status_code=400, detail="lat, lon and report_type required")
    r = UserReport(
        lat=float(lat), lon=float(lon),
        segment_key=report.get("segment_key"),
        rating=report.get("rating"),
        report_type=report_type,
        note=report.get("note"),
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return {"ok": True, "id": r.id}


@router.get("/reports")
def get_reports(bbox: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(UserReport)
    if bbox:
        s, w, n, e = map(float, bbox.split(","))
        q = (q.filter(UserReport.lat >= s).filter(UserReport.lat <= n)
              .filter(UserReport.lon >= w).filter(UserReport.lon <= e))
    rows = q.order_by(UserReport.created_at.desc()).limit(500).all()
    return {"reports": [
        {"id": r.id, "lat": r.lat, "lon": r.lon, "type": r.report_type,
         "rating": r.rating, "note": r.note, "created_at": r.created_at.isoformat()}
        for r in rows
    ]}


@router.post("/pass-through")
def toggle_pass_through(payload: Dict[str, Any] = Body(...), db: Session = Depends(get_db)):
    bid = payload.get("building_osm_id")
    if not bid:
        raise HTTPException(status_code=400, detail="building_osm_id required")
    rec = db.query(BuildingPassThrough).filter(BuildingPassThrough.building_osm_id == str(bid)).first()
    if not rec:
        rec = BuildingPassThrough(
            building_osm_id=str(bid),
            name=payload.get("name"),
            enabled=bool(payload.get("enabled", True)),
            notes=payload.get("notes"),
        )
        db.add(rec)
    else:
        rec.enabled = bool(payload.get("enabled", not rec.enabled))
        if payload.get("name"):
            rec.name = payload.get("name")
    db.commit()
    db.refresh(rec)
    return {"ok": True, "id": rec.id, "enabled": rec.enabled}
