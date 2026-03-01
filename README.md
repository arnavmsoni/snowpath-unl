# SnowPath UNL

Winter-aware campus routing + realistic “likely foot-traffic zones” (events + time-of-day model).

- Backend: FastAPI (Python)
- Frontend: Next.js + MapLibre
- DB: Supabase Postgres

## Quickstart (dev)

1. Backend

	- Create a Python virtualenv and install deps (use the backend/.venv if provided).

	```bash
	cd backend
	python -m venv .venv
	source .venv/bin/activate
	pip install -r requirements.txt
	cp .env.example .env
	# edit .env to set DATABASE_URL
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
	```

2. Frontend

	```bash
	cd frontend
	cp .env.example .env.local
	npm install
	npm run dev
	# open http://localhost:3000
	```

3. Notes

	- Backend exposes `/campus/geojson`, `/campus/search`, `/reports`, `/pass-through`, and extended `/route` endpoints.
	- The backend caches Overpass results to `backend/cache/campus_geojson.json`.
