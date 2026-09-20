"""Build the location lookups the bot needs. Reads D:\\Morphy (read-only), writes ./data/.

    .venv\\Scripts\\python scripts\\build_geo.py

Outputs
  data/blocks.json        block_id -> {name, district, state, lat, lon}   (from blocks.parquet)
  data/blocks_geom.pkl.gz block ids + polygon WKB, lightly simplified     (from IND_ADM3.geojson)
  data/pincodes.json      PIN -> {lat, lon, blocks: [[block_id, n_offices], ...]}

PIN source, in order of preference:
  1. India Post "All India Pincode Directory" on data.gov.in (Department of Posts, OGD licence), when
     DATAGOVIN_API_KEY is set in .env (a free personal key; the public sample key only returns 10 rows).
  2. GeoNames postal codes for India (CC BY 4.0), downloaded to .cache/. Coarser: many PINs share one point.
"""
from __future__ import annotations

import gzip
import io
import json
import os
import pickle
import statistics
import sys
import time
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
import shapely
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.config import get_settings  # noqa: E402

DATAGOV_RESOURCE = "5c2f62fe-5afa-4119-a499-fec9d604d5bd"
GEONAMES_URL = "https://download.geonames.org/export/zip/IN.zip"
SIMPLIFY_DEG = 0.0002  # ~20 m; boundaries stay well inside block-level accuracy


def build_blocks(out: Path) -> dict:
    s = get_settings()
    df = pd.read_parquet(s.blocks_parquet, columns=["block_id", "name", "district", "state", "lat", "lon"])
    blocks = {r.block_id: {"name": r.name, "district": r.district, "state": r.state,
                           "lat": round(float(r.lat), 5), "lon": round(float(r.lon), 5)} for r in df.itertuples()}
    (out / "blocks.json").write_text(json.dumps(blocks, ensure_ascii=False), encoding="utf-8")
    print(f"blocks.json: {len(blocks)} blocks")
    return blocks


def build_geoms(out: Path, blocks: dict) -> tuple[list[str], list]:
    s = get_settings()
    t = time.time()
    with open(s.boundaries_geojson, encoding="utf-8") as f:
        features = json.load(f)["features"]
    ids, geoms = [], []
    for ft in features:
        bid = ft["properties"].get("shapeID")
        if bid not in blocks or not ft.get("geometry"):
            continue
        g = shape(ft["geometry"])
        if not g.is_valid:
            g = shapely.make_valid(g)
        ids.append(bid)
        geoms.append(g.simplify(SIMPLIFY_DEG, preserve_topology=True))
    with gzip.open(out / "blocks_geom.pkl.gz", "wb") as f:
        pickle.dump({"ids": ids, "wkb": [shapely.to_wkb(g) for g in geoms]}, f)
    print(f"blocks_geom.pkl.gz: {len(ids)} polygons ({len(blocks) - len(ids)} blocks without a polygon) "
          f"in {time.time() - t:.0f}s")
    return ids, geoms


def pin_points_datagov(key: str) -> list[tuple[str, float, float]]:
    rows, offset, limit = [], 0, 1000
    while True:
        url = (f"https://api.data.gov.in/resource/{DATAGOV_RESOURCE}?api-key={key}&format=json"
               f"&limit={limit}&offset={offset}")
        with urllib.request.urlopen(url, timeout=60) as r:
            recs = json.load(r).get("records", [])
        for rec in recs:
            try:
                rows.append((str(rec["pincode"]), float(rec["latitude"]), float(rec["longitude"])))
            except (KeyError, TypeError, ValueError):
                pass
        offset += len(recs)
        print(f"  data.gov.in: {offset} offices", end="\r")
        if len(recs) < limit:
            return rows


def pin_points_geonames() -> list[tuple[str, float, float]]:
    cache = ROOT / ".cache" / "IN.zip"
    if not cache.exists():
        cache.parent.mkdir(exist_ok=True)
        urllib.request.urlretrieve(GEONAMES_URL, cache)
    text = zipfile.ZipFile(cache).read("IN.txt").decode("utf-8")
    rows = []
    for line in io.StringIO(text):
        f = line.rstrip("\n").split("\t")
        try:
            rows.append((f[1], float(f[9]), float(f[10])))
        except (IndexError, ValueError):
            pass
    return rows


def build_pins(out: Path, ids: list[str], geoms: list) -> None:
    key = os.environ.get("DATAGOVIN_API_KEY") or _dotenv("DATAGOVIN_API_KEY")
    if key:
        points, source = pin_points_datagov(key), "India Post directory (data.gov.in, OGD licence)"
    else:
        points, source = pin_points_geonames(), "GeoNames postal codes (CC BY 4.0)"
    # India's bounding box; the India Post data has some swapped or zero coordinates.
    points = [p for p in points if 6 <= p[1] <= 37.5 and 68 <= p[2] <= 97.5]
    tree = shapely.STRtree(geoms)
    pts = shapely.points([p[2] for p in points], [p[1] for p in points])
    pidx, gidx = tree.query(pts, predicate="within")
    hit = {int(i): ids[int(g)] for i, g in zip(pidx, gidx)}
    by_pin: dict[str, list] = defaultdict(list)
    for i, (pin, lat, lon) in enumerate(points):
        by_pin[pin].append((lat, lon, hit.get(i)))
    pins = {}
    for pin, lst in by_pin.items():
        counts = Counter(b for _, _, b in lst if b)
        pins[pin] = {"lat": round(statistics.median(x[0] for x in lst), 5),
                     "lon": round(statistics.median(x[1] for x in lst), 5),
                     "blocks": counts.most_common(5)}
    (out / "pincodes.json").write_text(json.dumps({"_source": source, "pins": pins}), encoding="utf-8")
    mapped = sum(1 for v in pins.values() if v["blocks"])
    print(f"pincodes.json: {len(pins)} PINs, {mapped} mapped to a block, source: {source}")


def _dotenv(name: str) -> str | None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip() or None
    return None


def main() -> None:
    out = get_settings().geo_dir
    out.mkdir(parents=True, exist_ok=True)
    blocks = build_blocks(out)
    ids, geoms = build_geoms(out, blocks)
    build_pins(out, ids, geoms)


if __name__ == "__main__":
    main()
