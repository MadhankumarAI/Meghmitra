import { chromium } from "playwright";
const b = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const p = await b.newPage({ viewport: { width: 1600, height: 900 } });
const logs = [];
p.on("console", (m) => logs.push(`${m.type()}: ${m.text()}`));
await p.goto("http://localhost:3100/", { waitUntil: "load" });
await p.waitForTimeout(9000);
const s = await p.evaluate(async () => {
  const m = window.__map;
  if (!m) return "no __map";
  const src = m.getSource("india");
  return {
    zoom: m.getZoom().toFixed(2), center: m.getCenter().toArray().map(v => v.toFixed(2)),
    loaded: m.loaded(), styleLoaded: m.isStyleLoaded(), sourceLoaded: m.isSourceLoaded("india"),
    srcMin: src?.minzoom, srcMax: src?.maxzoom, bounds: src?.bounds, tilesTpl: src?.tiles,
    states: m.querySourceFeatures("india", { sourceLayer: "states" }).length,
    blocks: m.querySourceFeatures("india", { sourceLayer: "blocks" }).length,
  };
});
console.log(JSON.stringify(s, null, 1));
console.log(logs.filter(l => !/HMR|DevTools|Fast Refresh/.test(l)).slice(0, 10).join("\n"));
await b.close();
