# Brief: advisory delivery service (WhatsApp + SMS)

You are building the **last stage** of a block-level monsoon early-warning system. Another session is building the forecasting model and the web console. Your job is to take finished advisories and get them to farmers and agricultural extension officers on WhatsApp and SMS, in Indian languages. Use dummy advisories for now; the real ones will arrive later in exactly the format below, so **the contract in §2 matters more than anything else in this brief.**

## 1. Ground rules

- **Work only in your own project folder.** The forecasting system lives in `C:\Users\jaip7\Downloads\madhan\Last hope` and its data in `D:\Morphy`. Read from those, never write to them.
- **Heavy reuse of existing open-source software is expected and preferred.** Don't hand-write a WhatsApp client, an SMS stack, a TTS engine or a translation model. Find a maintained library or self-hostable tool, wrap it, and write only the glue. Check each dependency is actively maintained and its licence allows this use, and record the choice in `README.md`.
- **Python + FastAPI**, because the rest of the system is Python. SQLite is fine for subscribers and the send log.
- **Secrets only in `.env`**, gitignored. Commit a `.env.example`.
- **You don't compute forecasts or decide when to send.** The advisory engine upstream decides what to say and when. You render, translate, deliver, log, and answer farmers' inbound questions from the latest forecast file.

## 2. Contracts (don't change these without flagging it)

### 2a. Inbound: an advisory to deliver (`POST /advisories`, JSON)

```json
{
  "advisory_id": "7132399B30508081289508_2026-06-21_ragi_delay",
  "issued_at": "2026-06-21T06:00:00+05:30",
  "valid_from": "2026-06-21",
  "valid_to": "2026-07-18",
  "product": "CMRI v1.0",
  "block": { "block_id": "7132399B30508081289508", "name": "Kundgol", "district": "Dharwad", "state": "Karnataka" },
  "cmri_class": "warning",
  "crop": "ragi",
  "template_id": "DELAY_SOWING",
  "params": { "wait_until": "2026-07-05", "p_event": 0.68, "p_clim": 0.31, "event": "dry_spell_10d", "lead_week": 2 },
  "weeks": [
    { "week": 1, "onset": 0.42, "dry_spell": 0.21, "heavy_rain": 0.08, "confidence": "high" },
    { "week": 2, "onset": 0.18, "dry_spell": 0.68, "heavy_rain": 0.05, "confidence": "high" },
    { "week": 3, "onset": 0.30, "dry_spell": 0.44, "heavy_rain": 0.07, "confidence": "medium" },
    { "week": 4, "onset": 0.35, "dry_spell": 0.33, "heavy_rain": 0.09, "confidence": "low" }
  ],
  "officer": { "name": "Assistant Director of Agriculture, Kundgol", "phone": "+91XXXXXXXXXX" },
  "requires_approval": true
}
```

- `cmri_class` is one of `normal | watch | warning | alert`. Map these to IMD's green / yellow / orange / red.
- `template_id` is one of: `DELAY_SOWING`, `SOW_NOW`, `PREPARE_IRRIGATION`, `SWITCH_CROP`, `HEAVY_RAIN_PROTECT`, `DRY_SPELL_CONSERVE_MOISTURE`, `ALL_CLEAR`. Add more if needed, and list them in the README.
- Probabilities are 0–1. Show them to farmers as natural frequencies ("7 in 10 chance"), not percentages. Always pair them with the normal rate ("usually 3 in 10").
- If `requires_approval` is true, hold the advisory until an officer approves it (`POST /advisories/{id}/approve`). Nothing reaches a farmer without human sign-off in that case.

### 2b. Forecast lookup, for inbound "show me the 4-week outlook" requests

Read `forecast/latest.json`: `{ block_id: { "onset"|"dry_spell"|"heavy_rain": [ {week, p, p_clim, confidence} ×4 ] } }`. Put a dummy one in `fixtures/`. The real one will replace it at the same path.

### 2c. Outbound: the send log, consumed by the officer console's Dispatch Centre

`GET /dispatch/log?block_id=&since=` returns rows of `advisory_id, subscriber_id, channel (whatsapp|sms|voice), language, status (queued|sent|delivered|read|failed), ts, error`. Also expose `GET /dispatch/summary` with counts by status, channel, language and block.

### 2d. Subscribers

`subscriber_id, phone, channel_pref, language, block_id, crops[], role (farmer|officer), consent_ts, opted_out`.

### 2e. Location to block

- Blocks: `D:\Morphy\processed\blocks.parquet` (block_id, name, district, state, lat, lon).
- Polygons: `D:\Morphy\raw\boundaries\IND_ADM3.geojson`.
- A WhatsApp shared location maps to a block by point-in-polygon.
- A typed PIN code maps via an open India Post PIN-to-lat/lon dataset, then point-in-polygon.

## 3. WhatsApp: taps, not typing

The model is the Namma Metro (BMRCL) WhatsApp bot: every step is a tap, nothing needs to be typed, and each message does one thing.

- **Onboarding (once):** language list → share location (or type PIN) → confirm the detected block by name → crop list (multi-select across messages) → done, subscribed.
- **Main menu, always one tap away:** `4-week outlook` · `Change crop` · `Talk to officer`.
- **An advisory message** = a rendered **advisory card image**, a short text in the subscriber's language, a **voice note** of the same text, and buttons.
- Stay inside WhatsApp's limits: at most 3 reply buttons per message and 10 rows per list.
- Any typed word like "menu", "hi" or "help" in any supported language returns the main menu. "STOP" opts out and is confirmed.
- Use the **official Meta WhatsApp Cloud API**. Its free test number supports interactive buttons, lists and location requests. Pick a maintained open-source Python wrapper for it rather than calling the raw REST API.
- The webhook needs a public HTTPS URL during development. Use a free tunnel such as `cloudflared` quick tunnels.
- Unofficial WhatsApp-Web libraries break Meta's terms and get numbers banned. Use one only as a clearly labelled fallback if Meta verification blocks the demo, never as the main path. This pitch is to a ministry.

## 4. SMS

- A commercial bulk-SMS provider in India needs TRAI DLT template registration, which takes too long for the demo. Twilio and Brevo SMS hit the same wall for Indian numbers.
- **For the demo, use an open-source Android SMS gateway app** on a spare phone with a SIM. It exposes a REST API and sends real SMS from that SIM at no cost.
- Hide the provider behind a `SmsSender` interface so a DLT-registered provider (mKisan in production) can replace it with one class.
- SMS text is the same template rendered short: 160 GSM characters in English, or 70 per segment in Unicode Indic scripts. Keep advisories within 2 segments.
- Our advisories are fixed templates with parameters. That's what makes them DLT-compatible, so say so in the README.

## 5. Languages, text and audio

- Supported languages: **Kannada, Hindi, Telugu, Tamil, Marathi, English**. Build it so adding a language is a data change, not a code change.
- **Templates are written and translated ahead of time, then reviewed. Never generate text with a language model at send time.** A mistranslated agricultural instruction costs a farmer a season.
- Pre-translate the templates with an open Indic translation model (AI4Bharat IndicTrans2) or Bhashini, store them as files per language, and mark each as `machine` or `reviewed`.
- Voice notes come from an open Indic TTS model (the AI4Bharat family) or Bhashini TTS. Pre-render them per rendered message and cache them. WhatsApp wants OGG/Opus.
- Use Anek-family fonts for the Indic scripts on the card image.

## 6. Advisory card image

A 1080×1350 PNG rendered from an HTML template (headless browser or an HTML-to-image library):

- The CMRI colour band and class word
- One verdict line in large type ("Wait to sow")
- Four week tiles with icons
- 2–3 numbered actions
- The block name and validity dates
- A footer crediting "Based on IMD data · CMRI v1.0"

Readable on a cheap phone in sunlight. Never rely on colour alone: every state gets an icon and a word too.

## 7. Dummy data

In `fixtures/`: three realistic advisories using **real block names** from `blocks.parquet` (for example Kundgol and Navalgund in Dharwad, Karnataka). They should cover `DELAY_SOWING` (warning), `HEAVY_RAIN_PROTECT` (alert) and `ALL_CLEAR` (normal). Add a matching `forecast/latest.json` and 5 dummy subscribers. The subscribers must include the WhatsApp test recipients you register with Meta, and at least one Kannada speaker and one Hindi speaker.

## 7b. Real data (available now)

Real model output exists in exactly the §2a and §2b formats. The drive paths are `D:\Morphy\exports\…`, with a server copy at `~/morphy/data/exports/…`.

- `contract/2023-06-22.jsonl`: one §2a advisory per line. That's 5,574 advisories for 22 June 2023, a real day in the monsoon's stall-and-surge, and every one has `requires_approval: true`. Good test blocks are Navalgund (Dharwad), which gets `SWITCH_CROP` for ragi, maize and pigeonpea.
- `forecast/latest.json`: the §2b outlook for all 6,824 blocks, flat `{block_id: {...}}` plus `_meta` (`valid_from`, `source`: `live` or `hindcast`). Weeks where an event doesn't apply are left out.
- Regenerate for any date from the forecasting repo with `python src/export/advisory_contract.py <YYYY-MM-DD> --latest [PATH]`. `scripts/daily_live.sh` writes today’s live outlook straight to `act_1/forecast/latest.json`.

Templates emitted today: `DELAY_SOWING`, `SOW_NOW`, `SWITCH_CROP`, `PREPARE_IRRIGATION`, `DRY_SPELL_CONSERVE_MOISTURE`, `HEAVY_RAIN_PROTECT`. `ALL_CLEAR` isn't emitted by the engine yet; blocks with no advice simply have no row.

The contract layer (`advisory_contract.py`, mirrored in `web/src/lib/contract.ts`) adapts the engine's output to the delivery service (integrated 19 Sep 2026):

- **Crop ids** use the service's vocabulary: `rice` → `paddy`, `pigeonpea` → `tur`.
- **`SWITCH_CROP`**: `alternative` is a crop id the bot can name in every language. The engine's English ladder text moves to `variety_advice`. Rungs that keep the same crop (short-duration variety) go out as `DELAY_SOWING` instead.
- **`sow_by`** (issue date + 13 days) is added to `SOW_NOW` and `SWITCH_CROP`.
- **No nulls**: `officer` is omitted until a real contact is known, and a week's `onset` is `0` once onset has already come.

Parameters per template (engine side):

| Template | `params` keys |
|---|---|
| `DELAY_SOWING` | `event, lead_week, wait_until, p_event, p_clim, resow` (true = re-sowing after a failed onset) |
| `SOW_NOW` | `p_onset, lead_week` |
| `SWITCH_CROP` | `delay_weeks, ladder_level` (0–2), `alternative` (English text of the contingency crop; translate it with the template) |
| `PREPARE_IRRIGATION`, `DRY_SPELL_CONSERVE_MOISTURE` | `event, lead_week, p_event, p_clim, crop_tolerance` |
| `HEAVY_RAIN_PROTECT` | `event, lead_week, p_event, p_clim` |


## 7c. Connecting to the officer console

Connected and tested (19 Sep 2026). The console talks to the service through its own server route, `web/src/app/api/delivery`, so the service's `ADMIN_API_KEY` never reaches a browser. That route forwards only the calls below, and reduces subscriber lists to counts.

- **Settings** go in `web/.env.local`: `DELIVERY_URL=http://127.0.0.1:8000` and `DELIVERY_API_KEY=<act_1's ADMIN_API_KEY>`. With `DELIVERY_URL` unset, the dialog says "not connected". The public Vercel site leaves it unset: the console has no login, so anyone could approve.
- **Opening Review & send** posts each advisory (`POST /advisories`, idempotent), so each one is held as `pending_approval` and shows its recipient count. The phone then shows the service's own rendering (`/advisories/{id}/preview?lang=`): card PNG, voice note once rendered, and WhatsApp text, in any of the 6 languages.
- **Approve & send** calls `POST /advisories/{id}/approve`, which is the officer's sign-off. The dialog then polls `/dispatch/log` and shows queued → sent → delivered → read.
- **Delivery Centre** (top bar → *Delivery*) is the console's view of the service itself: `GET /health`, `GET /dispatch/summary` and `GET /dispatch/log`, refreshed every 5 seconds. It shows how far each message got, the split by language and block, which provider sent it (simulator or WhatsApp Cloud API) and the recent activity feed. Block names are the only thing the browser adds.
- **The service lives in `act_1/`** in this repo, with its own `.venv`, `.env` and SQLite database. `scripts/daily_live.sh` writes each day's outlook to `act_1/forecast/latest.json`.
- **Test without real WhatsApp:** run a second copy in simulator mode on its own database, and point the console at it:
  `WHATSAPP_MODE=simulator DB_PATH=<copy of act_1/var/delivery.sqlite3> uvicorn app.main:app --port 8001` (run from `act_1/`), then `DELIVERY_URL=http://127.0.0.1:8001 npx next dev -p 3100`. `web/scripts/shot_delivery.mjs` drives the whole flow in a browser.
- The farmer page a WhatsApp message should link to is `/f/{block_id}?lang={kn|hi|en}&crop={crop}&date={YYYY-MM-DD}` on the console's host. It's the same page shown in the console's phone preview.

## 8. Done means

1. A real phone completes WhatsApp onboarding using taps only.
2. `POST /advisories` with a fixture, approve it, and it arrives on WhatsApp as card, text, voice note and buttons, in the subscriber's language.
3. The same advisory arrives as a real SMS through the Android gateway.
4. `4-week outlook` answers from `forecast/latest.json`.
5. `/dispatch/log` and `/dispatch/summary` show all of the above with correct statuses.
6. `README.md` covers the setup, every open-source dependency with its licence, and the production path (mKisan/DLT, Bhashini, KVK network).

Record a screen capture of steps 1 and 2 on a real phone. It goes into the demo video.
