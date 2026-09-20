"""Probabilistic verification: Brier, Brier Skill Score vs climatology, ROC AUC, reliability.

All functions take arrays with identical shape (year, issue, lead, block) and a
target where -1 means not applicable. Scoring is restricted to the evaluation
years (1991-2025) so every model is judged on the same forecasts.
"""
from __future__ import annotations
import numpy as np
from sklearn.metrics import roc_auc_score

EVAL_YEARS = (1991, 2025)
N_BINS = 10


def _flat(p, t, lead_axis=2, lead=None):
    if lead is not None:
        p, t = np.take(p, lead, axis=lead_axis), np.take(t, lead, axis=lead_axis)
    m = t >= 0
    return p[m].astype(np.float64), t[m].astype(np.float64)


def brier(p, t):
    return float(np.mean((p - t) ** 2))


def reliability(p, t, n_bins=N_BINS):
    """Returns (bin mean forecast, observed frequency, count) per bin."""
    edges = np.linspace(0, 1, n_bins + 1)
    idx = np.clip(np.digitize(p, edges) - 1, 0, n_bins - 1)
    cnt = np.bincount(idx, minlength=n_bins)
    fp = np.bincount(idx, p, n_bins) / np.maximum(cnt, 1)
    fo = np.bincount(idx, t, n_bins) / np.maximum(cnt, 1)
    return fp, fo, cnt


def reliability_error(p, t, n_bins=N_BINS):
    """Count-weighted mean |forecast - observed| over bins (expected calibration error)."""
    fp, fo, cnt = reliability(p, t, n_bins)
    return float(np.sum(cnt * np.abs(fp - fo)) / np.sum(cnt))


def summary(p_model, p_clim, target, years, sample=4_000_000, seed=0):
    """Per-lead Brier, BSS vs clim, AUC; plus reliability. Returns a dict."""
    ysel = (years >= EVAL_YEARS[0]) & (years <= EVAL_YEARS[1])
    pm, pc, tg = p_model[ysel], p_clim[ysel], target[ysel]
    rng = np.random.default_rng(seed)
    out = {}
    for li in range(tg.shape[2]):
        a, t = _flat(pm, tg, lead=li)
        c, _ = _flat(pc, tg, lead=li)
        bs, bc = brier(a, t), brier(c, t)
        k = rng.choice(len(t), min(sample, len(t)), replace=False)   # AUC on a sample
        auc = roc_auc_score(t[k], a[k]) if 0 < t[k].mean() < 1 else np.nan
        out[f"W{li + 1}"] = dict(brier=bs, brier_clim=bc, bss=1 - bs / bc, auc=float(auc),
                                  base_rate=float(t.mean()), n=int(len(t)))
    a, t = _flat(pm, tg)
    out["reliability"] = [list(map(float, x)) for x in reliability(a, t)]
    out["reliability_error"] = reliability_error(a, t)
    return out


def bss_map(p_model, p_clim, target, years):
    """BSS per block over all eval years, issues and leads -> (lead, block)."""
    ysel = (years >= EVAL_YEARS[0]) & (years <= EVAL_YEARS[1])
    pm, pc, tg = p_model[ysel], p_clim[ysel], target[ysel].astype(np.float32)
    m = tg >= 0
    se_m = np.where(m, (pm - tg) ** 2, 0).sum((0, 1))
    se_c = np.where(m, (pc - tg) ** 2, 0).sum((0, 1))
    return 1 - se_m / np.maximum(se_c, 1e-12)
