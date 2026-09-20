/**
 * One block's outlook for the farmer page: a few KB instead of the 500 KB all-India
 * day file. GET /api/farmer?block=<block_id>&date=YYYY-MM-DD
 */
import type { ForecastFile } from "@/lib/data";
import { fetchJSON, fetchDaily } from "@/lib/gz";
import type { AdvisoryFile } from "@/lib/advisory";
import type { BlockMeta } from "@/lib/store";
import type { FarmerSlice } from "@/lib/farmer";

const cache = new Map<string, Promise<unknown>>();

// Fetch the static data files over HTTP from this same site: on Vercel they live on the
// CDN, not in the function's filesystem. Cached per server instance.
function json<T>(origin: string, rel: string, daily = false): Promise<T> {
  const url = `${origin}/data/${rel}`;
  if (!cache.has(url)) {
    const p = daily ? fetchDaily<T>(url) : fetchJSON<T>(url);
    p.catch(() => cache.delete(url));               // don't cache a missing file forever
    cache.set(url, p);
  }
  return cache.get(url) as Promise<T>;
}

interface Crops { by_state: Record<string, string[]>; default: string[] }

export async function GET(request: Request) {
  const url = new URL(request.url);
  const get = <T,>(rel: string) => json<T>(url.origin, rel);
  const getDaily = <T,>(rel: string) => json<T>(url.origin, rel, true);
  const id = url.searchParams.get("block") ?? "";
  const date = url.searchParams.get("date") ?? "";
  if (date !== "live" && !/^\d{4}-\d{2}-\d{2}$/.test(date))
    return Response.json({ error: "date must be YYYY-MM-DD or live" }, { status: 400 });

  const blocks = await get<BlockMeta[]>("blocks_index.json");
  const b = blocks.find((x) => x.id === id);
  if (!b) return Response.json({ error: `unknown block ${id}` }, { status: 404 });

  let fc: ForecastFile, adv: AdvisoryFile | null;
  try {
    fc = await getDaily<ForecastFile>(`forecast/${date}`);
  } catch {
    return Response.json({ error: `no forecast for ${date}` }, { status: 404 });
  }
  try { adv = await getDaily<AdvisoryFile>(`advisory/${date}`); } catch { adv = null; }
  const crops = await get<Crops>("crops.json").catch(() => ({ by_state: {}, default: ["rice", "maize"] }));
  const stateCrops = Object.entries(crops.by_state).find(([s]) => b.state.toLowerCase().includes(s.toLowerCase()))?.[1];

  const i = b.i;
  const ev = (k: "onset" | "dry10" | "heavy") => [0, 1, 2, 3].map((w) => ({
    p: fc.events[k].p[w][i], clim: fc.events[k].clim[w][i],
  }));
  const slice: FarmerSlice = {
    issued: fc.issued,
    source: fc.source,
    block: { id: b.id, name: b.name, district: b.district, state: b.state, names: b.names },
    crops: stateCrops ?? crops.default,
    cmri: [0, 1, 2, 3].map((w) => fc.cmri[w][i]),
    onset: ev("onset"), dry: ev("dry10"), heavy: ev("heavy"),
    onset_status: fc.onset_status?.[i] ?? null,
    sowing_rain_doy: fc.sowing_rain_doy?.[i] ?? null,
    advice: adv?.advisories[String(i)] ?? [],
  };
  return Response.json(slice, { headers: { "Cache-Control": "public, max-age=3600" } });
}
