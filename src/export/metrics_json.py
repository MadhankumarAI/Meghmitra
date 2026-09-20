"""Export verification results for the Science page (runs on the server).

  python metrics_json.py fast [fast_v2 ...]      model tags = suffixes of gbm_pred_{tag}.nc

Writes EXPORTS/metrics.json:
  { protocol, eval_years, models: { tag: { event: {
        leads: [{week, bss, auc, auc_clim, brier, brier_clim, base_rate, n}],
        reliability: {forecast: [..], observed: [..], count: [..]}, reliability_error } } },
    skill_map: { tag: { event: [[B ints: BSS x100, clipped -100..100] x 4 weeks] } } }
Every number is scored only on years the model never saw (five 7-year blocks).
"""
from __future__ import annotations
import os, sys, json
from pathlib import Path
import numpy as np
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify.score import summary, bss_map, EVAL_YEARS          # noqa: E402

DATA = Path(os.environ.get("MORPHY_DATA", Path.home() / "morphy" / "data"))
P, EXPORTS = DATA / "processed", DATA / "exports"
EVENTS = ("onset", "dry10", "dry7", "heavy")


def main(tags):
    tg = xr.open_dataset(P / "targets.nc")
    clim = xr.open_dataset(P / "clim_folds.nc")
    years = tg.year.values
    out = {"protocol": "Five blocks of 7 consecutive years (1991-2025), each held out whole",
           "eval_years": list(EVAL_YEARS), "models": {}, "skill_map": {}}
    clim_auc = {}
    for e in EVENTS:
        t = tg[e].values.astype(np.int8)
        c = clim[e].values
        s = summary(c, c, t, years)
        clim_auc[e] = [s[f"W{k}"]["auc"] for k in (1, 2, 3, 4)]
    for tag in tags:
        pred = xr.open_dataset(P / f"gbm_pred_{tag}.nc")
        out["models"][tag], out["skill_map"][tag] = {}, {}
        for e in EVENTS:
            t = tg[e].values.astype(np.int8)
            c = clim[e].values
            p = pred[e].values
            p = np.where(np.isnan(p), c, p)
            s = summary(p, c, t, years)
            out["models"][tag][e] = {
                "leads": [{"week": k, **{m: round(s[f"W{k}"][m], 4) for m in
                           ("bss", "auc", "brier", "brier_clim", "base_rate")},
                           "auc_clim": round(clim_auc[e][k - 1], 4), "n": s[f"W{k}"]["n"]}
                          for k in (1, 2, 3, 4)],
                "reliability": dict(zip(("forecast", "observed", "count"),
                                        [[round(v, 4) for v in x] for x in s["reliability"]])),
                "reliability_error": round(s["reliability_error"], 4),
            }
            m = bss_map(p, c, t, years)                      # (lead, block)
            out["skill_map"][tag][e] = np.clip(np.nan_to_num(m * 100), -100, 100).round().astype(int).tolist()
            print(f"{tag} {e}: W1 BSS {s['W1']['bss']:+.3f} ... W4 {s['W4']['bss']:+.3f}", flush=True)
    f = EXPORTS / "metrics.json"
    f.write_text(json.dumps(out, separators=(",", ":")))
    print(f"{f} {f.stat().st_size / 1e3:.0f} kB")


if __name__ == "__main__":
    main(sys.argv[1:] or ["fast"])
