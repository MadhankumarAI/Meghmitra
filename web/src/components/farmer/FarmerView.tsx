"use client";

import { useEffect, useMemo, useState } from "react";
import { Sun, CloudRain, CloudSun, CloudLightning, Phone, Sprout, Clock, Droplets, ShieldCheck } from "lucide-react";
import type { FarmerSlice } from "@/lib/farmer";
import { UI, VERDICT, CROP_NAME, LANGS, fill, inTen, locale, type Lang } from "@/lib/i18n";
import { BrandMark, Wordmark, BRAND } from "@/components/Brand";

const TIER = {
  3: { bg: "#fde8e8", edge: "#c62828", ink: "#7f1414" },     // alert
  2: { bg: "#fff1e0", edge: "#e07b00", ink: "#7a3e00" },     // warning
  0: { bg: "#e7f5ec", edge: "#2e7d4f", ink: "#16432a" },     // no action
} as const;

const ICON: Record<string, typeof Sun> = {
  DELAY_SOWING: Clock, SOW_NOW: Sprout, SWITCH_CROP: Sprout, PREPARE_IRRIGATION: Droplets,
  DRY_SPELL_CONSERVE_MOISTURE: Sun, HEAVY_RAIN_PROTECT: CloudLightning, NONE: ShieldCheck,
};

const CACHE_KEY = (id: string, date: string) => `mungaru:${id}:${date}`;

export default function FarmerView({ blockId, lang: lang0, crop: crop0, date }: {
  blockId: string; lang: Lang; crop?: string; date: string;
}) {
  const [lang, setLang] = useState<Lang>(lang0);
  const [data, setData] = useState<FarmerSlice | null>(null);
  const [state, setState] = useState<"loading" | "ok" | "offline" | "missing">("loading");
  const [crop, setCrop] = useState<string | undefined>(crop0);

  useEffect(() => {
    let live = true;
    fetch(`/api/farmer?block=${encodeURIComponent(blockId)}&date=${date}`)
      .then(async (r) => {
        if (r.status === 404) { if (live) setState("missing"); return; }
        const d = (await r.json()) as FarmerSlice;
        if (!live) return;
        setData(d); setState("ok");
        try { localStorage.setItem(CACHE_KEY(blockId, date), JSON.stringify(d)); } catch {}
      })
      .catch(() => {
        // offline: fall back to the last copy this phone saw
        try {
          const s = localStorage.getItem(CACHE_KEY(blockId, date));
          if (s && live) { setData(JSON.parse(s)); setState("offline"); return; }
        } catch {}
        if (live) setState("missing");
      });
    return () => { live = false; };
  }, [blockId, date]);

  const activeCrop = crop && data?.crops.includes(crop) ? crop : data?.crops[0];
  const advice = useMemo(
    () => data?.advice.find((a) => a[0] === activeCrop) ?? null,
    [data, activeCrop],
  );

  const fmt = (d: string) =>
    new Date(d + "T00:00:00Z").toLocaleDateString(locale(lang), { day: "numeric", month: "short", timeZone: "UTC" });
  const fmtDoy = (doy: number) => fmt(isoFromDoy(Number(data!.issued.slice(0, 4)), doy));

  return (
    <div lang={lang} className="h-full overflow-y-auto bg-white text-[#10202e]" style={{ fontFamily: "var(--font-indic)" }}>
      <div className="mx-auto max-w-md px-4 pb-10 pt-4">
        {/* who this is from: the same mark the farmer sees on WhatsApp */}
        <div className="mb-4 flex items-center gap-2.5">
          <BrandMark size={34} />
          <div className="leading-tight">
            <Wordmark className="block text-[18px] text-[#1f4a33]" />
            <div className="text-[12px] tracking-wide text-[#5b6b62]">{BRAND.tagline}</div>
          </div>
        </div>
        {/* language: first thing a farmer may need to change */}
        <nav aria-label="Language" className="mb-4 flex gap-2">
          {LANGS.map((l) => (
            <button key={l.key} onClick={() => setLang(l.key)} aria-pressed={lang === l.key}
              className={`min-h-11 flex-1 cursor-pointer rounded-full border text-[16px] transition-colors ${
                lang === l.key ? "border-[#10202e] bg-[#10202e] text-white" : "border-[#c9d3dd] bg-white text-[#10202e]"}`}>
              {l.label}
            </button>
          ))}
        </nav>

        {state === "loading" && <Skeleton />}
        {state === "missing" && <p className="rounded-2xl bg-[#f3f5f8] p-5 text-[18px]">{UI.notFound[lang]}</p>}

        {data && (
          <>
            {state === "offline" && (
              <p role="status" className="mb-3 rounded-xl bg-[#fff7d6] px-4 py-2.5 text-[15px] text-[#5c4700]">{UI.offline[lang]}</p>
            )}

            <header className="mb-4">
              <div className="text-[15px] text-[#4a5b6b]">{UI.forYourField[lang]}</div>
              <h1 className="text-[26px] font-bold leading-tight">{data.block.names?.[lang] ?? data.block.name}</h1>
              <div className="text-[15px] text-[#4a5b6b]">
                {data.block.names?.[lang] && lang !== "en" ? `${data.block.name} · ` : ""}{data.block.district}, {data.block.state}
              </div>
            </header>

            {/* crop */}
            {data.crops.length > 1 && (
              <div className="mb-4">
                <div className="mb-1.5 text-[14px] font-semibold text-[#4a5b6b]">{UI.crop[lang]}</div>
                <div className="flex flex-wrap gap-2">
                  {data.crops.map((c) => (
                    <button key={c} onClick={() => setCrop(c)} aria-pressed={activeCrop === c}
                      className={`min-h-11 cursor-pointer rounded-full border px-4 text-[16px] ${
                        activeCrop === c ? "border-[#1d6b45] bg-[#e7f5ec] font-semibold text-[#16432a]" : "border-[#c9d3dd]"}`}>
                      {CROP_NAME[c]?.[lang] ?? c}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <Verdict advice={advice} lang={lang} fmt={fmt} />

            <OnsetStory data={data} lang={lang} fmtDoy={fmtDoy} />

            <section aria-labelledby="wk" className="mt-6">
              <h2 id="wk" className="mb-2 text-[18px] font-bold">{UI.next4[lang]}</h2>
              <div className="grid grid-cols-2 gap-2.5">
                {[0, 1, 2, 3].map((w) => <WeekTile key={w} w={w} data={data} lang={lang} fmt={fmt} />)}
              </div>
            </section>

            <a href="tel:18001801551"
              className="mt-6 flex min-h-14 items-center justify-center gap-3 rounded-2xl bg-[#10202e] px-4 text-white">
              <Phone size={22} aria-hidden />
              <span className="text-left leading-tight">
                <span className="block text-[17px] font-semibold">{UI.callHelp[lang]}</span>
                <span className="block text-[14px] opacity-80">{UI.kcc[lang]}</span>
              </span>
            </a>

            <footer className="mt-6 text-center text-[13px] leading-relaxed text-[#6a7a8a]">
              {UI.issued[lang]}: {fmt(data.issued)}
              <br />{UI.source[lang]}
            </footer>
          </>
        )}
      </div>
    </div>
  );
}

function Verdict({ advice, lang, fmt }: {
  advice: FarmerSlice["advice"][number] | null; lang: Lang; fmt: (d: string) => string;
}) {
  const tid = advice?.[1] ?? "NONE";
  const v = VERDICT[tid] ?? VERDICT.NONE;
  const tier = (advice?.[2] ?? 0) >= 3 ? 3 : advice ? 2 : 0;
  const c = TIER[tier];
  const Icon = ICON[tid] ?? ShieldCheck;
  const p = advice?.[3] ?? {};
  const vars = {
    d: p.wait_until ? fmt(String(p.wait_until)) : "",
    w: String(p.delay_weeks ?? ""),
  };
  return (
    <section aria-live="polite" className="rounded-2xl border-l-8 p-5" style={{ background: c.bg, borderColor: c.edge, color: c.ink }}>
      <div className="flex items-start gap-3">
        <Icon size={40} strokeWidth={2} aria-hidden className="mt-0.5 shrink-0" />
        <h2 className="text-[clamp(20px,6.5vw,26px)] font-bold leading-tight">{v.title[lang]}</h2>
      </div>
      {typeof p.p_event === "number" && (
        <p className="mt-3 text-[17px] leading-snug">
          {tid === "HEAVY_RAIN_PROTECT" ? UI.heavyRain[lang] : UI.drySpell[lang]}:{" "}
          <strong>{inTen(p.p_event, lang)}</strong>{" "}
          <span className="opacity-80">({UI.usually[lang]} {inTen(Number(p.p_clim ?? 0), lang)})</span>
        </p>
      )}
      <h3 className="mt-4 text-[15px] font-semibold uppercase tracking-wide opacity-80">{UI.whatToDo[lang]}</h3>
      <ol className="mt-1.5 space-y-2">
        {v.actions.map((a, k) => (
          <li key={k} className="flex gap-3 text-[18px] leading-snug">
            <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-white/70 text-[15px] font-bold">{k + 1}</span>
            <span>{fill(a[lang], vars)}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

function OnsetStory({ data, lang, fmtDoy }: { data: FarmerSlice; lang: Lang; fmtDoy: (d: number) => string }) {
  const s = data.onset_status, doy = data.sowing_rain_doy ?? -1;
  let text: string | null = null;
  if (s === 0) text = UI.arrived[lang];
  else if (s === 1 && doy > 0) text = fill(UI.holding[lang], { d: fmtDoy(doy) });
  else if (s === 3 && doy > 0) text = fill(UI.failed[lang], { d: fmtDoy(doy) });
  else if (s === 2) text = UI.pending[lang];
  return text ? <p className="mt-4 rounded-xl bg-[#f3f5f8] px-4 py-3 text-[16px] leading-snug">{text}</p> : null;
}

function WeekTile({ w, data, lang, fmt }: { w: number; data: FarmerSlice; lang: Lang; fmt: (d: string) => string }) {
  const dry = data.dry[w], hv = data.heavy[w];
  const start = addDays(data.issued, 7 * w);
  const heavy = hv.p >= 20 && hv.p >= 2 * Math.max(hv.clim, 1);
  const Icon = heavy ? CloudLightning : dry.p >= 50 ? Sun : dry.p >= 30 ? CloudSun : CloudRain;
  const risky = heavy || dry.p - dry.clim >= 10;
  const main = heavy ? hv : dry;
  return (
    <div className={`rounded-2xl border-2 p-3.5 ${risky ? "border-[#e07b00] bg-[#fff8ee]" : "border-[#e1e7ee]"}`}>
      <div className="flex items-baseline justify-between">
        <span className="text-[16px] font-bold">{UI.week[lang]} {w + 1}</span>
        <span className="text-[13px] text-[#4a5b6b]">{fmt(start)}</span>
      </div>
      <Icon size={34} className="my-1.5" aria-hidden color={heavy ? "#3a55c9" : dry.p >= 50 ? "#c66a00" : "#4a6b8a"} />
      <div className="text-[14px] text-[#4a5b6b]">{heavy ? UI.heavyRain[lang] : UI.drySpell[lang]}</div>
      <div className="text-[19px] font-bold leading-tight">{main.p < 0 ? "—" : inTen(main.p / 100, lang)}</div>
      {main.p >= 0 && (
        <div className="text-[13px] text-[#6a7a8a]">{UI.usually[lang]} {inTen(main.clim / 100, lang)}</div>
      )}
    </div>
  );
}

function Skeleton() {
  return (
    <div aria-hidden className="space-y-3">
      <div className="h-16 animate-pulse rounded-xl bg-[#eef2f6]" />
      <div className="h-48 animate-pulse rounded-2xl bg-[#eef2f6]" />
      <div className="grid grid-cols-2 gap-2.5">{[0, 1, 2, 3].map((k) => <div key={k} className="h-32 animate-pulse rounded-2xl bg-[#eef2f6]" />)}</div>
    </div>
  );
}

// all date arithmetic in UTC: local-midnight + toISOString would shift a day back in IST
const addDays = (iso: string, n: number) => {
  const d = new Date(iso + "T00:00:00Z"); d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
};
const isoFromDoy = (year: number, doy: number) => {
  const d = new Date(Date.UTC(year, 0, doy));
  return d.toISOString().slice(0, 10);
};
