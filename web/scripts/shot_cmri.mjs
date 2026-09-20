import { chromium } from "playwright";
const out = process.argv[2];
const b = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const p = await b.newPage({ viewport: { width: 1600, height: 900 } });
const errs = []; p.on("pageerror", (e) => errs.push(e.message)); p.on("console", (m) => { if (m.type() === "error") errs.push(m.text()); });
await p.goto(`http://localhost:${process.env.PORT ?? 3100}/`, { waitUntil: "load" }); await p.waitForTimeout(7000);
for (const d of ["2023-06-12", "2023-08-10"]) {
  await p.evaluate((d) => window.__console.getState().setDate(d), d); await p.waitForTimeout(2000);
  await p.screenshot({ path: `${out}/cmri_${d}.png` });
}
console.log(errs.join("\n") || "no errors");
await b.close();
