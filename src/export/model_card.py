"""Model card: what the model is, what goes into it, how it was trained and how it scores.

  python model_card.py

Everything is read from the artifacts themselves - the trained models' metadata, the scoring
run, the label definitions and the index/rainfall files - so the card cannot drift from the
system it describes. Writes EXPORTS/model_card.json, rendered on the Evidence page.
"""
from __future__ import annotations
import sys, json
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import PROCESSED, EXPORTS, RAW, WET_DAY_MM, HEAVY_RAIN_MM, ONSET_ACCUM_MM, ONSET_WINDOW_DAYS, \
    FALSE_ONSET_DRY_RUN, ONSET_CHECK_DAYS, DRY_SPELL_DAYS, LONG_DRY_SPELL_DAYS
from models.climatology import FOLDS, PRIOR_WEIGHT
from models.gbm import PARAMS, YEARS
from features.targets import ISSUE_DOY0, ISSUE_DOY1, CONFIRM_DAYS
from export.explain_json import GROUPS

EVENT_LABEL = {"onset": "Monsoon onset", "dry10": "10+ day dry spell", "dry7": "7+ day dry spell",
               "heavy": "Heavy-rain day"}


def main() -> None:
    import xarray as xr
    import pandas as pd

    meta = json.loads((PROCESSED / "final_models" / "meta.json").read_text())
    scores = json.loads((PROCESSED / "gbm_scores_fast.json").read_text())
    rain = xr.open_dataset(PROCESSED / "imd_block_rain.nc")
    blocks = int(rain.sizes["block"])
    idx = pd.read_parquet(PROCESSED / "indices_asof.parquet")
    idx_through = str(pd.to_datetime(idx["issue_date"]).max())[:10]

    # feature importance (gain) folded into the same six drivers the explanations use
    group_of = {f: g for g, fs in GROUPS.items() for f in fs}
    gain: dict[str, dict[str, float]] = {}
    for model, imp in scores["importance"].items():
        g: dict[str, float] = {}
        for f, v in imp.items():
            g[group_of.get(f, "other")] = g.get(group_of.get(f, "other"), 0.0) + float(v)
        gain[model] = {k: round(v, 4) for k, v in sorted(g.items(), key=lambda kv: -kv[1])}

    matrix = {}
    for e, s in scores["scores"].items():
        matrix[e] = {"label": EVENT_LABEL.get(e, e), "reliability_error": round(s["reliability_error"], 4),
                     "weeks": [{"week": k, "bss": round(s[f"W{k}"]["bss"], 4), "auc": round(s[f"W{k}"]["auc"], 4),
                                "brier": round(s[f"W{k}"]["brier"], 4), "brier_clim": round(s[f"W{k}"]["brier_clim"], 4),
                                "base_rate": round(s[f"W{k}"]["base_rate"], 4), "n": int(s[f"W{k}"]["n"])}
                               for k in (1, 2, 3, 4)]}

    rt = sorted(RAW.joinpath("imd_rt").glob("*.grd"))
    card = {
        "product": "CMRI v1.0-draft",
        "generated": pd.Timestamp.now(tz="Asia/Kolkata").strftime("%Y-%m-%d"),
        "model": {
            "type": "LightGBM gradient-boosted trees, binary objective (one model per event and lead week)",
            "params": {k: v for k, v in PARAMS.items() if k != "verbose"},
            "count": len(meta["models"]),
            "trained_on": f"{int(YEARS[0])}-{int(YEARS[-1])}",
            "models": meta["models"],
            "sampling": meta["sampling"],
            "early_stopping_years": meta["val_years"],
            "calibration": "none: the raw probability is published (reliability measured, see matrix)",
        },
        "predicts": {
            "events": [EVENT_LABEL[e] for e in meta["events"]],
            "leads": "weeks 1-4 ahead",
            "blocks": blocks,
            "issued": f"daily, DOY {ISSUE_DOY0}-{ISSUE_DOY1} (1 May - 30 Sep)",
        },
        "labels": {
            "wet_day_mm": WET_DAY_MM, "heavy_mm": HEAVY_RAIN_MM,
            "dry_spell_days": [DRY_SPELL_DAYS, LONG_DRY_SPELL_DAYS],
            "onset": f"{ONSET_ACCUM_MM:g} mm in {ONSET_WINDOW_DAYS} days with at least 3 wet days, starting on a wet day",
            "false_onset": f"a dry run of {FALSE_ONSET_DRY_RUN}+ days within {ONSET_CHECK_DAYS} days of the sowing rain",
            "onset_confirmed_after_days": CONFIRM_DAYS,
        },
        "features": {"count": len(meta["features"]), "names": meta["features"], "groups": {g: fs for g, fs in GROUPS.items()},
                     "gain_by_group": gain},
        "validation": {
            "protocol": f"{len(FOLDS)} contiguous blocks of {FOLDS[0][1] - FOLDS[0][0] + 1} years, each held out whole",
            "folds": [f"{a}-{b}" for a, b in FOLDS],
            "nested": "climatology, usual-onset date and every fold-dependent input are rebuilt without the held-out years",
            "climatology_prior_weight": PRIOR_WEIGHT,
            "scored_model": "v1 'fast' settings (the published model)",
        },
        "matrix": matrix,
        "inputs": {
            "rainfall": {"source": "IMD 0.25 deg gridded rainfall", "history": f"{int(rain.time.dt.year.min())}-{int(rain.time.dt.year.max())}",
                         "realtime_days_held": len(rt),
                         "realtime": "imdlib real-time grids, fetched daily"},
            "mjo": {"source": "NOAA PSL ROMI", "through": idx_through},
            "enso": {"source": "NOAA CPC weekly Nino 3.4", "through": idx_through},
            "boundaries": {"source": "geoBoundaries ADM3 (CC BY 4.0)", "blocks": blocks},
            "not_used_by_the_model": "ERA5 / NOAA GFS fields power the 'Understand' weather view only",
        },
        "runtime": {
            "training": "one pass over 1991-2025 on 20 CPU threads; no GPU",
            "daily_run": "one forecast run (a few minutes) plus a static file refresh; no inference server",
            "explanations": "exact tree SHAP per block for week 1, published with each day's forecast",
        },
    }
    out = EXPORTS / "model_card.json"
    out.write_text(json.dumps(card, indent=1))
    print(f"model card -> {out}  ({len(meta['models'])} models, {len(meta['features'])} features, {blocks} blocks)")


if __name__ == "__main__":
    main()
