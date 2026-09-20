"""Vector tiles and the block search index for the web console (runs on the server).

  python make_tiles.py              tiles + index
  python make_tiles.py --index-only index only (tiles unchanged)

india.pmtiles   layers: blocks (feature id = dense index i), districts, states
blocks_index.json  [{i, id, name, district, state, bb:[w,s,e,n], names?:{kn,hi,te,ta,mr}}], ordered by i
                   names come from processed/block_names.parquet (Wikidata) when present
"""
import os, sys, json, subprocess
from pathlib import Path
import geopandas as gpd, pandas as pd

D = Path(os.environ["MORPHY_DATA"]); B = D / "raw" / "boundaries"; O = D / "exports"; O.mkdir(exist_ok=True)
blocks = pd.read_parquet(D / "processed" / "blocks.parquet")
g = gpd.read_file(B / "IND_ADM3.geojson")[["shapeID", "geometry"]].rename(columns={"shapeID": "block_id"})
g = g.merge(blocks[["block_id", "name", "district", "state"]], on="block_id")
g["i"] = g.block_id.map({b: k for k, b in enumerate(blocks.block_id)}).astype(int)   # dense index = array position
g["geometry"] = g.geometry.make_valid()

if "--index-only" not in sys.argv:
    g[["i", "block_id", "name", "district", "state", "geometry"]].to_file(O / "_blocks.geojson", driver="GeoJSON")
    for lvl, name in [("ADM2", "districts"), ("ADM1", "states")]:
        x = gpd.read_file(B / f"IND_{lvl}.geojson")[["shapeName", "geometry"]].rename(columns={"shapeName": "name"})
        x.to_file(O / f"_{name}.geojson", driver="GeoJSON")
    cmd = ["tippecanoe", "-o", str(O / "india.pmtiles"), "--force", "-Z3", "-z11",
           "--detect-shared-borders", "--no-tiny-polygon-reduction", "--no-feature-limit", "--no-tile-size-limit",
           "--simplification=8", "--use-attribute-for-id=i",
           "-L", f"blocks:{O / '_blocks.geojson'}", "-L", f"districts:{O / '_districts.geojson'}",
           "-L", f"states:{O / '_states.geojson'}"]
    subprocess.run(cmd, check=True, capture_output=True)
    for p in O.glob("_*.geojson"):
        p.unlink()
    print(f"india.pmtiles {os.path.getsize(O / 'india.pmtiles') / 1e6:.1f} MB")

bounds = g.geometry.bounds.round(3)
# r["name"], not r.name: on an iterrows() row, .name is the row's index label
index = [{"i": int(r["i"]), "id": r["block_id"], "name": r["name"], "district": r["district"],
          "state": r["state"], "bb": bounds.loc[k].tolist()}
         for k, r in g.sort_values("i").iterrows()]
assert all(isinstance(x["name"], str) for x in index), "block names must be strings"

names_file = D / "processed" / "block_names.parquet"
if names_file.exists():
    nm = pd.read_parquet(names_file).set_index("block_id")
    cols = [c for c in nm.columns if c.startswith("name_")]
    n_with = 0
    for x in index:
        if x["id"] in nm.index:
            r = nm.loc[x["id"]]
            loc = {c[5:]: r[c] for c in cols if isinstance(r[c], str)}
            if loc:
                x["names"] = loc
                n_with += 1
    print(f"local-script names attached to {n_with} blocks")
json.dump(index, open(O / "blocks_index.json", "w", encoding="utf-8"), separators=(",", ":"), ensure_ascii=False)
print(f"blocks_index.json {os.path.getsize(O / 'blocks_index.json') / 1e6:.2f} MB, {len(g)} blocks")
