"""Fold-independent features on the (year, issue, block) grid.

Every feature at issue day d uses rainfall observed up to d-1 and indices as
published by d. Fold-dependent features (climatology, usual onset date) are
added at training time, see models/gbm.py.

Output PROCESSED/features/{year}.npz with array X (issue, block, feature) float32
and PROCESSED/features/names.json.
"""
from __future__ import annotations
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
from scipy import sparse
from sklearn.neighbors import BallTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import PROCESSED, WET_DAY_MM, ONSET_CHECK_DAYS, FALSE_ONSET_DRY_RUN
from features.labels import candidate_onset, forward_dry_run
from features.targets import ISSUE_DOY0, ISSUE_DOY1, N_ISSUE
from features.onset_normal import search_start_doy

SEASON0 = ISSUE_DOY0 - 1            # 0-based index of 1 May
CONFIRM = ONSET_CHECK_DAYS + FALSE_ONSET_DRY_RUN
EARTH_KM = 6371.0


def neighbour_matrix(lat, lon, radius_km):
    """Row-normalised sparse matrix averaging over blocks within radius (incl. self)."""
    X = np.radians(np.c_[lat, lon])
    idx = BallTree(X, metric="haversine").query_radius(X, r=radius_km / EARTH_KM)
    rows = np.concatenate([np.full(len(i), r) for r, i in enumerate(idx)])
    cols = np.concatenate(idx)
    M = sparse.csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(lat),) * 2)
    return sparse.diags(1 / np.asarray(M.sum(1)).ravel()) @ M


def back_dry_run(rain):
    """run[t] = consecutive dry days ending at t (inclusive)."""
    dry = rain < WET_DAY_MM
    run = np.zeros(rain.shape, np.int16)
    run[0] = dry[0]
    for t in range(1, len(rain)):
        run[t] = np.where(dry[t], run[t - 1] + 1, 0)
    return run


def year_features(rain, idx_row, N150, N400, start0):
    """rain: (T, B) mm for one calendar year; start0: (B,) 0-based first day onset may count.
    Returns (N_ISSUE, B, F), names."""
    T, B = rain.shape
    r = np.nan_to_num(rain, nan=0.0).astype(np.float32)
    cs = np.concatenate([np.zeros((1, B), np.float32), np.cumsum(r, 0)])
    wet = (r >= WET_DAY_MM).astype(np.int16)
    cw = np.concatenate([np.zeros((1, B), np.int32), np.cumsum(wet, 0)])
    brun = back_dry_run(r)
    frun = forward_dry_run(r[:, :, None])[:, :, 0]

    cand = candidate_onset(r[:, :, None])[:, :, 0]
    cand &= np.arange(T)[:, None] >= start0[None]
    # a candidate at c is only KNOWN once its 5-day window is complete (c+4)
    known_at = np.zeros_like(cand)
    known_at[4:] = cand[:-4]
    ccount = np.cumsum(known_at, 0)
    idx_t = np.where(known_at, np.arange(T)[:, None] - 4, -1)
    last_c = np.maximum.accumulate(idx_t, axis=0)            # day index of last known candidate

    # confirmed true onset: candidate c whose killing-dry-run test is fully
    # observed by c+CONFIRM and passed.
    held = np.zeros_like(cand)
    for c in range(SEASON0, T - CONFIRM):
        ok = cand[c] & (frun[c:c + ONSET_CHECK_DAYS + 1].max(0) < FALSE_ONSET_DRY_RUN)
        held[c] = ok
    conf_at = np.zeros_like(held)
    conf_at[CONFIRM:] = held[:-CONFIRM]
    confirmed_by = np.cumsum(conf_at, 0) > 0
    idx_h = np.where(conf_at, np.arange(T)[:, None] - CONFIRM, -1)
    fc = np.full(B, -1)
    first_conf = np.empty((T, B), np.int32)
    for t in range(T):
        new = (fc < 0) & (idx_h[t] >= 0)
        fc = np.where(new, idx_h[t], fc)
        first_conf[t] = fc

    feats, names = [], None
    for i in range(N_ISSUE):
        d = ISSUE_DOY0 + i            # issue DOY
        t = d - 2                     # 0-based index of DOY d-1 (last observed day)
        s = lambda n: cs[t + 1] - cs[t + 1 - n]
        f = {
            "r1": r[t], "r3": s(3), "r7": s(7), "r14": s(14), "r30": s(30),
            "wet14": (cw[t + 1] - cw[t + 1 - 14]).astype(np.float32),
            "dry_run": brun[t].astype(np.float32),
            "season_rain": cs[t + 1] - cs[SEASON0],
            "cand_count": ccount[t].astype(np.float32),
            "days_since_cand": np.where(last_c[t] >= 0, t - last_c[t], 999).astype(np.float32),
            "onset_confirmed": confirmed_by[t].astype(np.float32),
            "days_since_conf_onset": np.where(first_conf[t] >= 0, t - first_conf[t], -1).astype(np.float32),
        }
        # spatial context: what is happening around this block (onset front proxy)
        f["r7_150km"] = N150 @ f["r7"]
        f["r7_400km"] = N400 @ f["r7"]
        f["cand_share_150km"] = N150 @ (f["cand_count"] > 0).astype(np.float32)
        f["cand_share_400km"] = N400 @ (f["cand_count"] > 0).astype(np.float32)
        f["conf_share_400km"] = N400 @ f["onset_confirmed"]
        f["dry_run_150km"] = N150 @ f["dry_run"]
        f["doy"] = np.full(B, d, np.float32)
        for k, v in idx_row(d).items():
            f[k] = np.full(B, v, np.float32)
        if names is None:
            names = list(f)
        feats.append(np.stack([f[n] for n in names], -1).astype(np.float32))
    return np.stack(feats), names


def main():
    rain = xr.open_dataset(PROCESSED / "imd_block_rain.nc")["rain"]
    blocks = pd.read_parquet(PROCESSED / "blocks.parquet").set_index("block_id").loc[rain.block.values]
    N150 = neighbour_matrix(blocks.lat.values, blocks.lon.values, 150)
    N400 = neighbour_matrix(blocks.lat.values, blocks.lon.values, 400)
    print(f"neighbours: median {np.median(np.diff(N150.indptr)):.0f} within 150 km, "
          f"{np.median(np.diff(N400.indptr)):.0f} within 400 km", flush=True)

    ix = pd.read_parquet(PROCESSED / "indices_asof.parquet").set_index("issue_date")
    icols = ["mjo_pc1", "mjo_pc2", "mjo_amp", "mjo_sin", "mjo_cos", "nino34"]
    out = PROCESSED / "features"; out.mkdir(exist_ok=True)
    static = np.stack([blocks.lat.values, blocks.lon.values,
                       np.log(blocks.area_km2.values)], -1).astype(np.float32)
    start0 = search_start_doy(blocks.lat.values, blocks.lon.values) - 1
    tt = rain.time.to_index()
    for yr in range(1991, 2026):
        sel = tt.year == yr
        ry = rain.values[sel]
        def idx_row(doy, yr=yr):
            day = pd.Timestamp(yr, 1, 1) + pd.Timedelta(days=doy - 1)
            return {c: float(ix.at[day, c]) if day in ix.index else np.nan for c in icols}
        X, names = year_features(ry, idx_row, N150, N400, start0)
        X = np.concatenate([X, np.broadcast_to(static, (X.shape[0],) + static.shape)], -1)
        np.savez_compressed(out / f"{yr}.npz", X=X)
        print(f"{yr}: X {X.shape}  NaN share {np.isnan(X).mean():.4f}", flush=True)
    (out / "names.json").write_text(json.dumps(names + ["lat", "lon", "log_area"]))


if __name__ == "__main__":
    main()
