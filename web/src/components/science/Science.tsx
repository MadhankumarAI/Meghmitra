"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowLeft } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { BrandMark, Wordmark } from "@/components/Brand";
import ModelCard from "./ModelCard";
import TriedAndRejected from "./Tried";
import {
  loadMetrics, bssExpression, EVENT_LABEL, MODEL_LABEL, PUBLISHED,
  type Metrics, type MetricEvent, type EventScore,
} from "@/lib/metrics";

const MapView = dynamic(() => import("@/components/map/MapView"), {
  ssr: false,
  loading: () => <div className="absolute inset-0 bg-(--ocean)" />,
});

const EVENTS: MetricEvent[] = ["dry10", "dry7", "onset", "heavy"];

type Tab = "works" | "honest" | "where" | "model";
const TABS: { key: Tab; label: string; note: string }[] = [
  { key: "works", label: "Does it work?", note: "advice checked against what happened" },
  { key: "honest", label: "Is it reliable?", note: "do the stated chances hold up" },
  { key: "where", label: "Where it works", note: "skill block by block" },
  { key: "model", label: "The model", note: "what it is, and its full matrix" },
];

export default function Science() {
  const [m, setM] = useState<Metrics | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("works");
  useEffect(() => { loadMetrics().then(setM).catch((e) => setErr(String(e))); }, []);

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-6xl px-6 pb-12 pt-7">
        <Link href="/" className="group mb-4 inline-flex items-center gap-2.5 text-[12px] text-text-3 hover:text-text">
          <ArrowLeft size={14} className="transition-transform group-hover:-translate-x-0.5" />
          <BrandMark size={26} /> <Wordmark className="text-[14px] text-text" /> <span>· back to the observatory</span>
        </Link>
        <h1 className="text-[27px] font-semibold tracking-tight">How good is the outlook?</h1>
        <p className="mt-1.5 max-w-2xl text-[14px] leading-relaxed text-text-2">
          Scored only on years the model never saw: 1991–2025 in five seven-year blocks, each held out whole,
          with its climatology rebuilt without it.
        </p>

        <Headlines m={m} />

        {/* four short views instead of one long page */}
        <nav className="sticky top-0 z-10 -mx-6 mb-6 mt-7 bg-(--bg)/95 px-6 pb-3 pt-1 backdrop-blur">
          <div className="flex flex-wrap gap-1.5">
            {TABS.map((t) => (
              <button key={t.key} onClick={() => setTab(t.key)} aria-current={tab === t.key ? "page" : undefined}
                className={`cursor-pointer rounded-lg px-3.5 py-2 text-left transition-colors ${
                  tab === t.key ? "bg-surface-2 text-text shadow-[0_0_0_1px_var(--line-strong)]" : "text-text-2 hover:bg-surface-2/50 hover:text-text"}`}>
                <span className="block text-[13px] font-semibold">{t.label}</span>
                <span className="block text-[11px] text-text-3">{t.note}</span>
              </button>
            ))}
          </div>
        </nav>

        {err && <div role="alert" className="panel mb-6 px-4 py-3 text-sm text-alert">Couldn’t load metrics: {err}</div>}
        {!m && !err && <div className="panel h-64 animate-pulse" />}

        {m && (
          <AnimatePresence mode="wait" initial={false}>
            <motion.div key={tab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.18 }} className="space-y-10">
              {tab === "works" && <><AdviceOutcomes /><SkillTable m={m} /></>}
              {tab === "honest" && <><Reliability m={m} /><Honesty /><TriedAndRejected /></>}
              {tab === "where" && <SkillMapSection m={m} />}
              {tab === "model" && <><ModelCard /><Lineage /></>}
            </motion.div>
          </AnimatePresence>
        )}
      </div>
    </div>
  );
}

/* ---------- the three numbers that matter, before any detail ---------------------- */

function Headlines({ m }: { m: Metrics | null }) {
  const [adv, setAdv] = useState<{ rows: AdviceRow[] } | null>(null);
  useEffect(() => { fetch("/data/advice_skill_2023.json").then((r) => (r.ok ? r.json() : null)).then(setAdv).catch(() => {}); }, []);
  const wait = adv?.rows.find((r) => r.template === "DELAY_SOWING");
  const dry = m?.models[PUBLISHED]?.dry10?.leads?.[0];
  const tiles = [
    wait && { big: `${Math.round(wait.came_true * 100)}%`, label: "of “wait to sow” advisories were followed by a dry spell",
              sub: `against ${Math.round((wait.usual ?? 0) * 100)}% normally · ${wait.n.toLocaleString("en-IN")} block-days` },
    dry && { big: `+${dry.bss.toFixed(3)}`, label: "skill over climatology, dry spell in week 1",
             sub: "Brier Skill Score; 0 would mean no better than normal" },
    dry && { big: dry.auc.toFixed(2), label: "AUC: risky blocks ranked above safe ones",
             sub: `climatology manages ${dry.auc_clim.toFixed(2)}` },
  ].filter(Boolean) as { big: string; label: string; sub: string }[];
  if (!tiles.length) return null;
  return (
    <div className="mt-6 grid gap-3 sm:grid-cols-3">
      {tiles.map((t, i) => (
        <motion.div key={t.label} className="panel px-4 py-3.5" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.07 }}>
          <div className="num text-[30px] font-semibold leading-none text-(--onset)">{t.big}</div>
          <div className="mt-1.5 text-[12.5px] leading-snug text-text">{t.label}</div>
          <div className="mt-1 text-[11px] leading-snug text-text-3">{t.sub}</div>
        </motion.div>
      ))}
    </div>
  );
}

/* ---------- did the advice come true? --------------------------------------------- */

interface AdviceRow { template: string; n: number; came_true: number; all_blocks: number; forecast: number | null; usual: number | null }
const ADVICE_TEXT: Record<string, { title: string; happened: string }> = {
  DELAY_SOWING: { title: "“Wait to sow”", happened: "a 10+ day dry spell followed" },
  DRY_SPELL_CONSERVE_MOISTURE: { title: "“Conserve soil moisture”", happened: "a 10+ day dry spell followed" },
  PREPARE_IRRIGATION: { title: "“Arrange protective irrigation”", happened: "a 10+ day dry spell followed" },
  SOW_NOW: { title: "“Sow on the coming rain”", happened: "true onset came within 2 weeks" },
  HEAVY_RAIN_PROTECT: { title: "“Heavy rain: protect the crop”", happened: "a ≥ 64.5 mm day followed" },
  SWITCH_CROP: { title: "“Monsoon late: switch crop”", happened: "onset stayed away for 2 more weeks" },
};

function AdviceOutcomes() {
  const [d, setD] = useState<{ year: number; rows: AdviceRow[] } | null>(null);
  useEffect(() => { fetch("/data/advice_skill_2023.json").then((r) => (r.ok ? r.json() : null)).then(setD).catch(() => {}); }, []);
  if (!d) return null;
  return (
    <section aria-labelledby="adv-h">
      <SectionHead id="adv-h" title="Did the advice come true?"
        note={`Every advisory issued in the ${d.year} replay, against what IMD rainfall then recorded. One count per block and day.`} />
      <div className="grid gap-3 md:grid-cols-3">
        {d.rows.map((r, k) => {
          const t = ADVICE_TEXT[r.template] ?? { title: r.template, happened: "the event followed" };
          const bars: [string, number | null, string][] = [
            ["Happened", r.came_true, "var(--onset)"],
            ["Model said", r.forecast, "var(--text-2)"],
            ["Usual here", r.usual, "var(--line-strong)"],
          ];
          return (
            <motion.div key={r.template} className="panel p-4" initial={{ opacity: 0, y: 10 }} whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-40px" }} transition={{ delay: k * 0.06 }}>
              <div className="text-[13px] font-semibold">{t.title}</div>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="num text-[30px] font-semibold leading-none">{Math.round(r.came_true * 100)}%</span>
                <span className="text-[12px] leading-snug text-text-3">of the time, {t.happened}</span>
              </div>
              <div className="mt-3 space-y-1.5">
                {bars.filter(([, v]) => v !== null).map(([label, v, color]) => (
                  <div key={label} className="grid grid-cols-[74px_1fr_36px] items-center gap-2 text-[11px]">
                    <span className="text-text-3">{label}</span>
                    <span className="h-1.5 overflow-hidden rounded-full bg-line/60">
                      <motion.span className="block h-full rounded-full" style={{ background: color }}
                        initial={{ width: 0 }} whileInView={{ width: `${(v as number) * 100}%` }} viewport={{ once: true }}
                        transition={{ duration: 0.7, delay: 0.15 + k * 0.06, ease: "easeOut" }} />
                    </span>
                    <span className="num text-right text-text-2">{Math.round((v as number) * 100)}%</span>
                  </div>
                ))}
              </div>
              <div className="mt-3 text-[11px] text-text-3">
                {r.n.toLocaleString("en-IN")} block-days
                {r.forecast != null && <span> · stated {Math.round((r.forecast as number) * 100)}%</span>}
                {r.template === "SWITCH_CROP" && <span> · no like-for-like baseline</span>}
              </div>
            </motion.div>
          );
        })}
      </div>
    </section>
  );
}

/* ---------- skill by lead week ---------------------------------------------- */

function SkillTable({ m }: { m: Metrics }) {
  const pub = m.models[PUBLISHED];
  const alt = m.models.fast_v2;
  return (
    <section aria-labelledby="skill-h">
      <SectionHead id="skill-h" title="Skill by lead week"
        note="Brier Skill Score against climatology. Where skill is zero or below, the product shows climatology instead, and says so." />
      <div className="panel overflow-hidden">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-line text-[11px] uppercase tracking-wide text-text-3">
              <th className="px-5 py-3 font-medium">Event</th>
              {[1, 2, 3, 4].map((w) => <th key={w} className="px-4 py-3 font-medium">Week {w}</th>)}
              <th className="px-5 py-3 font-medium">Separates risky from safe blocks (week 1)</th>
            </tr>
          </thead>
          <tbody>
            {EVENTS.map((e) => (
              <tr key={e} className="border-b border-line last:border-0">
                <td className="px-5 py-4 text-[14px] font-medium">{EVENT_LABEL[e]}</td>
                {pub[e].leads.map((l, k) => (
                  <SkillCell key={l.week} bss={l.bss} alt={alt?.[e].leads[k].bss} />
                ))}
                <td className="px-5 py-4">
                  <AucLine auc={pub[e].leads[0].auc} clim={pub[e].leads[0].auc_clim} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {alt && (
        <p className="mt-3 text-[12px] text-text-3">
          Small figures show {MODEL_LABEL.fast_v2}. It was measured under the identical protocol and did not beat
          the published model, so it was not adopted.
        </p>
      )}
    </section>
  );
}

function SkillCell({ bss, alt }: { bss: number; alt?: number }) {
  const shown = bss > 0.005;
  const width = Math.max(0, Math.min(1, bss / 0.3)) * 100;
  return (
    <td className="px-4 py-4 align-top">
      {shown ? (
        <>
          <div className="num text-[18px] font-semibold">+{bss.toFixed(3)}</div>
          <div className="mt-1.5 h-1 w-full rounded-full bg-line">
            <div className="h-1 rounded-full bg-(--onset)" style={{ width: `${width}%` }} />
          </div>
        </>
      ) : (
        <div className="leading-tight">
          <div className="num text-[15px] text-text-3">{bss >= 0 ? "+" : ""}{bss.toFixed(3)}</div>
          <div className="mt-1 text-[11px] text-text-3">shows climatology</div>
        </div>
      )}
      {alt !== undefined && (
        <div className="num mt-1.5 text-[10px] text-text-3">v2 {alt >= 0 ? "+" : ""}{alt.toFixed(3)}</div>
      )}
    </td>
  );
}

function AucLine({ auc, clim }: { auc: number; clim: number }) {
  return (
    <div className="text-[13px] text-text-2">
      <span className="num font-semibold text-text">{auc.toFixed(2)}</span>
      <span className="text-text-3"> vs </span>
      <span className="num">{clim.toFixed(2)}</span>
      <span className="text-text-3"> for climatology (AUC)</span>
    </div>
  );
}

/* ---------- reliability ---------------------------------------------------- */

function Reliability({ m }: { m: Metrics }) {
  const pub = m.models[PUBLISHED];
  return (
    <section aria-labelledby="rel-h">
      <SectionHead id="rel-h" title="When we say 30%, it happens about 30% of the time"
        note="Reliability: forecast probability against how often the event actually happened. The diagonal is perfect calibration; dot size is how many forecasts fell in that range." />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {EVENTS.map((e) => <RelPlot key={e} title={EVENT_LABEL[e]} s={pub[e]} />)}
      </div>
    </section>
  );
}

function RelPlot({ title, s }: { title: string; s: EventScore }) {
  const W = 220, H = 220, pad = 28;
  const { forecast, observed, count } = s.reliability;
  const maxN = Math.max(...count);
  const x = (v: number) => pad + v * (W - pad - 8);
  const y = (v: number) => H - pad - v * (H - pad - 8);
  const pts = forecast.map((f, k) => ({ f, o: observed[k], n: count[k] })).filter((p) => p.n > 0);
  return (
    <figure className="panel p-4">
      <figcaption className="mb-2 flex items-baseline justify-between">
        <span className="text-[13px] font-medium">{title}</span>
        <span className="num text-[11px] text-text-3">error {(s.reliability_error * 100).toFixed(1)}%</span>
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img"
        aria-label={`${title}: calibration error ${(s.reliability_error * 100).toFixed(1)} percent`}>
        {[0, 0.25, 0.5, 0.75, 1].map((v) => (
          <g key={v}>
            <line x1={x(v)} x2={x(v)} y1={y(0)} y2={y(1)} stroke="var(--line)" strokeWidth="1" />
            <line x1={x(0)} x2={x(1)} y1={y(v)} y2={y(v)} stroke="var(--line)" strokeWidth="1" />
            <text x={x(v)} y={H - 10} fontSize="9" fill="var(--text-3)" textAnchor={v === 1 ? "end" : "middle"}>{v * 100}%</text>
            <text x={10} y={y(v) + 3} fontSize="9" fill="var(--text-3)" textAnchor="middle">{v * 100}</text>
          </g>
        ))}
        <line x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)} stroke="var(--text-3)" strokeDasharray="3 3" />
        <polyline fill="none" stroke="var(--focus)" strokeWidth="1.5"
          points={pts.map((p) => `${x(p.f)},${y(p.o)}`).join(" ")} />
        {pts.map((p, k) => (
          <circle key={k} cx={x(p.f)} cy={y(p.o)} r={2 + 6 * Math.sqrt(p.n / maxN)}
            fill="var(--focus)" fillOpacity="0.35" stroke="var(--focus)" strokeWidth="1">
            <title>{`forecast ${(p.f * 100).toFixed(0)}% → happened ${(p.o * 100).toFixed(0)}% (${p.n.toLocaleString("en-IN")} forecasts)`}</title>
          </circle>
        ))}
      </svg>
      <div className="mt-1 flex justify-between text-[10px] text-text-3">
        <span>forecast chance →</span><span>↑ how often it happened</span>
      </div>
    </figure>
  );
}

/* ---------- skill map ------------------------------------------------------ */

function SkillMapSection({ m }: { m: Metrics }) {
  const [event, setEvent] = useState<MetricEvent>("dry10");
  const [week, setWeek] = useState(1);
  const values = useMemo(
    () => Float32Array.from(m.skill_map[PUBLISHED][event][week - 1], (v) => v / 100),
    [m, event, week],
  );
  const positive = useMemo(() => values.filter((v) => v > 0.02).length / values.length, [values]);
  return (
    <section aria-labelledby="map-h">
      <SectionHead id="map-h" title="Where it works, and where it doesn’t"
        note="Skill per block. Teal: better than climatology. Brown: worse, so those blocks are shown climatology." />
      <div className="panel relative h-[560px] overflow-hidden">
        <MapView values={values} expr={bssExpression} padRight={300} />
        <div className="absolute right-4 top-4 w-64 space-y-4">
          <div className="panel p-3">
            <div className="mb-2 text-[11px] uppercase tracking-wide text-text-3">Event</div>
            <div className="flex flex-wrap gap-1.5">
              {EVENTS.map((e) => (
                <button key={e} onClick={() => setEvent(e)} aria-pressed={event === e}
                  className={`cursor-pointer rounded-md px-2.5 py-1.5 text-[12px] ${event === e ? "bg-surface-2 text-text shadow-[0_0_0_1px_var(--line-strong)]" : "text-text-2 hover:text-text"}`}>
                  {EVENT_LABEL[e]}
                </button>
              ))}
            </div>
            <div className="mb-2 mt-3 text-[11px] uppercase tracking-wide text-text-3">Lead</div>
            <div className="flex gap-1.5">
              {[1, 2, 3, 4].map((w) => (
                <button key={w} onClick={() => setWeek(w)} aria-pressed={week === w}
                  className={`min-h-9 flex-1 cursor-pointer rounded-md text-[12px] ${week === w ? "bg-surface-2 text-text shadow-[0_0_0_1px_var(--line-strong)]" : "text-text-2 hover:text-text"}`}>
                  W{w}
                </button>
              ))}
            </div>
          </div>
          <div className="panel p-3">
            <div className="num text-[22px] font-semibold">{Math.round(positive * 100)}%</div>
            <div className="text-[12px] text-text-2">of blocks beat climatology here</div>
            <div className="mt-3 h-2 rounded-sm" style={{ background: "linear-gradient(90deg,#7a4a1f,#3a3028,#1c2533,#1f4a50,#2a8a86,#6fd6c4)" }} />
            <div className="num relative mt-1 h-3 text-[10px] text-text-3">
              <span className="absolute left-0">−0.2</span>
              {/* zero sits at 0.2 / 0.5 = 40% of the scale */}
              <span className="absolute left-[40%] -translate-x-1/2">0</span>
              <span className="absolute right-0">+0.3</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ---------- honesty and lineage -------------------------------------------- */

function Honesty() {
  const items = [
    ["Regional atmosphere, for extended range.",
      "The next stage feeds the monsoon jet, moisture transport and the BSISO from ERA5 into the model, which is where week 3 and 4 skill comes from. The pipeline and the domain (20°S–40°N, 40–160°E) are already built."],
    ["A higher-resolution daily target.",
      "IMERG at 0.1° and MSWEP are the candidates for a daily high-resolution target alongside the IMD gauge record, which would sharpen block-to-block contrast further."],
    ["Every event defined on IMD gauge data.",
      "CHIRPS at 5 km gives each block its own texture (seasonal totals agree at ratio 1.06, dry weeks at 86%), while the events themselves stay on IMD’s gauge record, so the labels carry no satellite timing error."],
    ["More languages, on the same machinery.",
      "Six today. Each string carries its own review status, so adding a language is content work rather than engineering."],
  ];
  return (
    <section aria-labelledby="hon-h">
      <SectionHead id="hon-h" title="What comes next" note="Built on what is already measured." />
      <div className="grid gap-4 md:grid-cols-2">
        {items.map(([t, d]) => (
          <div key={t} className="panel p-5">
            <div className="text-[14px] font-semibold">{t}</div>
            <p className="mt-1.5 text-[13px] leading-relaxed text-text-2">{d}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function Lineage() {
  const rows = [
    ["Rainfall (truth)", "IMD gridded daily rainfall, 0.25°", "1981–2025"],
    ["Rainfall (texture)", "CHIRPS v2.0 daily, 0.05°", "1981–2025"],
    ["MJO", "NOAA PSL ROMI (real-time OLR MJO index)", "1991 → 14 Sep 2026"],
    ["ENSO", "NOAA CPC weekly OISST Niño 3.4", "1981 → 9 Sep 2026"],
    ["Blocks", "geoBoundaries India ADM3 (6,824 subdistricts)", "CC BY 4.0"],
  ];
  const checks = [
    "Our drought years match IMD’s official list exactly: 1982, 1987, 2002, 2004, 2009, 2014, 2015.",
    "Every input is dated to when it was published, not when it was observed.",
    "Discontinued or lagging feeds were replaced: BoM’s MJO index ended Feb 2024; NOAA’s dipole index runs four months behind, so we computed the dipole ourselves from ERSST v5 before testing it.",
    "A naive parse of NOAA’s weekly ENSO file silently drops 73% of weeks, mostly La Niña weeks. Caught and fixed.",
    "Leak test: inverting every label in a held-out block leaves that block’s climatology bit-identical.",
  ];
  return (
    <section aria-labelledby="lin-h" className="pb-12">
      <SectionHead id="lin-h" title="Data and checks" />
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="panel overflow-hidden">
          <table className="w-full text-left text-[13px]">
            <tbody>
              {rows.map(([k, v, d]) => (
                <tr key={k} className="border-b border-line last:border-0">
                  <td className="px-4 py-3 text-text-3">{k}</td>
                  <td className="px-4 py-3">{v}</td>
                  <td className="num px-4 py-3 text-text-3">{d}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <ul className="panel space-y-2.5 p-5 text-[13px] leading-relaxed text-text-2">
          {checks.map((c) => (
            <li key={c} className="flex gap-2.5">
              <span aria-hidden className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-(--onset)" />
              {c}
            </li>
          ))}
        </ul>
      </div>
    </section>
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
