"""What a village adds to its block's forecast, in percentage points, per half-month.

  python src/export/villages_clim_json.py

The model forecasts a block. Inside that block, CHIRPS at 5 km says which villages are normally
drier than the block average and which are wetter (features/village_clim.py). That difference,
and only that difference, is what a village adds:

    chance for this village = chance for the block + (village normal - block normal)

Both normals come from the same CHIRPS record, so the correction carries no cross-dataset bias,
and it is zero where a village sits on its block's average.

Writes EXPORTS/villages/clim/{block index}.json:

    {"w": [121, 136, ...],
     "v": {"Kengeri Gollahalli": [-3, -2, 0, ...]},      dry spell
     "h": {"Kengeri Gollahalli": [ 1,  0, 2, ...]}}      heavy-rain day

one entry per village, in whole percentage points, per half-month window of the season. "h" is
absent in files written before heavy rain was computed, and the console simply shows no village
adjustment for that layer when it is.
"""
from __future__ import annotations
import sys, json, glob
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import PROCESSED, EXPORTS

OUT = EXPORTS / "villages" / "clim"
CLIM = PROCESSED / "village_clim.npz"
LAT0, LON0, RES = 6.025, 66.025, 0.05          # CHIRPS India grid, cell centres


def main() -> None:
    if not CLIM.exists():
        sys.exit(f"{CLIM} not found. Run: python src/features/village_clim.py (on the server)")
    z = np.load(CLIM)
    cell, block_clim, windows = z["cell"], z["block"], z["windows"]
    # heavy rain is only in files written by the current features/village_clim.py
    heavy = ("cell_heavy" in z.files, z["cell_heavy"] if "cell_heavy" in z.files else None,
             z["block_heavy"] if "block_heavy" in z.files else None)
    if not heavy[0]:
        print("   no heavy-rain climatology in the npz: writing dry spell only "
              "(re-run src/features/village_clim.py where CHIRPS lives)")

    idx_file = EXPORTS / "blocks_index.json"
    pos = {b["id"]: b["i"] for b in json.loads(idx_file.read_text(encoding="utf-8"))}
    blocks = pd.read_parquet(PROCESSED / "blocks.parquet")["block_id"].tolist()
    row_of = {b: i for i, b in enumerate(blocks)}       # order of the block axis in village_clim

    files = sorted(glob.glob(str(PROCESSED / "villages_*.parquet"))) or [str(PROCESSED / "villages.parquet")]
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.json"):
        f.unlink()

    per_block: dict[int, dict[str, list[int]]] = {}
    per_block_h: dict[int, dict[str, list[int]]] = {}
    total, off_grid = 0, 0
    for f in files:
        v = pd.read_parquet(f, columns=["name", "block_id", "lat", "lon"])
        iy = np.round((v["lat"].to_numpy() - LAT0) / RES).astype(int)
        ix = np.round((v["lon"].to_numpy() - LON0) / RES).astype(int)
        ok = (iy >= 0) & (iy < cell.shape[1]) & (ix >= 0) & (ix < cell.shape[2])
        off_grid += int((~ok).sum())
        for name, bid, y, x, good in zip(v["name"], v["block_id"], iy, ix, ok):
            i, r = pos.get(bid), row_of.get(bid)
            if i is None or r is None or not good:
                continue
            d = cell[:, y, x] - block_clim[:, r]
            per_block.setdefault(i, {})[str(name)] = [int(round(float(v) * 100)) for v in d]
            if heavy[0]:
                dh = heavy[1][:, y, x] - heavy[2][:, r]
                per_block_h.setdefault(i, {})[str(name)] = [int(round(float(v) * 100)) for v in dh]
            total += 1

    for i, entries in per_block.items():
        doc: dict = {"w": [int(w) for w in windows], "v": entries}
        if heavy[0]:
            doc["h"] = per_block_h.get(i, {})
        (OUT / f"{i}.json").write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
    spread = np.array([abs(x) for e in per_block.values() for row in e.values() for x in row])
    print(f"{total:,} villages across {len(per_block):,} blocks -> {OUT}")
    print(f"   median |adjustment| {np.median(spread):.1f} points, "
          f"90th percentile {np.percentile(spread, 90):.0f} points")
    if off_grid:
        print(f"   {off_grid:,} villages outside the CHIRPS grid, left without an adjustment")


if __name__ == "__main__":
    main()
