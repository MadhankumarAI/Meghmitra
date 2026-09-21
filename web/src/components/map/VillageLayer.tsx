"use client";

/**
 * Villages and gram panchayats on the map: real boundaries, not dots.
 *
 * India has 649,309 of them, so the outlines are cut one file per block
 * (src/export/villages_geom.py) and only the blocks actually on screen are fetched, once the map
 * is zoomed inside a block. Each village is filled with the outlook issued for its block, so the
 * map reads at the scale a farmer thinks in while the forecast stays honest about its own scale.
 * Names come from the point index and are drawn as DOM labels, centre of the screen outwards.
 */
import { useEffect, useRef, useState } from "react";
import type { GeoJSONSource } from "maplibre-gl";
import { useMap } from "@/lib/mapbus";
import { useConsole, type BlockMeta } from "@/lib/store";
import { villagesIn, villageShapes, villageAdjust, type Point } from "@/lib/villages";
import { colorForValue, rampColor, RAMPS } from "@/lib/colors";

const ZOOM_IN = 8.6;                 // below this a village is a speck: draw blocks instead
const ZOOM_NAMES = 9.2;              // names start later than the shapes: fewer, and readable
const MAX_BLOCKS = 12;               // more than this on screen and the outlines are pointless
const SRC = "villages";
const NARROW = 0.22;                 // a view this tight in probability gets its own shading band

/** The band to stretch the shading across, or null when the view spans enough of the ramp already.
 *  Ends are the 5th and 95th percentile so one odd village cannot flatten everything else. */
function bandOf(v: number[]): [number, number] | null {
  if (v.length < 12) return null;
  const s = [...v].sort((a, b) => a - b);
  const lo = s[Math.floor(s.length * 0.05)], hi = s[Math.ceil(s.length * 0.95) - 1];
  return hi - lo >= 0.015 && hi - lo < NARROW ? [lo, hi] : null;
}
const CHAR_PX = 5.4;

export default function VillageLayer({ blocks, values, doy }: {
  blocks: BlockMeta[] | null; values: Float32Array | null; doy: number;
}) {
  const map = useMap();
  const event = useConsole((s) => s.event);
  const state = useRef({ values, doy, event });
  useEffect(() => { state.current = { values, doy, event }; }, [values, doy, event]);
  const [shown, setShown] = useState<{ p: Point; x: number; y: number }[]>([]);
  const points = useRef<Point[]>([]);
  const loaded = useRef<Set<number>>(new Set());
  const reload = useRef<() => void>(() => {});
  useEffect(() => { reload.current(); }, [values, doy, event]);

  // the source and its two layers exist from the start and stay empty until there is something
  useEffect(() => {
    if (!map) return;
    if (!map.getSource(SRC)) {
      map.addSource(SRC, { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({
        id: "villages-fill", type: "fill", source: SRC, minzoom: ZOOM_IN,
        paint: {
          // a colour where the village has its own number, invisible (but tappable) otherwise
          "fill-color": ["coalesce", ["get", "col"], "#ffffff"],
          "fill-opacity": ["case", ["has", "col"], 0.95, 0.001],
        },
      }, "blocks-line");
      map.addLayer({
        id: "villages-line", type: "line", source: SRC, minzoom: ZOOM_IN,
        paint: {
          // a hairline that separates one village from the next without drawing a cage over the map
          "line-color": "#ffffff",
          "line-width": ["interpolate", ["linear"], ["zoom"], ZOOM_IN, 0.3, 13, 0.9],
          "line-opacity": ["interpolate", ["linear"], ["zoom"], ZOOM_IN, 0.1, 10.5, 0.26],
        },
      }, "blocks-line");
    }
    return () => {
      for (const id of ["villages-fill", "villages-line"]) if (map.getLayer(id)) map.removeLayer(id);
      if (map.getSource(SRC)) map.removeSource(SRC);
      loaded.current.clear();
      useConsole.getState().setVillageRange(null);
    };
  }, [map]);

  // fetch the outlines of the blocks on screen, and nothing else
  useEffect(() => {
    if (!map) return;
    let raf = 0, live = true;

    const draw = () => {
      if (!live) return;
      const z = map.getZoom();
      if (z < ZOOM_NAMES) { setShown([]); return; }
      const b = map.getBounds();
      // A name for every village is unreadable. Label a handful near the middle of the view and let
      // the shapes carry the rest; zooming in brings more, which is what a map is for.
      const phone = map.getContainer().clientWidth < 768;
      const cap = Math.round((phone ? 5 : 10) * Math.min(2.2, 1 + (z - ZOOM_NAMES) * 0.55));
      const taken: [number, number, number, number][] = [...document.querySelectorAll(".panel, .panel-solid")]
        .map((el) => el.getBoundingClientRect())
        .filter((r) => r.width > 0)
        .map((r) => [r.left, r.top, r.right, r.bottom] as [number, number, number, number]);
      const c = map.getCenter();
      const near = [...points.current].sort(
        (a, z2) => (a.lat - c.lat) ** 2 + (a.lon - c.lng) ** 2 - ((z2.lat - c.lat) ** 2 + (z2.lon - c.lng) ** 2),
      );
      const out: { p: Point; x: number; y: number }[] = [];
      for (const p of near) {
        if (out.length >= cap) break;
        if (p.lon < b.getWest() || p.lon > b.getEast() || p.lat < b.getSouth() || p.lat > b.getNorth()) continue;
        const { x, y } = map.project([p.lon, p.lat]);
        const w = 14 + p.name.length * CHAR_PX;
        const box: [number, number, number, number] = [x - w / 2 - 8, y - 14, x + w / 2 + 8, y + 14];
        if (taken.some((t) => box[0] < t[2] && box[2] > t[0] && box[1] < t[3] && box[3] > t[1])) continue;
        taken.push(box);
        out.push({ p, x, y });
      }
      setShown(out);
    };
    const schedule = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(draw); };

    const load = async () => {
      const src = map.getSource(SRC) as GeoJSONSource | undefined;
      if (map.getZoom() < ZOOM_IN) {
        points.current = [];
        loaded.current.clear();
        src?.setData({ type: "FeatureCollection", features: [] });
        useConsole.getState().setVillageRange(null);
        setShown([]);
        return;
      }
      // which blocks are actually under the viewport right now
      const rendered = map.queryRenderedFeatures({ layers: ["blocks-fill"] });
      const ids = [...new Set(rendered.map((f) => Number(f.id)).filter((n) => Number.isFinite(n)))]
        .slice(0, MAX_BLOCKS);
      const b = map.getBounds();
      points.current = await villagesIn(b.getWest(), b.getSouth(), b.getEast(), b.getNorth());
      const [fc, adjust] = await Promise.all([
        villageShapes(ids),
        villageAdjust(ids, state.current.doy,
                      state.current.event === "heavy" ? "heavy" : "dry10"),
      ]);
      if (!live || !src) return;
      // Every village is painted on the same scale as the map behind it, so a zoomed-in view is a
      // surface made of villages rather than a flat block with a mesh drawn over it. For the dry
      // spell we also hold a number for the village itself, and that is what it gets.
      const vals = state.current.values;
      const ev = state.current.event;
      const num: number[] = [];
      for (const f of fc.features) {
        const i = f.properties.i;
        const raw = vals ? vals[i] : NaN;
        const d = ev === "dry10" || ev === "heavy" ? adjust.get(`${i}:${f.properties.n}`) : undefined;
        const own = d !== undefined && Number.isFinite(raw);
        const v = own ? Math.max(0, Math.min(1, raw + d)) : raw;   // both are already 0..1
        f.properties.v = v;
        f.properties.own = own ? 1 : 0;
        if (ev === "dry10" || ev === "heavy") {
          f.properties.p = Math.round(v * 100);
          if (Number.isFinite(v)) num.push(v);
        } else delete f.properties.p;
      }
      // Inside one block the villages differ by a few points, and a national ramp paints all of
      // them the same colour. Where the whole view sits in a narrow band, spread the same ramp
      // across that band instead, and tell the legend the band, so no colour is unexplained.
      const range = ev === "dry10" || ev === "heavy" ? bandOf(num) : null;
      useConsole.getState().setVillageRange(range ? [Math.round(range[0] * 100), Math.round(range[1] * 100)] : null);
      const top = RAMPS[ev === "heavy" ? "heavy" : "dry10"].at(-1)![0];
      for (const f of fc.features) {
        const v = f.properties.v as number;
        const col = range && Number.isFinite(v)
          ? rampColor(RAMPS[ev === "heavy" ? "heavy" : "dry10"],
                      ((v - range[0]) / (range[1] - range[0])) * top)
          : colorForValue(ev, v);
        if (col) f.properties.col = col;
        else { delete f.properties.col; delete f.properties.p; delete f.properties.own; }
        delete f.properties.v;
      }
      loaded.current = new Set(ids);
      src.setData(fc);
      schedule();
    };

    map.on("move", schedule);
    map.on("moveend", load);
    map.on("zoomend", load);
    reload.current = load;
    load();
    return () => {
      live = false;
      cancelAnimationFrame(raf);
      map.off("move", schedule);
      map.off("moveend", load);
      map.off("zoomend", load);
    };
  }, [map]);

  // click a village: open the block that forecasts it, with the village named
  useEffect(() => {
    if (!map) return;
    const onClick = (e: { features?: { properties?: Record<string, unknown> }[] }) => {
      const f = e.features?.[0];
      if (!f?.properties) return;
      const i = Number(f.properties.i);
      const s = useConsole.getState();
      s.setSelected(i);
      s.setPlace(String(f.properties.n ?? ""));
      const own = f.properties.p;
      s.setPlaceChance(typeof own === "number" ? own : null);
      if (blocks?.[i]) s.setFocus(blocks[i].bb);
    };
    map.on("click", "villages-fill", onClick);
    return () => { map.off("click", "villages-fill", onClick); };
  }, [map, blocks]);

  if (!shown.length) return null;
  return (
    <div className="pointer-events-none absolute inset-0 z-[5]">
      {shown.map(({ p, x, y }) => (
        <span key={`${p.name}:${p.lat}:${p.lon}`} className="village-mark" style={{ left: x, top: y }}>
          <span className="village-name">{p.name}</span>
        </span>
      ))}
    </div>
  );
}
