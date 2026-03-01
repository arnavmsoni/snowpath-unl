# SnowPath UNL

SnowPath UNL is a winter-aware campus navigation app for the University of Nebraska-Lincoln (City Campus).
It computes routes using weather, reported path conditions, and indoor connector availability to reduce winter exposure.

## Predictive Analytics (Top-Line)

SnowPath UNL includes a predictive risk layer for winter walking:

- Predicts near-term walking risk from live weather signals (`snowfall`, wind, freezing temperatures).
- Blends weather risk with reported path conditions (`blocked`, `icy`, `salted`, `cleared`).
- Produces mode-specific route scoring for `shortest`, `sheltered`, and `cleared`.
- Surfaces judge-friendly metrics: distance, outdoor exposure, sheltered distance, and snow-risk score.
- Provides competition analytics endpoints for snapshot evaluation and diagnostics:
  - `GET /platform/analytics/snapshot`
  - `GET /platform/analytics/route-matrix`
  - `GET /platform/scrape/status`

This repository includes:
- `frontend/`: Next.js + MapLibre UI
- `backend/`: FastAPI API, routing engine, and condition modeling

## Core Features

- Multi-mode routing:
  - `shortest`: distance-first
  - `sheltered`: prefers indoor connectors and lower exposure
  - `cleared`: favors cleared/salted outdoor corridors and avoids risky segments
- Weather-aware penalties using live Open-Meteo hourly data.
- User reports API for `icy`, `blocked`, `salted`, `cleared` conditions.
- Campus search + map geometry endpoints.
- Synthetic events + traffic intensity generation for demo and evaluation.

## Prediction Behavior (for judging)

This project includes rule-based predictive modeling (not a deep learning model):

- **Cold-exposure prediction**:
  - The backend predicts an `outdoor_penalty` from live weather (`snowfall`, freezing precip risk, wind).
  - That penalty directly affects route scoring and `snow_risk_score`.

- **Likely foot-traffic prediction**:
  - `/events` generates near-future campus activity windows.
  - `/traffic` generates synthetic hotspot points based on time-of-day and event proximity.
  - This simulates likely crowded zones for evaluation/demo scenarios.

## Tech Stack

- Frontend: Next.js 16, React, MapLibre GL
- Backend: FastAPI, NetworkX, SQLAlchemy
- Data: OpenStreetMap geometry, Open-Meteo weather
- Database: PostgreSQL-compatible `DATABASE_URL` (e.g., Supabase Postgres)

## Project Structure

```text
snowpath-unl/
  backend/
    app/
      routes/
      services/
      models/
      db/
    requirements.txt
    .env.example
  frontend/
    app/
    package.json
    .env.example
```

## Prerequisites

- Python 3.11+ (3.13 tested)
- Node.js 18+ and npm
- A PostgreSQL connection string (local Postgres or Supabase)

## 5-Minute Local Setup

## 1) Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `backend/.env`:

```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/snowpath
CAMPUS_LAT=40.8200
CAMPUS_LON=-96.7000
BBOX=40.812,-96.713,40.827,-96.690
```

Run backend:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Expected:

```json
{"ok": true}
```

## 2) Frontend

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev -- -H 127.0.0.1 -p 3000
```

Open:
- `http://127.0.0.1:3000`

## API Endpoints

- `GET /health`
- `GET /campus/geojson`
- `GET /campus/search?q=...`
- `GET /route?start_lat=...&start_lon=...&end_lat=...&end_lon=...`
- `GET /route/advanced?...&mode=shortest|sheltered|cleared`
- `POST /reports`
- `GET /reports`
- `POST /pass-through`
- `GET /events`
- `GET /traffic?store=true|false`
- `GET /platform/analytics/snapshot`
- `GET /platform/analytics/route-matrix`
- `GET /platform/scrape/status`

## Judge Evaluation Script (quick manual)

Run from repo root while backend is running:

```bash
for mode in shortest sheltered cleared; do
  echo "=== $mode ==="
  curl -s "http://127.0.0.1:8000/route/advanced?start_lat=40.8177&start_lon=-96.6968&end_lat=40.8260&end_lon=-96.6990&mode=$mode" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); r=d["route"]; print("total_m:", round(r["total_meters"],1), "outdoor_m:", round(r["outdoor_meters"],1), "sheltered_m:", round(r["sheltered_meters"],1), "risk:", round(r["snow_risk_score"],3))'
done
```

What to look for:
- Different totals and `outdoor_meters` by mode.
- Sheltered route should include non-zero `sheltered_meters`.
- Cleared route should avoid high-risk segments and stay outdoor-oriented.

## Recommended Demo Scenario

- Start: `14th and Avery`
- Destination: `Cather Dining Hall`
- Compare all three modes:
  - `shortest`: baseline direct path
  - `sheltered`: should include indoor connectors where available
  - `cleared`: should follow a distinct outdoor detour when hazards exist

## Database Notes

- On backend startup, SQLAlchemy creates required tables from models.
- `GET /traffic?store=true` persists sample synthetic traffic rows.
- `POST /reports` records user condition reports for routing influence.

## Known Constraints

- Routing is heuristic/rule-based and graph-constrained (not turn-by-turn automotive navigation).
- Traffic endpoint is synthetic for evaluation and demo repeatability.
- Route behavior depends on available campus graph connectivity.

## Troubleshooting

- Backend not reachable:
  - Confirm `uvicorn` is running on `127.0.0.1:8000`.
- Frontend fetch errors:
  - Ensure `NEXT_PUBLIC_API_BASE=http://localhost:8000` in `frontend/.env.local`.
- DB errors:
  - Verify `DATABASE_URL` credentials and network access.
- Stale UI state:
  - Hard refresh browser (`Cmd+Shift+R` on macOS).

## Submission Notes

This README is intentionally judge-focused:
- exact run commands
- explicit validation checkpoints
- concrete demo scenario
- explanation of predictive behavior and evaluation criteria
