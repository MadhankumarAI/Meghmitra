# Advisory delivery service: WhatsApp, in Indian languages

This is the last stage of the Meghmitra block-level monsoon early-warning system. The
advisory engine upstream decides *what* to say and *when*. This service **renders, translates, delivers,
logs**, and answers farmers' questions from the latest forecast. It sends nothing until an officer approves.

```
 advisory engine ──POST /advisories──► hold for approval ──POST /approve──► fan-out per subscriber
 (upstream)                           (officer console)                     │
                                                                             └─ WhatsApp (Meta Cloud API, pywa)
 forecast/latest.json ◄── "4-week outlook" button                                 card PNG + text + voice note + buttons
 officer console ◄──GET /dispatch/log, /dispatch/summary── statuses: queued → sent → delivered → read | failed
```

- **Templates, not generated text.** Every message is a fixed template filled with parameters.
  Translations are made ahead of time, stored per language, and marked `machine` until a native speaker
  marks them `reviewed`. No language model runs at send time.
- **Taps, not typing.** WhatsApp onboarding and the menu are buttons, lists and a location share.
- **Honest numbers.** Probabilities go out as natural frequencies ("7 in 10") next to the usual rate
  ("usually 3 in 10"), never "10 in 10". Week 4 is shown as less certain than week 1.

---

## 1. Quick start (simulator, no accounts needed)

```powershell
cd <repo>\act_1
python -m venv .venv; .venv\Scripts\pip install -r requirements.txt; .venv\Scripts\python -m playwright install chromium
copy .env.example .env          # defaults run everything in simulator mode
.venv\Scripts\python scripts\build_geo.py      # once: block polygons + PIN index from D:\Morphy (read-only)
.venv\Scripts\python scripts\seed.py           # 5 fixture subscribers
.venv\Scripts\uvicorn app.main:app --port 8000
```

- `http://127.0.0.1:8000/dev/phone` is a WhatsApp-like phone that talks to the real bot code. Type `hi`
  and onboard with taps. Share a location with the preset buttons, or type a PIN such as `581113`.
- `http://127.0.0.1:8000/docs` is the full API.
- `.venv\Scripts\python scripts\seed.py --advisories` posts the three fixture advisories. Approve Kundgol with
  `POST /advisories/{id}/approve` and watch it arrive on the phone page (use phone `+919000000001`).

For voice notes, also build the ML venv (section 6) and start `scripts\tts_worker.py`, or use
`scripts\run.ps1`, which starts the service and the worker together.

Tests: `.venv\Scripts\python -m pytest -q`. They cover onboarding by taps, STOP/START, the approval gate,
fan-out, the status lifecycle, log and summary, validation, PIN handling, every template in every language
within button limits, the Meta webhook parsed by pywa (signature check included), and the exact Graph API
requests sent (including picture headers).

---

## 2. Contracts

### 2a. `POST /advisories`: exactly the brief's JSON

| Field | Handling |
|---|---|
| `cmri_class` | `normal→green`, `watch→yellow`, `warning→orange`, `alert→red` (IMD colour code). Card, text and voice always show **icon + word + colour**. |
| `template_id` | Must be one of the templates below; unknown ids get `422`. |
| `params` | Probabilities 0–1. `event`, `p_event`, `p_clim`, `lead_week` together add the "chance vs usual" line. |
| `weeks` | Four tiles; each shows the event with the highest probability that week, its odds, and confidence. |
| `crop` | Sent to subscribers in the block who grow it. `null` or `"all"` goes to every farmer in the block. Officers of the block always get it. |
| `requires_approval` | `true`: state `pending_approval`, and **nothing is sent** until `POST /advisories/{id}/approve {"approved_by": "..."}`. `false`: dispatched at once, logged as `approved_by: "auto: requires_approval=false"`. |

Re-posting an identical advisory is a no-op. A changed advisory with the same id replaces it only while
it is still unapproved; after that it gets `409`. Expired advisories (`valid_to` in the past) get `422`
unless `ALLOW_EXPIRED_ADVISORIES=true`. The fixtures are dated June–July 2026, so the demo `.env` sets it.

**Templates** (wording in `content/locales/*.yaml`, spec in `content/templates.yaml`):

| template_id | Required params | Verdict (en) |
|---|---|---|
| `DELAY_SOWING` | `wait_until` | Wait to sow |
| `SOW_NOW` | `sow_by` | Sow now |
| `PREPARE_IRRIGATION` | none | Get irrigation ready |
| `SWITCH_CROP` | `alternative` (crop id), `sow_by` | Switch to {alternative} |
| `HEAVY_RAIN_PROTECT` | none | Heavy rain coming |
| `DRY_SPELL_CONSERVE_MOISTURE` | none | Save soil moisture |
| `ALL_CLEAR` | none | No action needed |

`params.event` is one of: `onset`, `false_onset`, `dry_spell_7d`, `dry_spell_10d`, `heavy_rain`.

**Additional endpoints the console can use:** `GET /advisories?state=`, `GET /advisories/{id}`,
`POST /advisories/{id}/reject`, and `GET /advisories/{id}/preview?lang=kn`. The preview returns exactly what
that language's subscribers will get: WhatsApp text, card PNG URL, voice-note URL
once rendered, and the review status of every string used. It is the "phone preview in Kannada" for the
review-and-send screen.

### 2b. `forecast/latest.json`

Read on every "4-week outlook" tap, and re-read whenever the file changes, so the pipeline can overwrite it
in place (`FORECAST_PATH` in `.env` if it lives elsewhere). The dummy is in `fixtures/forecast/latest.json`.
**Proposed optional addition (flagged):** a top-level `"_meta": {"valid_from": "2026-06-21", ...}` key. When
it is present, weeks are labelled with dates; without it they say "Week 1..4". Keys starting with `_` are
never treated as blocks.

### 2c. `GET /dispatch/log?block_id=&since=` and `GET /dispatch/summary`

One row per (advisory, subscriber, channel), with the fields `advisory_id, subscriber_id, channel, language,
status, ts, error`. `ts` is the time of the **last status change** (UTC ISO 8601), so polling with
`since=<latest ts seen>` returns only changed rows. `advisory_id=` is also accepted as a filter.

**Additive fields (flagged):**
- `block_id`: needed for the filter.
- `provider`: `meta-cloud` or `simulator`, so simulated traffic is never mistaken for real.
- `message_ref`: the provider message id.
- `by_provider` in the summary.

A WhatsApp row covers three messages (card, voice note, text with buttons). Its status is the least-advanced
of the three, and any failure fails the row with the reason in `error`. If the voice note isn't ready,
`error` says "sent without voice note" while the status still reflects what was delivered.
`channel=voice` is reserved for an IVR/outbound-call channel. Voice notes travel inside the WhatsApp row.

Summary: `{total, by_status, by_channel, by_language, by_block, by_provider}`, with the same filters.

### 2d. Subscribers: `GET/POST /subscribers`, `GET/PATCH /subscribers/{id}`

Fields as in the brief. `channel_pref` is always `whatsapp` (see §4), and `phone` is stored as E.164.
WhatsApp onboarding creates subscribers itself, recording consent time. STOP sets `opted_out`; START clears it.

### 2e. The farmer's record: `POST /farmers`, `GET /farmers/{id}`

Additive to the brief. A subscriber is a phone number in a block; a farmer is a person with land.
Registration happens at the panchayat office, where the land and soil details already live, so the
register comes to us in one form and the farmer confirms it later on WhatsApp.

```bash
curl -X POST localhost:8000/farmers -H "X-API-Key: $ADMIN_API_KEY" -H 'Content-Type: application/json' -d '{
  "phone": "9876543210", "language": "kn", "block_id": "7132399B30508081289508",
  "name": "Ramesh", "village": "Yettinhatti", "panchayat": "Yettinhatti gram panchayat",
  "land_ha": 1.2, "soil": "red", "irrigation": "rainfed",
  "plots": [{"survey_no": "114/2", "area_ha": 1.2}],
  "crops": [{"crop": "ragi", "sown_on": "2026-07-12"}]
}'
```

| Route | What it does |
|---|---|
| `POST /farmers` | register or update one farmer. The same phone keeps the same subscriber id |
| `GET /farmers?block_id=&village=` | the register, by block or village, with the crops standing now |
| `GET /farmers/{id}` | the whole record: land, crops with growth stage, and every message we sent |
| `PATCH /farmers/{id}` | correct the land record |
| `POST /farmers/{id}/crops` | record a sowing. `source` is panchayat, farmer or officer |
| `POST /farmers/{id}/notes` | an officer's note, kept with everything else |

Re-posting the same phone updates the record in place, so a farmer who sows again or moves village
does not become a second person in the database.

**Confirming it.** A record entered at the panchayat office is somebody else's account of a farmer.
The first time that farmer reaches us on WhatsApp, we do not ask them to onboard: we read the record
back in their own language and ask. *Yes, that is me* records consent and opens the menu. *Something
is wrong* lets them fix what is theirs to fix (village, block, crops) and sends the rest to the
panchayat and the officer, because a land record is not ours to change from a chat message. *This is
not me* stops the messages at once and tells the officer. Any farmer can send `FARM` at any time to
see what we hold.

### 2f. Who an alert reaches: `GET /advisories/{id}/audience`, `POST /audience`

The block is where the forecast is made. It is not who the warning is for. `app/audience.py` turns one
advisory into a list of farmers with a reason against each name, and a second list of the people it
deliberately left out, so the officer sees both before signing off. It decides on what the farmer or
the panchayat told us, and nothing else:

| Rule | Effect |
|---|---|
| in the block | the forecast applies here at all |
| in the village | when the advisory carries `villages`, and we know where the farmer is |
| grows the crop | the advisory's crop, or every crop when it has none |
| growth stage | from the sowing date: a dry spell at flowering scores 3, at maturity 0 and is not sent |
| irrigation | a dry spell is one step less serious on canal, borewell or tank land |
| not repeating | nobody hears about the same kind of weather twice inside `QUIET_DAYS` (5) |

A red (`alert`) advisory skips the last three: at that point everyone in the area hears it. Every send
and every skip is written to the farmer's own history, which is what the quiet window reads back next
time. `POST /audience` answers the same question for an advisory that has not been submitted yet.

### Auth (flagged)

Every route except the two webhooks needs `X-API-Key: $ADMIN_API_KEY`. Without it, anyone who finds the
tunnel URL could approve an advisory. `/dev/*` works only when `DEV_MODE=true`, and refuses any request that
came through the tunnel (it checks for the `X-Forwarded-For` / `CF-Connecting-IP` headers a tunnel adds).

---

## 3. WhatsApp: Meta Cloud API (the real path)

1. Go to <https://developers.facebook.com> and create an app of type **Business**, then add the **WhatsApp**
   product. The free **test number** is created for you.
2. Under **WhatsApp › API Setup**, add up to 5 **recipient numbers**: your phone and the demo testers. Put
   them in `.env` as `DEMO_PHONE_1…`, run `scripts\seed.py`, and copy these values into `.env`:
   - `WA_PHONE_ID`: the "Phone number ID".
   - `WA_TOKEN`: the temporary token, which lasts 24 h. A system-user token doesn't expire.
   - `WA_APP_SECRET`: from **App settings › Basic**. It verifies webhook signatures.
   - `WA_VERIFY_TOKEN`: any string you choose.
   - Also set `WHATSAPP_MODE=cloud` and `ADMIN_API_KEY` (a long random string).
3. Get a **fixed public address**, free, from ngrok:
   - Sign up at <https://dashboard.ngrok.com>.
   - Copy your **Authtoken**, and claim your one **free static domain** (e.g. `name.ngrok-free.dev`).
   - Put `NGROK_AUTH_TOKEN` and `NGROK_DOMAIN` in `.env`. `tools\ngrok.exe` is the official ngrok client.
4. Run the service (`scripts\run.ps1`), then the tunnel (`scripts\tunnel.ps1`). The address stays the same
   across restarts. The free tier shows a warning page to *browsers*; Meta's webhook calls are unaffected.
5. Under **WhatsApp › Configuration › Webhook**, set the callback URL to
   `https://<NGROK_DOMAIN>/whatsapp/webhook` and the verify token to your `WA_VERIFY_TOKEN`. Click **Verify and
   save**, then subscribe to the **messages** field. This is done **once**.
6. Make sure the Meta app is subscribed to your WhatsApp Business Account. `POST /{WABA-ID}/subscribed_apps`
   does it; without it, Meta verifies the webhook but never forwards messages.
7. From your phone, send "hi" to the test number. Onboarding starts.

**The 24-hour rule.** WhatsApp only allows free-form messages within 24 hours of the farmer's last message.
An advisory is business-initiated, so outside that window it needs a **Meta-approved utility template**.
For the demo, onboard (or tap anything) shortly before approving, and it goes through as card, text, voice
note and buttons. Outside the window the service **fails fast**, with a clear `error` in the log, instead
of sending something Meta will reject. The production answer is in section 9.

**If Meta verification blocks the demo:** an unofficial WhatsApp Web library (e.g. Baileys, whatsapp-web.js)
could drive a personal number. That breaks Meta's terms and gets numbers banned, so **none is included
here**. If it's ever needed, it belongs behind the same `WhatsAppChannel` interface, clearly labelled as a
fallback. The `/dev/phone` simulator is the safer backup for a live pitch.

## 4. SMS: removed by decision

This build is **WhatsApp only**. SMS was built, then taken out by the project owner's decision. It was tested
first with *SMS Gateway for Android* and then with *Traccar SMS Gateway*, and a real SMS was sent from a spare
phone's SIM. The removal went all the way through: SMS code, settings, SMS template strings and the `/sms/webhook`
route are all gone. **Flagged against the brief:** "Done means" step 3 (the same advisory as a real SMS) is
deliberately not met, and `channel_pref` in §2d only takes `whatsapp`.

If SMS comes back, don't use a phone gateway for real farmers. Use **mKisan** with TRAI DLT-registered
templates. The advisories are already fixed templates with a few variables, which is exactly what DLT
registration expects. See the git history (`SMS: Traccar SMS Gateway sender`) for the previous code.

## 5. Languages and review

Kannada, Hindi, Telugu, Tamil, Marathi and English are supported. **Adding a language is a data change.**
Create `content/locales/<code>.yaml` with a `meta:` block (script, font, IndicTrans2 code, TTS speaker),
typed keywords, and a crop glossary, then run the translation script. Nothing in the code lists languages.

```powershell
$env:HF_HOME="$PWD\.cache\hf"; .venv-ml\Scripts\python scripts\translate_content.py        # all
.venv-ml\Scripts\python scripts\translate_content.py kn --force                              # one, redo machine entries
```

The script translates `content/locales/en.yaml` with **AI4Bharat IndicTrans2** (en→indic, distilled 200M;
MIT licence). It runs offline, ahead of time, and has these safeguards:

- Placeholders are protected: `{crop}` becomes `#crop`, IndicTrans2's toolkit shields it, and it is restored
  afterwards.
- The model's 5-best output is searched for the first translation that keeps every placeholder and fits
  WhatsApp's length limits.
- Anything that still fails is saved as `needs_fix`. The service then uses English for that string, and
  the model output is kept for the reviewer.
- Crop names come from a hand-entered `glossary`, because single words translate unreliably ("tur" became
  "pea", "horse gram" became "horses' gram").
- `mt_hints` in `en.yaml` give the model an unambiguous input for short labels. CMRI class words go out as
  IMD's familiar "orange alert / red alert", because "warning" and "alert" translated to the same word.

Each entry is `{source, text, status}`:

| Status | Meaning |
|---|---|
| `machine` | Raw IndicTrans2 output, placeholders verified. **Must be reviewed.** |
| `checked` | Read line by line against the English and corrected where wrong. Not a native speaker's sign-off. Never overwritten by the script. |
| `glossary` | Hand-entered term. Still needs a native speaker's sign-off. |
| `reviewed` | Signed off by a native speaker. Never overwritten by the script. |
| `stale` | Was reviewed, but the English has since changed. Needs a new review. |
| `needs_fix` | Rejected by the checks; English is used until it's fixed. |

**Review workflow for native speakers (no YAML editing):**

```powershell
.venv\Scripts\python scripts
eview_sheet.py export kn        # -> review\kn_review.csv, opens in Excel / Google Sheets
#   The reviewer marks `approved` = Y, or writes a `corrected` translation, row by row.
#   Each row shows the English, where the text appears, and its length limit.
.venv\Scripts\python scripts
eview_sheet.py import kn --reviewer "Name, KVK Dharwad"
```

Imported rows become `reviewed` and carry the reviewer's name, and the translation script never overwrites
them. Rows whose `{placeholders}` don't match the English, or that break a WhatsApp length limit, are refused
and listed.

Every preview reports `review_status`, and `GET /health` counts statuses per language.
**Current state: Kannada and Hindi are `checked`, every string read against the English and corrected; Telugu, Tamil and Marathi are still raw machine output. No language carries a native speaker's sign-off yet.** A native agronomy reviewer per language should go through
`content/locales/<code>.yaml` before any real farmer receives it. Several problems were caught while
building this: "dry spell" came out as "dry spelling", "sow by" as "sow from", and "confidence" as
"self-confidence". The English source was reworded to avoid them, and the remaining outputs are listed in
§10.

Typed words such as `menu`, `hi`, `help`, `ನಮಸ್ಕಾರ`, `नमस्ते`, `வணக்கம்`, `STOP`, `रुको`, `START` and
`language` work in every language, whatever language the farmer chose.

## 6. Voice notes: AI4Bharat Indic Parler-TTS (offline)

```powershell
python -m venv .venv-ml
.venv-ml\Scripts\pip install --no-deps "torch==2.14.0+cu126" --index-url https://download.pytorch.org/whl/cu126   # NVIDIA GPU
#   (no NVIDIA GPU: torch==2.14.0 --index-url https://download.pytorch.org/whl/cpu)
.venv-ml\Scripts\pip install -r requirements-ml.txt
$env:HF_TOKEN="hf_..."; $env:HF_HOME="$PWD\.cache\hf"
.venv-ml\Scripts\python scripts	ts_worker.py            # scripts
un.ps1 starts it in a restart loop
```

- **Access and download.** The models are gated on Hugging Face. Accept the terms for
  `ai4bharat/indic-parler-tts` and `ai4bharat/indictrans2-en-indic-dist-200M`, then use a read token.
  The downloads are about 6 GB, free.
- **When notes are rendered.** When an advisory arrives, one voice note per target language is queued in
  SQLite and rendered while the advisory waits for approval. When an officer approves, that advisory's
  notes jump to the front of the queue. Dispatch waits once, for all of this
  advisory's notes together, up to `VOICE_WAIT_SECONDS` (15 min). A note that still isn't ready is left
  out, and the log says "sent without voice note".
- **Cache.** The `.ogg` files on disk are the cache, so a reset database never re-renders a note that already exists.
- **Output.** OGG/Opus mono 48 kHz at 24 kbps, which WhatsApp plays as a voice note. A 40 s advisory is
  about 120 KB, under WhatsApp's 512 KB limit. Files are content-addressed: the same text in the same voice
  is rendered once and reused for every subscriber.
- **Speed on this laptop.** Parler generates audio token by token:

  | Setup | Time for a 40 s note |
  |---|---|
  | CPU | about 16 min |
  | GTX 1650, fp32, 3 sentences per batch | about 4½ min |

  **fp16 is not used**: the model's T5 text encoder overflows to NaN in half precision, and the note comes
  out silent. The worker rejects any note that is silent or contains NaN rather than send it.
- **Recovery.** After a CUDA error the worker re-queues the job and exits, and the loop restarts it with a
  fresh GPU context. A 4 GB card also needs the model loaded in fp16 and then upcast on the GPU, because
  building it in fp32 in 7.5 GB of system RAM crashes.
- **Why a separate venv.** The ML venv is separate because `parler-tts` pins `transformers==4.46.1`. That
  library is the official way to run the model but hasn't been updated since Dec 2024. The worker boundary
  means Bhashini TTS can replace it without touching the service.
- **Numbers in speech.** Voice notes speak small numbers as words (`meta.number_words`, 0–31 per language)
  rather than leaving the model to guess at digits. `meta.speech_replace` fixes the sandhi this creates:
  Kannada "ಹತ್ತುರಲ್ಲಿ" becomes "ಹತ್ತರಲ್ಲಿ".

## 7. Location → block

- **Shared WhatsApp location:** point-in-polygon (Shapely STRtree) over `IND_ADM3.geojson`. A point in a
  boundary gap or just offshore falls back to the nearest block within about 2 km.
- **Typed PIN code:** PIN → post-office coordinates → point-in-polygon. The index is prebuilt by
  `scripts\build_geo.py`. The source is the **India Post All-India Pincode Directory** (data.gov.in, OGD
  licence) if `DATAGOVIN_API_KEY` is set (a free personal key). Otherwise it's **GeoNames postal codes**
  (CC BY 4.0), which is coarser: many PINs share one point.
- **Either way the farmer confirms by name** ("Your block is Kundgol, Dharwad district. Is this correct?").
  **No** opens a list of the PIN's other blocks and the nearest blocks, plus "Send location". A coarse PIN
  therefore never silently mis-assigns anyone.

## 8. Demo runbook (the "Done means" list)

| # | Step | How |
|---|---|---|
| 0 | Preflight | `.venv\Scripts\python scripts\doctor.py` checks geo data, Chromium, ffmpeg, voice notes, demo phone numbers, the Meta token and phone ID (live Graph API call), and Meta's webhook handshake through your tunnel. Every problem comes with its fix. |
| 1 | Onboarding by taps on a real phone | §3 steps 1–5. Send "hi", then tap ಕನ್ನಡ → Send location → Yes → pick crops → Done. **Screen-record this.** |
| 2 | Advisory arrives on WhatsApp | `seed.py --advisories`, then approve Kundgol from `/docs`. The phone gets card, text, voice note and buttons in Kannada. **Screen-record this.** |
| 3 | ~~Same advisory as a real SMS~~ | Dropped: SMS was removed by decision (§4). |
| 4 | "4-week outlook" | Tap the button under the advisory. The answer comes from `forecast/latest.json`. |
| 5 | Log and summary | `GET /dispatch/log?block_id=7132399B30508081289508` and `GET /dispatch/summary`. Rows move queued → sent → delivered → read as the phone opens the chat. |

To record on Android, use the built-in screen recorder from Quick Settings with "device audio" on, so the
Kannada voice note is captured.

## 9. Production path

- **SMS (if it is wanted again): mKisan with DLT.** Register each advisory template once per language, and
  add a sender next to the WhatsApp channel. See §4.
- **WhatsApp at scale:**
  - Move from the test number to a verified business number under the Ministry's or state department's
    Business Manager.
  - Register one **utility template** per advisory template and language (card image header plus the same
    variables). That is what lets advisories go out outside the 24-hour window. It's the one piece not
    built here.
  - Use a system-user token, and a server with its own HTTPS domain instead of a tunnel on a laptop.
- **Language: Bhashini.** Swap IndicTrans2-local for Bhashini's translation pipeline (which also serves
  IndicTrans2), and Parler-TTS for Bhashini TTS. Both sit behind the offline scripts and the TTS worker,
  so the service is untouched. The review workflow stays; it is the part that protects farmers.
- **KVK network:**
  - Register Krishi Vigyan Kendra scientists and block agriculture officers as `role: officer` subscribers.
    They receive every advisory for their block, and are pinged when a farmer taps *Talk to officer*.
  - Put the native-speaker review of templates with KVKs: one reviewer per language covers every district.
  - Add the Kisan Call Centre (1800-180-1551) to every officer card as a fallback.
- **Voice channel:** `channel=voice` is reserved for outbound IVR calls (mKisan supports voice) for farmers
  without smartphones. The same pre-rendered voice note is the audio.

## 10. Known limitations (as of this build)

- **Tested live on the Meta test number** (Meghmitra app, 19 Sept 2026), on one phone:
  - onboarding by taps in Kannada: welcome picture, language, location, block map, crops, including a typed
    "Other crop";
  - the 4-week outlook with its tile picture, and STOP and START;
  - an approved advisory delivered as card, voice note, text and buttons, with the log moving to `read`.
  - Still needed for production: a permanent token, and a server instead of a laptop plus an ngrok tunnel.
- **SMS was removed by decision** (§4), so "Done means" step 3 is not met.
- **Translation status** (§5): Kannada and Hindi are `checked` — every string was read against the English
  source and corrected in a model review (50 Kannada and 46 Hindi strings changed), with placeholders and
  WhatsApp limits verified. That is not a native speaker's sign-off, and the farmer preview says so.
  Fixed in that pass: the brand misspelt (ಮುಂಗಾರೂ / मुंगारू), colons rendered as visarga (`ಃ` / `ः`),
  Kannada "variety" as ಜಾತಿ instead of ತಳಿ, top-dressing as ಮೇಲ್ಮಟ್ಟದ instead of ಮೇಲುಗೊಬ್ಬರ, the accusative
  after a placeholder ("ಭತ್ತ ಅನ್ನು"), SWITCH_CROP's reversed "ಬದಲಿಗೆ {crop}", Hindi's stray full stop in
  `officer_alert` and "कॉल अधिकारी" for *Talk to officer*, and colour bands now use IMD's own Kannada and
  Hindi names (ಕಿತ್ತಳೆ ಎಚ್ಚರಿಕೆ / नारंगी चेतावनी) instead of transliterated English.
- **Telugu, Tamil and Marathi are still raw machine output** (`machine`) and have had no read-through.
  - Telugu, Tamil and Marathi haven't had even a developer read-through.
- Voice-note pronunciation hasn't been checked by ear: listen to `var/media/voice/*.ogg`.
- The Meta utility-template path (for advisories outside the 24-hour window) is not implemented.
- Block names appear in Latin script on cards and in messages (`blocks.parquet` has no native-script names).

## 11. Open-source components

| Component | Use | Licence |
|---|---|---|
| [pywa](https://github.com/david-lev/pywa) 4.4 | WhatsApp Cloud API client and webhook | MIT |
| [FastAPI](https://fastapi.tiangolo.com) / [Uvicorn](https://www.uvicorn.org) / [Pydantic](https://docs.pydantic.dev) | HTTP service, contract validation | MIT / BSD-3 / MIT |
| [Playwright](https://playwright.dev/python/) (Chromium) + [Jinja2](https://jinja.palletsprojects.com) | HTML → 1080×1350 card PNG | Apache-2.0 / BSD-3 |
| [Anek](https://github.com/EkType/Anek) (Kannada, Devanagari, Telugu, Tamil, Latin) | Card and simulator fonts | SIL OFL 1.1 |
| [Lucide](https://lucide.dev) icons | Card icons | ISC |
| [Shapely](https://shapely.readthedocs.io) | Point-in-polygon | BSD-3 |
| [Babel](https://babel.pocoo.org) | Dates in each language | BSD-3 |
| [AI4Bharat IndicTrans2](https://github.com/AI4Bharat/IndicTrans2) (`indictrans2-en-indic-dist-200M`) + [IndicTransToolkit](https://github.com/VarunGumma/IndicTransToolkit) | Offline template translation | MIT / MIT |
| [AI4Bharat Indic Parler-TTS](https://huggingface.co/ai4bharat/indic-parler-tts) + [parler-tts](https://github.com/huggingface/parler-tts) | Offline voice notes | Apache-2.0 / Apache-2.0 |
| [PyTorch](https://pytorch.org) / [Transformers](https://github.com/huggingface/transformers) | Model runtime | BSD-style / Apache-2.0 |
| [FFmpeg](https://ffmpeg.org) (system binary, subprocess) | WAV → OGG/Opus | LGPL/GPL build, not linked |
| [ngrok](https://ngrok.com) (free plan, static domain) | Dev HTTPS tunnel with a fixed address | Free plan, proprietary client |
| [GeoNames postal codes](https://download.geonames.org/export/zip/) | PIN → lat/lon fallback | CC BY 4.0 |
| [India Post Pincode Directory](https://www.data.gov.in/catalog/all-india-pincode-directory) | PIN → lat/lon (with key) | Government Open Data Licence – India |
| PyYAML, httpx, python-dotenv, pandas, pyarrow, pytest | Plumbing and tests | MIT / BSD-3 / BSD-3 / BSD-3 / Apache-2.0 / MIT |

## Layout

```
app/            service: main.py (wiring), bot.py (conversation), dispatch.py (lifecycle), geo.py, forecast.py
                farmers.py (the farmer's record and memory), audience.py (who an alert reaches, and why)
  channels/     whatsapp.py (Cloud + simulator, picture headers, button icons)
  render/       text.py (templates → text/speech), card.py + banner.py + templates/, voice.py (TTS queue)
  api/          routes.py (contract endpoints), dev.py (simulator)   static/phone.html
content/        templates.yaml, locales/<lang>.yaml
fixtures/       advisories/*.json, subscribers.json, forecast/latest.json
scripts/        build_geo, seed, translate_content, review_sheet, tts_worker, doctor, run.ps1, tunnel.ps1
```
