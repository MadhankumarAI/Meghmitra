"use client";

import { Fragment, useEffect, useState } from "react";
import { loadMetrics, PUBLISHED, type Metrics, type MetricEvent } from "@/lib/metrics";
import { X } from "lucide-react";
import { loadAdvisory, renderAdvice, citation, type AdvisoryFile, type Advice } from "@/lib/advisory";
import { AnimatePresence, motion } from "motion/react";
import ReviewSend from "./ReviewSend";
import WhyPanel from "./WhyPanel";
import Odds from "./Odds";
import type { ExplainEvent } from "@/lib/explain";
import { useConsole } from "@/lib/store";
import type { BlockMeta } from "@/lib/store";
import type { ForecastFile } from "@/lib/data";
import { CMRI, REGIMES, isRegime, inTen } from "@/lib/colors";

const ROWS = [
  { key: "onset", label: "Onset arrives", tone: "var(--onset)" },
  { key: "dry10", label: "10+ day dry spell", tone: "var(--dry)" },
  { key: "heavy", label: "Heavy-rain day", tone: "var(--wet)" },
] as const;

export default function BlockPanel({ forecast, blocks }: { forecast: ForecastFile; blocks: BlockMeta[] }) {
  const selected = useConsole((s) => s.selected);
  const setSelected = useConsole((s) => s.setSelected);
  const week = useConsole((s) => s.week);
  const expert = useConsole((s) => s.view) === "expert";
  const b = selected !== null ? blocks[selected] : null;
  const [advFile, setAdvFile] = useState<AdvisoryFile | null | undefined>(undefined);
  useEffect(() => {
    let live = true;
    loadAdvisory(forecast.issued).then((f) => { if (live) setAdvFile(f); });
    return () => { live = false; };
  }, [forecast.issued]);
  const advice = selected !== null ? advFile?.advisories[String(selected)] ?? [] : [];
  const [reviewing, setReviewing] = useState(false);

  return (
    <AnimatePresence>
      {b && selected !== null && (
        <motion.aside
          key="panel"
          aria-label={`Outlook for ${b.name}`}
          initial={{ opacity: 0, x: 24 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: 16, transition: { duration: 0.14 } }}
          transition={{ type: "spring", stiffness: 420, damping: 38 }}
          className="panel-solid absolute right-3 top-[72px] bottom-33 z-20 flex w-95 flex-col overflow-hidden"
        >
          <div className="flex items-start justify-between border-b border-line px-5 py-4">
            <div>
              <div className="text-[18px] font-semibold leading-tight">{b.name}</div>
              <div className="text-[12px] text-text-3">{b.district} · {b.state}</div>
            </div>
            <button
              aria-label="Close panel"
              onClick={() => setSelected(null)}
              className="grid h-9 w-9 cursor-pointer place-items-center rounded-md text-text-2 hover:bg-surface-2 hover:text-text"
            >
              <X size={18} />
            </button>
          </div>

          <div className="flex-1 space-y-5 overflow-y-auto px-5 py-4">
            <Headline forecast={forecast} i={selected} week={week} advice={advice} />
            <WhyPanel forecast={forecast} i={selected} preferred={eventOf(advice)} />

            {expert && <section aria-label="Four-week outlook">
              <div className="mb-2 grid grid-cols-[1fr_repeat(4,48px)] gap-1 text-[10px] uppercase tracking-wide text-text-3">
                <span />
                {[1, 2, 3, 4].map((w) => (
                  <span key={w} className={`text-center ${w === week ? "text-focus" : ""}`}>W{w}</span>
                ))}
              </div>
              {ROWS.map((r) => (
                <div key={r.key} className="grid grid-cols-[1fr_repeat(4,48px)] items-center gap-1 py-1">
                  <span className="flex items-center gap-2 text-[12px] text-text-2">
                    <span className="h-2 w-2 rounded-full" style={{ background: r.tone }} />
                    {r.label}
                  </span>
                  {[0, 1, 2, 3].map((w) => {
                    const p = forecast.events[r.key].p[w][selected];
                    const c = forecast.events[r.key].clim[w][selected];
                    return <Cell key={w} p={p} c={c} active={w + 1 === week} />;
                  })}
                </div>
              ))}
              <p className="mt-2 text-[11px] leading-relaxed text-text-3">
                Each cell: chance this week. The tick marks the normal chance for this block and week.
              </p>
            </section>}
            {expert && <BlockSkill i={selected} />}

            <Advisories file={advFile} rows={advice} onReview={() => setReviewing(true)} />
          </div>
        </motion.aside>
      )}
      {b && (
        <ReviewSend key={`${b.id}-${forecast.issued}`} open={reviewing} onClose={() => setReviewing(false)}
          advice={advice} block={b} forecast={forecast} />
      )}
    </AnimatePresence>
  );
}

/** How much to trust the outlook here: this block's own hindcast skill (Brier Skill Score). */
function BlockSkill({ i }: { i: number }) {
  const [m, setM] = useState<Metrics | null>(null);
  useEffect(() => { loadMetricsOnce().then(setM).catch(() => {}); }, []);
  if (!m) return null;
  const map = m.skill_map[PUBLISHED];
  const rows: [MetricEvent, string][] = [["dry10", "10+ day dry spell"], ["onset", "Onset"], ["heavy", "Heavy rain"]];
  return (
    <section aria-label="Model skill in this block">
      <div className="mb-2 flex items-baseline justify-between">
        <h3 className="text-[12px] font-semibold uppercase tracking-wide text-text-3">Skill here</h3>
        <span className="text-[10px] text-text-3">vs climatology · years never seen</span>
      </div>
      <div className="grid grid-cols-[1fr_repeat(4,48px)] gap-1 text-[12px]">
        {rows.map(([e, label]) => (
          <Fragment key={e}>
            <span className="py-1 text-text-2">{label}</span>
            {[0, 1, 2, 3].map((w) => {
              const v = map[e][w][i] / 100;
              return (
                <span key={w} className={`num py-1 text-center ${v > 0.02 ? "font-semibold text-(--onset)" : "text-text-3"}`}
                  title={v > 0.02 ? "Better than climatology" : "Shows climatology here"}>
                  {v > 0.02 ? `+${v.toFixed(2)}` : "clim"}
                </span>
              );
            })}
          </Fragment>
        ))}
      </div>
    </section>
  );
}

let metricsPromise: Promise<Metrics> | null = null;
const loadMetricsOnce = () => (metricsPromise ??= loadMetrics());

function Advisories({ file, rows, onReview }: {
  file: AdvisoryFile | null | undefined; rows: Advice[]; onReview: () => void;
}) {
  return (
    <section aria-label="Crop advisories">
      <div className="mb-2 flex items-baseline justify-between">
        <h3 className="text-[12px] font-semibold uppercase tracking-wide text-text-3">Advisories</h3>
        <span className="text-[10px] text-text-3">indicative crops · CRIDA contingency logic</span>
      </div>
      {file === undefined && <div className="h-16 animate-pulse rounded-lg bg-surface-2/60" />}
      {file !== undefined && rows.length === 0 && (
        <p className="rounded-lg border border-line px-3 py-3 text-[12px] text-text-3">
          No action needed this week beyond normal practice.
        </p>
      )}
      <ul className="space-y-2">
        {rows.map((a, k) => {
          const { title, body } = renderAdvice(a);
          const tone = a[2] >= 3 ? "var(--cmri-alert)" : "var(--cmri-warning)";
          return (
            <li key={k} className="rounded-lg border border-line bg-surface-2/40 py-2.5 pl-3 pr-3"
              style={{ boxShadow: `inset 3px 0 0 ${tone}` }}>
              <div className="text-[13px] font-semibold">{title}</div>
              <p className="mt-0.5 text-[12px] leading-snug text-text-2">{body}</p>
              <Source p={a[3]} />
            </li>
          );
        })}
      </ul>
      {rows.length > 0 && (
        <button onClick={onReview} className="mt-3 min-h-10 w-full cursor-pointer rounded-md bg-focus/15 text-[13px] font-medium text-focus transition-colors hover:bg-focus/25">
          Review &amp; send to farmers
        </button>
      )}
    </section>
  );
}

function Cell({ p, c, active }: { p: number; c: number; active: boolean }) {
  if (p < 0) return <span className="text-center text-[11px] text-text-3">—</span>;
  const up = p - c;
  return (
    <span
      title={`${p}% (normal ${c}%)`}
      className={`num relative flex h-9 flex-col items-center justify-center rounded-md text-[13px] font-semibold ${
        active ? "bg-surface-2 shadow-[0_0_0_1px_var(--line-strong)]" : ""
      }`}
    >
      {p}
      <span className="relative mt-0.5 block h-0.75 w-8 rounded-full bg-line">
        <span className="absolute inset-y-0 left-0 rounded-full bg-text-2" style={{ width: `${Math.min(100, p)}%` }} />
        <span className="absolute -top-0.5 h-1.75 w-px bg-text" style={{ left: `${Math.min(100, c)}%` }} />
      </span>
      {Math.abs(up) >= 5 && (
        <span className={`absolute -right-0.5 -top-0.5 h-1.5 w-1.5 rounded-full ${up > 0 ? "bg-warning" : "bg-normal"}`} />
      )}
    </span>
  );
}

function Headline({ forecast, i, week, advice }: {
  forecast: ForecastFile; i: number; week: number; advice: Advice[];
}) {
  const w = week - 1;
  const cls = forecast.cmri[w][i];
  if (isRegime(cls)) {
    const r = REGIMES[cls];
    return (
      <section className="rounded-lg border border-line bg-surface-2/50 p-4">
        <div className="mb-1.5 text-[12px] font-semibold">{r.label}</div>
        <p className="text-[13px] leading-snug text-text-2">{r.detail}</p>
      </section>
    );
  }
  const c = CMRI[cls] ?? CMRI[0];
  const dry = forecast.events.dry10.p[w][i];
  const dryN = forecast.events.dry10.clim[w][i];
  // Lead with the reason for the tier: in weeks 1-2 the most urgent advice sets it.
  const top = w < 2 && advice.length ? [...advice].sort((a, b) => b[2] - a[2])[0] : null;
  // odds for the event the advice is about, so the picture matches the sentence
  const ev = top ? eventOf([top]) : "dry10";
  const key = ev === "heavy" ? "heavy" : ev === "onset" ? "onset" : "dry10";
  const pv = forecast.events[key].p[w][i], cv = forecast.events[key].clim[w][i];
  const odds = pv >= 0 && cv >= 0 ? <Odds kind={key} p={pv / 100} clim={cv / 100} /> : null;
  if (top) {
    const { title, body } = renderAdvice(top);
    return (
      <section className="rounded-lg border border-line bg-surface-2/50 p-4">
        <div className="mb-1.5 flex items-center gap-2">
          <span className="rounded px-1.5 py-0.5 text-[11px] font-semibold text-[#08101c]" style={{ background: c.color }}>
            {c.label.toUpperCase()}
          </span>
          <span className="text-[11px] text-text-3">Week {week}</span>
        </div>
        {/* block-level: drop the "Crop: " prefix the cards below carry */}
        <p className="text-[14px] font-semibold leading-snug">{capitalise(title.replace(/^[^:]+:\s*/, ""))}</p>
        <p className="mt-1 text-[13px] leading-snug text-text-2">{body}</p>
        {odds && <div className="mt-3">{odds}</div>}
      </section>
    );
  }
  return (
    <section className="rounded-lg border border-line bg-surface-2/50 p-4">
      <div className="mb-1.5 flex items-center gap-2">
        <span className="rounded px-1.5 py-0.5 text-[11px] font-semibold text-[#08101c]" style={{ background: c.color }}>
          {c.label.toUpperCase()}
        </span>
        <span className="text-[11px] text-text-3">Week {week}</span>
      </div>
      <p className="text-[14px] leading-snug">
        {dry >= 0 ? (
          <>
            <span className="font-semibold">{inTen(dry / 100)}</span> chance of a 10+ day dry spell this week
            <span className="text-text-3"> (usually {inTen(dryN / 100)}).</span>
          </>
        ) : (
          "No dry-spell outlook available."
        )}
      </p>
      {odds && <div className="mt-3">{odds}</div>}
    </section>
  );
}

// the event behind the block's most urgent advice, so "why" opens on what matters here
function eventOf(advice: Advice[]): ExplainEvent | undefined {
  const top = [...advice].sort((a, b) => b[2] - a[2])[0];
  if (!top) return undefined;
  const e = String(top[3].event ?? "");
  return e === "heavy_rain" ? "heavy" : e.startsWith("dry_spell") ? "dry10" : "onset";
}

/** Every plan-backed advisory says which plan and page it came from. */
function Source({ p }: { p: Record<string, unknown> }) {
  const c = citation(p);
  if (!c) return p.indicative ? (
    <div className="mt-1.5 text-[10.5px] text-text-3">Indicative contingency: no district plan read for this district</div>
  ) : null;
  return (
    <a href={c.url} target="_blank" rel="noreferrer"
      className="mt-1.5 block truncate text-[10.5px] text-text-3 underline decoration-dotted underline-offset-2 hover:text-text-2"
      title={`${c.condition} — ${c.plan}`}>
      Source: {c.plan}, p{c.page}
    </a>
  );
}

const capitalise = (x: string) => x.charAt(0).toUpperCase() + x.slice(1);
