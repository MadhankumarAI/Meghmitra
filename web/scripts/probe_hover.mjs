import { chromium } from "playwright";
const b = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const d = await b.newPage({ viewport: { width: 1400, height: 800 } });
const errs = []; d.on("pageerror", (e) => errs.push(e.message));
await d.goto("http://localhost:3100/", { waitUntil: "load" });
await d.waitForTimeout(9000);
await d.evaluate(() => { const s = window.__console.getState(); s.setDate("2023-07-20"); s.setEvent("heavy"); s.setUnderstand(true); });
await d.waitForTimeout(6000);
await d.mouse.move(420, 300);            // over the map, right where the left panel sits
await d.waitForTimeout(1200);
await d.mouse.move(430, 320);
await d.waitForTimeout(1200);
await d.screenshot({ path: `${process.argv[2]}/hover_understand.png` });
console.log(errs.join("\n") || "no errors");
await b.close();
