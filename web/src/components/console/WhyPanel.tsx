"use client";

import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { CloudRain, Radar, Sprout, Orbit, Waves, RotateCcw, Info } from "lucide-react";
import { loadExplain, explain, DRIVERS, type ExplainFile, type ExplainEvent, type Driver } from "@/lib/explain";
import type { ForecastFile } from "@/lib/data";

const ICON: Record<Exclude<Driver, "normal">, typeof CloudRain> = {
  recent: CloudRain, around: Radar, progress: Sprout, mjo: Orbit, enso: Waves,
};
const EVENTS: { key: ExplainEvent; label: string; noun: string }[] = [
  { key: "dry10", label: "Dry spell", noun: "10+ day dry spell" },
  { key: "onset", label: "Onset", noun: "monsoon onset" },
  { key: "heavy", label: "Heavy rain", noun: "heavy-rain day" },
];
const SMALL = 0.01;          // under 1 point: grouped as "small effects"
const pts = (x: number) => Math.round(x * 100);
const tenth = (p: number) => `${Math.max(0, Math.min(10, Math.round(p * 10)))} in 10`;

/**
 * "Why this outlook": the block's week-1 forecast built up from its baseline, one driver at a
 * time, using the exact contributions of the model that issued it. Replays on every change.
 */
export default function WhyPanel({ forecast, i, preferred }: { forecast: ForecastFile; i: number; preferred?: ExplainEvent }) {
  const [file, setFile] = useState<{ date: string; f: ExplainFile | null } | null>(null);
  const [picked, setPicked] = useState<ExplainEvent | null>(null);
  const [run, setRun] = useState(0);
  const reduce = useReducedMotion();
  useEffect(() => {
    let live = true;
    loadExplain(forecast.issued).then((f) => { if (live) setFile({ date: forecast.issued, f }); });
    return () => { live = false; };
  }, [forecast.issued]);

  const f = file?.date === forecast.issued ? file.f : undefined;
  const available = EVENTS.filter((e) => forecast.events[e.key].p[0][i] >= 0);
  const ev = picked && available.some((e) => e.key === picked) ? picked
    : preferred && available.some((e) => e.key === preferred) ? preferred : available[0]?.key;
  const x = f && ev ? explain(f, ev, i, forecast.onset_status?.[i]) : null;

  if (f === null) return null;                      // no explanation published for this day
  const noun = EVENTS.find((e) => e.key === ev)?.noun ?? "";
  const bad = ev !== "onset";                        // for onset, a higher chance is good news
  const raise = bad ? "var(--cmri-warning)" : "var(--onset)";
  const lower = bad ? "var(--cmri-normal)" : "var(--dry)";
  const big = x?.steps.filter((s) => Math.abs(s.to - s.from) >= SMALL) ?? [];
  const small = x?.steps.filter((s) => Math.abs(s.to - s.from) < SMALL) ?? [];
  const stagger = reduce ? 0 : 0.18;
  const key = `${i}|${ev}|${forecast.issued}|${run}`;

  return (
    <section aria-label="Why this outlook">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-wide text-text-3">
          Why this outlook
          <span title="Exact contributions from the model that issued this forecast (tree SHAP), grouped into drivers. Added up, they give the forecast.">
            <Info size={12} />
          </span>
        </h3>
        <button onClick={() => setRun((n) => n + 1)}
          className="flex min-h-7 cursor-pointer items-center gap-1 rounded px-1.5 text-[11px] text-text-3 hover:bg-surface-2 hover:text-text">
          <RotateCcw size={12} /> Replay
        </button>
      </div>
      <div className="mb-2 grid rounded-md bg-surface-2 p-0.5" role="tablist" aria-label="Event"
        style={{ gridTemplateColumns: `repeat(${Math.max(1, available.length)}, minmax(0, 1fr))` }}>
        {available.map((e) => (
          <button key={e.key} role="tab" aria-selected={ev === e.key} onClick={() => setPicked(e.key)}
            className={`min-h-7 cursor-pointer whitespace-nowrap rounded px-2 text-[12px] transition-colors ${ev === e.key ? "bg-surface text-text shadow-[0_0_0_1px_var(--line-strong)]" : "text-text-3 hover:text-text"}`}>
            {e.label}
          </button>
        ))}
      </div>

      {f === undefined || !x ? (
        <div className="h-40 animate-pulse rounded-lg bg-surface-2/60" />
      ) : (
        <div key={key} className="rounded-lg border border-line bg-surface-2/35 p-3.5">
          <p className="text-[13px] leading-snug text-text-2">
            Chance of a {noun} in week 1: usually <b className="text-text">{tenth(x.start)}</b> here at this time of year;
            this week <motion.b className="text-text" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              transition={{ delay: stagger * (big.length + 1) }}>{tenth(x.end)}</motion.b>.
          </p>

          {/* the running forecast: from baseline to final, one driver at a time */}
          <div className="relative mb-1 mt-4 h-6">
            <div className="absolute inset-x-0 top-2.5 h-1 rounded-full bg-line" />
            {[0, 0.5, 1].map((t) => (
              <span key={t} className="absolute top-5 -translate-x-1/2 text-[9.5px] text-text-3" style={{ left: `${t * 100}%` }}>{t * 100}%</span>
            ))}
            <span className="absolute top-1.5 h-3 w-3 -translate-x-1/2 rounded-full border-2 border-text-3 bg-(--surface-solid)"
              style={{ left: `${x.start * 100}%` }} title={`Baseline ${pts(x.start)}%`} />
            <motion.span className="absolute top-1 h-4 w-4 -translate-x-1/2 rounded-full shadow-[0_0_0_3px_rgba(0,0,0,0.4)]"
              style={{ background: x.end > x.start ? raise : lower }}
              initial={{ left: `${x.start * 100}%` }}
              animate={{ left: [`${x.start * 100}%`, ...big.map((s) => `${s.to * 100}%`), `${x.end * 100}%`] }}
              transition={{ duration: stagger * (big.length + 1) || 0.01, ease: "easeInOut" }}
              title={`Forecast ${pts(x.end)}%`} />
          </div>

          <ol className="mt-4 space-y-2.5">
            <li className="grid grid-cols-[22px_1fr_44px] items-start gap-2.5">
              <span className="mt-0.5 h-3 w-3 justify-self-center rounded-full border-2 border-text-3" />
              <div className="min-w-0">
                <div className="text-[12.5px] font-medium">Starting point: usual for this block and date</div>
                <div className="text-[11.5px] text-text-3">Its own history for this week, and how early or late the season is</div>
              </div>
              <span className="num text-right text-[12.5px] font-semibold">{pts(x.start)}%</span>
            </li>
            {big.map((s, k) => {
              const Icon = ICON[s.driver];
              const up = s.to > s.from;
              const d = pts(s.to) - pts(s.from);
              return (
                <motion.li key={s.driver} className="grid grid-cols-[22px_1fr_44px] items-start gap-2.5"
                  initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: stagger * (k + 1), duration: 0.3 }}>
                  <span className="mt-0.5 grid h-5.5 w-5.5 place-items-center rounded-md" style={{ background: `color-mix(in srgb, ${up ? raise : lower} 18%, transparent)`, color: up ? raise : lower }}>
                    <Icon size={13} />
                  </span>
                  <div className="min-w-0">
                    <div className="text-[12.5px] font-medium">{DRIVERS[s.driver].label}</div>
                    <div className="text-[11.5px] leading-snug text-text-3">{s.evidence}</div>
                    {/* this driver's move on the 0–100% scale */}
                    <div className="relative mt-1.5 h-1.5 rounded-full bg-line/70">
                      <motion.div className="absolute inset-y-0 rounded-full" style={{ background: up ? raise : lower, left: `${Math.min(s.from, s.to) * 100}%` }}
                        initial={{ width: 0 }} animate={{ width: `${Math.abs(s.to - s.from) * 100}%` }}
                        transition={{ delay: stagger * (k + 1) + 0.1, duration: 0.45, ease: "easeOut" }} />
                    </div>
                  </div>
                  <span className="num text-right text-[12.5px] font-semibold" style={{ color: d === 0 ? "var(--text-3)" : up ? raise : lower }}>
                    {d > 0 ? `+${d}` : d === 0 ? "±0" : `−${-d}`}
                  </span>
                </motion.li>
              );
            })}
            {small.length > 0 && (
              <motion.li className="grid grid-cols-[22px_1fr_44px] items-start gap-2.5 text-[11.5px] text-text-3"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: stagger * (big.length + 1) }}>
                <span />
                <span>Little effect this week: {small.map((s) => DRIVERS[s.driver].short).join(", ")}</span>
                <span className="num text-right">±0</span>
              </motion.li>
            )}
            <motion.li className="grid grid-cols-[22px_1fr_44px] items-center gap-2.5 border-t border-line pt-2.5"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: stagger * (big.length + 1) }}>
              <span className="h-3 w-3 justify-self-center rounded-full" style={{ background: x.end > x.start ? raise : lower }} />
              <span className="text-[12.5px] font-semibold">This week’s forecast</span>
              <span className="num text-right text-[14px] font-semibold">{pts(x.end)}%</span>
            </motion.li>
          </ol>
          <p className="mt-3 text-[10.5px] leading-relaxed text-text-3">
            Exact contributions of the model behind this forecast ({x.model}), largest first. Points are percentage points on the way
            from the starting point to the forecast.
          </p>
        </div>
      )}
    </section>
  );
}
