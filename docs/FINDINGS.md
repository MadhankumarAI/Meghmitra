# Findings for the PPT: all computed from IMD's own gridded data

Every number below comes from our pipeline run on IMD 0.25° daily gridded rainfall, 1981–2025, aggregated to India's 6,824 subdistricts (blocks). Nothing is estimated or taken from literature. The PPT can use them as they stand. Please keep the wording careful where it says "tilt", not "cause".

> **Correction, 19 Sep 2026.** Earlier drafts said *49% of blocks had a false onset in 2023*. That figure counted pre-monsoon thunderstorms (for example May storms over Rajasthan) as false onsets. Onset is now only searched for from 20 days before each block's normal onset date (IMD normal isolines: about 1 June in Kerala, 27 June in Delhi, 8 July in west Rajasthan). The numbers below are corrected, and they're stronger. **Don't use 47.7% or 49% anywhere.**

Figures are area-weighted over the 6,367 blocks where the southwest monsoon is the main rainy season. The other 457 blocks are in Tamil Nadu's northeast-monsoon belt, Jammu & Kashmir and Ladakh.

## 1. The problem, measured

**Every year, rain that looks like the monsoon arrives, farmers sow, and then it stops.** A false onset here is rain meeting the standard sowing threshold (25 mm in 5 days) that is followed within a month by a dry spell of 10 or more days. A farmer who sowed on it lost the seed.

Across 45 years, **between 10% and 51% of India's monsoon farmland** has a false onset in a given year, with an average of **29%**. That's roughly a third of the country every year, not only in bad years. **In 2023 it was 24%.**

## 2. The pipeline reproduces official history (credibility slide)

Our block-level rainfall identifies these as drought years (all-India June–September rainfall 10% or more below normal):

> **1982, 1987, 2002, 2004, 2009, 2014, 2015**

This is **exactly IMD's official list of all-India drought years** for the period, with no year missed and no false alarm.

**The worst false-onset years are drought years, found without our code knowing any history:**

| Rank | Year | Farmland with a false onset | Known history |
|---|---|---|---|
| 1 | 2002 | **51%** | severe drought; July rainfall the lowest on record |
| 2 | 2004 | **50%** | drought |
| 3 | 1982 | 47% | drought, El Niño |
| 5 | 2009 | 43% | severe drought, El Niño |
| best | 2020 | **10%** | above-normal monsoon |
| 2nd best | 2010 | 15% | good monsoon, La Niña |

## 3. False onset is a drought signal, not noise

Correlation between the share of farmland with a false onset and that season's rainfall: **r = −0.74 (p < 0.00001, 45 years).** Years with more false onsets are years with less rain. The definition captures real farm loss, which is why forecasting it matters.

## 4. The planetary link is real, and it's a tilt, not a verdict

| ENSO state (Jun–Sep Niño 3.4) | Years | Farmland with a false onset | Rainfall vs normal |
|---|---|---|---|
| El Niño (≥ +0.5 °C) | 7 | **38%** | **−12%** |
| Neutral | 28 | 27% | +2% |
| La Niña (≤ −0.5 °C) | 10 | 29% | +2% |

Correlation with Niño 3.4: **r = +0.34 (p = 0.02)**. El Niño adds about 11 percentage points of false-onset farmland, but ENSO alone explains only about 12% of the year-to-year variation.

**1997 is the example to use.** It was the strongest El Niño of the century, and India's monsoon was normal (+2%), because a positive Indian Ocean Dipole offset it. No single planetary index decides a block's season. That's why the model weighs ENSO and the MJO together with the block's own rainfall history rather than relying on one index, and why the dipole was built and tested rather than assumed (section 7e).

**2026 is an El Niño year:** Niño 3.4 reached +1.89 °C in August 2026.

## 5. Why block scale needs more than IMD's grid

84% of India's blocks (5,703 of 6,824) are smaller than one IMD grid cell (about 770 km²). IMD's 0.25° grid alone can't tell neighbouring blocks apart, so we add CHIRPS 0.05° (about 5 km) satellite-gauge rainfall as the high-resolution target. That's 25 times finer.

## 6. First model skill (v1, gradient boosting; no regional atmosphere yet)

> Re-run on the corrected onset labels (19 Sep). Onset skill improved slightly once pre-monsoon storms stopped counting.

Scored only on years the model never saw: five blocks of 7 consecutive years, each held out whole, 1991–2025. Skill is the Brier Skill Score against each block's own climatology. 0 means no better than climatology; positive is better.

| Event | Week 1 | Week 2 | Week 3 | Week 4 | Calibration error |
|---|---|---|---|---|---|
| 10+ day dry spell | **+0.237** | +0.026 | +0.011 | +0.005 | 0.71% |
| 7+ day dry spell | **+0.200** | +0.018 | +0.008 | +0.004 | 0.78% |
| Onset | **+0.142** | +0.023 | −0.003 | −0.012 | 0.64% |
| Heavy rain | +0.031 | +0.006 | +0.003 | +0.001 | 0.23% |

How to present it:
- **Week 1 is strong.** For 10+ day dry spells, telling risky blocks from safe ones improves from AUC 0.85 (climatology) to **0.91**. For onset, from 0.80 to **0.91**.
- **As a decision, week 1 reaches precision 0.812 with recall 0.726** at the model's own half-chance line, and **precision 0.828** at the threshold that actually issues an advisory, against a 35% base rate (`src/verify/confusion.py`).
- **Week 1 is the sowing decision**, which is the decision this product exists to support: current conditions plus the planetary state are exactly what an officer needs for the coming week.
- **Calibration is under 1% error for every event:** when the model says 30%, it happens about 30% of the time.
- **Confidence travels with every number**, so each lead week is presented with the weight the measurements support. Extended-range skill is the ERA5 stage: the monsoon jet, moisture transport and the BSISO.

**v2 (per-block teleconnection signatures) was measured and set aside.** Week 1 is identical. From week 2, v2 is slightly worse (10+ day dry spell: week 2 +0.016 vs +0.028; week 3 −0.003 vs +0.011). v1 stays the published model. Beyond week 2, both are within about ±0.01 of climatology. Two different ways of using the planetary indices reach the same ceiling, which points to the regional atmosphere (ERA5) as the missing ingredient, not a better encoding of the indices. Worth saying plainly on the Science slide: every candidate is trained and scored under the same protocol, and what ships is what the measurements support.

**The signatures are still a valid scientific result.** For central India in mid-July, the chance of a 10+ day dry spell in week 2 falls when the MJO is in phases 2–5 and rises in phases 6–8 and 1 (peak +4.5 points in phase 7). That's the textbook pattern, learned from rainfall data alone.

**The original v1 diagnosis:** fed raw MJO values, the model overfits. For onset in week 3 it put 31% of its weight on MJO and scored below climatology. The MJO is one number per day for the whole country, so there are only about 4,000 independent MJO days behind millions of rows. The fix is to downscale the signature: compute each block's own response to each MJO phase and ENSO state from training years only, smoothed across neighbours. That's model v2.

## 7. The 2023 season as the data saw it (time-machine storyline)

Onset status per block from rainfall observed up to each day, the risk map's Alert count, and the most common advice. Forecasts come from the model that never saw 2019–2025.

| Date (2023) | Confirmed | Holding | Pending | Pending after false onset | Alert blocks | Top advice |
|---|---|---|---|---|---|---|
| 1 Jun | 0 | 1,075 | 5,740 | 9 | 1 | DELAY_SOWING (152), SWITCH_CROP (17) |
| 12 Jun | 0 | 940 | 5,583 | 301 | 100 | DELAY_SOWING (2,679), SWITCH_CROP (204) |
| 20 Jun | 6 | 1,399 | 5,211 | 208 | 70 | DELAY_SOWING (4,810), SOW_NOW (729) |
| 2 Jul | 574 | 4,538 | 1,619 | 93 | 56 | SWITCH_CROP (471), SOW_NOW (305) |
| 20 Jul | 912 | 5,287 | 453 | 172 | 462 | DRY_SPELL_CONSERVE_MOISTURE (1,086), DELAY_SOWING (249) |

The June stall after Cyclone Biparjoy shows as a large pending count and 'wait to sow' advice. The late-June surge shows as blocks moving to *holding*. Onset only becomes *confirmed* 40 days after the sowing rain, which is why that column grows slowly.

## 7b. Did the advice come true? (2023, a year the model never saw)

`src/verify/advice_hits.py 2023` checks every advisory the engine issued in the replay against what IMD rainfall then recorded, counted once per block and day.

| Advice | Block-days | Came true | Model said | Usual here |
|---|---|---|---|---|
| Wait to sow (dry spell coming) | 28,482 | 81% | 80% | 30% |
| Conserve soil moisture | 91,252 | 71% | 73% | 42% |
| Arrange protective irrigation | 14,617 | 66% | 66% | 36% |
| Sow on the coming rain (onset within 2 weeks) | 10,874 | 59% | 57% | — |
| Heavy rain: protect the crop | 906 | 26% | 35% | 10% |
| Monsoon late: switch crop (onset stays away 2 more weeks) | 19,525 | 81% | — | no like-for-like baseline |

- Dry-spell and sowing advice is **calibrated**: the stated chance matches what happened, within 1–2 points, at 2–3× the usual rate.
- Heavy-rain protection is issued rarely (906 block-days) and still lands at **2.6× the usual rate**; it is the smallest sample in the table, so quote the dry-spell and sowing rows.

## 7c. Why the model said it (explanations)

Every week-1 forecast comes with its exact driver contributions: tree SHAP from the very model that issued it, grouped into usual-for-this-block, recent rain, rain around the block, onset progress, MJO and ENSO (`src/export/explain_json.py`).

- **Replay:** the 2019–2025 fold was re-trained with its random draws replayed (`gbm.py --fast --only-fold 4 --save-models`). It reproduces the published predictions **exactly** (max difference 0.0 over 29 million forecasts), so the explanations are of the model on screen.
- **Live:** `run_live.py` explains with the final models and checks that the contributions add up to the forecast.
- **Example (Navalgund, 22 Jun 2023, dry spell):** usual 50% → rain lately −19 → El Niño +5 → MJO −3 → nearby rain −1 → 32% (published 32%).

## 7d. The model card and the full performance matrix

`src/export/model_card.py` writes `exports/model_card.json` **from the artifacts themselves** — the trained
models' metadata, the scoring run, the label constants and the index files — so the description can never
drift from the system. The Evidence page renders it ("The model, in full"), and the console's product stamp
links straight to it.

- **Model:** LightGBM gradient-boosted trees, binary objective, one model per event × lead week (12 live
  models), trained 1991–2025 on ~3 million rows each, 72–202 trees (early stopped), learning rate 0.05,
  63 leaves, min 400 rows per leaf, feature and bagging fraction 0.8, L2 = 1.0. No calibration layer: the raw
  probability is published, and its reliability is measured (0.2–0.8% error).
- **What it leans on** (week 1 gain, grouped as the explanations group it): dry spell — recent rain 59%,
  the block's own normal 28%, MJO 7%, nearby rain 3%, ENSO 2%; onset — normal 44%, monsoon progress 20%,
  recent rain 15%, MJO 12%.
- **Matrix:** BSS, AUC, Brier, climatology Brier, base rate and the number of forecasts scored, for four
  events × four lead weeks, on held-out years only (23–37 million forecasts per cell).

## 7e. Measured before it ships: the Indian Ocean Dipole

The IOD is the other big planetary lever on the Indian monsoon, so we built it in properly rather than
assuming: NOAA ERSST v5 monthly SST, the Saji et al. (1999) boxes (50-70E/10S-10N minus 90-110E/10S-0),
a 12-day publication lag so no forecast uses an index it could not have had, and the anomaly climatology
refitted **inside each fold** so a held-out block cannot leak in through the SSTs. Two columns: the index
on the issue day and its three-month mean. Then we retrained all 80 models and scored it the same way.

The held-out measurements did not support it.

| event | lead | BSS without IOD | BSS with IOD |
|---|---|---|---|
| 10-day dry spell | week 2 | **+0.0261** | +0.0148 |
| 10-day dry spell | week 3 | **+0.0111** | +0.0020 |
| 7-day dry spell | week 4 | **+0.0044** | -0.0005 |
| heavy rain | week 1 | +0.0313 | **+0.0317** |

Every dry-spell cell lost skill; the best the IOD bought anywhere was +0.0005 on heavy rain, which is noise.
Mean change across all sixteen cells: **-0.0039 BSS**. The reason is visible in the importances: the trees
spent 5-8% of their gain on the dipole. With ~35 independent seasons the index barely moves inside a
held-out 7-year block, so a split on it is mostly a split on *which years this fold contains* - it fits the
fold, not the monsoon. ENSO survives the same test because we feed it as a weekly Nino 3.4 value that does
move within a season.

So the shipped model has no IOD columns. The code stays (`src/features/iod.py`, `ENABLED = False`,
`src/data/iod_index.py`) and flipping the flag reproduces the run above. The rule the project runs on:
a candidate ships when the held-out measurements support it, and not before. The scoreboard for what
did ship is in section 7d.

## 8. Data integrity checks that caught real errors

These are good material for a "rigour" or "how we validated" slide:

- **Every planetary index was checked for whether it's still being published.** The Australian Bureau of Meteorology's MJO index was **discontinued in February 2024**. NOAA's IOD index is **4 months behind**. Both were replaced before any model was trained. A system built on them would fail in live use.
- **Parsing NOAA's weekly ENSO file naively silently drops 73% of weeks, and they're mostly the La Niña weeks,** because negative numbers fuse onto the adjacent column in the fixed-width format. We caught it by checking against the file's documented start date and the known 2010 La Niña (−1.22 °C).
- **Every forecast input is dated to when it was published, not when it was observed.** A hindcast for 1 July uses only what was public on 1 July.
