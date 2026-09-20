"""Did the advice come true? Outcome rates of issued advisories against observed IMD rainfall.

  python advice_hits.py 2023

For every block-day that got an advisory (crops at the same block share one decision, so each
block-day-template is counted once), look up what actually happened in the lead week the advice
was about (features/targets.py: same event definitions the model is trained on):

  DELAY_SOWING, PREPARE_IRRIGATION, DRY_SPELL_CONSERVE_MOISTURE   a 10+ day dry spell in week k
  HEAVY_RAIN_PROTECT                                              a heavy-rain day in week k
  SOW_NOW                                                         true onset within 2 weeks
  SWITCH_CROP                                                     NO onset within 2 weeks

and compare with the chance the model gave, the block's usual chance, and the rate over all
monsoon blocks that day. Writes EXPORTS/advice_skill_{year}.json for the Evidence page.
"""
from __future__ import annotations
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import PROCESSED, EXPORTS

DRY = ("DELAY_SOWING", "PREPARE_IRRIGATION", "DRY_SPELL_CONSERVE_MOISTURE")


def main(year: int):
    tg = xr.open_dataset(PROCESSED / "targets.nc").sel(year=year)
    dry10, heavy, onset = (tg[v].values.astype(np.int8) for v in ("dry10", "heavy", "onset"))   # (I, L, B)
    issues = tg.issue.values
    acc: dict[str, dict[str, list]] = {}
    for i, doy in enumerate(issues):
        d = (pd.Timestamp(year, 1, 1) + pd.Timedelta(days=int(doy) - 1)).strftime("%Y-%m-%d")
        f = EXPORTS / "advisory" / f"{d}.json"
        fc = EXPORTS / "forecast" / f"{d}.json"
        if not f.exists() or not fc.exists():
            continue
        adv = json.loads(f.read_text())["advisories"]
        cm = np.array(json.loads(fc.read_text())["cmri"][0])
        monsoon = cm >= 0
        seen = set()
        for key, rows in adv.items():
            b = int(key)
            for _, tid, _, p in rows:
                k = int(p.get("lead_week", 1)) - 1
                if (b, tid, k) in seen:
                    continue
                seen.add((b, tid, k))
                if tid in DRY:
                    hit, base = dry10[i, k, b], dry10[i, k][monsoon].mean()
                    fp, cp = p.get("p_event"), p.get("p_clim")
                elif tid == "HEAVY_RAIN_PROTECT":
                    hit, base = heavy[i, k, b], heavy[i, k][monsoon].mean()
                    fp, cp = p.get("p_event"), p.get("p_clim")
                elif tid in ("SOW_NOW", "SWITCH_CROP"):
                    o = onset[i, :2, b]
                    if (o < 0).any():
                        continue                               # onset status not applicable
                    came = int((o == 1).any())
                    ok_all = (onset[i, :2] >= 0).all(0) & monsoon
                    came_all = ((onset[i, :2] == 1).any(0))[ok_all].mean()
                    if tid == "SOW_NOW":
                        hit, base, fp, cp = came, came_all, p.get("p_onset"), None
                    else:
                        hit, base, fp, cp = 1 - came, 1 - came_all, None, None
                else:
                    continue
                a = acc.setdefault(tid, {"hit": [], "base": [], "p": [], "c": []})
                a["hit"].append(int(hit)); a["base"].append(float(base))
                if fp is not None: a["p"].append(float(fp))
                if cp is not None: a["c"].append(float(cp))
    rows = []
    for tid, a in sorted(acc.items(), key=lambda kv: -len(kv[1]["hit"])):
        rows.append({"template": tid, "n": len(a["hit"]), "came_true": round(float(np.mean(a["hit"])), 3),
                     "all_blocks": round(float(np.mean(a["base"])), 3),
                     "forecast": round(float(np.mean(a["p"])), 3) if a["p"] else None,
                     "usual": round(float(np.mean(a["c"])), 3) if a["c"] else None})
        r = rows[-1]
        print(f"{tid:28s} n={r['n']:6d}  came true {r['came_true']:.0%}  (model said {r['forecast']}, usual {r['usual']}, "
              f"all monsoon blocks {r['all_blocks']:.0%})")
    out = EXPORTS / f"advice_skill_{year}.json"
    out.write_text(json.dumps({"year": year, "rows": rows}, indent=1))
    print(f"-> {out}")


if __name__ == "__main__":
    main(int(sys.argv[1]))
