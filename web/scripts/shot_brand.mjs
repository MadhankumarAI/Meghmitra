// Intro + header branding: node scripts/shot_brand.mjs OUTDIR
import { chromium } from "playwright";
const out = process.argv[2];
const b = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const p = await b.newPage({ viewport: { width: 1600, height: 900 } });
const errs = []; p.on("pageerror", (e) => errs.push(e.message)); p.on("console", (m) => { if (m.type() === "error" || m.type() === "warning") errs.push(m.text().slice(0, 200)); });
await p.goto(`http://localhost:${process.env.PORT ?? 3100}/`, { waitUntil: "domcontentloaded" });
await p.waitForTimeout(1300); await p.screenshot({ path: `${out}/brand_intro.png` });
await p.waitForTimeout(9000); await p.screenshot({ path: `${out}/brand_header.png`, clip: { x: 0, y: 0, width: 800, height: 80 } });
await p.reload({ waitUntil: "domcontentloaded" }); await p.waitForTimeout(600);
await p.screenshot({ path: `${out}/brand_repeat.png`, clip: { x: 0, y: 0, width: 800, height: 450 } });
console.log(errs.filter((e) => !e.includes("404")).join("\n") || "no errors");
await b.close();
