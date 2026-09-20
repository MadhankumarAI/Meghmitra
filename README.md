# Mungaru — block-level monsoon risk, and advice a farmer can act on

*Rain · Resilient · Rural*

India's monsoon forecasts are issued for meteorological subdivisions. Farm decisions — when to sow,
whether to re-sow, whether to switch crop — are made in a block. Mungaru closes that gap: a 1–4 week
probabilistic outlook for **every one of India's 6,824 blocks**, turned into crop advice that reaches
farmers on WhatsApp in their own language, after an agriculture officer approves it.

Built for Smart India Hackathon 2026, problem statement 86 (Ministry of Earth Sciences).

## What it does

| | |
|---|---|
| **Forecasts** | monsoon onset, 10+ day dry spells and heavy-rain days, weeks 1–4, per block, daily from 1 May to 30 Sep |
| **Explains** | every week-1 number breaks down into the drivers that produced it — exact tree SHAP from the model that issued it |
| **Shows the weather** | animated wind, pressure, moisture, surface heat and lows from ERA5 / NOAA GFS, as physical context |
| **Advises** | crop advice grounded in the district's own ICAR-CRIDA contingency plan, cited to a page |
| **Delivers** | a picture card, a voice note and a text on WhatsApp, in 6 languages, only after an officer approves |

## Is it any good?

Scored only on years the model never saw (1991–2025 split into five seven-year blocks, each held out whole,
with its climatology rebuilt without it):

- **+0.237** Brier Skill Score for a 10+ day dry spell at week 1, **AUC 0.91** (climatology 0.85)
- **+0.142** for monsoon onset at week 1, AUC 0.91
- Weeks 3–4 are at climatology, and the product **shows climatology there and says so**
- In the 2023 replay, **81%** of "wait to sow" advisories were followed by a real dry spell (normal rate: 30%)
- Heavy-rain advice is **over-confident** — 35% said against 26% observed — and the Evidence page states it

Full numbers, the reliability diagrams and the model card: `/science` in the app, and [docs/FINDINGS.md](docs/FINDINGS.md).

## Layout

```
src/          the forecasting pipeline: features, labels, models, exports, live run
  data/       IMD rainfall, NOAA indices, block boundaries, CRIDA contingency plans
  features/   event labels (onset, false onset, dry spells, heavy rain) and model features
  models/     LightGBM per event and lead week, with the 5-block validation protocol
  advisory/   the advice engine, grounded in district contingency plans
  export/     the JSON the console reads: forecasts, explanations, model card, contracts
  live/       today's outlook from real-time data
web/          the officer console (Next.js): map, explanations, weather view, approvals
act_1/        the WhatsApp delivery service (FastAPI): onboarding, cards, voice notes, dispatch
docs/         how it works, what was measured, and what it can't do yet
```

## Run it

See [docs/RUNBOOK.md](docs/RUNBOOK.md). The short version:

```bash
cd web && npm install && npm run dev      # the console at localhost:3100
bash scripts/daily_live.sh                # today's forecast, end to end
```

Data lives outside the repo (`D:\Morphy` on the development machine); the scripts fetch and rebuild it.

## Honesty

- Week-1 skill is partly persistence: a dry spell already under way counts, and that carries about half the
  model's weight at week 1.
- The plans behind the advice are the 2011–12 CRIDA editions; districts created since borrow the nearest
  district's plan, and the advisory says so.
- Kannada and Hindi wording has been corrected in review but has **not** had a native speaker's sign-off;
  Telugu, Tamil and Marathi are still raw machine translation, and the console marks them.

## Sources

IMD 0.25° gridded rainfall (real-time and 1981–2025) · NOAA PSL ROMI (MJO) · NOAA CPC Niño 3.4 ·
NOAA GFS and ERA5 for the weather view · geoBoundaries ADM3 (CC BY 4.0) ·
ICAR-CRIDA District Agriculture Contingency Plans · AI4Bharat IndicTrans2 and Indic Parler-TTS.
