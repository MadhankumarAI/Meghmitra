"""Village-scale climatology from CHIRPS 5 km, so a forecast can be stated per panchayat.

Two events are computed, because both are shown on the map at village zoom: the chance that a 10+
day dry spell touches a half-month window, and the chance of at least one heavy-rain day (64.5 mm)
inside it. Onset is not here: it is a date, not a per-window probability, and a village-scale onset
would need the whole onset rule re-run on CHIRPS rather than a climatological difference.

  python src/features/village_clim.py

The model issues probabilities per block, which is the scale it was trained and validated at.
Within a block, villages still differ in how dry they normally are, and CHIRPS resolves that at
5 km. This computes, for every CHIRPS cell over India and every half-month window of the season,
the climatological chance that a 10+ day dry spell touches that window (1991-2025), and the same
quantity aggregated to blocks from the same data.

The difference between the two is what a village adds:

    p(village) = p(block, from the model) + [ clim(village cell) - clim(block) ]

Both terms come from CHIRPS, so the correction carries no CHIRPS-versus-IMD bias: it is purely
"this village is normally drier or wetter than its block, by this much, at this time of year".

Writes PROCESSED/village_clim.npz:
  cell, cell_heavy     (nwin, ny, nx) float32   climatological chance per CHIRPS cell
  block, block_heavy   (nwin, nblocks) float32  the same, area-weighted to blocks
  windows              (nwin,) int16            the first day-of-year of each half-month window
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import RAW, PROCESSED, WET_DAY_MM, LONG_DRY_SPELL_DAYS, HEAVY_RAIN_MM

YEARS = range(1991, 2026)
# half-month windows across the season, by day of year: 1 May to 30 September
WINDOWS = np.array([121, 136, 152, 167, 182, 197, 213, 228, 244, 259], dtype=np.int16)
WIN_LEN = 15


def dry_run_touching(dry: np.ndarray, start: int, end: int) -> np.ndarray:
    """(ny, nx) bool: does a run of LONG_DRY_SPELL_DAYS dry days overlap [start, end)?

    `dry` is (days, ny, nx) for one year, indexed by day of year - 1.
    """
    n = LONG_DRY_SPELL_DAYS
    lo, hi = max(0, start - n), min(dry.shape[0], end + n)
    win = dry[lo:hi]
    # a run of n dry days ending at t means the n-day rolling sum is n
    csum = np.concatenate([np.zeros((1,) + win.shape[1:], np.int16), np.cumsum(win, 0, dtype=np.int16)])
    runs = csum[n:] - csum[:-n]                       # (days - n + 1, ny, nx)
    # keep only runs that actually overlap the window
    first = max(0, start - lo - n + 1)
    last = min(runs.shape[0], end - lo)
    return (runs[first:last] == n).any(0) if last > first else np.zeros(win.shape[1:], bool)


def main() -> None:
    import xarray as xr

    files = {y: RAW / "chirps" / f"chirps_india_{y}.nc" for y in YEARS}
    have = [y for y, p in files.items() if p.exists()]
    if not have:
        sys.exit(f"no CHIRPS files in {RAW / 'chirps'}")
    print(f"{len(have)} years of CHIRPS: {have[0]}-{have[-1]}", flush=True)

    counts = heavy_counts = None
    for k, y in enumerate(have):
        with xr.open_dataset(files[y]) as ds:
            rain = np.nan_to_num(ds["precip"].values, nan=0.0)   # (days, ny, nx)
        dry = (rain < WET_DAY_MM).astype(np.int16)
        big = rain >= HEAVY_RAIN_MM
        del rain
        if counts is None:
            counts = np.zeros((len(WINDOWS),) + dry.shape[1:], np.int16)
            heavy_counts = np.zeros_like(counts)
        for w, doy in enumerate(WINDOWS):
            a = int(doy) - 1
            counts[w] += dry_run_touching(dry, a, a + WIN_LEN)
            heavy_counts[w] += big[a:a + WIN_LEN].any(0)
        del dry, big
        print(f"  {y} done ({k + 1}/{len(have)})", flush=True)

    cell = (counts / len(have)).astype(np.float32)
    cell_heavy = (heavy_counts / len(have)).astype(np.float32)
    print(f"cell climatology {cell.shape}, dry mean {cell.mean():.3f}, "
          f"heavy mean {cell_heavy.mean():.3f}", flush=True)

    # the same quantity per block, from the same data, so the difference is unbiased
    w = pd.read_parquet(PROCESSED / "chirps_block_weights.parquet")
    blocks = pd.read_parquet(PROCESSED / "blocks.parquet")["block_id"].tolist()
    pos = {b: i for i, b in enumerate(blocks)}
    bi = w["block_id"].map(pos).to_numpy()
    iy, ix, ww = w["iy"].to_numpy(), w["ix"].to_numpy(), w["w"].to_numpy(dtype=np.float32)

    def to_blocks(grid: np.ndarray) -> np.ndarray:
        out = np.zeros((len(WINDOWS), len(blocks)), np.float32)
        for wi in range(len(WINDOWS)):
            np.add.at(out[wi], bi, grid[wi][iy, ix] * ww)
        return out

    block, block_heavy = to_blocks(cell), to_blocks(cell_heavy)

    out = PROCESSED / "village_clim.npz"
    np.savez_compressed(out, cell=cell, block=block, cell_heavy=cell_heavy, block_heavy=block_heavy,
                        windows=WINDOWS)
    print(f"-> {out}  cell {cell.shape}  block {block.shape}  (dry and heavy rain)")


if __name__ == "__main__":
    main()
