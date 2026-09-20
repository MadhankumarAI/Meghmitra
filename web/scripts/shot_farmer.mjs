import { chromium } from "playwright";
const out = process.argv[2];
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
const errs = []; p.on("pageerror", (e) => errs.push(e.message)); p.on("console", (m) => { if (m.type() === "error") errs.push(m.text()); });
for (const lang of ["kn", "hi"]) {
  await p.goto(`http://localhost:3100/f/7132399B62927069207149?lang=${lang}&date=2023-06-22`, { waitUntil: "load" });
  await p.waitForTimeout(3500);
  await p.screenshot({ path: `${out}/farmer_${lang}.png`, fullPage: false });
  await p.evaluate(() => document.querySelector(".overflow-y-auto").scrollTo(0, 9999)); await p.waitForTimeout(600);
  await p.screenshot({ path: `${out}/farmer_${lang}_bottom.png` });
}
console.log(errs.join("\n") || "no errors");
await b.close();
