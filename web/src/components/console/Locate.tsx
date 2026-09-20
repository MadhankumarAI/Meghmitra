"use client";

/**
 * "Where I am", for a phone. Asks the browser for a location, flies there, and selects the block
 * under that point from the tiles already on screen, so the outlook that opens is the one for the
 * user's own block. Zooming out afterwards is the normal map gesture: nothing is locked.
 *
 * Desktop is untouched: the control only renders below the md breakpoint.
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
          // the block under the point, read from the vector tiles already rendered
          const f = map.queryRenderedFeatures(map.project(at), { layers: ["blocks-fill"] })[0];
          if (f?.id !== undefined) {
            useConsole.getState().setSelected(Number(f.id));
            useConsole.getState().setPlace(null);
            setStatus("idle");
          } else {
            setStatus("outside");
          }
        });
        map.flyTo({ center: at, zoom: 8.5, duration: 900 });
      },
      () => setStatus("denied"),
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 300_000 },
    );
  };

  const note = status === "denied" ? "Location is off. Search your village instead."
    : status === "outside" ? "That looks outside India. Search your village instead."
    : null;

  return (
    <div className="pointer-events-none absolute right-2 top-[124px] z-20 flex flex-col items-end gap-1.5 md:hidden">
      {note && (
        <p role="status" className="panel pointer-events-auto max-w-56 px-2.5 py-1.5 text-[11px] leading-snug text-text-2">
          {note}
        </p>
      )}
      <button
        onClick={go}
        aria-label="Show the outlook for where I am"
        className="panel pointer-events-auto grid h-11 w-11 place-items-center text-text-2 transition-colors active:text-text"
      >
        {status === "locating"
          ? <Loader2 size={18} className="animate-spin" />
          : <LocateFixed size={18} />}
      </button>
    </div>
  );
}
