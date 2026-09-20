/**
 * Village and panchayat lookup (src/export/villages_json.py). A farmer says "Kengeri", not
 * "Bengaluru South". This resolves the name they use to the block the forecast is issued for,
 * and the console then says which block that is. The files carry no probabilities: the forecast
 * stays at block scale, and the panel states that.
 */
import { fetchJSON } from "./gz";

export interface Village { name: string; blockId: string; lat: number; lon: number }
type Row = [string, string, number, number];

let cache: Promise<Village[]> | null = null;

/** Every village in the states that have been built. Loaded once, on first search. */
export function loadVillages(): Promise<Village[]> {
  if (!cache) {
    cache = fetchJSON<Record<string, { state: string; n: number }>>("/data/villages/index.json")
      .then((idx) =>
        Promise.all(
          Object.keys(idx).map((k) =>
            fetchJSON<{ villages: Row[] }>(`/data/villages/${k}.json`)
              .then((f) => f.villages.map(([name, blockId, lat, lon]) => ({ name, blockId, lat, lon })))
              .catch(() => [] as Village[]),
          ),
        ).then((all) => all.flat()),
      )
      .catch(() => [] as Village[]);
  }
  return cache;
}
