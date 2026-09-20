"use client";

/**
 * The model card: what the model is, what goes into it, how it was trained, and the full
 * performance matrix. Generated from the artifacts themselves (src/export/model_card.py),
 * so it cannot drift from the system it describes.
 */
import { useEffect, useState } from "react";
import { motion } from "motion/react";

export interface ModelCardData {
  product: string; generated: string;
  model: {
    type: string; params: Record<string, string | number>; count: number; trained_on: string;
    models: Record<string, { trees: number; rows: number }>;
    sampling: { issue_step: number; block_frac: number };
    early_stopping_years: number[]; calibration: string;
  };
  predicts: { events: string[]; leads: string; blocks: number; issued: string };
  labels: Record<string, string | number | number[]>;
  features: { count: number; names: string[]; groups: Record<string, string[]>; gain_by_group: Record<string, Record<string, number>> };
  validation: { protocol: string; folds: string[]; nested: string; climatology_prior_weight: number; scored_model: string };
  matrix: Record<string, { label: string; reliability_error: number; weeks: { week: number; bss: number; auc: number; brier: number; brier_clim: number; base_rate: number; n: number }[] }>;
  inputs: Record<string, { source?: string; history?: string; through?: string; blocks?: number; realtime?: string; realtime_days_held?: number } | string>;
  runtime: Record<string, string>;
}

const DRIVER_LABEL: Record<string, string> = {
  recent: "Rain here lately", normal: "Usual for the block and date", around: "Rain around the block",
  progress: "Monsoon progress here", mjo: "MJO", enso: "El Niño / La Niña",
  iod: "Indian Ocean Dipole", other: "Other",
};
const EVENT_ORDER = ["dry10", "onset", "heavy", "dry7"];
const pct = (x: number) => `${Math.round(x * 100)}%`;

export default function ModelCard() {
  const [c, setC] = useState<ModelCardData | null>(null);
  useEffect(() => { fetch("/data/model_card.json").then((r) => (r.ok ? r.json() : null)).then(setC).catch(() => {}); }, []);
  if (!c) return null;

  const drivers = Object.keys(DRIVER_LABEL).filter((d) =>
    EVENT_ORDER.some((e) => (c.features.gain_by_group[`${e}_W1`]?.[d] ?? 0) > 0.001));
  const events = EVENT_ORDER.filter((e) => c.matrix[e]);

  return (
    <section aria-labelledby="model-h" id="model">
      <div className="mb-4">
        <h2 id="model-h" className="text-[18px] font-semibold tracking-tight">The model, in full</h2>
        <p className="mt-1 max-w-3xl text-[13px] leading-relaxed text-text-2">
          Written by the pipeline from the trained models and the scoring run, not by hand
          ({c.product}, {c.generated}). {c.model.type}.
        </p>
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        <Card title="What it predicts">
          <Row k="Events" v={c.predicts.events.join(" · ")} />
          <Row k="Lead" v={c.predicts.leads} />
          <Row k="Area" v={`${c.predicts.blocks.toLocaleString("en-IN")} blocks, all India`} />
          <Row k="Issued" v={c.predicts.issued} />
          <Row k="Models" v={`${c.model.count} (one per event × lead week)`} />
        </Card>
        <Card title="How it was trained">
          <Row k="Years" v={c.model.trained_on} />
          <Row k="Held out for early stopping" v={c.model.early_stopping_years.join(", ")} />
          <Row k="Training rows" v={`${Math.round(Math.max(...Object.values(c.model.models).map((m) => m.rows)) / 1e6)} million per model`} />
          <Row k="Trees" v={`${Math.min(...Object.values(c.model.models).map((m) => m.trees))}–${Math.max(...Object.values(c.model.models).map((m) => m.trees))}, early stopped`} />
          <Row k="Sampling" v={`every ${c.model.sampling.issue_step}th issue day, ${pct(c.model.sampling.block_frac)} of blocks`} />
          <Row k="Hardware" v={c.runtime.training} />
        </Card>
        <Card title="How it was scored">
          <Row k="Protocol" v={c.validation.protocol} />
          <Row k="Folds" v={c.validation.folds.join(" · ")} />
          <Row k="Nested" v={c.validation.nested} />
          <Row k="Calibration" v={c.model.calibration} />
        </Card>
      </div>

      {/* which drivers the model actually leans on, in the same groups the explanations use */}
      <div className="mt-6">
        <h3 className="mb-2 text-[13px] font-semibold">What the model leans on (week 1, share of total gain)</h3>
        <div className="panel overflow-x-auto">
          <table className="w-full min-w-[560px] text-left">
            <thead>
              <tr className="border-b border-line text-[11px] uppercase tracking-wide text-text-3">
                <th className="px-5 py-2.5 font-medium">Driver</th>
                {events.map((e) => <th key={e} className="px-4 py-2.5 font-medium">{c.matrix[e].label}</th>)}
              </tr>
            </thead>
            <tbody>
              {drivers.map((d) => (
                <tr key={d} className="border-b border-line last:border-0">
                  <td className="px-5 py-2.5 text-[13px]">{DRIVER_LABEL[d]}</td>
                  {events.map((e) => {
                    const g = c.features.gain_by_group[`${e}_W1`]?.[d] ?? 0;
                    return (
                      <td key={e} className="px-4 py-2.5">
                        <div className="flex items-center gap-2">
                          <span className="h-1.5 w-16 overflow-hidden rounded-full bg-line">
                            <motion.span className="block h-full rounded-full bg-focus/70" initial={{ width: 0 }}
                              whileInView={{ width: `${g * 100}%` }} viewport={{ once: true }} transition={{ duration: 0.6 }} />
                          </span>
                          <span className="num text-[12px] text-text-2">{(g * 100).toFixed(g < 0.01 ? 1 : 0)}%</span>
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-[11.5px] text-text-3">
          LightGBM split gain, averaged over the five folds, grouped exactly as the per-block explanations
          group it. {c.features.count} features in total.
        </p>
      </div>

      {/* every number behind the summary table at the top of the page */}
      <div className="mt-6">
        <h3 className="mb-2 text-[13px] font-semibold">Performance matrix, in full</h3>
        <div className="panel overflow-x-auto">
          <table className="w-full min-w-[760px] text-left">
            <thead>
              <tr className="border-b border-line text-[11px] uppercase tracking-wide text-text-3">
                <th className="px-5 py-2.5 font-medium">Event</th>
                <th className="px-3 py-2.5 font-medium">Week</th>
                <th className="px-3 py-2.5 font-medium">Skill (BSS)</th>
                <th className="px-3 py-2.5 font-medium">AUC</th>
                <th className="px-3 py-2.5 font-medium">Brier</th>
                <th className="px-3 py-2.5 font-medium">Brier, climatology</th>
                <th className="px-3 py-2.5 font-medium">Happens</th>
                <th className="px-3 py-2.5 font-medium">Forecasts scored</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => c.matrix[e].weeks.map((w, k) => (
                <tr key={`${e}${w.week}`} className={`text-[12.5px] ${k === 3 ? "border-b border-line" : ""} last:border-0`}>
                  <td className="px-5 py-1.5">{k === 0 ? <span className="font-medium">{c.matrix[e].label}</span> : ""}</td>
                  <td className="num px-3 py-1.5 text-text-3">W{w.week}</td>
                  <td className={`num px-3 py-1.5 font-semibold ${w.bss > 0.005 ? "text-(--onset)" : "text-text-3"}`}>
                    {w.bss >= 0 ? "+" : ""}{w.bss.toFixed(3)}
                  </td>
                  <td className="num px-3 py-1.5">{w.auc.toFixed(3)}</td>
                  <td className="num px-3 py-1.5 text-text-2">{w.brier.toFixed(4)}</td>
                  <td className="num px-3 py-1.5 text-text-3">{w.brier_clim.toFixed(4)}</td>
                  <td className="num px-3 py-1.5 text-text-2">{pct(w.base_rate)}</td>
                  <td className="num px-3 py-1.5 text-text-3">{(w.n / 1e6).toFixed(1)}M</td>
                </tr>
              )))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-[11.5px] text-text-3">
          Scored only on held-out years, against each block&rsquo;s own climatology. The 7+ day dry spell is
          validated but not published as its own map layer: the crop advice uses the 10+ day break.
          Reliability error:{" "}
          {events.map((e) => `${c.matrix[e].label} ${(c.matrix[e].reliability_error * 100).toFixed(1)}%`).join(" · ")}.
        </p>
      </div>

      <div className="mt-6 grid gap-3 lg:grid-cols-2">
        <Card title="Inputs">
          {Object.entries(c.inputs).map(([k, v]) => (
            <Row key={k} k={k.replace(/_/g, " ")}
              v={typeof v === "string" ? v
                : [v.source, v.history, v.through && `through ${v.through}`,
                   v.realtime_days_held !== undefined && `${v.realtime_days_held} real-time days held`].filter(Boolean).join(" · ")} />
          ))}
        </Card>
        <Card title="Event definitions (the labels it learns)">
          <Row k="Wet day" v={`${c.labels.wet_day_mm} mm or more`} />
          <Row k="Dry spell" v={`${(c.labels.dry_spell_days as number[]).join(" and ")} consecutive dry days`} />
          <Row k="Heavy rain" v={`${c.labels.heavy_mm} mm in a day (IMD's heavy class)`} />
          <Row k="Onset" v={String(c.labels.onset)} />
          <Row k="False onset" v={String(c.labels.false_onset)} />
          <Row k="Onset confirmed after" v={`${c.labels.onset_confirmed_after_days} days`} />
        </Card>
      </div>

      <p className="mt-4 text-[12px] leading-relaxed text-text-3">
        Daily cost: {c.runtime.daily_run}. Explanations: {c.runtime.explanations}.
      </p>
    </section>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="panel p-4">
      <h3 className="mb-2.5 text-[13px] font-semibold">{title}</h3>
      <dl className="space-y-1.5">{children}</dl>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="grid grid-cols-[minmax(0,140px)_1fr] gap-3 text-[12px]">
      <dt className="text-text-3 first-letter:uppercase">{k}</dt>
      <dd className="text-text-2">{v}</dd>
    </div>
  );
}
