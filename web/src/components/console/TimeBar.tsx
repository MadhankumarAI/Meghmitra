"use client";

import { useEffect, useRef, useState } from "react";
import { Play, Pause, ChevronLeft, ChevronRight } from "lucide-react";
import { useConsole, type Week } from "@/lib/store";

const WEEKS: Week[] = [1, 2, 3, 4];
const CONF = { 1: "High", 2: "Medium", 3: "Low", 4: "Low" } as const;
const BARS = { 1: 3, 2: 2, 3: 1, 4: 1 } as const;   // skill at this lead, as a meter
const DAY_MS = 160;                                       // playback: ~6 days per second

const fmtDay = (d: string, opts: Intl.DateTimeFormatOptions) =>
  new Date(d + "T00:00:00").toLocaleDateString("en-IN", opts);

function weekRange(issued: string, w: number) {
  const a = new Date(issued + "T00:00:00");
  a.setDate(a.getDate() + 7 * (w - 1));
  const b = new Date(a);
  b.setDate(b.getDate() + 6);
  const f = (d: Date) => d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
  return `${f(a)} – ${f(b)}`;
}

export default function TimeBar({ dates, issued }: { dates: string[]; issued: string }) {
  const week = useConsole((s) => s.week);
  const setWeek = useConsole((s) => s.setWeek);
  const date = useConsole((s) => s.date);
  const setDate = useConsole((s) => s.setDate);
  const dayPlaying = useConsole((s) => s.dayPlaying);
  const setDayPlaying = useConsole((s) => s.setDayPlaying);
  const k = date ? dates.indexOf(date) : -1;

  const step = (n: number) => {
    if (!dates.length) return;
    const j = Math.min(dates.length - 1, Math.max(0, (k < 0 ? 0 : k) + n));
    setDate(dates[j]);
  };

  // day playback, stops at the end of the season
  useEffect(() => {
    if (!dayPlaying || !dates.length) return;
    const t = setInterval(() => {
      const s = useConsole.getState();
      const j = dates.indexOf(s.date ?? "");
      if (j >= dates.length - 1) { s.setDayPlaying(false); return; }
      s.setDate(dates[j + 1]);
    }, DAY_MS);
    return () => clearInterval(t);
  }, [dayPlaying, dates]);

  // keyboard: arrows step days, 1-4 pick the lead week, space plays the season
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.closest("input,textarea,[role=dialog]")) return;
      if (e.key === "ArrowRight") { e.preventDefault(); step(1); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); step(-1); }
      else if (["1", "2", "3", "4"].includes(e.key)) setWeek(Number(e.key) as Week);
      else if (e.key === " ") { e.preventDefault(); setDayPlaying(!useConsole.getState().dayPlaying); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-0 z-20 flex justify-center p-3">
      <div className="panel pointer-events-auto w-[min(1040px,calc(100vw-24px))] overflow-hidden">
        {/* row 1: issue date across the season */}
        <div className="flex items-center gap-3 border-b border-line px-2 py-1.5">
          <div className="flex items-center gap-1">
            <IconBtn label="Previous day" onClick={() => step(-1)}><ChevronLeft size={18} /></IconBtn>
            <IconBtn label={dayPlaying ? "Pause season" : "Play season"} onClick={() => setDayPlaying(!dayPlaying)} primary>
              {dayPlaying ? <Pause size={18} /> : <Play size={18} />}
            </IconBtn>
            <IconBtn label="Next day" onClick={() => step(1)}><ChevronRight size={18} /></IconBtn>
          </div>
          <div className="w-40 shrink-0 leading-tight">
            <div className="text-[10px] uppercase tracking-wide text-text-3">Forecast issued</div>
            <div className="num text-[15px] font-semibold">
              {fmtDay(issued, { day: "numeric", month: "short", year: "numeric" })}
            </div>
          </div>
          <SeasonTrack dates={dates} k={k} onPick={(j) => { setDayPlaying(false); setDate(dates[j]); }} />
        </div>

        {/* row 2: how far ahead */}
        <div className="flex items-stretch">
          <div className="flex w-[196px] shrink-0 items-center px-4 text-[11px] leading-tight text-text-3">
            Looking ahead
            <br />
            (skill falls with lead)
          </div>
          <div role="radiogroup" aria-label="Lead week" className="flex flex-1">
            {WEEKS.map((w) => {
              const active = w === week;
              return (
                <button
                  key={w}
                  role="radio"
                  aria-checked={active}
                  onClick={() => setWeek(w)}
                  className={`group relative flex-1 cursor-pointer border-l border-line px-4 py-2 text-left transition-colors duration-150 ${
                    active ? "bg-surface-2" : "hover:bg-surface-2/60"
                  }`}
                >
                  <div className="flex items-baseline justify-between">
                    <span className={`text-[13px] font-semibold ${active ? "text-text" : "text-text-2"}`}>Week {w}</span>
                    <span className="flex items-center gap-1 text-[10px] uppercase tracking-wide text-text-3"
                      title={`Model skill at this lead time: ${CONF[w]}`}>
                      {CONF[w]}
                      <span className="flex gap-[2px]">
                        {[0, 1, 2].map((i) => (
                          <span key={i} className={`h-2.5 w-[3px] rounded-full ${i < BARS[w] ? "bg-focus/80" : "bg-line-strong"}`} />
                        ))}
                      </span>
                    </span>
                  </div>
                  <div className="num mt-0.5 text-[11px] text-text-3">{weekRange(issued, w)}</div>
                  <span
                    className={`absolute inset-x-3 bottom-0 h-[3px] rounded-full transition-opacity duration-200 ${
                      active ? "bg-focus opacity-100" : "bg-line-strong opacity-0 group-hover:opacity-100"
                    }`}
                  />
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

/** Season track: the months as one continuous rail, with a playhead and a hover preview. */
function SeasonTrack({ dates, k, onPick }: { dates: string[]; k: number; onPick: (j: number) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);
  const [hover, setHover] = useState<number | null>(null);
  const n = dates.length;
  const at = (clientX: number) => {
    const r = ref.current?.getBoundingClientRect();
    if (!r || n < 2) return 0;
    return Math.min(n - 1, Math.max(0, Math.round(((clientX - r.left) / r.width) * (n - 1))));
  };
  // month blocks, sized by how many issue days fall in each
  const months: { label: string; start: number; count: number }[] = [];
  dates.forEach((d) => {
    const m = fmtDay(d, { month: "short" });
    const last = months.at(-1);
    if (last && last.label === m) last.count++;
    else months.push({ label: m, start: months.length ? months.at(-1)!.start + months.at(-1)!.count : 0, count: 1 });
  });
  const pct = (j: number) => (n > 1 ? (j / (n - 1)) * 100 : 0);
  const pos = k >= 0 ? pct(k) : 0;

  return (
    <div
      ref={ref}
      role="slider"
      aria-label="Forecast issue date"
      aria-valuemin={0}
      aria-valuemax={Math.max(0, n - 1)}
      aria-valuenow={Math.max(0, k)}
      aria-valuetext={k >= 0 ? dates[k] : undefined}
      tabIndex={0}
      onPointerDown={(e) => { dragging.current = true; e.currentTarget.setPointerCapture(e.pointerId); onPick(at(e.clientX)); }}
      onPointerMove={(e) => { const j = at(e.clientX); setHover(j); if (dragging.current) onPick(j); }}
      onPointerUp={() => { dragging.current = false; }}
      onPointerLeave={() => { dragging.current = false; setHover(null); }}
      className="group relative h-11 flex-1 cursor-pointer touch-none select-none"
    >
      {/* the season as one rail, divided by month */}
      <div className="absolute inset-x-0 top-3 flex h-6 overflow-hidden rounded-md bg-surface-2/70 ring-1 ring-inset ring-line">
        {months.map((m, i) => (
          <div key={m.label} style={{ flexGrow: m.count }} className={i ? "relative border-l border-line" : "relative"}>
            <span className="absolute left-1.5 top-1/2 -translate-y-1/2 text-[9.5px] font-medium uppercase tracking-[0.14em] text-text-3">
              {m.label}
            </span>
          </div>
        ))}
      </div>
      {/* season so far */}
      <div className="pointer-events-none absolute left-0 top-3 h-6 rounded-l-md bg-focus/18" style={{ width: `${pos}%` }} />
      {/* where the pointer is */}
      {hover !== null && hover !== k && (
        <>
          <div className="pointer-events-none absolute top-3 h-6 w-px bg-text-2/50" style={{ left: `${pct(hover)}%` }} />
          <span className="num pointer-events-none absolute -top-0.5 z-10 -translate-x-1/2 whitespace-nowrap rounded bg-(--surface-solid) px-1.5 py-0.5 text-[10px] text-text ring-1 ring-line"
            style={{ left: `${pct(hover)}%` }}>
            {fmtDay(dates[hover], { day: "numeric", month: "short" })}
          </span>
        </>
      )}
      {/* playhead */}
      <div className="pointer-events-none absolute top-2 h-8 w-[3px] -translate-x-1/2 rounded-full bg-focus shadow-[0_0_10px_rgba(92,200,255,0.55)]"
        style={{ left: `${pos}%` }}>
        <span className="absolute -top-[3px] left-1/2 h-2 w-2 -translate-x-1/2 rotate-45 rounded-[1px] bg-focus" />
      </div>
    </div>
  );
}

function IconBtn({
  children, label, onClick, primary,
}: { children: React.ReactNode; label: string; onClick: () => void; primary?: boolean }) {
  return (
    <button
      aria-label={label}
      title={label}
      onClick={onClick}
      className={`grid h-10 w-10 cursor-pointer place-items-center rounded-md transition-colors duration-150 ${
        primary ? "bg-focus/15 text-focus hover:bg-focus/25" : "text-text-2 hover:bg-surface-2 hover:text-text"
      }`}
    >
      {children}
    </button>
  );
}
