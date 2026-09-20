"""Location -> block. Point-in-polygon over block boundaries; PIN codes via the prebuilt PIN index.

Data comes from scripts/build_geo.py (run once). Loaded lazily on first use and kept in memory.
"""
from __future__ import annotations

import gzip
import json
import math
import pickle
import threading
from functools import lru_cache

import shapely

from .config import get_settings

_lock = threading.Lock()


@lru_cache
def blocks() -> dict[str, dict]:
    return json.loads((get_settings().geo_dir / "blocks.json").read_text(encoding="utf-8"))


@lru_cache
def _index() -> tuple[list[str], list, shapely.STRtree]:
    with _lock, gzip.open(get_settings().geo_dir / "blocks_geom.pkl.gz", "rb") as f:
        raw = pickle.load(f)  # our own build artefact (scripts/build_geo.py), never user input
    geoms = list(shapely.from_wkb(raw["wkb"]))
    return raw["ids"], geoms, shapely.STRtree(geoms)


@lru_cache
def _pins() -> dict:
    path = get_settings().geo_dir / "pincodes.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"pins": {}}


def block(block_id: str) -> dict | None:
    b = blocks().get(block_id)
    return {"block_id": block_id, **b} if b else None


def block_at(lat: float, lon: float) -> str | None:
    """Block containing the point; if it falls in a sliver gap or just offshore, the nearest within ~2 km."""
    ids, geoms, tree = _index()
    pt = shapely.Point(lon, lat)
    hits = tree.query(pt, predicate="within")
    if len(hits):
        return ids[int(hits[0])]
    near = tree.query_nearest(pt, max_distance=0.02)
    return ids[int(near[0])] if len(near) else None


def nearest_blocks(lat: float, lon: float, k: int = 9, exclude: set[str] | None = None) -> list[str]:
    """Blocks whose centroids are closest to the point (for 'No, that is not my block')."""
    exclude = exclude or set()
    scored = sorted(
        ((_km(lat, lon, b["lat"], b["lon"]), bid) for bid, b in blocks().items() if bid not in exclude),
    )
    return [bid for _, bid in scored[:k]]


def pin_lookup(pin: str) -> dict | None:
    """{'lat', 'lon', 'blocks': [[block_id, n], ...]} for a 6-digit PIN, or None."""
    rec = _pins()["pins"].get(pin.strip())
    if not rec:
        return None
    if not rec["blocks"]:
        bid = block_at(rec["lat"], rec["lon"])
        rec = {**rec, "blocks": [[bid, 1]] if bid else []}
    return rec


def pin_source() -> str:
    return _pins().get("_source", "none")


def warm() -> None:
    """Load everything up front (called in a background thread at startup)."""
    blocks()
    _index()
    _pins()


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 12742 * math.asin(math.sqrt(a))
