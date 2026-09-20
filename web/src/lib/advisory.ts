/**
 * Advisory display text. The engine (src/advisory/engine.py) emits template ids +
 * parameters; this is the English rendering for the officer console. Farmer-facing
 * rendering in Indian languages lives in the delivery service, from reviewed templates.
 */
import { fetchDaily } from "./gz";

export type Advice = [crop: string, template: string, tier: number, params: Record<string, unknown>];

/** Where a plan-backed advisory came from (src/advisory/sources.py). */
export interface Citation { plan: string; page: number; url: string; condition: string }
export const citation = (p: Record<string, unknown>) => (p.source as Citation | undefined) ?? null;
export interface AdvisoryFile { issued: string; advisories: Record<string, Advice[]> }

const cache = new Map<string, Promise<AdvisoryFile | null>>();
export function loadAdvisory(date: string) {
  if (!cache.has(date)) {
    cache.set(date, fetchDaily<AdvisoryFile>(`/data/advisory/${date}`).catch(() => null));
  }
  return cache.get(date)!;
}

const CROP = (c: string) => c.charAt(0).toUpperCase() + c.slice(1);
const inTen = (p: unknown) => `${Math.round(Number(p) * 10)} in 10`;
const date = (d: unknown) =>
  new Date(String(d) + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" });

/** The district plan's own measure, appended to our sentence when the plan gave one. */
const planAdds = (p: Record<string, unknown>) =>
  p.agronomy && String(p.agronomy).toLowerCase() !== "no change" ? ` Plan for this district: ${p.agronomy}` : "";

export function renderAdvice([crop, tid, , p]: Advice): { title: string; body: string } {
  switch (tid) {
    case "DELAY_SOWING":
      if (p.late_monsoon)                             // late monsoon, plan names no single crop
        return {
          title: `${CROP(crop)}: monsoon ${p.delay_weeks} weeks late`,
          body: `Onset isn’t expected within two weeks. `
            + (p.plan_no_change
              ? `The district plan keeps this crop at this delay: don’t switch, sow after ${date(p.wait_until)}.`
              : `The district plan names no single replacement crop, so keep seed ready and sow after `
                + `${date(p.wait_until)}. Plan: “${String(p.plan_says ?? "").slice(0, 160)}”.`)
            + (p.agronomy && p.agronomy !== "No change" ? ` ${p.agronomy}` : ""),
        };
      return {
        title: p.resow ? `${CROP(crop)}: don’t re-sow yet` : `${CROP(crop)}: wait to sow`,
        body: `${inTen(p.p_event)} chance of a 10+ day dry spell in week ${p.lead_week} (usually ${inTen(p.p_clim)}). `
          + `Don’t sow on the first showers; wait until after ${date(p.wait_until)} or until the soil is wet to a hand’s depth.`
          + planAdds(p),
      };
    case "SOW_NOW":
      return {
        title: `${CROP(crop)}: sow on the coming rain`,
        body: `Onset is likely within two weeks (${inTen(p.p_onset)}) and no unusual dry spell is expected after it.`,
      };
    case "SWITCH_CROP": {
      // the district plan names the crop; without a plan we fall back to an indicative ladder
      const alt = p.alternative ? CROP(String(p.alternative)) : String(p.variety_advice ?? "");
      return {
        title: `${CROP(crop)}: monsoon ${p.delay_weeks} weeks late`,
        body: `Onset isn’t expected within two weeks. ${p.alternative ? `Sow ${alt} instead` : `Contingency: ${alt}`}`
          + `${p.agronomy && p.agronomy !== "No change" ? `. ${p.agronomy}` : "."}`,
      };
    }
    case "PREPARE_IRRIGATION":
      return {
        title: `${CROP(crop)}: seedlings at risk, arrange water`,
        body: `${inTen(p.p_event)} chance of a 10+ day dry spell in week ${p.lead_week} (usually ${inTen(p.p_clim)}). `
          + `This crop tolerates dry spells poorly: plan one protective irrigation and mulch.` + planAdds(p),
      };
    case "DRY_SPELL_CONSERVE_MOISTURE":
      return {
        title: `${CROP(crop)}: conserve soil moisture`,
        body: `${inTen(p.p_event)} chance of a 10+ day dry spell in week ${p.lead_week} (usually ${inTen(p.p_clim)}). `
          + `Mulch, hoe lightly to break the soil crust, and hold off on fertiliser until it rains.` + planAdds(p),
      };
    case "HEAVY_RAIN_PROTECT":
      return {
        title: `${CROP(crop)}: heavy rain likely`,
        body: `${inTen(p.p_event)} chance of a day with 64.5 mm or more in week ${p.lead_week} (usually ${inTen(p.p_clim)}). `
          + `Clear field drains and postpone spraying and fertiliser.` + planAdds(p),
      };
    default:
      return { title: `${CROP(crop)}`, body: tid };
  }
}
