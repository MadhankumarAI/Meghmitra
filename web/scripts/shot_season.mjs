import { chromium } from "playwright";
const out = process.argv[2];
const b = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const p = await b.newPage({ viewport: { width: 1600, height: 900 } });
const errs = []; p.on("pageerror", (e) => errs.push(e.message)); p.on("console", (m) => { if (m.type() === "error") errs.push(m.text()); });
await p.goto("http://localhost:3100/", { waitUntil: "load" }); await p.waitForTimeout(7000);
await p.getByRole("button", { name: "Onset" }).click(); await p.waitForTimeout(800);
for (const d of ["2023-06-01", "2023-06-12", "2023-06-22", "2023-07-02"]) {
  await p.evaluate((d) => window.__console.getState().setDate(d), d);
  await p.waitForTimeout(1800);
  await p.screenshot({ path: `${out}/season_${d}.png`, clip: { x: 430, y: 60, width: 740, height: 700 } });
}
await p.getByRole("button", { name: "Risk (CMRI)" }).click();
await p.evaluate(() => window.__console.getState().setDate("2023-06-12")); await p.waitForTimeout(1800);
await p.screenshot({ path: `${out}/full_cmri_0612.png` });
console.log(errs.join("\n") || "no errors");
await b.close();
