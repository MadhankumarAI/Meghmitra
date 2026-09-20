"""Teleconnection signatures: each block's own response to each planetary state.

The design goal is to downscale the signatures of ENSO/IOD/MJO to a block. Feeding a
raw index to a model makes it overfit: the MJO is one number per day for all of
India, so millions of rows carry only ~4,000 independent MJO days. Instead we
estimate, per block, per half-month of the season, per lead week:

    P(event | planetary state at issue time)  -  P(event)          (anomaly)

from training years only, pooled over neighbours within 150 km and shrunk toward
the block's normal so thin evidence fades to "no signal" instead of inventing one.

States: MJO phase 1-8 when amplitude >= 1, else 0 ("weak"); ENSO La Nina / neutral /
El Nino by weekly Nino 3.4 at +-0.5 C. Unknown state (before the index exists) = -1.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

BIN_EDGES = np.array([0, 15, 30, 45, 60, 75, 90, 105, 120, 135, 153])   # issue-index bins
N_BINS = len(BIN_EDGES) - 1
PRIOR = 30.0          # pseudo-observations toward the block's normal (per pooled cell)
SMOOTH = np.array([0.25, 0.5, 0.25])                                 # across adjacent bins


def issue_bin(n_issue: int) -> np.ndarray:
    return np.searchsorted(BIN_EDGES, np.arange(n_issue), side="right") - 1


def state_tables(indices_asof: pd.DataFrame, years, issue_doys):
    """(year, issue) arrays of MJO phase (0..8) and ENSO state (0..2); -1 if unknown."""
    ix = indices_asof.set_index("issue_date")
    Y, I = len(years), len(issue_doys)
    mjo = np.full((Y, I), -1, np.int8)
    enso = np.full((Y, I), -1, np.int8)
    for yi, y in enumerate(years):
        dates = pd.Timestamp(int(y), 1, 1) + pd.to_timedelta(np.asarray(issue_doys) - 1, unit="D")
        rows = ix.reindex(dates)
        amp, ph, n34 = rows["mjo_amp"].values, rows["mjo_phase"].values, rows["nino34"].values
        ok = np.isfinite(amp) & np.isfinite(ph)
        mjo[yi, ok] = np.where(amp[ok] >= 1.0, ph[ok], 0).astype(np.int8)
        ok = np.isfinite(n34)
        enso[yi, ok] = np.where(n34[ok] >= 0.5, 2, np.where(n34[ok] <= -0.5, 0, 1)).astype(np.int8)
    return mjo, enso


def per_year_counts(T: np.ndarray, state: np.ndarray, n_states: int):
    """Hits and valid counts per (year, state, bin, lead, block).

    T: (Y, I, L, B) int8 targets with -1 = not applicable. state: (Y, I).
    """
    Y, I, L, B = T.shape
    H = np.zeros((Y, n_states, N_BINS, L, B), np.float32)
    V = np.zeros_like(H)
    hit, val = (T == 1), (T >= 0)
    for y in range(Y):
        for s in range(n_states):
            m = (state[y] == s)[:, None, None]
            if not m.any():
                continue
            # cast first: np.add.reduceat on booleans is a logical OR, not a count
            H[y, s] = np.add.reduceat((hit[y] & m).astype(np.float32), BIN_EDGES[:-1], axis=0)
            V[y, s] = np.add.reduceat((val[y] & m).astype(np.float32), BIN_EDGES[:-1], axis=0)
    return H, V


def _smooth_bins(a: np.ndarray) -> np.ndarray:
    """Weighted smoothing across adjacent season bins (axis -3), edges renormalised."""
    out = np.zeros_like(a)
    wsum = np.zeros(a.shape[-3], np.float32)
    for k, w in zip((-1, 0, 1), SMOOTH):
        src = np.arange(a.shape[-3]) + k
        ok = (src >= 0) & (src < a.shape[-3])
        out[..., ok, :, :] += w * a[..., src[ok], :, :]
        wsum[ok] += w
    return out / wsum[:, None, None]


def estimate(H, V, keep: np.ndarray, N150):
    """Signature anomaly (state, bin, lead, block) from the kept years only."""
    h, v = H[keep].sum(0), V[keep].sum(0)                     # (S, nb, L, B)
    S, nb, L, B = h.shape
    # pool over neighbours: sparse (B,B) row-normalised average applied to counts
    pool = lambda a: (N150 @ a.reshape(-1, B).T).T.reshape(a.shape)
    h, v = pool(_smooth_bins(h)), pool(_smooth_bins(v))
    base = h.sum(0) / np.maximum(v.sum(0), 1e-6)              # block normal over all states
    p = (h + PRIOR * base) / (v + PRIOR)
    return (p - base).astype(np.float32)


def lookup(sig: np.ndarray, state_row: np.ndarray, bins: np.ndarray, lead: int, blk: np.ndarray):
    """Gather sig[state, bin, lead, block] for rows (issue x block); unknown state -> 0."""
    s = np.clip(state_row, 0, None)
    val = sig[s[:, None], bins[:, None], lead, blk[None, :]]
    return np.where((state_row >= 0)[:, None], val, 0.0).astype(np.float32)
