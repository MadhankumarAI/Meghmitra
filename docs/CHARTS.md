# Performance charts: the content

Every number here is copied from the artifacts the pipeline writes, so a chart built from this page
cannot disagree with the product. Sources: `exports/model_card.json` (matrix, feature gain),
`exports/metrics.json` (reliability curves, per-block skill), `exports/advice_skill_2023.json`
(advice outcomes), `exports/experiments.json` (what was tested and dropped).

Two rules for every chart below:

1. **Label the baseline.** Skill is measured against each block's own climatology, so a bar of zero
   means "no better than the normal chance for that block on that date". Draw the zero line and name it.
2. **Say what was held out.** 1991 to 2025 is split into five blocks of seven consecutive years and each
   block is scored only by a model that never saw any year in it. Put that in the subtitle, not a footnote.

---

# Part A. Forecaster performance

## A1. Skill by lead week (the headline chart)

**Type:** grouped column chart. X axis: lead week 1 to 4. Y axis: Brier Skill Score, from -0.02 to 0.25.
One colour per event. Horizontal line at 0 labelled "climatology".

| Event | Week 1 | Week 2 | Week 3 | Week 4 |
|---|---|---|---|---|
| 10+ day dry spell | 0.237 | 0.026 | 0.011 | 0.005 |
| 7+ day dry spell | 0.200 | 0.018 | 0.008 | 0.004 |
| Monsoon onset | 0.142 | 0.024 | -0.003 | -0.012 |
| Heavy-rain day | 0.031 | 0.006 | 0.003 | 0.001 |

**Caption:** "Skill against each block's own climatology, scored only on years the model never saw.
Week 1 is strong; by week 3 the model is at climatology, and the product shows climatology there."

**Do not** cut the y axis to make weeks 2 to 4 look bigger. The honesty of this chart is the point, and
the next chart is where the late-week story is told properly.

## A2. Ranking skill: can it tell risky blocks from safe ones?

**Type:** dumbbell or paired bars, week 1 only. Two dots per event, joined: climatology and model.

| Event | Climatology AUC | Model AUC | Gain |
|---|---|---|---|
| 10+ day dry spell | 0.854 | 0.911 | +0.057 |
| 7+ day dry spell | 0.839 | 0.893 | +0.055 |
| Monsoon onset | 0.800 | 0.910 | +0.110 |
| Heavy-rain day | 0.766 | 0.799 | +0.033 |

**Caption:** "Even where the probability is only a little better than normal, the ordering is much
better: this is what lets an officer work down a list of blocks."

Climatology AUC comes from `metrics.json` (`auc_clim`); it is above 0.5 because a block's normal chance
already carries real geography and seasonality.

## A3. Reliability: does 70% mean 70%?

**Type:** line chart with the 45-degree diagonal drawn in grey. X axis: forecast probability.
Y axis: observed frequency. Both 0 to 1. Add a small bar chart of bin counts underneath, or use dot size.

10+ day dry spell (weighted reliability error 0.71%):

| Forecast | 0.046 | 0.145 | 0.248 | 0.349 | 0.449 | 0.549 | 0.649 | 0.750 | 0.853 | 0.944 |
|---|---|---|---|---|---|---|---|---|---|---|
| Observed | 0.042 | 0.152 | 0.264 | 0.359 | 0.450 | 0.542 | 0.637 | 0.738 | 0.855 | 0.953 |
| Forecasts (millions) | 41.9 | 22.1 | 14.6 | 12.1 | 10.7 | 9.4 | 8.1 | 7.5 | 9.3 | 10.4 |

7+ day dry spell (error 0.78%):

| Forecast | 0.058 | 0.148 | 0.249 | 0.349 | 0.450 | 0.550 | 0.650 | 0.750 | 0.852 | 0.951 |
|---|---|---|---|---|---|---|---|---|---|---|
| Observed | 0.054 | 0.151 | 0.260 | 0.362 | 0.461 | 0.550 | 0.640 | 0.732 | 0.837 | 0.952 |

Monsoon onset (error 0.64%, top bins empty because a 90% onset week is rare):

| Forecast | 0.025 | 0.142 | 0.240 | 0.342 | 0.445 | 0.546 | 0.644 | 0.735 | 0.829 |
|---|---|---|---|---|---|---|---|---|---|
| Observed | 0.028 | 0.157 | 0.222 | 0.292 | 0.409 | 0.529 | 0.623 | 0.724 | 0.774 |
| Forecasts (millions) | 76.3 | 11.4 | 3.8 | 1.2 | 0.5 | 0.3 | 0.2 | 0.04 | 0.01 |

Heavy rain (error 0.23%):

| Forecast | 0.037 | 0.135 | 0.240 | 0.343 | 0.446 | 0.544 | 0.641 | 0.740 | 0.822 |
|---|---|---|---|---|---|---|---|---|---|
| Observed | 0.039 | 0.134 | 0.224 | 0.326 | 0.455 | 0.568 | 0.632 | 0.765 | 0.867 |

**Caption:** "When the model says 30%, it happens about 30% of the time. Weighted error under 1% for
every event, with no calibration layer applied: this is the raw model output."

If you show only one reliability diagram, show the 10+ day dry spell: it has the most forecasts spread
across the whole range. If you show onset, keep the count bars, because the high bins are thin and an
honest chart shows that.

## A4. Where the skill is (per block, week 1)

**Type:** choropleth of India if you have time, otherwise a box plot or a histogram per event.
Values are BSS x100 per block from `metrics.json` `skill_map`.

| Event | Blocks with positive skill | 10th percentile | Median | 90th percentile |
|---|---|---|---|---|
| 10+ day dry spell | 100% | 0.16 | 0.24 | 0.28 |
| 7+ day dry spell | 100% | 0.14 | 0.19 | 0.25 |
| Monsoon onset | 94% | 0.02 | 0.15 | 0.23 |
| Heavy-rain day | 74% | -0.01 | 0.02 | 0.05 |

**Caption:** "Week-1 dry-spell skill is positive in every one of the 6,824 blocks, not an average that
hides a few good regions."

## A5. What the model leans on

**Type:** 100% stacked horizontal bar, one row per event and lead week. Share of gain by driver group,
grouped exactly as the explanations group them, so this chart and the "why this outlook" panel agree.

| Row | Recent rain | Block's normal | Monsoon progress | Rain nearby | MJO | ENSO |
|---|---|---|---|---|---|---|
| Dry spell, week 1 | 59% | 28% | 0% | 3% | 7% | 2% |
| Dry spell, week 2 | 5% | 75% | 0% | 5% | 11% | 4% |
| Onset, week 1 | 15% | 44% | 20% | 7% | 12% | 3% |
| Onset, week 2 | 8% | 54% | 8% | 7% | 19% | 4% |
| Heavy rain, week 1 | 16% | 51% | 1% | 12% | 18% | 3% |

**Caption:** "At week 1 the model is mostly reading the ground. By week 2 the local signal is spent and
the planetary state (MJO) carries more of what is left. That is the honest shape of the problem."

This chart also carries the persistence admission: the single largest week-1 feature for dry spells is
the current dry-run length.

## A6. Tried, measured, not shipped

**Type:** diverging horizontal bars, centred on zero. One panel per idea, one row per event and lead.
Negative (left) in red, positive (right) in green. Data is in `exports/experiments.json`.

Indian Ocean Dipole, change in BSS against the shipped model (mean -0.0039 over 16 cells):

| Row | 7d dry wk1 | wk2 | wk3 | wk4 | 10d dry wk1 | wk2 | wk3 | wk4 |
|---|---|---|---|---|---|---|---|---|
| Change | -0.0049 | -0.0073 | -0.0034 | -0.0049 | -0.0076 | -0.0113 | -0.0091 | -0.0074 |

| Row | Heavy wk1 | wk2 | wk3 | wk4 | Onset wk1 | wk2 | wk3 | wk4 |
|---|---|---|---|---|---|---|---|---|
| Change | +0.0004 | +0.0004 | +0.0005 | +0.0002 | -0.0077 | +0.0011 | -0.0009 | -0.0004 |

Per-block teleconnection signatures, mean -0.0044 over the same 16 cells.

**Caption:** "Two ideas that should have worked, scored the same way as everything else and left out.
The dipole moves too slowly to separate from the year it belongs to: the trees spent 5 to 8% of their
gain on it and lost skill at every dry-spell lead."

## A7. Scale, as four stat cards rather than a chart

| | |
|---|---|
| **6,824** | blocks forecast, every day of the season |
| **36.5 million** | held-out forecasts scored per event and lead week (23.5 million for onset) |
| **35 seasons** | 1991 to 2025, five held-out blocks of seven years |
| **12** | production models, one per event and lead week |

Model settings for the methods slide: LightGBM, binary objective, learning rate 0.05, 63 leaves,
minimum 400 rows per leaf, feature and bagging fraction 0.8, L2 1.0, early stopping on held-out years,
72 to 202 trees, 31 features. No calibration layer.

---

# Part B. Advisor performance

All of Part B is the 2023 replay, a year the model never saw. An advisory is counted once per block,
template and lead week. The outcome is checked against IMD rainfall using the same event definitions
the model is trained on.

## B1. Did the advice come true?

**Type:** paired horizontal bars, one pair per template: what happened where the advice was issued,
against what happened across all monsoon blocks that day. Sort by the gap.

| Advice | Advisories | Came true | All blocks that day | Lift |
|---|---|---|---|---|
| Wait to sow (DELAY_SOWING) | 28,482 | **81.1%** | 47.4% | 1.7x |
| Conserve soil moisture | 91,252 | **71.1%** | 39.7% | 1.8x |
| Prepare irrigation | 14,617 | **65.7%** | 35.8% | 1.8x |
| Sow now | 10,874 | **58.7%** | 23.1% | 2.5x |
| Protect against heavy rain | 906 | **25.5%** | 10.1% | 2.5x |

**Caption:** "Where the system said wait, a 10-or-more-day dry spell followed 81% of the time, against
47% across all monsoon blocks that day. The advice was not just correct on average, it was pointed at
the right blocks."

Outcome definitions to put in small type under the chart: wait to sow, conserve moisture and prepare
irrigation are checked against a 10+ day dry spell in the week the advice covered; protect against
heavy rain against a heavy-rain day in that week; sow now against a true onset within two weeks.

**Leave SWITCH_CROP out of this chart.** Its outcome (no onset within two weeks) was true 80.8% of the
time, but it was true for 89.3% of all blocks that day, so the bar would read as a failure when it is
really a baseline problem: late in a stalled monsoon, most blocks have no onset coming. If you want it
on a slide, put it in text with that sentence attached.

## B2. Are the advice's own numbers honest?

**Type:** scatter or slope chart. X axis: the chance the system stated when it sent the advice.
Y axis: what actually happened. Diagonal drawn. One point per template, sized by volume.

| Advice | Stated chance | Observed | Verdict |
|---|---|---|---|
| Conserve soil moisture | 72.6% | 71.1% | honest |
| Wait to sow | 79.6% | 81.1% | honest, slightly cautious |
| Prepare irrigation | 65.8% | 65.7% | honest |
| Sow now | 57.1% | 58.7% | honest |
| Protect against heavy rain | 35.3% | 25.5% | **over-confident** |

**Caption:** "Four of the five sit on the diagonal. Heavy-rain advice does not: it said 35% and 26%
happened. It is on the Evidence page in those words, and it is the first thing on the fix list."

This is the strongest slide in the deck because it shows a miss. Say the miss out loud, then say what
the product does about it: heavy-rain messages carry the lowest confidence band, and the number shown
to the farmer is the natural frequency next to the usual rate.

## B3. What the season actually produced

**Type:** stacked column by date, or a simple volume bar. 2023 replay.

| Advice | Advisories in the replay |
|---|---|
| Conserve soil moisture | 91,252 |
| Wait to sow | 28,482 |
| Switch crop | 19,525 |
| Prepare irrigation | 14,617 |
| Sow now | 10,874 |
| Protect against heavy rain | 906 |

**Caption:** "165,656 advisories over one season, dominated by moisture conservation. Heavy-rain alerts
are rare by design: the threshold is IMD's 64.5 mm day."

## B4. Where the advice comes from

**Type:** single stacked bar, 100% wide, three segments. This is the grounding chart, and it belongs
next to any claim that the advice is official rather than generated.

| Segment | Blocks | Share |
|---|---|---|
| The block's own district has a contingency plan | 3,693 | 54% |
| Uses the nearest district's plan, and says so in the citation | 2,426 | 36% |
| No plan within reach: indicative table, labelled as such | 705 | 10% |

**Caption:** "385 ICAR-CRIDA district contingency plans parsed into 34,184 rows. 90% of blocks get advice
traceable to a published plan, cited to a page, and the other 10% are labelled."

Live cross-check for the same slide: of the 1,333 advisories issued on 20 September 2026, 713 (53%)
carried a plan citation. The rest are situations the plans do not cover, where the system falls back to
its own rule and says so.

## B5. The guardrails, as a figure rather than a list

**Type:** simple flow or three icons. Not a chart, but it belongs in the advisor section.

- Retrieval, not generation: district, then crop, then situation, then the plan's own row. No model
  writes advice text.
- Never recommend what a plan says to avoid: negative clauses are parsed, and crops inside them are
  never offered.
- When the parse is ambiguous, automation stops: the officer sees the plan's exact sentence and page,
  and the advisory falls back to "wait, keep seed ready".
- Nothing is sent without an officer's name against it.

---

## Colour and style notes

- Keep IMD's semantics wherever a class appears: green normal, yellow watch, orange warning, red alert.
  Do not reuse those colours for anything that is not a risk class.
- One accent colour for "model", one neutral grey for "climatology" or "baseline", everywhere.
- Percentages to one decimal only where the difference matters (reliability). Elsewhere round.
- Every chart needs the held-out sentence in the subtitle. If a chart cannot carry it, it is the wrong
  chart for this deck.

## Regenerating these numbers

```bash
python src/export/model_card.py          # matrix and feature gain
python src/export/metrics_json.py fast   # reliability curves and the per-block skill map
python src/verify/advice_hits.py 2023    # advice outcomes
python src/export/experiments_json.py    # tried and not shipped
python src/advisory/sources.py coverage  # plan coverage by block
```
