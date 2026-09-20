"use client";

/**
 * Ideas we tested and did not ship, with the scoreboard that made the decision
 * (src/export/experiments_json.py reads the runs themselves). Each row is one event and lead:
 * the dot sits left of the line if the idea lost skill, right if it gained. Nothing typed by hand.
 */
import { useEffect, useState } from "react";
import { motion } from "motion/react";

interface Cell { event: string; label: string; week: number; shipped: number; variant: number }
interface Tried { key: string; title: string; idea: string; found: string; verdict: string; cells: Cell[]; mean_bss_change: number }

export default function TriedAndRejected() {
  const [t, setT] = useState<Tried[] | null>(null);
  useEffect(() => {
    fetch("/data/experiments.json").then((r) => (r.ok ? r.json() : null))
      .then((d) => setT(d?.tried ?? null)).catch(() => {});
  }, []);
  if (!t?.length) return null;

  return (
    <section aria-labelledby="tried-h">
      <SectionHead id="tried-h" title="Tried, measured, not shipped"
        note="Two ideas that should have worked. We scored them the same way as everything else and left them out." />
      <div className="grid gap-4 lg:grid-cols-2">
        {t.map((x) => <Card key={x.key} x={x} />)}
      </div>
    </section>
  );
}

function Card({ x }: { x: Tried }) {
  const worse = x.mean_bss_change < 0;
  const span = Math.max(...x.cells.map((c) => Math.abs(c.variant - c.shipped)), 1e-4);
  return (
    <div className="panel flex flex-col p-5">
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-[14px] font-semibold">{x.title}</h3>
        <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold tracking-wide ${
          worse ? "bg-[#c1554a]/15 text-[#ff9e93]" : "bg-[#3f8f6b]/15 text-[#7fd6ab]"}`}>
          {worse ? "LOST SKILL" : "NO GAIN"}
        </span>
      </div>
      <p className="mt-1.5 text-[13px] leading-relaxed text-text-2">{x.idea}</p>

      <div className="my-4 space-y-1">
        <div className="mb-1.5 flex items-center justify-between text-[10px] uppercase tracking-wider text-text-3">
          <span>worse</span><span>skill change, per event and lead</span><span>better</span>
        </div>
        {x.cells.map((c, i) => {
          const d = c.variant - c.shipped;
          const frac = (d / span) * 0.5;                      // -0.5 .. 0.5 of the track
          return (
            <div key={`${c.event}${c.week}`} className="flex items-center gap-2">
              <span className="w-[112px] shrink-0 truncate text-[10.5px] text-text-3">{c.label} · wk {c.week}</span>
              <span className="relative h-3 flex-1 rounded-sm bg-white/[0.04]">
                <span aria-hidden className="absolute inset-y-0 left-1/2 w-px bg-white/20" />
                <motion.span
                  className="absolute top-1/2 h-1.5 rounded-full"
                  style={{ background: d < 0 ? "#e0736a" : "#5cc08f",
                           left: d < 0 ? `${50 + frac * 100}%` : "50%" }}
                  initial={{ width: 0, opacity: 0, y: "-50%" }}
                  whileInView={{ width: `${Math.abs(frac) * 100}%`, opacity: 1, y: "-50%" }}
                  viewport={{ once: true, margin: "-40px" }}
                  transition={{ duration: 0.5, delay: 0.25 + i * 0.03, ease: "easeOut" }} />
              </span>
              <span className={`num w-[52px] shrink-0 text-right text-[10.5px] tabular-nums ${d < 0 ? "text-[#e0736a]" : "text-text-3"}`}>
                {d >= 0 ? "+" : ""}{d.toFixed(4)}
              </span>
            </div>
          );
        })}
      </div>

      <p className="text-[13px] leading-relaxed text-text-2">{x.found}</p>
      <p className="mt-2 text-[12.5px] font-medium text-text">
        {x.verdict} <span className="num font-normal text-text-3">
          Mean change {x.mean_bss_change >= 0 ? "+" : ""}{x.mean_bss_change.toFixed(4)} BSS over {x.cells.length} cells.
        </span>
      </p>
    </div>
  );
}

function SectionHead({ id, title, note }: { id: string; title: string; note?: string }) {
  return (
    <div className="mb-4">
      <h2 id={id} className="text-[18px] font-semibold tracking-tight">{title}</h2>
      {note && <p className="mt-1 max-w-3xl text-[13px] text-text-3">{note}</p>}
    </div>
  );
}
