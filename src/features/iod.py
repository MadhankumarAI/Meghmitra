"""The Indian Ocean Dipole as model columns, fitted inside the fold.

The raw monthly SST boxes come from data/iod_index.py. The anomalies that make the index are
taken against a weekly climatology built **only from the years a model is allowed to see**, so
a held-out block cannot leak in through the IOD. Columns, appended after the fold-dependent
ones so every consumer keeps the same order:

    [ ...year features..., clim, usual_onset, days_vs_usual, dmi, dmi_3m ]

`dmi` is the index as known on the issue day; `dmi_3m` is its three-month mean, the slow state
that matters across a season.

**Off by default, on measured evidence.** Trained in (2026-09-20, five 7-year blocks), the pair
cost skill at every dry-spell lead -- dry10 week 2 BSS fell from +0.0261 to +0.0148, dry7 week 4
from +0.0044 to -0.0005 -- while buying at most +0.0005 on heavy rain. The trees spent 5-8% of
their gain on it: with ~35 independent seasons the IOD is nearly constant within a held-out
block, so splits on it memorise which years the fold contains rather than how the monsoon
behaves. ENABLED = True reproduces that run; see docs/FINDINGS.md 7e.
"""
from __future__ import annotations
import sys
from functools import lru_cache
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import PROCESSED

ENABLED = False                       # see the note above; the shipped model has no IOD columns
NAMES = ["dmi", "dmi_3m"] if ENABLED else []
PUBLISH_LAG_DAYS = 12         # ERSST v5 lands in the first week of the following month
BOXES = PROCESSED / "iod_boxes.parquet"


@lru_cache(maxsize=8)
def series(keep_years: tuple[int, ...] | None = None) -> pd.DataFrame:
    """Weekly DMI, with the climatology fitted on `keep_years` only (None = every year)."""
    b = pd.read_parquet(BOXES)
    b["month"] = b["date"].dt.month
    base = b if keep_years is None else b[b["date"].dt.year.isin(keep_years)]
    clim = base.groupby("month")[["sst_west", "sst_east"]].mean()
    j = b.join(clim, on="month", rsuffix="_clim")
    dmi = (j["sst_west"] - j["sst_west_clim"]) - (j["sst_east"] - j["sst_east_clim"])
    out = pd.DataFrame({"available": b["date"] + pd.Timedelta(days=PUBLISH_LAG_DAYS),
                        "dmi": dmi.astype(np.float32)})
    out["dmi_3m"] = out["dmi"].rolling(3, min_periods=1).mean().astype(np.float32)
    return out.sort_values("available").reset_index(drop=True)


def columns(year: int, doys: np.ndarray, keep_years: tuple[int, ...] | None = None) -> np.ndarray:
    """(len(doys), 2) of [dmi, dmi_3m] as publishable on each issue day of `year`; empty if off."""
    if not ENABLED:
        return np.zeros((len(np.asarray(doys)), 0), dtype=np.float32)
    s = series(keep_years)
    days = pd.Timestamp(year, 1, 1) + pd.to_timedelta(np.asarray(doys) - 1, unit="D")
    got = pd.merge_asof(pd.DataFrame({"issue": days}).sort_values("issue"), s,
                        left_on="issue", right_on="available", direction="backward")
    return np.nan_to_num(got[NAMES].to_numpy(dtype=np.float32), nan=0.0)


def append(feat: np.ndarray, year: int, doys: np.ndarray, blocks: int,
           keep_years: tuple[int, ...] | None = None) -> np.ndarray:
    """Broadcast the day's IOD across blocks and stick it on the end of `feat`.

    feat is (issues, blocks, F), or (blocks, F) for a single day. A no-op while ENABLED is False.
    """
    if not ENABLED:
        return feat
    cols = columns(year, doys, keep_years)
    wide = np.repeat(cols[:, None, :], blocks, axis=1) if feat.ndim == 3 else np.repeat(cols, blocks, axis=0)
    return np.concatenate([feat, wide.astype(np.float32)], -1)
