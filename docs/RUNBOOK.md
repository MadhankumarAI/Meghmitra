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

## 5. Rebuild outputs

```bash
# on the server (ssh user02@14.143.127.114, then: source ~/morphy/env.sh && cd ~/morphy)
python src/export/forecast_json.py 2023 --source gbm_fast   # the replay season + advisories
python src/export/explain_json.py 2023                      # per-block "why", week 1
python src/export/model_card.py                             # model card + performance matrix
python src/verify/advice_hits.py 2023                       # did the advice come true?
python src/live/run_live.py                                 # today's outlook

# on the laptop
.venv/Scripts/python src/export/advisory_contract.py 2026-09-19 --latest act_1/forecast/latest.json
```

## 6. Deploy

```bash
cd web
npm run data:stage      # copy + gzip D: exports into public/data (Vercel's 100 MB limit)
npx vercel --prod
npm run data:link       # restore the junction for local work
```

Leave `DELIVERY_URL` unset on Vercel: the public console has no login, so anyone could otherwise
approve messages to farmers.

## 7. Tests

```bash
.venv/Scripts/python tests/test_labels.py     # label definitions
cd act_1 && .venv\Scripts\python -m pytest -q  # 56 delivery-service tests
cd web && npx tsc --noEmit && npx eslint src && npx next build
```

## 8. Screenshots (for the deck and the video)

```bash
cd web
node scripts/shot_tour.mjs OUT          # every screen
node scripts/shot_understand.mjs OUT    # the weather animation
node scripts/shot_delivery.mjs OUT      # Review -> Approve -> Track
node scripts/shot_dispatch.mjs OUT      # Delivery Centre
node scripts/shot_labels.mjs OUT        # map labels + model card
```
