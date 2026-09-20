"""Map the 6,824 geoBoundaries ADM3 blocks onto the IMD 0.25 deg rainfall grid.

Outputs (in PROCESSED):
  blocks.parquet        one row per block: id, names, district, state, area,
                        n_cells, subgrid flag, representative point
  block_weights.parquet sparse (block_id, iy, ix, w) with w summing to 1 per block

Weights are area-weighted in an equal-area projection and are renormalised over
cells that actually carry IMD data, so coastal blocks are not diluted by sea cells.
"""
from __future__ import annotations
import sys, re, unicodedata
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import RAW, RAW_IMD, PROCESSED, IMD_RES

EQUAL_AREA = "EPSG:6933"


def ascii_name(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"\s*\(?\bPt\b\.?\)?\s*$", "", s, flags=re.I)   # census "(Pt)" suffix
    return re.sub(r"\s+", " ", s).strip()


def imd_grid():
    """Cell centres and a land mask from any downloaded IMD year."""
    import imdlib
    yr = sorted(int(p.stem) for p in (RAW_IMD / "rain").glob("*.grd"))[-1]
    ds = imdlib.open_data("rain", yr, yr, "yearwise", str(RAW_IMD)).get_xarray()
    r = ds["rain"].values
    valid = (np.isfinite(r) & (r >= 0)).any(axis=0)
    return ds["lat"].values, ds["lon"].values, valid


def main():
    bdir = RAW / "boundaries"
    adm3 = gpd.read_file(bdir / "IND_ADM3.geojson")[["shapeID", "shapeName", "geometry"]]
    adm2 = gpd.read_file(bdir / "IND_ADM2.geojson")[["shapeName", "geometry"]].rename(
        columns={"shapeName": "district"})
    adm1 = gpd.read_file(bdir / "IND_ADM1.geojson")[["shapeName", "geometry"]].rename(
        columns={"shapeName": "state"})
    adm3 = adm3.rename(columns={"shapeID": "block_id", "shapeName": "name_raw"})
    adm3["geometry"] = adm3.geometry.make_valid()

    # parent names via a point guaranteed inside each block
    pts = adm3.copy()
    pts["geometry"] = adm3.geometry.representative_point()
    pts = gpd.sjoin(pts, adm2, how="left", predicate="within").drop(columns="index_right")
    pts = gpd.sjoin(pts, adm1, how="left", predicate="within").drop(columns="index_right")
    pts = pts.drop_duplicates("block_id")
    adm3 = adm3.merge(pts[["block_id", "district", "state"]], on="block_id", how="left")
    adm3["name"] = adm3["name_raw"].map(ascii_name)
    adm3["district"] = adm3["district"].fillna("").map(ascii_name)
    adm3["state"] = adm3["state"].fillna("").map(ascii_name)

    # grid cells as polygons, land cells only
    lat, lon, valid = imd_grid()
    h = IMD_RES / 2
    iy, ix = np.nonzero(valid)
    cells = gpd.GeoDataFrame(
        {"iy": iy, "ix": ix},
        geometry=[box(lon[j] - h, lat[i] - h, lon[j] + h, lat[i] + h) for i, j in zip(iy, ix)],
        crs="EPSG:4326",
    )

    blocks_ea = adm3[["block_id", "geometry"]].to_crs(EQUAL_AREA)
    cells_ea = cells.to_crs(EQUAL_AREA)
    adm3["area_km2"] = blocks_ea.geometry.area.values / 1e6

    inter = gpd.overlay(blocks_ea, cells_ea, how="intersection", keep_geom_type=True)
    inter["a"] = inter.geometry.area
    inter = inter[inter["a"] > 0]
    inter["w"] = inter["a"] / inter.groupby("block_id")["a"].transform("sum")
    weights = inter[["block_id", "iy", "ix", "w"]].reset_index(drop=True)

    # blocks with no land-cell overlap (small islands): nearest valid cell
    missing = sorted(set(adm3["block_id"]) - set(weights["block_id"]))
    if missing:
        cc = cells_ea.copy()
        cc["geometry"] = cc.geometry.centroid
        near = gpd.sjoin_nearest(
            blocks_ea[blocks_ea["block_id"].isin(missing)], cc, how="left"
        ).drop_duplicates("block_id")
        weights = pd.concat([weights, pd.DataFrame(
            {"block_id": near["block_id"], "iy": near["iy"], "ix": near["ix"], "w": 1.0})],
            ignore_index=True)

    ncell = weights.groupby("block_id").size().rename("n_cells")
    adm3 = adm3.merge(ncell, left_on="block_id", right_index=True, how="left")
    cell_km2 = (IMD_RES * 111.0) ** 2
    adm3["subgrid"] = adm3["area_km2"] < cell_km2          # finer than the data
    adm3["nearest_fallback"] = adm3["block_id"].isin(missing)
    rp = adm3.geometry.representative_point()
    adm3["lon"], adm3["lat"] = rp.x, rp.y

    PROCESSED.mkdir(parents=True, exist_ok=True)
    cols = ["block_id", "name", "name_raw", "district", "state", "area_km2",
            "n_cells", "subgrid", "nearest_fallback", "lat", "lon"]
    adm3[cols].to_parquet(PROCESSED / "blocks.parquet", index=False)
    weights.to_parquet(PROCESSED / "block_weights.parquet", index=False)

    s = weights.groupby("block_id")["w"].sum()
    print(f"blocks: {len(adm3)}  weight rows: {len(weights)}  "
          f"weights sum to 1: {np.allclose(s, 1)}")
    print(f"median cells/block: {adm3['n_cells'].median():.0f}   "
          f"sub-grid blocks: {adm3['subgrid'].sum()}   "
          f"nearest-cell fallback: {adm3['nearest_fallback'].sum()}")
    print(f"missing state: {(adm3['state']=='').sum()}   "
          f"missing district: {(adm3['district']=='').sum()}")
    print(adm3[adm3["state"].str.contains("Karnataka")][["name", "district", "n_cells"]].head(6))


if __name__ == "__main__":
    main()
