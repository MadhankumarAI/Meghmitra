"""Today's block-level outlook from real-time data (runs on the server, daily).

  python run_live.py [YYYY-MM-DD]      issue date; default = today (IST)

Inputs, all published daily:
  IMD real-time gridded rainfall   raw/imd_rt/*.grd (fetched from imdpune.gov.in, which only the
                                   laptop can reach; see scripts in docs/LIVE.md)
  NOAA PSL ROMI (MJO)              refreshed here
  NOAA CPC weekly Nino 3.4         refreshed here
Model: final_models/ (models/final.py), trained on 1991-2025 with the validated v1 settings.

Writes exports/forecast/live.json and exports/advisory/live.json in the same format as the
hindcast day files, plus dated copies. Outside the season window (1 May - 30 Sep) it writes
a small status file instead, so the site can say the season is over rather than show nothing.
"""
from __future__ import annotations
import os, sys, json, shutil, subprocess
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
import lightgbm as lgb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import PROCESSED, RAW_INDICES, RAW, EXPORTS
from features.targets import ISSUE_DOY0, ISSUE_DOY1
from features.build_features import year_features, neighbour_matrix
from features.onset_normal import search_start_doy
from features.block_series import weight_matrix
from export import forecast_json as fj

EVENTS = ("onset", "dry10", "heavy")
RT = RAW / "imd_rt"
MODELS = PROCESSED / "final_models"
INDEX_URLS = {
    "romi.cpcolr.1x.txt": "https://psl.noaa.gov/mjo/mjoindex/romi.cpcolr.1x.txt",
    "oni_weekly.txt": "https://www.cpc.ncep.noaa.gov/data/indices/wksst9120.for",
}


def refresh_indices():
    for name, url in INDEX_URLS.items():
        tmp = RAW_INDICES / (name + ".part")
        r = subprocess.run(["curl", "-sf", "--max-time", "120", "-o", str(tmp), url])
        if r.returncode == 0 and tmp.stat().st_size > 1000:
            tmp.replace(RAW_INDICES / name)
        else:
            print(f"warning: could not refresh {name}; using the cached copy", flush=True)
    from data import indices
    indices.main()


def rain_year(year: int, issue: pd.Timestamp, blocks_W, nx: int) -> np.ndarray:
    """Daily block rainfall for the calendar year; days not yet observed are 0 and unused."""
    import imdlib
    W = blocks_W
    days = pd.date_range(f"{year}-01-01", f"{year}-12-31")
    out = np.zeros((len(days), W.shape[0]), np.float32)
    have = sorted(RT.glob(f"rain_ind0.25_{year % 100:02d}_*.grd"))
    if not have:
        raise SystemExit(f"no real-time rainfall for {year} in {RT}")
    first = pd.Timestamp(f"{year}-" + have[0].stem.split("_")[-2] + "-" + have[0].stem.split("_")[-1])
    last = issue - pd.Timedelta(days=1)                            # observations up to d-1 only
    # Read day by day: imdlib's range reader fails on any gap, and live feeds have gaps.
    missing = []
    for d in pd.date_range(first, last):
        if not (RT / f"rain_ind0.25_{d:%y_%m_%d}.grd").exists():
            missing.append(d)
            continue
        da = imdlib.open_real_data("rain", d.strftime("%Y-%m-%d"), d.strftime("%Y-%m-%d"), str(RT)).get_xarray()["rain"]
        flat = da.where(da >= 0).values.reshape(1, -1)
        valid = np.isfinite(flat)
        num = (W @ np.where(valid, flat, 0.0).T).T
        den = (W @ valid.T.astype(float)).T
        out[(d - days[0]).days] = np.nan_to_num(np.where(den > 0.5, num / np.maximum(den, 1e-9), np.nan), nan=0.0)[0]
    n = (last - first).days + 1
    print(f"rainfall {first:%d %b} -> {last:%d %b %Y}: {n - len(missing)} of {n} days"
          + (f"; MISSING {len(missing)} (treated as unobserved): {[d.strftime('%d %b') for d in missing][:6]}"
             if missing else ""), flush=True)
    return out, missing


def main(issue: pd.Timestamp):
    doy = issue.dayofyear
    (EXPORTS / "forecast").mkdir(parents=True, exist_ok=True)
    status = EXPORTS / "forecast" / "live_status.json"
    if not (ISSUE_DOY0 <= doy <= ISSUE_DOY1):
        status.write_text(json.dumps({"issued": issue.strftime("%Y-%m-%d"), "in_season": False,
                                      "message": "The monsoon outlook runs from 1 May to 30 September."}))
        print("outside the season window; wrote status only")
        return
    refresh_indices()

    first = xr.open_dataset(PROCESSED / "imd_block_rain.nc")
    B = first.sizes["block"]
    W, blocks = weight_matrix(129, 135)
    blocks = blocks.set_index("block_id").loc[first.block.values]
    rain, missing = rain_year(issue.year, issue, W, 135)
    # Safety: never publish from a patchy record. Features look back up to 40 days and onset
    # status uses the whole season, so require the last 60 days to be >= 90% observed.
    recent = [d for d in missing if d >= issue - pd.Timedelta(days=60)]
    if len(recent) > 6:
        status.write_text(json.dumps({"issued": issue.strftime("%Y-%m-%d"), "in_season": True, "published": False,
                                      "message": f"Not enough recent rainfall observations ({len(recent)} of the last 60 days missing)."}))
        raise SystemExit(f"refusing to publish: {len(recent)} of the last 60 days of rainfall are missing")

    N150 = neighbour_matrix(blocks.lat.values, blocks.lon.values, 150)
    N400 = neighbour_matrix(blocks.lat.values, blocks.lon.values, 400)
    ix = pd.read_parquet(PROCESSED / "indices_asof.parquet").set_index("issue_date")
    icols = ["mjo_pc1", "mjo_pc2", "mjo_amp", "mjo_sin", "mjo_cos", "nino34"]

    def idx_row(d):
        day = pd.Timestamp(issue.year, 1, 1) + pd.Timedelta(days=d - 1)
        return {c: float(ix.at[day, c]) if day in ix.index else np.nan for c in icols}

    start0 = search_start_doy(blocks.lat.values, blocks.lon.values) - 1
    Xall, names = year_features(rain, idx_row, N150, N400, start0)
    i = doy - ISSUE_DOY0
    static = np.stack([blocks.lat.values, blocks.lon.values, np.log(blocks.area_km2.values)], -1).astype(np.float32)
    x = np.concatenate([Xall[i], static], -1)                           # (B, F)
    age = {c: float(idx_row(doy).get(c, np.nan)) for c in ("mjo_amp", "nino34")}

    meta = json.loads((MODELS / "meta.json").read_text())
    ca = np.load(MODELS / "clim_all.npz")
    uo = ca["usual_onset"]
    doy_col = names.index("doy")
    P, C = {}, {}
    for e in EVENTS:
        c = ca[e][i]                                                    # (L, B)
        P[e] = np.zeros((4, B), np.float32)
        for li in range(4):
            feat = np.concatenate([x, c[li][:, None], uo[:, None], (x[:, doy_col] - uo)[:, None]], -1)
            m = lgb.Booster(model_file=str(MODELS / f"{e}_W{li + 1}.txt"))
            P[e][li] = m.predict(feat)
        C[e] = c

    usual, regime, crops, s0, places = fj.block_context(first, [])        # all years: this is live, not a hindcast
    st, last_doy = fj.onset_status(rain, issue, s0)
    confirmed = st == fj.CONFIRMED
    P["onset"][:, confirmed] = np.nan                                    # onset already happened

    # why: exact week-1 driver contributions from the same models (export/explain_json.py)
    from export import explain_json as xj
    groups, appl, worst = {}, {}, 0.0
    for e in EVENTS:
        m = lgb.Booster(model_file=str(MODELS / f"{e}_W1.txt"))
        feat = np.concatenate([x, C[e][0][:, None], uo[:, None], (x[:, doy_col] - uo)[:, None]], -1)
        groups[e], p = xj.contributions(m, feat, meta["features"])
        appl[e] = np.isfinite(P[e][0])
        worst = max(worst, float(np.abs(p[appl[e]] - P[e][0][appl[e]]).max()) if appl[e].any() else 0.0)
    xj.write(EXPORTS / "explain" / f"{issue:%Y-%m-%d}.json", f"{issue:%Y-%m-%d}",
             "v1 gradient boosting, trained 1991-2025", groups, appl,
             xj.raw_values(x, meta["features"]), xj.planet_values(x[0], meta["features"]))
    shutil.copy(EXPORTS / "explain" / f"{issue:%Y-%m-%d}.json", EXPORTS / "explain" / "live.json")
    print(f"explanations written; max |sum of contributions - forecast| = {worst:.1e}", flush=True)
    pct = lambda a: np.where(np.isfinite(a), np.round(a * 100), -1).astype(int).tolist()
    out = {"issued": issue.strftime("%Y-%m-%d"), "source": "live", "product": "CMRI v1.0-draft",
           "blocks": int(B), "events": {e: {"p": pct(P[e]), "clim": pct(np.where(np.isnan(P[e]), np.nan, C[e]))}
                                         for e in EVENTS}, "cmri": []}
    adv = fj.write_advisories(issue, P, C, st, usual, regime, crops, places)
    tier = np.zeros(B, np.int8)
    for k, rows in adv.items():
        tier[k] = max(r[2] for r in rows)
    window_open = st == fj.HOLDING
    for w in range(4):
        pw = {e: np.nan_to_num(P[e][w], nan=0.0) for e in EVENTS}
        cw = {e: np.nan_to_num(C[e][w], nan=0.0) for e in EVENTS}
        cls = fj.cmri_class(pw, cw, window_open, regime)
        if w < 2:
            cls = np.where(regime < 0, cls, np.maximum(cls, tier))
        out["cmri"].append(cls.tolist())
    out["onset_status"] = st.tolist()
    out["sowing_rain_doy"] = last_doy.tolist()
    out["inputs"] = {"rain_through": (issue - pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                     "rain_days_missing": [d.strftime("%Y-%m-%d") for d in missing],
                     "mjo_amp": age["mjo_amp"], "nino34": age["nino34"],
                     "model": "v1 gradient boosting, trained 1991-2025", "trees": meta["models"]}
    day = EXPORTS / "forecast" / f"{out['issued']}.json"
    day.write_text(json.dumps(out, separators=(",", ":")))
    shutil.copy(day, EXPORTS / "forecast" / "live.json")
    shutil.copy(EXPORTS / "advisory" / f"{out['issued']}.json", EXPORTS / "advisory" / "live.json")
    status.write_text(json.dumps({"issued": out["issued"], "in_season": True}))
    counts = np.bincount(np.array(out["cmri"][0]) + 2, minlength=6)
    print(f"live outlook {out['issued']}: CMRI winter/NE/normal/watch/warning/alert = {counts.tolist()}; "
          f"{len(adv)} blocks with advice; onset confirmed/holding/pending/failed = {np.bincount(st, minlength=4).tolist()}")


if __name__ == "__main__":
    d = pd.Timestamp(sys.argv[1]) if len(sys.argv) > 1 else pd.Timestamp.now(tz="Asia/Kolkata").normalize().tz_localize(None)
    main(d)
