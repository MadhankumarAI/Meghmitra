import { chromium, devices } from "playwright";
const b = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const ctx = await b.newContext({ ...devices["Pixel 7"], isMobile: true, hasTouch: true });
const p = await ctx.newPage();
const errs = []; p.on("pageerror", (e) => errs.push(e.message));
await p.goto("http://localhost:3100/", { waitUntil: "load" });
await p.waitForTimeout(9000);
await p.evaluate(() => { const s = window.__console.getState(); s.setDate("2023-07-20"); });
const ev = () => p.evaluate(() => window.__console.getState().event);

// 1. plain: open the menu and tap a layer
await p.getByLabel("Open menu").tap();
await p.waitForTimeout(700);
await p.screenshot({ path: `${process.argv[2]}/menu_open.png` });
await p.getByRole("button", { name: "Heavy rain" }).tap();
await p.waitForTimeout(900);
console.log("after tapping Heavy rain:", await ev());

// 2. with the block sheet open underneath, which used to paint over the menu
await p.evaluate(() => window.__console.getState().setSelected(2831));
await p.waitForTimeout(1200);
await p.getByLabel("Open menu").tap();
await p.waitForTimeout(700);
await p.screenshot({ path: `${process.argv[2]}/menu_over_sheet.png` });
await p.getByRole("button", { name: "Dry spell" }).tap();
await p.waitForTimeout(900);
console.log("with the sheet open:", await ev());

// 3. the scrim closes it, and does not reach the map
await p.getByLabel("Open menu").tap();
await p.waitForTimeout(600);
const before = await p.evaluate(() => window.__console.getState().selected);
await p.mouse.click(200, 700);
await p.waitForTimeout(700);
console.log("scrim tap closed:", !(await p.getByRole("dialog").isVisible().catch(() => false)),
            "| selection unchanged:", before === await p.evaluate(() => window.__console.getState().selected));
console.log(errs.join("\n") || "no errors");
await b.close();
