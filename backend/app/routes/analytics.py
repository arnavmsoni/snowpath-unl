from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.competition_analytics import (
    CompetitionSnapshot,
    PairRouteComparison,
    RouteMatrixSummary,
    ScrapeDiagnostics,
    build_competition_snapshot,
    build_route_matrix,
    summarize_route_matrix,
    scrape_diagnostics,
)

router = APIRouter()


@router.get("/platform/analytics/snapshot", response_model=CompetitionSnapshot)
def platform_analytics_snapshot(db: Session = Depends(get_db)):
    """
    Large competition-facing analytics payload.
    Does not alter routing logic; it measures and summarizes current behavior.
    """
    return build_competition_snapshot(db)


@router.get("/platform/analytics/route-matrix")
def platform_route_matrix():
    rows = build_route_matrix()
    summary: RouteMatrixSummary = summarize_route_matrix(rows)
    return {
        "summary": summary,
        "rows": rows,
    }


@router.get("/platform/scrape/status", response_model=ScrapeDiagnostics)
def platform_scrape_status(db: Session = Depends(get_db)):
    """
    Demo scraper/source diagnostics endpoint for competition storytelling.
    """
    return scrape_diagnostics(db)
