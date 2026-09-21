# Feasibility of the deployed system

This describes the system as it would run in production: hosted, department operated, with farmers
enrolled by their gram panchayat and every advisory approved by an agriculture officer. Load figures
are computed from the pipeline's own 2023 season and from the live run on 20 September 2026, not
estimated.

Sections: [The operating model](#1-the-operating-model) · [Onboarding](#2-onboarding-at-the-panchayat) ·
[Human in the loop](#3-human-in-the-loop) · [Load and capacity](#4-load-and-capacity) ·
[Infrastructure](#5-infrastructure) · [Cost](#6-cost) · [Institutions and data](#7-institutions-and-data) ·
[Risks](#8-risks-and-how-they-are-handled) · [Rollout](#9-rollout)

---

## 1. The operating model

Three parties, each doing what they already do.

| Party | Role in the system | What they already have |
|---|---|---|
| **Gram panchayat** | registers farmers, holds the land and soil details, is the first point of contact | the land records, the Soil Health Card data, and the farmer's trust |
| **Block or district agriculture officer** | reviews and approves every advisory before it is sent, by name | the mandate to issue crop advice, and the KVK link behind them |
| **The platform** | produces block-level probabilistic outlooks, turns them into advice grounded in the district's contingency plan, and delivers them | open meteorological data and the ICAR-CRIDA plans |

Nothing in that chain is new to the department. The system slots into an existing advisory practice and
makes it block-specific, probabilistic and traceable.

## 2. Onboarding at the panchayat

Farmer registration happens at the panchayat, not on a consumer app store. This is the single most
important feasibility decision in the design, for four reasons: the data already sits there, the
identity is verified by someone who knows the farmer, no smartphone literacy is required to enrol, and
the panchayat is accountable for the list.

**What the panchayat enters, once per farmer**

| Field | Source at the panchayat | Used for |
|---|---|---|
| Name and mobile number | the farmer, verified in person | delivery on WhatsApp |
| Village or panchayat | already known | resolves to the forecast block |
| Survey number and area | land records held at the panchayat | field-level reference on the advisory |
| Soil type and Soil Health Card details | the SHC already issued for that holding | irrigation and moisture advice, and future soil-aware advice |
| Crops this season | the farmer | advice is issued per crop, from the district contingency plan |
| Sowing date per crop | the farmer | the growth stage the crop will be in when the weather arrives, which decides who is warned |
| Preferred language | the farmer | six languages available |
| Consent, with timestamp | signed at registration | lawful basis for messaging, and the record of it |

**The flow**

1. The panchayat secretary or Krishi Sakhi opens the registration page, which works on a phone.
2. They pick the village from the list (29,803 villages already loaded for the pilot state, from the
   Census village directory), then enter the farmer's details from the records in front of them.
3. The farmer receives one WhatsApp message that reads their record back in their own language, and
   taps once to confirm. That tap is the opt-in. If something is wrong they say so: what is theirs to
   change they change by tapping, and the rest goes to the panchayat and the agriculture officer,
   because a land record is not ours to edit from a chat message. If it is the wrong number, the
   messages stop at once and the officer is told.
4. From then on the farmer can change crops, record a sowing, ask for the four-week outlook, see
   everything we hold about their farm, or reach an officer, all by tapping buttons in WhatsApp. STOP
   unsubscribes instantly.

**This part is built, not planned.** `POST /farmers` takes the panchayat's form, `GET /farmers/{id}`
returns the whole record including every message ever sent to that farmer, and the confirmation
conversation is in `act_1/app/bot.py`. See act_1/README.md §2e.

**Effort.** India has roughly 2.55 lakh gram panchayats. A panchayat with 40 registered farmers, at two
minutes of data entry each, is about 80 minutes of one-time work, spread across the enrolment drive the
department already runs for schemes. Corrections afterwards are a single field edit, not a re-entry.

**Why it is robust.** A list built by the panchayat is a list somebody owns. Phone numbers change,
farmers lease land, crops change mid-season: all of that is maintained where the information lives,
rather than depending on the farmer to update an app.

**What the register buys, beyond delivery.** Once a farmer's village, irrigation and sowing dates are
known, an advisory stops being a broadcast to a block. A ten-day dry spell reaches the rainfed farmer
whose crop is about to flower, is softened for the neighbour on canal water, and is not sent at all to
a farm already harvested or to a farmer told the same thing four days ago. Each of those decisions
carries its reason, and the officer sees both the recipients and the omissions before approving
(`act_1/app/audience.py`). That is the difference between a register and a mailing list.

## 3. Human in the loop

The system is deliberately not autonomous. Two humans stand between the model and the field.

**The officer approves every batch.** The console shows each advisory with the evidence behind it, the
recipients and their languages, and the message exactly as it will arrive. The officer signs with their
name, and the approval is stored with a timestamp against every message that goes out. Rejection is a
first-class action with a recorded reason.

**The panchayat closes the loop on the ground.** The advisory names the officer's contact and the Kisan
Call Centre, and a farmer can ask for a callback from the message itself, which notifies the officers
registered for that block.

**Where the automation stops on its own.** When a contingency plan is ambiguous, or warns against a
crop rather than naming one, the system does not resolve it: the officer sees the plan's own sentence
and page number and decides. That behaviour is what makes a human gate meaningful rather than
ceremonial; the officer is asked to decide exactly where a decision is needed.

## 4. Load and capacity

All measured, not assumed.

| Quantity | Value | Where it comes from |
|---|---|---|
| Blocks forecast daily | 6,824 | every block in India |
| Blocks carrying advice on a given day | about 20% | 1,333 blocks on 20 Sep 2026; 16% average across the 2023 season |
| Advisories per block per season | 24 | 165,656 advisories over the 2023 replay |
| Advisories to review, nationally, per day | about 1,300 | the live run |
| Advisories per district per day | **about 3** | 1,300 spread over roughly 500 district offices |

**Officer capacity is the number that decides whether this works, and it is small.** Three advisories a
day per district, each pre-written, pre-translated and shown with its evidence, is a few minutes of
work. The review is a judgement on advice that is already drafted and cited, not an authoring task. A
single officer can comfortably cover a district; a state can run the whole season without new posts.

**Messages per farmer per season: about 24**, one per advisory for their block and crop. A farmer with
two crops in different situations may receive more, which the console shows before approval.

**Peak.** The season peaks when the monsoon stalls, which is exactly when advice matters. The 2023
replay's worst day issued advice for a large share of blocks; the fan-out is queued per subscriber and
the delivery log shows progress, so a peak lengthens the queue rather than dropping messages.

## 5. Infrastructure

The production shape of the system, and why each part is modest.

| Component | Production form | Why it scales |
|---|---|---|
| Forecast pipeline | one scheduled run a day on a CPU machine | about 30 minutes of training when the model is refreshed; the daily run is minutes, and it is a batch job, not a service |
| Serving | static JSON on a CDN, plus a 25 MB tile file | nothing is computed at request time, so readership does not change the cost |
| Console | a static build behind department sign-in | per-district scoping is an authorisation rule, not new code |
| Delivery service | a hosted API with a managed Postgres | six tables, already normalised; the SQLite used in development maps directly |
| Messaging | Meta WhatsApp Cloud API, official business account | the provider absorbs the throughput; our side is a queue and a status log |
| Media | rendered card and voice note, cached by content hash | the same card serves everyone in a block and language, so cost per message falls as the audience grows |
| Storage | about 365 MB of exports per season, plus the archive | trivial by modern standards |

There is no inference server, no message broker to operate, no vector database, and no GPU in the
forecast path. The deployment is a scheduled job, a static site, an API and a database.

## 6. Cost

The dominant recurring cost is messaging; everything else is small and fixed.

- **Per farmer per season: about 24 messages.** At an Indian utility-template rate in the region of
  ₹0.10 to ₹0.15 per message, that is roughly **₹2.50 to ₹3.50 per farmer per season**. The exact rate
  comes from Meta's current India price card and from any volume agreement the department negotiates.
- **Per district**, with 20,000 registered farmers, that is about ₹50,000 to ₹70,000 a season in
  messaging.
- **Compute and hosting** are a single daily batch job and a static site: a small always-on server plus
  CDN bandwidth, in the low tens of thousands of rupees a year at this scale.
- **Voice notes** are generated once per block, language and message, then reused, so they add storage
  rather than per-farmer cost.

Set against that, a single false onset costs a farmer the seed, the sowing labour and the land
preparation for that attempt. One avoided re-sowing on one acre pays for that farmer's messages for
many seasons. The economics are not close.

## 7. Institutions and data

| Question | Position |
|---|---|
| Who is the meteorological authority | IMD. The product is decision support built on IMD's own gridded rainfall, and says so on screen. |
| Who owns the advice | The department. Advice comes from ICAR-CRIDA district contingency plans, cited to a page, and an officer of the department approves each batch. |
| Data licences | IMD gridded rainfall, NOAA (MJO, Nino 3.4, GFS, ERSST), ECMWF ERA5, geoBoundaries ADM3 and ADM5 under CC BY 4.0 and ODbL, ICAR-CRIDA plans. All open, all attributable. |
| Personal data | Only a phone number, a village, crops and consent, held in the delivery database. The console never receives a subscriber list, only counts. Consent is recorded at registration with a timestamp, and STOP is honoured immediately. This is the shape the DPDP Act expects: a stated purpose, a recorded consent and an easy withdrawal. |
| Data residency | The delivery database and the media store sit wherever the department requires; nothing in the design depends on a particular region. |
| Integration | The farmer registry, land records and Soil Health Card data already exist in state systems; registration at the panchayat can read from them rather than duplicating them. |

## 8. Risks and how they are handled

| Risk | Handling |
|---|---|
| Officer bandwidth during a monsoon break | Three advisories per district per day at the measured rate; the console sorts by severity so the ones that matter are first, and batches can be approved together. |
| Phone numbers change | The panchayat holds the list and edits one field; the farmer does not need to do anything. |
| A farmer stops reading messages | Delivery status is tracked to "read", so silent lists are visible and the panchayat can follow up. |
| WhatsApp template policy | All templates are fixed, pre-approved formats; no free-form text is generated at send time, which is exactly what the policy expects. |
| Connectivity in the field | Messages are asynchronous and queue until the handset reconnects; the voice note works without reading. |
| Language quality | Every string carries a review status, and the officer sees it before approving. New languages are content work on the same machinery. |
| A data feed changes or stops | Every input is dated by publication, feeds are checked daily by a health endpoint, and the daily run validates its inputs before publishing. |
| Scale of enrolment | Enrolment is distributed across 2.55 lakh panchayats, each handling its own few dozen farmers, so it never becomes one central data-entry project. |

## 9. Rollout

| Stage | Scope | What it proves | Ready today |
|---|---|---|---|
| **1. District pilot** | one district, its panchayats, one officer | the human chain end to end: registration, approval, delivery, callback | the pipeline, console, delivery service and village layer are built and running |
| **2. State** | a full state, KVK network involved | officer load at scale and language quality in the field | national forecasts already run daily; the console is national |
| **3. National** | all 6,824 blocks | the same daily run, more registered farmers | the forecast side is already national; only enrolment grows |

The forecasting system is not the part that has to scale: it already produces every block in India every
day. What grows with adoption is the registered farmer list, and that grows the way the government
already works, one panchayat at a time.

---

### Where these numbers come from

`exports/advice_skill_2023.json` (165,656 advisories across the 2023 season), the live contract file for
20 September 2026 (1,333 advisories, 19.5% of blocks), `exports/model_card.json` (runtime and model
counts), and `processed/villages_karnataka.parquet` (29,803 villages). The commands that regenerate each
of them are in [RUNBOOK.md](RUNBOOK.md).
