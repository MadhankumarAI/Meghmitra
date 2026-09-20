"""Does CHIRPS (0.05 deg, satellite+gauge) agree with IMD (0.25 deg, gauge) per block?

A mis-mapped grid (e.g. latitude flipped) shows up as near-zero correlation; a
sound one gives high weekly correlation and agreement on dry-spell weeks.
Scored over June-September 1981-2025.
"""
import os, sys
from pathlib import Path
import numpy as np
import xarray as xr

DATA = Path(os.environ.get("MORPHY_DATA", Path.home() / "morphy" / "data"))
P = DATA / "processed"

imd = xr.open_dataset(P / "imd_block_rain.nc")["rain"].load()     # load first: selecting
chi = xr.open_dataset(P / "chirps_block_rain.nc")["rain"].load()  # scattered dates lazily
t = np.intersect1d(imd.time.values, chi.time.values)              # re-decompresses chunks
jjas = t[np.isin(t.astype("datetime64[M]").astype(int) % 12 + 1, [6, 7, 8, 9])]
ia = np.searchsorted(imd.time.values, jjas)
ib = np.searchsorted(chi.time.values, jjas)
assert chi.block.values.tolist() == imd.block.values.tolist(), "block order differs"
a = imd.values[ia].astype(np.float64)                              # (T, B)
b = chi.values[ib].astype(np.float64)
ok = np.isfinite(a).all(0) & np.isfinite(b).all(0)
a, b = a[:, ok], b[:, ok]


def colcorr(x, y):
    x = x - x.mean(0); y = y - y.mean(0)
    return (x * y).sum(0) / np.sqrt((x ** 2).sum(0) * (y ** 2).sum(0))


# weekly totals: consecutive 7-day chunks inside each season
n = (a.shape[0] // 7) * 7
aw = a[:n].reshape(-1, 7, a.shape[1]).sum(1)
bw = b[:n].reshape(-1, 7, b.shape[1]).sum(1)
r_day, r_week = colcorr(a, b), colcorr(aw, bw)
bias = b.mean(0) / np.maximum(a.mean(0), 0.1)

# dry-week agreement: week with <5 mm total counts as dry
dry_a, dry_b = aw < 5, bw < 5
agree = (dry_a == dry_b).mean(0)

print(f"blocks compared: {ok.sum()} of {ok.size}")
print(f"daily  correlation  median {np.median(r_day):.2f}   10th pct {np.percentile(r_day, 10):.2f}")
print(f"weekly correlation  median {np.median(r_week):.2f}   10th pct {np.percentile(r_week, 10):.2f}")
print(f"CHIRPS/IMD JJAS mean ratio  median {np.median(bias):.2f}   IQR "
      f"{np.percentile(bias, 25):.2f}-{np.percentile(bias, 75):.2f}")
print(f"dry-week agreement  median {np.median(agree):.1%}")
print(f"blocks with weekly r < 0.5: {(r_week < 0.5).sum()}")
# a flipped or shifted grid would give ~0 here; guard against it explicitly
assert np.median(r_week) > 0.6, "CHIRPS does not track IMD: check grid orientation"
