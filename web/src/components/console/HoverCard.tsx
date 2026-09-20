"use client";

import { useConsole } from "@/lib/store";
import type { BlockMeta } from "@/lib/store";
import { onsetFront, doyLabel, ONSET, type ForecastFile } from "@/lib/data";
import { CMRI, REGIMES, isRegime, ONSET_FRONT } from "@/lib/colors";

const NAME = { dry10: "10+ day dry spell", heavy: "Heavy-rain day" } as const;

/** "What's here?": plain-language answer for the block under the cursor. */
export default function HoverCard({ forecast, blocks }: { forecast: ForecastFile; blocks: BlockMeta[] }) {
  const hovered = useConsole((s) => s.hovered);
  const event = useConsole((s) => s.event);
  const week = useConsole((s) => s.week);
  if (hovered === null) return null;
  const b = blocks[hovered];
  if (!b) return null;
  const w = week - 1;

  return (
    <div
      aria-live="polite"
      className="panel pointer-events-none absolute left-3 top-[72px] z-20 w-72 px-4 py-3"
    >
      <div className="text-[14px] font-semibold leading-tight">{b.name}</div>
      <div className="mb-2 text-[11px] text-text-3">{b.district} · {b.state}</div>
      {event === "cmri" ? (
        <CmriLine cls={forecast.cmri[w][hovered]} />
      ) : event === "onset" ? (
        <OnsetLine forecast={forecast} i={hovered} />
      ) : (
        <ProbLine
          label={`${NAME[event]} · week ${week}`}
          p={forecast.events[event].p[w][hovered]}
          c={forecast.events[event].clim[w][hovered]}
        />
      )}
      <div className="mt-2 text-[10px] text-text-3">Click for the full outlook</div>
    </div>
  );
}

function OnsetLine({ forecast, i }: { forecast: ForecastFile; i: number }) {
  const cls = onsetFront(forecast)[i];
  const c = ONSET_FRONT[cls] ?? ONSET_FRONT[6];
  const yr = Number(forecast.issued.slice(0, 4));
  const doy = forecast.sowing_rain_doy?.[i] ?? -1;
  const when = doy > 0 ? doyLabel(yr, doy) : null;
  const status = forecast.onset_status?.[i];
  const headline =
    cls === 0 ? "Monsoon has arrived" :
    cls === 1 ? "Monsoon arrived — holding" :
    `Onset expected: ${c.label.toLowerCase()}`;
  const story =
    cls === 0 && when ? `Sowing rain on ${when}; it held.` :
    cls === 1 && when ? `Sowing rain on ${when}. No 10-day dry break yet.` :
    status === ONSET.FAILED && when ? `False onset: rain on ${when} was followed by a 10+ day dry spell.` :
    c.note;
  return (
    <div>
      <div className="flex items-center gap-2">
        <span className="h-3 w-3 shrink-0 rounded-sm" style={{ background: c.color }} />
        <span className="text-[13px] font-semibold">{headline}</span>
      </div>
      <div className={`mt-1 text-[12px] ${status === ONSET.FAILED ? "text-warning" : "text-text-2"}`}>{story}</div>
    </div>
  );
}

function CmriLine({ cls }: { cls: number }) {
  if (isRegime(cls)) {
    const r = REGIMES[cls];
    return (
      <div className="flex items-center gap-2">
        <span className="h-3 w-3 shrink-0 rounded-sm border border-line-strong" style={{ background: r.color }} />
        <span className="text-[13px] font-semibold">{r.label}</span>
        <span className="text-[11px] text-text-3">{r.short}</span>
      </div>
    );
  }
  const c = CMRI[cls] ?? CMRI[0];
  return (
    <div className="flex items-center gap-2">
      <span className="h-3 w-3 rounded-sm" style={{ background: c.color }} />
      <span className="text-[13px] font-semibold">{c.label}</span>
      <span className="text-[11px] text-text-3">{c.note}</span>
    </div>
  );
}

export function ProbLine({ label, p, c }: { label: string; p: number; c: number }) {
  if (p < 0) return <div className="text-[12px] text-text-3">{label}: onset already confirmed</div>;
  const d = p - c;
  return (
    <div>
      <div className="text-[11px] text-text-2">{label}</div>
      <div className="num flex items-baseline gap-2">
        <span className="text-[22px] font-semibold">{p}%</span>
        <span className="text-[11px] text-text-3">normal {c}%</span>
        {Math.abs(d) >= 3 && (
          <span className={`text-[11px] font-medium ${d > 0 ? "text-warning" : "text-text-2"}`}>
            {d > 0 ? "▲" : "▼"} {Math.abs(d)} pts
          </span>
        )}
      </div>
    </div>
  );
}
