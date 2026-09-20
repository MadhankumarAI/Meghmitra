"""Atmosphere frames for the "Understand" view: winds, pressure, moisture + diagnostics.

One frame = one moment on a fixed 0.5 deg grid over 15S-40N, 40-110E (the Indian
monsoon domain: Arabian Sea jet, Bay of Bengal lows, the monsoon trough):

  u850, v850  wind at 850 hPa (m/s)      -> the low-level monsoon jet, drawn as particles
  msl         sea-level pressure (hPa)   -> isobars, lows (L) and the monsoon trough
  tcwv        column water vapour (mm)   -> moisture shading
  t2m         2 m temperature (deg C)    -> heat over the northwest (the heat low)

Sources (same output for both):
  era5   python frames.py era5 2023-06-01 2023-09-30   historical (Google ARCO ERA5, no key)
  gfs    python frames.py gfs                           live NOAA GFS 0.25 run, 0-240 h

Diagnostics are the standard active/break indicators meteorologists use, computed
from the frame itself and written alongside it for the narrative panel.
"""
from __future__ import annotations
import os, sys, json, gzip, time, argparse, subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np

DATA = Path(os.environ.get("MORPHY_DATA", Path.home() / "morphy" / "data"))
OUT = DATA / "exports" / "atmos"
LAT = np.round(np.arange(40.0, -15.0 - 1e-9, -0.5), 2)      # north to south, 111
LON = np.round(np.arange(40.0, 110.0 + 1e-9, 0.5), 2)       # west to east, 141
FIELDS = ("u850", "v850", "msl", "tcwv", "t2m")
OROG_FILE = DATA / "processed" / "atmos_orography_m.npy"
MAX_ELEV_M = 600          # sea-level pressure over higher ground is extrapolated, not measured


def orography() -> np.ndarray:
    """Surface elevation (m) on the frame grid, from ERA5's static surface geopotential."""
    if not OROG_FILE.exists():
        import xarray as xr
        ds = xr.open_zarr("gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3",
                          chunks=None, storage_options=dict(token="anon"))
        z = ds["geopotential_at_surface"]
        if "time" in z.dims:
            # ARCO's time axis runs from 1900 but holds data only from 1940: index 0 is NaN
            z = z.sel(time="2023-01-01T00:00")
        z = z.sel(latitude=slice(40.5, -15.5), longitude=slice(39.5, 110.5))
        elev = regrid(z, "latitude", "longitude") / 9.80665
        assert np.isfinite(elev).mean() > 0.99, "orography came back empty"
        np.save(OROG_FILE, elev)
    return np.load(OROG_FILE)


# ----------------------------------------------------------------- diagnostics
def box(a, la0, la1, lo0, lo1):
    iy = (LAT >= la0) & (LAT <= la1)
    ix = (LON >= lo0) & (LON <= lo1)
    return a[np.ix_(iy, ix)]


def diagnostics(f: dict) -> dict:
    """Active/break indicators from one frame."""
    u, v = f["u850"], f["v850"]
    # mask high ground: its "sea-level" pressure makes fake lows (Tibet, Himalaya, Western Ghats)
    msl = np.where(orography() > MAX_ELEV_M, np.nan, f["msl"])
    d = {}
    # 1. Low-level jet (Findlater jet) over the Arabian Sea: mean westerly at 850 hPa
    d["jet_ms"] = round(float(np.nanmean(box(u, 5, 15, 55, 70))), 1)
    # 2. Monsoon trough axis: for each longitude 75-85E, the latitude of lowest pressure
    #    in 18-30N, averaged. Normal July axis runs ~25-26N here; north of ~27.5N
    #    (hugging the Himalayan foothills) is the classic break signature.
    sub = box(msl, 18, 30, 75, 85)
    lats = LAT[(LAT >= 18) & (LAT <= 30)]
    axis = [lats[int(np.nanargmin(c))] for c in sub.T if np.isfinite(c).any()]
    d["trough_lat"] = round(float(np.mean(axis)), 1)
    # 3. Heat low over the northwest (pressure over NW India vs the Bay)
    d["nw_minus_bay_hpa"] = round(float(np.nanmean(box(msl, 24, 30, 68, 75)) - np.nanmean(box(msl, 15, 22, 85, 92))), 1)
    # 4. Lows: local pressure minima at least 2.5 hPa below their 5-deg surroundings
    lows = []
    a = msl
    for i in range(5, len(LAT) - 5):
        for j in range(5, len(LON) - 5):
            c = a[i, j]
            if not np.isfinite(c):
                continue
            nb = a[i - 1:i + 2, j - 1:j + 2]
            if c > np.nanmin(nb):
                continue
            ring = a[i - 5:i + 6, j - 5:j + 6]
            if np.isnan(ring).mean() > 0.25:
                continue
            depth = float(np.nanmean(ring) - c)
            if depth >= 2.5 and 5 <= LAT[i] <= 30 and 60 <= LON[j] <= 100:
                lows.append({"lat": float(LAT[i]), "lon": float(LON[j]), "hpa": round(float(c), 1),
                             "depth": round(depth, 1)})
    lows.sort(key=lambda x: -x["depth"])
    d["lows"] = lows[:4]
    # 5. Moisture over central India
    d["tcwv_central_mm"] = round(float(np.nanmean(box(f["tcwv"], 18, 26, 74, 84))), 1)
    return d


def write_frame(key: str, when: str, f: dict, source: str):
    OUT.mkdir(parents=True, exist_ok=True)
    rnd = {"u850": 1, "v850": 1, "msl": 1, "tcwv": 0, "t2m": 0}
    rec = {"t": when, "source": source, "lat0": float(LAT[0]), "lon0": float(LON[0]), "d": 0.5,
           "ny": len(LAT), "nx": len(LON), "diag": diagnostics(f)}
    for k in FIELDS:
        rec[k] = [None if not np.isfinite(x) else round(float(x), rnd[k]) for x in f[k].ravel()]
    with gzip.open(OUT / f"{key}.json.gz", "wt", encoding="utf-8") as fh:
        json.dump(rec, fh, separators=(",", ":"))
    return rec["diag"]


def regrid(da, lat_name, lon_name):
    """Interpolate a 2-D xarray field onto the frame grid."""
    return da.interp({lat_name: LAT, lon_name: LON}).values.astype(np.float64)


# ------------------------------------------------------------------ ERA5 (history)
def era5(start: str, end: str, hour: int = 6, workers: int = 6):
    import pandas as pd, xarray as xr
    ds = xr.open_zarr("gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3",
                      chunks=None, storage_options=dict(token="anon"))
    sel = dict(latitude=slice(40.5, -15.5), longitude=slice(39.5, 110.5))
    days = pd.date_range(start, end, freq="D")

    def one(day):
        key = f"era5_{day:%Y-%m-%d}"
        if (OUT / f"{key}.json.gz").exists():
            return f"{key} cached"
        t = day + pd.Timedelta(hours=hour)
        g = lambda v, lev=None: (ds[v].sel(time=t, level=lev) if lev else ds[v].sel(time=t)).sel(**sel)
        f = {"u850": regrid(g("u_component_of_wind", 850), "latitude", "longitude"),
             "v850": regrid(g("v_component_of_wind", 850), "latitude", "longitude"),
             "msl": regrid(g("mean_sea_level_pressure"), "latitude", "longitude") / 100.0,
             "tcwv": regrid(g("total_column_water_vapour"), "latitude", "longitude"),
             "t2m": regrid(g("2m_temperature"), "latitude", "longitude") - 273.15}
        d = write_frame(key, f"{t:%Y-%m-%dT%H:00Z}", f, "ERA5 reanalysis")
        return f"{key} ok  jet {d['jet_ms']} m/s  trough {d['trough_lat']}N  lows {len(d['lows'])}"

    with ThreadPoolExecutor(workers) as ex:
        for msg in ex.map(one, days):
            print(msg, flush=True)


# --------------------------------------------------------------------- GFS (live)
NOMADS = ("https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl?dir=%2Fgfs.{day}%2F{cyc}%2Fatmos"
          "&file=gfs.t{cyc}z.pgrb2.0p25.f{fh:03d}&var_UGRD=on&var_VGRD=on&var_PRMSL=on&var_TMP=on&var_PWAT=on"
          "&lev_850_mb=on&lev_mean_sea_level=on&lev_2_m_above_ground=on"
          "&lev_entire_atmosphere_%5C%28considered_as_a_single_layer%5C%29=on"
          "&subregion=&toplat=41&leftlon=39&rightlon=111&bottomlat=-16")


def latest_gfs_cycle():
    """Most recent GFS cycle whose f240 file exists (runs finish ~4-5 h after cycle time)."""
    import datetime as dt
    now = dt.datetime.now(dt.timezone.utc)
    for back in range(0, 48, 6):
        c = now - dt.timedelta(hours=back)
        day, cyc = c.strftime("%Y%m%d"), f"{(c.hour // 6) * 6:02d}"
        url = NOMADS.format(day=day, cyc=cyc, fh=240)
        r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "-r", "0-0", url],
                           capture_output=True, text=True)
        if r.stdout.strip() in ("200", "206"):
            return day, cyc
    raise RuntimeError("no complete GFS cycle found in the last 48 h")


def gfs(hours=range(0, 241, 12)):
    import datetime as dt, xarray as xr
    day, cyc = latest_gfs_cycle()
    base = dt.datetime.strptime(day + cyc, "%Y%m%d%H").replace(tzinfo=dt.timezone.utc)
    tmp = DATA / "raw" / "gfs"; tmp.mkdir(parents=True, exist_ok=True)
    index = []
    for fh in hours:
        path = tmp / f"gfs_{day}{cyc}_f{fh:03d}.grb2"
        for attempt in range(4):
            r = subprocess.run(["curl", "-s", "-f", "-o", str(path), NOMADS.format(day=day, cyc=cyc, fh=fh)])
            if r.returncode == 0 and path.stat().st_size > 10_000:
                break
            time.sleep(10 * (attempt + 1))
        else:
            print(f"f{fh:03d} FAILED", flush=True); continue
        open_ = lambda **k: xr.open_dataset(path, engine="cfgrib",
                                            backend_kwargs={"filter_by_keys": k, "indexpath": ""})
        pl, ms = open_(typeOfLevel="isobaricInhPa"), open_(typeOfLevel="meanSea")
        hl, at = open_(typeOfLevel="heightAboveGround"), open_(typeOfLevel="atmosphereSingleLayer")
        f = {"u850": regrid(pl["u"], "latitude", "longitude"), "v850": regrid(pl["v"], "latitude", "longitude"),
             "msl": regrid(ms["prmsl"], "latitude", "longitude") / 100.0,
             "tcwv": regrid(at["pwat"], "latitude", "longitude"),
             "t2m": regrid(hl["t2m"], "latitude", "longitude") - 273.15}
        valid = base + dt.timedelta(hours=fh)
        key = f"gfs_f{fh:03d}"
        d = write_frame(key, valid.strftime("%Y-%m-%dT%H:00Z"), f, f"NOAA GFS {day} {cyc}Z +{fh}h")
        index.append({"key": key, "t": valid.strftime("%Y-%m-%dT%H:00Z"), "fh": fh})
        path.unlink()
        print(f"{key} ok  valid {valid:%d %b %H}Z  jet {d['jet_ms']}  trough {d['trough_lat']}N  lows {len(d['lows'])}", flush=True)
    (OUT / "live_index.json").write_text(json.dumps({"run": f"{day}{cyc}", "frames": index}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("source", choices=["era5", "gfs"])
    ap.add_argument("start", nargs="?"); ap.add_argument("end", nargs="?")
    a = ap.parse_args()
    if a.source == "era5":
        era5(a.start, a.end)
    else:
        gfs()
