"""The Indian Ocean Dipole, computed here from weekly sea-surface temperature.

The problem statement names IOD alongside ENSO and MJO. NOAA PSL's published Dipole Mode Index
(HadISST) is months behind - on 20 Sep 2026 its newest month was May, and the file had not been
touched since 25 July - so a system built on it would be blind in the season it is meant to serve.

So we compute the index ourselves from NOAA **ERSST v5** monthly (PSL, 1854-present, updated in
the first week of the following month - the same dataset NOAA uses for its own ENSO indices):

    DMI = SST anomaly over 50-70E, 10S-10N  minus  SST anomaly over 90-110E, 10S-0
          (Saji et al. 1999, the standard definition)

This module writes only the raw weekly box temperatures. The anomalies - and therefore the index
itself - are formed later against a climatology built from the *training* years alone, so a
validation fold can never see its own seasons through the IOD (features/iod.py).

  python iod_index.py            -> PROCESSED/iod_boxes.parquet
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import RAW_INDICES, PROCESSED

SST = RAW_INDICES / "sst.mnmean.nc"
URL = "https://downloads.psl.noaa.gov/Datasets/noaa.ersst.v5/sst.mnmean.nc"
WEST = dict(lat=(-10, 10), lon=(50, 70))                  # Saji et al. (1999) west pole
EAST = dict(lat=(-10, 0), lon=(90, 110))                  # east pole


def box_mean(da, box: dict) -> np.ndarray:
    """Area-weighted mean SST over a lat/lon box, whichever way the axes run."""
    lat0, lat1 = box["lat"]
    lon0, lon1 = box["lon"]
    lat = da.lat.values
    sub = da.sel(lat=slice(lat1, lat0) if lat[0] > lat[-1] else slice(lat0, lat1),
                 lon=slice(lon0, lon1))
    w = np.cos(np.deg2rad(sub.lat))
    return sub.weighted(w).mean(dim=("lat", "lon")).values.astype(np.float32)


def main() -> None:
    import xarray as xr
    if not SST.exists():
        sys.exit(f"missing {SST}\n  curl -o {SST} {URL}")
    ds = xr.open_dataset(SST)
    sst = ds["sst"]
    out = pd.DataFrame({
        "date": pd.to_datetime(sst.time.values).to_period("M").to_timestamp("M"),   # month end
        "sst_west": box_mean(sst, WEST),
        "sst_east": box_mean(sst, EAST),
    })
    out = out[out["date"] >= "1985-01-01"].reset_index(drop=True)
    out.to_parquet(PROCESSED / "iod_boxes.parquet", index=False)
    span = f"{out.date.min().date()} .. {out.date.max().date()}"
    behind = (pd.Timestamp.today().normalize() - out.date.max()).days
    print(f"monthly SST boxes {span}  rows {len(out)}  (newest month ended {behind} days ago)")
    # sanity: the 2019 positive IOD should stand out in the raw gradient
    g = (out.set_index("date")["sst_west"] - out.set_index("date")["sst_east"])
    print(f"west-east gradient: 2019 Oct {g['2019-10'].mean():+.2f} C vs all-Octobers {g[g.index.month == 10].mean():+.2f} C")


if __name__ == "__main__":
    main()
