import { chromium } from "playwright";
const out = process.argv[2];
for (const [name, args] of [["nogl", ["--disable-webgl2", "--disable-3d-apis"]],
                            ["gl", ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]]]) {
  const b = await chromium.launch({ args });
  const p = await b.newPage({ viewport: { width: 1440, height: 850 } });
  const errs = []; p.on("pageerror", (e) => errs.push(e.message));
  await p.goto("http://localhost:3100/", { waitUntil: "load" }); await p.waitForTimeout(7000);
  const hasCanvas = await p.evaluate(() => !!document.querySelector("canvas.maplibregl-canvas"));
  const notice = await p.getByText("The map needs graphics acceleration").count();
  await p.screenshot({ path: `${out}/${name}.png` });
  console.log(name, "| map canvas:", hasCanvas, "| notice:", notice > 0, "| errors:", errs.join("; ") || "none");
  await b.close();
}
