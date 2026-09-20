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

  return (
    <aside aria-label="Legend" className="panel pointer-events-auto absolute bottom-33 left-3 z-10 w-72 px-4 py-3">
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
              <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 border-t border-line pt-2">
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
              <div className="mb-2 text-[12px] font-semibold">{TITLE[event]}</div>
              <div className="h-2.5 w-full rounded-sm"
                style={{
                  background: `linear-gradient(90deg, ${RAMPS[event]
                    .map(([v, c]) => `${c} ${(v / RAMPS[event].at(-1)![0]) * 100}%`)
                    .join(",")})`,
                }} />
              <div className="num mt-1 flex justify-between text-[10px] text-text-3">
                <span>0%</span>
                <span>{Math.round(RAMPS[event].at(-1)![0] * 50)}%</span>
                <span>{Math.round(RAMPS[event].at(-1)![0] * 100)}%+</span>
              </div>
            </>
          )}
        </motion.div>
      </AnimatePresence>
    </aside>
  );
}
