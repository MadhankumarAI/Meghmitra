import type { Advice } from "./advisory";

/** One block's outlook, as served by /api/farmer. Probabilities are integer percent, -1 = n/a. */
export interface FarmerSlice {
  issued: string;
  source: string;
  block: { id: string; name: string; district: string; state: string; names?: Partial<Record<string, string>> };
  crops: string[];
  cmri: number[];
  onset: { p: number; clim: number }[];
  dry: { p: number; clim: number }[];
  heavy: { p: number; clim: number }[];
  onset_status: number | null;
  sowing_rain_doy: number | null;
  advice: Advice[];
}
