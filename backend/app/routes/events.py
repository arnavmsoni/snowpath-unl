from fastapi import APIRouter
from datetime import datetime, timezone
from app.services.events import seed_events_near_unl

router = APIRouter()

@router.get("/events")
def events():
    now = datetime.now(timezone.utc)
    evts = seed_events_near_unl(now)
    for e in evts:
        e["start_time"] = e["start_time"].isoformat()
        e["end_time"] = e["end_time"].isoformat()
    return {"events": evts}