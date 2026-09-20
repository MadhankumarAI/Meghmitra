# Feature list

Everything the system does, named and described. Each entry is written so it can be lifted straight
onto a slide: the name is the headline, the content is the body. Numbers are from the running system
on 20 September 2026.

Start with [the fifteen that matter](#the-fifteen-that-matter). The rest is the full inventory.

Sections: [Forecasting](#1-forecasting) · [Risk map and console](#2-risk-map-and-console) ·
[Explainability](#3-explainability) · [Weather context](#4-weather-context) ·
[Advisory](#5-advisory) · [Officer review and delivery](#6-officer-review-and-delivery) ·
[Farmer experience](#7-farmer-experience) · [Evidence and validation](#8-evidence-and-validation) ·
[Operations](#9-operations)

---

## The fifteen that matter

If only one slide of features survives, use these. The first eight are what the brief requires. The
last seven are what makes this system ours: none of them is obvious, and each one is measured or
visible in the product rather than claimed.

### Required

**1. Block-level probabilistic outlook, nationwide.**
Onset, dry spell and heavy rain as probabilities for weeks 1 to 4, for every one of India's 6,824
blocks, issued daily from 1 May to 30 September. Forecasts today are issued for subdivisions; 84% of
blocks are smaller than a single IMD grid cell, which is why a subdivision number cannot answer a
sowing question.

**2. Planetary signals brought down to the block.**
The MJO and ENSO enter the model as five and one features respectively, and the model learns each
block's own response to them alongside its rainfall history, so the same MJO phase moves two
neighbouring blocks differently. The alternative, quoting a national index, is what makes planetary
forecasts useless at farm scale.

**3. Colour-coded risk map, one indicator not four.**
Four probabilities become the Composite Monsoon Risk Index with four named classes, Normal, Watch,
Warning and Alert, in IMD's colour semantics. Escalation follows departure from the block's own normal,
so a naturally dry block is not permanently red.

**4. Crop advice, not weather text.**
Five decision templates (wait to sow, sow now, switch crop, conserve soil moisture, prepare
irrigation) plus heavy-rain protection, issued per crop the farmer registered, with the sowing window
enforced so nothing is recommended too late to plant.

**5. Advice grounded in the district's own contingency plan.**
Every recommendation is taken from the ICAR-CRIDA District Agriculture Contingency Plan for that
district, quoted and cited to a page. 385 plans parsed into 34,184 rows; 90% of blocks covered, either
by their own plan or by a declared nearest neighbour in the same state.

**6. Delivery on WhatsApp and sms,(text image and voice) in the farmer's language.**
A picture card, a text message and a voice note, in six languages, with onboarding by taps, buttons
and a shared location or PIN code., the voice note reaches anyone who does not
read comfortably.

**7. An officer approves every batch, by name.**
Review, approve, track. The officer sees the evidence, the recipients and the rendered message before
signing, and every dispatch is logged from queued to sent to delivered to read.

**8. Measured skill, published in the product.**
The full performance matrix, reliability diagrams and per-block skill live on an Evidence page inside
the app, generated from the artifacts, scored only on years the model never saw.

### What makes it ours

**9. False onset is a forecast event, not a footnote.**
The system forecasts the specific failure that destroys a sown crop: rain that meets the sowing
threshold and then stops for ten days or more. It affects 10% to 51% of India's monsoon farmland in a
given year, averaging 29%, and no public product forecasts it at block scale.

**10. Every number explains itself, exactly.**
Week-1 forecasts decompose into six driver groups using exact tree SHAP from the very model that
issued them, and the arithmetic is verified: baseline plus drivers lands on the published probability
to within 3e-08. It is the model's own arithmetic, not a story written afterwards.

**11. Odds are shown as odds.**
A chance is drawn as ten cells with the forecast number of them filling: "if this week played out 10
times, it happens in 4 of them, usually 1". The animation encodes the probability and never implies
that rain is coming.

**12. Retrieval, not generation, and it stops when unsure.**
No language model writes advice, at any point. Where a plan is ambiguous or warns against a crop
rather than naming one, the automation halts and the officer sees the plan's own sentence and page.
Ambiguity never becomes a confident instruction.

**13. A time machine over a hindcast archive.**
Any day of the 2023 season replays from a model that never saw a year after 2018, block by block,
with the advice and the explanation it would have issued. The archive is 35 seasons deep, which is
days of pipeline work rather than something assembled late.

**14. The weather behind the outlook, as physics not decoration.**
Wind, pressure, moisture, surface heat and active lows from ERA5 and GFS, each field carrying the
diagnostic it is drawn from, with the wind streaks colourable by the moisture the air is carrying so
the animation shows moisture transport. The panel states that the risk model does not read these
fields.

**15. Safeguards that hold in production.**
Every number carries its confidence, and the daily run validates its own inputs before publishing: if
the rainfall record is incomplete it holds and reports why, rather than drawing a map on thin data.
Combined with the officer gate and the full dispatch log, nothing reaches a farmer unchecked.

### What was asked, and where it is

| The requirement | Where it lives |
|---|---|
| Downscale planetary signals to local scale | features 1 and 2; `src/features/build_features.py`, `src/models/gbm.py` |
| Probabilistic outlook for monsoon onset, dry spells and heavy rain | feature 1; `/` in the console, any block panel |
| Colour-coded risk map | feature 3; the national map and its legend |
| Crop advisories from the forecast | features 4 and 5; the block panel and `src/advisory/` |
| Reach farmers in their own language | features 6 and 7; `act_1/`, and `/f/[block]` on the web |
| Show that it works | features 8 and 13; `/science` in the console |

---

## 1. Forecasting

### Block-level outlooks for all of India
Probabilistic forecasts for every one of India's 6,824 blocks (ADM3 subdistricts), not for
meteorological subdivisions. 84% of blocks are smaller than a single IMD grid cell, which is the gap
that makes subdivision forecasts unusable for a sowing decision.

### Three decision events, not rainfall totals
The system forecasts the events a farmer actually decides on: monsoon onset (25 mm over 5 days with at
least 3 wet days), a dry spell (runs of 7 or more and 10 or more consecutive dry days), and a
heavy-rain day (64.5 mm, IMD's own threshold). A millimetre total does not tell anyone whether to sow.

### False onset as a first-class event
Rain that meets the sowing threshold and is then followed within 30 days by a 10-day dry run is
labelled a false onset, the exact failure that kills a sown crop. Across 45 years it affects between
10% and 51% of India's monsoon farmland each year, averaging 29%.

### Four-week lead, issued daily through the season
Every event carries a probability for weeks 1, 2, 3 and 4 ahead, issued every day from 1 May to
30 September, which is 153 issue days a year.

### One model per event and lead week
Twelve LightGBM models in production, trained on 1991 to 2025, each specialised to a single event at a
single lead. A model that has to answer four questions at four ranges answers all of them worse.

### 31 features across six evidence groups
The block's own normal, recent rain here, monsoon progress here, rain in the neighbourhood (150 km and
400 km), the MJO, and ENSO. Every feature is computed as of the issue day, with each index stamped by
the date it was actually published.

### Calibrated probabilities, published raw
There is no calibration layer: the model's raw probability is what appears on screen, and its
reliability is measured instead of assumed. Weighted calibration error is under 1% for every event.

### Confidence travels with every number
Each lead week carries the confidence the measurements support, and the console labels what it is
showing, so an officer always knows how much weight a number can take.

---

## 2. Risk map and console

### Composite Monsoon Risk Index (CMRI)
Four probabilities become one indicator with four named classes, Normal, Watch, Warning and Alert, in
IMD's colour semantics. Escalation is based on departure from the block's own normal rather than raw
probability, so a naturally dry block is not permanently red.

### National map at block resolution
All 6,824 blocks in one WebGL map, served from a single 25 MB PMTiles file with no tile server. Pan
and zoom stay smooth because the map reads only the byte ranges it needs.

### Zoom-tiered place labels
State names, then districts, then blocks as you zoom, with collision avoidance that also respects the
open panels, so a name never hides behind a card. Without them, a risk map is a pretty abstraction
nobody can navigate.

### Event switching
One tap moves the map between the composite risk view and the individual layers: onset, dry spell and
heavy rain. The legend and the map key follow.

### Time machine, 2023 replay
A full season replayed day by day from a model that never saw any year after 2018, with a segmented
month rail, a playhead and a hover date chip. This is what lets someone name a date and see what the
system would have said on it.

### Live mode
The same console against today's real-time data, clearly stamped as live rather than hindcast, with
the rainfall-through date visible.

### Confidence by lead week
Week tiles carry a confidence band (high, medium, low) that follows the measured skill at that lead,
not a guess, so week 4 never looks as solid as week 1.

### Block search
Search any block, district or state by name, with Ctrl+K from anywhere in the console, including local
language names where available.

### Block panel
One block's full picture: the four-week outlook, the onset status, the advice, the evidence behind the
number, and the recipients who would receive it.

### Hover card
A fast read of any block under the cursor without opening anything: name, class and the headline
number.

### Daily briefing
The day in four numbers: blocks at Alert, blocks at Warning, blocks with advice, and where the risk is
concentrated, so an officer knows where to look before touching the map.

---

## 3. Explainability

### Why this outlook
Every week-1 number decomposes into the six driver groups that produced it, starting from the block's
baseline and landing exactly on the published probability. It is not a narrative added afterwards.

### Exact tree SHAP, from the model that issued it
Contributions come from LightGBM's exact tree SHAP on the very model that made the forecast, and the
arithmetic is verified: baseline plus drivers matches the published probability to within 3e-08 across
every forecast in the archive.

### Evidence in plain words
Each driver carries the observation behind it, for example "0 mm in the last 7 days, 8 dry days in a
row" or "Nino 3.4 at +1.2 C: El Nino", so the officer sees the fact, not just the weight.

### Animated contribution replay
The explanation plays out as the marker moves from the baseline to the final number, one driver at a
time, which is what makes it land in a demo and in a farmer briefing alike.

### Odds shown as odds
A probability is drawn as ten cells with the forecast number of them filling: "if this week played out
10 times, a heavy-rain day happens in 4 of them, usually 1". It animates the chance, never a
prediction that rain is coming.

### Drivers follow the published file
If the model did not use a driver, it is not shown. The console reads the driver list from the
forecast file rather than assuming a fixed set, so an explanation can never invent a factor.

---

## 4. Weather context

### Understand: the atmosphere behind the outlook
Wind at 1.5 km, sea-level pressure, column moisture, surface heat and active lows from ERA5 for the
replay and NOAA GFS for live, drawn over the map. It answers "why is the season behaving like this",
which the risk number alone cannot.

### Four fields with equal standing
Each field lists the diagnostic it is drawn from (jet speed in m/s, column water in mm, hottest plains
point in C, the deepest low's central pressure) with a marker that animates at that value's own rate.
Any field can be switched off so the others can be read alone.

### Moisture transport, not just wind
The wind streaks can be coloured by the column moisture sampled at each particle, so a dry streak over
the desert stays faint while the same wind over the Arabian Sea glows. That is the quantity that
actually decides onset.

### Phase-aware trough labelling
The dashed line of lowest pressure is labelled Heat low while the monsoon is still advancing and
Monsoon trough once it has arrived, with the colour following. High ground above 600 m is masked so
extrapolated pressure over the Himalaya cannot invent a low.

### Plain-language reading
A short narration in the terms an IMD forecaster would use: jet strength, trough position, active or
break phase, with the numbers in brackets.

### Stated as context, not as reasoning
The panel says on screen that the risk model does not read these fields. Mixing the two would be the
easiest way to mislead an audience, so the product refuses to.

---

## 5. Advisory

### Advice grounded in official contingency plans
Recommendations come from the district's own ICAR-CRIDA District Agriculture Contingency Plan, quoted
and cited to a page, so an officer can open the source and check before approving. 385 plans are
parsed into 34,184 rows.

### Retrieval, not generation
The lookup is deterministic: district, then crop, then situation, then that plan's own row. No
language model writes advice text, at any point, including at send time.

### Nearest-plan fallback, declared
Districts created after the plans were published have none of their own, so the engine falls back to
the nearest plan in the same state and the citation says so in words. 54% of blocks use their own
district's plan, 36% a declared neighbour, 10% a labelled indicative table.

### Never recommends what a plan warns against
Sentences like "Avoid green gram, groundnut and soybean" are parsed as negative clauses, and any crop
inside them is excluded from being offered as an alternative.

### Automation stops at ambiguity
Where a plan's recommendation cannot be resolved to a single crop, the advisory falls back to "wait,
keep seed ready" and the officer sees the plan's exact sentence and page. Ambiguity never becomes a
confident instruction.

### Five decision templates
Wait to sow, sow now, switch crop, conserve soil moisture and prepare irrigation, plus a heavy-rain
protection message, each with its own parameters, severity and outcome definition.

### Crop-aware
Advice is issued per crop registered by the farmer, using the crops the district plan itself names as
relevant, not a generic national list.

### Timing guards
A switch-crop recommendation is suppressed when the sowing window for that crop has passed, so the
system cannot tell someone in September to plant something that needed sowing in June.

---

## 6. Officer review and delivery

### Nothing is sent automatically
Every batch passes an agriculture officer. The approval records their name, and the dispatch is
traceable back to it.

### Three-step review
Review, approve, track. Step one shows each advisory with its evidence, its recipients and their
languages, and the WhatsApp card exactly as it will arrive. Step two takes the officer's name and an
explicit confirmation that they read it. Step three tracks delivery live.

### Rendered preview in the farmer's language
The preview is produced by the delivery service itself, not a mockup, so what the officer sees is what
the farmer receives.

### Translation status on every message
Each string carries a status (machine, checked, reviewed, glossary) and the console shows it before
approval, so nobody signs off on raw machine output believing it to be reviewed.

### Reject with a reason
Rejection is a first-class action with a recorded reason, not a silent discard.

### Delivery Centre
Service health, queue depth and what has actually been sent, refreshed live: statuses move queued,
sent, delivered, read, or failed with the provider's error.

### Key never reaches the browser
The console talks to the delivery service through its own server-side proxy, which forwards only an
allowlist of calls and reduces subscriber lists to counts. On the public deployment the connection is
deliberately left unconfigured, because the console has no login.

---

## 7. Farmer experience

### WhatsApp, in six languages
English, Kannada, Hindi, Telugu, Tamil and Marathi, delivered where farmers already are, with no app
to install.

### Onboarding by taps, not typing
Language, location and crops are chosen with buttons, lists and a shared location. A PIN code works
for anyone who will not share a location.

### Three artefacts per advisory
A picture card with the alert colour, the verdict, the four-week tiles and three steps; a text message
with buttons; and a voice note in the same language, for anyone who does not read comfortably.

### Natural frequencies, never certainty
Chances are sent as "7 in 10" next to the usual rate "usually 3 in 10", and never as a promise. Week 4
is explicitly shown as less certain than week 1.

### Four-week outlook on demand
A button returns the block's current outlook from the live forecast, as a picture and text, without
waiting for the next advisory.

### Talk to an officer
A button hands over the local officer's contact card and the Kisan Call Centre number, and notifies
the officers registered for that block that a farmer asked for them.

### Crop changes any time
A farmer can change their registered crops from the menu, and subsequent advice follows.

### STOP and START honoured immediately
Opting out is instant and recorded with a timestamp; START brings them back. Consent is stored per
subscriber.

### Web farmer view
The same content as a public web page per block, in the same languages, for sharing in a WhatsApp
group or projecting at a village meeting.

---

## 8. Evidence and validation

### An evidence section, not a claim
Four tabs: does it work, is it reliable, where does it work, and the model in full. Each one is
generated from the artifacts, so the page cannot drift from the system.

### The full performance matrix
BSS, AUC, Brier, climatology Brier, base rate and the number of forecasts scored, for four events
across four lead weeks, on held-out years only, 36.5 million forecasts per cell.

### Reliability diagrams
The measured curve against the diagonal for every event, with the number of forecasts in each bin
shown, so a thin bin cannot masquerade as proof.

### Did the advice come true?
The 2023 replay checks every issued advisory against what the rain actually did: 81% for wait to sow
against a 47% base rate, 71% for conserve moisture against 40%, 66% for irrigation against 36%, and
59% for sow now against 23%.

### Candidates are measured before they ship
Every proposed addition is trained and scored under the same protocol before it can enter the model,
and the comparison is published: the Indian Ocean Dipole and per-block teleconnection signatures were
both built, scored and set aside because the measurements did not support them.

### Model card
What the model is, what it was trained on, its parameters, its inputs and their publication dates, all
read from the trained artifacts rather than written by hand.

### Where it works, block by block
Per-block skill rather than a national average: week-1 dry-spell skill is positive in 100% of the
6,824 blocks, and the map shows the value for each one.

### The validation protocol, stated on screen
Five contiguous blocks of seven years, each held out whole, with every fitted quantity including the
climatology input rebuilt without the held-out years. The header of the console says "hindcast" when
you are looking at a replayed year.

---

## 9. Operations

### One command for the daily run
Fetch, forecast, explain, advise, export and hand over, in four stages, in a few minutes.

### Refuses to publish rather than mislead
Outside the season, or when more than 6 of the last 60 days of rainfall are missing, the run declines
to publish and the console shows the reason.

### Every input dated by publication, not observation
No forecast uses a value it could not have had on the day. Feeds that lag or stop are replaced, which
is why the MJO comes from ROMI and the dipole was computed in house.

### Deterministic training
Training is seeded, so re-running the same code reproduces the same predictions exactly. That is how a
code change is proved not to move any published number.

### No inference server
The pipeline writes static JSON; the console and the delivery service read it. There is nothing to
scale at request time, and the daily cost is one forecast run plus a static refresh.

### Simulator mode
The entire delivery path can be exercised end to end without sending a single real message, including
a WhatsApp-like phone page driven by the real bot code.

### Health checks
One endpoint reports the access token, the geo data, ffmpeg, the webhook and the per-language
translation status, so a failure is visible before a farmer notices it.

### Test coverage where it matters
Label definitions, the delivery service's approval gate, fan-out, the status lifecycle, template
lengths in every language, and the exact Graph API requests sent.

### Audit trail
Who approved what, when, to whom it went, and what the provider said, kept per message part.
