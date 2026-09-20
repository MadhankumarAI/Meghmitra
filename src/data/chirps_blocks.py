"""Block weights on the CHIRPS 0.05 deg grid, then daily rainfall per block.

Blocks are rasterised at 0.01 deg (5x finer than CHIRPS); counting fine pixels per
coarse cell gives area-fraction weights without a 450k-polygon overlay.
Runs on the server. Outputs PROCESSED/chirps_block_weights.parquet and
PROCESSED/chirps_block_rain.nc (time, block).
"""
from __future__ import annotations
import os, sys
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
import xarray as xr
from rasterio import features
from rasterio.transform import from_origin
from scipy import sparse

DATA = Path(os.environ.get("MORPHY_DATA", Path.home() / "morphy" / "data"))
PROCESSED = DATA / "processed"
CHIRPS = DATA / "raw" / "chirps"
SUB = 5                                       # 0.01 deg pixels per 0.05 deg cell edge


def weights():
    ds = xr.open_dataset(sorted(CHIRPS.glob("chirps_india_*.nc"))[0])
    lat, lon = ds.latitude.values, ds.longitude.values          # cell centres, lat ascending
    res = float(np.round(lon[1] - lon[0], 4))
    ny, nx = len(lat), len(lon)
    west, north = lon[0] - res / 2, lat[-1] + res / 2
    fine = res / SUB
    tr = from_origin(west, north, fine, fine)                     # row 0 = north

    blocks = pd.read_parquet(PROCESSED / "blocks.parquet")
    g = gpd.read_file(DATA / "raw" / "boundaries" / "IND_ADM3.geojson")[["shapeID", "geometry"]]
    g = g.set_index("shapeID").loc[blocks.block_id]
    code = np.arange(1, len(g) + 1, dtype=np.int32)
    ras = features.rasterize(zip(g.geometry.values, code), out_shape=(ny * SUB, nx * SUB),
                             transform=tr, fill=0, dtype="int32")
    # fine pixel (r, c) -> coarse cell (ny-1 - r//SUB, c//SUB) because lat is ascending
    r, c = np.nonzero(ras)
    b = ras[r, c] - 1
    iy = ny - 1 - r // SUB
    ix = c // SUB
    df = pd.DataFrame({"b": b, "iy": iy, "ix": ix}).value_counts().rename("n").reset_index()
    # drop cells where CHIRPS has no data (sea / masked) and renormalise
    valid = np.isfinite(ds["precip"].isel(time=180).values)
    df = df[valid[df.iy, df.ix]]
    df["w"] = df.n / df.groupby("b").n.transform("sum")
    df["block_id"] = blocks.block_id.values[df.b]
    missing = len(blocks) - df.b.nunique()
    df[["block_id", "iy", "ix", "w"]].to_parquet(PROCESSED / "chirps_block_weights.parquet", index=False)
    cells = df.groupby("b").size()
    print(f"CHIRPS grid {ny}x{nx} at {res} deg | blocks mapped {df.b.nunique()}/{len(blocks)} "
          f"(unmapped {missing}: smaller than a 1 km pixel or offshore)")
    print(f"cells per block: median {cells.median():.0f}  10th pct {cells.quantile(.1):.0f}  "
          f"blocks with 1 cell: {(cells == 1).sum()}")
    return df, blocks, ny, nx


def block_rain(df, blocks, ny, nx):
    B = len(blocks)
    W = sparse.csr_matrix((df.w.values, (df.b.values, df.iy.values * nx + df.ix.values)),
                          shape=(B, ny * nx))
    parts, times = [], []
    for f in sorted(CHIRPS.glob("chirps_india_*.nc")):
        da = xr.open_dataset(f)["precip"]
        v = da.values.reshape(da.sizes["time"], -1)
        ok = np.isfinite(v)
        num = (W @ np.where(ok, v, 0).T).T
        den = (W @ ok.T.astype(float)).T
        parts.append(np.where(den > 0.5, num / np.maximum(den, 1e-9), np.nan).astype("float32"))
        times.append(da.time.values)
        print(f.name, flush=True)
    xr.Dataset({"rain": (("time", "block"), np.concatenate(parts))},
               coords={"time": np.concatenate(times), "block": blocks.block_id.values}
               ).to_netcdf(PROCESSED / "chirps_block_rain.nc",
                           encoding={"rain": {"zlib": True, "complevel": 4}})


if __name__ == "__main__":
    df, blocks, ny, nx = weights()
    if "--weights-only" not in sys.argv:
        block_rain(df, blocks, ny, nx)
