import { chromium } from "playwright";
const out = process.argv[2];
const b = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const d = await b.newPage({ viewport: { width: 1400, height: 800 } });
const errs = []; d.on("pageerror", (e) => errs.push(e.message));
await d.goto("http://localhost:3100/", { waitUntil: "load" });
await d.waitForTimeout(9000);
await d.evaluate(() => { const s = window.__console.getState(); s.setDate("2023-07-20"); s.setEvent("dry10"); });
await d.waitForTimeout(2500);
// tight on a few panchayats near Koppal, Karnataka (rebuilt as a coverage)
await d.evaluate(() => window.__console.getState().setFocus([76.02, 15.30, 76.14, 15.38]));
await d.waitForTimeout(9000);
console.log(JSON.stringify(await d.evaluate(() => ({
  zoom: +window.__map.getZoom().toFixed(2),
  shapes: window.__map.queryRenderedFeatures({ layers: ["villages-fill"] }).length,
  labels: document.querySelectorAll(".village-name").length,
}))));
await d.screenshot({ path: `${out}/close_karnataka.png` });
console.log(errs.join("\n") || "no errors");
await b.close();
