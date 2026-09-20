"use client";

import { useEffect, useRef, useState } from "react";
import { Play, Pause, ChevronLeft, ChevronRight, Radio } from "lucide-react";
import type { LiveIndex } from "@/lib/atmos";
import { useConsole } from "@/lib/store";

const STEP_MS = 900;

/** Live mode time control: steps through the latest NOAA GFS run, now to +10 days. */
export default function LiveBar({ index }: { index: LiveIndex | null }) {
  const k = useConsole((s) => s.liveIdx);
  const setK = useConsole((s) => s.setLiveIdx);
  const playing = useConsole((s) => s.dayPlaying);
  const setPlaying = useConsole((s) => s.setDayPlaying);
  const n = index?.frames.length ?? 0;

  useEffect(() => {
    if (!playing || !n) return;
    const t = setInterval(() => {
      const s = useConsole.getState();
      s.setLiveIdx((s.liveIdx + 1) % n);
    }, STEP_MS);
    return () => clearInterval(t);
  }, [playing, n]);

  const f = index?.frames[k];
  const when = (t: string) => new Date(t).toLocaleString("en-IN", {
    weekday: "short", day: "numeric", month: "short", hour: "2-digit", timeZone: "Asia/Kolkata",
  });
  const run = index ? `${index.run.slice(6, 8)} ${new Date(`${index.run.slice(0, 4)}-${index.run.slice(4, 6)}-01`)
    .toLocaleString("en-IN", { month: "short" })} ${index.run.slice(8)}Z` : "";

  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-0 z-20 flex justify-center p-2 md:p-3">
      <div className="panel pointer-events-auto flex w-[min(1040px,calc(100vw-24px))] items-center gap-3 px-2 py-2">
        <div className="flex items-center gap-1">
          <Btn label="Previous" onClick={() => setK(Math.max(0, k - 1))}><ChevronLeft size={18} /></Btn>
          <Btn label={playing ? "Pause" : "Play forecast"} onClick={() => setPlaying(!playing)} primary>
            {playing ? <Pause size={18} /> : <Play size={18} />}
          </Btn>
          <Btn label="Next" onClick={() => setK(Math.min(n - 1, k + 1))}><ChevronRight size={18} /></Btn>
        </div>
        <div className="w-52 shrink-0 leading-tight">
          <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wide text-[#ff6b6b]">
            <Radio size={11} /> Live · NOAA GFS run {run}
          </div>
          <div className="num text-[15px] font-semibold">{f ? when(f.t) : "Loading…"}</div>
        </div>
        <LiveTrack frames={index?.frames ?? []} k={k} onPick={(i) => { setPlaying(false); setK(i); }} when={when} />
      </div>
    </div>
  );
}

/** The forecast run as one rail: each frame a step, day boundaries marked, playhead on top. */
function LiveTrack({ frames, k, onPick, when }: {
  frames: { key: string; t: string; fh: number }[]; k: number; onPick: (i: number) => void; when: (t: string) => string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);
  const [hover, setHover] = useState<number | null>(null);
  const n = frames.length;
  const at = (clientX: number) => {
    const r = ref.current?.getBoundingClientRect();
    if (!r || n < 2) return 0;
    return Math.min(n - 1, Math.max(0, Math.round(((clientX - r.left) / r.width) * (n - 1))));
  };
  const pct = (i: number) => (n > 1 ? (i / (n - 1)) * 100 : 0);

  return (
    <div ref={ref} role="slider" aria-label="Forecast hour" tabIndex={0}
      aria-valuemin={0} aria-valuemax={Math.max(0, n - 1)} aria-valuenow={k}
      aria-valuetext={frames[k] ? when(frames[k].t) : undefined}
      onPointerDown={(e) => { dragging.current = true; e.currentTarget.setPointerCapture(e.pointerId); onPick(at(e.clientX)); }}
      onPointerMove={(e) => { const i = at(e.clientX); setHover(i); if (dragging.current) onPick(i); }}
      onPointerUp={() => { dragging.current = false; }}
      onPointerLeave={() => { dragging.current = false; setHover(null); }}
      className="relative h-11 flex-1 cursor-pointer touch-none select-none">
      <div className="absolute inset-x-0 top-4 h-5 overflow-hidden rounded-md bg-surface-2/70 ring-1 ring-inset ring-line" />
      <div className="pointer-events-none absolute left-0 top-4 h-5 rounded-l-md bg-focus/25" style={{ width: `${pct(k)}%` }} />
      {/* one tick per forecast day */}
      {frames.map((fr, i) => fr.fh % 24 === 0 && (
        <div key={fr.key} className="pointer-events-none absolute top-4 h-5" style={{ left: `${pct(i)}%` }}>
          <span className="absolute top-0 h-5 w-px bg-line-strong" />
          <span className="absolute -top-3.5 left-1 whitespace-nowrap text-[9.5px] tracking-wide text-text-3">
            {fr.fh === 0 ? "now" : `+${fr.fh / 24}d`}
          </span>
        </div>
      ))}
      {hover !== null && hover !== k && (
        <span className="num pointer-events-none absolute top-0 z-10 -translate-x-1/2 whitespace-nowrap rounded bg-(--surface-solid) px-1.5 py-0.5 text-[10px] text-text ring-1 ring-line"
          style={{ left: `${pct(hover)}%` }}>
          {frames[hover] && when(frames[hover].t)}
        </span>
      )}
      <div className="pointer-events-none absolute top-3 h-7 w-[3px] -translate-x-1/2 rounded-full bg-focus shadow-[0_0_10px_rgba(92,200,255,0.55)]"
        style={{ left: `${pct(k)}%` }}>
        <span className="absolute -top-[3px] left-1/2 h-2 w-2 -translate-x-1/2 rotate-45 rounded-[1px] bg-focus" />
      </div>
    </div>
  );
}

function Btn({ children, label, onClick, primary }: { children: React.ReactNode; label: string; onClick: () => void; primary?: boolean }) {
  return (
    <button aria-label={label} title={label} onClick={onClick}
      className={`grid h-10 w-10 cursor-pointer place-items-center rounded-md transition-colors ${
        primary ? "bg-focus/15 text-focus hover:bg-focus/25" : "text-text-2 hover:bg-surface-2 hover:text-text"}`}>
      {children}
    </button>
  );
}
