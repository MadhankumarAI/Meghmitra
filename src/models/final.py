"""Train and save the operational (live) models on every year 1991-2025.

Validation (gbm.py) trains one model per held-out 7-year block and scores it on that
block. For live use we want one model per (event, lead) that has seen every year, with
exactly the same features and settings as the published v1 ("fast") configuration.

Training rows use each year's out-of-fold climatology (clim_folds.nc), the same way the
validated models saw it; at prediction time the climatology is estimated from all years.

  python final.py            -> PROCESSED/final_models/{event}_W{k}.txt + meta.json + clim_all.npz
"""
from __future__ import annotations
import os, sys, json, time
from pathlib import Path
import numpy as np
import xarray as xr
import lightgbm as lgb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import PROCESSED
from models.climatology import fold_of, smooth
from models.gbm import PARAMS, THREADS, estimate, usual_onset

EVENTS = ("onset", "dry10", "heavy")          # what the live export and advisories use
YEARS = np.arange(1991, 2026)
STEP, BLOCK_FRAC = 5, 0.5                     # the published v1 ("fast") sampling
OUT = PROCESSED / "final_models"


def main():
    OUT.mkdir(exist_ok=True)
    tg = xr.open_dataset(PROCESSED / "targets.nc")
    clim_oof = xr.open_dataset(PROCESSED / "clim_folds.nc")
    lab = xr.open_dataset(PROCESSED / "imd_block_labels.nc")
    names = json.loads((PROCESSED / "features" / "names.json").read_text())
    fnames = names + ["clim", "usual_onset", "days_vs_usual"]
    all_years = tg.year.values
    yidx = {int(y): i for i, y in enumerate(all_years)}
    I, B = tg.sizes["issue"], tg.sizes["block"]
    doy_col = names.index("doy")
    X = {y: np.load(PROCESSED / "features" / f"{y}.npz")["X"] for y in YEARS}
    rng = np.random.default_rng(0)
    folds = np.array([fold_of(int(y)) for y in all_years])

    # usual onset per training year: without that year's fold (as validation did)
    uo_oof = {g: usual_onset(lab.true_onset_doy.values, lab.year.values,
                             [y for y in lab.year.values if fold_of(int(y)) != g]) for g in range(5)}
    uo_all = usual_onset(lab.true_onset_doy.values, lab.year.values, list(lab.year.values))
    clim_all = {}
    val_years = set(rng.choice(YEARS, 4, replace=False).tolist())
    t0 = time.time()
    meta = {"features": fnames, "events": list(EVENTS), "val_years": sorted(int(v) for v in val_years),
            "sampling": {"issue_step": STEP, "block_frac": BLOCK_FRAC}, "models": {}}
    for e in EVENTS:
        T = tg[e].values.astype(np.int8)
        H, V = smooth(T == 1).astype(np.float32), smooth(T >= 0).astype(np.float32)
        clim_all[e] = estimate(H, V, np.ones(len(all_years), bool))          # (I, L, B) from all years
        C = clim_oof[e].values                                               # (Y, I, L, B)
        for li in range(4):
            Xtr, ytr, Xva, yva = [], [], [], []
            for y in YEARS:
                iss = np.arange(0, I, STEP)
                blk = np.sort(rng.choice(B, int(B * BLOCK_FRAC), replace=False))
                xs = X[y][np.ix_(iss, blk)]
                c = C[yidx[y]][np.ix_(iss, [li], blk)][:, 0]
                u = np.broadcast_to(uo_oof[fold_of(int(y))][blk], (len(iss), len(blk)))
                feat = np.concatenate([xs, c[..., None], u[..., None], (xs[..., doy_col] - u)[..., None]], -1)
                lab_ = T[yidx[y]][np.ix_(iss, [li], blk)][:, 0]
                feat, lab_ = feat.reshape(-1, feat.shape[-1]), lab_.ravel()
                ok = lab_ >= 0
                (Xva if y in val_years else Xtr).append(feat[ok])
                (yva if y in val_years else ytr).append(lab_[ok])
            dtr = lgb.Dataset(np.concatenate(Xtr), np.concatenate(ytr), feature_name=fnames, free_raw_data=True)
            dva = lgb.Dataset(np.concatenate(Xva), np.concatenate(yva), reference=dtr)
            m = lgb.train({**PARAMS, "num_threads": THREADS}, dtr, num_boost_round=1500, valid_sets=[dva],
                          callbacks=[lgb.early_stopping(50, verbose=False)])
            path = OUT / f"{e}_W{li + 1}.txt"
            m.save_model(str(path), num_iteration=m.best_iteration)
            meta["models"][f"{e}_W{li + 1}"] = {"trees": int(m.best_iteration), "rows": int(sum(map(len, ytr)))}
            print(f"{e} W{li + 1}: {m.best_iteration} trees, {time.time() - t0:.0f}s", flush=True)
    np.savez_compressed(OUT / "clim_all.npz", **clim_all, usual_onset=uo_all,
                        issue=tg.issue.values, block=tg.block.values)
    (OUT / "meta.json").write_text(json.dumps(meta, indent=1))
    print("saved to", OUT)


if __name__ == "__main__":
    main()
