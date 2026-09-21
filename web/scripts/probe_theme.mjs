import { chromium, devices } from "playwright";
const b = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const p = await b.newPage({ ...devices["Pixel 7"], isMobile: true });
await p.goto("http://localhost:3100/", { waitUntil: "load" });
await p.waitForTimeout(9000);
const out = await p.evaluate(() => {
  const el = document.querySelector(".map-label.state") || document.querySelector(".map-label");
  const root = getComputedStyle(document.documentElement);
  return {
    label: el ? { cls: el.className, color: getComputedStyle(el).color } : "none",
    surface: root.getPropertyValue("--surface-solid").trim(),
    text: root.getPropertyValue("--text").trim(),
    width: window.innerWidth,
    matches: window.matchMedia("(max-width: 767px)").matches,
  };
});
console.log(JSON.stringify(out, null, 1));
await b.close();
