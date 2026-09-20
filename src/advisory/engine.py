"""Advisory engine: turns block probabilities into crop-specific, templated advice.

Rules follow ICAR-CRIDA district contingency-plan logic (what to do when the
monsoon is 2 / 4 / 6 weeks late) plus crop-stage rules for the false-onset trap.
Advice is a template id + parameters, never free text: the delivery service
renders it per language from reviewed templates (docs/DELIVERY_BRIEF.md).

Which crops a district grows, and what to sow when the monsoon is late, come from that
district's own ICAR-CRIDA contingency plan (advisory/sources.py, docs/ADVICE_SOURCES.md),
with the page cited on every advisory. CROPS and STATE_CROPS below are the FALLBACK for
districts whose plan we could not read; advisories from the fallback say so.
"""
from __future__ import annotations
import numpy as np

from advisory import sources

# drought tolerance: how much a 10+ day dry spell hurts at establishment
CROPS = {
    "rice":      dict(tolerance="low",    ladder=["short-duration variety or direct-seeded rice",
                                                  "short-duration rice or maize", "black gram or fodder crops"]),
    "soybean":   dict(tolerance="low",    ladder=["short-duration soybean variety",
                                                  "pigeonpea or black gram", "horse gram or fodder"]),
    "maize":     dict(tolerance="medium", ladder=["short-duration maize hybrid",
                                                  "green gram or black gram", "fodder maize or sorghum"]),
    "cotton":    dict(tolerance="medium", ladder=["Bt hybrid with closer spacing",
                                                  "pigeonpea with a millet intercrop", "sunflower or horse gram"]),
    "groundnut": dict(tolerance="medium", ladder=["bunch-type groundnut variety",
                                                  "sunflower or pulses", "horse gram or cowpea"]),
    "pigeonpea": dict(tolerance="high",   ladder=["short-duration pigeonpea",
                                                  "pigeonpea intercropped with millets", "horse gram"]),
    "ragi":      dict(tolerance="high",   ladder=["continue; transplanting can be later",
                                                  "short-duration ragi", "horse gram"]),
    "bajra":     dict(tolerance="high",   ladder=["continue sowing bajra",
                                                  "short-duration bajra or cluster bean", "fodder crops"]),
    "jowar":     dict(tolerance="high",   ladder=["continue sowing jowar",
                                                  "short-duration jowar", "fodder sorghum"]),
}

STATE_CROPS = {
    "Karnataka": ["ragi", "maize", "pigeonpea"], "Maharashtra": ["soybean", "cotton", "pigeonpea"],
    "Madhya Pradesh": ["soybean", "maize", "rice"], "Rajasthan": ["bajra", "groundnut", "jowar"],
    "Gujarat": ["cotton", "groundnut", "bajra"], "Telangana": ["cotton", "rice", "maize"],
    "Andhra Pradesh": ["rice", "cotton", "groundnut"], "Uttar Pradesh": ["rice", "maize", "bajra"],
    "Bihar": ["rice", "maize"], "Jharkhand": ["rice", "maize"], "Chhattisgarh": ["rice", "maize"],
    "Odisha": ["rice", "maize"], "West Bengal": ["rice", "jowar"], "Punjab": ["rice", "cotton"],
    "Haryana": ["rice", "cotton", "bajra"], "Assam": ["rice"], "Kerala": ["rice"],
    "Tamil Nadu": ["rice", "groundnut"], "Himachal Pradesh": ["maize", "rice"],
    "Uttarakhand": ["rice", "maize"], "Jammu and Kashmir": ["maize", "rice"],
}
DEFAULT_CROPS = ["rice", "maize"]

# template ids: the contract in docs/DELIVERY_BRIEF.md
DELAY_SOWING, SOW_NOW, PREPARE_IRRIGATION = "DELAY_SOWING", "SOW_NOW", "PREPARE_IRRIGATION"
SWITCH_CROP, HEAVY_RAIN_PROTECT = "SWITCH_CROP", "HEAVY_RAIN_PROTECT"
DRY_SPELL_CONSERVE_MOISTURE, ALL_CLEAR = "DRY_SPELL_CONSERVE_MOISTURE", "ALL_CLEAR"

CONFIRMED, HOLDING, PENDING, FAILED = 0, 1, 2, 3        # onset status (export)
MAX_LATE = 56                                           # days past usual onset: sowing advice stops


def crops_for(state: str, district: str = "") -> list[str]:
    """The crops to advise on here: what the district's plan actually talks about, else the
    indicative state list. Only crops the engine has stage rules for are kept."""
    if district:
        known = [c for c in sources.district_crops(district, state, limit=8) if c in CROPS]
        if known:
            return known[:3]
    for k, v in STATE_CROPS.items():
        if k.lower() in state.lower():
            return v
    return DEFAULT_CROPS


def cite(m: dict) -> dict:
    """The citation carried on a plan-backed advisory, shown in the console and the record."""
    plan = f"{m['district']} district agriculture contingency plan (ICAR-CRIDA)"
    if m.get("nearby"):                      # this district has no plan of its own (created later)
        plan += f" - nearest plan to {m['for_district']}"
    return {"plan": plan, "page": m["page"], "url": m["source"], "condition": m["condition"],
            "nearby": bool(m.get("nearby"))}


def measure_text(v: str) -> str:
    """Plan cells often say "-" or "Normal": that is not an instruction, so drop it."""
    return "" if (v or "").strip().lower() in ("", "-", "--", "normal", "no change", "na", "n/a") else v.strip()


def support(place, crop: str, kind: str, weeks: int | None = None) -> dict:
    """The district plan's own words for this situation, ready to merge into an advisory's
    params: the agronomic measure it prescribes, and the citation. Empty when no plan covers it."""
    if not place or not place[0]:
        return {}
    m = sources.measure(place[0], crop, kind, weeks, place[1])
    if not m:
        return {}
    out = {"source": cite(m)}
    if measure_text(m["agronomy"]):
        out["agronomy"] = m["agronomy"][:200]
    if measure_text(m["change"]):
        out["plan_says"] = m["change"][:300]
    return out


def advise(p, c, status, doy, usual_onset, crop, wait_until, place=("", "")):
    """One block, one crop. p/c: {event: [4 weekly probabilities 0..1]} (NaN allowed).

    wait_until: date string for "wait until the end of week 2" (computed once per day).
    place: (district, state) - used to look the advice up in that district's contingency plan.
    Returns (template_id, tier, params) or None when no action is needed beyond the map.
    tier: 2 warning, 3 alert. Only rules with an actionable instruction fire.
    """
    nz = lambda x: 0.0 if not np.isfinite(x) else float(x)
    dry, dry_c = [nz(v) for v in p["dry10"]], [nz(v) for v in c["dry10"]]
    hv, hv_c = [nz(v) for v in p["heavy"]], [nz(v) for v in c["heavy"]]
    on = [nz(v) for v in p["onset"]]
    tol = CROPS[crop]["tolerance"]

    # 1. heavy rain soon: no crop stage required
    for k in (0, 1):
        if hv[k] >= 0.3 and hv[k] >= 3 * max(hv_c[k], 0.01):
            return HEAVY_RAIN_PROTECT, 3, dict(event="heavy_rain", lead_week=k + 1,
                                               p_event=round(hv[k], 2), p_clim=round(hv_c[k], 2),
                                               **support(place, crop, sources.WET))

    # 2. seedlings establishing after sowing rain, and a dry spell is coming: the false-onset trap
    if status == HOLDING:
        for k in (0, 1):
            if dry[k] >= 0.5 and dry[k] - dry_c[k] >= 0.12:
                tid = PREPARE_IRRIGATION if tol == "low" else DRY_SPELL_CONSERVE_MOISTURE
                return tid, 3, dict(event="dry_spell_10d", lead_week=k + 1,
                                    p_event=round(dry[k], 2), p_clim=round(dry_c[k], 2), crop_tolerance=tol,
                                    **support(place, crop, sources.AFTER_SOWING))
        return None

    # 3. not yet sown (no sowing rain, or it failed)
    if status in (PENDING, FAILED) and usual_onset < 400:
        late = doy - usual_onset
        # CRIDA contingency plans cover delays up to ~6 weeks; past 8 the kharif sowing window
        # has closed (and a block this "late" is usually irrigated or already sown): no advice.
        if late >= MAX_LATE:
            return None
        soon = on[0] + on[1]                          # onset within 2 weeks (exclusive weeks: sum)
        if late >= 14 and soon < 0.5:
            level = 0 if late < 28 else (1 if late < 42 else 2)
            weeks = int(late // 7)
            alt, m = sources.alternative_crop(place[0], crop, weeks, place[1]) if place[0] else (None, None)
            if alt:                                   # the district plan names a crop to sow instead
                return SWITCH_CROP, 2, dict(delay_weeks=weeks, alternative=alt,
                                            plan_says=measure_text(m["change"])[:300],
                                            agronomy=measure_text(m["agronomy"])[:200], source=cite(m))
            if m:      # a plan exists but names no single crop to switch to: wait, and show the
                       # officer what it does say - "no change" is itself the plan's answer
                return DELAY_SOWING, 2, dict(
                    late_monsoon=True, wait_until=wait_until, delay_weeks=weeks,
                    plan_says=measure_text(m["change"])[:300], plan_no_change=not measure_text(m["change"]),
                    agronomy=measure_text(m["agronomy"])[:200], source=cite(m), resow=False)
            return SWITCH_CROP, 2, dict(delay_weeks=weeks, ladder_level=level,
                                        variety_advice=CROPS[crop]["ladder"][level], indicative=True)
        # Around the usual sowing date farmers are ready to sow on the first good shower.
        # A likely dry spell means "don't sow on it yet". (Requiring "onset likely AND a
        # dry spell" would never fire: a true onset is, by definition, rain that holds.)
        in_window = -7 <= late < 14
        k = int(np.argmax(dry[:2]))
        if in_window and dry[k] >= 0.5 and dry[k] - dry_c[k] >= 0.10:
            return DELAY_SOWING, 2 if status == PENDING else 3, dict(
                event="dry_spell_10d", lead_week=k + 1, wait_until=wait_until,
                p_event=round(dry[k], 2), p_clim=round(dry_c[k], 2), resow=status == FAILED,
                **support(place, crop, sources.DELAYED, max(0, int(late // 7))))
        if in_window and soon >= 0.35 and dry[1] <= dry_c[1] + 0.02:
            return SOW_NOW, 2, dict(p_onset=round(soon, 2), lead_week=2)
        return None

    # 4. established crop, dry spell coming: moisture conservation
    if status == CONFIRMED:
        for k in (0, 1):
            if dry[k] >= 0.5 and dry[k] - dry_c[k] >= 0.12:
                return DRY_SPELL_CONSERVE_MOISTURE, 2, dict(event="dry_spell_10d", lead_week=k + 1,
                                                            p_event=round(dry[k], 2), p_clim=round(dry_c[k], 2),
                                                            crop_tolerance=tol,
                                                            **support(place, crop, sources.MIDSEASON))
    return None
