"use client";

import { useConsole, type EventKey, type BlockMeta } from "@/lib/store";
import type { ForecastFile } from "@/lib/data";
import Link from "next/link";
import { Wind, Send } from "lucide-react";
import Search from "./Search";
import { BrandMark, Wordmark } from "@/components/Brand";

const EVENTS: { key: EventKey; label: string; hint: string }[] = [
  { key: "cmri", label: "Risk (CMRI)", hint: "Combined Monsoon Risk Indicator" },
  { key: "onset", label: "Onset", hint: "Chance the true monsoon onset arrives" },
  { key: "dry10", label: "Dry spell", hint: "Chance of a 10+ day dry spell" },
  { key: "heavy", label: "Heavy rain", hint: "Chance of a day with 64.5 mm or more" },
];

function fmt(d: string) {
  return new Date(d + "T00:00:00").toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

export default function TopBar({ forecast, blocks }: { forecast: ForecastFile | null; blocks: BlockMeta[] | null }) {
  const event = useConsole((s) => s.event);
  const setEvent = useConsole((s) => s.setEvent);
  const view = useConsole((s) => s.view);
  const understand = useConsole((s) => s.understand);
  const setUnderstand = useConsole((s) => s.setUnderstand);
  const setView = useConsole((s) => s.setView);
  const mode = useConsole((s) => s.mode);
  const setMode = useConsole((s) => s.setMode);
  const setDelivery = useConsole((s) => s.setDelivery);

  return (
    <header className="no-scrollbar pointer-events-auto absolute inset-x-0 top-0 z-20 flex items-start gap-2 overflow-x-auto p-2
      md:pointer-events-none md:justify-between md:gap-4 md:overflow-visible md:p-3">
      <div className="flex shrink-0 items-start gap-2">
        <div className="panel pointer-events-auto flex items-center gap-3 px-3 py-2 md:px-4 md:py-2.5">
          <BrandMark size={34} />
          <div className="leading-tight">
            <Wordmark className="block text-[16px]" />
            <div className="hidden whitespace-nowrap text-[11px] text-text-3 min-[1500px]:block">Monsoon Risk Observatory · India</div>
          </div>
        </div>
        {blocks && <Search blocks={blocks} />}
      </div>

      {forecast ? <nav aria-label="Map layer" className="panel pointer-events-auto flex shrink-0 p-1">
        {EVENTS.map((e) => (
          <button
            key={e.key}
            title={e.hint}
            aria-pressed={event === e.key}
            onClick={() => setEvent(e.key)}
            className={`relative min-h-9 cursor-pointer whitespace-nowrap rounded-md px-3 text-[13px] font-medium transition-colors duration-150 ${
              event === e.key ? "bg-surface-2 text-text shadow-[0_0_0_1px_var(--line-strong)]" : "text-text-2 hover:text-text"
            }`}
          >
            {e.label}
          </button>
        ))}
      </nav> : <div />}

      <div className="flex shrink-0 items-start gap-2">
        <div className="panel pointer-events-auto flex p-1" role="group" aria-label="Data mode">
          {([["replay", "2023 replay"], ["live", "Live"]] as const).map(([m, label]) => (
            <button key={m} aria-pressed={mode === m} onClick={() => setMode(m)}
              className={`flex min-h-9 cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md px-3 text-[12px] font-medium transition-colors ${
                mode === m ? "bg-surface-2 text-text" : "text-text-3 hover:text-text"}`}>
              {m === "live" && <span className={`h-1.5 w-1.5 rounded-full ${mode === "live" ? "animate-pulse bg-[#ff6b6b]" : "bg-text-3"}`} />}
              {label}
            </button>
          ))}
        </div>
        <button
          onClick={() => setUnderstand(!understand)}
          aria-pressed={understand}
          className={`panel pointer-events-auto flex min-h-11 cursor-pointer items-center gap-2 whitespace-nowrap px-3.5 text-[12px] font-semibold transition-colors ${
            understand ? "text-[#0a1220]" : "text-text-2 hover:text-text"}`}
          style={understand ? { background: "var(--focus)" } : undefined}
        >
          <Wind size={15} aria-hidden />
          Understand
        </button>
        <button
          onClick={() => setDelivery(true)}
          title="What the WhatsApp service has actually sent"
          className="panel pointer-events-auto flex min-h-11 cursor-pointer items-center gap-2 whitespace-nowrap px-3.5 text-[12px] font-medium text-text-2 transition-colors hover:text-text"
        >
          <Send size={14} aria-hidden />
          Delivery
        </button>
        <Link
          href="/science"
          className="panel pointer-events-auto flex min-h-11 items-center px-3.5 text-[12px] font-medium text-text-2 transition-colors hover:text-text"
        >
          Evidence
        </Link>
        {forecast && (
          <Link href="/science#model"
            className="panel pointer-events-auto hidden whitespace-nowrap px-3.5 py-2 text-right leading-tight transition-colors hover:text-text min-[1500px]:block"
            title={forecast.source === "live"
              ? "Live: today's outlook from real-time IMD rainfall and NOAA indices, model trained 1991–2025"
              : "Hindcast: the model issuing this forecast never saw 2019–2025 (five 7-year blocks, each held out whole)"}>
            <div className="text-[12px] font-semibold">
              {forecast?.product ?? "CMRI v1.0"}
              <span className="ml-2 rounded bg-surface-2 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-text-2">
                {forecast?.source === "clim" ? "Climatology" : forecast?.source === "live" ? "Live" : "Hindcast"}
              </span>
            </div>
            <div className="num text-[11px] text-text-3">Issued {forecast ? fmt(forecast.issued) : "—"} · 06:00 IST</div>
          </Link>
        )}
        {forecast && <div className="panel pointer-events-auto flex p-1" role="group" aria-label="Detail level">
          {(["standard", "expert"] as const).map((v) => (
            <button
              key={v}
              aria-pressed={view === v}
              onClick={() => setView(v)}
              className={`min-h-9 cursor-pointer rounded-md px-3 text-[12px] font-medium capitalize transition-colors ${
                view === v ? "bg-surface-2 text-text" : "text-text-3 hover:text-text"
              }`}
            >
              {v}
            </button>
          ))}
        </div>}
      </div>
    </header>
  );
}
