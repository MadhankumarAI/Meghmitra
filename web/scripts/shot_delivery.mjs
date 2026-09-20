// Review → Approve → Track against a running delivery service:
//   node scripts/shot_delivery.mjs OUTDIR [date|live] [blockIndex]
import { chromium } from "playwright";
const [out, date = "2023-06-12", block = "3856"] = process.argv.slice(2);
const b = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const p = await b.newPage({ viewport: { width: 1600, height: 900 } });
const errs = []; p.on("pageerror", (e) => errs.push(e.message)); p.on("console", (m) => { if (m.type() === "error") errs.push(m.text()); });
await p.goto(`http://localhost:${process.env.PORT ?? 3100}/`, { waitUntil: "load" }); await p.waitForTimeout(7000);
await p.evaluate(([d, i]) => { const s = window.__console.getState(); if (d === "live") s.setMode("live"); else s.setDate(d); s.setSelected(Number(i)); }, [date, block]);
await p.waitForTimeout(2500);
await p.getByRole("button", { name: /Review/ }).first().click();
await p.locator('img[alt^="Advisory card"]').or(p.getByRole("heading", { name: "Delivery" })).first().waitFor({ timeout: 60000 });
await p.waitForTimeout(1500);
await p.screenshot({ path: `${out}/rs_1_review.png` });
const next = p.getByRole("button", { name: /Continue to approval/ });
if (process.env.APPROVE !== "0" && await next.count() && await next.isEnabled()) {
  await next.click(); await p.waitForTimeout(600);
  await p.getByLabel("Approved by").fill("R. Verma, SADO Sehore");
  await p.getByRole("checkbox", { name: /I have read/ }).check();
  await p.waitForTimeout(400);
  await p.screenshot({ path: `${out}/rs_2_approve.png` });
  await p.getByRole("button", { name: /Approve & send|Hold back all/ }).click();
}
await p.waitForTimeout(Number(process.env.WAIT ?? 32000));
await p.screenshot({ path: `${out}/rs_3_track.png` });
console.log(errs.join("\n") || "no errors");
await b.close();
