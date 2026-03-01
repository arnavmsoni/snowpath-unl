import os
import json
from fastapi import APIRouter, HTTPException, Depends, Body
from typing import Optional, Dict, Any
from pydantic import BaseModel
from app.services.osm_graph import fetch_buildings_and_entrances_overpass, fetch_walkways_overpass
from app.db.session import get_db
from sqlalchemy.orm import Session
from app.models.user_report import UserReport
from app.models.building_pass_through import BuildingPassThrough

router = APIRouter()

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_FILE = os.path.join(CACHE_DIR, "campus_geojson.json")


def _elements_to_building_feature(el):
    props = {
        "osm_id": el.get("id"),
        "name": el.get("tags", {}).get("name"),
        "type": el.get("type"),
    }
    # geometry: try to use 'geometry' as list of {lat,lon}
    geom = el.get("geometry") or []
    coords = [[p["lon"], p["lat"]] for p in geom]
    # ensure polygon closed
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])
    return {"type": "Feature", "properties": props, "geometry": {"type": "Polygon", "coordinates": [coords]}}


def _way_to_line_feature(el):
    props = {"osm_id": el.get("id"), "tags": el.get("tags", {})}
    geom = el.get("geometry") or []
    coords = [[p["lon"], p["lat"]] for p in geom]
    return {"type": "Feature", "properties": props, "geometry": {"type": "LineString", "coordinates": coords}}


def _node_to_point_feature(el):
    props = {"osm_id": el.get("id"), "tags": el.get("tags", {})}
    lat = el.get("lat")
    lon = el.get("lon")
    return {"type": "Feature", "properties": props, "geometry": {"type": "Point", "coordinates": [lon, lat]}}


@router.get("/campus/geojson")
def campus_geojson(bbox: Optional[str] = None):
    # If cached, return cache. Otherwise fetch Overpass and cache file.
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)

    # use bbox from env or parameter
    from app.config import BBOX
    b = bbox or BBOX

    # fetch buildings + entrances + walkways
    try:
        bdata = fetch_buildings_and_entrances_overpass(b)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Overpass buildings request failed: {e}")

    try:
        wdata = fetch_walkways_overpass(b)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Overpass ways request failed: {e}")

    buildings = [el for el in bdata.get("elements", []) if el.get("type") in ("way", "relation") and el.get("tags", {}).get("building")]
    nodes = [el for el in bdata.get("elements", []) if el.get("type") == "node"]
    ways = [el for el in wdata.get("elements", []) if el.get("type") == "way"]

    features = {
        "buildings": {"type": "FeatureCollection", "features": []},
        "paths": {"type": "FeatureCollection", "features": []},
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
    # Simple Overpass name search limited to 30 results
    from app.config import BBOX
    s, w, n, e = BBOX.split(",")
    query = f"""
    [out:json][timeout:15];
    (
      node["name"~"{q}"]({s},{w},{n},{e});
      way["name"~"{q}"]({s},{w},{n},{e});
      relation["name"~"{q}"]({s},{w},{n},{e});
    );
    out center qt 30;
    """
    import requests
    r = requests.post("https://overpass-api.de/api/interpreter", data=query, timeout=20)
    r.raise_for_status()
    data = r.json()
    results = []
    for el in data.get("elements", [])[:30]:
        props = el.get("tags", {})
        name = props.get("name")
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        if name and lat and lon:
            results.append({"name": name, "lat": lat, "lon": lon, "osm_id": el.get("id"), "type": el.get("type")})
    return {"results": results}


@router.post("/reports")
def create_report(report: Dict[str, Any] = Body(...), db: Session = Depends(get_db)):
    # minimal validation
    lat = report.get("lat")
    lon = report.get("lon")
    report_type = report.get("report_type")
    if not lat or not lon or not report_type:
        raise HTTPException(status_code=400, detail="lat, lon and report_type required")
    r = UserReport(
        lat=float(lat), lon=float(lon), segment_key=report.get("segment_key"), rating=report.get("rating"), report_type=report_type, note=report.get("note")
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return {"ok": True, "id": r.id}


@router.get("/reports")
def get_reports(bbox: Optional[str] = None, db: Session = Depends(get_db)):
    # bbox: s,w,n,e
    q = db.query(UserReport)
    if bbox:
        s, w, n, e = map(float, bbox.split(","))
        q = q.filter(UserReport.lat >= float(s)).filter(UserReport.lat <= float(n)).filter(UserReport.lon >= float(w)).filter(UserReport.lon <= float(e))
    rows = q.order_by(UserReport.created_at.desc()).limit(500).all()
    out = []
    for r in rows:
        out.append({"id": r.id, "lat": r.lat, "lon": r.lon, "type": r.report_type, "rating": r.rating, "note": r.note, "created_at": r.created_at.isoformat()})
    return {"reports": out}


@router.post("/pass-through")
def toggle_pass_through(payload: Dict[str, Any] = Body(...), db: Session = Depends(get_db)):
    # payload: {building_osm_id, name, enabled}
    bid = payload.get("building_osm_id")
    if not bid:
        raise HTTPException(status_code=400, detail="building_osm_id required")
    rec = db.query(BuildingPassThrough).filter(BuildingPassThrough.building_osm_id == str(bid)).first()
    if not rec:
        rec = BuildingPassThrough(building_osm_id=str(bid), name=payload.get("name"), enabled=bool(payload.get("enabled", True)), notes=payload.get("notes"))
        db.add(rec)
    else:
        rec.enabled = bool(payload.get("enabled", not rec.enabled))
        if payload.get("name"):
            rec.name = payload.get("name")
    db.commit()
    db.refresh(rec)
    return {"ok": True, "id": rec.id, "enabled": rec.enabled}
