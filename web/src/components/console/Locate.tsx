"use client";

/**
 * "Where I am", for a phone. Asks the browser for a location, flies there, and opens the outlook
 * for the place the user actually lives in: their village or gram panchayat, with its own dry-spell
 * number, falling back to the block only when no village outline covers the point. Zooming out
 * afterwards is the normal map gesture: nothing is locked.
 *
 * On a desktop it sits under the top bar on the right, above the map's own controls.
 */
import { useState } from "react";
import { LocateFixed, Loader2 } from "lucide-react";
import { useMap } from "@/lib/mapbus";
import { useConsole } from "@/lib/store";

type Status = "idle" | "locating" | "denied" | "outside";

export default function Locate() {
  const map = useMap();
  const [status, setStatus] = useState<Status>("idle");

  const go = () => {
    if (!map || !navigator.geolocation) return setStatus("denied");
    setStatus("locating");
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        const at: [number, number] = [coords.longitude, coords.latitude];
        map.once("moveend", () => {
          // The village outlines for this view are fetched after the move, so try a few times
          // before settling for the block: a village answer is the one worth waiting a moment for.
          let tries = 0;
          const pick = () => {
            const pt = map.project(at);
            const v = map.getLayer("villages-fill")
              ? map.queryRenderedFeatures(pt, { layers: ["villages-fill"] })[0]
              : undefined;
            const b = map.queryRenderedFeatures(pt, { layers: ["blocks-fill"] })[0];
            if (!v && tries++ < 12) return void setTimeout(pick, 250);
            const i = v ? Number(v.properties?.i) : b?.id !== undefined ? Number(b.id) : NaN;
            if (!Number.isFinite(i)) return setStatus("outside");
            const st = useConsole.getState();
            st.setSelected(i);
            st.setPlace(v ? String(v.properties?.n ?? "") : null);
            const own = v?.properties?.p;
            st.setPlaceChance(typeof own === "number" ? own : null);
            st.setHome({ i, lon: at[0], lat: at[1], name: v ? String(v.properties?.n ?? "") : "" });
            setStatus("idle");
          };
          pick();
        });
        // zoomed past ZOOM_IN in VillageLayer, so the village outlines load for this point
        map.flyTo({ center: at, zoom: 10.2, duration: 900 });
      },
      () => setStatus("denied"),
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 300_000 },
    );
  };

  const note = status === "denied" ? "Location is off. Search your village instead."
    : status === "outside" ? "That looks outside India. Search your village instead."
    : null;

  return (
    <div className="pointer-events-none absolute right-2 top-[124px] z-20 flex flex-col items-end gap-1.5 md:top-[76px] md:right-3">
      {note && (
        <p role="status" className="panel pointer-events-auto max-w-56 px-2.5 py-1.5 text-[11px] leading-snug text-text-2">
          {note}
        </p>
      )}
      <button
        onClick={go}
        aria-label="Show the outlook for where I am"
        title="Show the outlook for my village"
        className="panel pointer-events-auto flex h-11 cursor-pointer items-center gap-2 px-3 text-text-2 transition-colors hover:text-text active:text-text"
      >
        {status === "locating"
          ? <Loader2 size={18} className="animate-spin" />
          : <LocateFixed size={18} />}
        <span className="hidden text-[12px] font-medium md:inline">My village</span>
      </button>
    </div>
  );
}
