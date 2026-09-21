import { chromium } from "playwright";
const b = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const ctx = await b.newContext({ viewport: { width: 1400, height: 800 },
  geolocation: { latitude: 15.3475, longitude: 76.0553 }, permissions: ["geolocation"] });  // near Koppal
const d = await ctx.newPage();
const errs = []; d.on("pageerror", (e) => errs.push(e.message));
await d.goto("http://localhost:3100/", { waitUntil: "load" });
await d.waitForTimeout(9000);
await d.evaluate(() => { const s = window.__console.getState(); s.setDate("2023-07-20"); s.setEvent("dry10"); });
await d.waitForTimeout(2500);
await d.getByRole("button", { name: "Show the outlook for where I am" }).click();
await d.waitForTimeout(10000);
console.log(JSON.stringify(await d.evaluate(() => {
  const s = window.__console.getState();
  return { zoom: +window.__map.getZoom().toFixed(2), selected: s.selected, place: s.place, chance: s.placeChance };
})));
await d.screenshot({ path: `${process.argv[2]}/locate_desktop.png` });
console.log(errs.join("\n") || "no errors");
await b.close();
