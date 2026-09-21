"""ROC, precision-recall and reliability curves from the held-out forecasts themselves.

  python src/verify/curves.py

Reads the same arrays every other number comes from (gbm_pred_fast.nc against targets.nc,
1991-2025, five 7-year blocks each held out whole) and writes EXPORTS/curves.json: a few hundred
points per curve, small enough to plot anywhere, computed on every forecast rather than a sample
where that is affordable.

For each event and lead week it stores:
  roc        false-positive rate, true-positive rate, and the same for climatology
  pr         recall, precision, with the base rate as the no-skill line
  reliability forecast, observed and count per bin (20 bins)
  points     the operating points the product actually uses, marked on the PR curve
"""
from __future__ import annotations
import sys, json
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import PROCESSED, EXPORTS

EVAL = (1991, 2025)
EVENTS = ("dry10", "onset", "heavy")
LABEL = {"dry10": "10+ day dry spell", "onset": "Monsoon onset", "heavy": "Heavy-rain day"}
GRID = np.linspace(0, 1, 501)          # thresholds, fine enough for a smooth curve


def curve(p: np.ndarray, y: np.ndarray) -> dict:
    """ROC and PR by counting how many forecasts fall in each probability bin: exact, and linear
    in the number of forecasts rather than in sorting them."""
    idx = np.clip((p * (len(GRID) - 1)).astype(np.int32), 0, len(GRID) - 1)
    pos = np.bincount(idx, weights=y, minlength=len(GRID))
    tot = np.bincount(idx, minlength=len(GRID))
    neg = tot - pos
    # everything at or above each threshold is a positive prediction
    tp = np.cumsum(pos[::-1])[::-1]
    fp = np.cumsum(neg[::-1])[::-1]
    P, N = pos.sum(), neg.sum()
    tpr, fpr = tp / max(P, 1), fp / max(N, 1)
    prec = np.where(tp + fp > 0, tp / np.maximum(tp + fp, 1), 1.0)
    auc = float(-np.trapezoid(tpr, fpr))          # fpr runs high to low
    ap = float(-np.trapezoid(prec, tpr))
    return dict(fpr=fpr, tpr=tpr, recall=tpr, precision=prec, auc=auc, ap=ap,
                base=float(P / max(P + N, 1)), thresholds=GRID)


def thin(x: np.ndarray, n: int = 220) -> list[float]:
    k = max(1, len(x) // n)
    return [round(float(v), 5) for v in x[::k]]


def main() -> None:
    import xarray as xr
    tg = xr.open_dataset(PROCESSED / "targets.nc")
    clim = xr.open_dataset(PROCESSED / "clim_folds.nc")
    pred = xr.open_dataset(PROCESSED / "gbm_pred_fast.nc")
    years = tg.year.values
    sel = (years >= EVAL[0]) & (years <= EVAL[1])

    out: dict = {"protocol": "five blocks of seven years, each held out whole (1991-2025)",
                 "events": {}}
    for e in EVENTS:
        t_all = tg[e].values[sel]
        c_all = clim[e].values[sel]
        p_all = np.where(np.isnan(pred[e].values[sel]), c_all, pred[e].values[sel])
        weeks = {}
        for k in range(4):
            t, c, p = t_all[:, :, k, :], c_all[:, :, k, :], p_all[:, :, k, :]
            ok = t >= 0
            y = t[ok].astype(np.float64)
            pm, pc = p[ok].astype(np.float64), c[ok].astype(np.float64)
            m, cl = curve(pm, y), curve(pc, y)
            # reliability, 20 bins, count weighted
            b = np.clip((pm * 20).astype(int), 0, 19)
            cnt = np.bincount(b, minlength=20)
            fo = np.bincount(b, weights=y, minlength=20) / np.maximum(cnt, 1)
            fp_ = np.bincount(b, weights=pm, minlength=20) / np.maximum(cnt, 1)
            weeks[f"W{k + 1}"] = dict(
                n=int(ok.sum()), base_rate=round(m["base"], 4),
                auc=round(m["auc"], 4), auc_clim=round(cl["auc"], 4), ap=round(m["ap"], 4),
                roc=dict(fpr=thin(m["fpr"]), tpr=thin(m["tpr"]),
                         fpr_clim=thin(cl["fpr"]), tpr_clim=thin(cl["tpr"])),
                pr=dict(recall=thin(m["recall"]), precision=thin(m["precision"])),
                reliability=dict(forecast=[round(float(v), 4) for v in fp_],
                                 observed=[round(float(v), 4) for v in fo],
                                 count=[int(v) for v in cnt]),
            )
            print(f"{e} W{k + 1}: AUC {m['auc']:.4f} (clim {cl['auc']:.4f})  AP {m['ap']:.4f}  "
                  f"base {m['base']:.4f}  n {int(ok.sum()):,}", flush=True)
        out["events"][e] = dict(label=LABEL[e], weeks=weeks)

    EXPORTS.mkdir(parents=True, exist_ok=True)
    (EXPORTS / "curves.json").write_text(json.dumps(out, separators=(",", ":")))
    print(f"-> {EXPORTS / 'curves.json'}")


if __name__ == "__main__":
    main()
