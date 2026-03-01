"use client";

import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

// ─── Complete UNL Campus Building Database ─────────────────────────────────
// Sorted A→Z. Every major building on City Campus with accurate coords.
// ─────────────────────────────────────────────────────────────────────────────
//  DROP-IN REPLACEMENTS for page.tsx
//  Replace the existing UNL_BUILDINGS array and SPECIAL_SEARCH_POINTS with these.
//  Key fixes:
//    • Willa Cather Dining is at the NORTH end of campus (40.8260), not the middle
//    • 14th & Avery is at 40.8177 / -96.6968, not 40.8201
//    • Abel, Cather Hall, Pound, Gaylord, Thunderbird all shifted north accordingly
// ─────────────────────────────────────────────────────────────────────────────

export const SPECIAL_SEARCH_POINTS = [
  // Intersections
  { name: "14th and Avery",      lat: 40.8177, lon: -96.6968, type: "Intersection",   icon: "📍" },
  { name: "14th & Avery",        lat: 40.8177, lon: -96.6968, type: "Intersection",   icon: "📍" },
  { name: "14th & Avery Garage", lat: 40.8180, lon: -96.6965, type: "Parking",        icon: "🅿️" },

  // Dining
  { name: "Cather Dining Hall",  lat: 40.8260, lon: -96.6990, type: "Dining",         icon: "🍽️" },
  { name: "Cather Dining",       lat: 40.8260, lon: -96.6990, type: "Dining",         icon: "🍽️" },
  { name: "Willa Cather Dining", lat: 40.8260, lon: -96.6990, type: "Dining",         icon: "🍽️" },
  { name: "Harper Dining Center",lat: 40.8260, lon: -96.6990, type: "Dining",         icon: "🍽️" },

  // Residence Halls (north campus cluster)
  { name: "Cather Hall",         lat: 40.8248, lon: -96.6992, type: "Residence Hall", icon: "🏠" },
  { name: "Abel Hall",           lat: 40.8240, lon: -96.6985, type: "Residence Hall", icon: "🏠" },
  { name: "Pound Hall",          lat: 40.8256, lon: -96.6990, type: "Residence Hall", icon: "🏠" },
  { name: "Selleck Quadrangle",  lat: 40.8225, lon: -96.6988, type: "Residence Hall", icon: "🏠" },
  { name: "Selleck",             lat: 40.8225, lon: -96.6988, type: "Residence Hall", icon: "🏠" },

  // Academic
  { name: "Hawks Hall",          lat: 40.8190, lon: -96.6985, type: "Academic",       icon: "💼" },
  { name: "Avery Hall",          lat: 40.8180, lon: -96.7015, type: "Academic",       icon: "🎓" },
];

// Full building list — sorted A→Z, corrected coordinates
export const UNL_BUILDINGS = [
  { name: "Abel Hall",                    lat: 40.8240, lon: -96.6985, type: "Residence Hall",   icon: "🏠" },
  { name: "Andersen Hall",                lat: 40.8194, lon: -96.7007, type: "Academic",          icon: "🎓" },
  { name: "Archy Hall (Architecture)",    lat: 40.8185, lon: -96.6994, type: "Academic",          icon: "🎓" },
  { name: "Avery Hall",                   lat: 40.8180, lon: -96.7015, type: "Academic",          icon: "🎓" },
  { name: "Bessey Hall",                  lat: 40.8196, lon: -96.7032, type: "Academic",          icon: "🎓" },
  { name: "Brace Laboratory",             lat: 40.8188, lon: -96.7020, type: "Lab",               icon: "🔬" },
  { name: "Burnett Hall",                 lat: 40.8205, lon: -96.7005, type: "Academic",          icon: "🎓" },
  { name: "Cather Hall",                  lat: 40.8248, lon: -96.6992, type: "Residence Hall",    icon: "🏠" },  // north campus
  { name: "Cather-Pound Dining",          lat: 40.8260, lon: -96.6990, type: "Dining",            icon: "🍽️" },  // north campus
  { name: "Champions Club",               lat: 40.8228, lon: -96.7058, type: "Athletics",         icon: "🏆" },
  { name: "Chase Hall",                   lat: 40.8200, lon: -96.7045, type: "Academic",          icon: "🎓" },
  { name: "City Campus Student Union",    lat: 40.8202, lon: -96.7009, type: "Student Services",  icon: "🏛️" },
  { name: "Classics Building",            lat: 40.8193, lon: -96.7020, type: "Academic",          icon: "🎓" },
  { name: "College of Business",          lat: 40.8190, lon: -96.6985, type: "Academic",          icon: "💼" },
  { name: "College of Law",               lat: 40.8210, lon: -96.6999, type: "Academic",          icon: "⚖️" },
  { name: "Cook Pavilion",                lat: 40.8235, lon: -96.7050, type: "Athletics",         icon: "🏟️" },
  { name: "Dinsdale Family Learning Comm.", lat: 40.8204, lon: -96.7018, type: "Academic",        icon: "📚" },
  { name: "East Stadium",                 lat: 40.8228, lon: -96.7045, type: "Athletics",         icon: "🏟️" },
  { name: "Eastside Dining",              lat: 40.8197, lon: -96.6993, type: "Dining",            icon: "🍽️" },
  { name: "Ferguson Hall",                lat: 40.8198, lon: -96.7042, type: "Academic",          icon: "🎓" },
  { name: "Filley Hall",                  lat: 40.8175, lon: -96.7010, type: "Academic",          icon: "🎓" },
  { name: "Fitzpatrick Hall",             lat: 40.8215, lon: -96.7020, type: "Academic",          icon: "🎓" },
  { name: "Gaughan-Maulick Study Hall",   lat: 40.8219, lon: -96.6995, type: "Academic",          icon: "📚" },
  { name: "Gaylord Hall",                 lat: 40.8245, lon: -96.6988, type: "Residence Hall",    icon: "🏠" },  // north campus
  { name: "Gillen Hall",                  lat: 40.8209, lon: -96.7030, type: "Academic",          icon: "🎓" },
  { name: "Grant Memorial Hall",          lat: 40.8207, lon: -96.7014, type: "Academic",          icon: "🎓" },
  { name: "Hardin Hall",                  lat: 40.8178, lon: -96.7008, type: "Academic",          icon: "🎓" },
  { name: "Harpster Hall",                lat: 40.8217, lon: -96.7010, type: "Academic",          icon: "🎓" },
  { name: "Harper Dining Center",         lat: 40.8260, lon: -96.6990, type: "Dining",            icon: "🍽️" },  // north campus
  { name: "Hawks Hall (Business)",        lat: 40.8190, lon: -96.6985, type: "Academic",          icon: "💼" },
  { name: "Health Center (SHCS)",         lat: 40.8211, lon: -96.7043, type: "Health",            icon: "🏥" },
  { name: "Henzlik Hall",                 lat: 40.8205, lon: -96.7025, type: "Academic",          icon: "🎓" },
  { name: "Hewit Place",                  lat: 40.8238, lon: -96.7002, type: "Residence Hall",    icon: "🏠" },
  { name: "Hope Residence Center",        lat: 40.8243, lon: -96.6995, type: "Residence Hall",    icon: "🏠" },
  { name: "Howard L. Hawks Hall",         lat: 40.8190, lon: -96.6985, type: "Academic",          icon: "💼" },
  { name: "Husker Hub",                   lat: 40.8202, lon: -96.7011, type: "Student Services",  icon: "🏛️" },
  { name: "Jorgensen Hall",               lat: 40.8199, lon: -96.7015, type: "Academic",          icon: "🎓" },
  { name: "Kauffman Academic Residential Comm.", lat: 40.8187, lon: -96.7008, type: "Residence Hall", icon: "🏠" },
  { name: "Keim Hall",                    lat: 40.8175, lon: -96.7025, type: "Academic",          icon: "🎓" },
  { name: "Kimball Hall",                 lat: 40.8197, lon: -96.7026, type: "Academic",          icon: "🎓" },
  { name: "Knoll Residential Center",     lat: 40.8213, lon: -96.7048, type: "Residence Hall",    icon: "🏠" },
  { name: "Krause Chapel",                lat: 40.8222, lon: -96.7060, type: "Other",             icon: "⛪" },
  { name: "Larsen Hall",                  lat: 40.8195, lon: -96.7018, type: "Academic",          icon: "🎓" },
  { name: "Liberal Arts and Sciences Hall",lat: 40.8187, lon: -96.7030, type: "Academic",         icon: "🎓" },
  { name: "Love Library",                 lat: 40.8197, lon: -96.7019, type: "Library",           icon: "📚" },
  { name: "Louise Pound Hall",            lat: 40.8201, lon: -96.7036, type: "Academic",          icon: "🎓" },
  { name: "Lyman Briggs Hall",            lat: 40.8195, lon: -96.7012, type: "Academic",          icon: "🎓" },
  { name: "Mabel Lee Hall",               lat: 40.8207, lon: -96.7038, type: "Academic",          icon: "🏋️" },
  { name: "Marvel Baker Hall",            lat: 40.8208, lon: -96.7003, type: "Academic",          icon: "🎓" },
  { name: "McCollum Hall",                lat: 40.8214, lon: -96.7030, type: "Academic",          icon: "🎓" },
  { name: "Memorial Stadium",             lat: 40.8231, lon: -96.7054, type: "Athletics",         icon: "🏟️" },
  { name: "Morrill Hall (Elephant Hall)", lat: 40.8204, lon: -96.7030, type: "Museum",            icon: "🦣" },
  { name: "Nebraska East Union",          lat: 40.8197, lon: -96.6993, type: "Student Services",  icon: "🏛️" },
  { name: "Nebraska Hall",                lat: 40.8183, lon: -96.7022, type: "Academic",          icon: "🎓" },
  { name: "Nebraska Innovation Campus",   lat: 40.8150, lon: -96.6980, type: "Research",          icon: "💡" },
  { name: "Nebraska Union",               lat: 40.8202, lon: -96.7009, type: "Student Services",  icon: "🏛️" },
  { name: "Newhouse Hall",                lat: 40.8215, lon: -96.7015, type: "Academic",          icon: "🎓" },
  { name: "Othmer Hall",                  lat: 40.8182, lon: -96.7017, type: "Academic",          icon: "🔬" },
  { name: "Plant Sciences Hall",          lat: 40.8178, lon: -96.7028, type: "Academic",          icon: "🌱" },
  { name: "Pound Hall",                   lat: 40.8256, lon: -96.6990, type: "Residence Hall",    icon: "🏠" },  // north campus
  { name: "Prem S. Paul Research Center", lat: 40.8176, lon: -96.7005, type: "Research",          icon: "🔬" },
  { name: "Public Policy Center",         lat: 40.8210, lon: -96.7008, type: "Research",          icon: "🔬" },
  { name: "Richards Hall",                lat: 40.8208, lon: -96.7017, type: "Academic",          icon: "🎓" },
  { name: "Roper Hall",                   lat: 40.8192, lon: -96.7028, type: "Academic",          icon: "🎓" },
  { name: "Ross Media Arts Center",       lat: 40.8200, lon: -96.7012, type: "Academic",          icon: "🎬" },
  { name: "Schmid Law Library",           lat: 40.8210, lon: -96.7001, type: "Library",           icon: "📚" },
  { name: "Scott Engineering Center",     lat: 40.8183, lon: -96.7005, type: "Academic",          icon: "⚙️" },
  { name: "Seaton Hall",                  lat: 40.8186, lon: -96.6997, type: "Academic",          icon: "🎓" },
  { name: "Selleck Quadrangle",           lat: 40.8225, lon: -96.6988, type: "Residence Hall",    icon: "🏠" },
  { name: "Sheldon Museum of Art",        lat: 40.8197, lon: -96.7003, type: "Museum",            icon: "🎨" },
  { name: "Smith Hall",                   lat: 40.8206, lon: -96.7006, type: "Academic",          icon: "🎓" },
  { name: "Student Rec Center",           lat: 40.8207, lon: -96.7042, type: "Recreation",        icon: "🏋️" },
  { name: "Teachers College",             lat: 40.8205, lon: -96.7026, type: "Academic",          icon: "🎓" },
  { name: "Temple Building",              lat: 40.8198, lon: -96.7010, type: "Academic",          icon: "🎓" },
  { name: "Thunderbird Hall",             lat: 40.8242, lon: -96.6985, type: "Residence Hall",    icon: "🏠" },  // north campus
  { name: "University Health Center",     lat: 40.8211, lon: -96.7044, type: "Health",            icon: "🏥" },
  { name: "University Police",            lat: 40.8208, lon: -96.7048, type: "Administrative",    icon: "🚔" },
  { name: "University Suites",            lat: 40.8244, lon: -96.6983, type: "Residence Hall",    icon: "🏠" },
  { name: "Van Brunt Visitor Center",     lat: 40.8215, lon: -96.7000, type: "Administrative",    icon: "ℹ️" },
  { name: "Walter Scott Engineering Center", lat: 40.8183, lon: -96.7005, type: "Academic",       icon: "⚙️" },
  { name: "Westbrook Music Building",     lat: 40.8202, lon: -96.7048, type: "Academic",          icon: "🎵" },
  { name: "Whitney Hall",                 lat: 40.8199, lon: -96.7046, type: "Academic",          icon: "🎓" },
  { name: "Willa Cather Dining",          lat: 40.8260, lon: -96.6990, type: "Dining",            icon: "🍽️" },  // north campus
  { name: "Woods Art Building",           lat: 40.8192, lon: -96.7014, type: "Academic",          icon: "🎨" },
  { name: "Ziegler Center",               lat: 40.8196, lon: -96.6999, type: "Administrative",    icon: "🏢" },
].sort((a, b) => a.name.localeCompare(b.name));

type ReportType = "icy" | "cleared" | "blocked" | "salted";
type ReportItem = {
  id: number;
  lat: number;
  lon: number;
  report_type: ReportType;
  note: string;
  rating: number;
  created_at: string;
};

const MOCK_REPORTS: ReportItem[] = [
  { id: 1, lat: 40.8208, lon: -96.7015, report_type: "icy", note: "Very slippery near steps", rating: 1, created_at: "2026-02-10T08:12:00Z" },
  { id: 2, lat: 40.8195, lon: -96.7022, report_type: "cleared", note: "Salted and dry", rating: 5, created_at: "2026-02-10T09:00:00Z" },
  { id: 3, lat: 40.8201, lon: -96.7005, report_type: "blocked", note: "Snowplow blocking path", rating: 2, created_at: "2026-02-10T07:30:00Z" },
  { id: 4, lat: 40.8185, lon: -96.7030, report_type: "salted", note: "Salt applied", rating: 4, created_at: "2026-02-10T09:45:00Z" },
  { id: 5, lat: 40.8212, lon: -96.7000, report_type: "cleared", note: "Fully shoveled", rating: 5, created_at: "2026-02-10T08:50:00Z" },
  { id: 6, lat: 40.8190, lon: -96.7012, report_type: "icy", note: "Black ice near fountain", rating: 1, created_at: "2026-02-10T10:00:00Z" },
  { id: 7, lat: 40.8209, lon: -96.7022, report_type: "blocked", note: "Temporary blockage", rating: 2, created_at: "2026-02-10T11:15:00Z" },
  { id: 8, lat: 40.8210, lon: -96.7028, report_type: "cleared", note: "Open walkway", rating: 5, created_at: "2026-02-10T14:00:00Z" },
];

const REPORT_CONFIG: Record<ReportType, { color: string; icon: string; label: string; bg: string }> = {
  icy: { color: "#60a5fa", icon: "🧊", label: "Icy", bg: "rgba(96,165,250,0.15)" },
  cleared: { color: "#4ade80", icon: "✅", label: "Cleared", bg: "rgba(74,222,128,0.15)" },
  blocked: { color: "#f87171", icon: "🚧", label: "Blocked", bg: "rgba(248,113,113,0.15)" },
  salted: { color: "#fb923c", icon: "🧂", label: "Salted", bg: "rgba(251,146,60,0.15)" },
};

function normalizeSearchText(v: string) {
  return v.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function localSearchResults(q: string) {
  const qn = normalizeSearchText(q);
  const qTokens = qn.split(" ").filter(Boolean);
  if (!qn || qTokens.length === 0) return [];

  const pool = [...SPECIAL_SEARCH_POINTS, ...UNL_BUILDINGS];
  const scored = pool.map((item) => {
    const nn = normalizeSearchText(item.name);
    const nTokens = nn.split(" ").filter(Boolean);
    let score = 0;
    if (nn === qn) score = 5000;
    else if (nn.startsWith(qn)) score = 3000;
    else if (qn.length >= 3 && nn.includes(qn)) score = 2100;
    else {
      const overlap = qTokens.filter((t) => nTokens.includes(t)).length;
      if (overlap > 0) score = 1300 + overlap * 180;
    }
    if (score === 0) return null;
    // Penalize long unrelated names for short queries.
    score -= Math.max(0, nTokens.length - qTokens.length) * 20;
    return { ...item, score };
  }).filter(Boolean) as Array<any>;

  const bestByName = new Map<string, any>();
  for (const row of scored) {
    const key = normalizeSearchText(row.name);
    const prev = bestByName.get(key);
    if (!prev || row.score > prev.score) bestByName.set(key, row);
  }

  return Array.from(bestByName.values())
    .sort((a, b) => b.score - a.score || a.name.localeCompare(b.name))
    .slice(0, 8)
    .map(({ score, ...rest }) => rest);
}

// ─── Search logic: local fuzzy match + Overpass fallback ─────────────────
function searchBuildings(query: string): Array<{ name: string; lat: number; lon: number; type: string; icon: string; score: number }> {
  void query;
  // Kept for type compatibility; authoritative search now comes from backend /campus/search.
  return [];
}

function approxMeters(lat1: number, lon1: number, lat2: number, lon2: number) {
  const R = 6371000;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a = Math.sin(dLat / 2) ** 2 + Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function normalizeAngle(a: number) { while (a > 180) a -= 360; while (a <= -180) a += 360; return a; }
function bearingToCompass(b: number) {
  const v = (b + 360) % 360;
  if (v >= 337.5 || v < 22.5) return "North"; if (v < 67.5) return "NE";
  if (v < 112.5) return "East"; if (v < 157.5) return "SE";
  if (v < 202.5) return "South"; if (v < 247.5) return "SW";
  if (v < 292.5) return "West"; return "NW";
}

function instructionText(step: any, prevStep: any | null) {
  const bearing = (Math.atan2(step.end.lon - step.start.lon, step.end.lat - step.start.lat) * 180) / Math.PI;
  if (!step.outdoors) return step.instr || "Pass through building";
  if (!prevStep) return `Head ${bearingToCompass(bearing)}`;
  const prevBearing = (Math.atan2(prevStep.end.lon - prevStep.start.lon, prevStep.end.lat - prevStep.start.lat) * 180) / Math.PI;
  const diff = normalizeAngle(bearing - prevBearing);
  if (Math.abs(diff) < 30) return `Continue ${bearingToCompass(bearing)}`;
  if (diff > 0) return `Turn right · ${bearingToCompass(bearing)}`;
  return `Turn left · ${bearingToCompass(bearing)}`;
}

function toFiniteNumber(v: any): number | null {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function routeFeaturesFromMeta(meta: any) {
  const route = meta?.route || {};
  const segs = Array.isArray(route.segments) ? route.segments : [];
  const features = segs
    .map((s: any) => {
      const coords = (Array.isArray(s?.coords) ? s.coords : [])
        .map((c: any) => {
          const lat = toFiniteNumber(c?.lat);
          const lon = toFiniteNumber(c?.lon);
          return lat == null || lon == null ? null : [lon, lat];
        })
        .filter(Boolean);
      if (coords.length < 2) return null;
      return {
        type: "Feature",
        geometry: { type: "LineString", coordinates: coords },
        properties: { outdoors: s?.outdoors !== false },
      };
    })
    .filter(Boolean);

  if (features.length > 0) return features;

  const routeCoords = (Array.isArray(route.coords) ? route.coords : [])
    .map((c: any) => {
      const lat = toFiniteNumber(c?.lat);
      const lon = toFiniteNumber(c?.lon);
      return lat == null || lon == null ? null : [lon, lat];
    })
    .filter(Boolean);

  if (routeCoords.length < 2) return [];
  return [{
    type: "Feature",
    geometry: { type: "LineString", coordinates: routeCoords },
    properties: { outdoors: true },
  }];
}

function endpointPin(letter: string, color: string) {
  const d = document.createElement("div");
  d.innerHTML = `<div style="background:${color};color:#fff;font-size:13px;font-weight:800;border-radius:50%;width:34px;height:34px;display:flex;align-items:center;justify-content:center;border:3px solid #fff;box-shadow:0 3px 10px rgba(0,0,0,0.4)">${letter}</div>`;
  return d;
}

type Panel = "route" | "report" | "alerts" | null;
const MODE_META = {
  shortest: {
    title: "Fastest",
    description: "Picks the most direct path with minimum travel distance/time.",
  },
  sheltered: {
    title: "Sheltered",
    description: "Prefers indoor connectors and reduces outdoor exposure in cold weather.",
  },
  cleared: {
    title: "Cleared",
    description: "Prefers segments with positive condition reports and avoids risky areas when possible.",
  },
} as const;

export default function SnowPathApp() {
  const mapDivRef  = useRef<HTMLDivElement | null>(null);
  const mapRef     = useRef<maplibregl.Map | null>(null);
  const userMarkerRef  = useRef<maplibregl.Marker | null>(null);
  const startMarkerRef = useRef<maplibregl.Marker | null>(null);
  const endMarkerRef   = useRef<maplibregl.Marker | null>(null);
  const watchIdRef = useRef<number | null>(null);
  const headingRef = useRef<number>(0);

  const [panel, setPanel]           = useState<Panel>("route");
  const [start, setStart]           = useState<any | null>(null);
  const [end, setEnd]               = useState<any | null>(null);
  const [mode, setMode]             = useState<"shortest" | "sheltered" | "cleared">("sheltered");
  const [routeMeta, setRouteMeta]   = useState<any>(null);
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [liveNav, setLiveNav]       = useState(false);
  const [userLoc, setUserLoc]       = useState<{ lat: number; lon: number } | null>(null);
  const [userHeading, setUserHeading] = useState<number>(0);
  const [reports, setReports]       = useState<ReportItem[]>(MOCK_REPORTS);
  const [loading, setLoading]       = useState(false);
  const [mapReady, setMapReady]     = useState(false);

  // Report form state
  const [reportPos, setReportPos]   = useState<{ lat: number; lon: number } | null>(null);
  const [reportType, setReportType] = useState<ReportType>("icy");
  const [reportNote, setReportNote] = useState<string>("");
  const [reportRating, setReportRating] = useState<number>(3);
  const [reportSuccess, setReportSuccess] = useState(false);

  // ── Build user arrow marker ───────────────────────────────────────────────
  const buildArrow = () => {
    const el = document.createElement("div");
    el.style.cssText = "width:44px;height:44px;position:relative;display:flex;align-items:center;justify-content:center;";
    el.innerHTML = `
      <div style="width:44px;height:44px;border-radius:50%;background:radial-gradient(circle at 40% 35%,#4f8ef7,#1a56e8);box-shadow:0 0 0 5px rgba(79,142,247,0.3),0 4px 14px rgba(26,86,232,0.6);display:flex;align-items:center;justify-content:center;">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="white"><path d="M12 2L4.5 20.29l.71.71L12 18l6.79 3 .71-.71z"/></svg>
      </div>
      <div style="position:absolute;bottom:-8px;left:50%;transform:translateX(-50%);width:14px;height:14px;border-radius:50%;background:rgba(79,142,247,0.25);animation:snowpulse 2s infinite;"></div>`;
    return el;
  };

  // ── Map init ──────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!mapDivRef.current) return;
    const styleEl = document.createElement("style");
    styleEl.textContent = `
      @keyframes snowpulse{0%,100%{transform:translateX(-50%) scale(1);opacity:.6}50%{transform:translateX(-50%) scale(2.5);opacity:0}}
      .maplibregl-ctrl-attrib,.maplibregl-ctrl-logo{display:none!important}
    `;
    document.head.appendChild(styleEl);

    const map = new maplibregl.Map({
      container: mapDivRef.current!,
      style: {
        version: 8,
        sources: { osm: { type: "raster", tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"], tileSize: 256 } },
        layers: [{ id: "osm", type: "raster", source: "osm" }],
      },
      center: [-96.7009, 40.8202],
      zoom: 15.0,
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), "bottom-right");

    map.on("load", () => {
      // Fetch campus GeoJSON from backend
      fetch(`${API_BASE}/campus/geojson`).then(r => r.json()).then(data => {
        const feats = data.features || {};
        if (feats.buildings?.features?.length) {
          map.addSource("buildings", { type: "geojson", data: feats.buildings });
          map.addLayer({ id: "buildings-fill", type: "fill", source: "buildings", paint: { "fill-color": "#4b5563", "fill-opacity": 0.5 } });
          map.addLayer({ id: "buildings-line", type: "line", source: "buildings", paint: { "line-color": "#2d3748", "line-width": 1.5 } });
          // Keep map readable: building labels + OSM labels create heavy overlap.
          map.addLayer({
            id: "buildings-label",
            type: "symbol",
            source: "buildings",
            minzoom: 16.8,
            layout: {
              "text-field": ["get", "name"],
              "text-size": 9,
              "text-max-width": 8,
            },
            paint: { "text-color": "#cbd5e0", "text-opacity": 0.65 },
          });
        }
        if (feats.paths?.features?.length) {
          map.addSource("paths", { type: "geojson", data: feats.paths });
          map.addLayer({ id: "paths-line", type: "line", source: "paths", paint: { "line-color": "#6b7280", "line-width": 2, "line-opacity": 0.6 } });
        }
        // Keep active route above buildings/paths even if those layers load later.
        if (map.getLayer("route-casing")) map.moveLayer("route-casing");
        if (map.getLayer("route-fill")) map.moveLayer("route-fill");
      }).catch(console.error);

      // Route segments
      map.addSource("route-seg", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({
        id: "route-casing",
        type: "line",
        source: "route-seg",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-width": 12, "line-color": "#fff", "line-opacity": 0.30 },
      });
      map.addLayer({
        id: "route-fill", type: "line", source: "route-seg",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-width": 7,
          "line-color": ["case", ["==", ["get", "outdoors"], false], "#34d399", "#4f8ef7"],
          "line-opacity": 0.95,
        },
      });

      // Reports dots
      map.addSource("reports", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({
        id: "reports-circle", type: "circle", source: "reports",
        paint: {
          "circle-radius": 11,
          "circle-color": ["match", ["get", "report_type"], "icy", "#60a5fa", "cleared", "#4ade80", "blocked", "#f87171", "salted", "#fb923c", "#a78bfa"],
          "circle-opacity": 0.9, "circle-stroke-width": 2.5, "circle-stroke-color": "#fff",
        },
      });

      // User arrow
      userMarkerRef.current = new maplibregl.Marker({ element: buildArrow(), rotationAlignment: "map", pitchAlignment: "map" })
        .setLngLat([-96.7009, 40.8202]).addTo(map);

      // Map click → set report position or start/end
      map.on("click", (e) => {
        const loc = { lat: e.lngLat.lat, lon: e.lngLat.lng };
        setPanel(p => {
          if (p === "report") { setReportPos(loc); return "report"; }
          return p;
        });
      });

      setMapReady(true);
    });

    mapRef.current = map;
    return () => { map.remove(); mapRef.current = null; };
  }, []);

  // ── Initial location (single fix) ────────────────────────────────────────
  useEffect(() => {
    if (!("geolocation" in navigator)) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude: lat, longitude: lon, heading } = pos.coords;
        setUserLoc({ lat, lon });
        userMarkerRef.current?.setLngLat([lon, lat]);
        if (heading != null && !isNaN(heading)) {
          headingRef.current = heading;
          setUserHeading(heading);
          userMarkerRef.current?.setRotation(heading);
        }
      },
      () => undefined,
      { enableHighAccuracy: true, timeout: 7000, maximumAge: 30000 }
    );
  }, []);

  // ── Reports → map ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (!mapReady) return;
    const src = mapRef.current?.getSource("reports") as any;
    if (!src) return;
    src.setData({
      type: "FeatureCollection",
      features: reports.map(r => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [r.lon, r.lat] },
        properties: { report_type: r.report_type, note: r.note, rating: r.rating },
      })),
    });
  }, [reports, mapReady]);

  // ── Route meta → map (handles async race when source isn't ready yet) ───
  useEffect(() => {
    if (!mapReady) return;
    const map = mapRef.current;
    if (!map) return;
    const src = map.getSource("route-seg") as any;
    if (!src) return;
    const segs = routeFeaturesFromMeta(routeMeta);
    src.setData({ type: "FeatureCollection", features: segs });
  }, [routeMeta, mapReady]);

  // ── Device orientation → arrow heading ───────────────────────────────────
  useEffect(() => {
    const handler = (e: any) => {
      const h = e.webkitCompassHeading ?? (e.alpha != null ? 360 - e.alpha : null);
      if (h != null) { headingRef.current = h; setUserHeading(h); userMarkerRef.current?.setRotation(h); }
    };
    window.addEventListener("deviceorientationabsolute", handler, true);
    window.addEventListener("deviceorientation", handler, true);
    return () => { window.removeEventListener("deviceorientationabsolute", handler, true); window.removeEventListener("deviceorientation", handler, true); };
  }, []);

  // ── Geolocation watch ─────────────────────────────────────────────────────
  useEffect(() => {
    if (!liveNav) { if (watchIdRef.current != null) { navigator.geolocation.clearWatch(watchIdRef.current); watchIdRef.current = null; } return; }
    if (!("geolocation" in navigator)) { alert("Geolocation not supported"); setLiveNav(false); return; }
    const id = navigator.geolocation.watchPosition(
      (pos) => {
        const { latitude: lat, longitude: lon, heading } = pos.coords;
        setUserLoc({ lat, lon });
        if (heading != null && !isNaN(heading)) { headingRef.current = heading; setUserHeading(heading); userMarkerRef.current?.setRotation(heading); }
        userMarkerRef.current?.setLngLat([lon, lat]);
        mapRef.current?.easeTo({ center: [lon, lat], duration: 600 });
      },
      (err) => console.warn("Geo:", err),
      { enableHighAccuracy: true, maximumAge: 2000 }
    );
    watchIdRef.current = id;
    return () => { navigator.geolocation.clearWatch(id); };
  }, [liveNav]);

  // ── Fetch route ───────────────────────────────────────────────────────────
  const fetchRoute = useCallback(async () => {
    if (!start || !end) return;
    setLoading(true);
    try {
      const r = await fetch(`${API_BASE}/route/advanced?start_lat=${start.lat}&start_lon=${start.lon}&end_lat=${end.lat}&end_lon=${end.lon}&mode=${mode}`);
      if (!r.ok) throw new Error(`Route request failed: ${r.status}`);
      const j = await r.json();
      setRouteMeta(j); setCurrentStep(0);

      const map = mapRef.current;
      if (!map) return;

      const segs = routeFeaturesFromMeta(j);
      (map.getSource("route-seg") as any)?.setData({ type: "FeatureCollection", features: segs });

      const coords = j?.route?.coords || [];
      if (coords.length > 1) {
        const bounds = coords.reduce((b: maplibregl.LngLatBounds, c: any) => b.extend([c.lon, c.lat]),
          new maplibregl.LngLatBounds([coords[0].lon, coords[0].lat], [coords[0].lon, coords[0].lat]));
        map.fitBounds(bounds, {
          padding: { top: 90, left: 70, bottom: 90, right: 460 },
          maxZoom: 16.2,
          duration: 900,
        });
      }

    } catch (err) { console.error("Route failed:", err); }
    setLoading(false);
  }, [start, end, mode]);

  useEffect(() => {
    if (!start || !end) return;
    fetchRoute();
  }, [mode, start, end, fetchRoute]);

  // Keep A/B pins synced to selected points immediately.
  useEffect(() => {
    if (!mapReady) return;
    const map = mapRef.current;
    if (!map) return;
    startMarkerRef.current?.remove();
    if (start) {
      startMarkerRef.current = new maplibregl.Marker({ element: endpointPin("A", "#4f8ef7") })
        .setLngLat([start.lon, start.lat])
        .addTo(map);
    }
  }, [start, mapReady]);

  useEffect(() => {
    if (!mapReady) return;
    const map = mapRef.current;
    if (!map) return;
    endMarkerRef.current?.remove();
    if (end) {
      endMarkerRef.current = new maplibregl.Marker({ element: endpointPin("B", "#f87171") })
        .setLngLat([end.lon, end.lat])
        .addTo(map);
    }
  }, [end, mapReady]);

  // ── Submit report ─────────────────────────────────────────────────────────
  const submitReport = useCallback(async () => {
    if (!reportPos) return;
    const nr = { id: Date.now(), lat: reportPos.lat, lon: reportPos.lon, report_type: reportType, note: reportNote, rating: reportRating, created_at: new Date().toISOString() };
    try { await fetch(`${API_BASE}/reports`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(nr) }); } catch (_) {}
    setReports(p => [nr, ...p]);
    setReportSuccess(true); setReportNote(""); setReportPos(null);
    setTimeout(() => { setReportSuccess(false); setPanel("route"); }, 2200);
  }, [reportPos, reportType, reportNote, reportRating]);

  const sc = useMemo(() => ({
    icy: reports.filter(r => r.report_type === "icy").length,
    cleared: reports.filter(r => r.report_type === "cleared").length,
    blocked: reports.filter(r => r.report_type === "blocked").length,
    salted: reports.filter(r => r.report_type === "salted").length,
  }), [reports]);

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div style={{ position: "fixed", inset: 0, fontFamily: "'Google Sans','Segoe UI',sans-serif", overflow: "hidden" }}>
      <div ref={mapDivRef} style={{ position: "absolute", inset: 0 }} />

      {/* ── Top bar ─────────────────────────────────────────────────────── */}
      <div style={{ position: "absolute", top: 12, right: 12, zIndex: 20, width: "min(420px,calc(100vw - 24px))", display: "flex", flexDirection: "column", gap: 8 }}>

        {/* Header chip */}
        <div style={{ background: "rgba(18,18,28,0.96)", backdropFilter: "blur(20px)", borderRadius: 16, padding: "10px 12px", boxShadow: "0 8px 32px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.07)", display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 22 }}>❄️</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ color: "#f0f4ff", fontWeight: 700, fontSize: 15, letterSpacing: "-.3px" }}>SnowPath UNL</div>
            <div style={{ color: "#4b5563", fontSize: 11 }}>Winter-aware campus routing</div>
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            <TabBtn active={panel === "route"}  onClick={() => setPanel(p => p === "route"  ? null : "route")}  icon="🗺️" label="Route"  />
            <TabBtn active={panel === "report"} onClick={() => setPanel(p => p === "report" ? null : "report")} icon="📍" label="Report" />
            <TabBtn active={panel === "alerts"} onClick={() => setPanel(p => p === "alerts" ? null : "alerts")} icon="⚠️" label={String(reports.length)} />
          </div>
        </div>

        {/* ── ROUTE PANEL ─────────────────────────────────────────────── */}
        {panel === "route" && (
          <div style={{ background: "rgba(18,18,28,0.97)", backdropFilter: "blur(20px)", borderRadius: 16, overflow: "hidden", boxShadow: "0 8px 32px rgba(0,0,0,0.5)" }}>
            <div style={{ padding: "16px 16px 12px" }}>

              {/* From field */}
              <div style={{ marginBottom: 8 }}>
                <LocationSearchInput
                  dotColor="#4f8ef7"
                  placeholder="Starting point…"
                  selected={start}
                  onSelect={setStart}
                  onClear={() => { setStart(null); startMarkerRef.current?.remove(); }}
                  onLocate={() => {
                    if (userLoc) { setStart({ lat: userLoc.lat, lon: userLoc.lon, name: "My Location", icon: "📡", type: "Current Location" }); }
                    else { setLiveNav(true); }
                  }}
                  showLocateBtn
                  onFlyTo={(loc) => mapRef.current?.easeTo({ center: [loc.lon, loc.lat], zoom: 17, duration: 700 })}
                />
              </div>

              {/* Swap divider */}
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                <div style={{ flex: 1, height: 1, background: "rgba(255,255,255,0.05)" }} />
                <button onClick={() => { const tmp = start; setStart(end); setEnd(tmp); }} style={{ background: "rgba(255,255,255,0.06)", border: "none", borderRadius: 8, width: 28, height: 28, cursor: "pointer", color: "#9ca3af", fontSize: 14, display: "flex", alignItems: "center", justifyContent: "center" }} title="Swap">⇅</button>
                <div style={{ flex: 1, height: 1, background: "rgba(255,255,255,0.05)" }} />
              </div>

              {/* To field */}
              <div style={{ marginBottom: 12 }}>
                <LocationSearchInput
                  dotColor="#f87171"
                  placeholder="Search destination…"
                  selected={end}
                  onSelect={setEnd}
                  onClear={() => { setEnd(null); endMarkerRef.current?.remove(); }}
                  onFlyTo={(loc) => mapRef.current?.easeTo({ center: [loc.lon, loc.lat], zoom: 17, duration: 700 })}
                />
              </div>

              {/* Mode */}
              <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
                {(["shortest", "sheltered", "cleared"] as const).map((m) => (
                  <button key={m} onClick={() => setMode(m)} style={{
                    flex: 1, padding: "9px 4px", borderRadius: 10, border: `1.5px solid ${mode === m ? "transparent" : "rgba(255,255,255,0.07)"}`,
                    fontWeight: mode === m ? 700 : 400, fontSize: 11,
                    background: mode === m ? (m === "sheltered" ? "linear-gradient(135deg,#1e3a8a,#1e40af)" : m === "cleared" ? "linear-gradient(135deg,#14532d,#15803d)" : "linear-gradient(135deg,#1f2937,#374151)") : "rgba(255,255,255,0.04)",
                    color: mode === m ? "#fff" : "#6b7280", cursor: "pointer", transition: "all .2s",
                  }}>
                    {m === "shortest" ? "⚡ Fastest" : m === "sheltered" ? "🏛️ Sheltered" : "✅ Cleared"}
                  </button>
                ))}
              </div>
              <div style={{ marginBottom: 12, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)", borderRadius: 10, padding: "8px 10px" }}>
                <div style={{ fontSize: 11, color: "#cbd5e1", fontWeight: 700 }}>
                  Path mode: {MODE_META[mode].title}
                </div>
                <div style={{ fontSize: 11, color: "#6b7280", marginTop: 2 }}>
                  {MODE_META[mode].description}
                </div>
              </div>

              <button onClick={fetchRoute} disabled={!start || !end || loading} style={{
                width: "100%", padding: "13px", borderRadius: 12, border: "none",
                background: (!start || !end) ? "rgba(79,142,247,0.15)" : "linear-gradient(135deg,#4f8ef7,#1a56e8)",
                color: (!start || !end) ? "#374151" : "#fff",
                fontWeight: 700, fontSize: 14, cursor: (!start || !end) ? "default" : "pointer",
                boxShadow: (!start || !end) ? "none" : "0 4px 18px rgba(79,142,247,0.45)",
                letterSpacing: "-.2px", transition: "all .2s",
              }}>
                {loading ? "Finding best route…" : "Get Directions"}
              </button>
            </div>

            {/* Route summary */}
            {routeMeta && (
              <div style={{ padding: "0 16px 14px" }}>
                <div style={{ background: "rgba(79,142,247,0.08)", border: "1px solid rgba(79,142,247,0.15)", borderRadius: 12, padding: "12px 14px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10 }}>
                    <Stat label="Distance" value={`${(routeMeta.route.total_meters / 1000).toFixed(2)} km`} />
                    <Stat label="Outdoors"  value={`${((routeMeta.route.outdoor_meters / Math.max(1, routeMeta.route.total_meters)) * 100).toFixed(0)}%`} />
                    <Stat label="Cold Exp." value={`${routeMeta.route.cold_exposure_minutes.toFixed(0)} min`} />
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 11, color: "#6b7280" }}>Snow risk</span>
                    <div style={{ flex: 1, height: 5, background: "rgba(255,255,255,0.07)", borderRadius: 99, overflow: "hidden" }}>
                      <div style={{ height: "100%", borderRadius: 99, width: `${Math.min(100, (routeMeta.route.snow_risk_score || 0) * 100).toFixed(0)}%`, background: `hsl(${120 - (routeMeta.route.snow_risk_score || 0) * 120},75%,52%)` }} />
                    </div>
                    <span style={{ fontSize: 11, color: "#9ca3af" }}>{((routeMeta.route.snow_risk_score || 0) * 100).toFixed(0)}%</span>
                  </div>
                </div>
              </div>
            )}

            {/* Turn-by-turn */}
            {routeMeta?.route?.steps?.length > 0 && (
              <>
                <div style={{ padding: "0 16px 6px", color: "#4b5563", fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: ".8px" }}>Turn-by-turn</div>
                <div style={{ maxHeight: 210, overflowY: "auto", borderTop: "1px solid rgba(255,255,255,0.04)" }}>
                  {routeMeta.route.steps.map((s: any, i: number) => (
                    <div key={i} onClick={() => setCurrentStep(i)} style={{ padding: "10px 16px", display: "flex", alignItems: "center", gap: 12, background: i === currentStep ? "rgba(79,142,247,0.09)" : "transparent", cursor: "pointer", borderBottom: "1px solid rgba(255,255,255,0.03)" }}>
                      <div style={{ width: 34, height: 34, borderRadius: 10, background: i === currentStep ? "rgba(79,142,247,0.22)" : "rgba(255,255,255,0.05)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 17, flexShrink: 0 }}>
                        {i === 0 ? "🚶" : s.outdoors ? "↗️" : "🏛️"}
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 13, color: "#e2e8f0", fontWeight: i === currentStep ? 600 : 400, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {instructionText(s, i > 0 ? routeMeta.route.steps[i - 1] : null)}
                        </div>
                        <div style={{ fontSize: 11, color: "#6b7280", marginTop: 1 }}>
                          {s.distance_m.toFixed(0)} m · {Math.ceil(s.distance_m / 80)} min
                          {liveNav && userLoc && <span style={{ marginLeft: 6, color: "#4f8ef7" }}>~{Math.ceil(approxMeters(userLoc.lat, userLoc.lon, s.end.lat, s.end.lon) / 80)} min</span>}
                        </div>
                      </div>
                      <span style={{ fontSize: 10, fontWeight: 700, color: s.outdoors ? "#4f8ef7" : "#34d399" }}>{s.outdoors ? "OUT" : "IN"}</span>
                    </div>
                  ))}
                </div>
              </>
            )}

            {/* Live nav toggle */}
            <div style={{ padding: "12px 16px", borderTop: "1px solid rgba(255,255,255,0.04)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span style={{ fontSize: 12, color: "#6b7280" }}>📡 Live navigation</span>
              <Toggle on={liveNav} onChange={setLiveNav} />
            </div>
          </div>
        )}

        {/* ── REPORT PANEL ─────────────────────────────────────────────── */}
        {panel === "report" && (
          <div style={{ background: "rgba(18,18,28,0.97)", backdropFilter: "blur(20px)", borderRadius: 16, padding: 18, boxShadow: "0 8px 32px rgba(0,0,0,0.5)" }}>
            {reportSuccess ? (
              <div style={{ textAlign: "center", padding: "24px 0" }}>
                <div style={{ fontSize: 44, marginBottom: 10 }}>✅</div>
                <div style={{ color: "#4ade80", fontWeight: 700, fontSize: 17 }}>Report submitted!</div>
                <div style={{ color: "#6b7280", fontSize: 13, marginTop: 5 }}>Thanks for helping other walkers.</div>
              </div>
            ) : (
              <>
                <div style={{ color: "#e2e8f0", fontWeight: 700, fontSize: 15, marginBottom: 14 }}>📍 Report a path condition</div>
                {reportPos
                  ? <div style={{ background: "rgba(79,142,247,0.1)", border: "1px solid rgba(79,142,247,0.2)", borderRadius: 9, padding: "7px 11px", marginBottom: 13, fontSize: 12, color: "#9ca3af", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span>📌 {reportPos.lat.toFixed(5)}, {reportPos.lon.toFixed(5)}</span>
                      <button onClick={() => setReportPos(null)} style={{ background: "none", border: "none", color: "#6b7280", cursor: "pointer", fontSize: 14 }}>✕</button>
                    </div>
                  : <div style={{ background: "rgba(251,146,60,0.1)", border: "1px solid rgba(251,146,60,0.2)", borderRadius: 9, padding: "8px 12px", marginBottom: 13, fontSize: 12, color: "#fb923c" }}>👆 Tap anywhere on the map to drop a pin first</div>
                }
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 13 }}>
                  {(Object.entries(REPORT_CONFIG) as Array<[ReportType, (typeof REPORT_CONFIG)[ReportType]]>).map(([type, cfg]) => (
                    <button key={type} onClick={() => setReportType(type)} style={{ padding: "11px 8px", borderRadius: 10, border: `2px solid ${reportType === type ? cfg.color : "transparent"}`, background: reportType === type ? cfg.bg : "rgba(255,255,255,0.04)", color: reportType === type ? cfg.color : "#6b7280", cursor: "pointer", fontSize: 13, fontWeight: reportType === type ? 700 : 400, display: "flex", alignItems: "center", justifyContent: "center", gap: 6, transition: "all .15s" }}>
                      {cfg.icon} {cfg.label}
                    </button>
                  ))}
                </div>
                <div style={{ marginBottom: 12 }}>
                  <div style={{ color: "#6b7280", fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: ".5px", marginBottom: 6 }}>Severity</div>
                  <div style={{ display: "flex", gap: 6 }}>
                    {[1,2,3,4,5].map(n => (
                      <button key={n} onClick={() => setReportRating(n)} style={{ flex: 1, height: 34, borderRadius: 8, border: "none", background: n <= reportRating ? "#fbbf24" : "rgba(255,255,255,0.06)", cursor: "pointer", fontSize: 15, transition: "all .15s" }}>⭐</button>
                    ))}
                  </div>
                </div>
                <textarea value={reportNote} onChange={e => setReportNote(e.target.value)} placeholder="Add a note… (optional)" rows={2} style={{ width: "100%", background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10, padding: "10px 12px", color: "#e2e8f0", fontSize: 13, resize: "none", fontFamily: "inherit", marginBottom: 12, boxSizing: "border-box", outline: "none" }} />
                <button onClick={submitReport} disabled={!reportPos} style={{ width: "100%", padding: "13px", borderRadius: 12, border: "none", background: reportPos ? "linear-gradient(135deg,#fb923c,#ea580c)" : "rgba(255,255,255,0.06)", color: reportPos ? "#fff" : "#374151", fontWeight: 700, fontSize: 14, cursor: reportPos ? "pointer" : "default", transition: "all .2s" }}>
                  Submit Report
                </button>
              </>
            )}
          </div>
        )}

        {/* ── ALERTS PANEL ─────────────────────────────────────────────── */}
        {panel === "alerts" && (
          <div style={{ background: "rgba(18,18,28,0.97)", backdropFilter: "blur(20px)", borderRadius: 16, overflow: "hidden", boxShadow: "0 8px 32px rgba(0,0,0,0.5)" }}>
            <div style={{ padding: "12px 16px", borderBottom: "1px solid rgba(255,255,255,0.05)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ color: "#e2e8f0", fontWeight: 700, fontSize: 14 }}>⚠️ Conditions ({reports.length})</span>
              <div style={{ display: "flex", gap: 6 }}>
                {(Object.entries(sc) as Array<[ReportType, number]>).map(([type, count]) => (
                  <span key={type} style={{ fontSize: 10, padding: "2px 7px", borderRadius: 99, background: REPORT_CONFIG[type]?.bg, color: REPORT_CONFIG[type]?.color, fontWeight: 700 }}>
                    {REPORT_CONFIG[type]?.icon} {count}
                  </span>
                ))}
              </div>
            </div>
            <div style={{ maxHeight: 320, overflowY: "auto" }}>
              {reports.map((r) => {
                const cfg = REPORT_CONFIG[r.report_type];
                return (
                  <div key={r.id} onClick={() => mapRef.current?.easeTo({ center: [r.lon, r.lat], zoom: 18, duration: 700 })} style={{ padding: "10px 16px", borderBottom: "1px solid rgba(255,255,255,0.03)", display: "flex", gap: 12, alignItems: "flex-start", cursor: "pointer" }}>
                    <span style={{ fontSize: 20, flexShrink: 0 }}>{cfg?.icon}</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: cfg?.color }}>{cfg?.label}</div>
                      {r.note && <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.note}</div>}
                      <div style={{ fontSize: 10, color: "#4b5563", marginTop: 2 }}>{"⭐".repeat(r.rating || 0)} · {new Date(r.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</div>
                    </div>
                    <span style={{ fontSize: 10, color: "#374151", flexShrink: 0 }}>{r.lat.toFixed(3)},{r.lon.toFixed(3)}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* ── FABs ─────────────────────────────────────────────────────────── */}
      <div style={{ position: "absolute", bottom: 100, right: 16, zIndex: 10, display: "flex", flexDirection: "column", gap: 10 }}>
        <FAB icon="📍" title="Center on me" onClick={() => { if (userLoc) mapRef.current?.easeTo({ center: [userLoc.lon, userLoc.lat], zoom: 17, duration: 600 }); else setLiveNav(true); }} active={!!userLoc} />
        <FAB icon={liveNav ? "🔵" : "🗺️"} title="Live nav" onClick={() => setLiveNav(v => !v)} active={liveNav} />
      </div>

      {/* ── Legend ───────────────────────────────────────────────────────── */}
      <div style={{ position: "absolute", bottom: 16, left: 16, zIndex: 10, background: "rgba(18,18,28,0.9)", backdropFilter: "blur(12px)", borderRadius: 12, padding: "8px 12px", boxShadow: "0 4px 16px rgba(0,0,0,0.4)", display: "flex", gap: 10, flexWrap: "wrap" }}>
        {(Object.entries(REPORT_CONFIG) as Array<[ReportType, (typeof REPORT_CONFIG)[ReportType]]>).map(([type, cfg]) => (
          <div key={type} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: cfg.color }}>
            <div style={{ width: 8, height: 8, borderRadius: 99, background: cfg.color }} /> {cfg.label}
          </div>
        ))}
        <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: "#4f8ef7" }}>
          <div style={{ width: 16, height: 3, background: "#4f8ef7", borderRadius: 99 }} /> Outdoor
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: "#34d399" }}>
          <div style={{ width: 16, height: 3, background: "#34d399", borderRadius: 99 }} /> Indoor
        </div>
      </div>

      {/* ── Compass ──────────────────────────────────────────────────────── */}
      {liveNav && (
        <div style={{ position: "absolute", top: 80, right: 16, zIndex: 10, background: "rgba(18,18,28,0.92)", backdropFilter: "blur(14px)", borderRadius: 14, padding: "12px 14px", textAlign: "center", boxShadow: "0 4px 18px rgba(0,0,0,0.4)" }}>
          <svg viewBox="0 0 52 52" width="52" height="52">
            <circle cx="26" cy="26" r="24" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="2" />
            <text x="26" y="11"  textAnchor="middle" fill="#f87171" fontSize="9" fontWeight="700">N</text>
            <text x="26" y="47"  textAnchor="middle" fill="#6b7280" fontSize="9" fontWeight="700">S</text>
            <text x="46" y="29"  textAnchor="middle" fill="#6b7280" fontSize="9" fontWeight="700">E</text>
            <text x="6"  y="29"  textAnchor="middle" fill="#6b7280" fontSize="9" fontWeight="700">W</text>
            <g transform={`rotate(${userHeading},26,26)`}>
              <polygon points="26,7 22,29 26,26 30,29" fill="#4f8ef7" />
              <polygon points="26,45 22,23 26,26 30,23" fill="#374151" />
            </g>
          </svg>
          <div style={{ color: "#6b7280", fontSize: 10, marginTop: 3 }}>{Math.round(userHeading)}°</div>
        </div>
      )}
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────

/** Smart location search with instant local results + Overpass fallback */
function LocationSearchInput({
  dotColor, placeholder, selected, onSelect, onClear, onLocate, showLocateBtn, onFlyTo, clearOnFocus = true,
}: {
  dotColor: string; placeholder: string; selected: any; onSelect: (v: any) => void;
  onClear: () => void; onLocate?: () => void; showLocateBtn?: boolean;
  onFlyTo?: (loc: { lat: number; lon: number }) => void;
  clearOnFocus?: boolean;
}) {
  const [query, setQuery]       = useState("");
  const [results, setResults]   = useState<any[]>([]);
  const [open, setOpen]         = useState(false);
  const [fetching, setFetching] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const isSelected = !!selected;

  const runSearch = useCallback(async (q: string) => {
    if (q.trim().length < 2) { setResults([]); return; }
    setFetching(true);
    const local = localSearchResults(q);
    try {
      const r = await fetch(`${API_BASE}/campus/search?q=${encodeURIComponent(q)}`);
      const data = await r.json();
      const remote = (data.results || []).map((res: any) => ({
        ...res,
        icon: "📍",
        type: res.type === "landmark" ? "Campus Landmark" : "Campus Building",
      }));

      const merged: any[] = [];
      const seen = new Set<string>();
      for (const item of [...local, ...remote]) {
        const key = `${normalizeSearchText(item.name)}|${Number(item.lat).toFixed(6)}|${Number(item.lon).toFixed(6)}`;
        if (seen.has(key)) continue;
        seen.add(key);
        merged.push(item);
      }
      setResults(merged.slice(0, 12));
    } catch (_) {
      setResults(local);
    }
    setFetching(false);
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);
    if (!val.trim()) { setResults([]); setOpen(false); return; }
    setOpen(true);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => runSearch(val), 120);
  };

  const pick = (res: any) => {
    onSelect({ lat: res.lat, lon: res.lon, name: res.name, icon: res.icon || "📍", type: res.type });
    onFlyTo?.({ lat: res.lat, lon: res.lon });
    setQuery(""); setResults([]); setOpen(false);
    inputRef.current?.blur();
  };

  const displayValue = isSelected && !open ? "" : query;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, position: "relative", zIndex: 50 }}>
      <div style={{ width: 9, height: 9, borderRadius: 99, background: dotColor, flexShrink: 0, boxShadow: `0 0 0 2px ${dotColor}33` }} />
      <div style={{ flex: 1, position: "relative" }}>
        <input
          ref={inputRef}
          value={displayValue}
          onChange={handleChange}
          onFocus={() => {
            if (isSelected && clearOnFocus) {
              onClear();
              setQuery("");
              setResults([]);
            }
            setOpen(true);
          }}
          onBlur={() => setTimeout(() => setOpen(false), 180)}
          placeholder={isSelected ? "" : placeholder}
          autoComplete="off"
          style={{
            width: "100%", background: "rgba(255,255,255,0.06)", border: `1.5px solid ${open ? dotColor + "55" : "rgba(255,255,255,0.08)"}`,
            borderRadius: 10, padding: "10px 36px 10px 12px", color: isSelected && !open ? "#e2e8f0" : "#d1d5db",
            fontSize: 13, outline: "none", boxSizing: "border-box", transition: "border .2s",
          }}
        />
        {/* Selected badge */}
        {isSelected && !open && (
          <div style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", pointerEvents: "none", display: "flex", alignItems: "center", gap: 5 }}>
            <span style={{ fontSize: 14 }}>{selected.icon || "📍"}</span>
            <span style={{ fontSize: 13, color: "#e2e8f0", fontWeight: 500, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 260 }}>{selected.name}</span>
          </div>
        )}
        {/* Clear / locate buttons */}
        <div style={{ position: "absolute", right: 6, top: "50%", transform: "translateY(-50%)", display: "flex", gap: 2 }}>
          {isSelected && <button onMouseDown={e => { e.preventDefault(); onClear(); setQuery(""); }} style={{ background: "none", border: "none", color: "#6b7280", cursor: "pointer", fontSize: 15, padding: "2px 3px" }}>✕</button>}
          {showLocateBtn && !isSelected && <button onMouseDown={e => { e.preventDefault(); onLocate?.(); }} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 16, padding: "2px 3px" }} title="Use my location">📡</button>}
        </div>

        {/* Dropdown */}
        {open && (results.length > 0 || fetching || query.length >= 1) && (
          <div style={{
            position: "absolute", top: "calc(100% + 5px)", left: 0, right: 0,
            background: "rgba(14,14,22,0.99)", backdropFilter: "blur(20px)",
            border: `1.5px solid ${dotColor}33`, borderRadius: 12,
            boxShadow: "0 16px 56px rgba(0,0,0,0.8)", zIndex: 1000, overflow: "hidden",
          }}>
            {/* Quick-type hint when few chars */}
            {query.length >= 1 && results.length === 0 && !fetching && (
              <div style={{ padding: "12px 16px", color: "#6b7280", fontSize: 12 }}>No buildings found for "{query}"</div>
            )}
            {fetching && results.length === 0 && (
              <div style={{ padding: "12px 16px", color: "#6b7280", fontSize: 12 }}>Searching campus…</div>
            )}
            {results.map((res, i) => (
              <div key={i} onMouseDown={() => pick(res)} style={{
                padding: "11px 16px", display: "flex", alignItems: "center", gap: 12,
                borderBottom: i < results.length - 1 ? "1px solid rgba(255,255,255,0.04)" : "none",
                cursor: "pointer", transition: "background .12s",
              }}
              onMouseEnter={e => (e.currentTarget.style.background = "rgba(255,255,255,0.05)")}
              onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
              >
                <div style={{ width: 34, height: 34, borderRadius: 10, background: `${dotColor}18`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 17, flexShrink: 0 }}>
                  {res.icon || "📍"}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, color: "#e2e8f0", fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    <HighlightMatch text={res.name} query={query} />
                  </div>
                  <div style={{ fontSize: 11, color: "#6b7280", marginTop: 2 }}>{res.type || "Building"}</div>
                </div>
                <div style={{ fontSize: 10, color: "#374151", flexShrink: 0 }}>{res.lat?.toFixed(3)},{res.lon?.toFixed(3)}</div>
              </div>
            ))}

            {/* A–Z browse shortcut when empty */}
            {query.length === 0 && (
              <div style={{ padding: "10px 14px", borderTop: "1px solid rgba(255,255,255,0.04)" }}>
                <div style={{ color: "#4b5563", fontSize: 10, fontWeight: 600, textTransform: "uppercase", marginBottom: 6 }}>Browse A–Z</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                  {"ABCDEFGHIJKLMNOPRSTUVWZ".split("").map(letter => (
                    <button key={letter} onMouseDown={() => { setQuery(letter); runSearch(letter); }}
                      style={{ background: "rgba(255,255,255,0.05)", border: "none", borderRadius: 6, width: 26, height: 26, color: "#9ca3af", fontSize: 11, fontWeight: 700, cursor: "pointer" }}>
                      {letter}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/** Bold-highlights matching substring in result name */
function HighlightMatch({ text, query }: { text: string; query: string }) {
  if (!query) return <>{text}</>;
  const idx = text.toLowerCase().indexOf(query.toLowerCase());
  if (idx === -1) return <>{text}</>;
  return (
    <>
      {text.slice(0, idx)}
      <span style={{ color: "#4f8ef7", fontWeight: 700 }}>{text.slice(idx, idx + query.length)}</span>
      {text.slice(idx + query.length)}
    </>
  );
}

function TabBtn({ active, onClick, icon, label }: { active: boolean; onClick: () => void; icon: string; label: string }) {
  return (
    <button onClick={onClick} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2, padding: "6px 10px", borderRadius: 10, border: "none", background: active ? "rgba(79,142,247,0.18)" : "rgba(255,255,255,0.05)", color: active ? "#4f8ef7" : "#6b7280", cursor: "pointer", fontSize: 10, fontWeight: active ? 700 : 400, transition: "all .2s" }}>
      <span style={{ fontSize: 16 }}>{icon}</span>{label}
    </button>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ color: "#f0f4ff", fontWeight: 700, fontSize: 16 }}>{value}</div>
      <div style={{ color: "#6b7280", fontSize: 10, textTransform: "uppercase", marginTop: 1 }}>{label}</div>
    </div>
  );
}

function Toggle({ on, onChange }: { on: boolean; onChange: (v: boolean) => void }) {
  return (
    <div onClick={() => onChange(!on)} style={{ width: 42, height: 24, borderRadius: 99, background: on ? "#4f8ef7" : "rgba(255,255,255,0.1)", position: "relative", cursor: "pointer", transition: "background .2s" }}>
      <div style={{ position: "absolute", top: 3, left: on ? 21 : 3, width: 18, height: 18, borderRadius: 99, background: "#fff", transition: "left .2s", boxShadow: "0 1px 4px rgba(0,0,0,0.3)" }} />
    </div>
  );
}

function FAB({ icon, title, onClick, active }: { icon: string; title: string; onClick: () => void; active?: boolean }) {
  return (
    <button onClick={onClick} title={title} style={{ width: 48, height: 48, borderRadius: 14, border: "none", background: active ? "rgba(79,142,247,0.22)" : "rgba(18,18,28,0.92)", backdropFilter: "blur(12px)", cursor: "pointer", fontSize: 20, boxShadow: "0 4px 16px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.06)", display: "flex", alignItems: "center", justifyContent: "center", transition: "all .2s" }}>
      {icon}
    </button>
  );
}
