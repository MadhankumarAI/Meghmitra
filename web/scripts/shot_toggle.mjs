import { chromium } from "playwright";
const out = process.argv[2];
const b = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const p = await b.newPage({ viewport: { width: 1600, height: 900 } });
const errs = []; p.on("pageerror", (e) => errs.push(e.message));
await p.goto("http://localhost:3100/", { waitUntil: "load" }); await p.waitForTimeout(8000);
await p.evaluate(() => { const s = window.__console.getState(); s.setDate("2023-07-27"); s.setUnderstand(true); });
await p.waitForTimeout(6000);
// moisture-coloured streaks, everything else off: wind alone, carrying water
await p.evaluate(() => { const s = window.__console.getState(); s.setWindBy("moisture"); ["moist","heat","press"].forEach(k => s.toggleLayer(k)); });
await p.waitForTimeout(6000);
await p.screenshot({ path: `${out}/understand_windonly.png` });
console.log(errs.join("\n") || "no errors");
await b.close();
