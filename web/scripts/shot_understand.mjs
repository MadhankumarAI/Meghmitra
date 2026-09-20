import { chromium } from "playwright";
const out = process.argv[2];
const b = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const p = await b.newPage({ viewport: { width: 1600, height: 900 } });
const errs = []; p.on("pageerror", (e) => errs.push(e.message)); p.on("console", (m) => { if (m.type() === "error") errs.push(m.text()); });
await p.goto(`http://localhost:${process.env.PORT ?? 3100}/`, { waitUntil: "load" }); await p.waitForTimeout(8000);
for (const d of (process.env.DATES ?? "2023-06-12,2023-08-10").split(",")) {
  await p.evaluate((d) => { const s = window.__console.getState(); s.setDate(d); s.setUnderstand(true); }, d);
  await p.waitForTimeout(6000);                                   // let particles build trails
  await p.screenshot({ path: `${out}/understand_${d}.png` });
}
console.log(errs.join("\n") || "no errors");
await b.close();
