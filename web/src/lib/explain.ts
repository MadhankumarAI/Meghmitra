/**
 * Why the model said what it said (src/export/explain_json.py): for each block, the exact
 * week-1 contribution of six drivers to the forecast, in log-odds (tree SHAP from the very
 * model that issued it). Starting from the block's baseline and adding the drivers lands
 * exactly on the published probability.
 */
import { fetchDaily } from "./gz";

export type Driver = "normal" | "recent" | "progress" | "around" | "mjo" | "enso" | "iod";
export type ExplainEvent = "onset" | "dry10" | "heavy";
export interface ExplainFile {
  issued: string; model: string; scale: number; na: number; week: number; groups: Driver[];
  events: Record<ExplainEvent, Record<Driver, number[]>>;
  raw: { r7: number[]; r30: number[]; dry_run: number[]; r7_400km: number[]; front_400km: number[] };
  planet: { mjo_amp: number | null; mjo_phase: number | null; nino34: number | null; dmi?: number | null };
}

const cache = new Map<string, Promise<ExplainFile | null>>();
export function loadExplain(date: string) {
  if (!cache.has(date)) cache.set(date, fetchDaily<ExplainFile>(`/data/explain/${date}`).catch(() => null));
  return cache.get(date)!;
}

export const DRIVERS: Record<Exclude<Driver, "normal">, { label: string; short: string }> = {
  recent: { label: "Rain here lately", short: "Recent rain" },
  around: { label: "Rain around the block", short: "Nearby rain" },
  progress: { label: "Monsoon progress here", short: "Onset progress" },
  mjo: { label: "Madden–Julian Oscillation", short: "MJO" },
  enso: { label: "El Niño / La Niña", short: "ENSO" },
  iod: { label: "Indian Ocean Dipole", short: "IOD" },
};

const sigmoid = (x: number) => 1 / (1 + Math.exp(-x));

// Wheeler–Hendon phases: where the MJO's rain-making region is
const MJO_WHERE = ["", "over Africa", "over the Indian Ocean", "over the Indian Ocean",
  "over the Maritime Continent", "over the Maritime Continent", "over the West Pacific",
  "over the West Pacific", "over the Americas"];

const ONSET_STATUS = [
  "Monsoon onset confirmed here",
  "Sowing rains came; seedlings establishing",
  "Monsoon rains haven’t arrived here yet",
  "Sowing rains came, then failed (false onset)",
];

export interface Step { driver: Exclude<Driver, "normal">; delta: number; from: number; to: number; evidence: string }
export interface Explanation { start: number; end: number; steps: Step[]; model: string }

/** Baseline, then drivers largest first; each step's from/to are probabilities (0–1). */
export function explain(f: ExplainFile, ev: ExplainEvent, i: number, onsetStatus?: number): Explanation | null {
  const g = f.events[ev];
  if (!g || g.normal[i] === f.na) return null;
  const s = f.scale;
  const drivers = (Object.keys(DRIVERS) as Exclude<Driver, "normal">[])
    .filter((d) => f.groups.includes(d) && g[d])            // a driver the model didn't use isn't published
    .map((d) => ({ d, v: g[d][i] / s }))
    .sort((a, b) => Math.abs(b.v) - Math.abs(a.v));
  let logit = g.normal[i] / s;
  const start = sigmoid(logit);
  const steps: Step[] = drivers.map(({ d, v }) => {
    const from = sigmoid(logit);
    logit += v;
    return { driver: d, delta: v, from, to: sigmoid(logit), evidence: evidence(f, d, i, onsetStatus) };
  });
  return { start, end: sigmoid(logit), steps, model: f.model };
}

function evidence(f: ExplainFile, d: Driver, i: number, onsetStatus?: number): string {
  const r = f.raw, p = f.planet;
  switch (d) {
    case "recent": {
      const dry = r.dry_run[i] >= 3 ? `; ${r.dry_run[i]} dry days in a row` : "";
      return `${r.r7[i]} mm in the last 7 days, ${r.r30[i]} mm in 30${dry}`;
    }
    case "around":
      return `${r.r7_400km[i]} mm fell within 400 km last week; monsoon rain has begun in ${r.front_400km[i]}% of nearby blocks`;
    case "progress":
      return onsetStatus !== undefined && ONSET_STATUS[onsetStatus] ? ONSET_STATUS[onsetStatus] : "Onset status from rainfall so far";
    case "mjo":
      if (p.mjo_amp === null || p.mjo_phase === null) return "MJO index not available";
      return p.mjo_amp < 1
        ? `Weak this week (strength ${p.mjo_amp.toFixed(1)})`
        : `Phase ${p.mjo_phase}, ${MJO_WHERE[p.mjo_phase]} (strength ${p.mjo_amp.toFixed(1)})`;
    case "enso":
      if (p.nino34 === null) return "Niño 3.4 not available";
      return `Niño 3.4 at ${p.nino34 > 0 ? "+" : ""}${p.nino34.toFixed(1)} °C: ${p.nino34 >= 0.5 ? "El Niño" : p.nino34 <= -0.5 ? "La Niña" : "neutral"}`;
    case "iod":
      if (p.dmi === null || p.dmi === undefined) return "Dipole Mode Index not available";
      return `Dipole Mode Index ${p.dmi > 0 ? "+" : ""}${p.dmi.toFixed(2)} °C: `
        + `${p.dmi >= 0.4 ? "positive IOD, which usually helps the monsoon" : p.dmi <= -0.4 ? "negative IOD, which usually weakens it" : "neutral"}`;
    default:
      return "";
  }
}
