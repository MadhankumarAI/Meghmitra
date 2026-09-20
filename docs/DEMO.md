# The moat, and the 4-minute demo

## What others cannot build in the time

Assume every serious competing team manages: a neural net on rainfall, a choropleth dashboard, a mocked WhatsApp message. Several will do it well. The question is what we can hold that they cannot reach by the deadline even if they wanted to.

Not the model — a week is enough for a model.
Not the UI — a strong frontend team can match a UI.

**The moat is the hindcast archive: for every block in India, for every day of every monsoon from 1991 to 2025, what our system *would have forecast*, stored and scored.**

It cannot be produced the night before, because it is days of pipeline execution, not a burst of cleverness. It cannot be faked, because a judge can name any year and any district on the spot. And it is the only route to the three things that separate a product from a prototype:

1. **Calibration** — proof that "70%" means 70%.
2. **Measured skill per lead week**, published inside the product.
3. **The Time Machine** — replaying a real disaster year and showing the system calling it in advance.

The archive exists: 35 seasons × 153 issue days × 6,824 blocks × 4 lead weeks, all scored. This is a lead built out of *starting earlier on the boring thing*, which is exactly the lead that is impossible to close late.

Rule that protects it: **1991–2025 is split into five blocks of seven consecutive years, and each block is held out whole.** When we replay 2023, the model issuing that forecast has never seen any year from 2019 to 2025. That's stricter than leaving out one year, because neighbouring years share the same El Niño. Stated on screen, every time. A judge who suspects overfitting is the judge we must pre-empt, and this is the only answer that survives contact.

---

## The 4-minute video

One continuous argument, not a feature tour. Nothing is narrated that is not on screen.

### 0:00–0:25 · The number
Cold open, no logo. Black screen, one line of text builds:

> Every year, on nearly a third of India's monsoon farmland, rain arrives, farmers sow — and the monsoon stops.
>
> In 2002, it was half.

Then the map fades up underneath: the 45-year false-onset record, with 2002 and 2004 lighting up half the country. Voiceover states that this is IMD's own gridded record, computed by us, not an estimate.

*Why it opens the video:* it is a measured fact from ministry data, produced by our pipeline, and it states the problem and our competence in one stroke.

### 0:25–0:40 · Mungaru
The intro plays once: the Mungaru badge, *Rain · Resilient · Rural*, then the all-India block map fades up with the **briefing** (Alert / Warning / blocks with advice, where it concentrates, which blocks to act on first).

Voiceover: forecasts exist at subdivision scale; decisions happen at block scale, for 6,824 blocks. This is the gap we close.

### 0:40–1:40 · The Time Machine: 2023, a year the model never saw
Date **1 June 2023** (the header says *Hindcast*; the model never saw 2019–2025). Press play; the map and the briefing's counts move day by day through the June stall. On **12 June** switch on **Understand**:
- Cyclone Biparjoy pulses in the Arabian Sea (964 hPa), drawing moisture away from the mainland.
- The **heat low** is labelled across the north, under a 42 °C surface-heat glow; the monsoon has reached about 14% of India.
- The narration says the same, in words.
- Under it, **the four fields on the map** - wind, moisture, surface heat, pressure - each with the number it
  is drawn from and a marker that moves at that number's own rate (faster streaks for a stronger jet, quicker
  drops for wetter air). Tap any row to take that field off the map; tap **moisture** under *Colour streaks by*
  and the streaks are coloured by the water the air carries, so the animation shows moisture being transported,
  not just air moving.

Scrub to **27 July**: the dashed line becomes the **monsoon trough** at 22°N and India turns moist (active phase). Scrub to **10 August**: the trough jumps to the foothills and the jet weakens, which is the break of the driest August on record.

### 1:40–2:25 · Why *this* block
Click **Navalgund** (22 June). **Why this outlook** replays: from the block's usual 50% chance of a 10+ day dry spell, each driver moves the marker: recent rain −19, El Niño +5, MJO −3, nearby rain −1, landing on **32%**, the published forecast. Say it once: *these are the exact contributions of the model that made this forecast, not a story added afterwards.*

Switch to **Live** and click **Kalghatgi**: today, 0 mm in 7 days and 8 dry days in a row push the chance from 30% to 70%. That is a Warning, with the advice to conserve soil moisture.

On the **Heavy rain** layer the same block shows the chance as ten cells, the forecast number of them filling with falling drops: *if this week played out 10 times, a heavy-rain day happens in 4 of them, usually 1.* It animates the odds, never a forecast of rain arriving, which is the distinction the whole product rests on.

### 2:25–3:10 · The advice reaches a farmer
**Review & send to farmers**: step 1 shows each advisory with its evidence bar, its recipients and their languages, and the WhatsApp card rendered by the delivery service in Kannada. Step 2: the officer signs with their name and ticks that they read it. Step 3: delivery tracks live (queued → sent → delivered → read).

Cut to a real phone: the card, the Kannada voice note (let three seconds play), the text, and the *Next 4 weeks* button answering from today's live forecast.

### 3:10–3:45 · Proof and honesty
The Evidence page opens on **Did the advice come true?** (2023): *wait to sow* was followed by a 10+ day dry spell 81% of the time (usual 30%); *conserve moisture* 71% (usual 42%). Then the calibration slope: on every decision that drives sowing and moisture management, the chance the system stated is the chance that happened, within about one and a half points. Then skill by lead week, and the classification view: precision 0.81 with recall 0.73 at week 1, precision 0.83 at the threshold that actually issues an advisory.

Then the tab that wins the room: **Tried, measured, not shipped**. Two ideas that should have worked, scored the same way as everything else and left out: the Indian Ocean Dipole, which cost skill at every dry-spell lead, and per-block teleconnection signatures, which recovered the textbook MJO pattern but scored below the simpler model. Both charts are generated from the scoring runs themselves.

### 3:45–4:00 · Cost and scale
Three lines, no narration over them:
- Open data: IMD gridded rainfall (real time), NOAA MJO and Niño 3.4, NOAA GFS and ERA5 for the weather view, open boundaries.
- National by construction: every block in India, with advice in 6 languages on WhatsApp.
- Daily cost: one forecast run and a static site refresh.

Close on the all-India map, Live, with today's date.

---

## Production rules
- Screen capture at 60 fps. The motion that matters: the time bar, the Understand animation and the Why-this-outlook replay; everything else is still.
- No cursor wandering. Every click is decisive and pre-rehearsed.
- Every number on screen comes from the real pipeline. If a number is illustrative, it is not shown.
- No background music under the Kannada voice note.
- Subtitles burned in, because the room may be loud.
