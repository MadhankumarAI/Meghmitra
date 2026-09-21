# Commands

Everything runs from `Last hope/`. Git Bash for the `bash` lines, PowerShell for `.ps1`.
The D: drive must be connected (it holds the data), and `.venv` is the project's Python.

## 1. Show the thing (console)

```bash
cd web && npm run dev            # http://localhost:3100
```

`public/data` is a junction to `D:\Morphy\exports`, so it serves the real files.

## 2. Today's forecast, for real (daily)

```bash
bash scripts/daily_live.sh              # fetch IMD rain -> model -> D: -> act_1/forecast/latest.json
bash scripts/daily_live.sh --deploy     # ...and publish to Vercel
```

It does: IMD real-time rainfall to yesterday (laptop) → upload → live outlook + GFS weather + model
card (server) → pull results to D: → hand today's outlook to the WhatsApp service.
Out of season, or with a patchy rainfall record, it refuses to publish and says why.

## 3. The WhatsApp delivery service (`act_1/`)

```powershell
cd act_1
.\scripts\run.ps1                       # the bot + the voice-note worker
.\scripts\tunnel.ps1                    # public address for Meta's webhook
.venv\Scripts\python scripts\doctor.py  # preflight: token, geo data, ffmpeg, webhook
```

Test **without** sending to real phones — a simulator copy on its own database:

```bash
cd act_1
WHATSAPP_MODE=simulator DB_PATH=/tmp/sim.sqlite3 VOICE_WAIT_SECONDS=20 \
  .venv/Scripts/uvicorn app.main:app --port 8001
# then point the console at it:
cd ../web && DELIVERY_URL=http://127.0.0.1:8001 npx next dev -p 3100
```

The console reads `DELIVERY_URL` and `DELIVERY_API_KEY` from `web/.env.local` (already set to the
real service on port 8000). Officer flow: click a block → **Review & send**; service health and what
has actually been sent: top bar → **Delivery**.

## 4. Where the advice comes from (CRIDA plans)

```bash
.venv/Scripts/python src/data/crida_plans.py index        # 391 district plans
.venv/Scripts/python src/data/crida_plans.py fetch        # download PDFs (resumable)
.venv/Scripts/python src/data/crida_plans.py parse        # -> PROCESSED/crida_plans.json
.venv/Scripts/python src/advisory/sources.py coverage     # blocks covered by a plan
.venv/Scripts/python src/advisory/sources.py show Dharwad cotton
```

## 4b. Villages and panchayats (the name a farmer uses)

```bash
.venv/Scripts/python src/data/villages.py fetch              # geoBoundaries ADM5, 467 MB, once
.venv/Scripts/python src/data/villages.py build --state Karnataka
.venv/Scripts/python src/data/villages.py show Kengeri
.venv/Scripts/python src/export/villages_json.py             # search shards + map cells
.venv/Scripts/python src/export/villages_geom.py             # village outlines, one file per block
python src/features/village_clim.py                          # on the server: CHIRPS 5 km normals
.venv/Scripts/python src/export/villages_clim_json.py        # per-village adjustment, per block

The logo lives in exactly one place, `act_1/dp.png`. After replacing it:

```bash
.venv/Scripts/python scripts/brand.py --check     # what would change
.venv/Scripts/python scripts/brand.py             # badge, mark, favicons, WhatsApp profile
```

It cuts the round badge and the cloud-leaf-rain mark out of that file and writes every size the
product uses, in `web/public/brand`, `web/src/app` and `act_1/assets/brand`. Cards and banners the
delivery service has already drawn carry the old logo in their filename hash, so they redraw by
themselves; `act_1/var/media` can be emptied to reclaim the space.

`villages_geom.py` simplifies each state as one coverage (`shapely.coverage_simplify`), so villages
keep sharing their borders instead of drifting apart into slivers. Defaults are 0.00025 degrees
(about 28 m) and five decimals; `--tolerance` and `--precision` override them, and a coarser build
is a quarter of the size: the national set is about 900 MB at the default and 190 MB at 0.0008 / 4.

`village_clim.py` needs CHIRPS, which lives on the server (`ssh user02@14.143.127.114`, then
`source ~/morphy/env.sh && cd ~/morphy`). It now writes both events: the dry spell and the
heavy-rain day. Copy `processed/village_clim.npz` back before running `villages_clim_json.py`; an
npz without the heavy-rain arrays still exports, dry spell only, and the console then shows no
village adjustment on the heavy-rain layer.
```

Building every state takes about 20 minutes and yields 649,309 villages. `villages_json.py` writes two
things: letter shards for search, and half-degree map cells (1,254 of them, 25 MB in total) that the
map layer fetches only for what is on screen.

## 5. Retrain (server, GPU box)

```bash
python src/models/gbm.py --fast          # 80 models, 5 held-out blocks, ~30 min -> gbm_pred_fast.nc
                                         #   + gbm_scores_fast.json (the performance matrix)
python src/models/gbm.py --only-fold 4 --save-models PROCESSED/fold_models/f4_fast
                                         #   keep one fold's models so explanations can be recomputed
python src/models/final.py               # the 12 models that issue live forecasts (all years)
```

Training is seeded, so a rerun of the same code reproduces the same predictions exactly; that is how a
code change is verified not to move any published number. Feature switches live next to the feature:
`src/features/iod.py` has `ENABLED = False`, and flipping it reproduces the IOD experiment in
`docs/FINDINGS.md` section 7e. Keep a copy of the scores before any experiment
(`cp gbm_scores_fast.json gbm_scores_fast.<name>.json`); `src/export/experiments_json.py` reads those
copies to build the Evidence page's "tried and not shipped" charts.

## 6. Rebuild outputs

```bash
# on the server (ssh user02@14.143.127.114, then: source ~/morphy/env.sh && cd ~/morphy)
python src/export/forecast_json.py 2023 --source gbm_fast   # the replay season + advisories
python src/export/explain_json.py 2023                      # per-block "why", week 1
python src/export/model_card.py                             # model card + performance matrix
python src/export/experiments_json.py                       # ideas tested and not shipped (Evidence page)
python src/verify/advice_hits.py 2023                       # did the advice come true?
python src/verify/confusion.py                              # precision/recall at the real thresholds
python src/verify/curves.py                                 # ROC, PR and reliability points
python src/live/run_live.py                                 # today's outlook

# on the laptop
.venv/Scripts/python src/export/advisory_contract.py 2026-09-19 --latest act_1/forecast/latest.json
```

## 7. Deploy

```bash
cd web
npm run data:stage      # copy + gzip D: exports into public/data (Vercel's 100 MB limit)
npx vercel --prod
npm run data:link       # restore the junction for local work
```

Leave `DELIVERY_URL` unset on Vercel: the public console has no login, so anyone could otherwise
approve messages to farmers.

## 8. Tests

```bash
.venv/Scripts/python tests/test_labels.py     # label definitions
cd act_1 && .venv\Scripts\python -m pytest -q  # 56 delivery-service tests
cd web && npx tsc --noEmit && npx eslint src && npx next build
```

## 9. Screenshots (for the deck and the video)

```bash
cd web
node scripts/shot_tour.mjs OUT          # every screen
node scripts/shot_understand.mjs OUT    # the weather animation
node scripts/shot_delivery.mjs OUT      # Review -> Approve -> Track
node scripts/shot_dispatch.mjs OUT      # Delivery Centre
node scripts/shot_labels.mjs OUT        # map labels + model card

# the four performance figures (laptop, matplotlib)
.venv/Scripts/python scripts/plots.py
node scripts/shot_tried.mjs OUT         # Evidence: tried, measured, not shipped
node scripts/shot_toggle.mjs OUT        # atmosphere layers off, streaks coloured by moisture
```
