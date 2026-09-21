"use client";

/**
 * Place names on the map. The vector style carries no font glyphs, so labels are drawn as an
 * HTML overlay from the block index itself: states when zoomed out, districts in between,
 * block names close in. Only what is on screen is labelled, biggest first, and overlapping
 * labels are dropped so the map stays readable.
 */
import { useEffect, useMemo, useState } from "react";
import { useMap } from "@/lib/mapbus";
import type { BlockMeta } from "@/lib/store";

type Place = { key: string; name: string; lon: number; lat: number; weight: number };
type Tier = "state" | "district" | "block";

const ZOOM_DISTRICT = 5.6;      // above this, districts instead of states
const ZOOM_BLOCK = 7.4;         // above this, block names
const MAX_LABELS = { state: 26, district: 44, block: 70 };
// a phone has a fraction of the width and of the GPU: draw what fits, not what exists
const MAX_LABELS_PHONE = { state: 10, district: 12, block: 14 };
const CHAR_PX = 6.2;            // rough half-width per character at our label size

/** One point per place, from the union of its blocks' bounding boxes. */
function places(blocks: BlockMeta[], of: (b: BlockMeta) => string | null): Place[] {
  const acc = new Map<string, { w: number; s: number; e: number; n: number; area: number }>();
  for (const b of blocks) {
    const key = of(b);
    if (!key) continue;
    const [w, s, e, n] = b.bb;
    const a = acc.get(key);
    const area = (e - w) * (n - s);
    if (!a) acc.set(key, { w, s, e, n, area });
    else { a.w = Math.min(a.w, w); a.s = Math.min(a.s, s); a.e = Math.max(a.e, e); a.n = Math.max(a.n, n); a.area += area; }
  }
  return [...acc].map(([name, a]) => ({
    key: name, name, lon: (a.w + a.e) / 2, lat: (a.s + a.n) / 2, weight: a.area,
  }));
}

export default function MapLabels({ blocks }: { blocks: BlockMeta[] | null }) {
  const map = useMap();
  const [shown, setShown] = useState<{ name: string; x: number; y: number; tier: Tier }[]>([]);

  const byTier = useMemo(() => ({
    state: places(blocks ?? [], (b) => b.state || null),
    district: places(blocks ?? [], (b) => b.district || null),
    block: (blocks ?? []).map((b) => ({
      key: b.id, name: b.name, lon: (b.bb[0] + b.bb[2]) / 2, lat: (b.bb[1] + b.bb[3]) / 2,
      weight: (b.bb[2] - b.bb[0]) * (b.bb[3] - b.bb[1]),
    })),
  }), [blocks]);

  useEffect(() => {
    if (!map || !blocks) return;
    let raf = 0;
    const draw = () => {
      const z = map.getZoom();
      const tier: Tier = z >= ZOOM_BLOCK ? "block" : z >= ZOOM_DISTRICT ? "district" : "state";
      const cap = (map.getContainer().clientWidth < 768 ? MAX_LABELS_PHONE : MAX_LABELS)[tier];
      const b = map.getBounds();
      const out: { name: string; x: number; y: number; tier: Tier }[] = [];
      // panels float over the map and are translucent: don't put names underneath them
      const taken: [number, number, number, number][] = [...document.querySelectorAll(".panel")]
        .map((el) => el.getBoundingClientRect())
        .filter((r) => r.width > 0)
        .map((r) => [r.left, r.top, r.right, r.bottom] as [number, number, number, number]);
      const cands = byTier[tier]
        .filter((p) => p.lon >= b.getWest() && p.lon <= b.getEast() && p.lat >= b.getSouth() && p.lat <= b.getNorth())
        .sort((p, q) => q.weight - p.weight);
      for (const p of cands) {
        if (out.length >= cap) break;
        const { x, y } = map.project([p.lon, p.lat]);
        const hw = p.name.length * CHAR_PX * (tier === "state" ? 0.62 : 0.5), hh = tier === "state" ? 11 : 9;
        const box: [number, number, number, number] = [x - hw, y - hh, x + hw, y + hh];
        if (taken.some((t) => box[0] < t[2] && box[2] > t[0] && box[1] < t[3] && box[3] > t[1])) continue;
        taken.push(box);
        out.push({ name: p.name, x, y, tier });
      }
      setShown(out);
    };
    const schedule = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(draw); };
    schedule();
    map.on("move", schedule);
    map.on("zoom", schedule);
    map.on("resize", schedule);
    return () => { cancelAnimationFrame(raf); map.off("move", schedule); map.off("zoom", schedule); map.off("resize", schedule); };
  }, [map, blocks, byTier]);

  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 z-[6] overflow-hidden">
      {shown.map((l) => (
        <span key={`${l.tier}|${l.name}|${Math.round(l.x)}`}
          className={`map-label ${l.tier}`} style={{ left: l.x, top: l.y }}>
          {l.name}
        </span>
      ))}
    </div>
  );
}
