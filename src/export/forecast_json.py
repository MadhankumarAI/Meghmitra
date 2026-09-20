"""Export one issue date as the compact JSON the web console reads.

  python forecast_json.py 2023-07-01 [--source clim|gbm|gbm_fast]
  python forecast_json.py 2023 --source gbm_fast        (whole season + season_2023.json)

Writes EXPORTS/forecast/{date}.json:
  { issued, source, product, blocks: N,
    events: { onset|dry10|heavy: { p: [[N ints] x 4 weeks], clim: [[N] x 4] } },
    cmri:           [[N ints -2..3] x 4]   0 normal .. 3 alert; -1 NE-monsoon regime, -2 winter regime
    onset_status:   [N]  0 confirmed, 1 holding, 2 pending, 3 pending after a false onset
    sowing_rain_doy:[N]  most recent sowing-grade rain, -1 none
    window:         [N]  open decision window: 0 none, 1 sowing, 2 seedlings establishing }
Probabilities are integer percent; -1 means not applicable (onset already confirmed).
Arrays are indexed by the block index `i` used in the map tiles.
"""
from __future__ import annotations
import os, sys, json, argparse
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr

DATA = Path(os.environ.get("MORPHY_DATA", Path.home() / "morphy" / "data"))
PROCESSED, EXPORTS = DATA / "processed", DATA / "exports"
EVENTS = ("onset", "dry10", "heavy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from features.labels import candidate_onset, forward_dry_run          # noqa: E402
from advisory import engine                                           # noqa: E402
from features.onset_normal import search_start_doy                   # noqa: E402

SEASON0 = 120                   # 0-based day index of 1 May
CONFIRM = 40                    # 30-day check + 10-day dry run, see LABELS.md
# onset status codes, observable at issue time from rainfall up to d-1
CONFIRMED, HOLDING, PENDING, FAILED = 0, 1, 2, 3


def onset_status(rain_year: np.ndarray, d: pd.Timestamp, start0: np.ndarray):
    """Per block: status code and DOY of the most recent sowing rain (or -1).

    Uses only days before the issue date. A sowing rain (candidate onset) at c is
    known once its 5-day window closes. It is FAILED if a >=10-day dry run starting
    at or after c has already been observed, CONFIRMED if 40 days have passed
    without one, otherwise HOLDING.
    """
    last = d.dayofyear - 2                          # 0-based index of d-1
    r = rain_year[: last + 1].copy()                # observed only
    cand = candidate_onset(r[:, :, None])[:, :, 0]
    cand &= np.arange(len(r))[:, None] >= start0[None]      # no pre-monsoon storms
    cand[max(last - 3, 0):] = False                 # window must be fully observed
    frun = forward_dry_run(r[:, :, None])[:, :, 0]  # truncated series: runs end at d-1
    B = r.shape[1]
    status = np.full(B, PENDING, np.int8)
    last_c = np.full(B, -1, np.int32)
    for c in range(int(start0.min()), last - 3):
        hit = cand[c]
        if not hit.any():
            continue
        # killing dry run must START within the 30-day check window (LABELS.md);
        # runs are truncated at d-1, so >=10 means already observed to be >=10
        killed = frun[c:c + 31].max(0) >= 10
        # later candidates supersede earlier ones; a confirmed onset is final
        upd = hit & (status != CONFIRMED)
        last_c[upd] = c
        status[upd & killed] = FAILED
        status[upd & ~killed & (c + CONFIRM <= last)] = CONFIRMED
        status[upd & ~killed & (c + CONFIRM > last)] = HOLDING
    return status, np.where(last_c >= 0, last_c + 1, -1)


# Not a southwest-monsoon region: no CMRI. Named by which season actually dominates.
NE_MONSOON, WINTER_REGIME = -1, -2
SW_SHARE_MIN = 0.40           # Jun-Sep share of annual rain below this -> other regime
MONSOON_MIN_MM = 100.0        # and arid blocks with almost no Jun-Sep rain
SOWING_BEFORE, SOWING_AFTER = 21, 35     # sowing decision window around usual onset (days)


def cmri_class(p: dict, c: dict, window_open: np.ndarray, regime: np.ndarray) -> np.ndarray:
    """CMRI v1.0 on one lead week. 0 normal, 1 watch, 2 warning, 3 alert;
    -1 northeast-monsoon regime, -2 winter-precipitation regime (no SW-monsoon CMRI).

    Escalates on departure from normal, not raw probability, so a dry desert block
    isn't permanently red. ALERT means "act now": a warning-level dry signal while
    seedlings are establishing after sowing rain (the false-onset trap). Heavy-rain
    alerts don't wait for a crop stage. The planetary 'Watch' input (signatures)
    joins once the v2 model export exists.
    """
    dry_up = p["dry10"] - c["dry10"]
    wet_ratio = p["heavy"] / np.maximum(c["heavy"], 0.01)
    heavy_alert = (wet_ratio >= 3.0) & (p["heavy"] >= 0.3)
    cls = np.zeros(p["dry10"].shape, np.int8)
    cls[(dry_up >= 0.05) | ((wet_ratio >= 1.5) & (p["heavy"] >= 0.08))] = 1
    cls[(dry_up >= 0.12) | ((wet_ratio >= 2.0) & (p["heavy"] >= 0.15))] = 2
    cls[((dry_up >= 0.12) & (p["dry10"] >= 0.5) & window_open) | heavy_alert] = 3
    cls[regime < 0] = regime[regime < 0]
    return cls


def block_context(tg, exclude_years):
    """Usual onset DOY and rainfall regime per block, from years NOT excluded.

    regime: 0 southwest monsoon (CMRI applies); -1 northeast monsoon dominant
    (Oct-Dec > Jan-May); -2 winter precipitation dominant (Jammu & Kashmir, Ladakh).
    """
    lab = xr.open_dataset(PROCESSED / "imd_block_labels.nc")
    keep = ~np.isin(lab.year.values, exclude_years)
    od = lab.true_onset_doy.values[keep].astype(float)
    od[od < 0] = np.nan
    usual = np.nanmedian(od, axis=0)
    usual = np.where(np.isfinite(usual), usual, 999.0)
    r = xr.open_dataset(PROCESSED / "imd_block_rain.nc")["rain"].load()
    yrs = r.time.dt.year.values
    mon = r.time.dt.month.values
    kept = ~np.isin(yrs, exclude_years)
    n_years = max(len(np.unique(yrs[kept])), 1)
    total = lambda months: np.nansum(r.values[kept & np.isin(mon, months)], 0) / n_years
    jjas, ond, jfmam = total([6, 7, 8, 9]), total([10, 11, 12]), total([1, 2, 3, 4, 5])
    share = jjas / np.maximum(jjas + ond + jfmam, 1.0)
    regime = np.zeros(len(share), np.int8)
    other = (share < SW_SHARE_MIN) | (jjas < MONSOON_MIN_MM)
    regime[other & (ond >= jfmam)] = NE_MONSOON
    regime[other & (ond < jfmam)] = WINTER_REGIME
    blocks = pd.read_parquet(PROCESSED / "blocks.parquet").set_index("block_id").loc[tg.block.values]
    districts = blocks.district.fillna("").values if "district" in blocks else [""] * len(blocks)
    states = blocks.state.fillna("").values
    crops = [engine.crops_for(st, di) for st, di in zip(states, districts)]
    places = list(zip(districts, states))
    start0 = search_start_doy(blocks.lat.values, blocks.lon.values) - 1
    return usual.astype(np.float32), regime, crops, start0, places


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date", help="YYYY-MM-DD, or a year to export its whole season")
    ap.add_argument("--source", default="clim", choices=["clim", "gbm", "gbm_fast"])
    a = ap.parse_args()
    clim = xr.open_dataset(PROCESSED / "clim_folds.nc")
    tg = xr.open_dataset(PROCESSED / "targets.nc")
    model = clim if a.source == "clim" else xr.open_dataset(PROCESSED / f"{a.source.replace('gbm', 'gbm_pred')}.nc")
    if len(a.date) == 4:                                  # whole season: every issue day
        yr = int(a.date)
        days = [pd.Timestamp(yr, 1, 1) + pd.Timedelta(days=int(i) - 1) for i in tg.issue.values]
        # load the year once; per-day slicing from memory is fast
        model = model.sel(year=yr).load(); clim_y = clim.sel(year=yr).load(); tg_y = tg.sel(year=yr).load()
        rain = year_rain(yr)
        ctx = block_context(tg, fold_years(yr))
        for d in days:
            export_day(d, a.source, model, clim_y, tg_y, rain, ctx, yearless=True)
        index = {"year": yr, "source": a.source, "dates": [d.strftime("%Y-%m-%d") for d in days]}
        (EXPORTS / "forecast" / f"season_{yr}.json").write_text(json.dumps(index))
        print(f"season {yr}: {len(days)} days exported")
    else:
        d = pd.Timestamp(a.date)
        export_day(d, a.source, model, clim, tg, year_rain(d.year), block_context(tg, fold_years(d.year)))


def write_advisories(d, P, C, st, usual, regime, crops, places=None):
    """Sparse per-day advisories: {block index: [[crop, template, tier, params], ...]}."""
    doy = d.dayofyear
    wait_until = (d + pd.Timedelta(days=13)).strftime("%Y-%m-%d")      # end of week 2
    out = {}
    for i in np.nonzero(regime == 0)[0]:
        p = {e: P[e][:, i] for e in EVENTS}
        c = {e: C[e][:, i] for e in EVENTS}
        rows = []
        for crop in crops[i]:
            a = engine.advise(p, c, int(st[i]), doy, float(usual[i]), crop, wait_until,
                              places[i] if places else ("", ""))
            if a:
                rows.append([crop, a[0], a[1], a[2]])
        if rows:
            out[int(i)] = rows
    dest = EXPORTS / "advisory"; dest.mkdir(parents=True, exist_ok=True)
    (dest / f"{d.strftime('%Y-%m-%d')}.json").write_text(
        json.dumps({"issued": d.strftime("%Y-%m-%d"), "advisories": out}, separators=(",", ":")))
    return out


def fold_years(yr: int) -> list[int]:
    """All years of the validation block containing yr (the model never saw them)."""
    from models.climatology import FOLDS
    for a, b in FOLDS:
        if a <= yr <= b:
            return list(range(a, b + 1))
    return [yr]


def year_rain(yr: int) -> np.ndarray:
    r = xr.open_dataset(PROCESSED / "imd_block_rain.nc")["rain"]
    return np.nan_to_num(r.sel(time=str(yr)).values.astype(np.float32), nan=0.0)


def export_day(d, source, model, clim, tg, rain, ctx, yearless=False):
    doy = d.dayofyear
    sel = dict(issue=doy) if yearless else dict(year=d.year, issue=doy)
    out = {"issued": d.strftime("%Y-%m-%d"), "source": source, "product": "CMRI v1.0-draft",
           "blocks": int(tg.sizes["block"]), "events": {}, "cmri": []}
    P, C = {}, {}
    for e in EVENTS:
        p = model[e].sel(**sel).values                      # (lead, block)
        c = clim[e].sel(**sel).values
        na = tg[e].sel(**sel).values < 0
        p = np.where(na | ~np.isfinite(p), np.nan, p)
        P[e], C[e] = p, c
        pct = lambda x: np.where(np.isfinite(x), np.round(x * 100), -1).astype(int).tolist()
        out["events"][e] = {"p": pct(p), "clim": pct(np.where(na, np.nan, c))}
    usual, regime, crops, start0, places = ctx
    st, last_doy = onset_status(rain, d, start0)
    sowing = np.isin(st, [PENDING, FAILED]) & (doy >= usual - SOWING_BEFORE) & (doy <= usual + SOWING_AFTER)
    # ALERT is for the false-onset trap: sowing rain came, seedlings are establishing,
    # and a dry spell is coming. Pending blocks can't sow a rainfed crop yet ("keep
    # waiting" = Warning); established crops get Warning for moisture stress.
    window_open = st == HOLDING
    # advice first: the map may never look calmer than the advice for the same block
    adv = write_advisories(d, P, C, st, usual, regime, crops, places)
    tier = np.zeros(len(st), np.int8)
    for i, rows in adv.items():
        tier[i] = max(r[2] for r in rows)
    for w in range(4):
        pw = {e: np.nan_to_num(P[e][w], nan=0.0) for e in EVENTS}
        cw = {e: np.nan_to_num(C[e][w], nan=0.0) for e in EVENTS}
        cls = cmri_class(pw, cw, window_open, regime)
        if w < 2:                                   # advice covers the next two weeks
            cls = np.where(regime < 0, cls, np.maximum(cls, tier))
        out["cmri"].append(cls.tolist())
    out["window"] = np.where(sowing, 1, np.where(st == HOLDING, 2, 0)).astype(int).tolist()  # 1 sowing, 2 establishing
    out["onset_status"] = st.tolist()          # 0 confirmed, 1 holding, 2 pending, 3 failed
    out["sowing_rain_doy"] = last_doy.tolist()  # most recent sowing-grade rain, -1 none
    dest = EXPORTS / "forecast"; dest.mkdir(parents=True, exist_ok=True)
    f = dest / f"{out['issued']}.json"
    f.write_text(json.dumps(out, separators=(",", ":")))
    if not yearless:
        counts = np.bincount(np.array(out["cmri"][0]) + 2, minlength=6)   # winter, NE, normal..alert
        sc = np.bincount(st, minlength=4)
        print(f"{f.name} {f.stat().st_size / 1e3:.0f} kB  source={source}  "
              f"W1 CMRI winter/NE/normal/watch/warning/alert = {counts.tolist()}  "
              f"onset confirmed/holding/pending/failed = {sc.tolist()}")


if __name__ == "__main__":
    main()
