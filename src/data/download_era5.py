"""ERA5 daily means over 20S-40N, 40E-160E from the Copernicus CDS (runs on the server).

Why CDS and not ARCO-ERA5: docs/DECISIONS.md. Daily means are computed by CDS in
IST (UTC+05:30) so an ERA5 "day" lines up with Indian calendar days.

  python download_era5.py --test          one tiny request per variable: validates
                                          names and licences in minutes
  python download_era5.py 1981 2025       full download, resumable, 6 in parallel
"""
from __future__ import annotations
import os, sys, time, argparse, traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DATA = Path(os.environ.get("MORPHY_DATA", Path.home() / "morphy" / "data"))
OUT = DATA / "raw" / "era5"; OUT.mkdir(parents=True, exist_ok=True)
AREA = [40, 40, -20, 160]                     # N, W, S, E

PL = "derived-era5-pressure-levels-daily-statistics"
SL = "derived-era5-single-levels-daily-statistics"
# (dataset, CDS variable name, pressure level or None, short name)
VARS = [
    (PL, "u_component_of_wind", "850", "u850"),
    (PL, "v_component_of_wind", "850", "v850"),
    (PL, "specific_humidity", "850", "q850"),
    (PL, "u_component_of_wind", "200", "u200"),
    (PL, "geopotential", "500", "z500"),
    (SL, "mean_sea_level_pressure", None, "msl"),
    (SL, "total_column_water_vapour", None, "tcwv"),
    (SL, "mean_top_net_long_wave_radiation_flux", None, "olr"),
    (SL, "volumetric_soil_water_layer_1", None, "swvl1"),
    (SL, "sea_surface_temperature", None, "sst"),
]


def request(dataset, var, level, year, months):
    r = {
        "product_type": "reanalysis",
        "variable": [var],
        "year": str(year),
        "month": [f"{m:02d}" for m in months],
        "day": [f"{d:02d}" for d in range(1, 32)],
        "daily_statistic": "daily_mean",
        "time_zone": "utc+05:30",
        "frequency": "6_hourly",
        "area": AREA,
    }
    if level:
        r["pressure_level"] = [level]
    return r


def fetch(task):
    import cdsapi
    dataset, var, level, short, year, months, path = task
    if path.exists() and path.stat().st_size > 10_000:
        return f"{short} {year} cached"
    tmp = path.with_suffix(".part")
    for attempt in range(4):
        try:
            cdsapi.Client(quiet=True).retrieve(dataset, request(dataset, var, level, year, months), str(tmp))
            tmp.rename(path)
            return f"{short} {year} ok {path.stat().st_size / 1e6:.0f} MB"
        except Exception as e:
            msg = str(e).splitlines()[0][:200]
            if "licen" in msg.lower() or "not found" in msg.lower() or "invalid" in msg.lower():
                return f"{short} {year} FATAL {msg}"          # retrying won't help
            time.sleep(60 * (attempt + 1))
    return f"{short} {year} FAILED after retries: {msg}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("years", nargs="*", type=int)
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    if a.test:
        tasks = [(d, v, l, s, 2023, [7], OUT / f"_test_{s}.nc") for d, v, l, s in VARS]
    else:
        y0, y1 = a.years
        tasks = [(d, v, l, s, y, range(1, 13), OUT / f"{s}_{y}.nc")
                 for y in range(y0, y1 + 1) for d, v, l, s in VARS]
    print(f"{len(tasks)} requests, {a.workers} in parallel", flush=True)
    with ThreadPoolExecutor(a.workers) as ex:
        for msg in ex.map(fetch, tasks):
            print(msg, flush=True)
    if a.test:
        import xarray as xr
        for d, v, l, s in VARS:
            p = OUT / f"_test_{s}.nc"
            if p.exists():
                ds = xr.open_dataset(p)
                name = list(ds.data_vars)[0]
                print(f"  {s}: var '{name}' dims {dict(ds[name].sizes)} "
                      f"range {float(ds[name].min()):.3g}..{float(ds[name].max()):.3g}")


if __name__ == "__main__":
    main()
