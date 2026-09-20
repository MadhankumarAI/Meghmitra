import { fetchDaily } from "./gz";
import type { BlockMeta, EventKey, Week } from "./store";

export interface ForecastFile {
  issued: string;
  source: string;
  product: string;
  blocks: number;
  events: Record<"onset" | "dry10" | "heavy", { p: number[][]; clim: number[][] }>;
  cmri: number[][];
  /** observed at issue time: 0 confirmed, 1 holding, 2 pending, 3 pending after a false onset */
  onset_status?: number[];
  /** day-of-year of the most recent sowing-grade rain, -1 if none */
  sowing_rain_doy?: number[];
  /** open decision window: 0 none, 1 sowing, 2 seedlings establishing */
  window?: number[];
}

export const ONSET = { CONFIRMED: 0, HOLDING: 1, PENDING: 2, FAILED: 3 } as const;

const cache = new Map<string, Promise<unknown>>();
function getJSON<T>(url: string): Promise<T> {
  if (!cache.has(url)) cache.set(url, fetch(url).then((r) => {
    if (!r.ok) throw new Error(`${url}: ${r.status}`);
    return r.json();
  }));
  return cache.get(url) as Promise<T>;
}

export interface SeasonIndex { year: number; source: string; dates: string[] }

/** geoBoundaries names come in mixed case: some are ALL CAPS. Present them consistently. */
const titleCase = (s: string) =>
  s === s.toUpperCase() && /[A-Z]{2}/.test(s)
    ? s.toLowerCase().replace(/(^|[\s(./-])([a-z])/g, (_, a, b) => a + b.toUpperCase())
    : s;

export const loadBlocks = () =>
  getJSON<BlockMeta[]>("/data/blocks_index.json").then((bs) =>
    bs.map((b) => ({ ...b, name: titleCase(b.name), district: titleCase(b.district) })));
const forecastCache = new Map<string, Promise<ForecastFile>>();
export const loadForecast = (date: string) => {
  if (!forecastCache.has(date)) {
    const p = fetchDaily<ForecastFile>(`/data/forecast/${date}`);
    p.catch(() => forecastCache.delete(date));
    forecastCache.set(date, p);
  }
  return forecastCache.get(date)!;
};
export const loadSeason = (year: number) => getJSON<SeasonIndex>(`/data/forecast/season_${year}.json`);

/**
 * Onset Front class per block (codes match ONSET_FRONT in colors.ts):
 *   0 arrived (confirmed), 1 holding (sowing rain came, no dry break yet),
 *   2..5 = first week in which the cumulative chance of onset reaches 50%,
 *   6 = not expected within four weeks.
 * What has already happened comes from observations (onset_status); only pending
 * blocks use the forecast. Weekly onset probabilities are mutually exclusive
 * ("onset falls in week k"), so the cumulative chance by week k is their running sum.
 */
export function onsetFront(f: ForecastFile): Float32Array {
  const p = f.events.onset.p;
  const st = f.onset_status;
  const out = new Float32Array(f.blocks);
  for (let i = 0; i < f.blocks; i++) {
    const s = st?.[i];
    if (s === ONSET.CONFIRMED || (s === undefined && p[0][i] < 0)) { out[i] = 0; continue; }
    if (s === ONSET.HOLDING) { out[i] = 1; continue; }
    let cum = 0, cls = 6;
    for (let w = 0; w < 4; w++) {
      cum += Math.max(0, p[w][i]) / 100;
      if (cum >= 0.5) { cls = w + 2; break; }
    }
    out[i] = cls;
  }
  return out;
}

/** "14 Jun" from a day-of-year in the forecast's year. */
export function doyLabel(year: number, doy: number): string {
  const d = new Date(year, 0, doy);
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

/** Values for the map: a class code (CMRI, Onset Front) or probability 0..1. */
export function layerValues(f: ForecastFile, event: EventKey, week: Week): Float32Array {
  const w = week - 1;
  if (event === "cmri") return Float32Array.from(f.cmri[w]);
  if (event === "onset") return onsetFront(f);
  return Float32Array.from(f.events[event].p[w], (v) => (v < 0 ? NaN : v / 100));
}
