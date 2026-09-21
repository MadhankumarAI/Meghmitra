import { chromium, devices } from "playwright";
const out = process.argv[2];
const b = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const ctx = await b.newContext({ ...devices["Pixel 7"], isMobile: true, hasTouch: true,
  permissions: ["geolocation"], geolocation: { latitude: 12.917, longitude: 77.48 } });   // Kengeri
const p = await ctx.newPage();
const errs = []; p.on("pageerror", (e) => errs.push(e.message));
await p.goto("http://localhost:3100/", { waitUntil: "load" });
await p.waitForTimeout(8000);
await p.getByLabel("Show the outlook for where I am").click();
await p.waitForTimeout(6000);
await p.screenshot({ path: `${out}/m4_located.png` });
// close the sheet and zoom out: their block must stay marked
await p.getByLabel(/close/i).first().click().catch(() => {});
await p.waitForTimeout(800);
await p.evaluate(() => { const s = window.__console.getState(); s.setSelected(null); });
await p.waitForTimeout(1200);
await p.mouse.move(540, 900); for (let i = 0; i < 6; i++) { await p.keyboard.press("Minus"); await p.waitForTimeout(250); }
await p.waitForTimeout(3500);
await p.screenshot({ path: `${out}/m5_zoomed_out.png` });
console.log(errs.join("\n") || "no errors");
await b.close();
