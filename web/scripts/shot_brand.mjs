import { chromium } from "playwright";
const out = process.argv[2];
const b = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const d = await b.newPage({ viewport: { width: 1400, height: 800 } });
const errs = []; d.on("pageerror", (e) => errs.push(e.message));
await d.goto("http://localhost:3100/", { waitUntil: "load" });
await d.waitForTimeout(3000);
await d.screenshot({ path: `${out}/brand_intro.png` });     // the intro badge
await d.waitForTimeout(9000);
await d.locator("header").screenshot({ path: `${out}/brand_header.png` });
console.log(errs.join("\n") || "no errors");
await b.close();
