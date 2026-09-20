"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { animate, AnimatePresence, motion } from "motion/react";
import { ChevronDown, MapPin, ArrowUpRight } from "lucide-react";
import { useConsole, type BlockMeta } from "@/lib/store";
import type { ForecastFile } from "@/lib/data";
import { loadAdvisory, type AdvisoryFile } from "@/lib/advisory";

/** A number that eases to its new value instead of jumping (the time bar changes it daily). */
function Count({ value }: { value: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const prev = useRef(value);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const c = animate(prev.current, value, { duration: 0.6, ease: "easeOut", onUpdate: (v) => { el.textContent = Math.round(v).toLocaleString("en-IN"); } });
    prev.current = value;
    return () => c.stop();
  }, [value]);
  return <span ref={ref} className="num">{value.toLocaleString("en-IN")}</span>;
}

const union = (bbs: BlockMeta["bb"][]): BlockMeta["bb"] => [
  Math.min(...bbs.map((b) => b[0])), Math.min(...bbs.map((b) => b[1])),
  Math.max(...bbs.map((b) => b[2])), Math.max(...bbs.map((b) => b[3])),
];

/**
 * What an officer needs first: how much of India is at Warning or Alert this week, how many
 * blocks have crop advice waiting, where it concentrates, and which blocks are most urgent.
 */
export default function Briefing({ forecast, blocks }: { forecast: ForecastFile; blocks: BlockMeta[] }) {
  const [open, setOpen] = useState(true);
  const [adv, setAdv] = useState<{ date: string; f: AdvisoryFile | null } | null>(null);
  const setSelected = useConsole((s) => s.setSelected);
  const setFocus = useConsole((s) => s.setFocus);
  useEffect(() => {
    let live = true;
    loadAdvisory(forecast.issued).then((f) => { if (live) setAdv({ date: forecast.issued, f }); });
    return () => { live = false; };
  }, [forecast.issued]);
  const advice = adv?.date === forecast.issued ? adv.f : undefined;

  const s = useMemo(() => {
    const w1 = forecast.cmri[0];
    let alert = 0, warning = 0, monsoon = 0;
    const byState = new Map<string, { n: number; risk: number; bbs: BlockMeta["bb"][] }>();
    w1.forEach((c, i) => {
      if (c < 0) return;                                       // winter / NE-monsoon regimes
      monsoon++;
      if (c === 3) alert++; else if (c === 2) warning++;
      const st = blocks[i]?.state ?? "";
      const r = byState.get(st) ?? { n: 0, risk: 0, bbs: [] };
      r.n++;
      if (c >= 2) { r.risk++; r.bbs.push(blocks[i].bb); }
      byState.set(st, r);
    });
    const states = [...byState.entries()].filter(([, r]) => r.risk > 0)
      .sort((a, b) => b[1].risk - a[1].risk).slice(0, 3);
    // most urgent: Alert blocks, highest dry-spell (or heavy-rain) chance above normal first
    const ev = forecast.events;
    const urgency = (i: number) => Math.max(ev.dry10.p[0][i] - ev.dry10.clim[0][i], ev.heavy.p[0][i] - ev.heavy.clim[0][i]);
    const urgent = w1.map((c, i) => [c, i] as const).filter(([c]) => c === 3)
      .map(([, i]) => i).sort((a, b) => urgency(b) - urgency(a)).slice(0, 3);
    return { alert, warning, monsoon, states, urgent };
  }, [forecast, blocks]);
  const withAdvice = advice ? Object.keys(advice.advisories).length : null;
  const nAdvice = advice ? Object.values(advice.advisories).reduce((n, r) => n + r.length, 0) : null;

  const d0 = new Date(forecast.issued + "T00:00:00"), d1 = new Date(d0); d1.setDate(d0.getDate() + 6);
  const range = `${d0.toLocaleDateString("en-IN", { day: "numeric", month: "short" })} – ${d1.toLocaleDateString("en-IN", { day: "numeric", month: "short" })}`;

  return (
    <motion.aside aria-label="Today's briefing" initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -12 }} className="panel pointer-events-auto absolute left-3 top-[72px] z-10 w-72 overflow-hidden">
      <button onClick={() => setOpen(!open)} aria-expanded={open}
        className="flex w-full cursor-pointer items-center justify-between px-4 py-3 text-left">
        <span>
          <span className="block text-[12.5px] font-semibold">{forecast.source === "live" ? "Today’s briefing" : "Briefing for this day"}</span>
          <span className="block text-[11px] text-text-3">Week 1 · {range}</span>
        </span>
        <ChevronDown size={16} className={`text-text-3 transition-transform ${open ? "" : "-rotate-90"}`} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22 }} className="overflow-hidden">
            <div className="px-4 pb-4">
              <div className="grid grid-cols-3 gap-1.5">
                <Tile label="Alert" tone="var(--cmri-alert)" value={s.alert} />
                <Tile label="Warning" tone="var(--cmri-warning)" value={s.warning} />
                <Tile label="Advice" tone="var(--focus)" value={withAdvice} />
              </div>
              <p className="mt-2 text-[11px] leading-snug text-text-3">
                Blocks, of {s.monsoon.toLocaleString("en-IN")} in the monsoon regime
                {nAdvice !== null && <> · {nAdvice.toLocaleString("en-IN")} crop advisories to review</>}
              </p>

              {s.states.length > 0 && (
                <div className="mt-3.5">
                  <div className="mb-1.5 text-[10.5px] uppercase tracking-wide text-text-3">Where</div>
                  <ul className="space-y-1">
                    {s.states.map(([name, r]) => (
                      <li key={name}>
                        <button onClick={() => setFocus(union(r.bbs))}
                          className="group grid w-full cursor-pointer grid-cols-[1fr_auto] items-center gap-x-2 rounded-md px-1.5 py-1 text-left hover:bg-surface-2">
                          <span className="truncate text-[12px] text-text-2 group-hover:text-text">{name}</span>
                          <span className="num text-[11.5px] text-text-3">{r.risk}/{r.n}</span>
                          <span className="col-span-2 mt-1 h-1 overflow-hidden rounded-full bg-line">
                            <motion.span className="block h-full rounded-full bg-warning" initial={false}
                              animate={{ width: `${(r.risk / r.n) * 100}%` }} transition={{ duration: 0.5 }} />
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {s.urgent.length > 0 && (
                <div className="mt-3.5">
                  <div className="mb-1.5 text-[10.5px] uppercase tracking-wide text-text-3">Act first</div>
                  <ul className="space-y-0.5">
                    {s.urgent.map((i) => (
                      <li key={i}>
                        <button onClick={() => { setSelected(i); setFocus(blocks[i].bb); }}
                          className="group flex w-full cursor-pointer items-center gap-2 rounded-md px-1.5 py-1.5 text-left hover:bg-surface-2">
                          <MapPin size={13} className="shrink-0 text-alert" />
                          <span className="min-w-0 flex-1 truncate text-[12px]">
                            <span className="text-text">{blocks[i].name}</span>
                            <span className="text-text-3"> · {blocks[i].district}</span>
                          </span>
                          <ArrowUpRight size={13} className="shrink-0 text-text-3 opacity-0 transition-opacity group-hover:opacity-100" />
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.aside>
  );
}

function Tile({ label, tone, value }: { label: string; tone: string; value: number | null }) {
  return (
    <div className="rounded-lg bg-surface-2/70 px-2.5 py-2" style={{ boxShadow: `inset 0 2px 0 ${tone}` }}>
      <div className="text-[18px] font-semibold leading-none">{value === null ? "—" : <Count value={value} />}</div>
      <div className="mt-1 text-[10.5px] uppercase tracking-wide text-text-3">{label}</div>
    </div>
  );
}
