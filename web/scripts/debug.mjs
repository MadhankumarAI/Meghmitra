import { chromium } from "playwright";
const b = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const p = await b.newPage({ viewport: { width: 1600, height: 900 } });
const logs = [], reqs = [];
p.on("console", (m) => logs.push(`${m.type()}: ${m.text()}`));
p.on("pageerror", (e) => logs.push(`pageerror: ${e.message}`));
p.on("request", (r) => { if (r.url().includes("/data/")) reqs.push(`${r.method()} ${r.url().split("3100")[1]} ${r.headers()["range"] ?? ""}`); });
p.on("response", (r) => { if (r.url().includes("/data/")) reqs.push(`  -> ${r.status()} ${r.url().split("3100")[1]}`); });
await p.goto("http://localhost:3100/", { waitUntil: "load" });
await p.waitForTimeout(8000);
const info = await p.evaluate(() => {
  const c = document.querySelector("canvas.maplibregl-canvas");
  const gl = document.createElement("canvas").getContext("webgl2");
  return { canvas: c ? `${c.width}x${c.height}` : "NO CANVAS", webgl2: !!gl,
           container: document.querySelector(".maplibregl-map") ? "map container ok" : "no map container" };
});
console.log(JSON.stringify(info));
console.log("--- requests:\n" + reqs.slice(0, 14).join("\n"));
console.log("--- console:\n" + logs.filter(l => !l.includes("[HMR]") && !l.includes("React DevTools")).slice(0, 12).join("\n"));
await p.screenshot({ path: process.argv[2] + "/04_debug.png" });
await b.close();
