"""IMD gridded rainfall -> daily rainfall per block -> event labels per block.

Outputs (PROCESSED):
  imd_block_rain.nc     rain[time, block]  mm/day, 1981-2025, area-weighted
  imd_block_labels.nc   per (year, block): true_onset_doy, n_false, first_false_doy
                        per (time, block): dry7, dry10, heavy  (daily, bool)

Labels are computed on the block-mean series: the question a farmer asks is
about their block, not about a 25 km grid cell.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
from scipy import sparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import RAW_IMD, PROCESSED, SEASON_START_DOY, SEASON_END_DOY
from features.labels import onset_labels, spell_labels
from features.onset_normal import search_start_doy

YEARS = range(1981, 2026)


def weight_matrix(ny: int, nx: int):
    blocks = pd.read_parquet(PROCESSED / "blocks.parquet")
    w = pd.read_parquet(PROCESSED / "block_weights.parquet")
    bidx = pd.Series(np.arange(len(blocks)), index=blocks["block_id"])
    rows = bidx.loc[w["block_id"]].values
    cols = w["iy"].values * nx + w["ix"].values
    W = sparse.csr_matrix((w["w"].values, (rows, cols)), shape=(len(blocks), ny * nx))
    return W, blocks


def read_imd_year(yr: int) -> xr.DataArray:
    import imdlib
    da = imdlib.open_data("rain", yr, yr, "yearwise", str(RAW_IMD)).get_xarray()["rain"]
    return da.where(da >= 0)


def main():
    first = read_imd_year(YEARS[0])
    ny, nx = first.sizes["lat"], first.sizes["lon"]
    W, blocks = weight_matrix(ny, nx)
    start = (search_start_doy(blocks.lat.values, blocks.lon.values) - SEASON_START_DOY)[:, None]

    rain_all, times = [], []
    onset, nfalse, ffalse = [], [], []
    dry7_all, dry10_all, heavy_all = [], [], []
    for yr in YEARS:
        da = read_imd_year(yr)
        flat = da.values.reshape(da.sizes["time"], -1)
        valid = np.isfinite(flat)
        # renormalise per day so a missing cell doesn't bias the block mean low
        num = (W @ np.where(valid, flat, 0.0).T).T
        den = (W @ valid.T.astype(float)).T
        rb = np.where(den > 0.5, num / np.maximum(den, 1e-9), np.nan).astype("float32")
        rain_all.append(rb); times.append(da["time"].values)

        s0, s1 = SEASON_START_DOY - 1, SEASON_END_DOY        # 0-based slice
        season = rb[s0:s1][:, :, None]
        to, nf, ff = onset_labels(season, start)
        d7, d10, hv = spell_labels(season)
        onset.append(np.where(to[:, 0] >= 0, to[:, 0] + SEASON_START_DOY, -1))
        nfalse.append(nf[:, 0])
        ffalse.append(np.where(ff[:, 0] >= 0, ff[:, 0] + SEASON_START_DOY, -1))
        pad = lambda a: np.concatenate(
            [np.zeros((s0, a.shape[1]), bool), a[:, :, 0],
             np.zeros((rb.shape[0] - s1, a.shape[1]), bool)])
        dry7_all.append(pad(d7)); dry10_all.append(pad(d10)); heavy_all.append(pad(hv))
        print(f"{yr}: onset found {np.mean(onset[-1] > 0):.0%}  "
              f"false-onset blocks {np.mean(nfalse[-1] > 0):.0%}  "
              f"median onset DOY {np.median(onset[-1][onset[-1] > 0]):.0f}", flush=True)

    t = np.concatenate(times)
    bid = blocks["block_id"].values
    xr.Dataset({"rain": (("time", "block"), np.concatenate(rain_all))},
               coords={"time": t, "block": bid}).to_netcdf(
        PROCESSED / "imd_block_rain.nc", encoding={"rain": {"zlib": True, "complevel": 4}})
    xr.Dataset(
        {"true_onset_doy": (("year", "block"), np.stack(onset).astype("int16")),
         "n_false": (("year", "block"), np.stack(nfalse).astype("int16")),
         "first_false_doy": (("year", "block"), np.stack(ffalse).astype("int16")),
         "dry7": (("time", "block"), np.concatenate(dry7_all)),
         "dry10": (("time", "block"), np.concatenate(dry10_all)),
         "heavy": (("time", "block"), np.concatenate(heavy_all))},
        coords={"year": list(YEARS), "time": t, "block": bid},
    ).to_netcdf(PROCESSED / "imd_block_labels.nc",
                encoding={k: {"zlib": True} for k in ["dry7", "dry10", "heavy"]})
    print("written", PROCESSED / "imd_block_rain.nc", PROCESSED / "imd_block_labels.nc")


if __name__ == "__main__":
    main()
