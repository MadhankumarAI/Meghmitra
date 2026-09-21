# UI / UX plan: the officer console

Working name: **Meghmitra** (ಮುಂಗಾರು — "monsoon"). Change freely; nothing depends on it.

Who judges this: MoES is the parent ministry of IMD, IITM and NCMRWF. Assume at least one evaluator is a meteorologist. They will recognise an MJO phase diagram and a reliability curve on sight, and they will distrust any screen that shows a forecast without showing its skill. The UI is designed to earn that person's trust *and* look better than anything else in the room.

---

## 1. Principles

1. **Answer first, evidence one tap away.** Every screen leads with a plain sentence ("68% chance of a 10+ day dry spell, 2–9 July — normal is 31%"). Charts support the sentence, never replace it.
2. **Uncertainty is visible, not hidden.** Colour = probability. Opacity / hatching = how much the model can be trusted at that lead time. Week 4 visibly fades. Nobody else will do this; experts will love it.
3. **Always against normal.** A raw "40% chance of dry spell" means nothing. Every probability is shown next to the climatological probability for that block and week.
4. **Data is the only colour.** UI chrome is neutral slate. The map and charts carry all the colour, so the eye goes where the information is.
5. **Three users, three surfaces, one design system.** Officer (desktop console), farmer (phone, WhatsApp-first), judge/scientist (model transparency).
6. **Fast is a feature.** Precomputed everything. Targets in §7.

---

## 1b. Visual language — this is NOT a chart dashboard

Reference points: UK Met Office warnings, NOAA/NWS outlooks, US Drought Monitor, Copernicus EMS, IMD bulletins. Government-grade products are **map + plain statement + alert tier + action**. Charts live on the Science page only. Everywhere else we use our own purpose-built visuals:

1. **The Onset Front.** IMD's most famous product is the *Northern Limit of Monsoon* line. We draw its probabilistic, block-resolution descendant: a moving front with bands — "onset expected within 1 / 2 / 3 weeks" — sweeping across the map as the week scrubber moves. Blocks where the onset is likely *false* are marked with a broken-line pattern behind the front. Domain-native, instantly legible to MoES, and nobody else will have it.
2. **Texture carries meaning, not just colour.** Dry-spell risk = cracked-earth pattern that gets denser with probability. Heavy rain = rain-stroke pattern. Low model confidence = the pattern dissolves into grain/mist. A block is readable in greyscale and by colour-blind users.
3. **Living atmosphere layer.** Animated flow particles for the low-level monsoon jet and moisture transport (WebGL particle layer). It is beautiful on video *and* it is the actual regional driver the model uses — toggling "why" lights up the flow feeding or starving a block.
4. **The Season Ribbon** (replaces the fan chart in the block panel). One horizontal 30-day band per block: rain texture where wet is likely, cracked texture where dry is likely, fading to mist with lead time. Crop decision windows sit on top as brackets; the recommended sowing window is a highlighted slot. One glyph answers "when do I sow?".
5. **Planet-to-field chain** (replaces gauges). A small globe showing warm/cool Pacific (ENSO), Indian Ocean dipole, and the MJO pulse travelling along the equator → India → this block → this field. Four linked stops, each with one sentence. It is the whole idea, drawn.
6. **Odds as people understand them.** Icon arrays ("in 10 years like this one, 7 had a dry spell here") instead of bars. Analog years are told as memory: "The sky last looked like this in 2014 — sowing here was delayed three weeks."
7. **IMD alert semantics.** Alert tiers reuse IMD's green / yellow / orange / red colour-code meaning (no action / be aware / be prepared / take action), so the ministry reads it without a legend.
8. **The Bulletin.** Every block gets an auto-written, signed-off bulletin — same content as the console — printable as a one-page PDF for the gram panchayat notice board, in the local language. Low-tech last mile, high feasibility.

Where a conventional chart remains (Science page: reliability, ROC, skill by lead), it earns its place because an expert judge expects exactly that chart.

---

## 1c. The headline product: **CMRI — Combined Monsoon Risk Indicator v1.0**

Lesson from Copernicus EDO: their front page does not show five competing datasets. It shows **one named, versioned indicator with three words** — Watch / Warning / Alert. The Combined Drought Indicator fuses rainfall anomaly, soil-moisture anomaly and vegetation stress into a single classified layer, and the classes encode the *physical cascade* of a drought. That single decision is why EDO reads as an authority and most risk maps read as a class project.

We do the same for monsoon sowing risk. CMRI is a cascade from planet to field, expressed as one legend:

| Class | Meaning | Condition |
|---|---|---|
| **Normal** | Nothing to act on | No signal at any level |
| **Watch** | Planetary signal unfavourable | ENSO / IOD / MJO / BSISO state tilts this region toward suppressed convection |
| **Warning** | Local forecast confirms it | Downscaled block-level P(damaging dry spell) exceeds threshold inside the 1–4 week window |
| **Alert** | Act now | A crop decision window is open *and* the block's sowing/soil-moisture state makes the outcome damaging |

Three consequences:
- **One map, one legend, one sentence** on the landing view. Onset / dry spell / heavy rain become drill-downs beneath CMRI, not four peers competing for attention.
- It is **citable and versioned** ("CMRI v1.0", with a validity period stamped under it), which is how operational products are named. Cheap to do, and it changes how the whole thing is perceived.
- Escalation is explainable: a block sitting at Warning can always answer *which* level fired and why.

Colour semantics follow IMD's own green / yellow / orange / red so the ministry needs no legend.

## 1d. Observatory conventions (adopted from EDO, GloFAS, US Drought Monitor)

- **Map is the application.** Full-bleed, edge to edge. Every panel floats over it and is collapsible. No chart appears on the operational view.
- **Standard map / Expert map split** — EDO's single best structural idea. Same data, two audiences, one URL away: *Standard* shows CMRI + one sentence; *Expert* unlocks raw probabilities per event, ensemble spread, driver fields, skill overlays. Our third tier is the farmer phone view. This is how we serve farmer, officer and MoES scientist without compromising any of them.
- **Validity stamp always visible** — "CMRI v1.0 · valid 2026-06-21 to 2026-06-30 · issued 06:00 IST". Operational products state their validity period; forecasts without one look untrustworthy.
- **Layer tray with three tabs**, exactly as EDO splits them:
  - *Indicators* — CMRI, onset probability, dry-spell probability, heavy-rain probability, model confidence
  - *Context* — sown area, crop calendar stage, irrigation coverage, soil water-holding capacity, KVK and rain-gauge network
  - *Base* — terrain / satellite / plain, plus admin boundary level
- **Scale bar, coordinate readout, projection and attribution** in the corner. Small details, and they are precisely what separates a government product from a demo.
- **Downloads is a first-class nav item.** Open data (GeoTIFF / CSV / API) signals the system is meant to be built on. Strong adoption and interoperability point for the PPT.
- **Institutional header** — MoES / IMD / ICAR-CRIDA attribution bar, because it is genuinely built on their data and standards.

### Viewer vs observatory — a deliberate rejection
NASA Earthdata GIS and similar Esri-based portals are **viewers**: a generic shell where the user supplies the meaning (hence "Untitled map", a Sign In button, an onboarding card, and popups reading `1,208,440,000,000,000.00 molecules/cm^2`). EDO is an **observatory**: the product supplies the meaning — one named indicator, three classes, a validity date. We build the observatory. Any hint of a generic GIS shell reads as "someone else's tool with our data in it".

Two things the Esri viewer does better than EDO, both adopted:

**1. Time control (upgraded spec).** A single bottom bar carrying: play/pause, single-step forward and back, a scrubber with tick marks per step, explicit range labels at both ends, a large current-validity readout in the middle, and a settings affordance for step size. Ours steps Week 1 → 4 for forecasts and day-by-day in the hindcast time machine. This is the control that makes the Onset Front visibly *move* — the single most valuable four seconds of the demo video.

**2. "What's here?"** Click anywhere on the map and get a plain-language answer for that point without first hunting for the right layer: block name, current CMRI class, the one-sentence headline, and a link into the full block panel. For an officer or a farmer this is the primary interaction, not a secondary one. Never a raw unit without its interpretation.

Where we go beyond EDO rather than copying it: EDO is visually dated (boxy orange chrome, static classes, no motion). We keep its authority and information architecture, and execute with a modern dark operational theme, the probabilistic Onset Front, texture-encoded risk, the living atmosphere layer and the time-machine replay.

---

## 2. Surface A — Officer Console (desktop; the hero of the demo video)

Dark "mission control" theme — choropleths glow on dark and it films beautifully.

```
┌───────────────────────────────────────────────────────────────────────┐
│ Logo   [Onset | Dry spell | Heavy rain]      Ctrl+K search   ಕ / EN  │
├──────────┬─────────────────────────────────────────┬──────────────────┤
│ PRIORITY │                                         │  BLOCK PANEL     │
│ QUEUE    │              FULL-BLEED MAP             │  headline        │
│ blocks   │   India → state → district → block      │  vs normal       │
│ needing  │        → panchayat (pilot state)        │  4-week strip    │
│ action   │                                         │  rainfall fan    │
│ this wk  │                                         │  why (drivers)   │
│          │                                         │  analog years    │
│          │                                         │  advisories      │
│          │  ◄ W1 ─── W2 ─── W3 ─── W4 ►  ▶ play    │  [Review & send] │
└──────────┴─────────────────────────────────────────┴──────────────────┘
```

### Map
- MapLibre GL, block polygons from a single static PMTiles file. Drill-down by click with smooth `flyTo`; breadcrumb (India › Karnataka › Kalaburagi › Afzalpur) to climb back.
- **Event switcher** (top): Onset · Dry spell · Heavy rain. Each has its own sequential palette (§6).
- **Lead-time scrubber** (bottom): Week 1–4 with play button. Colours morph between weeks on the GPU (feature-state swap — no tile reload), so scrubbing is 60 fps.
- **Confidence encoding:** low-skill cells get reduced opacity + fine hatch pattern. Legend is two-dimensional (probability × confidence).
- Toggle: *probability* ↔ *departure from normal* (diverging palette).
- Hover = tooltip with the number; click = open block panel. Keyboard: arrow keys move the scrubber, `/` or Ctrl+K opens search across all blocks/panchayats.

### Block panel (right)
1. **Headline sentence** — generated from a template, same text the farmer gets.
2. **Probability vs normal** — two horizontal bars, forecast over climatology.
3. **4-week strip** — four cells per event, number + icon + confidence tier (High / Medium / Low).
4. **Rainfall timeline** — last 60 days observed (bars) + forecast fan (median dashed line, 50% and 90% bands). Onset date and any detected false onset annotated on the chart.
5. **Why this forecast** — top-5 drivers from SHAP, phrased for humans ("MJO in phase 4, amplitude 1.6 → suppressed rain over peninsular India"; "low-level jet weakening"). Bar length = contribution, direction = wetter/drier.
6. **Planetary state mini-widgets** — MJO 8-phase wheel with the last 40 days' track (the diagram every meteorologist knows), ENSO and IOD gauges, BSISO phase.
7. **Analog years** — "most similar past situations: 2009, 2014, 2019" with what actually happened in this block.
8. **Advisories** — per major crop of the block, with the decision window it belongs to.
9. **Review & send** — officer edits/approves, sees a phone preview in the chosen language, dispatches. Human-in-the-loop is a trust and feasibility point, not a limitation.

### Priority queue (left)
Blocks ranked by *risk × sown area × an open decision window*. This is the officer's actual workflow: triage → open → review → send. Badge shows pending count.

### Dispatch centre (second tab)
Sent / delivered / read by channel (WhatsApp, SMS, voice) and language; per-panchayat coverage map; message log with the exact template sent. Virtualised table.

---

## 3. Surface B — Farmer view (phone)

**WhatsApp is the front door; the web page is what a link opens.** No login, no install. Light theme, high contrast (cheap screens in sunlight), body ≥ 16 px, targets ≥ 48 px.

One scrolling screen:
1. **Verdict card** — large icon + colour + words: "ಬಿತ್ತನೆ ಮುಂದೂಡಿ · Wait to sow". A **Listen** button plays the advisory as audio (pre-generated TTS).
2. **Next 4 weeks** — four simple tiles (rain / dry / heavy-rain icon). Probability in natural frequencies: "7 in 10 chance", backed by the word scale (likely / possible / unlikely). Research on risk communication consistently finds frequencies are understood better than percentages.
3. **What to do** — 2–4 numbered actions for the selected crop, with the date window.
4. **Crop switcher** and **language switcher** (chips).
5. **Talk to your officer** — tap-to-call the block's extension officer / Kisan Call Centre 1800-180-1551.

Never colour alone: every state has icon + colour + text. Works offline from cache (PWA). No map library on this page — a static SVG locator at most.

---

## 4. Surface C — WhatsApp bot (Namma Metro-style: taps, not typing)

```
Farmer: Hi
Bot:    [list]  Choose language · ಕನ್ನಡ · हिन्दी · తెలుగు · தமிழ் · मराठी · English
Bot:    [location request]  Share your location  (or type your PIN code)
Bot:    [list]  Your crop · Ragi · Tur · Maize · Cotton · Groundnut · Soybean …
Bot:    Advisory card (image) + text + voice note
        [4-week outlook] [Change crop] [Talk to officer]
```
- After this one-time setup the farmer is subscribed; **proactive alerts fire at decision windows** (before sowing, at gap-filling, at contingency switch), not on a fixed daily spam schedule.
- WhatsApp limits we design within: ≤ 3 reply buttons per message, ≤ 10 rows per list.
- Advisory card is a rendered image (same design tokens as the web) so it looks branded and is readable at a glance; text below it is for accessibility and forwarding.
- **Provider: Meta WhatsApp Cloud API directly** — free test number, interactive buttons/lists/location requests supported, no Twilio needed. Needs a Meta developer account and a public webhook (tunnel in dev).
- **SMS:** any Indian bulk-SMS provider needs DLT template registration, which is slow. For the prototype use an Android phone as the SMS gateway (open-source gateways exist) — real SMS, zero cost. Production path: DLT-registered templates via mKisan. Our advisories are fixed templates, so they are DLT-compatible by design.
- **Voice:** TTS voice note over WhatsApp; no IVR needed for the prototype.

---

## 5. Surface D — Model transparency ("Science" page; for judges)

1. **Skill by lead week** — Brier Skill Score vs climatology, per event, weeks 1–4. Honest bars, including the small ones.
2. **Reliability diagram** — "when we say 70%, it happens ~70% of the time".
3. **ROC curves** and a **skill map** (where the model is strong / weak, block by block).
4. **Time machine (hindcast replay)** — pick a past date (e.g. a delayed-onset or long-break year), see exactly what the system would have issued, then reveal what actually happened. This is the centrepiece of the demo video. We only feature years where the held-out model genuinely shows skill, and we show a miss too.
5. **Data lineage & freshness** — sources, last update time, pipeline status.

---

## 6. Design system

| Token | Choice |
|---|---|
| Console theme | Dark slate (`#0B1220` bg, `#111A2E` surface, `#E6EDF7` text) |
| Farmer theme | Light (`#FFFFFF` / `#0F172A`), AA+ contrast everywhere |
| Dry-spell ramp | Yellow → orange → deep brown (YlOrBr, colour-blind safe) |
| Heavy-rain ramp | Light blue → indigo → purple |
| Onset ramp | Pale teal → deep green |
| Departure-from-normal | Brown ↔ teal diverging |
| Never | Rainbow ramps; red/green as the only distinction |
| Latin type | Inter (UI), tabular numerals for every figure |
| Indic type | **Anek** family (Anek Kannada / Devanagari / Telugu / Tamil …) — one designed family across scripts, so every language looks equally first-class |
| Icons | Lucide + a small custom weather/crop set, single stroke width. No emoji. |
| Motion | 200 ms ease-out default; map `flyTo` on drill; count-up on headline numbers; week-scrub colour morph; respects `prefers-reduced-motion` |
| Spacing | 4/8 px scale; breakpoints 375 / 768 / 1024 / 1440 |
| Charts | ECharts — fan chart, reliability, ROC, SHAP bars, MJO wheel (custom) |

---

## 7. Speed plan

- **Geometry is static, data is tiny.** Block polygons live in one PMTiles file on a CDN and never change. The daily forecast is a ~7,000-row array joined client-side via MapLibre `feature-state`. Re-colouring the whole country = one GPU expression swap.
- Per-block detail is a small static JSON fetched on click and prefetched on hover.
- Next.js static/ISR pages; map and charts are lazy-loaded chunks; the farmer page ships no map or chart library.
- Skeletons for anything > 300 ms; space reserved so nothing jumps.

Targets: console interactive < 2 s on a laptop · week scrub 60 fps · farmer page < 100 KB and LCP < 1.5 s on 3G · block panel opens < 150 ms.

---

## 8. Data contract (lets UI and model be built in parallel)

| File | Content |
|---|---|
| `blocks.pmtiles` | Block (and pilot-state panchayat) geometry with stable ids, names in all languages |
| `forecast/latest.json` | per block id → event × week → `p`, `p_clim`, `confidence` |
| `block/{id}.json` | observed timeline, forecast fan, top drivers, analog years, advisories per crop |
| `drivers.json` | current MJO phase/amplitude + track, Niño 3.4, DMI, BSISO |
| `metrics.json` | BSS, reliability bins, ROC points per event × lead × region |
| `hindcast/{date}.json` | same shape as `latest.json`, for the time machine |

UI developers build against schema-valid placeholder files from day one; these are swapped for real model output as soon as it exists and are never shipped.

---

## 9. Build order for the UI track

1. Design tokens, fonts, app shell, theme.
2. Map with block PMTiles, drill-down, event switcher, week scrubber (placeholder data).
3. Block panel: headline, vs-normal, 4-week strip, fan chart.
4. Wire real `forecast/latest.json` + `block/{id}.json`.
5. Why-panel, MJO wheel, analog years.
6. Science page + time machine.
7. Farmer page + advisory card renderer.
8. WhatsApp bot flow → dispatch centre.
9. Polish pass: motion, empty/error states, accessibility, performance audit, demo-video walkthrough script.
