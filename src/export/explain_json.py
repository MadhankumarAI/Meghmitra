"""Why the model said what it said: exact per-block driver contributions for week 1.

LightGBM's pred_contrib gives tree-SHAP values: per-feature contributions in log-odds that,
with the model's bias, add up EXACTLY to each forecast. We group the 31 features into six
drivers an officer can reason about, and check the sum against the published probability.

  python explain_json.py 2023            the replay season, with the fold models that never saw
                                         2019-2025 (models/gbm.py --only-fold 4 --save-models)
  (live)                                 run_live.py calls write() with the final models

Writes EXPORTS/explain/{date}.json:
  {issued, model, scale, groups, events: {event: {group: [int per block]}}, raw: {...}, planet: {...}}
Contributions are log-odds x SCALE as ints; -32768 = not applicable (e.g. onset already came).
"""
from __future__ import annotations
import sys, json
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SCALE = 100
NA = -32768
EVENTS = ("onset", "dry10", "heavy")
# drivers, in the words the console uses (web/src/lib/explain.ts); "normal" also takes the bias
GROUPS = {
    "normal": ["clim", "usual_onset", "days_vs_usual", "doy", "lat", "lon", "log_area"],
    "recent": ["r1", "r3", "r7", "r14", "r30", "wet14", "dry_run", "season_rain"],
    "progress": ["cand_count", "days_since_cand", "onset_confirmed", "days_since_conf_onset"],
    "around": ["r7_150km", "r7_400km", "cand_share_150km", "cand_share_400km", "conf_share_400km", "dry_run_150km"],
    "mjo": ["mjo_pc1", "mjo_pc2", "mjo_amp", "mjo_sin", "mjo_cos"],
    "enso": ["nino34"],
}


def contributions(model, feat: np.ndarray, fnames: list[str]) -> tuple[dict[str, np.ndarray], np.ndarray]:
    """Grouped log-odds contributions (B,) per driver, and the model probability they add up to."""
    c = model.predict(feat, pred_contrib=True)                  # (B, F + 1); last column = bias
    col = {n: i for i, n in enumerate(fnames)}
    missing = set(fnames) - {n for g in GROUPS.values() for n in g}
    assert not missing, f"features without a driver group: {missing}"
    out = {g: c[:, [col[n] for n in names if n in col]].sum(1) for g, names in GROUPS.items()}
    out["normal"] = out["normal"] + c[:, -1]
    total = sum(out.values())
    return out, 1 / (1 + np.exp(-total))


def mjo_phase(sin: float, cos: float) -> int:
    """Wheeler-Hendon phase 1-8 from the angle the index code stores (data/indices.py)."""
    ang = np.arctan2(sin, cos)
    return int(((ang + np.pi) // (np.pi / 4)) % 8) + 1


def write(path: Path, issued: str, model_note: str, groups: dict[str, dict[str, np.ndarray]],
          applicable: dict[str, np.ndarray], raw: dict[str, np.ndarray], planet: dict) -> None:
    ev = {}
    for e, g in groups.items():
        ok = applicable[e]
        ev[e] = {k: np.where(ok, np.clip(np.round(v * SCALE), -32767, 32767), NA).astype(int).tolist() for k, v in g.items()}
    out = {"issued": issued, "model": model_note, "scale": SCALE, "na": NA, "week": 1,
           "groups": list(GROUPS), "events": ev,
           "raw": {k: np.round(v).astype(int).tolist() for k, v in raw.items()}, "planet": planet}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, separators=(",", ":")))


def raw_values(x: np.ndarray, names: list[str]) -> dict[str, np.ndarray]:
    """The few observed numbers the explanation quotes (per block)."""
    n = {k: i for i, k in enumerate(names)}
    return {"r7": x[:, n["r7"]], "r30": x[:, n["r30"]], "dry_run": x[:, n["dry_run"]],
            "r7_400km": x[:, n["r7_400km"]], "front_400km": x[:, n["cand_share_400km"]] * 100}


def planet_values(x0: np.ndarray, names: list[str]) -> dict:
    n = {k: i for i, k in enumerate(names)}
    amp = float(x0[n["mjo_amp"]])
    return {"mjo_amp": round(amp, 2) if np.isfinite(amp) else None,
            "mjo_phase": mjo_phase(float(x0[n["mjo_sin"]]), float(x0[n["mjo_cos"]])) if np.isfinite(amp) else None,
            "nino34": round(float(x0[n["nino34"]]), 2) if np.isfinite(x0[n["nino34"]]) else None}


def season(year: int) -> None:
    """Replay season: same rows as gbm.py's test rows for the fold holding out `year`."""
    import xarray as xr
    import pandas as pd
    import lightgbm as lgb
    from config import PROCESSED, EXPORTS
    from models.climatology import FOLDS, fold_of, smooth
    from models.gbm import estimate, usual_onset

    f = fold_of(year)
    fa, fb = FOLDS[f]
    mdir = PROCESSED / "fold_models" / f"f{f}_fast"
    tg = xr.open_dataset(PROCESSED / "targets.nc")
    all_years = tg.year.values
    folds_all = np.array([fold_of(int(y)) for y in all_years])
    lab = xr.open_dataset(PROCESSED / "imd_block_labels.nc")
    uo = usual_onset(lab.true_onset_doy.values, lab.year.values,
                     [y for y in lab.year.values if fold_of(int(y)) != f])
    names = json.loads((PROCESSED / "features" / "names.json").read_text())
    X = np.load(PROCESSED / "features" / f"{year}.npz")["X"]                # (I, B, F)
    doy_col = names.index("doy")
    fnames = names + ["clim", "usual_onset", "days_vs_usual"]
    published = xr.open_dataset(PROCESSED / "gbm_pred_fast.nc").sel(year=year)
    yi = int(np.where(all_years == year)[0][0])
    issues = tg.issue.values

    clim, models, pub_p, label = {}, {}, {}, {}
    for e in EVENTS:
        T = tg[e].values.astype(np.int8)
        label[e] = T[yi, :, 0]                                          # (I, B), read once
        pub_p[e] = published[e].values[:, 0]                            # (I, B)
        clim[e] = np.moveaxis(estimate(smooth(T == 1).astype(np.float32), smooth(T >= 0).astype(np.float32), folds_all != f), 1, 0)[0]
        models[e] = lgb.Booster(model_file=str(mdir / f"{e}_W1.txt"))
    worst = 0.0
    for i, doy in enumerate(issues):
        x = X[i]
        # [features, clim (filled per event), usual onset, days vs usual]: gbm.py's column order
        feat = np.concatenate([x, np.zeros((x.shape[0], 1), np.float32),
                               uo[:, None], (x[:, doy_col] - uo)[:, None]], -1)
        groups, appl = {}, {}
        for e in EVENTS:
            feat[:, len(names)] = clim[e][i]
            g, p = contributions(models[e], feat, fnames)
            pub = pub_p[e][i]
            ok = np.isfinite(pub) & (label[e][i] >= 0)
            worst = max(worst, float(np.nanmax(np.abs(p[ok] - pub[ok]))) if ok.any() else 0.0)
            groups[e], appl[e] = g, ok
        d = (pd.Timestamp(year, 1, 1) + pd.Timedelta(days=int(doy) - 1)).strftime("%Y-%m-%d")
        write(EXPORTS / "explain" / f"{d}.json", d, f"v1 gradient boosting, fold {fa}-{fb} (never saw {fa}-{fb})",
              groups, appl, raw_values(x, names), planet_values(x[0], names))
    print(f"explain {year}: {len(issues)} days; max |model - published| = {worst:.2e}")


if __name__ == "__main__":
    season(int(sys.argv[1]))
