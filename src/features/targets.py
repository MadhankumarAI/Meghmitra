"""Forecast targets on the fixed issue/lead grid (docs/LABELS.md, "Forecast timing").

Output PROCESSED/targets.nc, dims (year, issue, lead, block):
  dry7, dry10, heavy : uint8   1 if the event touches lead week k
  onset              : int8    1/0, or -1 where not applicable (onset already happened)
Issue index i <-> DOY 121 + i, i = 0..152 (1 May .. 30 Sep; 29 Feb ignored by using DOY).
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import PROCESSED, ONSET_CHECK_DAYS, FALSE_ONSET_DRY_RUN

CONFIRM_DAYS = ONSET_CHECK_DAYS + FALSE_ONSET_DRY_RUN     # 40

ISSUE_DOY0, ISSUE_DOY1 = 121, 273
LEADS = 4
N_ISSUE = ISSUE_DOY1 - ISSUE_DOY0 + 1


def week_any(daily: np.ndarray, doy0: int) -> np.ndarray:
    """daily: (days_in_year, B) bool indexed by DOY-1. Returns (N_ISSUE, LEADS, B)."""
    csum = np.concatenate([np.zeros((1, daily.shape[1]), np.int32),
                           np.cumsum(daily, axis=0, dtype=np.int32)])
    out = np.zeros((N_ISSUE, LEADS, daily.shape[1]), np.uint8)
    for i in range(N_ISSUE):
        d = doy0 + i - 1                       # 0-based day index of issue day
        for k in range(LEADS):
            a, b = d + 7 * k, d + 7 * k + 7
            out[i, k] = (csum[b] - csum[a]) > 0
    return out


def main():
    lab = xr.open_dataset(PROCESSED / "imd_block_labels.nc")
    years = lab.year.values
    B = lab.sizes["block"]
    tt = lab.time.to_index()
    res = {k: np.zeros((len(years), N_ISSUE, LEADS, B), np.uint8) for k in ("dry7", "dry10", "heavy")}
    onset = np.full((len(years), N_ISSUE, LEADS, B), -1, np.int8)

    for yi, yr in enumerate(years):
        sel = tt.year == yr
        for k in res:
            res[k][yi] = week_any(lab[k].values[sel], ISSUE_DOY0)
        od = lab["true_onset_doy"].values[yi]            # (B,) DOY or -1
        for i in range(N_ISSUE):
            d = ISSUE_DOY0 + i
            # An onset is only KNOWN to be true once its 30-day check window has
            # passed. Selecting rows with "onset >= d" would use future rain to
            # decide which forecasts count. Operationally we still forecast for a
            # block until its onset is confirmed; if the onset already happened
            # but is unconfirmed, every future week correctly scores 0.
            # A killing dry run may START as late as day 30 of the check window and
            # is only known to reach 10 days on day 39, so certainty needs 30 + 10.
            confirmed = (od >= 0) & (od + CONFIRM_DAYS <= d - 1)
            pending = ~confirmed
            for k in range(LEADS):
                a, b = d + 7 * k, d + 7 * k + 7
                hit = (od >= a) & (od < b)
                onset[yi, i, k] = np.where(pending, hit.astype(np.int8), -1)

    ds = xr.Dataset({**{k: (("year", "issue", "lead", "block"), v) for k, v in res.items()},
                     "onset": (("year", "issue", "lead", "block"), onset)},
                    coords={"year": years, "issue": np.arange(ISSUE_DOY0, ISSUE_DOY1 + 1),
                            "lead": np.arange(1, LEADS + 1), "block": lab.block.values})
    ds.to_netcdf(PROCESSED / "targets.nc", encoding={v: {"zlib": True} for v in ds.data_vars})

    # --- checks against the daily labels ----------------------------------
    for k in ("dry7", "dry10", "heavy"):
        print(f"{k:6s} base rate by lead: " +
              "  ".join(f"W{l}={ds[k].sel(lead=l).mean().item():.3f}" for l in (1, 2, 3, 4)))
    o = ds["onset"]
    print("onset  applicable share by lead: " +
          "  ".join(f"W{l}={(o.sel(lead=l) >= 0).mean().item():.2f}" for l in (1, 2, 3, 4)))
    # every block with a true onset must be 'hit' exactly once across issue day = onset week
    yi = list(years).index(2023)
    od = lab["true_onset_doy"].values[yi]
    b = int(np.argmax(od > ISSUE_DOY0 + 10))
    i = od[b] - ISSUE_DOY0
    assert onset[yi, i, 0, b] == 1 and onset[yi, i - 7, 1, b] == 1, "onset indexing wrong"
    # the day after onset it is not yet confirmed: still forecast, all weeks 0
    assert (onset[yi, i + 1, :, b] == 0).all(), "unconfirmed past onset must score 0"
    # once the 30-day window has passed it is confirmed: not applicable
    j = i + CONFIRM_DAYS + 1
    if j < N_ISSUE:
        assert (onset[yi, j, :, b] == -1).all(), "confirmed onset must be not-applicable"
    print("onset indexing and confirmation checks pass")


if __name__ == "__main__":
    main()
