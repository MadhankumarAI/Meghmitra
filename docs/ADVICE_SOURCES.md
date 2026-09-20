# Where the advice comes from

The forecast says *what the weather will probably do*. The advice says *what to do about it*, and that
must come from agronomy, not from us. This is the separation:

| Part | Source | Status |
|---|---|---|
| **When to advise** (is there a risk here, this week?) | our model's probabilities + the observed onset status for that block | real data, scored in `docs/FINDINGS.md` |
| **Which crops matter in this district** | the district's own ICAR-CRIDA contingency plan | real, `src/data/crida_plans.py` |
| **What to do when the monsoon is N weeks late** | the same plan's "Change in crop/cropping system" and "Agronomic measures" for that delay | real, cited to a page |
| **Which farmer gets it** | the crops the farmer registered on WhatsApp | real, from the delivery service's subscribers |
| **The wording sent** | fixed templates, translated and reviewed (`act_1/content/locales`) | nothing generated at send time |

## The plans

ICAR-CRIDA publishes a District Agriculture Contingency Plan for each district: the normal cropping
systems, the sowing windows, and a table of what to do when the monsoon is late by 2 / 4 / 6 / 8 weeks,
when a dry spell follows sowing, in a mid-season break, in terminal drought and in unusual rain.

```bash
python src/data/crida_plans.py index          # 391 plans across 20 states
python src/data/crida_plans.py fetch          # download the PDFs (resumable) -> RAW/crida
python src/data/crida_plans.py parse          # -> PROCESSED/crida_plans.json
python src/advisory/sources.py coverage       # how many of our blocks a plan covers
python src/advisory/sources.py show Dharwad cotton
```

A parsed row keeps the district, the condition, the farming situation, the cropping system, the prescribed
change, the agronomic measure, **the page** and the source URL. The advisory carries that citation, so an
officer can open the plan and check the advice before approving it.

Example, Dharwad (`Dharwad plan, p16–17`):

| Monsoon late by | The plan says |
|---|---|
| 2 weeks | "Maize + Red gram and no other change in cropping system, as the farmers have already decided and kept the inputs ready" |
| 4 weeks | "Avoid green gram–rabi jowar sequence… Maize + Redgram (4:2), Groundnut + Redgram (4:2)", with ridges-and-furrows sowing |
| 6 weeks | "Avoid green gram, groundnut and soybean based cropping systems. Sunflower hybrids–chickpea", Bt cotton spacing 60 × 60 cm |

## Coverage (20 Sep 2026)

385 of the 391 published plans are on disk, parsed into 34,184 rows across 385 districts.

| | blocks |
|---|---|
| The block's own district has a plan | 3,693 (54%) |
| Uses the nearest district's plan, and says so | 2,426 (36%) |
| No plan within reach: indicative table, labelled | 705 (10%) |

Districts created after 2011–12 have no plan of their own, so the engine falls back to the nearest
district **in the same state** (contingency plans are agro-climatically zoned, so a neighbour is a
reasonable proxy) and the citation reads "… — nearest plan to <district>". Beyond about two degrees,
it does not borrow at all.

By state, the plans cover Karnataka 93%, Haryana 93%, Kerala 92%, Tamil Nadu 87%, Andhra Pradesh 85%,
Maharashtra 94%; Arunachal Pradesh and the small union territories have none.

## Rules we hold to

- **Retrieval, not generation.** The lookup is deterministic: district → crop → situation → the plan's own
  row. No model writes advice text.
- **Never recommend what the plan says to avoid.** A sentence like "Avoid green gram, groundnut…" is parsed
  as a negative clause; crops inside it are never offered as the alternative.
- **When the parse is ambiguous, automation stops.** If a plan's recommendation cannot be resolved to a
  single crop, the advisory falls back to "wait, keep seed ready" and the officer sees the plan's exact
  sentence and page in the console. Ambiguity never becomes a confident instruction.
- **Plans age.** These are the 2011–12 editions, the set CRIDA publishes openly; district boundaries have
  changed since, so some new districts have no plan. Where there is no plan, the engine falls back to its
  indicative table and the advisory says so.

## What is still ours, not sourced

- The **crop-stage logic** for the false-onset trap (sowing rain, then a dry spell during establishment) is
  our rule; the measure it quotes comes from the plans' "normal onset followed by a dry spell" rows.
- **Which situation a plan row belongs to** is inferred from its condition text ("delay by 4 weeks",
  "mid season drought", "unusual rains"). Stage rows ("at vegetative stage") inherit the condition above
  them. Rows whose condition we cannot classify are simply not used.
- **Drought tolerance per crop** (used to pick irrigation vs mulching advice) is still an indicative table.
