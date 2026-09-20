"""Ideas we tested and rejected, scored side by side with what we shipped.

  python experiments_json.py

Reads the scoring runs themselves - the shipped one and the ones kept from each experiment -
and writes EXPORTS/experiments.json, so the numbers on the Evidence page are the same numbers
the training run printed. Nothing here is typed in by hand.

Runs kept in PROCESSED:
  gbm_scores_fast.json       shipped (local rainfall + MJO + ENSO)
  gbm_scores_fast.iod.json   the same, with the Indian Ocean Dipole added (features/iod.py)
  gbm_scores_fast_v2.json    per-block teleconnection signatures learnt from data
"""
from __future__ import annotations
import sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import PROCESSED, EXPORTS

EVENT_LABEL = {"onset": "Monsoon onset", "dry10": "10+ day dry spell", "dry7": "7+ day dry spell",
               "heavy": "Heavy-rain day"}

TRIED = [
    dict(key="iod", file="gbm_scores_fast.iod.json",
         title="Adding the Indian Ocean Dipole",
         idea="The other big planetary lever on the monsoon: NOAA ERSST v5 sea-surface temperatures, the "
              "Saji (1999) boxes, published with a 12-day lag, its climatology refitted inside every fold.",
         found="Every dry-spell lead lost skill and the trees still spent 5-8% of their gain on it. With "
               "about 35 independent seasons the dipole barely moves inside a held-out 7-year block, so a "
               "split on it is really a split on which years the block contains.",
         verdict="Not shipped. The code is kept, switched off."),
    dict(key="v2", file="gbm_scores_fast_v2.json",
         title="Per-block teleconnection signatures",
         idea="Let each block learn its own response to the MJO and ENSO instead of sharing one, and feed "
              "those signatures to the model.",
         found="It recovered the textbook MJO rainfall pattern from data alone, which was a good sign, but "
               "from week 2 onwards it scored a little below the simpler model.",
         verdict="Not shipped. We kept the simpler model."),
]


def main() -> None:
    ship = json.loads((PROCESSED / "gbm_scores_fast.json").read_text())["scores"]
    out = []
    for t in TRIED:
        p = PROCESSED / t["file"]
        if not p.exists():
            print(f"skipped {t['key']}: no {p.name}")
            continue
        alt = json.loads(p.read_text())["scores"]
        cells = []
        for e in ship:
            if e not in alt:
                continue
            for w in ship[e]:
                a, b = ship[e][w], alt[e].get(w)
                if not isinstance(a, dict) or not isinstance(b, dict):
                    continue
                cells.append(dict(event=e, label=EVENT_LABEL.get(e, e), week=int(w[1:]),
                                  shipped=round(a["bss"], 4), variant=round(b["bss"], 4)))
        if not cells:
            continue
        mean = sum(c["variant"] - c["shipped"] for c in cells) / len(cells)
        out.append({k: t[k] for k in ("key", "title", "idea", "found", "verdict")}
                   | dict(cells=cells, mean_bss_change=round(mean, 5)))
        print(f"{t['key']}: {len(cells)} cells, mean BSS change {mean:+.5f}")

    EXPORTS.mkdir(parents=True, exist_ok=True)
    (EXPORTS / "experiments.json").write_text(json.dumps({"tried": out}, separators=(",", ":")))
    print(f"-> {EXPORTS / 'experiments.json'}")


if __name__ == "__main__":
    main()
