import { chromium } from "playwright";
const out = process.argv[2];
const b = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const p = await b.newPage({ viewport: { width: 1600, height: 900 } });
const errs = []; p.on("pageerror", (e) => errs.push(e.message));
await p.goto("http://localhost:3100/", { waitUntil: "load" });
await p.waitForTimeout(8000);
await p.evaluate(() => { const s = window.__console.getState(); s.setDate("2023-07-20"); s.setEvent("dry10"); s.setFocus([76.0, 15.30, 76.15, 15.40]); });
await p.waitForTimeout(11000);
await p.mouse.click(800, 430);     // a village polygon near the centre
await p.waitForTimeout(5000);
await p.screenshot({ path: `${out}/village_panel.png` });
console.log(errs.join("\n") || "no errors");
await b.close();
