/**
 * Village and panchayat lookup (src/export/villages_json.py). A farmer says "Kengeri", not
 * "Bengaluru South". This resolves the name they use to the block the forecast is issued for,
 * and the console then says which block that is.
 *
 * India has 649,309 villages, so the index is sharded by first letter and only the shard the
 * query needs is fetched (about 400 KB gzipped, once per letter). The files carry no
 * probabilities: the forecast stays at block scale, and the panel states that.
 */
import { fetchJSON } from "./gz";

/** [village name, index into blocks_index.json] */
export type Village = [string, number];

const shards = new Map<string, Promise<Village[]>>();

const key = (q: string) => {
  const c = q.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().trimStart()[0];
  return c >= "a" && c <= "z" ? c : "other";
};

/** The villages whose name starts with the same letter as the query. */
export function villagesFor(q: string): Promise<Village[]> {
  const k = key(q);
  if (!shards.has(k)) {
    shards.set(k, fetchJSON<{ v: Village[] }>(`/data/villages/${k}.json`)
      .then((f) => f.v)
      .catch(() => [] as Village[]));
  }
  return shards.get(k)!;
}

/** A village on the map: name, where it is, and the block that forecasts it. */
export interface Point { name: string; lat: number; lon: number; i: number }
type Cell = [string, number, number, number];

const CELL = 0.5;
const cells = new Map<string, Promise<Point[]>>();

const cellKey = (lat: number, lon: number) =>
  `${Math.floor((lat + 90) / CELL)}_${Math.floor((lon + 180) / CELL)}`;

function cell(k: string): Promise<Point[]> {
  if (!cells.has(k)) {
    cells.set(k, fetchJSON<Cell[]>(`/data/villages/cells/${k}.json`)
      .then((rows) => rows.map(([name, lat, lon, i]) => ({ name, lat, lon, i })))
      .catch(() => [] as Point[]));           // most cells are sea or empty
  }
  return cells.get(k)!;
}

/** Every village inside these bounds, fetching only the half-degree cells that overlap them. */
export async function villagesIn(w: number, s: number, e: number, n: number): Promise<Point[]> {
  const keys: string[] = [];
  for (let lat = Math.floor(s / CELL) * CELL; lat <= n; lat += CELL)
    for (let lon = Math.floor(w / CELL) * CELL; lon <= e; lon += CELL)
      keys.push(cellKey(lat + CELL / 2, lon + CELL / 2));
  if (keys.length > 24) return [];            // zoomed too far out to be useful
  const got = await Promise.all([...new Set(keys)].map(cell));
  return got.flat();
}

/** Village outlines, one file per block (src/export/villages_geom.py), fetched on demand. */
/** A village outline. `p` and `col` are filled in by the map when the village has its own
 *  number for the day on screen (src/export/villages_clim_json.py). */
/** `own` marks a village whose number is its own, not its block's (the dry-spell layer). */
export interface VillageProps { n: string; i: number; p?: number; col?: string; own?: number; v?: number }
type Shapes = GeoJSON.FeatureCollection<GeoJSON.Geometry, VillageProps>;
const shapes = new Map<number, Promise<Shapes["features"]>>();

function blockShapes(i: number): Promise<Shapes["features"]> {
  if (!shapes.has(i)) {
    shapes.set(i, fetchJSON<Shapes>(`/data/villages/geom/${i}.json`)
      .then((f) => f.features)
      .catch(() => []));                  // a block whose outlines are not built yet
  }
  return shapes.get(i)!;
}

/** One FeatureCollection for the blocks on screen, and nothing else. */
export async function villageShapes(ids: number[]): Promise<Shapes> {
  const got = await Promise.all(ids.map(blockShapes));
  return { type: "FeatureCollection", features: got.flat() };
}

/** What a village adds to its block's chance, in percentage points per half-month window
 *  (src/export/villages_clim_json.py). Zero where a village sits on its block's average. */
interface Clim { w: number[]; v: Record<string, number[]>; h?: Record<string, number[]> }
const clims = new Map<number, Promise<Clim | null>>();

function blockClim(i: number): Promise<Clim | null> {
  if (!clims.has(i)) {
    clims.set(i, fetchJSON<Clim>(`/data/villages/clim/${i}.json`).catch(() => null));
  }
  return clims.get(i)!;
}

/** The adjustment for each village in these blocks, for the half-month containing `doy`.
 *  `event` picks the dry spell ("v") or the heavy-rain day ("h"); the map returns empty for an
 *  event a file does not carry, which is how a layer without village detail says so. */
export async function villageAdjust(ids: number[], doy: number,
                                    event: "dry10" | "heavy" = "dry10"): Promise<Map<string, number>> {
  const out = new Map<string, number>();
  const got = await Promise.all(ids.map(blockClim));
  got.forEach((c, k) => {
    if (!c) return;
    const table = event === "heavy" ? c.h : c.v;
    if (!table) return;
    let w = 0;
    for (let j = 0; j < c.w.length; j++) if (doy >= c.w[j]) w = j;
    for (const [name, deltas] of Object.entries(table)) out.set(`${ids[k]}:${name}`, deltas[w] / 100);
  });
  return out;
}
