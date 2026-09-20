"""Gradient boosting per (event, lead), trained and scored under the 5-block protocol.

Fold-dependent features are nested so nothing from the test block reaches training:
  test rows (fold f)        : climatology / usual onset estimated without fold f
  train rows (fold f' != f) : estimated without folds f AND f' (no own-year leakage)
Early stopping uses whole held-out TRAINING years, never test years.

Usage: python gbm.py [--fast] [--v2] [--only-fold F --save-models DIR]
  --fast  sparser training rows, for a first read
  --v2    per-block teleconnection signatures (models/signatures.py) replace raw indices
  --only-fold F --save-models DIR
          re-train fold F alone and save its boosters (for explanations, export/explain_json.py).
          Other folds' random draws are replayed so fold F sees exactly the same rows; its test
          predictions are checked against the existing gbm_pred*.nc, which is left untouched.
Writes PROCESSED/gbm_pred.nc (same grid as targets) and PROCESSED/gbm_scores.json.
"""
from __future__ import annotations
import os, sys, json, time, argparse
from pathlib import Path
import numpy as np
import xarray as xr
import lightgbm as lgb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import PROCESSED
from models.climatology import FOLDS, fold_of, smooth, PRIOR_WEIGHT, EVENTS
from features import iod
from verify.score import summary
from features.targets import ISSUE_DOY0

YEARS = np.arange(1991, 2026)
# threads from the shared-server budget (env.sh), never hard-coded: other jobs run here
THREADS = int(os.environ.get("MORPHY_CPUS", "16"))
PARAMS = dict(objective="binary", learning_rate=0.05, num_leaves=63, min_data_in_leaf=400,
              feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0,
              verbose=-1)


def estimate(H, V, keep):
    h, v = H[keep].sum(0), V[keep].sum(0)
    nat = h.sum(-1, keepdims=True) / np.maximum(v.sum(-1, keepdims=True), 1)
    return ((h + PRIOR_WEIGHT * nat) / (v + PRIOR_WEIGHT)).astype(np.float32)


def usual_onset(onset_doy, lab_years, keep_years):
    """Median true-onset DOY per block over kept years (blocks never onsetting -> 300)."""
    m = np.isin(lab_years, keep_years)
    od = onset_doy[m].astype(float)
    od[od < 0] = np.nan
    u = np.nanmedian(od, axis=0)
    return np.where(np.isfinite(u), u, 300.0).astype(np.float32)


def main(fast: bool, v2: bool = False, only_fold: int | None = None, save_models: str | None = None):
    tg = xr.open_dataset(PROCESSED / "targets.nc")
    all_years = tg.year.values
    lab = xr.open_dataset(PROCESSED / "imd_block_labels.nc")
    lab_years, onset_doy = lab.year.values, lab.true_onset_doy.values
    names = json.loads((PROCESSED / "features" / "names.json").read_text())
    X = {y: np.load(PROCESSED / "features" / f"{y}.npz")["X"] for y in YEARS}
    I, B = tg.sizes["issue"], tg.sizes["block"]
    doy_col = names.index("doy")
    folds_all = np.array([fold_of(int(y)) for y in all_years])
    yidx = {int(y): i for i, y in enumerate(all_years)}
    rng = np.random.default_rng(0)
    step, block_frac = (5, 0.5) if fast else (3, 1.0)
    fnames = names + ["clim", "usual_onset", "days_vs_usual"] + iod.NAMES

    # v2: replace raw planetary indices (which overfit: ~4,000 independent MJO days
    # behind millions of rows) with per-block teleconnection signatures.
    RAW_PLANET = ["mjo_pc1", "mjo_pc2", "mjo_sin", "mjo_cos", "nino34"]
    keep_cols = np.array([n not in RAW_PLANET for n in fnames]) if v2 else np.ones(len(fnames), bool)
    if v2:
        import pandas as pd
        from features.build_features import neighbour_matrix
        from models import signatures as sg
        blocks = pd.read_parquet(PROCESSED / "blocks.parquet").set_index("block_id").loc[tg.block.values]
        N150 = neighbour_matrix(blocks.lat.values, blocks.lon.values, 150)
        mjo_state, enso_state = sg.state_tables(pd.read_parquet(PROCESSED / "indices_asof.parquet"),
                                                all_years, tg.issue.values)
        bins = sg.issue_bin(I)
        fnames = [n for n in fnames if n not in RAW_PLANET] + ["mjo_sig", "enso_sig"]

    pred = {e: np.full((len(all_years), I, 4, B), np.nan, np.float32) for e in EVENTS}
    importances = {}
    t0 = time.time()
    for e in EVENTS:
        T = tg[e].values.astype(np.int8)
        Hs, Vs = smooth(T == 1).astype(np.float32), smooth(T >= 0).astype(np.float32)
        if v2:
            Hm, Vm = sg.per_year_counts(T, mjo_state, 9)
            He, Ve = sg.per_year_counts(T, enso_state, 3)
            signature = lambda keep: (sg.estimate(Hm, Vm, keep, N150), sg.estimate(He, Ve, keep, N150))
        for f, (fa, fb) in enumerate(FOLDS):
            test_years = [y for y in YEARS if fa <= y <= fb]
            train_years = [y for y in YEARS if not (fa <= y <= fb)]
            # nested fold-dependent estimates (the IOD climatology is nested the same way)
            iod_test = tuple(int(y) for y in YEARS if fold_of(int(y)) != f)
            iod_tr = {g: tuple(int(y) for y in YEARS if fold_of(int(y)) not in (f, g))
                      for g in range(len(FOLDS)) if g != f}
            clim_test = estimate(Hs, Vs, folds_all != f)
            clim_tr = {g: estimate(Hs, Vs, (folds_all != f) & (folds_all != g))
                       for g in range(len(FOLDS)) if g != f}
            keep_test = [y for y in lab_years if fold_of(int(y)) != f]
            uo_test = usual_onset(onset_doy, lab_years, keep_test)
            uo_tr = {g: usual_onset(onset_doy, lab_years,
                                    [y for y in lab_years if fold_of(int(y)) not in (f, g)])
                     for g in clim_tr}
            val_years = set(rng.choice(train_years, 3, replace=False).tolist())
            # signatures nested exactly like climatology
            sig_test = signature(folds_all != f) if v2 else None
            sig_tr = ({g: signature((folds_all != f) & (folds_all != g)) for g in clim_tr}
                      if v2 else {g: None for g in clim_tr})

            if only_fold is not None and f != only_fold:
                # replay this fold's random draws (training-row block samples) without training
                for li in range(4):
                    for y in train_years:
                        if block_frac < 1:
                            rng.choice(B, int(B * block_frac), replace=False)
                continue
            for li in range(4):
                def rows(y, clim, uo, sub, sigs=None, keep=None):
                    Xy = X[y]                                   # (I, B, F)
                    iss = np.arange(0, I, step) if sub else np.arange(I)
                    blk = (np.sort(rng.choice(B, int(B * block_frac), replace=False))
                           if sub and block_frac < 1 else np.arange(B))
                    xs = Xy[np.ix_(iss, blk)]
                    c = clim[li][np.ix_(iss, blk)]              # clim is (L, I, B)
                    u = np.broadcast_to(uo[blk], (len(iss), len(blk)))
                    dvu = xs[..., doy_col] - u
                    feat = np.concatenate([xs, c[..., None], u[..., None], dvu[..., None]], -1)
                    feat = iod.append(feat, y, iss + ISSUE_DOY0, len(blk), keep)
                    feat = feat[..., keep_cols]
                    if sigs is not None:
                        yi_ = yidx[y]
                        ms = sg.lookup(sigs[0], mjo_state[yi_][iss], bins[iss], li, blk)
                        es = sg.lookup(sigs[1], enso_state[yi_][iss], bins[iss], li, blk)
                        feat = np.concatenate([feat, ms[..., None], es[..., None]], -1)
                    lab_ = T[yidx[y]][np.ix_(iss, [li], blk)][:, 0]
                    feat, lab_ = feat.reshape(-1, feat.shape[-1]), lab_.ravel()
                    ok = lab_ >= 0
                    return feat[ok], lab_[ok], (iss, blk, ok)

                clim_by_lead = lambda arr: np.moveaxis(arr, 1, 0)   # (L, I, B)
                Xtr, ytr, Xva, yva = [], [], [], []
                for y in train_years:
                    g = fold_of(y)
                    a, b, _ = rows(y, clim_by_lead(clim_tr[g]), uo_tr[g], sub=True, sigs=sig_tr[g], keep=iod_tr[g])
                    (Xva if y in val_years else Xtr).append(a)
                    (yva if y in val_years else ytr).append(b)
                dtr = lgb.Dataset(np.concatenate(Xtr), np.concatenate(ytr), feature_name=fnames,
                                  free_raw_data=True)
                dva = lgb.Dataset(np.concatenate(Xva), np.concatenate(yva), reference=dtr)
                model = lgb.train({**PARAMS, "num_threads": THREADS}, dtr, num_boost_round=1500,
                                  valid_sets=[dva], callbacks=[lgb.early_stopping(50, verbose=False)])
                if save_models:
                    Path(save_models).mkdir(parents=True, exist_ok=True)
                    model.save_model(str(Path(save_models) / f"{e}_W{li + 1}.txt"))
                imp = model.feature_importance("gain")
                importances.setdefault(f"{e}_W{li + 1}", []).append((imp / imp.sum()).tolist())

                for y in test_years:
                    a, _, (iss, blk, ok) = rows(y, clim_by_lead(clim_test), uo_test, sub=False, sigs=sig_test,
                                                keep=iod_test)
                    p = np.full(len(iss) * len(blk), np.nan, np.float32)
                    p[ok] = model.predict(a, num_threads=THREADS)
                    pred[e][yidx[y], :, li, :] = p.reshape(len(iss), len(blk))
                print(f"{e} fold {fa}-{fb} W{li + 1}: {model.best_iteration} trees, "
                      f"{sum(map(len, ytr)):,} rows, {time.time() - t0:.0f}s", flush=True)

    tag = ("_fast" if fast else "") + ("_v2" if v2 else "")
    if only_fold is not None:
        # a check, not a new result: the re-trained fold must reproduce the published predictions
        old = xr.open_dataset(PROCESSED / f"gbm_pred{tag}.nc")
        fa, fb = FOLDS[only_fold]
        yi = [yidx[y] for y in YEARS if fa <= y <= fb]
        for e in EVENTS:
            a, b = pred[e][yi], old[e].values[yi]
            m = np.isfinite(a) & np.isfinite(b)
            d = np.abs(a[m] - b[m])
            print(f"check {e} fold {fa}-{fb}: max |diff| {d.max():.2e}, mean {d.mean():.2e} over {m.sum():,} forecasts")
        return
    ds = xr.Dataset({e: (("year", "issue", "lead", "block"), pred[e]) for e in EVENTS},
                    coords=tg.coords)
    ds.to_netcdf(PROCESSED / f"gbm_pred{tag}.nc", encoding={e: {"zlib": True} for e in EVENTS})

    clim = xr.open_dataset(PROCESSED / "clim_folds.nc")
    scores = {}
    for e in EVENTS:
        t = tg[e].values.astype(np.int8)
        p = np.where(np.isnan(pred[e]), clim[e].values, pred[e])
        scores[e] = summary(p, clim[e].values, t, all_years)
        print(f"\n{e}: " + "  ".join(
            f"W{k}: BSS {scores[e][f'W{k}']['bss']:+.3f} AUC {scores[e][f'W{k}']['auc']:.3f}"
            f" (clim {summary(clim[e].values, clim[e].values, t, all_years)[f'W{k}']['auc']:.3f})"
            for k in (1, 2, 3, 4)) + f"  | reliability error {scores[e]['reliability_error']:.4f}")
    imp_mean = {k: dict(zip(fnames, np.mean(v, 0).round(4).tolist())) for k, v in importances.items()}
    json.dump({"scores": scores, "importance": imp_mean}, open(PROCESSED / f"gbm_scores{tag}.json", "w"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--v2", action="store_true", help="teleconnection signatures instead of raw indices")
    ap.add_argument("--only-fold", type=int, help="re-train this fold only (0-4); see module doc")
    ap.add_argument("--save-models", help="directory to save the fold's boosters")
    a = ap.parse_args()
    main(a.fast, a.v2, a.only_fold, a.save_models)
