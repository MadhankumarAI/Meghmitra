import { chromium, devices } from "playwright";
const b = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const ctx = await b.newContext({ ...devices["Pixel 7"], isMobile: true, hasTouch: true,
  geolocation: { latitude: 12.9121, longitude: 77.5085 }, permissions: ["geolocation"] });  // Kengeri side
const p = await ctx.newPage();
const errs = []; p.on("pageerror", (e) => errs.push(e.message));
await p.goto("http://localhost:3100/", { waitUntil: "load" });
await p.waitForTimeout(9000);
await p.evaluate(() => { const s = window.__console.getState(); s.setDate("2023-07-20"); s.setEvent("dry10"); });
await p.waitForTimeout(2500);
await p.getByLabel("Show the outlook for where I am").click();
await p.waitForTimeout(9000);
console.log(JSON.stringify(await p.evaluate(() => {
  const s = window.__console.getState();
  return { selected: s.selected, place: s.place, placeChance: s.placeChance, home: s.home };
})));
await p.screenshot({ path: `${process.argv[2]}/locate_village.png` });
console.log(errs.join("\n") || "no errors");
await b.close();
