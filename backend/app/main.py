from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.db.session import engine
from app.models.base import Base

from app.routes.health import router as health_router
from app.routes.route import router as route_router
from app.routes.events import router as events_router
from app.routes.traffic import router as traffic_router
from app.routes.campus import router as campus_router

app = FastAPI(title="SnowPath UNL API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    # Create tables in Supabase (events, traffic_snapshots)
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

app.include_router(health_router)
app.include_router(route_router)
app.include_router(events_router)
app.include_router(traffic_router)
app.include_router(campus_router)
