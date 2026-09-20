import { chromium } from "playwright";
const b = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const p = await b.newPage({ viewport: { width: 1600, height: 900 } });
await p.goto("http://localhost:3100/", { waitUntil: "load" }); await p.waitForTimeout(8000);
await p.evaluate(() => { const s = window.__console.getState(); s.setDate("2023-07-22"); s.setUnderstand(true); });
await p.waitForTimeout(5000);
const info = await p.evaluate(() => {
  const cs = [...document.querySelectorAll("canvas")].filter((c) => !c.classList.contains("maplibregl-canvas"));
  return cs.map((c) => {
    const g = c.getContext("2d"); const d = g.getImageData(0, 0, c.width, c.height).data;
    let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i] > 0) n++;
    const r = c.getBoundingClientRect();
    return { w: c.width, h: c.height, cssW: r.width, cssH: r.height, z: getComputedStyle(c).zIndex, painted: n };
  });
});
console.log(JSON.stringify(info));
await b.close();
