"""Grounded advice: what the district's own CRIDA contingency plan says.

`crida_plans.py` parses the published plans; this turns them into a lookup the advisory engine
can use: which crops that district actually grows, and what the plan prescribes for a given
situation (monsoon late by N weeks, dry spell after sowing, mid-season break, heavy rain).

Retrieval is deterministic - district -> crop -> situation - and every hit carries the page and
URL of the plan it came from, so the console and the record can cite it. Nothing is generated.

  python sources.py coverage      how many blocks are covered by a plan
  python sources.py show DISTRICT CROP
"""
from __future__ import annotations
import sys, re, json, difflib
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import PROCESSED

PLANS = PROCESSED / "crida_plans.json"

# plan wording -> the crop ids the rest of the system uses (engine, delivery service glossary)
CROP_WORDS = {
    "paddy": "rice", "rice": "rice", "transplanted paddy": "rice", "drilled paddy": "rice",
    "redgram": "pigeonpea", "red gram": "pigeonpea", "pigeon pea": "pigeonpea", "pigeonpea": "pigeonpea",
    "tur": "pigeonpea", "arhar": "pigeonpea",
    "finger millet": "ragi", "ragi": "ragi",
    "sorghum": "jowar", "jowar": "jowar", "rabi sorghum": "jowar",
    "pearl millet": "bajra", "bajra": "bajra",
    "greengram": "greengram", "green gram": "greengram", "moong": "greengram",
    "blackgram": "blackgram", "black gram": "blackgram", "urd": "blackgram",
    "horsegram": "horsegram", "horse gram": "horsegram",
    "groundnut": "groundnut", "ground nut": "groundnut",
    "sunflower": "sunflower", "soybean": "soybean", "soyabean": "soybean",
    "cotton": "cotton", "maize": "maize", "castor": "castor", "safflower": "safflower",
    "sesamum": "sesamum", "sesame": "sesamum", "chickpea": "chickpea", "bengalgram": "chickpea",
    "bengal gram": "chickpea", "wheat": "wheat", "chilli": "chilli", "chillies": "chilli",
    "onion": "onion", "field bean": "fieldbean", "cowpea": "cowpea", "niger": "niger",
    "sugarcane": "sugarcane", "tomato": "tomato", "potato": "potato", "mustard": "mustard",
}
NOT_A_CROP = re.compile(r"cropping system|normal crop|during the event|stage|management|drain|crop$|kharif|rabi", re.I)

# plan condition -> the situation our engine reasons about
DELAYED, AFTER_SOWING, MIDSEASON, TERMINAL, WET = "delayed_onset", "dry_after_sowing", "mid_season", "terminal", "wet"


def situation(condition: str) -> str | None:
    c = condition.lower()
    if "delay" in c or "delayed onset" in c or "early season drought" in c:
        return DELAYED
    if "normal onset" in c and "dry" in c:
        return AFTER_SOWING
    if "mid season" in c or "mid-season" in c:
        return MIDSEASON
    if "terminal" in c:
        return TERMINAL
    if re.search(r"flood|unusual rain|heavy rain|excess (rain|moisture)|water logg", c):
        return WET
    return None


def crop_ids(crop_system: str) -> list[str]:
    """'Groundnut + Pigeon pea' -> ['groundnut', 'pigeonpea']; unknown words are dropped."""
    out: list[str] = []
    for part in re.split(r"[+/,]|\s-\s|\band\b", crop_system or ""):
        t = re.sub(r"\(.*?\)", " ", part).strip().lower()
        t = re.sub(r"\b(hy\.?|hybrid|sole|crop|system|bt|desi|local|improved|short duration)\b", " ", t)
        t = re.sub(r"\s+", " ", t).strip(" .-")
        if not t or NOT_A_CROP.search(t):
            continue
        cid = CROP_WORDS.get(t)
        if cid and cid not in out:
            out.append(cid)
    return out


def norm(s: str) -> str:
    s = re.sub(r"\b(district|dist\.?|rural|urban)\b", " ", (s or "").lower())
    return re.sub(r"[^a-z]", "", s)


@lru_cache(maxsize=1)
def _plans() -> dict:
    return json.loads(PLANS.read_text(encoding="utf-8")) if PLANS.exists() else {}


@lru_cache(maxsize=1)
def _by_district() -> dict[str, dict]:
    """Flat {normalised district name: plan}, with the state kept for disambiguation."""
    out: dict[str, dict] = {}
    for state, districts in _plans().items():
        for name, plan in districts.items():
            out.setdefault(norm(name), {"state": state, "district": name, **plan})
    return out


@lru_cache(maxsize=1)
def _centroids() -> dict[str, list[tuple[str, float, float]]]:
    """Centre of each of our districts, by state, so an unplanned district can borrow its
    neighbour's plan. Many districts were created after these plans were written (2011-12)."""
    import pandas as pd
    from config import PROCESSED as _P
    b = pd.read_parquet(_P / "blocks.parquet")
    g = b.groupby(["state", "district"])[["lat", "lon"]].mean().reset_index()
    out: dict[str, list[tuple[str, float, float]]] = {}
    for st, di, lat, lon in g[["state", "district", "lat", "lon"]].itertuples(index=False):
        out.setdefault(str(st), []).append((str(di), float(lat), float(lon)))
    return out


def _exact(district: str) -> dict | None:
    idx = _by_district()
    key = norm(district)
    if key in idx:
        return idx[key]
    near = difflib.get_close_matches(key, list(idx), n=1, cutoff=0.86)
    return idx[near[0]] if near else None


def find(district: str, state: str = "", allow_nearby: bool = True) -> dict | None:
    """The plan for this district. Close spellings match; failing that, and only within the same
    state, the nearest district that does have a plan - flagged `nearby` so the advisory says so."""
    hit = _exact(district)
    if hit or not allow_nearby or not state:
        return hit
    here = next(((la, lo) for d, la, lo in _centroids().get(state, []) if norm(d) == norm(district)), None)
    if not here:
        return None
    best, best_d2 = None, 9e9
    for d, la, lo in _centroids().get(state, []):
        plan = _exact(d)
        if not plan:
            continue
        d2 = (la - here[0]) ** 2 + ((lo - here[1]) * 0.94) ** 2       # ~equal-area at Indian latitudes
        if d2 < best_d2:
            best, best_d2 = plan, d2
    if best is None or best_d2 > 4.0:                                  # no plan within ~2 degrees
        return None
    return {**best, "nearby": True, "for_district": district}


def district_crops(district: str, state: str = "", limit: int = 6) -> list[str]:
    """The crops this district's plan actually talks about, most mentioned first."""
    plan = find(district, state)
    if not plan:
        return []
    counts: dict[str, int] = {}
    for r in plan["rows"]:
        for c in crop_ids(r["crop_system"]):
            counts[c] = counts.get(c, 0) + 1
    return [c for c, _ in sorted(counts.items(), key=lambda kv: -kv[1])][:limit]


def measure(district: str, crop: str, kind: str, weeks: int | None = None, state: str = "") -> dict | None:
    """What the plan prescribes here. For a late monsoon, the nearest delay at or below `weeks`."""
    plan = find(district, state)
    if not plan:
        return None
    hits = [r for r in plan["rows"]
            if (situation(r["condition"]) or situation(r.get("section", ""))) == kind
            and crop in crop_ids(r["crop_system"])]
    if kind == DELAYED and weeks is not None:
        graded = [r for r in hits if r["delay_weeks"] is not None]
        at_or_below = [r for r in graded if r["delay_weeks"] <= weeks]
        hits = sorted(at_or_below or graded, key=lambda r: -(r["delay_weeks"] or 0))
    # prefer a row that actually changes something over "no change"
    hits = sorted(hits, key=lambda r: (not r["change"], not r["agronomy"]))
    if not hits:
        return None
    r = hits[0]
    return {"change": r["change"], "agronomy": r["agronomy"], "crop_system": r["crop_system"],
            "condition": r["condition"], "delay_weeks": r["delay_weeks"],
            "district": plan["district"], "state": plan["state"], "page": r["page"], "source": plan["source"],
            "nearby": bool(plan.get("nearby")), "for_district": plan.get("for_district", "")}


# "Avoid green gram, groundnut and soybean ... Sunflower hybrids - chickpea": the crops to sow
# are in the clauses that are NOT telling the farmer to avoid something.
NEGATIVE = re.compile(r"\b(avoid|do not|not recommended|instead of|except|drop)\b", re.I)


def recommended_crops(change: str) -> list[str]:
    """Crop ids the plan tells the farmer to sow, never ones it tells them to avoid."""
    out: list[str] = []
    for clause in re.split(r"[.;\n]|\bthen\b", change or ""):
        if not clause.strip() or NEGATIVE.search(clause):
            continue
        for cid in crop_ids(clause):
            if cid not in out:
                out.append(cid)
    return out


def alternative_crop(district: str, crop: str, weeks: int, state: str = "") -> tuple[str | None, dict | None]:
    """The plan's replacement crop for a monsoon this late, as a crop id we can name in any language.

    Returns None when the plan prescribes no crop change, or only says what to avoid: then the
    advice stays "wait and keep seed ready" rather than inventing a crop.
    """
    m = measure(district, crop, DELAYED, weeks, state)
    if not m or not m["change"]:
        return None, m
    for cid in recommended_crops(m["change"]):
        if cid != crop:
            return cid, m
    return None, m


def coverage() -> None:
    import pandas as pd
    blocks = pd.read_parquet(PROCESSED / "blocks.parquet")
    found = [find(d, s) for d, s in zip(blocks["district"], blocks["state"])]
    hit = [f is not None for f in found]
    own = sum(1 for f in found if f and not f.get("nearby"))
    print(f"of those, {own:,} have their own district's plan; the rest borrow the nearest one")
    by_state = blocks.assign(hit=hit).groupby("state")["hit"].agg(["mean", "size"]).sort_values("mean")
    print(f"plans on disk: {sum(len(v) for v in _plans().values())} districts")
    print(f"blocks covered: {sum(hit):,} of {len(hit):,} ({sum(hit) / len(hit):.0%})\n")
    print(by_state.to_string(float_format=lambda v: f"{v:.0%}"))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "coverage"
    if cmd == "coverage":
        coverage()
    else:
        d, c = sys.argv[2], sys.argv[3]
        print("crops:", district_crops(d))
        for wk in (2, 4, 6):
            alt, m = alternative_crop(d, c, wk)
            print(f"\n{wk} weeks late -> {alt or '(no crop change)'}")
            if m:
                print(f"   plan: {m['crop_system']} -> {m['change'] or 'no change'}")
                print(f"   agronomy: {m['agronomy'][:120]}")
                print(f"   {m['district']} plan, p{m['page']}")
