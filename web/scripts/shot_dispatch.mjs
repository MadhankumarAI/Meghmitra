// Delivery Centre against the running service: node scripts/shot_dispatch.mjs OUTDIR
import { chromium } from "playwright";
const out = process.argv[2];
const b = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const p = await b.newPage({ viewport: { width: 1600, height: 900 } });
const errs = []; p.on("pageerror", (e) => errs.push(e.message)); p.on("console", (m) => { if (m.type() === "error") errs.push(m.text().slice(0, 160)); });
await p.goto(`http://localhost:${process.env.PORT ?? 3100}/`, { waitUntil: "load" }); await p.waitForTimeout(9000);
await p.getByRole("button", { name: "Delivery" }).click();
await p.waitForTimeout(3500);
await p.screenshot({ path: `${out}/dispatch.png` });
console.log(errs.filter((e) => !e.includes("404")).join("\n") || "no errors");
await b.close();
