// Map labels at three zooms + the model card: node scripts/shot_labels.mjs OUTDIR
import { chromium } from "playwright";
const out = process.argv[2];
const b = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const p = await b.newPage({ viewport: { width: 1600, height: 900 } });
const errs = []; p.on("pageerror", (e) => errs.push(e.message)); p.on("console", (m) => { if (m.type() === "error") errs.push(m.text().slice(0, 140)); });
await p.goto("http://localhost:3100/", { waitUntil: "load" }); await p.waitForTimeout(10000);
await p.evaluate(() => window.__console.getState().setDate("2023-06-22"));
await p.waitForTimeout(2500);
await p.screenshot({ path: `${out}/labels_national.png` });
// zoom to Dharwad district, Karnataka
await p.evaluate(() => window.__console.getState().setFocus([74.4, 15.0, 76.4, 16.4]));
await p.waitForTimeout(4000);
await p.screenshot({ path: `${out}/labels_district.png` });
await p.evaluate(() => window.__console.getState().setFocus([75.0, 15.2, 75.6, 15.7]));
await p.waitForTimeout(4000);
await p.screenshot({ path: `${out}/labels_block.png` });
await p.goto("http://localhost:3100/science#model", { waitUntil: "load" }); await p.waitForTimeout(5000);
await p.evaluate(() => document.getElementById("model")?.scrollIntoView());
await p.waitForTimeout(2000);
await p.screenshot({ path: `${out}/model_card.png` });
await p.evaluate(() => { const el = document.querySelector(".h-full.overflow-y-auto"); (el ?? window).scrollBy(0, 980); });
await p.waitForTimeout(1500);
await p.screenshot({ path: `${out}/model_matrix.png` });
console.log(errs.filter((e) => !e.includes("404")).join("\n") || "no errors");
await b.close();
