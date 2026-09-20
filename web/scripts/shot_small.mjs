// Layout at a common laptop size: node scripts/shot_small.mjs OUTDIR [width] [height]
import { chromium } from "playwright";
const [out, w = "1366", h = "768", date = "2023-06-22", block = "2813"] = process.argv.slice(2);
const b = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const p = await b.newPage({ viewport: { width: Number(w), height: Number(h) } });
await p.goto(`http://localhost:${process.env.PORT ?? 3100}/`, { waitUntil: "load" }); await p.waitForTimeout(9000);
await p.evaluate(([d, i]) => { const s = window.__console.getState(); if (d === "live") { s.setMode("live"); s.setUnderstand(false); } else s.setDate(d); s.setSelected(Number(i)); }, [date, block]);
await p.waitForTimeout(4000);
await p.screenshot({ path: `${out}/small_${w}_${date}.png` });
await b.close();
