"use client";

/**
 * The four fields on the map, each with the number it is drawn from and a small animation
 * whose speed or brightness is that same number — not decoration bolted on. Tapping a row
 * turns that field off on the map, so any one of them can be looked at on its own.
 */
import { motion } from "motion/react";
import { Wind, Droplets, Flame, TrendingDown } from "lucide-react";
import type { Frame, Heat } from "@/lib/atmos";
import { useConsole } from "@/lib/store";

type Key = "wind" | "moist" | "heat" | "press";
const clamp01 = (x: number) => Math.max(0, Math.min(1, x));

export default function LayerRows({ frame, heat }: { frame: Frame | null; heat: Heat | null }) {
  const layers = useConsole((s) => s.layers);
  const toggle = useConsole((s) => s.toggleLayer);
  const windBy = useConsole((s) => s.windBy);
  const setWindBy = useConsole((s) => s.setWindBy);
  if (!frame) return null;
  const d = frame.diag;
  const low = d.lows.length ? d.lows.reduce((a, b) => (b.hpa < a.hpa ? b : a)) : null;

  // 0-1 strength of each field, from the frame's own diagnostics
  const s = {
    wind: clamp01(d.jet_ms / 22),                        // 22 m/s is a very strong jet
    moist: clamp01((d.tcwv_central_mm - 20) / 40),       // 20 mm dry .. 60 mm monsoon air
    heat: heat ? clamp01((heat.max - 32) / 14) : 0,      // 32 .. 46 °C
    press: low ? clamp01(low.depth / 12) : clamp01(Math.abs(d.nw_minus_bay_hpa) / 10),
  };

  const rows: { k: Key; icon: React.ReactNode; label: string; value: string; note: string }[] = [
    { k: "wind", icon: <Wind size={13} />, label: "Wind at 1.5 km",
      value: `${d.jet_ms.toFixed(0)} m/s`, note: "monsoon jet, Arabian Sea" },
    { k: "moist", icon: <Droplets size={13} />, label: "Moisture in the air",
      value: `${d.tcwv_central_mm.toFixed(0)} mm`, note: "column water, central India" },
    { k: "heat", icon: <Flame size={13} />, label: "Surface heat",
      value: heat ? `${heat.max.toFixed(0)} °C` : "—",
      note: heat ? `hottest plains point${heat.cells40 ? `, ${heat.cells40} cells 40 °C+` : ""}` : "no land data" },
    { k: "press", icon: <TrendingDown size={13} />, label: "Pressure",
      value: low ? `${low.hpa.toFixed(0)} hPa` : `${d.nw_minus_bay_hpa >= 0 ? "+" : ""}${d.nw_minus_bay_hpa.toFixed(1)} hPa`,
      note: low ? `deepest of ${d.lows.length} low${d.lows.length > 1 ? "s" : ""}` : "north-west minus Bay" },
  ];

  return (
    <div className="space-y-0.5">
      {rows.map((r) => {
        const on = layers[r.k];
        return (
          <button key={r.k} onClick={() => toggle(r.k)} aria-pressed={on}
            className={`flex w-full cursor-pointer items-center gap-2 rounded px-1.5 py-1.5 text-left transition-colors hover:bg-white/[0.06] ${on ? "" : "opacity-40"}`}>
            <span className="shrink-0 text-(--ink-3)">{r.icon}</span>
            <span className="min-w-0 flex-1">
              <span className="block text-[11.5px] font-medium leading-tight text-(--ink)">{r.label}</span>
              <span className="block truncate text-[10px] leading-tight text-(--ink-3)">{r.note}</span>
            </span>
            <Pulse kind={r.k} strength={s[r.k]} on={on} />
            <span className="num w-[52px] shrink-0 text-right text-[11.5px] tabular-nums text-(--ink-2)">{r.value}</span>
          </button>
        );
      })}

      {/* the streaks can be coloured by what the air carries instead of how fast it moves */}
      <div className={`mt-1.5 flex items-center gap-1.5 border-t border-white/10 pt-2 ${layers.wind ? "" : "opacity-40"}`}>
        <span className="text-[10.5px] text-(--ink-3)">Colour streaks by</span>
        {(["speed", "moisture"] as const).map((w) => (
          <button key={w} onClick={() => setWindBy(w)} disabled={!layers.wind} aria-pressed={windBy === w}
            className={`cursor-pointer rounded px-1.5 py-0.5 text-[10.5px] transition-colors ${
              windBy === w ? "bg-white/15 font-medium text-(--ink)" : "text-(--ink-3) hover:text-(--ink-2)"}`}>
            {w}
          </button>
        ))}
      </div>
    </div>
  );
}

/** 30x16 of motion whose rate or brightness is the field's own value. */
function Pulse({ kind, strength, on }: { kind: Key; strength: number; on: boolean }) {
  const t = Math.max(0.05, strength);
  if (!on) return <span className="h-4 w-[30px] shrink-0" />;
  if (kind === "wind") {
    // streaks cross in the time the real jet would take to cross the same box
    const dur = 2.6 - 1.9 * t;
    return (
      <svg width={30} height={16} className="shrink-0" aria-hidden>
        {[3, 8, 13].map((y, i) => (
          <motion.line key={y} x1={-8} x2={0} y1={y} y2={y} stroke="#8ec5ff" strokeWidth={1.2}
            strokeOpacity={0.35 + 0.5 * t} strokeLinecap="round"
            animate={{ x: [0, 38] }}
            transition={{ duration: dur, repeat: Infinity, ease: "linear", delay: (i * dur) / 3 }} />
        ))}
      </svg>
    );
  }
  if (kind === "moist") {
    // more water in the column, more drops and the brighter they fall
    return (
      <svg width={30} height={16} className="shrink-0" aria-hidden>
        {[6, 15, 24].map((x, i) => (
          <motion.circle key={x} cx={x} r={1.5} fill="#7cbcff" fillOpacity={0.3 + 0.6 * t}
            initial={{ cy: 1, opacity: 0 }} animate={{ cy: [1, 15], opacity: [0, 1, 0] }}
            transition={{ duration: 1.9 - 0.7 * t, repeat: Infinity, ease: "easeIn", delay: i * 0.45 }} />
        ))}
      </svg>
    );
  }
  if (kind === "heat") {
    return (
      <svg width={30} height={16} className="shrink-0" aria-hidden>
        <motion.circle cx={15} cy={8} fill="#ff8a5c"
          initial={{ r: 4, opacity: 0.2 + 0.4 * t }} animate={{ opacity: [0.2 + 0.4 * t, 0.35 + 0.6 * t, 0.2 + 0.4 * t], r: [4, 6.5, 4] }}
          transition={{ duration: 2.6 - 1.3 * t, repeat: Infinity, ease: "easeInOut" }} />
      </svg>
    );
  }
  // pressure: rings converging on the low, faster the deeper it is
  return (
    <svg width={30} height={16} className="shrink-0" aria-hidden>
      {[0, 1].map((i) => (
        <motion.circle key={i} cx={15} cy={8} fill="none" stroke="#ff9f9f" strokeWidth={1}
          initial={{ r: 7.5, opacity: 0 }} animate={{ r: [7.5, 1.5], opacity: [0, 0.2 + 0.6 * t, 0] }}
          transition={{ duration: 2.8 - 1.4 * t, repeat: Infinity, ease: "linear", delay: i * (1.4 - 0.7 * t) }} />
      ))}
    </svg>
  );
}
