"use client";

import { useEffect, useRef, useState } from "react";
import {
  Map as MLMap, addProtocol, removeProtocol, setWorkerUrl,
  type StyleSpecification, type ExpressionSpecification,
} from "maplibre-gl";
import { Protocol } from "pmtiles";
import { setMap } from "@/lib/mapbus";
import { useConsole, type EventKey } from "@/lib/store";
import { RAMPS, rampExpression, cmriExpression, onsetFrontExpression } from "@/lib/colors";

const INDIA_BOUNDS: [[number, number], [number, number]] = [[67.5, 6.2], [97.8, 37.2]];
const SRC = "india";

function baseStyle(origin: string): StyleSpecification {
  return {
    version: 8,
    sources: {
      [SRC]: {
        type: "vector",
        url: `pmtiles://${origin}/data/india.pmtiles`,
        attribution: "Boundaries: geoBoundaries (CC BY 4.0) · Rainfall: IMD",
      },
    },
    layers: [
      { id: "ocean", type: "background", paint: { "background-color": "#04070d" } },
      {
        id: "land", type: "fill", source: SRC, "source-layer": "states",
        paint: { "fill-color": "#0c1320" },
      },
      // Two stacked fills for the week crossfade: "base" holds the current values,
      // "fade" receives new values and fades in over it (see the values effect).
      {
        id: "blocks-fill", type: "fill", source: SRC, "source-layer": "blocks",
        paint: { "fill-color": "#0f1726", "fill-opacity": 0.95 },
      },
      {
        id: "blocks-fade", type: "fill", source: SRC, "source-layer": "blocks",
        paint: { "fill-color": "#0f1726", "fill-opacity": 0, "fill-opacity-transition": { duration: 0, delay: 0 } },
      },
      // boundaries recede: hairlines that only firm up as you zoom in
      {
        id: "blocks-line", type: "line", source: SRC, "source-layer": "blocks", minzoom: 6,
        paint: {
          "line-color": "#04070d",
          "line-width": ["interpolate", ["linear"], ["zoom"], 6, 0.2, 10, 0.7],
          "line-opacity": ["interpolate", ["linear"], ["zoom"], 6, 0.15, 9, 0.35],
        },
      },
      {
        id: "districts-line", type: "line", source: SRC, "source-layer": "districts", minzoom: 4.5,
        paint: {
          "line-color": "#04070d",
          "line-width": ["interpolate", ["linear"], ["zoom"], 4.5, 0.3, 8, 1.1],
          "line-opacity": ["interpolate", ["linear"], ["zoom"], 4.5, 0.25, 8, 0.55],
        },
      },
      {
        id: "states-line", type: "line", source: SRC, "source-layer": "states",
        paint: {
          "line-color": "#8ea3c4",
          "line-width": ["interpolate", ["linear"], ["zoom"], 3, 0.5, 8, 1.6],
          "line-opacity": 0.55,
        },
      },
      {
        id: "blocks-hover", type: "line", source: SRC, "source-layer": "blocks",
        paint: {
          "line-color": "#e8eef8",
          "line-width": 1.6,
          "line-opacity": ["case", ["boolean", ["feature-state", "hover"], false], 0.9, 0],
        },
      },
      {
        id: "blocks-selected", type: "line", source: SRC, "source-layer": "blocks",
        paint: {
          "line-color": "#5cc8ff",
          "line-width": 2.6,
          "line-opacity": ["case", ["boolean", ["feature-state", "sel"], false], 1, 0],
        },
      },
    ],
  };
}

function fillFor(event: EventKey, key: "base" | "fade") {
  if (event === "cmri") return cmriExpression(key);
  if (event === "onset") return onsetFrontExpression(key);
  return rampExpression(RAMPS[event], key);
}

const FADE_MS = 420;

export interface MapViewProps {
  /** One value per block index i. For CMRI: class 0..3. Otherwise probability 0..1. */
  values: ArrayLike<number> | null;
  /** Colour expression override (e.g. the Science page skill map); ignores the console event. */
  expr?: (key: "base" | "fade") => ExpressionSpecification;
  /** Right padding when fitting India, for pages with a side column. */
  padRight?: number;
}

export default function MapView({ values, expr, padRight }: MapViewProps) {
  const el = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MLMap | null>(null);
  const loaded = useRef(false);
  const pending = useRef<(() => void) | null>(null);
  // read once when the map first fits; the map itself is created once per mount
  const initialPadRight = useRef(padRight);
  const storeEvent = useConsole((s) => s.event);
  const event: EventKey = expr ? "cmri" : storeEvent;   // a fixed scale when overridden
  const selected = useConsole((s) => s.selected);
  const prevHover = useRef<number | null>(null);
  const prevSel = useRef<number | null>(null);
  // MapLibre 6 needs WebGL2 and has no fallback. Check once (this component only renders
  // in the browser) so everything else keeps working when it's missing.
  const [webgl2] = useState(hasWebGL2);

  // create the map once
  useEffect(() => {
    if (!webgl2) return;
    // see scripts/copy-maplibre-worker.mjs: the bundled worker URL doesn't exist
    setWorkerUrl(`${window.location.origin}/maplibre/maplibre-gl-worker.mjs`);
    const protocol = new Protocol();
    addProtocol("pmtiles", protocol.tile);
    const map = new MLMap({
      container: el.current!,
      style: baseStyle(window.location.origin),
      bounds: INDIA_BOUNDS,
      // generous: a tight box clamps the zoom and stops India fitting beside the panels
      maxBounds: [[40, -16], [125, 50]],
      minZoom: 3,
      maxZoom: 11,
      attributionControl: { compact: true },
      dragRotate: false,
      pitchWithRotate: false,
    });
    map.touchZoomRotate.disableRotation();
    mapRef.current = map;
    if (process.env.NODE_ENV === "development") (window as unknown as { __map: MLMap }).__map = map;

    map.on("error", (e) => console.error("[map]", e.error?.message ?? e));
    map.on("load", () => {
      // constructor fitBoundsOptions is ignored in MapLibre 6: fit once the canvas is real.
      // Leave room for the top bar, time bar and (on wide screens) the side panels.
      const w = map.getContainer().clientWidth;
      const wide = w >= 1100, phone = w < 768;
      map.fitBounds(INDIA_BOUNDS, {
        padding: initialPadRight.current !== undefined
          ? { top: 24, bottom: 24, left: 24, right: initialPadRight.current }
          // a phone stacks the briefing on top and the legend and time bar below
          : phone ? { top: 130, bottom: 230, left: 12, right: 12 }
          : { top: 76, bottom: 104, left: wide ? 290 : 16, right: wide ? 290 : 16 },
        duration: 0,
      });
      loaded.current = true;
      setMap(map);                      // overlays (atmosphere) attach once the style is ready
      pending.current?.();
      pending.current = null;
    });

    map.on("mousemove", "blocks-fill", (e) => {
      const id = e.features?.[0]?.id as number | undefined;
      if (id === undefined || id === prevHover.current) return;
      if (prevHover.current !== null)
        map.setFeatureState({ source: SRC, sourceLayer: "blocks", id: prevHover.current }, { hover: false });
      map.setFeatureState({ source: SRC, sourceLayer: "blocks", id }, { hover: true });
      prevHover.current = id;
      map.getCanvas().style.cursor = "pointer";
      useConsole.getState().setHovered(id);
    });
    map.on("mouseleave", "blocks-fill", () => {
      if (prevHover.current !== null)
        map.setFeatureState({ source: SRC, sourceLayer: "blocks", id: prevHover.current }, { hover: false });
      prevHover.current = null;
      map.getCanvas().style.cursor = "";
      useConsole.getState().setHovered(null);
    });
    map.on("click", "blocks-fill", (e) => {
      const id = e.features?.[0]?.id as number | undefined;
      if (id !== undefined) useConsole.getState().setSelected(id);
    });

    return () => {
      setMap(null);
      map.remove();
      removeProtocol("pmtiles");
      mapRef.current = null;
      loaded.current = false;
    };
  }, [webgl2]);

  // Push values into feature-state (GPU recolour, no tile reload) and crossfade.
  // Changing the week fades the new colours in over the old ones; changing the
  // event (a different colour scale) switches instantly.
  const shownEvent = useRef<EventKey | null>(null);
  const fadeTimer = useRef<number | null>(null);
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !values) return;
    const write = (key: "base" | "fade") => {
      for (let i = 0; i < values.length; i++) {
        const v = values[i];
        map.setFeatureState({ source: SRC, sourceLayer: "blocks", id: i }, { [key]: Number.isFinite(v) ? v : null });
      }
    };
    const apply = () => {
      if (fadeTimer.current) window.clearTimeout(fadeTimer.current);
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const sameScale = shownEvent.current === event;
      map.setPaintProperty("blocks-fill", "fill-color", expr ? expr("base") : fillFor(event, "base"));
      map.setPaintProperty("blocks-fade", "fill-color", expr ? expr("fade") : fillFor(event, "fade"));
      if (!sameScale || reduce) {
        write("base");
        map.setPaintProperty("blocks-fade", "fill-opacity-transition", { duration: 0, delay: 0 });
        map.setPaintProperty("blocks-fade", "fill-opacity", 0);
      } else {
        write("fade");
        map.setPaintProperty("blocks-fade", "fill-opacity-transition", { duration: FADE_MS, delay: 0 });
        map.setPaintProperty("blocks-fade", "fill-opacity", 0.95);
        fadeTimer.current = window.setTimeout(() => {
          // settle: base takes the new values underneath, then drop the fade layer instantly
          write("base");
          map.setPaintProperty("blocks-fade", "fill-opacity-transition", { duration: 0, delay: 0 });
          map.setPaintProperty("blocks-fade", "fill-opacity", 0);
        }, FADE_MS + 40);
      }
      shownEvent.current = event;
    };
    if (loaded.current) apply();
    else pending.current = apply;
  }, [values, event, expr]);

  // fly to a searched block, leaving room for the block panel on the right
  const focus = useConsole((s) => s.focus);
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !focus) return;
    const [w, s, e, n] = focus;
    const wide = map.getContainer().clientWidth >= 1100;
    const phone = map.getContainer().clientWidth < 768;
    map.fitBounds([[w, s], [e, n]], {
      padding: phone
        ? { top: 130, bottom: 430, left: 24, right: 24 }
        : { top: 120, bottom: 140, left: wide ? 320 : 24, right: wide ? 420 : 24 },
      maxZoom: 9.5,
      duration: 1400,
      essential: false,           // skipped under prefers-reduced-motion
    });
    useConsole.getState().setFocus(null);
  }, [focus]);

  // selection outline
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded.current) return;
    if (prevSel.current !== null)
      map.setFeatureState({ source: SRC, sourceLayer: "blocks", id: prevSel.current }, { sel: false });
    if (selected !== null)
      map.setFeatureState({ source: SRC, sourceLayer: "blocks", id: selected }, { sel: true });
    prevSel.current = selected;
  }, [selected]);

  // MapLibre's unlayered CSS sets `position: relative` on its container, which beats
  // Tailwind's layered utilities. Position a wrapper; let the container fill it.
  if (!webgl2) return <NoWebGL2 />;
  return (
    <div className="absolute inset-0">
      <div ref={el} className="h-full w-full" aria-label="Map of India by block" role="application" />
    </div>
  );
}

function hasWebGL2(): boolean {
  try {
    return !!document.createElement("canvas").getContext("webgl2");
  } catch {
    return false;
  }
}

/** Shown instead of MapLibre's raw error; the rest of the console keeps working. */
function NoWebGL2() {
  return (
    <div className="absolute inset-0 grid place-items-center bg-(--ocean) p-6">
      <div role="alert" className="panel max-w-md px-6 py-5 text-[14px] leading-relaxed text-text-2">
        <div className="mb-1.5 text-[16px] font-semibold text-text">The map needs graphics acceleration</div>
        <p>
          This browser isn’t providing WebGL2, so the map can’t be drawn. Search, block outlooks, advisories and
          the farmer page still work.
        </p>
        <ul className="mt-3 list-disc space-y-1 pl-5 text-[13px]">
          <li>Chrome or Edge: Settings → System → turn on <em>Use graphics acceleration when available</em>, then relaunch.</li>
          <li>Open the page in Chrome, Edge or Firefox, not an editor’s built-in preview.</li>
          <li>Check <code className="text-text">chrome://gpu</code> shows <em>WebGL2: Hardware accelerated</em>.</li>
        </ul>
      </div>
    </div>
  );
}
