"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
import { useConsole } from "@/lib/store";
import { loadBlocks, loadForecast, loadSeason, layerValues, type ForecastFile, type SeasonIndex } from "@/lib/data";
import type { BlockMeta } from "@/lib/store";
import TopBar from "./TopBar";
import TimeBar from "./TimeBar";
import Legend from "./Legend";
import HoverCard from "./HoverCard";
import BlockPanel from "./BlockPanel";
import UnderstandPanel from "./UnderstandPanel";
import Locate from "./Locate";
import HomeMarker from "../map/HomeMarker";
import VillageLayer from "../map/VillageLayer";
import { AnimatePresence } from "motion/react";
import { loadFrame, loadOrography, loadLiveIndex, era5Key, heatOf, narrate, type Frame, type LiveIndex } from "@/lib/atmos";
import LiveBar from "./LiveBar";
import Intro from "./Intro";
import Briefing from "./Briefing";
import DeliveryPanel from "./DeliveryPanel";

const AtmosLayer = dynamic(() => import("@/components/map/AtmosLayer"), { ssr: false });
const MapLabels = dynamic(() => import("@/components/map/MapLabels"), { ssr: false });
const MapView = dynamic(() => import("@/components/map/MapView"), {
  ssr: false,
  loading: () => <div className="absolute inset-0 bg-(--ocean)" />,
});

const SEASON_YEAR = 2023;
const START_DATE = "2023-06-01";
const PREFETCH = 4;

const doyOf = (d: string | null) => {
  if (!d) return 152;
  const t = new Date(d + "T00:00:00Z");
  return Math.floor((t.getTime() - Date.UTC(t.getUTCFullYear(), 0, 0)) / 86400000);
};

export default function Console() {
  const event = useConsole((s) => s.event);
  const week = useConsole((s) => s.week);
  const date = useConsole((s) => s.date);
  const understand = useConsole((s) => s.understand);
  const mode = useConsole((s) => s.mode);
  const liveIdx = useConsole((s) => s.liveIdx);
  const [liveIndex, setLiveIndex] = useState<LiveIndex | null>(null);
  // today's block outlook from the daily live run (src/live/run_live.py); null = not available
  const [liveFc, setLiveFc] = useState<ForecastFile | null | undefined>(undefined);
  const [liveMsg, setLiveMsg] = useState<string | null>(null);
  // the frame that last arrived, keyed, so "loading" is derived rather than set in the effect
  const [got, setGot] = useState<{ key: string; frame: Frame | null } | null>(null);
  const [elev, setElev] = useState<number[] | null>(null);
  const [season, setSeason] = useState<SeasonIndex | null>(null);
  const [forecast, setForecast] = useState<ForecastFile | null>(null);
  const [blocks, setBlocks] = useState<BlockMeta[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (process.env.NODE_ENV === "development") (window as unknown as { __console: typeof useConsole }).__console = useConsole;
    Promise.all([loadSeason(SEASON_YEAR), loadBlocks()])
      .then(([s, b]) => {
        setSeason(s);
        setBlocks(b);
        if (!useConsole.getState().date) useConsole.getState().setDate(s.dates.includes(START_DATE) ? START_DATE : s.dates[0]);
      })
      .catch((e) => setError(String(e)));
  }, []);

  // follow the issue date; keep showing the previous day until the next one is ready
  useEffect(() => {
    if (!date || !season) return;
    let live = true;
    loadForecast(date).then((f) => { if (live) setForecast(f); }).catch((e) => setError(String(e)));
    const k = season.dates.indexOf(date);
    for (const d of season.dates.slice(k + 1, k + 1 + PREFETCH)) loadForecast(d).catch(() => {});
    return () => { live = false; };
  }, [date, season]);

  // atmosphere for the date on screen (ERA5 06 UTC); keep the old frame until the new one lands
  useEffect(() => {
    if (mode !== "live") return;
    if (!liveIndex) loadLiveIndex().then(setLiveIndex).catch(() => setError("Live atmosphere data isn't available right now."));
    if (liveFc === undefined) {
      loadForecast("live").then(setLiveFc).catch(() => {
        setLiveFc(null);
        // the live run explains itself when it declines to publish (season over, patchy data)
        fetch("/data/forecast/live_status.json").then((r) => (r.ok ? r.json() : null))
          .then((st) => setLiveMsg(st?.message ?? null)).catch(() => {});
      });
    }
  }, [mode, liveIndex, liveFc]);

  const wantKey = mode === "live" ? liveIndex?.frames[liveIdx]?.key ?? null : date ? era5Key(date) : null;
  useEffect(() => {
    if (!understand || !wantKey) return;
    let live = true;
    const key = wantKey;
    loadOrography().then((o) => { if (live && o) setElev(o.elev); });
    loadFrame(key)
      .then((f) => { if (live) setGot({ key, frame: f }); })
      .catch(() => { if (live) setGot({ key, frame: null }); });
    return () => { live = false; };
  }, [understand, wantKey]);
  const frame = got?.frame ?? null;                 // keep showing the previous frame until the next lands
  const frameLoading = understand && got?.key !== wantKey;

  // share of monsoon blocks where monsoon rain has arrived (confirmed or holding)
  const coverage = useMemo(() => {
    const st = forecast?.onset_status;
    if (!st) return null;
    let arrived = 0, n = 0;
    st.forEach((v, i) => { if ((forecast!.cmri[0][i] ?? 0) >= 0) { n++; if (v === 0 || v === 1) arrived++; } });
    return n ? arrived / n : null;
  }, [forecast]);

  // their own place, remembered between visits; a phone opens on it rather than on all of India
  const restored = useRef(false);
  useEffect(() => {
    if (restored.current || !blocks) return;
    restored.current = true;
    let home: { i: number; lon: number; lat: number; name: string } | null = null;
    try { home = JSON.parse(localStorage.getItem("meghmitra.home") ?? "null"); } catch { home = null; }
    if (!home || !blocks[home.i]) return;
    const s = useConsole.getState();
    s.setHome(home);
    if (window.matchMedia("(max-width: 767px)").matches) {
      s.setSelected(home.i);
      s.setFocus(blocks[home.i].bb);
    }
  }, [blocks]);

  // one reading of the atmosphere, shared by the map (axis label, heat) and the panel (words)
  const heat = frame ? heatOf(frame, elev) : null;
  const reading = frame ? narrate(frame.diag, mode === "live" ? null : coverage, frame.t, heat) : null;

  // the forecast on screen: the hindcast day in replay, today's live run in live mode
  const shown = mode === "live" ? liveFc ?? null : forecast;
  const values = useMemo(
    () => (shown ? layerValues(shown, event, week)
      : mode === "live" ? new Float32Array(forecast?.blocks ?? 0).fill(NaN) : null),
    [shown, forecast, event, week, mode],
  );

  return (
    <main className="relative h-full w-full overflow-hidden">
      <MapView values={values} />
      <MapLabels blocks={blocks} />
      <VillageLayer blocks={blocks} values={values} doy={doyOf(shown?.issued ?? date)} />
      <HomeMarker blocks={blocks} />
      {understand && <AtmosLayer frame={frame} elev={elev} phase={reading?.phase ?? null} />}
      <TopBar forecast={shown} blocks={blocks} />
      {mode === "live" && liveFc === null && (
        <div role="status" className="panel absolute left-1/2 top-[72px] z-20 -translate-x-1/2 px-4 py-2.5 text-[13px] text-text-2">
          {liveMsg ?? "Today’s block outlook hasn’t been published yet."} The atmosphere below is live from NOAA GFS.
        </div>
      )}
      {!understand && <Legend />}
      <AnimatePresence>{!understand && shown && blocks && <Briefing key="briefing" forecast={shown} blocks={blocks} />}</AnimatePresence>
      <AnimatePresence>{understand && <UnderstandPanel frame={frame} loading={frameLoading} reading={reading} heat={heat} />}</AnimatePresence>
      {mode === "live"
        ? <LiveBar index={liveIndex} />
        : <TimeBar dates={season?.dates ?? []} issued={forecast?.issued ?? date ?? START_DATE} />}
      {shown && blocks && <HoverCard forecast={shown} blocks={blocks} />}
      {shown && blocks && <BlockPanel forecast={shown} blocks={blocks} />}
      <Locate />
      <DeliveryPanel blocks={blocks} />
      <Intro ready={!!(season && blocks) || !!error} />
      {error && (
        <div role="alert" className="panel absolute left-1/2 top-24 -translate-x-1/2 px-4 py-3 text-sm text-alert">
          Couldn’t load forecast data: {error}
        </div>
      )}
    </main>
  );
}
