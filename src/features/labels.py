"""Compute monsoon event labels on the IMD 0.25 deg grid.

Definitions and justification: docs/LABELS.md
Everything is vectorised over (lat, lon); only the day axis is looped.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (
    WET_DAY_MM, ONSET_WINDOW_DAYS, ONSET_ACCUM_MM, ONSET_CHECK_DAYS,
    FALSE_ONSET_DRY_RUN, DRY_SPELL_DAYS, LONG_DRY_SPELL_DAYS, HEAVY_RAIN_MM,
)


def forward_dry_run(rain: np.ndarray, wet_mm: float = WET_DAY_MM) -> np.ndarray:
    """runlen[t] = number of consecutive dry days starting at t (inclusive).

    rain: (T, Y, X) float array, NaN allowed for sea cells.
    """
    dry = (rain < wet_mm) & np.isfinite(rain)
    T = rain.shape[0]
    run = np.zeros(rain.shape, dtype=np.int16)
    run[T - 1] = dry[T - 1]
    for t in range(T - 2, -1, -1):
        run[t] = np.where(dry[t], run[t + 1] + 1, 0)
    return run


def candidate_onset(rain: np.ndarray) -> np.ndarray:
    """Boolean (T, Y, X): day t starts a 5-day wet spell of >=25 mm with >=3 rainy days.

    Day t must itself be a rainy day, otherwise the onset would be dated to a dry
    day preceding the rain whenever the window still sums past the threshold.
    """
    T = rain.shape[0]
    w = ONSET_WINDOW_DAYS
    r = np.nan_to_num(rain, nan=0.0)
    wet = (rain >= WET_DAY_MM) & np.isfinite(rain)

    # rolling forward sums via cumulative sum (pad so window [t, t+w-1] is valid)
    csum = np.concatenate([np.zeros((1,) + r.shape[1:]), np.cumsum(r, axis=0)], axis=0)
    cwet = np.concatenate([np.zeros((1,) + r.shape[1:]), np.cumsum(wet, axis=0)], axis=0)

    acc = np.full(rain.shape, np.nan)
    nwet = np.zeros(rain.shape, dtype=np.int16)
    end = T - w + 1
    acc[:end] = csum[w:T + 1] - csum[0:end]
    nwet[:end] = (cwet[w:T + 1] - cwet[0:end]).astype(np.int16)

    return (acc >= ONSET_ACCUM_MM) & (nwet >= 3) & wet


def onset_labels(rain: np.ndarray, start: np.ndarray | None = None):
    """Scan the season for false and true onsets.

    start: optional (Y, X) day index before which rain can't count as onset
    (pre-monsoon convection; see features/onset_normal.py).

    Returns
    -------
    true_onset  : (Y, X) int16  day index of the true onset, -1 if none
    n_false     : (Y, X) int16  how many false onsets preceded it
    first_false : (Y, X) int16  day index of the first false onset, -1 if none
    """
    T, Y, X = rain.shape
    cand = candidate_onset(rain)
    if start is not None:
        cand &= np.arange(T)[:, None, None] >= start[None]
    run = forward_dry_run(rain)

    true_onset = np.full((Y, X), -1, dtype=np.int16)
    first_false = np.full((Y, X), -1, dtype=np.int16)
    n_false = np.zeros((Y, X), dtype=np.int16)
    # cells may not be re-examined until the killing dry spell has passed
    blocked_until = np.zeros((Y, X), dtype=np.int16)
    resolved = ~np.isfinite(rain[0])          # sea / missing cells are done

    for t in range(T):
        active = (~resolved) & cand[t] & (t >= blocked_until)
        if not active.any():
            continue
        # does a >=10 day dry run begin anywhere in the next 30 days?
        hi = min(T, t + ONSET_CHECK_DAYS + 1)
        worst = run[t:hi].max(axis=0)
        killed = active & (worst >= FALSE_ONSET_DRY_RUN)
        held = active & ~killed

        true_onset[held] = t
        resolved |= held

        if killed.any():
            n_false[killed] += 1
            newly = killed & (first_false < 0)
            first_false[newly] = t
            # resume only after the dry spell that killed it
            dry_start = run[t:hi].argmax(axis=0) + t
            skip = dry_start + np.take_along_axis(
                run, np.clip(dry_start, 0, T - 1)[None], axis=0
            )[0]
            blocked_until = np.where(killed, np.minimum(skip, T).astype(np.int16),
                                     blocked_until)
    return true_onset, n_false, first_false


def spell_labels(rain: np.ndarray):
    """Per-day boolean labels for dry spells and heavy rain.

    dry7/dry10 mark every day on which a qualifying dry spell is ACTIVE, so a
    weekly aggregate answers "was the block in a break during this week?".
    """
    run = forward_dry_run(rain)
    T = rain.shape[0]
    dry7 = np.zeros(rain.shape, dtype=bool)
    dry10 = np.zeros(rain.shape, dtype=bool)
    # A spell of length L starting at s covers [s, s+L). Mark the starts, then
    # carry the remaining length forward day by day.
    for thresh, out in ((DRY_SPELL_DAYS, dry7), (LONG_DRY_SPELL_DAYS, dry10)):
        starts = run >= thresh
        cover = np.zeros(rain.shape[1:], dtype=np.int16)
        for t in range(T):
            cover = np.where(starts[t], run[t], np.maximum(cover - 1, 0))
            out[t] = cover > 0
    heavy = (rain >= HEAVY_RAIN_MM) & np.isfinite(rain)
    return dry7, dry10, heavy


def weekly(labels_daily: np.ndarray, season_start: int = 0) -> np.ndarray:
    """Collapse (T, Y, X) daily booleans to (n_weeks, Y, X) 'happened that week'."""
    T = labels_daily.shape[0]
    n = T // 7
    trimmed = labels_daily[season_start:season_start + n * 7]
    return trimmed.reshape(n, 7, *labels_daily.shape[1:]).any(axis=1)
