/**
 * Colour ramps for the map. Probabilities are encoded as *departure from normal*
 * where possible: a block that is 40% likely to go dry is alarming in Kerala and
 * unremarkable in the Thar. Ramps are colour-blind safe (no red/green pairs).
 */
import type { ExpressionSpecification } from "maplibre-gl";

export const CMRI = [
  { key: "normal", label: "Normal", color: "#3d9a64", note: "No signal at any level" },
  { key: "watch", label: "Watch", color: "#e5c14a", note: "Risk tilting above normal" },
  { key: "warning", label: "Warning", color: "#f08c3a", note: "Local forecast confirms risk" },
  { key: "alert", label: "Alert", color: "#e03e3e", note: "Act now: seedlings at risk" },
] as const;

/**
 * Blocks whose main rainy season isn't the southwest monsoon (Jun–Sep under 40% of
 * annual rain). Named by the season that actually dominates, not greyed out as "n/a".
 */
export const REGIMES = {
  [-1]: {
    label: "Northeast-monsoon regime",
    short: "Main rains Oct–Dec",
    color: "#27364a",
    detail: "Most rain here falls in the northeast monsoon (October–December), not June–September. "
      + "The southwest-monsoon outlook doesn’t apply; a northeast-monsoon module is the next step.",
  },
  [-2]: {
    label: "Winter-precipitation regime",
    short: "Main precipitation in winter",
    color: "#1f2a3a",
    detail: "Most precipitation here falls in winter and spring (western disturbances, snow). "
      + "Farming depends on snow- and glacier-melt, so no southwest-monsoon outlook is issued.",
  },
} as const;
export type RegimeCode = keyof typeof REGIMES;
export const isRegime = (cls: number): cls is RegimeCode => cls === -1 || cls === -2;

/** Sequential ramps as [probability, colour] stops. */
export const RAMPS: Record<"onset" | "dry10" | "heavy", [number, string][]> = {
  // dry: sand -> burnt orange -> deep earth
  // low end is a deliberate calm slate-teal, distinct from "no data" (#0f1726)
  dry10: [
    [0.0, "#1d3340"],
    [0.15, "#3b3a2c"],
    [0.3, "#7a5520"],
    [0.45, "#b86f1c"],
    [0.6, "#e08a24"],
    [0.75, "#f4b04d"],
    [0.9, "#ffe0a0"],
  ],
  // heavy rain: deep navy -> blue -> violet
  heavy: [
    [0.0, "#1a2436"],
    [0.05, "#1c2d52"],
    [0.1, "#23427f"],
    [0.2, "#2f63b8"],
    [0.3, "#5a7fe0"],
    [0.45, "#9b7ff0"],
    [0.6, "#d2b4ff"],
  ],
  // onset: dark -> teal -> fresh green
  onset: [
    [0.0, "#1a2733"],
    [0.1, "#15393a"],
    [0.2, "#16594f"],
    [0.35, "#1f8065"],
    [0.5, "#35a87a"],
    [0.7, "#7fd49a"],
    [0.9, "#d4f5c8"],
  ],
};

/** MapLibre expression colouring by feature-state `key` (0..1), grey when absent. */
export function rampExpression(stops: [number, string][], key = "p"): ExpressionSpecification {
  const interp: unknown[] = ["interpolate", ["linear"], ["feature-state", key]];
  for (const [v, c] of stops) interp.push(v, c);
  return ["case", ["==", ["feature-state", key], null], "#0f1726", interp] as unknown as ExpressionSpecification;
}

export function cmriExpression(key = "c"): ExpressionSpecification {
  return [
    "match",
    ["feature-state", key],
    -2, REGIMES[-2].color,
    -1, REGIMES[-1].color,
    0, CMRI[0].color,
    1, CMRI[1].color,
    2, CMRI[2].color,
    3, CMRI[3].color,
    "#0f1726",
  ] as ExpressionSpecification;
}

/**
 * Onset Front classes: the probabilistic, block-scale descendant of IMD's
 * "Northern Limit of Monsoon". Arrived is a distinct hue (water); pending blocks
 * run bright (imminent) to dim (later), so the front reads as a moving edge.
 */
export const ONSET_FRONT = [
  { code: 0, label: "Arrived", note: "Onset confirmed (held 40 days)", color: "#2f74b5" },
  { code: 1, label: "Holding", note: "Sowing rain came; no dry break yet", color: "#79aee3" },
  { code: 2, label: "Week 1", note: "Expected within 7 days", color: "#d7f26b" },
  { code: 3, label: "Week 2", note: "Expected in 8–14 days", color: "#93d36f" },
  { code: 4, label: "Week 3", note: "Expected in 15–21 days", color: "#5aa982" },
  { code: 5, label: "Week 4", note: "Expected in 22–28 days", color: "#3b7a74" },
  { code: 6, label: "Later", note: "Not expected within 4 weeks", color: "#233340" },
] as const;

export function onsetFrontExpression(key = "c"): ExpressionSpecification {
  const m: unknown[] = ["match", ["feature-state", key]];
  for (const c of ONSET_FRONT) m.push(c.code, c.color);
  m.push("#0f1726");
  return m as unknown as ExpressionSpecification;
}

/** "7 in 10" style natural frequency, the format farmers read most reliably. */
export function inTen(p: number): string {
  const n = Math.round(p * 10);
  if (n <= 0) return "less than 1 in 10";
  if (n >= 10) return "almost certain";
  return `${n} in 10`;
}
