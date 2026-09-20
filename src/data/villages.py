"""Villages and gram panchayats: the name a farmer actually uses for where they are.

  python src/data/villages.py fetch                 download the ADM5 layer (467 MB, once)
  python src/data/villages.py build                 all of India
  python src/data/villages.py build --state Karnataka
  python src/data/villages.py show Kengeri

Source: geoBoundaries gbOpen IND ADM5, canonical type "village", derived from the 2011 Census
village directory, ODbL. Each village is placed inside its block (ADM3) by a point guaranteed to
lie within it, so the mapping is exact rather than nearest-neighbour.

Outputs (in PROCESSED):
  villages.parquet        village_id, name, block_id, block, district, state, area_km2, lat, lon
  village_weights.parquet sparse (village_id, iy, ix, w) on the CHIRPS 0.05 deg grid, w sums to 1

The weights exist so a village can carry its **own** rainfall normal at 5 km rather than
inheriting its block's. That is what lets two villages in one block differ, and it is measured,
not assumed. The forecast itself is issued at block scale; see docs/ADVICE_SOURCES.md.
"""
from __future__ import annotations
import sys, argparse, urllib.request
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import RAW, PROCESSED
from data.blocks import ascii_name, EQUAL_AREA

URL = ("https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/IND/ADM5/"
       "geoBoundaries-IND-ADM5_simplified.geojson")
SRC = RAW / "boundaries" / "IND_ADM5.geojson"
CHIRPS_RES = 0.05
CHIRPS_ORIGIN = (-50.0 + CHIRPS_RES / 2, -180.0 + CHIRPS_RES / 2)      # lat0, lon0 of cell centres


def fetch() -> None:
    SRC.parent.mkdir(parents=True, exist_ok=True)
    if SRC.exists():
        print(f"{SRC} already here ({SRC.stat().st_size / 1e6:.0f} MB)")
        return
    part = SRC.with_suffix(".part")
    print(f"downloading {URL}")
    urllib.request.urlretrieve(URL, part)
    part.replace(SRC)
    print(f"-> {SRC} ({SRC.stat().st_size / 1e6:.0f} MB)")


def chirps_cell(lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Index of the CHIRPS 0.05 deg cell containing each point."""
    iy = np.round((lat - CHIRPS_ORIGIN[0]) / CHIRPS_RES).astype(int)
    ix = np.round((lon - CHIRPS_ORIGIN[1]) / CHIRPS_RES).astype(int)
    return iy, ix


def build(state: str | None = None) -> None:
    if not SRC.exists():
        sys.exit(f"{SRC} not found. Run: python src/data/villages.py fetch")
    blocks = pd.read_parquet(PROCESSED / "blocks.parquet")
    if state:
        keep = blocks["state"].str.casefold() == state.casefold()
        if not keep.any():
            sys.exit(f"no blocks in state {state!r}; states: {sorted(blocks['state'].unique())[:8]} ...")
        blocks = blocks[keep]
    print(f"{len(blocks):,} blocks in scope")

    adm3 = gpd.read_file(RAW / "boundaries" / "IND_ADM3.geojson")[["shapeID", "geometry"]]
    adm3 = adm3.rename(columns={"shapeID": "block_id"})
    adm3 = adm3[adm3["block_id"].isin(set(blocks["block_id"]))]
    adm3["geometry"] = adm3.geometry.make_valid()

    bbox = tuple(adm3.total_bounds)                      # read only the area we need
    print(f"reading villages within {np.round(bbox, 2)}")
    v = gpd.read_file(SRC, bbox=bbox)[["shapeID", "shapeName", "geometry"]]
    v = v.rename(columns={"shapeID": "village_id", "shapeName": "name_raw"})
    v["geometry"] = v.geometry.make_valid()
    print(f"{len(v):,} villages in the bounding box")

    # a point guaranteed inside the village decides which block it belongs to
    pts = v.copy()
    pts["geometry"] = v.geometry.representative_point()
    pts = gpd.sjoin(pts, adm3, how="inner", predicate="within").drop(columns="index_right")
    pts = pts.drop_duplicates("village_id")
    v = v.merge(pts[["village_id", "block_id"]], on="village_id", how="inner")
    print(f"{len(v):,} villages placed inside a block")

    v["name"] = v["name_raw"].map(ascii_name)
    v = v.merge(blocks[["block_id", "name", "district", "state"]].rename(columns={"name": "block"}),
                on="block_id", how="left")
    v_ea = v[["village_id", "geometry"]].to_crs(EQUAL_AREA)
    v["area_km2"] = v_ea.geometry.area.values / 1e6
    rp = v.geometry.representative_point()
    v["lon"], v["lat"] = rp.x, rp.y

    # CHIRPS cells under each village, area weighted; tiny villages fall in one cell
    iy, ix = chirps_cell(v["lat"].to_numpy(), v["lon"].to_numpy())
    weights = pd.DataFrame({"village_id": v["village_id"], "iy": iy, "ix": ix, "w": 1.0})

    PROCESSED.mkdir(parents=True, exist_ok=True)
    cols = ["village_id", "name", "name_raw", "block_id", "block", "district", "state",
            "area_km2", "lat", "lon"]
    out = PROCESSED / ("villages.parquet" if not state else f"villages_{state.lower()}.parquet")
    wout = PROCESSED / ("village_weights.parquet" if not state else f"village_weights_{state.lower()}.parquet")
    v[cols].to_parquet(out, index=False)
    weights.to_parquet(wout, index=False)

    per_block = v.groupby("block_id").size()
    print(f"-> {out}  {len(v):,} villages across {per_block.size:,} blocks")
    print(f"   median {per_block.median():.0f} villages per block, largest {per_block.max():,} "
          f"({blocks.set_index('block_id').loc[per_block.idxmax(), 'name']})")
    print(f"   median village area {v['area_km2'].median():.1f} km2 "
          f"(a block is {blocks['area_km2'].median():.0f} km2)")


def show(name: str) -> None:
    v = pd.read_parquet(PROCESSED / "villages.parquet")
    hit = v[v["name"].str.casefold().str.contains(name.casefold(), na=False)]
    if hit.empty:
        sys.exit(f"no village matching {name!r}")
    for _, r in hit.head(20).iterrows():
        print(f"{r['name']:<28} block {r['block']:<22} {r['district']:<18} {r['state']:<16} "
              f"{r['area_km2']:6.1f} km2  {r['lat']:.3f},{r['lon']:.3f}")
    print(f"{len(hit)} match(es)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=["fetch", "build", "show"])
    ap.add_argument("name", nargs="?", default=None)
    ap.add_argument("--state", default=None)
    a = ap.parse_args()
    if a.cmd == "fetch":
        fetch()
    elif a.cmd == "build":
        build(a.state)
    else:
        show(a.name or "")
