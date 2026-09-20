# Live mode: how it runs

The console has two modes:

- **2023 replay** is the validated hindcast, where every forecast comes from a model that never saw 2019–2025.
- **Live** is today, built from real-time data.

## What "Live" shows

| Layer | Source | Refreshed |
|---|---|---|
| Atmosphere animation (wind, pressure, moisture, lows) | NOAA GFS 0.25°, latest run, now → +10 days in 12 h steps | every GFS run (6-hourly); we take one run a day |
| Block outlook (CMRI, onset, dry spell, heavy rain, advisories) | Our v1 model, trained 1991–2025 (`src/models/final.py`), fed IMD real-time gridded rainfall plus NOAA ROMI (MJO) and CPC weekly Niño 3.4 | daily, 1 May–30 Sep |

## Daily run

```bash
bash scripts/daily_live.sh            # fetch, compute, pull to D:
bash scripts/daily_live.sh --deploy   # ...and publish to Vercel
```

1. **Laptop:** fetches IMD real-time rainfall up to yesterday (`src/data/download_imd_rt.py`). It's resumable and retries through IMD's throttling. `imdpune.gov.in` is reachable from the laptop but not from the server, which is why the laptop is in the loop.
2. **Server:** `src/live/run_live.py` refreshes the indices, builds features, predicts with the final models, and writes `live.json` plus advisories. Then `src/atmos/frames.py gfs` builds the atmosphere frames.
3. The results are pulled to `D:\Morphy\exports`, and optionally deployed.

## Safety rules (why Live can be blank)

- **Outside 1 May–30 Sep** no outlook is issued. `live_status.json` says so, and the console shows that message.
- **Patchy rainfall record:** if more than 6 of the last 60 days of IMD rainfall are missing, the run **refuses to publish** rather than show a misleading map. The console shows the reason.
- Every live file records its inputs: rainfall-through date, missing days, index values, and model and tree counts.

## Explaining the weather ("Understand")

The atmosphere layer explains the *weather situation*. It shows:

- the low-level jet strength over the Arabian Sea,
- the monsoon trough axis,
- lows, depressions and cyclones,
- column moisture.

The panel lists all four fields with the diagnostic each is drawn from (jet in m/s, column water in mm, hottest plains point in °C, the deepest low's central pressure), and a marker beside each one that moves at that value's own rate. Any field can be switched off so the others can be read alone, and the wind streaks can be coloured by column moisture instead of speed, which turns the animation into moisture transport rather than air movement.

Diagnostics are computed per frame (`src/atmos/frames.py`), and high terrain (> 600 m) is masked so extrapolated sea-level pressure over Tibet and the Himalaya can't produce fake lows.

It is **context, not the model's reasoning**: the v1 model does not use these fields, and the panel says so on screen. For 2023 the frames are ERA5 reanalysis (06 UTC daily).

Validated on 2023:

- **12 June:** Cyclone Biparjoy is found at 19.5°N 67.5°E, 964 hPa.
- **10 August:** a break (trough at 28.3°N, weak jet), during the driest August on record.
- **Late July:** an active phase (trough at 21–22°N, jet at 18 m/s).

## Explaining the forecast ("Why this outlook")

Each block panel shows why the model gave its week-1 number: from the block's usual chance for the date, each driver's exact contribution (tree SHAP from the same model) moves the marker to the forecast. The drivers are recent rain, rain around the block, onset progress, MJO and ENSO. The live run writes `explain/live.json` alongside the outlook; the replay uses the fold models that never saw 2019–2025. This is the model's reasoning, unlike "Understand", which is the weather context.

In "Understand", the dashed line of lowest pressure is labelled **Heat low** while the monsoon is still advancing and **Monsoon trough** once it has arrived, and surface heat (≥ 35 °C over land, ERA5/GFS 2 m temperature) shows as an amber–red glow.
