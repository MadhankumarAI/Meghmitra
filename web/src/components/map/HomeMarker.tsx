"use client";

/**
 * "Your place", kept marked. Once a farmer has located themselves or looked up their village, the
 * point stays on the map at every zoom, with their block outlined in the same amber (the
 * blocks-home layer in MapView). Zooming out to see the rest of the country never loses it.
 */
import { useEffect } from "react";
import { Marker } from "maplibre-gl";
import { useMap } from "@/lib/mapbus";
import { useConsole, type BlockMeta } from "@/lib/store";

export default function HomeMarker({ blocks }: { blocks: BlockMeta[] | null }) {
  const map = useMap();
  const home = useConsole((s) => s.home);

  useEffect(() => {
    if (!map || !home) return;
    const name = home.name || "Your place";        // a village name if they searched one, else this
    const el = document.createElement("div");
    el.className = "home-mark";
    el.innerHTML = `<span class="home-dot"></span><span class="home-name">${name}</span>`;
    el.setAttribute("aria-label", `Your place: ${name}`);
    const m = new Marker({ element: el, anchor: "left", offset: [6, 0] })
      .setLngLat([home.lon, home.lat])
      .addTo(map);
    el.addEventListener("click", () => {
      const s = useConsole.getState();
      s.setSelected(home.i);
      if (blocks?.[home.i]) s.setFocus(blocks[home.i].bb);
    });
    return () => { m.remove(); };
  }, [map, home, blocks]);

  return null;
}
