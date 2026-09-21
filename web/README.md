# The officer console

The web front end of [Meghmitra](../README.md): a block-level monsoon risk map for India, the
explanation behind every number, the atmosphere that produced it, and the approval queue an
agriculture officer works through before anything reaches a farmer.

Next.js 16 (App Router, Turbopack), React 19, Tailwind v4, MapLibre with PMTiles, zustand, motion.
No server rendering of data: the console reads static JSON exported by the pipeline, so it can be
hosted anywhere and stays fast on a bad connection.

## Routes

| Route | What it is |
|---|---|
| `/` | the console: risk map, time machine, block panel, explanations, atmosphere, delivery |
| `/science` | the evidence: how it works, whether it is honest, where it works, the model card |
| `/f/[block]` | the farmer view of a single block, the same content that goes out on WhatsApp |
| `/api/delivery/*` | server-side proxy to the delivery service, so its admin key never reaches a browser |
| `/api/farmer/*` | the public read path for the farmer view |

## Running it

```bash
npm install          # postinstall copies the MapLibre worker
npm run dev          # http://localhost:3100
```

`public/data` is a junction to `D:\Morphy\exports` during development, so the console always reads
whatever the pipeline last wrote. Two scripts manage it:

```bash
npm run data:stage   # replace the junction with a real folder holding only what the site may serve
npm run data:link    # put the junction back
```

Staging exists because a deployment cannot upload a link, and because the exports contain files the
public site must not serve (the advisory contract, the live forecast). Staging also gzips the daily
forecast, advisory and explanation files; `src/lib/gz.ts` unpacks them in the browser.

## Environment

Everything optional. Without them the console still runs, and says what is missing.

| Variable | Effect |
|---|---|
| `DELIVERY_URL` | where the delivery service lives, for example `http://127.0.0.1:8000`. Unset means the Delivery panel says "not connected" |
| `DELIVERY_API_KEY` | the delivery service's admin key. Server side only, never sent to the browser |
| `MORPHY_EXPORTS` | source folder for `data:stage`, default `/d/Morphy/exports` |

A public deployment should leave `DELIVERY_URL` unset: the console has no login, so anyone who could
open it could approve a dispatch.

## How the pieces fit

```
src/
  app/                routes, the delivery proxy, global styles
  components/
    console/          map furniture: time bar, block panel, why panel, odds, review and send
    map/              MapLibre view, the atmosphere canvas, zoom-tiered place labels
    science/          the evidence pages: model card, reliability, what we tried and dropped
    farmer/           the single-block view
  lib/
    store.ts          one zustand store: date, event, block, layers, mode
    atmos.ts          atmosphere frames and the plain-language reading of them
    explain.ts        driver contributions, exactly as the model produced them
    advisory.ts       advisory rendering, including contingency-plan citations
    gz.ts             gzipped daily file loading
```

Three rules the code follows, and reviews should hold it to:

1. **Nothing is invented in the browser.** Every number on screen comes from an exported file. If a
   file is missing, the UI says so rather than filling in a plausible value.
2. **Uncertainty is shown, not smoothed.** Where the model has no skill, the console shows
   climatology and labels it. Probabilities are drawn as chances, never as "rain is coming".
3. **The map is the subject.** Panels are captions: opaque, narrow, and dismissable.
