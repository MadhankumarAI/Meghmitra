import { create } from "zustand";

export type EventKey = "cmri" | "onset" | "dry10" | "heavy";
export type Week = 1 | 2 | 3 | 4;

export interface BlockMeta {
  i: number;
  id: string;
  name: string;
  district: string;
  state: string;
  /** bounding box [west, south, east, north] */
  bb: [number, number, number, number];
  /** name in Indian scripts, from Wikidata, when matched: kn, hi, te, ta, mr */
  names?: Partial<Record<string, string>>;
}

interface ConsoleState {
  /** "replay": the validated 2023 hindcast; "live": today's data from NOAA GFS */
  mode: "replay" | "live";
  setMode: (m: "replay" | "live") => void;
  liveIdx: number;
  setLiveIdx: (i: number) => void;
  /** Delivery Centre: what the WhatsApp service has actually sent (act_1) */
  delivery: boolean;
  setDelivery: (d: boolean) => void;
  /** "Understand" mode: animated atmosphere (wind, pressure, moisture) with narration */
  understand: boolean;
  setUnderstand: (u: boolean) => void;
  /** the village or panchayat the user searched for, if they searched by that name */
  place: string | null;
  setPlace: (p: string | null) => void;
  /** that village's own chance of a 10+ day dry spell, where CHIRPS gives it one */
  placeChance: number | null;
  /** [low, high] the village shading is stretched across at this zoom, or null when the map is
   *  painting the national scale. The legend reads this: the colours must never be unexplained. */
  villageRange: [number, number] | null;
  setVillageRange: (r: [number, number] | null) => void;
  setPlaceChance: (p: number | null) => void;
  /** the user's own place: their block, and the point they were located at or searched for */
  home: { i: number; lon: number; lat: number; name: string } | null;
  setHome: (h: { i: number; lon: number; lat: number; name: string } | null) => void;
  /** which atmosphere fields are drawn, and what colours the wind streaks */
  layers: { wind: boolean; moist: boolean; heat: boolean; press: boolean };
  toggleLayer: (k: "wind" | "moist" | "heat" | "press") => void;
  windBy: "speed" | "moisture";
  setWindBy: (w: "speed" | "moisture") => void;
  /** issue date being shown (YYYY-MM-DD); the time machine moves this */
  date: string | null;
  setDate: (d: string) => void;
  dayPlaying: boolean;
  setDayPlaying: (p: boolean) => void;
  event: EventKey;
  week: Week;
  playing: boolean;
  view: "standard" | "expert";
  hovered: number | null;
  selected: number | null;
  /** a bounding box the map should fly to (set by search), consumed by the map */
  focus: [number, number, number, number] | null;
  setFocus: (bb: [number, number, number, number] | null) => void;
  setEvent: (e: EventKey) => void;
  setWeek: (w: Week) => void;
  setPlaying: (p: boolean) => void;
  setView: (v: "standard" | "expert") => void;
  setHovered: (i: number | null) => void;
  setSelected: (i: number | null) => void;
}

export const useConsole = create<ConsoleState>((set) => ({
  mode: "replay",
  setMode: (mode) => set({ mode, understand: mode === "live" ? true : false, liveIdx: 0, dayPlaying: false }),
  liveIdx: 0,
  setLiveIdx: (liveIdx) => set({ liveIdx }),
  delivery: false,
  setDelivery: (delivery) => set({ delivery }),
  understand: false,
  setUnderstand: (understand) => set({ understand }),
  place: null,
  setPlace: (place) => set({ place, placeChance: null }),   // the number is set right after, if there is one
  placeChance: null,
  setPlaceChance: (placeChance) => set({ placeChance }),
  villageRange: null,
  setVillageRange: (villageRange) => set({ villageRange }),
  home: null,
  setHome: (home) => {
    set({ home });
    try {                                   // it should still be their place tomorrow
      if (home) localStorage.setItem("meghmitra.home", JSON.stringify(home));
      else localStorage.removeItem("meghmitra.home");
    } catch { /* private window, or storage blocked */ }
  },
  layers: { wind: true, moist: true, heat: true, press: true },
  toggleLayer: (k) => set((s) => ({ layers: { ...s.layers, [k]: !s.layers[k] } })),
  windBy: "speed",
  setWindBy: (windBy) => set({ windBy }),
  date: null,
  setDate: (date) => set({ date }),
  dayPlaying: false,
  setDayPlaying: (dayPlaying) => set({ dayPlaying }),
  event: "cmri",
  week: 1,
  playing: false,
  view: "standard",
  hovered: null,
  selected: null,
  focus: null,
  setFocus: (focus) => set({ focus }),
  setEvent: (event) => set({ event }),
  setWeek: (week) => set({ week }),
  setPlaying: (playing) => set({ playing }),
  setView: (view) => set({ view }),
  setHovered: (hovered) => set({ hovered }),
  setSelected: (selected) => set({ selected }),
}));
