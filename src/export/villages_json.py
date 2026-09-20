"""Village and panchayat lookup for the console: name -> the block that forecasts it.

  python src/export/villages_json.py                 every state that has villages built
  python src/export/villages_json.py --state Karnataka

Writes EXPORTS/villages/{state}.json, one compact array per village:

  ["Kengeri", "<block_id>", lat, lon]

so the console can resolve the name a farmer uses ("Kengeri") to the block the forecast is issued
for ("Bengaluru South"), and say so on screen. The forecast itself stays at block scale; this file
carries no probabilities.
"""
from __future__ import annotations
import sys, json, argparse
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import PROCESSED, EXPORTS

OUT = EXPORTS / "villages"


def sources(state: str | None) -> list[Path]:
    if state:
        p = PROCESSED / f"villages_{state.lower()}.parquet"
        return [p] if p.exists() else [PROCESSED / "villages.parquet"]
    got = sorted(PROCESSED.glob("villages_*.parquet"))
    nat = PROCESSED / "villages.parquet"
    return got or ([nat] if nat.exists() else [])


def main(state: str | None) -> None:
    files = sources(state)
    if not files:
        sys.exit("no villages parquet found. Run: python src/data/villages.py build --state Karnataka")
    OUT.mkdir(parents=True, exist_ok=True)
    index = {}
    for f in files:
        v = pd.read_parquet(f)
        if state:
            v = v[v["state"].str.casefold() == state.casefold()]
        for st, g in v.groupby("state"):
            if not st:
                continue
            rows = [[r["name"], r["block_id"], round(float(r["lat"]), 4), round(float(r["lon"]), 4)]
                    for _, r in g.sort_values("name").iterrows()]
            key = st.lower().replace(" ", "-")
            (OUT / f"{key}.json").write_text(
                json.dumps({"state": st, "villages": rows}, separators=(",", ":")), encoding="utf-8")
            index[key] = {"state": st, "n": len(rows)}
            print(f"{st}: {len(rows):,} villages -> {OUT / (key + '.json')}")
    (OUT / "index.json").write_text(json.dumps(index, separators=(",", ":")), encoding="utf-8")
    print(f"-> {OUT / 'index.json'} ({len(index)} state(s))")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state", default=None)
    main(ap.parse_args().state)
