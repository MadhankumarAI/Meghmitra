// Evidence page, one shot per view: node scripts/shot_science.mjs OUTDIR
import { chromium } from "playwright";
const out = process.argv[2];
const b = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const p = await b.newPage({ viewport: { width: 1500, height: 940 } });
const errs = []; p.on("pageerror", (e) => errs.push(e.message)); p.on("console", (m) => { if (m.type() === "error") errs.push(m.text().slice(0, 140)); });
await p.goto("http://localhost:3100/science", { waitUntil: "load" });
await p.waitForTimeout(4500);
for (const [tab, name] of [["Does it work?", "works"], ["Is it honest?", "honest"], ["Where it works", "where"], ["The model", "model"]]) {
  await p.getByRole("button", { name: new RegExp(tab.replace("?", "\?")) }).click();
  await p.waitForTimeout(2600);
  await p.screenshot({ path: `${out}/sci_${name}.png` });
}
console.log(errs.filter((e) => !e.includes("404")).join("\n") || "no errors");
await b.close();
