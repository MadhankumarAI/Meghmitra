import type { ExpressionSpecification } from "maplibre-gl";

export type MetricEvent = "onset" | "dry10" | "dry7" | "heavy";

export interface LeadScore {
  week: number; bss: number; auc: number; auc_clim: number;
  brier: number; brier_clim: number; base_rate: number; n: number;
}
export interface EventScore {
  leads: LeadScore[];
  reliability: { forecast: number[]; observed: number[]; count: number[] };
  reliability_error: number;
}
export interface Metrics {
  protocol: string;
  eval_years: [number, number];
  models: Record<string, Record<MetricEvent, EventScore>>;
  skill_map: Record<string, Record<MetricEvent, number[][]>>;
}

export const loadMetrics = () =>
  fetch("/data/metrics.json").then((r) => {
    if (!r.ok) throw new Error(`metrics.json: ${r.status}`);
    return r.json() as Promise<Metrics>;
  });

export const EVENT_LABEL: Record<MetricEvent, string> = {
  dry10: "10+ day dry spell",
  dry7: "7+ day dry spell",
  onset: "Monsoon onset",
  heavy: "Heavy-rain day",
};

/** Published model and the experiment it was compared against. */
export const PUBLISHED = "fast";
export const MODEL_LABEL: Record<string, string> = {
  fast: "v1 · gradient boosting (published)",
  fast_v2: "v2 · teleconnection signatures (not adopted)",
};

/** Skill map: BSS per block. Negative = worse than climatology (brown), positive = teal. */
export function bssExpression(key: string): ExpressionSpecification {
  return [
    "case", ["==", ["feature-state", key], null], "#0f1726",
    ["interpolate", ["linear"], ["feature-state", key],
      -0.2, "#7a4a1f", -0.05, "#3a3028", 0, "#1c2533", 0.05, "#1f4a50", 0.15, "#2a8a86", 0.3, "#6fd6c4"],
  ] as unknown as ExpressionSpecification;
}
