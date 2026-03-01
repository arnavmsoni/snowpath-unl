"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

const PRESETS = {
  union: { name: "Student Union", lat: 40.8202, lon: -96.7009 },
  love: { name: "Love Library", lat: 40.8197, lon: -96.7020 },
  hawks: { name: "Hawks Hall", lat: 40.8194, lon: -96.7026 },
  kauff: { name: "Kauffman Center", lat: 40.8187, lon: -96.7008 },
};

type Point = { lat: number; lon: number; intensity: number };

export default function Home() {
  const mapRef = useRef<maplibregl.Map | null>(null);
  const mapDivRef = useRef<HTMLDivElement | null>(null);

  const [start, setStart] = useState(PRESETS.union);
  const [end, setEnd] = useState(PRESETS.love);
  const [meta, setMeta] = useState<any>(null);
  const [savedRows, setSavedRows] = useState<number>(0);

  const center = useMemo(() => [start.lon, start.lat] as [number, number], [start]);

  useEffect(() => {
    if (!mapDivRef.current) return;

    const map = new maplibregl.Map({
      container: mapDivRef.current,
      style: "https://demotiles.maplibre.org/style.json",
      center,
      zoom: 15,
    });

    map.addControl(new maplibregl.NavigationControl(), "top-right");
    mapRef.current = map;

    map.on("load", () => {
      map.addSource("traffic", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });

      map.addLayer({
        id: "traffic-circles",
        type: "circle",
        source: "traffic",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["get", "intensity"], 0, 2, 1, 14],
          "circle-opacity": 0.35,
        },
      });

      map.addSource("route", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });

      map.addLayer({
        id: "route-line",
        type: "line",
        source: "route",
        paint: { "line-width": 5 },
      });
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    map.easeTo({ center: [start.lon, start.lat], zoom: 15 });
  }, [start]);

  async function refreshTraffic() {
    const r = await fetch(`${API_BASE}/traffic?store=true`);
    const data = await r.json();
    const pts: Point[] = data.points;
    setSavedRows(data.saved_rows ?? 0);

    const features = pts.map((p) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [p.lon, p.lat] },
      properties: { intensity: p.intensity },
    }));

    const map = mapRef.current;
    if (map?.getSource("traffic")) {
      (map.getSource("traffic") as any).setData({ type: "FeatureCollection", features });
    }
  }

  async function getRoute() {
    const url =
      `${API_BASE}/route?start_lat=${start.lat}&start_lon=${start.lon}` +
      `&end_lat=${end.lat}&end_lon=${end.lon}`;

    const r = await fetch(url);
    const data = await r.json();
    setMeta(data);

    const coords = data.route.coords.map((c: any) => [c.lon, c.lat]);

    const geo = {
      type: "FeatureCollection",
      features: [{ type: "Feature", geometry: { type: "LineString", coordinates: coords }, properties: {} }],
    };

    const map = mapRef.current;
    if (map?.getSource("route")) {
      (map.getSource("route") as any).setData(geo);
    }
  }

  useEffect(() => {
    refreshTraffic();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const total = meta?.route?.total_meters ?? null;
  const outdoor = meta?.route?.outdoor_meters ?? null;
  const penalty = meta?.outdoor_penalty ?? null;

  return (
    <div style={{ padding: 16, maxWidth: 1100, margin: "0 auto" }}>
      <h1 style={{ fontSize: 28, fontWeight: 800 }}>SnowPath UNL</h1>
      <p style={{ marginTop: 6, opacity: 0.85 }}>
        Winter-aware routing + realistic “likely foot-traffic zones” (events + time model).
      </p>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 12 }}>
        <Selector label="Start" value={start.name} onChange={(key) => setStart((PRESETS as any)[key])} />
        <Selector label="End" value={end.name} onChange={(key) => setEnd((PRESETS as any)[key])} />

        <button onClick={refreshTraffic} style={btnStyle}>
          Refresh Foot-Traffic Layer
        </button>

        <button onClick={getRoute} style={btnStyle}>
          Get Winter Route
        </button>
      </div>

      <div style={{ marginTop: 12 }} className="map" ref={mapDivRef} />

      <div style={{ marginTop: 12, padding: 12, border: "1px solid #ddd", borderRadius: 12 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700 }}>Route Insights</h2>
        <div style={{ opacity: 0.8, marginBottom: 8 }}>
          DB proof: last traffic refresh saved <b>{savedRows}</b> rows into Supabase.
        </div>

        {!meta ? (
          <p style={{ opacity: 0.8 }}>Click “Get Winter Route”.</p>
        ) : (
          <div style={{ display: "grid", gap: 6 }}>
            <div><b>Outdoor penalty:</b> {penalty?.toFixed?.(2)}</div>
            <div><b>Total distance:</b> {total ? (total / 1000).toFixed(2) + " km" : "-"}</div>
            <div><b>Outdoor distance:</b> {outdoor ? (outdoor / 1000).toFixed(2) + " km" : "-"}</div>
            <div>
              <b>Weather hour:</b>{" "}
              {meta.weather_hour.time} • {meta.weather_hour.temperature_2m}°C • snowfall {meta.weather_hour.snowfall} • wind {meta.weather_hour.wind_speed_10m}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Selector({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (key: string) => void;
}) {
  return (
    <label style={{ display: "grid", gap: 4 }}>
      <span style={{ fontSize: 12, opacity: 0.7 }}>{label}</span>
      <select
        defaultValue={Object.entries(PRESETS).find(([, v]) => v.name === value)?.[0]}
        onChange={(e) => onChange(e.target.value)}
        style={{ padding: "10px 12px", borderRadius: 10, border: "1px solid #ccc" }}
      >
        {Object.entries(PRESETS).map(([k, v]) => (
          <option key={k} value={k}>
            {v.name}
          </option>
        ))}
      </select>
    </label>
  );
}

const btnStyle: React.CSSProperties = {
  padding: "10px 12px",
  borderRadius: 10,
  border: "1px solid #ccc",
  fontWeight: 700,
  cursor: "pointer",
};
