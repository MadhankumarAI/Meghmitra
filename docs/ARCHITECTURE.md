# Technical architecture

Everything needed to draw the architecture diagram and defend it. Each component below lists what it
does, the technology it is built on, where it runs, what it writes and how often. Section 3.0 is the
whole stack on one page. Numbers are from the running system on 20 September 2026.

---

## 1. The system in one paragraph

Open meteorological data is aggregated from grids to India's 6,824 administrative blocks, turned into
per-block event probabilities by gradient-boosted trees (one model per event and lead week), classified
into a four-level risk index, explained with exact tree SHAP, matched against the district's official
crop contingency plan to produce advice, reviewed by an agriculture officer in a web console, and
delivered to farmers on WhatsApp as a card, a text and a voice note in their own language. Nothing is
computed at request time: the forecast pipeline writes static JSON, and both the console and the
delivery service read it.

## 2. Layers, for the diagram

Draw five columns left to right. Arrow labels are the real formats and protocols.

```
  SOURCES              INGEST + FEATURES        MODEL                 SERVE                 DELIVER
  ----------------     --------------------     ----------------      ----------------      ---------------
  IMD 0.25 deg    --.  block_series.py      .-> gbm.py (training) --. forecast_json.py --.  advisory_contract
  gridded rain     |   (area-weighted)      |   final.py (live)     | explain_json.py    |  .jsonl POST
                   |                        |                      |  metrics_json.py   |      |
  NOAA PSL ROMI   -+-> indices.py ----------+                      |  model_card.py     |      v
  (MJO)            |   (as-of dated)        |                      |  experiments_json  |  act_1 FastAPI
                   |                        |                      |                    |  (approval gate)
  NOAA CPC        -'   build_features.py ---'                      +-> advisory/engine -'      |
  Nino 3.4             31 features                                 |   + CRIDA plans           v
                       (issue x lead x block)                      |                      Meta WhatsApp
  geoBoundaries   ---> blocks.py, make_tiles.py -------------------+-> india.pmtiles      Cloud API
  ADM3 (6,824)                                                     |                          |
                                                                   |                          v
  ICAR-CRIDA      ---> crida_plans.py -----------------------------'                      farmer's phone
  contingency PDFs     34,184 parsed rows
                                                                   .-> Next.js console <-- static JSON
  ERA5 / NOAA GFS ---> atmos/frames.py ------------------------ ---'   (officer)
  (context only)       0.5 deg frames + diagnostics
```

Three boundaries worth labelling on the slide, because each is a design decision:

1. **Grid to block.** Everything upstream is a grid; everything downstream is a block. The conversion is
   area-weighted and happens once, in `block_series.py`.
2. **Model to advice.** The model outputs probabilities only. The decision of what to *do* comes from
   the contingency plans, not from the model and not from a language model.
3. **Advice to farmer.** An officer stands on this boundary. Nothing crosses it automatically.

## 3. Component catalogue

### 3.0 The stack, at a glance

| Layer | Technology | Why this one |
|---|---|---|
| Pipeline language | Python 3.11 (laptop 3.11.0, server 3.11.16) | the scientific stack lives here |
| Arrays and grids | numpy 2.4, xarray 2026.7, netCDF4, sparse | labelled multi-dimensional data is what a (year, issue, lead, block) cube is |
| Tables | pandas 3.0, pyarrow (Parquet) | index series and parsed plan rows |
| Geometry | geopandas 1.1, shapely 2.1, scikit-learn BallTree | block polygons, area weights, nearest-plan lookup |
| Model | LightGBM 4.7 | fast on millions of tabular rows, and its tree SHAP is exact rather than sampled |
| Scoring | scikit-learn (ROC AUC), scipy (smoothing) | standard implementations, no home-made metrics |
| Rainfall access | imdlib | IMD's own archive and real-time grid formats |
| Reanalysis and forecast | cdsapi (ERA5), cfgrib with eccodes (NOAA GFS GRIB2) | the formats the agencies actually publish |
| PDF extraction | pypdfium2 for page triage, pdfplumber for table text | pypdfium2 finds candidate pages in about 5 s per plan, pdfplumber then reads only those |
| Vector tiles | tippecanoe, PMTiles | one 25 MB file on a CDN instead of a tile server |
| Console | Next.js 16.3 (App Router, Turbopack), React 19.2, TypeScript, Tailwind v4 | static build, no server needed to serve data |
| Map | MapLibre GL 6.10, pmtiles 4.5, d3-contour | open source, WebGL, range requests straight from the tile file |
| UI state and motion | zustand 5, motion 13, lucide-react | one store, animations driven by real values |
| Delivery service | FastAPI 0.141, uvicorn, pydantic 2.13, SQLite | contract validation at the door, one file for state |
| WhatsApp | pywa 4.4 on the Meta Cloud API | typed handlers and webhook signature checking |
| Card rendering | Jinja2 with Playwright (headless Chromium) | the card is HTML and CSS, so it is edited like the rest of the UI |
| Voice notes | Indic Parler-TTS (transformers 4.46, torch 2.14), then ffmpeg to Opus | WhatsApp needs Opus in an Ogg container |
| Translation | AI4Bharat IndicTrans2 (indictranstoolkit), offline, ahead of time | no model runs at send time |
| Tests | pytest (delivery service), tsc and eslint (console), label unit tests (pipeline) | |

Deliberately absent: no inference server, no message queue, no vector database, no language model at
request time, no GPU in the forecast path. Each of those would be one more thing to operate, and none
of them is needed for what the product does.

### 3.1 Ingest

| Component | Purpose | Tech | Runs on | Writes | Cadence |
|---|---|---|---|---|---|
| `data/download_imd.py` | IMD 0.25 deg gridded daily rainfall archive | imdlib, numpy | laptop | `raw/imd/*.grd` | once, then yearly |
| `data/download_imd_rt.py` | real-time rainfall, resumable, retries through throttling | imdlib, requests | laptop | `raw/imd_rt/*.grd` | daily |
| `data/indices.py` | MJO (ROMI) and weekly Nino 3.4, stamped with the date each value was *published* | requests, pandas, pyarrow | server | `processed/indices_asof.parquet` | daily |
| `data/blocks.py` | geoBoundaries ADM3 to 6,824 block polygons and centroids | geopandas, shapely | laptop | `processed/blocks.parquet` | once |
| `data/make_tiles.py` | vector tiles for the map | geopandas, tippecanoe, PMTiles | laptop | `exports/india.pmtiles` (25 MB) | once |
| `data/crida_plans.py` | index, fetch and parse 385 district contingency plan PDFs | pypdfium2, pdfplumber, regex | laptop | `processed/crida_plans.json` (34,184 rows) | once per edition |
| `data/download_chirps.py`, `chirps_blocks.py` | 0.05 deg satellite rainfall for spatial texture | requests, xarray, sparse area weights | laptop | `processed/chirps_block_*.nc` | once |
| `data/download_era5.py` | ERA5 fields for the atmosphere view | cdsapi, xarray | laptop | `raw/era5/*.nc` | on demand |
| `data/iod_index.py` | ERSST v5 dipole boxes (experiment, off by default) | xarray, pandas | server | `processed/iod_boxes.parquet` | on demand |

The laptop is in the loop only because `imdpune.gov.in` is reachable from it and not from the server.
Everything heavy runs on the server.

### 3.2 Features and labels

| Component | Purpose | Tech | Output |
|---|---|---|---|
| `features/block_series.py` | area-weighted grid to block rainfall | sparse matrix product, xarray | `imd_block_rain.nc`, 177 MB, (year, doy, block) |
| `features/labels.py` | onset, false onset, dry spells, heavy rain per block-day | numpy run-length logic, vectorised over blocks | `imd_block_labels.nc`, 15 MB |
| `features/onset_normal.py` | each block's usual onset date, fitted inside the fold | numpy, scipy smoothing | part of the climatology set |
| `features/targets.py` | the fixed forecast grid: issue day x lead week x block | numpy, xarray, netCDF4 | `targets.nc`, 65 MB, (year=45, issue=153, lead=4, block=6824) |
| `features/build_features.py` | the 31 model features, all as-of the issue day | numpy, pandas `merge_asof`, BallTree neighbourhoods | in-memory per year, never a leaking cache |
| `features/iod.py` | the dipole pair, `ENABLED = False` | pandas | nothing, while off |

Issue days are DOY 121 to 273 (1 May to 30 September), 153 per year. Lead weeks are 1 to 4.

The 31 features, in the six groups the explanations use:

| Group | Features |
|---|---|
| The block's normal | `clim`, `usual_onset`, `days_vs_usual`, `doy`, `lat`, `lon`, `log_area` |
| Recent rain here | `r1`, `r3`, `r7`, `r14`, `r30`, `wet14`, `dry_run`, `season_rain` |
| Monsoon progress here | `cand_count`, `days_since_cand`, `onset_confirmed`, `days_since_conf_onset` |
| Rain around the block | `r7_150km`, `r7_400km`, `cand_share_150km`, `cand_share_400km`, `conf_share_400km`, `dry_run_150km` |
| MJO | `mjo_pc1`, `mjo_pc2`, `mjo_amp`, `mjo_sin`, `mjo_cos` |
| ENSO | `nino34` |

### 3.3 Models

| Component | Purpose | Tech | Detail |
|---|---|---|---|
| `models/climatology.py` | the baseline and the fold machinery | numpy, xarray | five folds: 1991-97, 1998-2004, 2005-11, 2012-18, 2019-25; prior weight 2.0 |
| `models/gbm.py` | validation training: 4 events x 5 folds x 4 leads = 80 models | LightGBM 4.7 on 20 CPU threads | about 30 min, writes `gbm_pred_fast.nc` (1.7 GB) and `gbm_scores_fast.json` |
| `models/final.py` | the 12 models that issue live forecasts, trained on all years | LightGBM, plain model text files | `processed/final_models/` with `meta.json` |
| `models/signatures.py` | per-block teleconnection signatures (v2, not shipped) | numpy, spatial smoothing | kept for the comparison chart |
| `verify/score.py`, `export/metrics_json.py` | BSS, AUC, reliability curves, per-block skill map | scikit-learn, numpy | held-out years only |
| `export/explain_json.py` | exact tree SHAP for week 1, grouped into six drivers | LightGBM `pred_contrib=True` | contributions sum to the published probability to 3e-08 |

LightGBM, binary objective, learning rate 0.05, 63 leaves, minimum 400 rows per leaf, feature and
bagging fraction 0.8, L2 1.0, early stopping on held-out years, 72 to 202 trees per model. No
calibration layer: the raw probability is published and its reliability is measured.

**The validation protocol is the part to put on the slide.** Five contiguous blocks of seven years,
each held out whole. Every quantity fitted from data, including the climatology the model takes as an
*input*, is refitted without the held-out years. Adjacent years share an El Nino, so leave-one-year-out
would leak.

### 3.4 Advisory

| Component | Purpose | Tech |
|---|---|---|
| `advisory/engine.py` | five decision rules over probabilities and observed onset status, producing a template id, a severity and parameters | plain Python, no model |
| `advisory/sources.py` | deterministic retrieval over the parsed contingency plans: district, then crop, then situation, then that plan's own row; nearest-plan fallback within the same state; negative-clause filter | pandas, regex clause parsing, centroid distance |
| `export/advisory_contract.py` | translates engine output into the delivery service's contract, one JSON object per line | stdlib json, atomic write through a `.part` file |

Retrieval, not generation. No model writes advice text. Where a plan is ambiguous or warns against a
crop rather than naming one, the automation stops and the officer sees the plan's own sentence.

### 3.5 Export layer (the only interface between pipeline and product)

| File | Shape | Size | Consumer |
|---|---|---|---|
| `forecast/{date}.json` | per-block probabilities, CMRI class, onset status | ~500 KB | console |
| `advisory/{date}.json` | advisories per block, with plan citations | ~765 KB | console |
| `explain/{date}.json` | week-1 tree SHAP per block, grouped into six drivers | ~545 KB | console |
| `atmos/{era5,gfs}_*.json.gz` | 0.5 deg wind, pressure, moisture, temperature plus diagnostics | ~68 KB each | console |
| `contract/{date}.jsonl` | one advisory per line, in the delivery contract | 1,333 lines today | delivery service |
| `forecast/latest.json` | today's four-week outlook, flat | small | delivery service |
| `blocks_index.json`, `crops.json`, `india.pmtiles` | static reference | 1.3 MB, 1.3 KB, 25 MB | console |
| `metrics.json`, `model_card.json`, `experiments.json`, `advice_skill_2023.json` | evidence | 540 KB, 10 KB, 4 KB, 1 KB | console |

Total export tree: 365 MB, 159 forecast days and 145 atmosphere frames for the replay season.

### 3.6 Console (Next.js)

Next.js 16.3 App Router with Turbopack, React 19.2, TypeScript, Tailwind v4, MapLibre GL 6.10 reading
PMTiles by range request, zustand for state, motion for animation, lucide-react for icons and d3-contour
for the isobars. Gzipped daily files are unpacked in the browser with the native `DecompressionStream`.
Static data only: no server rendering of forecasts, no database, no inference at request time. Hosted on
Vercel as a static build; the only server-side code in the console is the delivery proxy.

| Route | Purpose |
|---|---|
| `/` | risk map, time machine, block panel, why-this-outlook, atmosphere, review and send |
| `/science` | evidence: how it works, is it honest, where it works, the model card |
| `/f/[block]` | the farmer view of one block |
| `/api/delivery/[...path]` | allowlisted server-side proxy to the delivery service |
| `/api/farmer/*` | public read path for the farmer view |

The proxy exists so the delivery service's admin key never reaches a browser. It forwards only health,
advisory list, preview, approve, reject, dispatch log, dispatch summary and media, and it reduces
subscriber lists to counts before they leave the server.

### 3.7 Delivery service (`act_1`, FastAPI)

| Module | Purpose | Tech |
|---|---|---|
| `app/main.py`, `app/api/routes.py` | the admin API (below); the contract is validated at the door | FastAPI, pydantic 2, uvicorn |
| `app/bot.py` | WhatsApp conversation: onboarding by taps, menu, four-week outlook, STOP and START | pywa handlers over a session state machine in SQLite |
| `app/channels/whatsapp.py` | Meta Cloud API, with a simulator mode that sends nothing | pywa 4.4, httpx |
| `app/geo.py` | block lookup from a shared location or a PIN code | shapely point-in-polygon over a prebuilt index |
| `app/render/card.py`, `banner.py` | the picture card | Jinja2 template rendered by headless Chromium (Playwright) |
| `app/render/text.py` | message text and button labels, length-checked per language | Jinja2, babel for dates and numbers |
| `app/render/voice.py`, `scripts/tts_worker.py` | voice notes, queued and cached by content hash | Indic Parler-TTS on torch, ffmpeg to Opus |
| `app/dispatch.py` | fan-out per subscriber, status lifecycle, retries | SQLite transactions, FastAPI background tasks |
| `app/locales.py`, `scripts/translate_content.py` | six language files with per-string review status | PyYAML, IndicTrans2 offline |
| `app/db.py` | schema and connections | sqlite3 from the standard library, no ORM |

Endpoints:

```
POST   /advisories                      accept an advisory, state = pending_approval
GET    /advisories                      list, filterable by state
GET    /advisories/{id}                 one advisory
POST   /advisories/{id}/approve         officer name required, triggers fan-out
POST   /advisories/{id}/reject          with a reason
GET    /advisories/{id}/preview         rendered text per language, review status included
GET    /advisories/{id}/card/{lang}.png the picture card
GET    /dispatch/log                    per-message rows
GET    /dispatch/summary                counts by status
GET    /subscribers, POST, PATCH        subscriber management
GET    /health                          token, geo data, ffmpeg, webhook, locale status
POST   /webhook                         Meta inbound and status callbacks (signature checked)
```

SQLite, six tables:

| Table | Key columns |
|---|---|
| `advisories` | `advisory_id`, `block_id`, `payload`, `state`, `approved_by`, `approved_ts` |
| `subscribers` | `phone` (unique), `language`, `block_id`, `crops`, `role`, `consent_ts`, `opted_out` |
| `dispatch` | `advisory_id` + `subscriber_id` + `channel` unique, `status`, `provider`, `message_ref` |
| `dispatch_parts` | one row per part sent (card, text, voice) with the provider's id |
| `sessions` | the conversation state machine per phone |
| `tts_jobs` | voice cache keyed by sha256 of engine, language, voice and text |

Advisory states: `pending_approval` to `approved` to `dispatched`, or `rejected`. Message statuses:
`queued` to `sent` to `delivered` to `read`, or `failed` with the provider's error.

## 4. Deployment topology

```
  Laptop (Windows)            GPU server 14.143.127.114        Vercel              Meta Cloud API
  -----------------           --------------------------        ------              --------------
  IMD real-time fetch  --scp-> training, live run, exports  --scp-> static console --> (browser)
  D:\Morphy (source of                20 CPU threads          public, no login
  truth for data)                     no GPU needed
        |                                                                      
        '--> act_1 FastAPI (localhost:8000) <--proxy-- console                 
                    |                                                          
                    '--ngrok tunnel--> Meta webhook --> WhatsApp --> farmer's phone
```

Why each boundary exists:

- **Laptop to server:** only the laptop can reach IMD's real-time endpoint; only the server has the
  cores for training. The link is `scp` of a few `.grd` files.
- **Server to Vercel:** the console needs no compute, only files. Staging copies and gzips the subset
  the public site may serve, leaving out the advisory contract and the live forecast.
- **Console to delivery service:** a server-side proxy, never a direct browser call, so the admin key
  stays server side. `DELIVERY_URL` is deliberately unset on the public deployment, because the console
  has no login and anyone who could open it could otherwise approve a dispatch.
- **Delivery service to Meta:** Meta must reach a public HTTPS webhook, which is what the tunnel is for.
  In production this becomes a hosted endpoint.

## 5. The daily run

`scripts/daily_live.sh`, four stages, a few minutes end to end:

1. Laptop fetches IMD real-time rainfall up to yesterday.
2. New `.grd` files are copied to the server.
3. Server runs `live/run_live.py` (indices refresh, features, 12 models, advisories, explanations),
   then `atmos/frames.py gfs`, then `model_card.py` and `experiments_json.py`.
4. Results are pulled to `D:\Morphy\exports`, the advisory contract is written, and today's outlook is
   handed to the delivery service as `act_1/forecast/latest.json`.

Optionally `--deploy` stages the public subset and publishes.

## 6. Failure modes and what the system does

| Condition | Behaviour |
|---|---|
| Outside 1 May to 30 September | no outlook is issued; `live_status.json` says so and the console shows the message |
| More than 6 of the last 60 days of rainfall missing | the run refuses to publish rather than draw a misleading map, and states the reason |
| An index feed stalls | the last published value is used, with its publication date shown; feeds that lag badly are replaced (this is why the MJO uses ROMI and the dipole is computed in house) |
| A district has no contingency plan | the nearest plan in the same state is used and the citation says so; beyond about two degrees, no plan is borrowed and the advisory falls back to a labelled indicative table |
| A plan sentence cannot be resolved to one crop | automation stops; the officer sees the plan's exact sentence and page |
| The delivery service is unreachable | the console says "not connected"; nothing queues silently |
| A WhatsApp send fails | the dispatch row records the provider error and the status stays `failed`, visible in the Delivery Centre |
| Where model skill is zero or negative | climatology is shown, labelled as climatology |

## 7. Non-functional characteristics

| Property | Value |
|---|---|
| Forecast volume | 6,824 blocks x 4 lead weeks x 3 published events, daily for 153 days |
| Validation volume | 36.5 million held-out forecasts scored per event and lead (23.5 million for onset) |
| Training cost | one pass over 1991-2025, about 30 minutes, 20 CPU threads, no GPU |
| Daily cost | one forecast run of a few minutes plus a static file refresh; no inference server |
| Console payload | about 500 KB per forecast day, gzipped, plus a 25 MB tile file cached once |
| Explanation cost | tree SHAP computed once per day for week 1 and published with the forecast, not at request time |
| Languages | six: English, Kannada, Hindi, Telugu, Tamil, Marathi |

## 8. Security and privacy

- Farmer phone numbers live only in the delivery service's SQLite database, which is excluded from the
  repository. The console never receives a subscriber list, only counts.
- The delivery service's admin key is held server side by the console proxy and never sent to a browser.
- Meta webhook payloads are signature checked by pywa.
- Consent is recorded per subscriber with a timestamp, and STOP is honoured immediately and stored as
  `opted_out`.
- Nothing is dispatched without an officer's name recorded against the approval.

## 9. What would change at national production scale

| Now | Then | Why it is not a rewrite |
|---|---|---|
| Static JSON on a CDN | same, plus an object store | the product never computes at request time |
| SQLite | Postgres | the schema is six tables and already normalised |
| ngrok tunnel | a hosted HTTPS endpoint | only the webhook URL changes |
| One officer console without login | department SSO and per-district scoping | the approval gate and the audit trail already exist |
| Laptop in the loop for IMD real-time | a fetcher inside the department network | the pipeline stage is a single script |
| Six languages | more, on the same template machinery | strings carry a per-language review status already |

## 10. Diagram checklist

If the architecture slide shows only six things, show these:

1. Open data sources, named, with their update cadence.
2. Grid to block, with the number 6,824 on the arrow.
3. One model per event and lead week, with the held-out validation protocol written under it.
4. The export layer as the single interface, labelled "static JSON, no inference at request time".
5. The officer approval gate, drawn as a gate, with "nothing passes automatically" on it.
6. WhatsApp as three artefacts: card, text, voice note, in the farmer's language.
