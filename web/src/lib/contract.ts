/**
 * Advisory -> delivery-service contract (docs/DELIVERY_BRIEF.md §2a).
 * Mirrors src/export/advisory_contract.py; keep the two in step.
 * All calls go through /api/delivery (app/api/delivery), which holds the key of the
 * WhatsApp delivery service in act_1/.
 */
import type { Advice } from "./advisory";
import type { ForecastFile } from "./data";
import type { BlockMeta } from "./store";

const CMRI = ["normal", "watch", "warning", "alert"] as const;
const CONF = ["high", "medium", "low", "low"] as const;
const API = "/api/delivery";

// The delivery service names crops by its own ids (act/content/locales/*.yaml `crops`).
const CROP_ID: Record<string, string> = { rice: "paddy", pigeonpea: "tur" };
// SWITCH_CROP carries the crop id the district's plan names (src/advisory/sources.py). Only the
// fallback ladder (no plan for that district) has free text instead, and then we do not switch.
const SOW_WINDOW = 13;

const addDays = (iso: string, n: number) => {
  const d = new Date(iso + "T00:00:00Z"); d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
};

function deliveryParams(date: string, crop: string, tid: string, params: Record<string, unknown>) {
  const p: Record<string, unknown> = { ...params };
  const sowBy = addDays(date, SOW_WINDOW);
  if (tid === "SOW_NOW") p.sow_by = sowBy;
  if (tid === "SWITCH_CROP") {
    if (p.alternative) p.sow_by = sowBy;              // plan-backed: alternative is already a crop id
    else { tid = "DELAY_SOWING"; p.wait_until ??= sowBy; }   // indicative ladder: wait, don't switch
  }
  return [tid, p] as const;
}

export function toContract(adv: Advice, b: BlockMeta, fc: ForecastFile) {
  const [crop, engineTid, , engineParams] = adv;
  const date = fc.issued;
  const [tid, params] = deliveryParams(date, crop, engineTid, engineParams);
  const pct = (v: number) => (v < 0 ? 0 : Math.round(v) / 100);   // -1: onset already came
  return {
    advisory_id: `${b.id}_${date}_${crop}_${engineTid.toLowerCase()}`,
    issued_at: `${date}T06:00:00+05:30`,
    valid_from: date,
    valid_to: (params.wait_until as string | undefined) ?? addDays(date, SOW_WINDOW),
    product: fc.product,
    block: { block_id: b.id, name: b.name, district: b.district, state: b.state },
    cmri_class: CMRI[fc.cmri[0][b.i]] ?? "normal",
    crop: CROP_ID[crop] ?? crop,
    template_id: tid,
    params,
    weeks: [0, 1, 2, 3].map((w) => ({
      week: w + 1,
      onset: pct(fc.events.onset.p[w][b.i]),
      dry_spell: pct(fc.events.dry10.p[w][b.i]),
      heavy_rain: pct(fc.events.heavy.p[w][b.i]),
      confidence: CONF[w],
    })),
    requires_approval: true,
  };
}
export type ContractAdvisory = ReturnType<typeof toContract>;

export interface Health { connected: boolean; whatsapp?: string; subscribers?: number; languages: { code: string; name: string }[] }
export interface Preview {
  advisory_id: string; language: string; review_status: string; verdict: string;
  whatsapp_text: string; card_url: string; voice_state: string | null; voice_url: string | null;
}
export interface LogRow {
  advisory_id: string; subscriber_id: string; channel: string; language: string; status: string;
  ts: string; error: string | null; block_id: string; provider: string; message_ref: string | null;
}
export interface Audience { total: number; farmers: number; by_language: Record<string, number> }

async function call<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${API}/${path}`, body === undefined ? { cache: "no-store" } : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const d = (data as { detail?: unknown }).detail;
    throw new Error(typeof d === "string" ? d : d ? JSON.stringify(d).slice(0, 200) : `HTTP ${r.status}`);
  }
  return data as T;
}

/** null = the delivery service isn't connected or isn't reachable. */
export const health = () => call<Health>("health").catch(() => null);
export const audience = (blockId: string) => call<Audience>(`subscribers?block_id=${encodeURIComponent(blockId)}`);
/** Hold for approval (idempotent: re-posting the same advisory is a no-op). */
/** The service's view of one advisory (brief §2a response). */
export interface Summary {
  advisory_id: string; state: "pending_approval" | "approved" | "rejected" | string;
  recipients: number; languages: string[]; approved_by: string | null; approved_ts: string | null; warnings: string[];
  /** Who the service deliberately left out, and why: a crop already harvested, an irrigated farm,
   *  a village the advisory does not cover, or a farmer told the same thing days ago. */
  event?: string; not_sent?: number; left_out?: { subscriber_id: string; reason: string }[];
}
export const submit = (a: ContractAdvisory) => call<Summary>("advisories", a);
export const preview = (id: string, lang: string) =>
  call<Preview>(`advisories/${encodeURIComponent(id)}/preview?lang=${lang}`);
/** The officer's sign-off: only now does anything reach a farmer. */
export const approve = (id: string, by: string, note?: string) =>
  call<Summary>(`advisories/${encodeURIComponent(id)}/approve`, { approved_by: by, note });
/** Hold an advisory back: it is never sent. */
export const reject = (id: string, by: string, note?: string) =>
  call<Summary>(`advisories/${encodeURIComponent(id)}/reject`, { approved_by: by, note });
export const record = (id: string) => call<Summary & { received_ts: string; note: string | null }>(`advisories/${encodeURIComponent(id)}`);
export const dispatchLog = (blockId?: string, limit = 200) =>
  call<LogRow[]>(`dispatch/log?limit=${limit}${blockId ? `&block_id=${encodeURIComponent(blockId)}` : ""}`);

/** Counts across every advisory the service has handled (brief §2c). */
export interface DispatchSummary {
  total: number;
  by_status: Record<string, number>; by_channel: Record<string, number>;
  by_language: Record<string, number>; by_block: Record<string, number>; by_provider: Record<string, number>;
}
export const dispatchSummary = (since?: string) =>
  call<DispatchSummary>(`dispatch/summary${since ? `?since=${encodeURIComponent(since)}` : ""}`);
