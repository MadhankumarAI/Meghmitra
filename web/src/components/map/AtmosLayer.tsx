"use client";

/**
 * "Understand" overlay: the atmosphere behind the outlook, drawn on the main map.
 *   moisture   column water vapour as a translucent blue wash (image source)
 *   isobars    sea-level pressure every 2 hPa, hidden over high ground where it's extrapolated
 *   heat       surface air 35-45 °C over land as an amber-to-red glow (the fuel of the heat low)
 *   trough     the line of lowest pressure, dashed: the heat low before the monsoon arrives,
 *              the monsoon trough once it has (colour and label follow the phase)
 *   lows       pulsing L markers with central pressure
 *   wind       850 hPa flow as drifting particles on a canvas, coloured by speed
 */
import { useEffect, useRef, useState } from "react";
import { contours } from "d3-contour";
import { Marker, type GeoJSONSource, type ImageSource, type Map as MLMap } from "maplibre-gl";
import { useMap } from "@/lib/mapbus";
import { useConsole } from "@/lib/store";
import { sample, troughAxis, AXIS, type Frame, type Phase } from "@/lib/atmos";

const IDS = { heat: "atmos-heat", moist: "atmos-moist", iso: "atmos-isobars", trough: "atmos-trough" };
const BEFORE = "states-line";                  // draw weather above block fills, below state lines
const MAX_ELEV = 1500;       // display mask: Himalaya/Tibet, not the Deccan (diagnostics use 600 m)

export default function AtmosLayer({ frame, elev, phase }: { frame: Frame | null; elev: number[] | null; phase: Phase | null }) {
  const map = useMap();
  const layers = useConsole((s) => s.layers);
  const windBy = useConsole((s) => s.windBy);
  const shown = useRef({ layers, windBy });
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => { shown.current = { layers, windBy }; }, [layers, windBy]);   // the loop reads the latest
  const frameRef = useRef<Frame | null>(frame);
  useEffect(() => {
    frameRef.current = frame;                                   // the particle loop reads the latest frame
    const cv = canvas.current;                                  // and old trails must not bleed into it
    cv?.getContext("2d")?.clearRect(0, 0, cv.width, cv.height);
  }, [frame]);

  // static layers: add once, remove on unmount; dim the block colours so weather reads
  useEffect(() => {
    if (!map) return;
    map.addSource(IDS.heat, { type: "image", url: blankPng(), coordinates: [[0, 1], [1, 1], [1, 0], [0, 0]] });
    map.addLayer({ id: IDS.heat, type: "raster", source: IDS.heat,
      paint: { "raster-opacity": 0.8, "raster-fade-duration": 300, "raster-resampling": "linear" } }, BEFORE);
    map.addSource(IDS.moist, { type: "image", url: blankPng(), coordinates: [[0, 1], [1, 1], [1, 0], [0, 0]] });
    map.addLayer({ id: IDS.moist, type: "raster", source: IDS.moist,
      paint: { "raster-opacity": 0.75, "raster-fade-duration": 300 } }, BEFORE);
    map.addSource(IDS.iso, { type: "geojson", data: EMPTY });
    map.addLayer({ id: IDS.iso, type: "line", source: IDS.iso,
      paint: { "line-color": "#e8eef8", "line-opacity": ["case", ["==", ["%", ["get", "hpa"], 4], 0], 0.55, 0.25],
               "line-width": ["case", ["==", ["%", ["get", "hpa"], 4], 0], 1.1, 0.6] } });
    map.addSource(IDS.trough, { type: "geojson", data: EMPTY });
    map.addLayer({ id: IDS.trough, type: "line", source: IDS.trough,
      paint: { "line-color": "#ffd166", "line-width": 2.2, "line-dasharray": [2, 1.5], "line-opacity": 0.9 } });
    const prev = map.getPaintProperty("blocks-fill", "fill-opacity");
    map.setPaintProperty("blocks-fill", "fill-opacity", 0.18);
    return () => {
      for (const id of [IDS.trough, IDS.iso, IDS.moist, IDS.heat]) {
        if (map.getLayer(id)) map.removeLayer(id);
        if (map.getSource(id)) map.removeSource(id);
      }
      map.setPaintProperty("blocks-fill", "fill-opacity", (prev as number) ?? 0.95);
    };
  }, [map]);

  // each field is its own layer, and each can be turned off: they are equal citizens here
  useEffect(() => {
    if (!map) return;
    const vis = (id: string, on: boolean) => {
      if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
    };
    vis(IDS.moist, layers.moist);
    vis(IDS.heat, layers.heat);
    vis(IDS.iso, layers.press);
    vis(IDS.trough, layers.press);
  }, [map, layers]);

  // per-frame data: moisture image, isobars, trough, lows
  useEffect(() => {
    if (!map || !frame) return;
    const { lon0, lat0, d, nx, ny } = frame;
    const w = lon0 - d / 2, e = lon0 + (nx - 0.5) * d, n = lat0 + d / 2, s = lat0 - (ny - 0.5) * d;
    (map.getSource(IDS.moist) as ImageSource | undefined)?.updateImage({
      url: moistPng(frame), coordinates: [[w, n], [e, n], [e, s], [w, s]],
    });
    (map.getSource(IDS.heat) as ImageSource | undefined)?.updateImage({
      url: heatPng(frame, elev), coordinates: [[w, n], [e, n], [e, s], [w, s]],
    });
    (map.getSource(IDS.iso) as GeoJSONSource | undefined)?.setData(isobars(frame, elev));
    const axis = troughAxis(frame, elev);
    (map.getSource(IDS.trough) as GeoJSONSource | undefined)?.setData({
      type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: axis },
    });
    const markers = layers.press
      ? frame.diag.lows.map((l) => new Marker({ element: lowMarker(l.hpa, l.depth) }).setLngLat([l.lon, l.lat]).addTo(map))
      : [];
    // name the dashed line where it is drawn: heat low before the monsoon arrives, trough after
    const kind = phase === "advancing" ? AXIS.heat : AXIS.trough;
    map.setPaintProperty(IDS.trough, "line-color", kind.color);
    if (axis.length > 4 && layers.press) {
      const at = axis[Math.floor(axis.length * 0.3)];
      markers.push(new Marker({ element: axisLabel(kind.label, kind.color), anchor: "bottom", offset: [0, -6] })
        .setLngLat(at).addTo(map));
    }
    return () => markers.forEach((m) => m.remove());
  }, [map, frame, elev, phase, layers.press]);

  // how far the weather layer should step back, by zoom (0 at national view)
  const [scrim, setScrim] = useState(0);
  useEffect(() => {
    if (!map) return;
    const read = () => {
      const z = map.getZoom();
      setScrim(Math.max(0, Math.min(0.5, (z - 5.2) * 0.13)));     // starts at district zoom, caps at 0.5
    };
    read();
    map.on("zoom", read);
    return () => { map.off("zoom", read); };
  }, [map]);

  // wind particles
  useEffect(() => {
    const cv = canvas.current;
    if (!map || !cv) return;
    return runParticles(map, cv, () => frameRef.current, () => shown.current);
  }, [map]);

  // a canvas keeps its intrinsic 300x150 size unless given width and height explicitly
  return (
    <>
      {/* zoomed out the animation is the story; zoomed in it is background, so fade it back */}
      <div aria-hidden className="pointer-events-none absolute inset-0 z-[4] transition-[background-color] duration-300"
        style={{ backgroundColor: `rgba(6, 10, 18, ${scrim.toFixed(2)})` }} />
      <canvas ref={canvas} aria-hidden className="pointer-events-none absolute inset-0 z-[5] h-full w-full"
        style={{ opacity: 1 - scrim * 1.1 }} />
    </>
  );
}

/* ------------------------------------------------------------------ wind particles */

const N_PARTICLES = 3200, MAX_AGE = 90, SPEED = 0.0028;   // deg per (m/s) per animation step
// a phone has a fraction of the pixels and of the GPU, so it draws a fraction of the streaks
const particleCount = (w: number) => (w < 768 ? 900 : w < 1200 ? 2000 : N_PARTICLES);

function runParticles(map: MLMap, cv: HTMLCanvasElement, getFrame: () => Frame | null,
                      getShown: () => { layers: { wind: boolean }; windBy: "speed" | "moisture" }) {
  const ctx = cv.getContext("2d")!;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let W = 0, H = 0, raf = 0;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const resize = () => {
    W = cv.clientWidth; H = cv.clientHeight;
    cv.width = W * dpr; cv.height = H * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  };
  resize();
  const ps = Array.from({ length: particleCount(cv.clientWidth || W) }, () => spawn({ lon: 0, lat: 0, age: 0 }));
  function spawn(p: { lon: number; lat: number; age: number }) {
    const b = map.getBounds();
    p.lon = Math.max(40, Math.min(110, b.getWest() + Math.random() * (b.getEast() - b.getWest())));
    p.lat = Math.max(-15, Math.min(40, b.getSouth() + Math.random() * (b.getNorth() - b.getSouth())));
    p.age = Math.floor(Math.random() * MAX_AGE);
    return p;
  }
  const clear = () => ctx.clearRect(0, 0, W, H);
  map.on("movestart", clear); map.on("resize", resize);

  const step = () => {
    const f = getFrame();
    // fade previous trails
    ctx.globalCompositeOperation = "destination-in";
    ctx.fillStyle = "rgba(0,0,0,0.92)";
    ctx.fillRect(0, 0, W, H);
    ctx.globalCompositeOperation = "lighter";
    const on = getShown();
    if (f && !map.isMoving() && on.layers.wind) {
      const z = map.getZoom();
      ctx.lineWidth = z > 6.5 ? 0.8 : 1.1;
      ctx.globalAlpha = z > 6.5 ? 0.55 : 1;
      for (const p of ps) {
        const u = sample(f, f.u850, p.lon, p.lat), v = sample(f, f.v850, p.lon, p.lat);
        if (u == null || v == null || ++p.age > MAX_AGE) { spawn(p); p.age = 0; continue; }
        const a = map.project([p.lon, p.lat]);
        p.lon += u * SPEED / Math.cos((p.lat * Math.PI) / 180);
        p.lat += v * SPEED;
        const b = map.project([p.lon, p.lat]);
        const spd = Math.hypot(u, v);
        // colour by wind speed, or by how much water the air is actually carrying
        ctx.strokeStyle = on.windBy === "moisture"
          ? moistureColor(sample(f, f.tcwv, p.lon, p.lat))
          : speedColor(spd);
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      }
    }
    ctx.globalAlpha = 1;
    raf = requestAnimationFrame(step);
  };
  if (!reduce) raf = requestAnimationFrame(step);
  return () => { cancelAnimationFrame(raf); map.off("movestart", clear); map.off("resize", resize); clear(); };
}

/** Water in the column at this point: dry air stays faint, monsoon air glows. */
function moistureColor(mm: number | null) {
  if (mm == null) return "rgba(150,170,195,0.25)";
  const t = Math.max(0, Math.min(1, (mm - 25) / 35));            // 25 mm dry .. 60 mm monsoon
  const r = Math.round(120 - 60 * t), g = Math.round(180 + 40 * t), b = 255;
  return `rgba(${r},${g},${b},${(0.25 + 0.6 * t).toFixed(2)})`;
}

function speedColor(s: number) {
  // calm grey-blue -> cyan -> white for the jet core
  if (s < 5) return "rgba(160,190,220,0.35)";
  if (s < 10) return "rgba(120,210,240,0.55)";
  if (s < 15) return "rgba(110,230,255,0.75)";
  return "rgba(235,250,255,0.9)";
}

/* ------------------------------------------------------------------ fields -> map */

const EMPTY = { type: "FeatureCollection" as const, features: [] };
type IsoLine = { type: "Feature"; properties: { hpa: number }; geometry: { type: "LineString"; coordinates: number[][] } };

function isobars(f: Frame, elev: number[] | null) {
  const vals = f.msl.map((v, k) => (v == null || (elev && elev[k] > MAX_ELEV) ? NaN : v));
  const finite = vals.filter(Number.isFinite);
  const lo = Math.ceil(Math.min(...finite) / 2) * 2, hi = Math.floor(Math.max(...finite) / 2) * 2;
  const levels: number[] = [];
  for (let p = lo; p <= hi; p += 2) levels.push(p);
  // Masked cells are filled by diffusing their neighbours' values (a constant fill would draw
  // rings around the mask edge); contour segments entering the mask are dropped below.
  const filled = diffuseFill(vals, f.nx, f.ny);
  const toLL = ([x, y]: number[]) => [f.lon0 + (x - 0.5) * f.d, f.lat0 - (y - 0.5) * f.d];
  // a vertex is masked if it lies on the grid border (where d3-contour closes rings) or
  // any of the four cells around it is masked
  const masked = ([x, y]: number[]) => {
    if (x <= 1 || y <= 1 || x >= f.nx - 1 || y >= f.ny - 1) return true;
    for (const i of [Math.floor(y - 0.5), Math.ceil(y - 0.5)]) for (const j of [Math.floor(x - 0.5), Math.ceil(x - 0.5)]) {
      const ii = Math.min(f.ny - 1, Math.max(0, i)), jj = Math.min(f.nx - 1, Math.max(0, j));
      if (!Number.isFinite(vals[ii * f.nx + jj])) return true;
    }
    return false;
  };
  const features: IsoLine[] = [];
  for (const c of contours().size([f.nx, f.ny]).thresholds(levels)(filled)) {
    for (const poly of c.coordinates) for (const ring of poly) {
      let seg: number[][] = [];
      const flush = () => {
        if (seg.length > 3) features.push({ type: "Feature" as const, properties: { hpa: c.value },
          geometry: { type: "LineString" as const, coordinates: seg.map(toLL) } });
        seg = [];
      };
      for (const pt of ring) { if (masked(pt)) flush(); else seg.push(pt); }
      flush();
    }
  }
  return { type: "FeatureCollection" as const, features };
}

function diffuseFill(vals: number[], nx: number, ny: number) {
  const out = vals.slice();
  for (let iter = 0; iter < 60; iter++) {
    let left = 0;
    const next = out.slice();
    for (let i = 0; i < ny; i++) for (let j = 0; j < nx; j++) {
      const k = i * nx + j;
      if (Number.isFinite(out[k])) continue;
      let s = 0, n = 0;
      for (const [di, dj] of [[-1, 0], [1, 0], [0, -1], [0, 1]]) {
        const a = i + di, b = j + dj;
        if (a < 0 || b < 0 || a >= ny || b >= nx) continue;
        const v = out[a * nx + b];
        if (Number.isFinite(v)) { s += v; n++; }
      }
      if (n) next[k] = s / n; else left++;
    }
    for (let k = 0; k < out.length; k++) out[k] = next[k];
    if (!left) break;
  }
  return out.map((v) => (Number.isFinite(v) ? v : 1013));
}

function moistPng(f: Frame) {
  const c = document.createElement("canvas");
  c.width = f.nx; c.height = f.ny;
  const g = c.getContext("2d")!, img = g.createImageData(f.nx, f.ny);
  for (let k = 0; k < f.tcwv.length; k++) {
    const v = f.tcwv[k];
    if (v == null) continue;
    const t = Math.max(0, Math.min(1, (v - 25) / 45));        // 25 mm dry .. 70 mm saturated
    img.data[4 * k] = 40 + 20 * t; img.data[4 * k + 1] = 110 + 90 * t; img.data[4 * k + 2] = 200 + 55 * t;
    const i = Math.floor(k / f.nx), j = k % f.nx;
    const edge = Math.min(1, Math.min(i, j, f.ny - 1 - i, f.nx - 1 - j) / 8);   // 4-degree feather
    img.data[4 * k + 3] = Math.round(200 * t * t * edge);
  }
  g.putImageData(img, 0, 0);
  return c.toDataURL("image/png");
}

// surface heat over land: nothing below 35 °C, amber at 38, deep red by 45
function heatPng(f: Frame, elev: number[] | null) {
  const c = document.createElement("canvas");
  c.width = f.nx; c.height = f.ny;
  const g = c.getContext("2d")!, img = g.createImageData(f.nx, f.ny);
  for (let k = 0; k < f.t2m.length; k++) {
    const v = f.t2m[k], e = elev?.[k];
    if (v == null || v < 35 || e == null || e <= 5) continue;
    const t = Math.min(1, (v - 35) / 10);
    img.data[4 * k] = 255; img.data[4 * k + 1] = Math.round(170 - 120 * t); img.data[4 * k + 2] = Math.round(60 - 40 * t);
    img.data[4 * k + 3] = Math.round(170 * Math.sqrt(t));
  }
  g.putImageData(img, 0, 0);
  return c.toDataURL("image/png");
}

function axisLabel(text: string, color: string) {
  // MapLibre positions the outer element with `transform`; animate only the inner pill
  const el = document.createElement("div");
  const pill = document.createElement("span");
  pill.className = "atmos-axis";
  pill.style.setProperty("--axis", color);
  pill.textContent = text;
  el.appendChild(pill);
  return el;
}

function blankPng() {
  const c = document.createElement("canvas"); c.width = c.height = 1;
  return c.toDataURL("image/png");
}

function lowMarker(hpa: number, depth: number) {
  const el = document.createElement("div");
  const big = depth >= 15;
  el.className = "atmos-low";
  el.setAttribute("role", "img");
  el.setAttribute("aria-label", `${big ? "Cyclonic storm" : "Low pressure"}, ${Math.round(hpa)} hectopascals`);
  el.innerHTML = `<span class="atmos-low-ring"></span><span class="atmos-low-ring d2"></span>`
    + `<span class="atmos-low-L${big ? " big" : ""}">L</span><span class="atmos-low-hpa">${Math.round(hpa)}</span>`;
  return el;
}
