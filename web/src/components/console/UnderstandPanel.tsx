"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Wind, Waves, Droplets, TrendingDown, Flame, X, ChevronDown } from "lucide-react";
import { AXIS, type Frame, type Heat, type narrate } from "@/lib/atmos";
import LayerRows from "./LayerRows";
import { useConsole } from "@/lib/store";

const PHASE = {
  active: { color: "#4b90e2", label: "ACTIVE" },
  break: { color: "#d98324", label: "BREAK" },
  normal: { color: "#43a877", label: "NORMAL" },
  advancing: { color: "#35b89a", label: "ONSET PHASE" },
  withdrawing: { color: "#98a2b5", label: "WITHDRAWAL" },
} as const;

/**
 * Plain-language reading of the atmosphere on screen. It sits over a moving map, so it is
 * opaque rather than glassy, kept narrow, and only as tall as its text: the map is the subject,
 * this is the caption. The map key is one tap away instead of filling the panel.
 */
export default function UnderstandPanel({ frame, loading, reading: n, heat }: {
  frame: Frame | null; loading: boolean; reading: ReturnType<typeof narrate> | null; heat: Heat | null;
}) {
  const setUnderstand = useConsole((s) => s.setUnderstand);
  const windBy = useConsole((s) => s.windBy);
  const [keyOpen, setKeyOpen] = useState(false);
  const axis = n?.phase === "advancing" ? AXIS.heat : AXIS.trough;
  const when = frame ? new Date(frame.t).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Kolkata" }) : "";

  return (
    <motion.aside
      aria-label="Why the monsoon is behaving this way"
      initial={{ opacity: 0, x: -14 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -10 }}
      transition={{ type: "spring", stiffness: 380, damping: 34 }}
      className="panel-solid absolute inset-x-0 bottom-[178px] top-auto z-20 flex max-h-[56%] w-auto flex-col overflow-hidden rounded-t-xl
        md:inset-x-auto md:left-3 md:top-[72px] md:bottom-auto md:max-h-[calc(100%-180px)] md:w-80 md:rounded-none"
    >
      <header className="px-4 pb-2.5 pt-3">
        <div className="flex items-center gap-2">
          {n && (
            <span className="shrink-0 whitespace-nowrap rounded px-1.5 py-0.5 text-[10px] font-bold tracking-wide text-[#08101c]"
              style={{ background: PHASE[n.phase].color }}>
              {PHASE[n.phase].label}
            </span>
          )}
          <span className="num min-w-0 flex-1 truncate text-[10.5px] text-(--ink-3)">
            {frame ? `${frame.source} · ${when}` : "Loading…"}
          </span>
          <button aria-label="Close explanation" onClick={() => setUnderstand(false)}
            className="-mr-1 grid h-6 w-6 shrink-0 cursor-pointer place-items-center rounded text-(--ink-3) transition-colors hover:bg-white/10 hover:text-(--ink)">
            <X size={15} />
          </button>
        </div>
        <h2 className="mt-1.5 text-[15.5px] font-semibold leading-tight text-(--ink)">
          {n?.title ?? "What the atmosphere is doing"}
        </h2>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-3">
        {!frame && !loading && <p className="text-[13px] text-(--ink-3)">No atmosphere data for this date.</p>}
        {n && (
          <ul className="space-y-2">
            {n.points.map((p) => (
              <li key={p} className="border-l-2 border-white/10 pl-2.5 text-[12.5px] leading-[1.55] text-(--ink-2)">{p}</li>
            ))}
          </ul>
        )}
        {frame && (
          <div className="mt-3 border-t border-white/10 pt-2">
            <p className="mb-1 px-1.5 text-[10px] font-medium uppercase tracking-wider text-(--ink-3)">Four fields on the map</p>
            <LayerRows frame={frame} heat={heat} />
          </div>
        )}
      </div>

      {/* the key is reference, not reading: collapsed until asked for */}
      <div className="border-t border-white/10">
        <button onClick={() => setKeyOpen(!keyOpen)} aria-expanded={keyOpen}
          className="flex w-full cursor-pointer items-center justify-between px-4 py-2.5 text-left text-[11.5px] font-medium text-(--ink-2) transition-colors hover:text-(--ink)">
          What you’re seeing on the map
          <ChevronDown size={14} className={`transition-transform ${keyOpen ? "rotate-180" : ""}`} />
        </button>
        <AnimatePresence initial={false}>
          {keyOpen && (
            <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }} className="overflow-hidden">
              <div className="space-y-0.5 px-4 pb-3">
                <Key icon={<Wind size={14} />} label="Moving streaks"
                  note={windBy === "moisture" ? "wind at 1.5 km; the brighter the streak, the more water that air carries"
                    : "wind at 1.5 km; brightest is the monsoon jet"} />
                <Key icon={<Waves size={14} />} label="Thin lines" note="sea-level pressure, every 2 hPa" />
                <Key icon={<TrendingDown size={14} style={{ color: axis.color }} />}
                  label={n?.phase === "advancing" ? "Orange dashes" : "Yellow dashes"}
                  note={n?.phase === "advancing" ? "heat low, before the monsoon trough forms" : "monsoon trough axis"} />
                <Key icon={<span className="text-[12px] font-extrabold text-[#ff7b7b]">L</span>} label="Pulsing L" note="low, depression or cyclone" />
                <Key icon={<Droplets size={14} className="text-[#7cbcff]" />} label="Blue wash" note="water vapour in the air column" />
                <Key icon={<Flame size={14} className="text-[#ff8a5c]" />} label="Amber glow" note="surface heat over land, 35 °C and above" />
                <p className="pt-2 text-[10.5px] leading-relaxed text-(--ink-3)">
                  Weather context from reanalysis and forecast data. The risk model itself learns from rainfall and the
                  MJO/ENSO indices; it does not use these fields.
                </p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.aside>
  );
}

function Key({ icon, label, note }: { icon: React.ReactNode; label: string; note: string }) {
  return (
    <div className="flex items-start gap-2 py-0.5">
      <span className="mt-0.5 grid w-4 shrink-0 place-items-center text-(--ink-2)">{icon}</span>
      <span className="text-[11.5px] leading-snug">
        <span className="font-medium text-(--ink)">{label}</span>
        <span className="text-(--ink-3)"> · {note}</span>
      </span>
    </div>
  );
}
