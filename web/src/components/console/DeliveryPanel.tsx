"use client";

/**
 * Delivery Centre: what has actually reached farmers. Every number comes from the WhatsApp
 * delivery service (act_1) through /api/delivery — its dispatch log, its summary and its health.
 * Nothing here is computed in the browser except the join from block_id to block name.
 */
import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { X, RefreshCw, Loader2, AlertTriangle, Radio, Users, MessageSquare } from "lucide-react";
import { useConsole, type BlockMeta } from "@/lib/store";
import { health, dispatchLog, dispatchSummary, type Health, type LogRow, type DispatchSummary } from "@/lib/contract";

const STATUS_TONE: Record<string, string> = {
  read: "var(--cmri-normal)", delivered: "var(--onset)", sent: "var(--focus)",
  queued: "var(--text-3)", failed: "var(--cmri-alert)",
};
const ORDER = ["queued", "sent", "delivered", "read", "failed"];
const hhmm = (iso: string) => new Date(iso).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false });
const day = (iso: string) => new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short" });

export default function DeliveryPanel({ blocks }: { blocks: BlockMeta[] | null }) {
  const open = useConsole((s) => s.delivery);
  const setOpen = useConsole((s) => s.setDelivery);
  const [conn, setConn] = useState<Health | null | undefined>(undefined);
  const [sum, setSum] = useState<DispatchSummary | null>(null);
  const [log, setLog] = useState<LogRow[] | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!open) return;
    let live = true;
    const load = () => {
      health().then((h) => { if (live) setConn(h); });
      dispatchSummary().then((d) => { if (live) setSum(d); }).catch(() => { if (live) setSum(null); });
      dispatchLog(undefined, 40).then((r) => { if (live) setLog(r); }).catch(() => { if (live) setLog(null); });
    };
    load();
    const t = setInterval(load, 5000);
    return () => { live = false; clearInterval(t); };
  }, [open, tick]);

  const name = (id: string) => blocks?.find((b) => b.id === id)?.name ?? id.slice(-6);
  const langName = (c: string) => conn?.languages.find((l) => l.code === c)?.name ?? c;
  const total = sum?.total ?? 0;

  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-3 md:p-6"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, transition: { duration: 0.15 } }}
          onClick={() => setOpen(false)}>
          <motion.div role="dialog" aria-modal="true" aria-labelledby="dc-title"
            initial={{ opacity: 0, y: 14, scale: 0.99 }} animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, transition: { duration: 0.15 } }}
            transition={{ type: "spring", stiffness: 380, damping: 34 }}
            onClick={(e) => e.stopPropagation()}
            className="panel flex h-[min(86vh,760px)] w-full max-w-4xl flex-col overflow-hidden">

            <header className="flex items-center gap-3 border-b border-line px-6 py-4">
              <div>
                <h2 id="dc-title" className="text-[17px] font-semibold leading-tight">Delivery Centre</h2>
                <p className="text-[12px] text-text-3">What has actually reached farmers on WhatsApp</p>
              </div>
              <div className="ml-auto flex items-center gap-2">
                {conn && (
                  <span className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[12px] ${
                    conn.whatsapp === "simulator" ? "border-watch/40 text-watch" : "border-normal/40 text-normal"}`}>
                    <Radio size={12} /> {conn.whatsapp === "simulator" ? "Simulator" : "WhatsApp live"}
                  </span>
                )}
                <button onClick={() => setTick((n) => n + 1)} aria-label="Refresh"
                  className="grid h-9 w-9 cursor-pointer place-items-center rounded-md text-text-2 hover:bg-surface-2 hover:text-text">
                  <RefreshCw size={15} />
                </button>
                <button aria-label="Close" onClick={() => setOpen(false)}
                  className="grid h-9 w-9 cursor-pointer place-items-center rounded-md text-text-2 hover:bg-surface-2 hover:text-text">
                  <X size={18} />
                </button>
              </div>
            </header>

            <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
              {conn === undefined ? (
                <div className="flex items-center gap-2 text-[13px] text-text-3"><Loader2 size={15} className="animate-spin" /> Connecting to the delivery service…</div>
              ) : conn === null ? (
                <div className="flex items-start gap-2.5 rounded-lg border border-line bg-surface-2/60 px-4 py-3 text-[13px] text-text-2">
                  <AlertTriangle size={16} className="mt-0.5 shrink-0 text-warning" />
                  <span>The WhatsApp delivery service isn’t reachable. Start it (<code className="text-text">act_1\scripts\run.ps1</code>)
                    and set <code className="text-text">DELIVERY_URL</code> in <code className="text-text">web/.env.local</code>.</span>
                </div>
              ) : (
                <div className="space-y-6">
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <Stat icon={MessageSquare} label="Messages" value={total} />
                    <Stat icon={Users} label="Subscribers" value={conn.subscribers ?? 0} />
                    <Stat icon={Radio} label="Blocks reached" value={Object.keys(sum?.by_block ?? {}).length} />
                    <Stat icon={MessageSquare} label="Languages" value={Object.keys(sum?.by_language ?? {}).length} />
                  </div>

                  {total > 0 && sum && (
                    <>
                      <section>
                        <h3 className="mb-2 text-[11px] uppercase tracking-wide text-text-3">How far each message got</h3>
                        <div className="flex h-3 overflow-hidden rounded-full bg-line">
                          {ORDER.filter((s) => sum.by_status[s]).map((s) => (
                            <motion.div key={s} className="h-full" style={{ background: STATUS_TONE[s] }} initial={{ width: 0 }}
                              animate={{ width: `${(sum.by_status[s] / total) * 100}%` }} transition={{ duration: 0.5 }} title={`${s}: ${sum.by_status[s]}`} />
                          ))}
                        </div>
                        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
                          {ORDER.filter((s) => sum.by_status[s]).map((s) => (
                            <span key={s} className="flex items-center gap-1.5 text-[12px] text-text-2">
                              <span className="h-2 w-2 rounded-full" style={{ background: STATUS_TONE[s] }} />
                              <span className="capitalize">{s}</span>
                              <span className="num text-text-3">{sum.by_status[s]}</span>
                            </span>
                          ))}
                        </div>
                      </section>

                      <div className="grid gap-5 sm:grid-cols-2">
                        <Breakdown title="Languages" rows={Object.entries(sum.by_language)} total={total} label={langName} />
                        <Breakdown title="Blocks" rows={Object.entries(sum.by_block)} total={total} label={name} />
                      </div>
                      {Object.keys(sum.by_provider).length > 0 && (
                        <p className="text-[11.5px] text-text-3">
                          Sent through: {Object.entries(sum.by_provider).map(([p, n]) => `${p === "meta-cloud" ? "WhatsApp Cloud API" : p} (${n})`).join(" · ")}
                        </p>
                      )}
                    </>
                  )}

                  <section>
                    <h3 className="mb-2 text-[11px] uppercase tracking-wide text-text-3">Recent activity</h3>
                    {log === null ? <div className="h-20 animate-pulse rounded-lg bg-surface-2/60" />
                      : log.length === 0 ? (
                        <p className="rounded-lg border border-line px-4 py-3 text-[12.5px] text-text-3">
                          Nothing sent yet. Approve advisories from a block’s <b className="text-text-2">Review &amp; send</b>, and they appear here.
                        </p>
                      ) : (
                        <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line">
                          <AnimatePresence initial={false}>
                            {log.map((r) => (
                              <motion.li key={`${r.advisory_id}|${r.subscriber_id}`} layout
                                initial={{ opacity: 0, backgroundColor: "rgba(92,200,255,0.10)" }}
                                animate={{ opacity: 1, backgroundColor: "rgba(0,0,0,0)" }} transition={{ duration: 0.8 }}
                                className="grid grid-cols-[96px_1fr_auto] items-center gap-3 px-3.5 py-2 text-[12px]">
                                <span className="num whitespace-nowrap text-text-3">{day(r.ts)} {hhmm(r.ts)}</span>
                                <span className="min-w-0 truncate text-text-2">
                                  {name(r.block_id)} · {langName(r.language)} · farmer ···{r.subscriber_id.slice(-4)}
                                  {r.error && <span className="block truncate text-[11px] text-text-3">{r.error}</span>}
                                </span>
                                <span className="rounded-full px-2 py-0.5 text-[11px] font-medium capitalize"
                                  style={{ background: `color-mix(in srgb, ${STATUS_TONE[r.status] ?? "var(--text-3)"} 18%, transparent)`, color: STATUS_TONE[r.status] ?? "var(--text-3)" }}>
                                  {r.status}
                                </span>
                              </motion.li>
                            ))}
                          </AnimatePresence>
                        </ul>
                      )}
                  </section>
                </div>
              )}
            </div>

            <footer className="border-t border-line px-6 py-3 text-[11.5px] text-text-3">
              Live from the delivery service’s own log · refreshes every 5 seconds
            </footer>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function Stat({ icon: Icon, label, value }: { icon: typeof Radio; label: string; value: number }) {
  return (
    <div className="rounded-xl border border-line bg-surface-2/50 px-3.5 py-3">
      <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-text-3"><Icon size={12} /> {label}</div>
      <div className="num mt-1 text-[24px] font-semibold leading-none">{value.toLocaleString("en-IN")}</div>
    </div>
  );
}

function Breakdown({ title, rows, total, label }: {
  title: string; rows: [string, number][]; total: number; label: (k: string) => string;
}) {
  return (
    <section>
      <h3 className="mb-2 text-[11px] uppercase tracking-wide text-text-3">{title}</h3>
      <ul className="space-y-1.5">
        {rows.sort((a, b) => b[1] - a[1]).slice(0, 6).map(([k, n]) => (
          <li key={k} className="grid grid-cols-[1fr_auto] gap-x-2 text-[12px]">
            <span className="truncate text-text-2">{label(k)}</span>
            <span className="num text-text-3">{n}</span>
            <span className="col-span-2 h-1 overflow-hidden rounded-full bg-line">
              <motion.span className="block h-full rounded-full bg-focus/70" initial={{ width: 0 }}
                animate={{ width: `${(n / total) * 100}%` }} transition={{ duration: 0.5 }} />
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
