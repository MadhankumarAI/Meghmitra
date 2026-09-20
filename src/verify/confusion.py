"""Classification metrics at the operating points the product actually uses.

  python src/verify/confusion.py

Scored on held-out years only (1991-2025, five 7-year blocks), from gbm_pred_fast.nc against
targets.nc, exactly the arrays the Brier scores come from. Operating points are read from the
code that issues advice, not chosen to flatter the numbers:

  dry10   p >= 0.50 and p - climatology >= 0.12     (advisory/engine.py: DELAY_SOWING, CONSERVE)
  dry10   p - climatology >= 0.05                   (forecast_json.py: CMRI Watch)
  heavy   p >= 0.30 and p >= 3 x climatology        (forecast_json.py: heavy alert)
  onset   p >= 0.50                                 (the plain half-chance line)
"""
import sys, json
from pathlib import Path
import numpy as np
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import PROCESSED, EXPORTS

P = PROCESSED
EVAL = (1991, 2025)


def counts(flag, t):
    ok = t >= 0
    f, y = flag[ok], t[ok].astype(bool)
    tp = int(np.count_nonzero(f & y))
    fp = int(np.count_nonzero(f & ~y))
    fn = int(np.count_nonzero(~f & y))
    tn = int(np.count_nonzero(~f & ~y))
    return tp, fp, fn, tn


def row(name, event, week, tp, fp, fn, tn):
    prec = tp / max(tp + fp, 1)
    rec = tp / max(tp + fn, 1)
    f1 = 2 * prec * rec / max(prec + rec, 1e-9)
    n = tp + fp + fn + tn
    return dict(operating_point=name, event=event, week=week,
                precision=round(prec, 4), recall=round(rec, 4), f1=round(f1, 4),
                false_alarm_ratio=round(1 - prec, 4),
                specificity=round(tn / max(tn + fp, 1), 4),
                base_rate=round((tp + fn) / max(n, 1), 4),
                flagged_share=round((tp + fp) / max(n, 1), 4),
                lift=round(prec / max((tp + fn) / max(n, 1), 1e-9), 2),
                tp=tp, fp=fp, fn=fn, tn=tn, n=n)


def main():
    tg = xr.open_dataset(P / "targets.nc")
    clim = xr.open_dataset(P / "clim_folds.nc")
    pred = xr.open_dataset(P / "gbm_pred_fast.nc")
    years = tg.year.values
    sel = (years >= EVAL[0]) & (years <= EVAL[1])
    out = []
    for event in ("dry10", "heavy", "onset"):
        t_all = tg[event].values[sel].astype(np.int8)
        c_all = clim[event].values[sel]
        p_all = pred[event].values[sel]
        p_all = np.where(np.isnan(p_all), c_all, p_all)
        for k in range(4):
            p, c, t = p_all[:, :, k, :], c_all[:, :, k, :], t_all[:, :, k, :]
            if event == "dry10":
                out.append(row("advisory: p>=0.50 and departure>=0.12", event, k + 1,
                               *counts((p >= 0.5) & (p - c >= 0.12), t)))
                out.append(row("CMRI Watch: departure>=0.05", event, k + 1,
                               *counts(p - c >= 0.05, t)))
                out.append(row("plain p>=0.50", event, k + 1, *counts(p >= 0.5, t)))
            elif event == "heavy":
                out.append(row("alert: p>=0.30 and p>=3x climatology", event, k + 1,
                               *counts((p >= 0.3) & (p >= 3 * np.maximum(c, 0.01)), t)))
            else:
                out.append(row("plain p>=0.50", event, k + 1, *counts(p >= 0.5, t)))
            print(out[-1])
    EXPORTS.mkdir(parents=True, exist_ok=True)
    (EXPORTS / "confusion.json").write_text(json.dumps({"operating_points": out}, indent=1))
    print(f"-> {EXPORTS / 'confusion.json'}")


if __name__ == "__main__":
    main()
