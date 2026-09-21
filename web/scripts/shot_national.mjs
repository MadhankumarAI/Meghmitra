import { chromium } from "playwright";
const out = process.argv[2];
const box = [77.45, 12.85, 77.65, 13.00];          // inside Bengaluru South, as in the report
const b = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const d = await b.newPage({ viewport: { width: 1400, height: 800 } });
const errs = []; d.on("pageerror", (e) => errs.push(e.message));
await d.goto("http://localhost:3100/", { waitUntil: "load" });
await d.waitForTimeout(9000);
await d.evaluate(() => { const s = window.__console.getState(); s.setDate("2023-07-20"); });
await d.waitForTimeout(2500);
for (const ev of ["cmri", "dry10", "heavy"]) {
  await d.evaluate((e) => { const s = window.__console.getState(); s.setEvent(e); s.setFocus([77.45, 12.85, 77.65, 13.0]); }, ev);
  await d.waitForTimeout(8000);
  const n = await d.evaluate(() => {
    const m = window.__map;
    const f = m.queryRenderedFeatures({ layers: ["villages-fill"] });
    return { zoom: +m.getZoom().toFixed(2), shapes: f.length,
             coloured: f.filter((x) => x.properties.col).length,
             labels: document.querySelectorAll(".village-name").length };
  });
  console.log(ev, JSON.stringify(n));
  await d.screenshot({ path: `${out}/v_${ev}.png` });
}
console.log(errs.join("\n") || "no errors");
await b.close();
