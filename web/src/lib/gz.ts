/**
 * Fetch JSON that may be gzip-compressed on disk (*.json.gz, see scripts/stage-data.sh).
 * Checks the gzip magic bytes rather than trusting headers: some hosts send .gz files
 * with Content-Encoding: gzip (the browser has already unpacked them), others don't.
 * Works in the browser and in Node (route handlers).
 */
export async function fetchJSON<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  const buf = new Uint8Array(await r.arrayBuffer());
  if (buf[0] === 0x1f && buf[1] === 0x8b) {
    const stream = new Blob([buf]).stream().pipeThrough(new DecompressionStream("gzip"));
    return JSON.parse(await new Response(stream).text()) as T;
  }
  return JSON.parse(new TextDecoder().decode(buf)) as T;
}

/**
 * Daily files are gzipped on deploy but plain on the pipeline's own disk. Try whichever form
 * worked last first, so only the very first request can miss (no 404 per file).
 */
// Per folder (atmos/ is gzipped even locally). The first request in a folder probes; requests
// made while it is in flight wait for its answer instead of each missing once.
const format = new Map<string, Promise<".json.gz" | ".json">>();
export async function fetchDaily<T>(base: string): Promise<T> {
  const dir = base.slice(0, base.lastIndexOf("/"));
  const known = format.get(dir);
  if (known) {
    const ext = await known.catch(() => ".json.gz" as const);
    return fetchJSON<T>(base + ext);
  }
  let resolve!: (e: ".json.gz" | ".json") => void, reject!: (e: unknown) => void;
  format.set(dir, new Promise((a, b) => { resolve = a; reject = b; }));
  try {
    const v = await fetchJSON<T>(`${base}.json.gz`);
    resolve(".json.gz");
    return v;
  } catch {
    try {
      const v = await fetchJSON<T>(`${base}.json`);
      resolve(".json");
      return v;
    } catch (e) {
      format.delete(dir);                          // this file is missing: let the next one probe
      reject(e);
      throw e;
    }
  }
}
