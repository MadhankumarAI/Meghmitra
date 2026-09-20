// MapLibre 6 loads its tile worker from a URL relative to its own module. Once
// bundled, that URL no longer exists and tiles silently never load. Serve the
// worker (and the shared chunk it imports) as static files from the installed
// version, and point MapLibre at them with setWorkerUrl().
import { copyFileSync, mkdirSync } from "node:fs";
const src = "node_modules/maplibre-gl/dist";
const dst = "public/maplibre";
mkdirSync(dst, { recursive: true });
for (const f of ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"]) copyFileSync(`${src}/${f}`, `${dst}/${f}`);
console.log("maplibre worker copied to", dst);
