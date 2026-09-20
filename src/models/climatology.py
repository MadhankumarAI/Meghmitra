"""Leave-one-year-out climatological probabilities: the reference every model must beat.

P_clim(event | block, issue DOY, lead) for year y is estimated from all other years,
smoothed over +-7 issue days and shrunk toward the all-India value so no block gets
an impossible 0 or 1. Onset is conditional: only (issue, block) pairs where onset
hasn't happened yet count, matching how the target is defined.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import xarray as xr
from scipy.ndimage import uniform_filter1d

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import PROCESSED

HALF_WINDOW = 7          # +-7 issue days
PRIOR_WEIGHT = 2.0       # pseudo-observations pulling toward the national mean
EVENTS = ("dry7", "dry10", "heavy", "onset")


def smooth(a: np.ndarray) -> np.ndarray:
    """Sum over a (2*HALF_WINDOW+1)-day window along the issue axis (axis=-3)."""
    w = 2 * HALF_WINDOW + 1
    return uniform_filter1d(a.astype(np.float64), size=w, axis=-3, mode="nearest") * w


FOLDS = [(1991, 1997), (1998, 2004), (2005, 2011), (2012, 2018), (2019, 2025)]


def fold_of(year: int) -> int:
    for i, (a, b) in enumerate(FOLDS):
        if a <= year <= b:
            return i
    return -1                                     # 1981-1990: climatology only


def _estimate(H, V, keep):
    h, v = H[keep].sum(0), V[keep].sum(0)
    nat = h.sum(-1, keepdims=True) / np.maximum(v.sum(-1, keepdims=True), 1)
    return ((h + PRIOR_WEIGHT * nat) / (v + PRIOR_WEIGHT)).astype(np.float32)


def fold_climatology(t: np.ndarray, years: np.ndarray) -> np.ndarray:
    """Climatology for each year, estimated WITHOUT any year of that year's fold.

    t: (year, issue, lead, block) with 1/0 and -1 for not-applicable.
    Years outside the folds (1981-1990) get the climatology of all fold-free
    years except themselves; they are never scored.
    """
    H, V = smooth(t == 1), smooth(t >= 0)
    folds = np.array([fold_of(int(y)) for y in years])
    out = np.empty(t.shape, np.float32)
    for f in range(len(FOLDS)):
        est = _estimate(H, V, folds != f)
        out[folds == f] = est
    for yi in np.nonzero(folds < 0)[0]:
        keep = np.ones(len(years), bool); keep[yi] = False
        out[yi] = _estimate(H, V, keep)
    return out


def main():
    tg = xr.open_dataset(PROCESSED / "targets.nc")
    ds = xr.Dataset(coords=tg.coords)
    for e in EVENTS:
        t = tg[e].values.astype(np.int8)
        ds[e] = (tg[e].dims, fold_climatology(t, tg.year.values))
        print(f"{e}: clim range {ds[e].values.min():.3f}..{ds[e].values.max():.3f}", flush=True)
    ds.to_netcdf(PROCESSED / "clim_folds.nc", encoding={e: {"zlib": True} for e in EVENTS})
    print("written", PROCESSED / "clim_folds.nc")


if __name__ == "__main__":
    main()
