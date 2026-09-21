"use client";

import { AnimatePresence, motion } from "motion/react";
import { useConsole } from "@/lib/store";
import { CMRI, REGIMES, RAMPS, ONSET_FRONT } from "@/lib/colors";

const TITLE = {
  dry10: "Chance of a 10+ day dry spell",
  heavy: "Chance of a heavy-rain day (≥ 64.5 mm)",
} as const;

/** Compact key under the briefing; the full meaning of each class is in its tooltip. */
export default function Legend() {
  const event = useConsole((s) => s.event);
  const band = useConsole((s) => s.villageRange);

  return (
    <aside aria-label="Legend" className="panel pointer-events-auto absolute bottom-[190px] left-2 right-2 z-10 w-auto px-3 py-2
      md:bottom-33 md:left-3 md:right-auto md:w-72 md:px-4 md:py-3">
      <AnimatePresence mode="wait" initial={false}>
        <motion.div key={event} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.15 }}>
          {event === "cmri" ? (
            <>
              <div className="mb-2 flex items-baseline justify-between">
                <span className="text-[12px] font-semibold">Combined Monsoon Risk</span>
                <span className="text-[10.5px] text-text-3">IMD colours</span>
              </div>
              <ul className="grid grid-cols-4 gap-1">
                {CMRI.map((c) => (
                  <li key={c.key} title={c.note}>
                    <span className="block h-2 rounded-sm" style={{ background: c.color }} />
                    <span className="mt-1 block text-[11px] font-medium">{c.label}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-2 hidden flex-wrap gap-x-3 gap-y-1 border-t border-line pt-2 md:flex">
                {([-1, -2] as const).map((k) => (
                  <span key={k} className="flex items-center gap-1.5 text-[10.5px] text-text-3" title={REGIMES[k].detail}>
                    <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: REGIMES[k].color }} />
                    {REGIMES[k].label.replace(" regime", "")}
                  </span>
                ))}
              </div>
            </>
          ) : event === "onset" ? (
            <>
              <div className="mb-2 text-[12px] font-semibold">Onset front <span className="font-normal text-text-3">· when the true onset is expected</span></div>
              <ul className="grid grid-cols-2 gap-x-3 gap-y-1">
                {ONSET_FRONT.map((c) => (
                  <li key={c.code} className="flex items-center gap-2 text-[11px]" title={c.note}>
                    <span className="h-2.5 w-4 shrink-0 rounded-sm" style={{ background: c.color }} />
                    <span className="truncate">{c.label}</span>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <>
              <div className="mb-2 text-[12px] font-semibold">
                {TITLE[event]}
                {band && <span className="font-normal text-text-3"> · village by village</span>}
              </div>
              <div className="h-2.5 w-full rounded-sm"
                style={{
                  background: `linear-gradient(90deg, ${RAMPS[event]
                    .map(([v, c]) => `${c} ${(v / RAMPS[event].at(-1)![0]) * 100}%`)
                    .join(",")})`,
                }} />
              {band ? (
                <>
                  <div className="num mt-1 flex justify-between text-[10px] text-text-3">
                    <span>{band[0]}%</span>
                    <span>{band[1]}%</span>
                  </div>
                  <p className="mt-1.5 text-[10.5px] leading-snug text-text-3">
                    Zoomed in, the whole view sits between {band[0]}% and {band[1]}%, so the scale is
                    stretched across that band to show how villages differ inside a block.
                  </p>
                </>
              ) : (
                <div className="num mt-1 flex justify-between text-[10px] text-text-3">
                  <span>0%</span>
                  <span>{Math.round(RAMPS[event].at(-1)![0] * 50)}%</span>
                  <span>{Math.round(RAMPS[event].at(-1)![0] * 100)}%+</span>
                </div>
              )}
            </>
          )}
        </motion.div>
      </AnimatePresence>
    </aside>
  );
}
