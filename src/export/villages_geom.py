"""Village and panchayat boundaries for the map, cut one file per block.

  python src/export/villages_geom.py --state Karnataka
  python src/export/villages_geom.py                      every state that has villages built

A block holds about 95 villages, and the console only ever looks inside a handful of blocks at a
time, so the boundaries are stored per block: EXPORTS/villages/geom/{block index}.json, a GeoJSON
FeatureCollection whose features carry only the village name. The map fetches the blocks on
screen and nothing else.

Geometry comes from geoBoundaries ADM5 (2011 Census villages, ODbL). The whole state is simplified
as one *coverage*, not polygon by polygon: neighbouring villages share a border, and simplifying
each one separately moves that border twice, leaving the slivers and doubled lines that make a
boundary layer look homemade. shapely.coverage_simplify() moves a shared edge once, so villages
still tile their block exactly. Coordinates keep five decimals, about a metre, which is why the
rounding cannot reopen the seams that simplification just closed.
"""
from __future__ import annotations
import sys, json, argparse, glob
from pathlib import Path
import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import RAW, PROCESSED, EXPORTS

SRC = RAW / "boundaries" / "IND_ADM5.geojson"
OUT = EXPORTS / "villages" / "geom"
TOLERANCE = 0.00025         # degrees, about 28 m: holds its shape when you zoom to one panchayat
PRECISION = 5               # decimals, about 1 m: fine enough that shared borders stay shared


def block_index() -> dict[str, int]:
    idx = EXPORTS / "blocks_index.json"
    if not idx.exists():
        sys.exit(f"{idx} not found: the console's block order defines the file names")
    return {b["id"]: b["i"] for b in json.loads(idx.read_text(encoding="utf-8"))}


def one_state(path: Path, pos: dict[str, int]) -> tuple[int, int]:
    v = pd.read_parquet(path, columns=["village_id", "name", "block_id"])
    if not len(v):
        return 0, 0
    state = pd.read_parquet(path, columns=["state"])["state"].iloc[0]
    want = dict(zip(v["village_id"], v["name"]))
    blocks = dict(zip(v["village_id"], v["block_id"]))

    # read only the area this state covers, then keep the villages we already placed in a block
    b = gpd.read_file(PROCESSED / "blocks.parquet", columns=["block_id", "geometry"]) \
        if False else None                                   # blocks.parquet has no geometry
    bbox = gpd.read_file(SRC, rows=1).total_bounds            # touch the file once to fail early
    del b, bbox
    pts = pd.read_parquet(path, columns=["lat", "lon"])
    west, south = float(pts["lon"].min()) - 0.05, float(pts["lat"].min()) - 0.05
    east, north = float(pts["lon"].max()) + 0.05, float(pts["lat"].max()) + 0.05

    g = gpd.read_file(SRC, bbox=(west, south, east, north))[["shapeID", "geometry"]]
    g = g[g["shapeID"].isin(want)]
    if not len(g):
        return 0, 0
    g["geometry"] = g.geometry.make_valid()
    g = g[~g.geometry.is_empty]
    g["geometry"] = simplify_coverage(g.geometry)
    g = g[~g.geometry.is_empty]

    OUT.mkdir(parents=True, exist_ok=True)
    written = 0
    per_block: dict[int, list] = {}
    for vid, geom in zip(g["shapeID"], g.geometry):
        i = pos.get(blocks.get(vid, ""))
        if i is None or geom is None:
            continue
        per_block.setdefault(i, []).append({
            "type": "Feature",
            "properties": {"n": want[vid], "i": i},
            "geometry": json.loads(gpd.GeoSeries([geom]).to_json(drop_id=True))["features"][0]["geometry"],
        })
    for i, feats in per_block.items():
        text = json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":"))
        (OUT / f"{i}.json").write_text(round_coords(text), encoding="utf-8")
        written += 1
    print(f"{state}: {len(g):,} villages -> {written} block files", flush=True)
    return len(g), written


def simplify_coverage(geoms):
    """Simplify the state as one polygonal coverage, so a shared border moves once, not twice.

    Falls back to plain per-polygon simplification if the source is not a clean coverage (a few
    states overlap themselves at the coast); the fallback is what this script always used to do.
    """
    import shapely
    try:
        out = shapely.coverage_simplify(list(geoms), TOLERANCE, simplify_boundary=True)
        out = gpd.GeoSeries(out, index=geoms.index, crs=geoms.crs).make_valid()
        if out.is_empty.mean() < 0.02:
            return out
        print("   coverage simplification lost too much, falling back", flush=True)
    except Exception as e:                       # an invalid coverage raises rather than guessing
        print(f"   coverage simplification unavailable ({e}), falling back", flush=True)
    return geoms.simplify(TOLERANCE).buffer(0)


def round_coords(text: str) -> str:
    """Trim coordinates to PRECISION decimals without reparsing the geometry."""
    import re
    return re.sub(r"-?\d+\.\d+", lambda m: f"{float(m.group()):.{PRECISION}f}", text)


def main(state: str | None) -> None:
    if not SRC.exists():
        sys.exit(f"{SRC} not found. Run: python src/data/villages.py fetch")
    pos = block_index()
    files = ([PROCESSED / f"villages_{state.lower()}.parquet"] if state
             else sorted(Path(p) for p in glob.glob(str(PROCESSED / "villages_*.parquet"))))
    files = [f for f in files if f.exists()]
    if not files:
        sys.exit("no villages parquet found. Run: python src/data/villages.py build --state <state>")
    total, blocks = 0, 0
    for f in files:
        n, w = one_state(f, pos)
        total += n
        blocks += w
    size = sum(p.stat().st_size for p in OUT.glob("*.json")) / 1e6 if OUT.exists() else 0
    print(f"-> {OUT}  {total:,} village outlines across {blocks} blocks, {size:.0f} MB on disk")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state", default=None)
    ap.add_argument("--tolerance", type=float, default=TOLERANCE, help="simplification, in degrees")
    ap.add_argument("--precision", type=int, default=PRECISION, help="decimals kept in the output")
    a = ap.parse_args()
    TOLERANCE, PRECISION = a.tolerance, a.precision
    main(a.state)
