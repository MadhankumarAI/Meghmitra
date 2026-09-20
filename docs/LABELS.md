# Event definitions (ground truth)

Everything the model predicts is defined here. These are **agronomic** definitions — they describe what damages a crop — not the dynamical definitions IMD uses to declare monsoon onset over Kerala. That distinction is deliberate and is worth one line in the PPT: *IMD's onset is a circulation event for the country; ours is a sowing decision for a block.*

Thresholds follow Indian operational and agro-meteorological convention so a domain judge recognises every number.

## Rainy day
`rain >= 2.5 mm/day` — IMD's standard rainy-day threshold.

## Wet spell / candidate onset
A day `d` starts a candidate onset when, over `[d, d+4]`:
- total rainfall `>= 25 mm`, **and**
- at least 3 rainy days.

This is the widely used Indian agronomic sowing criterion (25 mm over 5 days). It is what a farmer actually responds to: enough moisture in the top soil to germinate seed.

## True onset vs **false onset** — the core label
A candidate onset is followed by a 30-day check window.

- If a **dry run of >= 10 consecutive days** begins anywhere in that window → **FALSE ONSET**. The seed germinates and then dies of moisture stress. This is the exact failure the problem statement describes.
- Otherwise → **TRUE ONSET**.

After a false onset the scan resumes past the killing dry spell and looks for the next candidate. A cell can therefore record several false onsets before its true onset, which is precisely the pattern seen in bad years.

Because false onset is baked into the label itself, the model is trained directly on *"will this rain hold?"* rather than on *"will it rain?"*. No other framing answers the farmer's real question.

## Dry spell (break)
A run of consecutive days with `rain < 2.5 mm`:
- `>= 7 days` — dry spell
- `>= 10 days` — long dry spell, treated as crop-damaging

## Heavy rain
`rain >= 64.5 mm/day` — IMD's "heavy rainfall" warning class. Using the ministry's own class boundary rather than an invented percentile.

## Season window
1 May to 31 October (DOY 121–304). The onset search starts a month before the climatological Kerala onset because interior peninsular blocks vary by many weeks.

## Forecast timing (fixed)

- A forecast is **issued on the morning of day d** and uses observations **up to d−1** only.
- **Lead week k** (k = 1…4) covers days **d + 7(k−1) … d + 7k − 1**. Week 1 is today through day 6.
- Issue days run from **1 May to 30 September** (DOY 121–273), so the week-4 window ends by late October, inside the labelled season.

## Prediction targets
For every block and every lead week (W1–W4), the model outputs a probability for:
1. **`onset`**: the true onset falls in week k. Forecast for a block until its onset is **confirmed**, meaning **40 days** have passed since the onset rain: the 30-day check window plus 10 days, because a killing dry spell that starts on day 30 is only known to have reached 10 days on day 39. Only then is the target "not applicable". *Why confirmed and not "happened"*: whether a rain event was the true onset is only knowable 30 days later, so selecting rows by "onset hasn't happened yet" would use future rainfall to choose which forecasts are scored. If onset has already happened but isn't confirmed yet, every future week correctly scores 0, and the model learns to recognise that case from recent rainfall.
2. **`dry7` / `dry10`**: a dry spell of ≥ 7 / ≥ 10 days overlaps week k. A spell already under way at issue time counts. The model is allowed to know the current dry-run length, which is legitimate persistence information.
3. **`heavy`**: at least one day in week k has ≥ 64.5 mm.

Plus one event-triggered question, the one a farmer actually asks after rain arrives:

4. **`false_onset`: "It just rained enough to sow. Will it hold?"** Sampled only on candidate-onset days. The label is whether a ≥ 10-day dry run begins within the next 30 days.

## CMRI v1.0: how a block's risk tier is set

Evaluated per block and lead week, in this order:

1. **Rainfall regime.** If June–September brings under 40% of the block's annual rain (or under 100 mm), it isn't a southwest-monsoon block and no CMRI is issued. It's labelled either *northeast-monsoon regime* (October–December dominant: most of Tamil Nadu, south coastal Andhra) or *winter-precipitation regime* (Jammu & Kashmir, Ladakh). That covers 457 of 6,824 blocks.
2. **Watch:** the dry-spell chance is ≥ 5 points above normal, or heavy rain is ≥ 1.5× normal (and ≥ 8%).
3. **Warning:** the dry-spell chance is ≥ 12 points above normal, or heavy rain is ≥ 2× normal (and ≥ 15%).
4. **Alert (act now):** a warning-level dry signal *while seedlings are establishing*, meaning sowing rain fell within the last 40 days. This is the false-onset trap. Heavy rain ≥ 3× normal and ≥ 30% is also an Alert at any crop stage.
5. **Consistency:** for weeks 1–2, the tier is never lower than the most urgent crop advisory issued for the block. The map can't look calmer than the advice.

Measured on 2023: 12 June (the stall) gave 186 Alert blocks and 3,236 Warning. 2 July (after the surge) gave 63 Alert. An earlier draft that alerted on any large dry departure gave 2,686 Alert blocks, which would have trained officers to ignore red.

## Advisory engine (src/advisory/engine.py)

Template id plus parameters, never free text. Rules follow ICAR-CRIDA contingency-plan logic:

| Situation (observed at issue time) | Condition | Advice | Tier |
|---|---|---|---|
| Any | Heavy rain ≥ 3× normal, ≥ 30%, weeks 1–2 | `HEAVY_RAIN_PROTECT` | Alert |
| Seedlings establishing | Dry spell ≥ 50% and ≥ 12 points above normal | `PREPARE_IRRIGATION` (low-tolerance crops) / `DRY_SPELL_CONSERVE_MOISTURE` | Alert |
| Not sown, ≥ 2 weeks past usual onset | Onset < 50% likely within 2 weeks | `SWITCH_CROP` (ladder at 2 / 4 / 6 weeks late) | Warning |
| Not sown, ≥ 8 weeks past usual onset | Any | None: the kharif sowing window has closed (CRIDA plans stop at ~6 weeks) | |
| Not sown, inside the sowing window | Dry spell ≥ 50% and ≥ 10 points above normal | `DELAY_SOWING` ("don't sow on the first showers") | Warning (Alert if re-sowing after a failed onset) |
| Not sown, inside the sowing window | Onset ≥ 35% within 2 weeks, no unusual dry risk | `SOW_NOW` | Warning |
| Established crop | Dry spell ≥ 50% and ≥ 12 points above normal | `DRY_SPELL_CONSERVE_MOISTURE` | Warning |

Crop lists per state and each crop's drought tolerance and contingency ladder are **indicative**. In deployment they come from state crop calendars and the CRIDA district contingency plans.

Each is reported against the **climatological probability** for that block and that calendar week, computed from the 1981–2025 record **excluding every year of the held-out 7-year block** (see DECISIONS.md, validation protocol). A probability with no baseline is not information.
