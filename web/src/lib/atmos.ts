/**
 * Atmosphere frames (src/atmos/frames.py): 850 hPa wind, sea-level pressure, moisture,
 * 2 m temperature on a 0.5 deg grid over 15S-40N, 40-110E, plus diagnostics.
 */
import { fetchDaily, fetchJSON } from "./gz";

export interface Low { lat: number; lon: number; hpa: number; depth: number }
export interface Diag {
  jet_ms: number;            // mean 850 hPa westerly, Arabian Sea 5-15N 55-70E
  trough_lat: number;        // monsoon trough axis latitude, 75-85E
  nw_minus_bay_hpa: number;  // heat-low strength: NW India minus Bay of Bengal pressure
  lows: Low[];
  tcwv_central_mm: number;   // column moisture over central India
}
export interface Frame {
  t: string; source: string;
  lat0: number; lon0: number; d: number; ny: number; nx: number;
  diag: Diag;
  u850: (number | null)[]; v850: (number | null)[]; msl: (number | null)[];
  tcwv: (number | null)[]; t2m: (number | null)[];
}
export interface LiveIndex { run: string; frames: { key: string; t: string; fh: number }[] }

const cache = new Map<string, Promise<Frame>>();
export function loadFrame(key: string) {
  if (!cache.has(key)) {
    const p = fetchDaily<Frame>(`/data/atmos/${key}`);
    p.catch(() => cache.delete(key));
    cache.set(key, p);
  }
  return cache.get(key)!;
}
export const era5Key = (date: string) => `era5_${date}`;
export const loadLiveIndex = () => fetchJSON<LiveIndex>("/data/atmos/live_index.json");
let orog: Promise<{ elev: number[] } | null> | null = null;
export const loadOrography = () =>
  (orog ??= fetchDaily<{ elev: number[] }>("/data/atmos/orography").catch(() => null));

/** Bilinear sample of a frame field at lon/lat; null outside the grid or on missing data. */
export function sample(f: Frame, field: (number | null)[], lon: number, lat: number): number | null {
  const x = (lon - f.lon0) / f.d, y = (f.lat0 - lat) / f.d;           // rows run north to south
  if (x < 0 || y < 0 || x > f.nx - 1 || y > f.ny - 1) return null;
  const x0 = Math.floor(x), y0 = Math.floor(y), x1 = Math.min(x0 + 1, f.nx - 1), y1 = Math.min(y0 + 1, f.ny - 1);
  const fx = x - x0, fy = y - y0;
  const g = (i: number, j: number) => field[i * f.nx + j];
  const a = g(y0, x0), b = g(y0, x1), c = g(y1, x0), e = g(y1, x1);
  if (a == null || b == null || c == null || e == null) return null;
  return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + e * fx) * fy;
}

/** Monsoon trough axis: latitude of lowest land pressure (18-30N) at each longitude 70-90E. */
export function troughAxis(f: Frame, elev: number[] | null): [number, number][] {
  const pts: [number, number][] = [];
  for (let lon = 70; lon <= 90; lon += 1) {
    let best = Infinity, bestLat = NaN;
    for (let lat = 18; lat <= 30; lat += 0.5) {
      const i = Math.round((f.lat0 - lat) / f.d), j = Math.round((lon - f.lon0) / f.d);
      const k = i * f.nx + j;
      if (elev && elev[k] > 600) continue;
      const p = f.msl[k];
      if (p != null && p < best) { best = p; bestLat = lat; }
    }
    if (Number.isFinite(bestLat)) pts.push([lon, bestLat]);
  }
  // light smoothing so the axis reads as a line, not a staircase
  return pts.map((p, k) => {
    const nb = pts.slice(Math.max(0, k - 2), k + 3);
    return [p[0], nb.reduce((s, q) => s + q[1], 0) / nb.length] as [number, number];
  });
}

export interface Heat { max: number; lat: number; lon: number; cells40: number }

/** Hottest surface air over the Indian plains (land below 600 m, 20-32N 66-90E), in °C. */
export function heatOf(f: Frame, elev: number[] | null): Heat | null {
  let best: Heat | null = null, cells40 = 0;
  for (let lat = 20; lat <= 32; lat += f.d) for (let lon = 66; lon <= 90; lon += f.d) {
    const k = Math.round((f.lat0 - lat) / f.d) * f.nx + Math.round((lon - f.lon0) / f.d);
    const t = f.t2m[k], e = elev?.[k];
    if (t == null || e == null || e <= 5 || e > 600) continue;    // land plains only
    if (t >= 40) cells40++;
    if (!best || t > best.max) best = { max: t, lat, lon, cells40: 0 };
  }
  return best && { ...best, cells40 };
}

export type Phase = "active" | "break" | "normal" | "advancing" | "withdrawing";

/** The dashed line of lowest pressure, named by phase (map layer and legend share this). */
export const AXIS = {
  heat: { color: "#ff9f43", label: "Heat low" },          // pre-monsoon: lowest pressure, not yet a trough
  trough: { color: "#ffd166", label: "Monsoon trough" },
};

/** Plain-language reading of a frame, in the terms an IMD forecaster would use. */
export function narrate(d: Diag, coverage: number | null = null, when: string | null = null, heat: Heat | null = null):
  { title: string; points: string[]; phase: Phase } {
  const points: string[] = [];
  // Before the monsoon covers most of India there is no monsoon trough yet: the lowest
  // pressure over the north is the pre-monsoon heat low. `coverage` = share of blocks where
  // monsoon rain has arrived (from our own onset status).
  const advancing = coverage != null && coverage < 0.6;
  const jet = d.jet_ms >= 15 ? "strong" : d.jet_ms >= 10 ? "moderate" : "weak";
  points.push(`The monsoon's low-level jet over the Arabian Sea is ${jet} (${d.jet_ms.toFixed(0)} m/s at 1.5 km). `
    + (jet === "strong" ? "It is pushing plenty of moisture onto the west coast."
       : jet === "weak" ? "Less moisture is reaching India." : "Moisture supply is near normal."));
  const north = d.trough_lat >= 27.5, south = d.trough_lat <= 24;
  const tt = when ? new Date(when) : null;
  const lateSeason = tt ? (tt.getUTCMonth() === 8 && tt.getUTCDate() >= 15) || tt.getUTCMonth() >= 9 : false;
  if (lateSeason) {
    points.push(`The lowest pressure over the plains lies near ${d.trough_lat.toFixed(1)}°N as the monsoon trough weakens.`);
  } else if (advancing) {
    points.push(`The monsoon is still advancing: it has reached about ${Math.round((coverage ?? 0) * 100)}% of India so far. `
      + "The lowest pressure over the north is the pre-monsoon heat low, not yet a monsoon trough.");
  } else {
    points.push(`The monsoon trough lies near ${d.trough_lat.toFixed(1)}°N. `
      + (north ? "It has shifted north towards the Himalayan foothills, the classic sign of a break: central and peninsular India dry out while the hills get heavy rain."
         : south ? "It sits south of its normal position, over central India, which favours widespread rain there (an active phase)."
         : "That is close to its normal position."));
  }
  // Surface heat is what builds the heat low; say so while it matters (before and early in the season)
  if (heat && heat.max >= 38 && !lateSeason) {
    const where = heat.lat >= 24 && heat.lon < 78 ? "northwest India" : heat.lat >= 24 ? "the north Indian plains" : "central India";
    points.push(`Surface heat reaches ${heat.max.toFixed(0)} °C over ${where}`
      + (heat.cells40 >= 20 ? ", with a wide area above 40 °C" : "") + ". "
      + (advancing ? "This heat deepens the heat low that pulls moist monsoon winds inland."
         : "Hot, dry air there keeps rain away from the desert margin."));
  }
  for (const l of d.lows.slice(0, 2)) {
    const where = l.lon < 75 ? (l.lat < 15 ? "the southeast Arabian Sea" : "the Arabian Sea")
      : l.lon > 85 && l.lat < 24 ? "the Bay of Bengal" : "central India";
    const strength = l.depth >= 15 ? "a cyclonic storm" : l.depth >= 6 ? "a depression" : "a low-pressure area";
    points.push(`${strength[0].toUpperCase() + strength.slice(1)} over ${where} (${l.hpa.toFixed(0)} hPa, ${l.depth.toFixed(0)} hPa below its surroundings) `
      + (where === "the Bay of Bengal" ? "is pulling monsoon rain inland along its track."
         : where.includes("Arabian") && l.depth >= 15 ? "is drawing moisture away from the Indian mainland."
         : "is organising rain around it."));
  }
  points.push(`Moisture over central India: ${d.tcwv_central_mm.toFixed(0)} mm of water in the air column `
    + (d.tcwv_central_mm >= 55 ? "(very moist)." : d.tcwv_central_mm >= 45 ? "(moist)." : "(on the dry side)."));
  // From mid-September the monsoon retreats from the northwest; a weak jet then is withdrawal,
  // not a break.
  const t = when ? new Date(when) : null;
  const late = t ? (t.getUTCMonth() === 8 && t.getUTCDate() >= 15) || t.getUTCMonth() >= 9 : false;
  if (late) points.unshift("It is the withdrawal season: the monsoon retreats from northwest India from mid-September, and the jet weakens as it goes.");
  const phase = late && jet !== "strong" ? "withdrawing" : advancing ? "advancing"
    : north && jet !== "strong" ? "break"
    : (south || jet === "strong") && !north ? "active" : "normal";
  const title = { advancing: "Monsoon advancing", break: "Break conditions", active: "Active monsoon",
    normal: "Normal monsoon flow", withdrawing: "Monsoon withdrawing" }[phase];
  return { title, points, phase };
}
