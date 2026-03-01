import json
import os
import time
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Tuple, Optional

from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.user_report import UserReport
from app.services.events import seed_events_near_unl, time_bump_intensity
from app.services.osm_graph import approx_meters
from app.services.weather import fetch_hourly_weather, compute_winter_penalty
from app.routes.route import compute_campus_route, synthetic_condition_reports
from app.config import CAMPUS_LAT, CAMPUS_LON


CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "cache", "campus_geojson.json")

# Canonical competition/demo points used for route-matrix benchmarking.
CANONICAL_POINTS: Dict[str, Tuple[float, float]] = {
    "14th and Avery": (40.8177, -96.6968),
    "Kauffman ARC": (40.8187, -96.7008),
    "Nebraska Union": (40.8202, -96.7009),
    "Love Library": (40.8197, -96.7019),
    "Student Rec Center": (40.8207, -96.7042),
    "Morrill Hall": (40.8204, -96.7030),
    "Memorial Stadium": (40.8231, -96.7054),
    "Selleck Quadrangle": (40.8222, -96.6988),
    "Abel Hall": (40.8240, -96.6985),
    "Cather Dining Hall": (40.8260, -96.6990),
    "Avery Hall": (40.8180, -96.7015),
}

CANONICAL_OD_PAIRS: List[Tuple[str, str]] = [
    ("Kauffman ARC", "Cather Dining Hall"),
    ("Kauffman ARC", "Memorial Stadium"),
    ("Kauffman ARC", "Nebraska Union"),
    ("Kauffman ARC", "Student Rec Center"),
    ("14th and Avery", "Cather Dining Hall"),
    ("14th and Avery", "Love Library"),
    ("Nebraska Union", "Memorial Stadium"),
    ("Love Library", "Selleck Quadrangle"),
    ("Avery Hall", "Cather Dining Hall"),
]


class SegmentTypeSummary(BaseModel):
    outdoor_meters: float
    sheltered_meters: float
    outdoor_ratio: float


class ModeRouteStat(BaseModel):
    mode: str
    total_meters: float
    cold_exposure_minutes: float
    snow_risk_score: float
    segment_summary: SegmentTypeSummary
    step_count: int


class PairRouteComparison(BaseModel):
    start_name: str
    end_name: str
    shortest: ModeRouteStat
    sheltered: ModeRouteStat
    cleared: ModeRouteStat
    divergence_score: float


class RouteMatrixSummary(BaseModel):
    pairs_evaluated: int
    avg_shortest_meters: float
    avg_sheltered_meters: float
    avg_cleared_meters: float
    avg_mode_divergence_score: float
    sheltered_with_indoor_pairs: int


class GeojsonCoverageStats(BaseModel):
    buildings_count: int
    named_buildings_count: int
    paths_count: int
    entrances_count: int
    total_path_km: float
    cache_present: bool


class PredictiveSignalPoint(BaseModel):
    hour_index: int
    temperature_c: float
    snowfall_mm: float
    wind_kph: float
    outdoor_penalty: float


class PredictiveSignalSeries(BaseModel):
    source: str
    generated_at: str
    points: List[PredictiveSignalPoint]
    avg_penalty: float
    peak_penalty: float


class ReportTypeStat(BaseModel):
    report_type: str
    count: int
    avg_rating: float


class ReportAnalytics(BaseModel):
    total_reports: int
    type_breakdown: List[ReportTypeStat]
    synthetic_reports_loaded: int


class ScrapeSourceStatus(BaseModel):
    source: str
    status: str
    records_collected: int
    latency_ms: float
    notes: str


class ScrapeDiagnostics(BaseModel):
    generated_at: str
    sources: List[ScrapeSourceStatus]


class CompetitionSnapshot(BaseModel):
    generated_at: str
    campus_geojson_coverage: GeojsonCoverageStats
    predictive_weather_series: PredictiveSignalSeries
    report_analytics: ReportAnalytics
    route_matrix_summary: RouteMatrixSummary
    route_matrix: List[PairRouteComparison]
    scrape_diagnostics: ScrapeDiagnostics


def _safe_float(v: Optional[float], default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _segment_summary(route: dict) -> SegmentTypeSummary:
    total = max(1.0, _safe_float(route.get("total_meters"), 0.0))
    outdoor = _safe_float(route.get("outdoor_meters"), 0.0)
    sheltered = _safe_float(route.get("sheltered_meters"), 0.0)
    return SegmentTypeSummary(
        outdoor_meters=outdoor,
        sheltered_meters=sheltered,
        outdoor_ratio=outdoor / total,
    )


def _mode_stat(mode: str, route: dict) -> ModeRouteStat:
    return ModeRouteStat(
        mode=mode,
        total_meters=_safe_float(route.get("total_meters"), 0.0),
        cold_exposure_minutes=_safe_float(route.get("cold_exposure_minutes"), 0.0),
        snow_risk_score=_safe_float(route.get("snow_risk_score"), 0.0),
        segment_summary=_segment_summary(route),
        step_count=len(route.get("steps", []) or []),
    )


def _pair_divergence(shortest: dict, sheltered: dict, cleared: dict) -> float:
    a = _safe_float(shortest.get("total_meters"), 0.0)
    b = _safe_float(sheltered.get("total_meters"), 0.0)
    c = _safe_float(cleared.get("total_meters"), 0.0)
    s_in = _safe_float(sheltered.get("sheltered_meters"), 0.0)
    c_in = _safe_float(cleared.get("sheltered_meters"), 0.0)
    # Distance spread + indoor-behavior spread
    return abs(a - b) + abs(a - c) + abs(b - c) + abs(s_in - c_in) * 0.6


def build_route_matrix(outdoor_penalty: float = 1.55) -> List[PairRouteComparison]:
    reports = synthetic_condition_reports()
    out: List[PairRouteComparison] = []
    for start_name, end_name in CANONICAL_OD_PAIRS:
        s = CANONICAL_POINTS[start_name]
        e = CANONICAL_POINTS[end_name]
        shortest = compute_campus_route(s[0], s[1], e[0], e[1], mode="shortest", outdoor_penalty=outdoor_penalty, reports=reports)
        sheltered = compute_campus_route(s[0], s[1], e[0], e[1], mode="sheltered", outdoor_penalty=outdoor_penalty, reports=reports)
        cleared = compute_campus_route(s[0], s[1], e[0], e[1], mode="cleared", outdoor_penalty=outdoor_penalty, reports=reports)
        out.append(PairRouteComparison(
            start_name=start_name,
            end_name=end_name,
            shortest=_mode_stat("shortest", shortest),
            sheltered=_mode_stat("sheltered", sheltered),
            cleared=_mode_stat("cleared", cleared),
            divergence_score=_pair_divergence(shortest, sheltered, cleared),
        ))
    return out


def summarize_route_matrix(rows: List[PairRouteComparison]) -> RouteMatrixSummary:
    if not rows:
        return RouteMatrixSummary(
            pairs_evaluated=0,
            avg_shortest_meters=0.0,
            avg_sheltered_meters=0.0,
            avg_cleared_meters=0.0,
            avg_mode_divergence_score=0.0,
            sheltered_with_indoor_pairs=0,
        )
    return RouteMatrixSummary(
        pairs_evaluated=len(rows),
        avg_shortest_meters=mean(r.shortest.total_meters for r in rows),
        avg_sheltered_meters=mean(r.sheltered.total_meters for r in rows),
        avg_cleared_meters=mean(r.cleared.total_meters for r in rows),
        avg_mode_divergence_score=mean(r.divergence_score for r in rows),
        sheltered_with_indoor_pairs=sum(1 for r in rows if r.sheltered.segment_summary.sheltered_meters > 1.0),
    )


def _line_km(coords: list) -> float:
    if not coords or len(coords) < 2:
        return 0.0
    meters = 0.0
    for i in range(len(coords) - 1):
        a = coords[i]
        b = coords[i + 1]
        meters += approx_meters((a[1], a[0]), (b[1], b[0]))
    return meters / 1000.0


def geojson_coverage_stats() -> GeojsonCoverageStats:
    if not os.path.exists(CACHE_FILE):
        return GeojsonCoverageStats(
            buildings_count=0,
            named_buildings_count=0,
            paths_count=0,
            entrances_count=0,
            total_path_km=0.0,
            cache_present=False,
        )

    try:
        with open(CACHE_FILE, "r") as f:
            data = json.load(f)
    except Exception:
        return GeojsonCoverageStats(
            buildings_count=0,
            named_buildings_count=0,
            paths_count=0,
            entrances_count=0,
            total_path_km=0.0,
            cache_present=True,
        )

    feats = data.get("features", {})
    buildings = feats.get("buildings", {}).get("features", []) or []
    paths = feats.get("paths", {}).get("features", []) or []
    entrances = feats.get("entrances", {}).get("features", []) or []
    named = 0
    total_km = 0.0
    for b in buildings:
        n = (b.get("properties", {}) or {}).get("name")
        if n and str(n).strip():
            named += 1
    for p in paths:
        coords = (p.get("geometry", {}) or {}).get("coordinates", []) or []
        total_km += _line_km(coords)

    return GeojsonCoverageStats(
        buildings_count=len(buildings),
        named_buildings_count=named,
        paths_count=len(paths),
        entrances_count=len(entrances),
        total_path_km=round(total_km, 3),
        cache_present=True,
    )


def predictive_weather_series() -> PredictiveSignalSeries:
    now = datetime.now(timezone.utc)
    points: List[PredictiveSignalPoint] = []
    source = "open-meteo"
    try:
        wx = fetch_hourly_weather(CAMPUS_LAT, CAMPUS_LON)
        hourly = wx.get("hourly", {})
        temps = hourly.get("temperature_2m", [])[:24]
        snows = hourly.get("snowfall", [])[:24]
        winds = hourly.get("wind_speed_10m", [])[:24]
        precs = hourly.get("precipitation", [])[:24]
        n = min(len(temps), len(snows), len(winds), len(precs), 24)
        for i in range(n):
            h = {
                "temperature_2m": _safe_float(temps[i]),
                "snowfall": _safe_float(snows[i]),
                "wind_speed_10m": _safe_float(winds[i]),
                "precipitation": _safe_float(precs[i]),
            }
            points.append(PredictiveSignalPoint(
                hour_index=i,
                temperature_c=h["temperature_2m"],
                snowfall_mm=h["snowfall"],
                wind_kph=h["wind_speed_10m"],
                outdoor_penalty=compute_winter_penalty(h),
            ))
    except Exception:
        source = "synthetic-fallback"
        for i in range(24):
            temp = -8.0 + (i % 12) * 0.9
            snow = 0.3 if i in (6, 7, 8, 17, 18) else 0.0
            wind = 8.0 + (i % 7) * 1.5
            h = {"temperature_2m": temp, "snowfall": snow, "wind_speed_10m": wind, "precipitation": 0.2 if snow > 0 else 0.0}
            points.append(PredictiveSignalPoint(
                hour_index=i,
                temperature_c=temp,
                snowfall_mm=snow,
                wind_kph=wind,
                outdoor_penalty=compute_winter_penalty(h),
            ))

    penalties = [p.outdoor_penalty for p in points] or [1.0]
    return PredictiveSignalSeries(
        source=source,
        generated_at=now.isoformat(),
        points=points,
        avg_penalty=round(mean(penalties), 3),
        peak_penalty=round(max(penalties), 3),
    )


def report_analytics(db: Session) -> ReportAnalytics:
    rows = (
        db.query(
            UserReport.report_type,
            func.count(UserReport.id),
            func.avg(UserReport.rating),
        )
        .group_by(UserReport.report_type)
        .all()
    )
    breakdown: List[ReportTypeStat] = []
    total = 0
    for report_type, count, avg_rating in rows:
        c = int(count or 0)
        total += c
        breakdown.append(ReportTypeStat(
            report_type=str(report_type),
            count=c,
            avg_rating=round(_safe_float(avg_rating, 0.0), 2),
        ))
    return ReportAnalytics(
        total_reports=total,
        type_breakdown=sorted(breakdown, key=lambda r: (-r.count, r.report_type)),
        synthetic_reports_loaded=len(synthetic_condition_reports()),
    )


def scrape_diagnostics(db: Session) -> ScrapeDiagnostics:
    now = datetime.now(timezone.utc).isoformat()
    out: List[ScrapeSourceStatus] = []

    t0 = time.perf_counter()
    cache_present = os.path.exists(CACHE_FILE)
    size_bytes = os.path.getsize(CACHE_FILE) if cache_present else 0
    out.append(ScrapeSourceStatus(
        source="osm-overpass-cache",
        status="ok" if cache_present else "missing",
        records_collected=size_bytes,
        latency_ms=round((time.perf_counter() - t0) * 1000.0, 2),
        notes="Reads cached campus geojson generated from Overpass queries.",
    ))

    t1 = time.perf_counter()
    try:
        wx = fetch_hourly_weather(CAMPUS_LAT, CAMPUS_LON)
        recs = len((wx.get("hourly", {}) or {}).get("time", []))
        status = "ok"
        notes = "Fetched hourly weather forecast from Open-Meteo."
    except Exception:
        recs = 0
        status = "degraded"
        notes = "Weather API unavailable; analytics can use synthetic fallback."
    out.append(ScrapeSourceStatus(
        source="weather-forecast-api",
        status=status,
        records_collected=recs,
        latency_ms=round((time.perf_counter() - t1) * 1000.0, 2),
        notes=notes,
    ))

    t2 = time.perf_counter()
    ev = seed_events_near_unl(datetime.now(timezone.utc))
    out.append(ScrapeSourceStatus(
        source="event-pattern-generator",
        status="ok",
        records_collected=len(ev),
        latency_ms=round((time.perf_counter() - t2) * 1000.0, 2),
        notes=f"Seeded event windows with time bump baseline {time_bump_intensity(datetime.now(timezone.utc)):.2f}.",
    ))

    t3 = time.perf_counter()
    reports_count = db.query(func.count(UserReport.id)).scalar() or 0
    out.append(ScrapeSourceStatus(
        source="user-report-store",
        status="ok",
        records_collected=int(reports_count),
        latency_ms=round((time.perf_counter() - t3) * 1000.0, 2),
        notes="Reads path-condition reports persisted in database.",
    ))

    return ScrapeDiagnostics(generated_at=now, sources=out)


def build_competition_snapshot(db: Session) -> CompetitionSnapshot:
    rows = build_route_matrix()
    return CompetitionSnapshot(
        generated_at=datetime.now(timezone.utc).isoformat(),
        campus_geojson_coverage=geojson_coverage_stats(),
        predictive_weather_series=predictive_weather_series(),
        report_analytics=report_analytics(db),
        route_matrix_summary=summarize_route_matrix(rows),
        route_matrix=rows,
        scrape_diagnostics=scrape_diagnostics(db),
    )
