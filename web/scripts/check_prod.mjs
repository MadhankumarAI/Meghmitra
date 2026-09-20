// Click-through check of a production build (no dev-only hooks).  PORT=3200 node scripts/check_prod.mjs <outdir>
import { chromium } from "playwright";
const out = process.argv[2], base = `http://localhost:${process.env.PORT ?? 3100}`;
const b = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const p = await b.newPage({ viewport: { width: 1600, height: 900 } });
const errs = []; p.on("pageerror", (e) => errs.push(e.message)); p.on("console", (m) => { if (m.type() === "error") errs.push(m.text()); });
await p.goto(base + "/", { waitUntil: "load" }); await p.waitForTimeout(8000);
await p.getByRole("slider", { name: "Forecast issue date" }).click({ position: { x: 300, y: 12 } }); await p.waitForTimeout(2500);
await p.screenshot({ path: `${out}/prod_map.png` });
await p.keyboard.press("Control+k"); await p.waitForTimeout(400);
await p.keyboard.type(process.env.BLOCK ?? "Harihar"); await p.waitForTimeout(500); await p.keyboard.press("Enter"); await p.waitForTimeout(3500);
await p.getByRole("button", { name: /Review/ }).click(); await p.waitForTimeout(5000);
await p.screenshot({ path: `${out}/prod_review.png` });
console.log(errs.join("\n") || "no errors");
await b.close();
