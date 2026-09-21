"""Village and panchayat lookup for the console: the name a farmer uses -> the block that forecasts it.

  python src/export/villages_json.py

India has 649,309 villages, far too many to hand a browser in one file, so the index is sharded by
the first letter of the name. A search only ever loads the shard it needs (about 400 KB gzipped),
and a village is stored as:

  ["Kengeri Gollahalli", <block index>]

where the block index is the position in blocks_index.json, which the console already holds. The
files carry no probabilities: the forecast is issued at block scale, and the panel says so.

Writes EXPORTS/villages/{a..z,other}.json for search, EXPORTS/villages/cells/{iy}_{ix}.json
for the map layer (0.5 degree cells, fetched only for what is on screen), and index.json.
"""
from __future__ import annotations
import sys, json, glob, unicodedata
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import PROCESSED, EXPORTS

OUT = EXPORTS / "villages"
LETTERS = "abcdefghijklmnopqrstuvwxyz"


CELL = 0.5          # degrees: a cell holds a few hundred villages, a few KB gzipped


def cell_of(lat: float, lon: float) -> str:
    """The map cell a village falls in, so the console fetches only the cells on screen."""
    return f"{int((lat + 90) // CELL)}_{int((lon + 180) // CELL)}"


def shard_of(name: str) -> str:
    n = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower().lstrip()
    return n[0] if n and n[0] in LETTERS else "other"


def main() -> None:
    idx_file = EXPORTS / "blocks_index.json"
    if not idx_file.exists():
        sys.exit(f"{idx_file} not found: the console's block order defines the ids used here")
    blocks = json.loads(idx_file.read_text(encoding="utf-8"))
    pos = {b["id"]: b["i"] for b in blocks}

    files = sorted(glob.glob(str(PROCESSED / "villages_*.parquet"))) or [str(PROCESSED / "villages.parquet")]
    shards: dict[str, list] = {}
    cells: dict[str, list] = {}
    dropped = 0
    for f in files:
        v = pd.read_parquet(f, columns=["name", "block_id", "lat", "lon"])
        for name, bid, lat, lon in zip(v["name"], v["block_id"], v["lat"], v["lon"]):
            i = pos.get(bid)
            if i is None:
                dropped += 1
                continue
            shards.setdefault(shard_of(name), []).append([name, i])
            # and again by map cell, so the map can fetch only what is on screen
            cells.setdefault(cell_of(lat, lon), []).append([name, round(float(lat), 4),
                                                            round(float(lon), 4), i])

    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.json"):
        old.unlink()
    index = {}
    total = 0
    for k, rows in sorted(shards.items()):
        rows.sort(key=lambda r: r[0])
        (OUT / f"{k}.json").write_text(json.dumps({"v": rows}, separators=(",", ":")), encoding="utf-8")
        index[k] = len(rows)
        total += len(rows)
    pts = OUT / "cells"
    pts.mkdir(parents=True, exist_ok=True)
    for old_cell in pts.glob("*.json"):
        old_cell.unlink()
    for k, rows in cells.items():
        (pts / f"{k}.json").write_text(json.dumps(rows, separators=(",", ":")), encoding="utf-8")
    (OUT / "index.json").write_text(json.dumps({"shards": index, "total": total,
                                                "cell_deg": CELL, "cells": len(cells)},
                                               separators=(",", ":")), encoding="utf-8")
    print(f"{len(cells):,} map cells of {CELL} degrees for the map layer")
    big = max(index.items(), key=lambda t: t[1])
    print(f"{total:,} villages in {len(index)} shards -> {OUT}")
    print(f"   largest shard '{big[0]}' with {big[1]:,} "
          f"({(OUT / (big[0] + '.json')).stat().st_size / 1e6:.1f} MB before gzip)")
    if dropped:
        print(f"   {dropped:,} villages skipped: their block is not in blocks_index.json")


if __name__ == "__main__":
    main()
