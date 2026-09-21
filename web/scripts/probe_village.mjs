import { chromium } from "playwright";
const b = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const p = await b.newPage({ viewport: { width: 1600, height: 900 } });
p.on("pageerror", (e) => console.log("pageerror", e.message));
await p.goto("http://localhost:3100/", { waitUntil: "load" });
await p.waitForTimeout(8000);
await p.evaluate(() => { const s = window.__console.getState(); s.setDate("2023-07-20"); s.setEvent("dry10"); s.setFocus([76.0, 15.30, 76.15, 15.40]); });
await p.waitForTimeout(8000);
await p.mouse.click(800, 430);
await p.waitForTimeout(2000);
const out = await p.evaluate(() => {
  const m = window.__map;
  const has = !!m;
  const layers = has ? m.getStyle().layers.map((l) => l.id).filter((i) => i.startsWith("villages")) : [];
  const q = has ? m.queryRenderedFeatures([800, 430], { layers: ["villages-fill"] }) : [];
  const st = window.__console.getState();
  return { has, layers, zoom: has ? m.getZoom().toFixed(2) : null,
           hit: q.length, props: q[0]?.properties ?? null,
           place: st.place, placeChance: st.placeChance, selected: st.selected };
});
console.log(JSON.stringify(out));
await b.close();
