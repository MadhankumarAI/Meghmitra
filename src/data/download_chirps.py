"""Download CHIRPS v2.0 daily 0.05 deg, crop to the India box, delete the global file.

Runs on the server. ~1.1 GB per global year -> ~70 MB per cropped year.
"""
import os, sys, subprocess, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import xarray as xr

DATA = Path(os.environ.get("MORPHY_DATA", Path.home() / "morphy" / "data"))
OUT = DATA / "raw" / "chirps"; OUT.mkdir(parents=True, exist_ok=True)
URL = "https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_daily/netcdf/p05/chirps-v2.0.{y}.days_p05.nc"
BOX = dict(latitude=slice(6.0, 38.5), longitude=slice(66.0, 100.5))

def one(y):
    final = OUT / f"chirps_india_{y}.nc"
    if final.exists() and final.stat().st_size > 1e6:
        return f"{y} cached"
    raw = OUT / f"_global_{y}.nc"
    for attempt in range(5):
        r = subprocess.run(["curl", "-sfL", "--retry", "3", "-C", "-", "-o", str(raw), URL.format(y=y)])
        if r.returncode == 0: break
        time.sleep(20 * (attempt + 1))
    else:
        return f"{y} DOWNLOAD FAILED"
    ds = xr.open_dataset(raw)
    ds = ds.sel(**BOX)
    ds["precip"].astype("float32").to_dataset().to_netcdf(
        final, encoding={"precip": {"zlib": True, "complevel": 4}})
    ds.close(); raw.unlink()
    return f"{y} ok {final.stat().st_size/1e6:.0f} MB"

if __name__ == "__main__":
    y0, y1 = int(sys.argv[1]), int(sys.argv[2])
    with ThreadPoolExecutor(3) as ex:          # 3 parallel: polite to UCSB
        for msg in ex.map(one, range(y0, y1 + 1)):
            print(msg, flush=True)
