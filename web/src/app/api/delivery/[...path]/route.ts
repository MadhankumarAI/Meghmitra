/**
 * Server-side bridge to the WhatsApp delivery service (act_1/, docs/DELIVERY_BRIEF.md).
 *
 *   DELIVERY_URL=http://127.0.0.1:8000     where the service runs (or its ngrok address)
 *   DELIVERY_API_KEY=...                    its ADMIN_API_KEY; stays on the server
 *
 * Only the routes the console needs are forwarded. Subscriber lists are reduced to counts, so
 * farmers' phone numbers never reach a browser. Unset DELIVERY_URL = not connected (503).
 */
const BASE = (process.env.DELIVERY_URL ?? "").replace(/\/$/, "");
const KEY = process.env.DELIVERY_API_KEY ?? "";

const ALLOW: [string, RegExp][] = [
  ["GET", /^health$/],
  ["POST", /^advisories$/],
  ["GET", /^advisories\/[\w.-]+\/preview$/],
  ["POST", /^advisories\/[\w.-]+\/approve$/],
  ["POST", /^advisories\/[\w.-]+\/reject$/],
  ["GET", /^advisories\/[\w.-]+$/],
  ["GET", /^dispatch\/(log|summary)$/],
  ["GET", /^subscribers$/],
  ["GET", /^media\/[\w./-]+\.(png|ogg|jpg)$/],
];

async function forward(req: Request, ctx: RouteContext<"/api/delivery/[...path]">) {
  const path = (await ctx.params).path.join("/");
  if (!ALLOW.some(([m, re]) => m === req.method && re.test(path)) || path.includes(".."))
    return Response.json({ detail: "not available through the console" }, { status: 404 });
  if (!BASE) return Response.json({ detail: "delivery service not connected" }, { status: 503 });

  const url = `${BASE}/${path}${new URL(req.url).search}`;
  let r: Response;
  try {
    r = await fetch(url, {
      method: req.method,
      headers: {
        "X-API-Key": KEY,
        "ngrok-skip-browser-warning": "1",          // the free tunnel's interstitial page
        ...(req.method === "POST" ? { "Content-Type": "application/json" } : {}),
      },
      body: req.method === "POST" ? await req.text() : undefined,
      cache: "no-store",
      signal: AbortSignal.timeout(60_000),           // first card render (headless Chromium) can be slow
    });
  } catch {
    return Response.json({ detail: "delivery service unreachable" }, { status: 502 });
  }

  if (path.startsWith("media/"))
    return new Response(r.body, { status: r.status, headers: { "Content-Type": r.headers.get("Content-Type") ?? "application/octet-stream", "Cache-Control": "private, max-age=300" } });

  const text = await r.text();
  let data: unknown;
  try { data = JSON.parse(text); } catch { data = { detail: text.slice(0, 300) }; }

  if (path === "subscribers" && Array.isArray(data)) {
    const live = (data as { opted_out?: boolean; language?: string; role?: string }[]).filter((s) => !s.opted_out);
    const by_language: Record<string, number> = {};
    for (const s of live) by_language[s.language ?? "?"] = (by_language[s.language ?? "?"] ?? 0) + 1;
    data = { total: live.length, farmers: live.filter((s) => s.role !== "officer").length, by_language };
  }
  if (path === "health" && data && typeof data === "object") {
    const h = data as { whatsapp?: string; languages?: Record<string, { name: string }>; subscribers?: number };
    data = { connected: r.ok, whatsapp: h.whatsapp, subscribers: h.subscribers,
             languages: Object.entries(h.languages ?? {}).map(([code, l]) => ({ code, name: l.name })) };
  }
  // media links point at the service itself; route them through here too
  const body = JSON.stringify(data).replaceAll(`${BASE}/media/`, "/api/delivery/media/")
    .replace(/"(card_url|voice_url)":"https?:\/\/[^"]*?\/media\//g, '"$1":"/api/delivery/media/');
  return new Response(body, { status: r.status, headers: { "Content-Type": "application/json" } });
}

export { forward as GET, forward as POST };
