"use client";

/**
 * Officer sign-off, in three steps: Review (what goes out, to whom, and why) → Approve (who signs,
 * with a note) → Track (delivery, live). Everything shown comes from the delivery service
 * (act_1/ via /api/delivery): recipients, languages, the rendered card, voice note and text,
 * approval records and the dispatch log. Nothing reaches a farmer before Approve.
 */
import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  X, Check, AlertTriangle, Mic, Loader2, Smartphone, Globe, RefreshCw, ShieldCheck,
  Users, ArrowRight, ArrowLeft, Ban, Radio, CheckCheck, Clock, Send,
} from "lucide-react";
import type { Advice } from "@/lib/advisory";
import { renderAdvice } from "@/lib/advisory";
import type { ForecastFile } from "@/lib/data";
import type { BlockMeta } from "@/lib/store";
import { LANGS, CROP_NAME } from "@/lib/i18n";
import {
  toContract, health, submit, preview, approve, reject, dispatchLog,
  type Health, type Preview, type LogRow, type Summary,
} from "@/lib/contract";

type Sub = Summary | { error: string };
type Step = "review" | "approve" | "track";
const STEP_LIST: { key: Step; label: string; hint: string }[] = [
  { key: "review", label: "Review", hint: "What goes out, and to whom" },
  { key: "approve", label: "Approve", hint: "Your sign-off" },
  { key: "track", label: "Track", hint: "Delivery, live" },
];
const DELIVERY = ["queued", "sent", "delivered", "read"] as const;
const CLASS = ["normal", "watch", "warning", "alert"] as const;
const OFFICER_KEY = "meghmitra.officer";

const ok = (s?: Sub): s is Summary => !!s && !("error" in s);
const isSent = (s?: Sub) => ok(s) && (s.state === "approved" || s.state === "dispatched");
const hhmm = (iso?: string | null) => iso
  ? new Date(iso).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }) : "";
const dmy = (iso: string) => new Date(iso + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" });

// first preview language when no farmer here has subscribed yet
function homeLang(state: string) {
  const s = state.toLowerCase();
  if (s.includes("karnataka")) return "kn";
  if (s.includes("tamil")) return "ta";
  if (s.includes("andhra") || s.includes("telangana")) return "te";
  if (s.includes("maharashtra")) return "mr";
  if (/(pradesh|bihar|rajasthan|haryana|jharkhand|chhattisgarh|uttarakhand|delhi)/.test(s)) return "hi";
  return "en";
}

function readOfficer() {
  try { return localStorage.getItem(OFFICER_KEY) ?? ""; } catch { return ""; }
}

export default function ReviewSend({ open, onClose, advice, block, forecast }: {
  open: boolean; onClose: () => void; advice: Advice[]; block: BlockMeta; forecast: ForecastFile;
}) {
  const items = useMemo(() => advice.map((a) => toContract(a, block, forecast)), [advice, block, forecast]);
  const [conn, setConn] = useState<Health | null | undefined>(undefined);
  const [attempt, setAttempt] = useState(0);
  const [subs, setSubs] = useState<Record<string, Sub>>({});
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [sel, setSel] = useState(0);
  const [pickedLang, setPickedLang] = useState<string | null>(null);
  const [view, setView] = useState<"whatsapp" | "web">("whatsapp");
  const [pv, setPv] = useState<{ key: string; data: Preview | null; error?: string } | null>(null);
  const [step, setStep] = useState<Step>("review");
  const [officer, setOfficer] = useState(readOfficer);
  const [note, setNote] = useState("");
  const [checked, setChecked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [log, setLog] = useState<LogRow[]>([]);

  // connect; hold every advisory for approval (idempotent) so the service can count recipients and render
  useEffect(() => {
    if (!open) return;
    let live = true;
    health().then(async (h) => {
      if (!live) return;
      setConn(h);
      if (!h) return;
      const got: Record<string, Sub> = {};
      for (const a of items) {
        got[a.advisory_id] = await submit(a).catch((e) => ({ error: String(e.message ?? e) }));
        if (!live) return;
        setSubs({ ...got });
      }
      const pending = items.filter((a) => ok(got[a.advisory_id]) && (got[a.advisory_id] as Summary).state === "pending_approval");
      setChosen(new Set(pending.map((a) => a.advisory_id)));
      // reopened after sending: go straight to tracking
      if (!pending.length && items.some((a) => isSent(got[a.advisory_id]))) setStep("track");
    });
    return () => { live = false; };
  }, [open, items, attempt]);

  // who receives what, from the service
  const recipients = items.reduce((n, a) => n + (chosen.has(a.advisory_id) && ok(subs[a.advisory_id]) ? (subs[a.advisory_id] as Summary).recipients : 0), 0);
  const farmerLangs = useMemo(() => {
    const s = new Set<string>();
    for (const a of items) { const x = subs[a.advisory_id]; if (ok(x)) x.languages.forEach((l) => s.add(l)); }
    return [...s];
  }, [items, subs]);
  const lang = pickedLang ?? farmerLangs[0] ?? homeLang(block.state);
  const langName = useCallback((code: string) =>
    conn?.languages.find((l) => l.code === code)?.name ?? LANGS.find((l) => l.key === code)?.label ?? code, [conn]);
  const allLangs = useMemo(() => {
    const all = conn?.languages?.length ? conn.languages.map((l) => l.code) : LANGS.map((l) => l.key as string);
    return [...farmerLangs, ...all.filter((c) => !farmerLangs.includes(c))];
  }, [conn, farmerLangs]);

  // phone preview: exactly what the service will send, re-polled until the voice note is ready
  const cur = items[sel];
  const pvKey = cur ? `${cur.advisory_id}|${lang}` : "";
  const ready = cur && ok(subs[cur.advisory_id]);
  useEffect(() => {
    if (!open || !conn || !ready || view !== "whatsapp") return;
    let live = true;
    const load = () => preview(cur.advisory_id, lang)
      .then((d) => { if (live) setPv({ key: pvKey, data: d }); })
      .catch((e) => { if (live) setPv((old) => old?.key === pvKey && old.data ? old : { key: pvKey, data: null, error: String(e.message ?? e) }); });
    load();
    const t = setInterval(load, 15_000);
    return () => { live = false; clearInterval(t); };
  }, [open, conn, ready, cur, lang, pvKey, view]);

  // delivery log for this block's advisories
  useEffect(() => {
    if (!open || step !== "track") return;
    const ids = new Set(items.map((a) => a.advisory_id));
    let live = true;
    const poll = () => dispatchLog(block.id).then((rows) => { if (live) setLog(rows.filter((r) => ids.has(r.advisory_id))); }).catch(() => {});
    poll();
    const t = setInterval(poll, 3000);
    return () => { live = false; clearInterval(t); };
  }, [open, step, items, block.id]);

  const close = () => {
    onClose();
    setStep("review"); setLog([]); setErrors([]); setPv(null); setSubs({}); setConn(undefined);
    setChecked(false); setNote(""); setPickedLang(null); setSel(0);
  };

  const pendingIds = items.filter((a) => ok(subs[a.advisory_id]) && (subs[a.advisory_id] as Summary).state === "pending_approval").map((a) => a.advisory_id);
  const toSend = pendingIds.filter((id) => chosen.has(id));
  const toHold = pendingIds.filter((id) => !chosen.has(id));
  const loading = !!conn && Object.keys(subs).length < items.length;
  const signer = officer.trim();

  const decide = async () => {
    setBusy(true);
    try { localStorage.setItem(OFFICER_KEY, signer); } catch { /* private window */ }
    const errs: string[] = [];
    const n = note.trim() || undefined;
    for (const id of toSend) {
      await approve(id, signer, n).then((r) => setSubs((s) => ({ ...s, [id]: r })))
        .catch((e) => errs.push(`${cropOf(items, id)}: ${e.message ?? e}`));
    }
    for (const id of toHold) {
      await reject(id, signer, n ?? "held back at review").then((r) => setSubs((s) => ({ ...s, [id]: r })))
        .catch((e) => errs.push(`${cropOf(items, id)}: ${e.message ?? e}`));
    }
    setErrors(errs);
    setBusy(false);
    setStep("track");
  };

  const cls = CLASS[forecast.cmri[0][block.i]] ?? null;
  const webLang = LANGS.some((l) => l.key === lang) ? lang : "en";
  const webSrc = `/f/${block.id}?lang=${webLang}&crop=${advice[sel]?.[0] ?? ""}&date=${forecast.issued}`;
  const shownPv = pv?.key === pvKey ? pv : null;
  const canTrack = items.some((a) => ok(subs[a.advisory_id]) && (subs[a.advisory_id] as Summary).state !== "pending_approval");

  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-3 md:p-6"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, transition: { duration: 0.15 } }}
          onClick={close}>
          <motion.div role="dialog" aria-modal="true" aria-labelledby="rs-title"
            initial={{ opacity: 0, y: 16, scale: 0.985 }} animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, transition: { duration: 0.15 } }}
            transition={{ type: "spring", stiffness: 380, damping: 34 }}
            onClick={(e) => e.stopPropagation()}
            className="panel flex h-[min(90vh,860px)] w-full max-w-6xl flex-col overflow-hidden">

            {/* header: where, what class, and whether the WhatsApp service is there */}
            <header className="flex items-center gap-4 border-b border-line px-6 py-4">
              <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[#f7efe0] shadow-inner">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/brand/mark.png" alt="" className="h-8 w-8" />
              </div>
              <div className="min-w-0 flex-1">
                <h2 id="rs-title" className="text-[17px] font-semibold leading-tight">Send advisory to farmers</h2>
                <p className="truncate text-[12.5px] text-text-3">
                  {block.name} · {block.district}, {block.state} · forecast issued {dmy(forecast.issued)}
                  {forecast.source === "live" ? " · live" : " · 2023 replay"}
                </p>
              </div>
              {cls && (
                <span className="hidden items-center gap-1.5 rounded-full border border-line px-2.5 py-1 text-[11.5px] font-semibold uppercase tracking-wide sm:flex">
                  <span className="h-2 w-2 rounded-full" style={{ background: `var(--cmri-${cls})` }} />{cls}
                </span>
              )}
              <ServicePill conn={conn} onRetry={() => { setConn(undefined); setAttempt((n) => n + 1); }} />
              <button aria-label="Close" onClick={close}
                className="grid h-9 w-9 cursor-pointer place-items-center rounded-md text-text-2 transition-colors hover:bg-surface-2 hover:text-text">
                <X size={18} />
              </button>
            </header>

            <Stepper step={step} canTrack={canTrack} canApprove={!!conn && !loading && pendingIds.length > 0}
              onGo={(s) => setStep(s)} />

            <div className="grid min-h-0 flex-1 grid-cols-1 md:grid-cols-[minmax(0,1fr)_380px]">
              {/* left: the step */}
              <div className="flex min-h-0 flex-col">
                <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
                  <AnimatePresence mode="wait" initial={false}>
                    <motion.div key={step} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: -12 }} transition={{ duration: 0.18 }}>
                      {step === "review" && (
                        <ReviewStep advice={advice} items={items} subs={subs} conn={conn} sel={sel} setSel={setSel}
                          chosen={chosen} setChosen={setChosen} langName={langName} />
                      )}
                      {step === "approve" && (
                        <ApproveStep items={items} toSend={toSend} toHold={toHold} recipients={recipients}
                          langs={farmerLangs.map(langName)} officer={officer} setOfficer={setOfficer}
                          note={note} setNote={setNote} checked={checked} setChecked={setChecked}
                          simulator={conn?.whatsapp === "simulator"} />
                      )}
                      {step === "track" && (
                        <TrackStep items={items} subs={subs} log={log} errors={errors} langName={langName}
                          simulator={conn?.whatsapp === "simulator"} />
                      )}
                    </motion.div>
                  </AnimatePresence>
                </div>

                {/* footer: the one next action */}
                <footer className="flex items-center gap-3 border-t border-line bg-(--surface-solid)/60 px-6 py-3.5">
                  {step === "review" && (
                    <>
                      <p className="min-w-0 flex-1 text-[12.5px] text-text-2">
                        {conn === null ? "Delivery service offline: you can read the advice, but not send it."
                          : loading ? "Checking recipients with the delivery service…"
                          : !pendingIds.length ? "Everything here has already been decided."
                          : <><b className="text-text">{toSend.length}</b> of {pendingIds.length} selected · reaches <b className="text-text">{recipients}</b> farmer{recipients === 1 ? "" : "s"}</>}
                      </p>
                      {canTrack && (
                        <button onClick={() => setStep("track")} className="btn-ghost">View delivery</button>
                      )}
                      <button onClick={() => setStep("approve")} disabled={!conn || loading || !pendingIds.length}
                        className="btn-primary">
                        Continue to approval <ArrowRight size={15} />
                      </button>
                    </>
                  )}
                  {step === "approve" && (
                    <>
                      <button onClick={() => setStep("review")} className="btn-ghost"><ArrowLeft size={15} /> Back</button>
                      <p className="min-w-0 flex-1 text-right text-[12px] text-text-3">
                        {!signer ? "Enter your name to sign." : !checked ? "Confirm you have read the message." : "Recorded with your name and time."}
                      </p>
                      <button onClick={decide} disabled={busy || !signer || !checked || (!toSend.length && !toHold.length)}
                        className="btn-primary">
                        {busy ? <Loader2 size={15} className="animate-spin" /> : <ShieldCheck size={15} />}
                        {busy ? "Recording…" : toSend.length
                          ? `Approve & send to ${recipients} farmer${recipients === 1 ? "" : "s"}`
                          : "Hold back all"}
                      </button>
                    </>
                  )}
                  {step === "track" && (
                    <>
                      <p className="min-w-0 flex-1 text-[12px] text-text-3">Updates every 3 seconds. You can close this; delivery continues.</p>
                      <button onClick={close} className="btn-primary">Done</button>
                    </>
                  )}
                </footer>
              </div>

              {/* right: the farmer's phone */}
              <aside className="hidden min-h-0 flex-col items-center gap-3 border-l border-line bg-(--bg) px-5 py-4 md:flex">
                <div className="flex w-full items-center justify-between">
                  <div className="flex rounded-md bg-surface-2 p-0.5 text-[12px]" role="tablist" aria-label="Preview">
                    {([["whatsapp", "WhatsApp", Smartphone], ["web", "Web link", Globe]] as const).map(([k, label, Icon]) => (
                      <button key={k} role="tab" aria-selected={view === k} onClick={() => setView(k)}
                        className={`flex min-h-8 cursor-pointer items-center gap-1.5 rounded px-3 transition-colors ${view === k ? "bg-surface text-text" : "text-text-2 hover:text-text"}`}>
                        <Icon size={13} /> {label}
                      </button>
                    ))}
                  </div>
                  <span className="max-w-[140px] truncate text-[11.5px] text-text-3">{items[sel] && cropName(items[sel].crop)}</span>
                </div>
                <div className="flex w-full flex-wrap gap-1" aria-label="Preview language">
                  {allLangs.map((code) => (
                    <button key={code} onClick={() => setPickedLang(code)} aria-pressed={lang === code}
                      title={farmerLangs.includes(code) ? "Farmers here read this language" : undefined}
                      className={`relative min-h-7 cursor-pointer rounded-md px-2.5 text-[12.5px] transition-colors ${
                        lang === code ? "bg-surface-2 text-text shadow-[0_0_0_1px_var(--line-strong)]" : "text-text-2 hover:text-text"}`}>
                      {langName(code)}
                      {farmerLangs.includes(code) && <span className="absolute right-0.5 top-0.5 h-1.5 w-1.5 rounded-full bg-normal" />}
                    </button>
                  ))}
                </div>
                <div className="relative min-h-0 w-[300px] flex-1 overflow-hidden rounded-[34px] border-[6px] border-[#1c2740] shadow-2xl">
                  {view === "web" || !conn ? (
                    <iframe key={webSrc} src={webSrc} title="Farmer web page preview" className="h-full w-full bg-white" />
                  ) : (
                    <WhatsAppPreview pv={shownPv} waiting={!ready} />
                  )}
                </div>
              </aside>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// the delivery service's crop id, shown as a name ("paddy" -> "Paddy", "tur" -> "Tur")
const cropName = (c: string) => CROP_NAME[c]?.en ?? CROP_NAME[{ paddy: "rice", tur: "pigeonpea" }[c] ?? ""]?.en ?? c.charAt(0).toUpperCase() + c.slice(1);
const cropOf = (items: { advisory_id: string; crop: string }[], id: string) => cropName(items.find((a) => a.advisory_id === id)?.crop ?? id);

/* ----------------------------------------------------------------- header pieces */

function ServicePill({ conn, onRetry }: { conn: Health | null | undefined; onRetry: () => void }) {
  if (conn === undefined)
    return <span className="flex items-center gap-1.5 text-[12px] text-text-3"><Loader2 size={13} className="animate-spin" /> Connecting</span>;
  if (conn === null)
    return (
      <button onClick={onRetry} className="flex cursor-pointer items-center gap-1.5 rounded-full border border-alert/40 px-2.5 py-1 text-[12px] text-alert hover:bg-alert/10">
        <RefreshCw size={12} /> Service offline · retry
      </button>
    );
  const sim = conn.whatsapp === "simulator";
  return (
    <span title={`${conn.subscribers ?? 0} subscribers on the service`}
      className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[12px] ${sim ? "border-watch/40 text-watch" : "border-normal/40 text-normal"}`}>
      <span className="relative flex h-2 w-2">
        <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-60 ${sim ? "bg-watch" : "bg-normal"}`} />
        <span className={`relative inline-flex h-2 w-2 rounded-full ${sim ? "bg-watch" : "bg-normal"}`} />
      </span>
      {sim ? "Simulator" : "WhatsApp live"}
    </span>
  );
}

function Stepper({ step, canApprove, canTrack, onGo }: {
  step: Step; canApprove: boolean; canTrack: boolean; onGo: (s: Step) => void;
}) {
  const k = STEP_LIST.findIndex((s) => s.key === step);
  const enabled = (s: Step) => (s === "review" ? true : s === "approve" ? canApprove : canTrack);
  return (
    <nav aria-label="Steps" className="border-b border-line px-6 py-3">
      <ol className="flex items-center gap-2">
        {STEP_LIST.map((s, i) => {
          const done = i < k, here = i === k;
          return (
            <Fragment key={s.key}>
              {i > 0 && (
                <li aria-hidden className="relative h-px flex-1 overflow-hidden bg-line">
                  <motion.div className="absolute inset-y-0 left-0 bg-focus" initial={false} animate={{ width: i <= k ? "100%" : "0%" }} transition={{ duration: 0.35 }} />
                </li>
              )}
              <li>
                <button onClick={() => enabled(s.key) && onGo(s.key)} disabled={!enabled(s.key)} aria-current={here ? "step" : undefined}
                  className="group flex cursor-pointer items-center gap-2.5 rounded-lg px-1.5 py-1 text-left disabled:cursor-default">
                  <span className={`grid h-7 w-7 place-items-center rounded-full text-[12px] font-semibold transition-colors ${
                    here ? "bg-focus text-[#06121c]" : done ? "bg-focus/20 text-focus" : "bg-surface-2 text-text-3"}`}>
                    {done ? <Check size={14} /> : i + 1}
                  </span>
                  <span className="hidden leading-tight sm:block">
                    <span className={`block text-[13px] font-semibold ${here ? "text-text" : "text-text-2"}`}>{s.label}</span>
                    <span className="block text-[11px] text-text-3">{s.hint}</span>
                  </span>
                </button>
              </li>
            </Fragment>
          );
        })}
      </ol>
    </nav>
  );
}

/* ----------------------------------------------------------------- step 1: review */

function Evidence({ params }: { params: Record<string, unknown> }) {
  const p = Number(params.p_event), c = Number(params.p_clim);
  if (!Number.isFinite(p) || !Number.isFinite(c)) return null;
  const label = params.event === "heavy_rain" ? "Heavy-rain day" : "10+ day dry spell";
  return (
    <div className="mt-2.5 grid grid-cols-[auto_1fr_auto] items-center gap-x-3 gap-y-1 text-[11.5px]">
      <span className="text-text-3">{label}, week {String(params.lead_week)}</span>
      <div className="relative h-1.5 overflow-hidden rounded-full bg-line">
        <motion.div className="absolute inset-y-0 left-0 rounded-full bg-warning" initial={{ width: 0 }} animate={{ width: `${p * 100}%` }} transition={{ duration: 0.6, ease: "easeOut" }} />
        <div className="absolute inset-y-[-2px] w-0.5 bg-text" style={{ left: `${c * 100}%` }} title="usual chance" />
      </div>
      <span className="tabular-nums text-text-2"><b className="text-text">{Math.round(p * 10)} in 10</b> · usually {Math.round(c * 10)}</span>
    </div>
  );
}

function StateTag({ s, recipients }: { s?: Sub; recipients?: boolean }) {
  if (!s) return <Loader2 size={13} className="animate-spin text-text-3" />;
  if (!ok(s)) return <span title={s.error} className="flex items-center gap-1 text-[11.5px] text-alert"><AlertTriangle size={12} /> Service refused</span>;
  if (isSent(s)) return <span className="flex items-center gap-1 text-[11.5px] text-normal"><CheckCheck size={13} /> Approved {hhmm(s.approved_ts)}</span>;
  if (s.state === "rejected") return <span className="flex items-center gap-1 text-[11.5px] text-text-3"><Ban size={12} /> Held back</span>;
  return recipients ? (
    <span className="flex items-center gap-1 text-[11.5px] text-text-2"><Users size={12} /> {s.recipients} farmer{s.recipients === 1 ? "" : "s"}</span>
  ) : null;
}

/** The farmers this advisory skips. Each one has a reason from the farmer's own record, so the
 *  officer can see that the gap is deliberate rather than a delivery failure. */
function LeftOut({ n, rows }: { n: number; rows: { subscriber_id: string; reason: string }[] }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen((v) => !v)}
              className="rounded-full border border-line px-1.5 py-0.5 hover:text-text-2">
        {n} not sent
      </button>
      {open && (
        <ul className="mt-1 w-full space-y-0.5 text-[11px] text-text-3">
          {rows.slice(0, 8).map((r) => <li key={r.subscriber_id}>· {r.reason}</li>)}
          {rows.length > 8 && <li>· and {rows.length - 8} more</li>}
        </ul>
      )}
    </>
  );
}

function ReviewStep({ advice, items, subs, conn, sel, setSel, chosen, setChosen, langName }: {
  advice: Advice[]; items: ReturnType<typeof toContract>[]; subs: Record<string, Sub>; conn: Health | null | undefined;
  sel: number; setSel: (k: number) => void; chosen: Set<string>; setChosen: (s: Set<string>) => void;
  langName: (c: string) => string;
}) {
  const toggle = (id: string) => { const n = new Set(chosen); if (n.has(id)) n.delete(id); else n.add(id); setChosen(n); };
  return (
    <div>
      <h3 className="text-[14px] font-semibold">Check each advisory</h3>
      <p className="mt-0.5 text-[12.5px] text-text-3">
        Select an advisory to see it on the phone. Untick any you want to hold back; only ticked ones are sent.
      </p>
      <ul className="mt-4 space-y-2.5">
        {advice.map((a, k) => {
          const it = items[k];
          const s = subs[it.advisory_id];
          const { title, body } = renderAdvice(a);
          const pending = ok(s) && s.state === "pending_approval";
          const on = chosen.has(it.advisory_id);
          return (
            <motion.li key={it.advisory_id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: k * 0.05 }}>
              <div onClick={() => setSel(k)}
                className={`group flex cursor-pointer gap-3 rounded-xl border px-3.5 py-3 transition-colors ${
                  sel === k ? "border-focus/70 bg-surface-2" : "border-line hover:border-line-strong hover:bg-surface-2/50"}`}>
                <div className="pt-0.5">
                  <input type="checkbox" aria-label={`Send ${it.crop} advisory`} checked={pending && on} disabled={!pending}
                    onChange={() => toggle(it.advisory_id)} onClick={(e) => e.stopPropagation()}
                    className="h-4 w-4 cursor-pointer accent-(--focus) disabled:cursor-default disabled:opacity-40" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="text-[13.5px] font-semibold">{title}</span>
                    {conn && <StateTag s={s} recipients />}
                  </div>
                  <p className="mt-1 text-[12.5px] leading-snug text-text-2">{body}</p>
                  <Evidence params={a[3]} />
                  <div className="mt-2.5 flex flex-wrap items-center gap-1.5 text-[11px] text-text-3">
                    <span className="rounded bg-surface-2 px-1.5 py-0.5 font-mono">{it.template_id}</span>
                    <span>valid {dmy(it.valid_from)} – {dmy(it.valid_to)}</span>
                    {ok(s) && s.languages.map((l) => <span key={l} className="rounded-full border border-line px-1.5 py-0.5">{langName(l)}</span>)}
                    {ok(s) && s.recipients === 0 && <span>· no subscriber grows {cropName(it.crop).toLowerCase()} here yet</span>}
                    {ok(s) && !!s.not_sent && <LeftOut n={s.not_sent} rows={s.left_out ?? []} />}
                  </div>
                </div>
              </div>
            </motion.li>
          );
        })}
      </ul>
      {conn === null && (
        <div className="mt-4 flex items-start gap-2.5 rounded-lg border border-line bg-surface-2/60 px-3 py-2.5 text-[12px] text-text-2">
          <AlertTriangle size={15} className="mt-0.5 shrink-0 text-warning" />
          <span>The WhatsApp delivery service isn’t reachable. Start it (<code className="text-text">act_1\scripts\run.ps1</code>)
            and check <code className="text-text">DELIVERY_URL</code>, then press retry at the top.</span>
        </div>
      )}
    </div>
  );
}

/* ----------------------------------------------------------------- step 2: approve */

function ApproveStep({ items, toSend, toHold, recipients, langs, officer, setOfficer, note, setNote, checked, setChecked, simulator }: {
  items: ReturnType<typeof toContract>[]; toSend: string[]; toHold: string[]; recipients: number; langs: string[];
  officer: string; setOfficer: (s: string) => void; note: string; setNote: (s: string) => void;
  checked: boolean; setChecked: (b: boolean) => void; simulator: boolean;
}) {
  const crops = (ids: string[]) => ids.map((id) => cropOf(items, id)).join(", ");
  return (
    <div className="max-w-xl">
      <h3 className="text-[14px] font-semibold">Your sign-off</h3>
      <p className="mt-0.5 text-[12.5px] text-text-3">Nothing reaches a farmer until you approve. Your name and the time are stored with each advisory.</p>

      <dl className="mt-4 grid grid-cols-3 overflow-hidden rounded-xl border border-line text-center">
        {[
          [toSend.length === 1 ? "Advisory" : "Advisories", toSend.length],
          [recipients === 1 ? "Farmer" : "Farmers", recipients],
          [langs.length === 1 ? "Language" : "Languages", langs.length],
        ].map(([k, v]) => (
          <div key={k as string} className="border-r border-line px-3 py-3 last:border-r-0">
            <dd className="text-[22px] font-semibold tabular-nums">{v}</dd>
            <dt className="text-[11px] uppercase tracking-wide text-text-3">{k}</dt>
          </div>
        ))}
      </dl>
      <ul className="mt-3 space-y-1.5 text-[12.5px] text-text-2">
        {toSend.length > 0 && <li className="flex gap-2"><Send size={14} className="mt-0.5 text-focus" /> Send: {crops(toSend)}{langs.length ? ` · in ${langs.join(", ")}` : ""}</li>}
        {toHold.length > 0 && <li className="flex gap-2"><Ban size={14} className="mt-0.5 text-text-3" /> Hold back: {crops(toHold)}</li>}
        <li className="flex gap-2"><Mic size={14} className="mt-0.5 text-text-3" /> Each farmer gets a picture card, a voice note and a text message on WhatsApp.</li>
        {simulator && <li className="flex gap-2 text-watch"><AlertTriangle size={14} className="mt-0.5" /> Simulator mode: messages are recorded, not sent to real phones.</li>}
      </ul>

      <label className="mt-5 block text-[12px] font-medium text-text-2" htmlFor="rs-officer">Approved by</label>
      <input id="rs-officer" value={officer} onChange={(e) => setOfficer(e.target.value)} autoComplete="name"
        placeholder="Your name and designation, e.g. R. Patil, ADA Navalgund"
        className="mt-1 w-full rounded-lg border border-line bg-surface-2 px-3 py-2 text-[13.5px] outline-none transition-colors placeholder:text-text-3 focus:border-focus" />
      <label className="mt-3 block text-[12px] font-medium text-text-2" htmlFor="rs-note">Note <span className="text-text-3">(optional, kept in the record)</span></label>
      <textarea id="rs-note" value={note} onChange={(e) => setNote(e.target.value)} rows={2}
        placeholder="e.g. Checked with KVK Dharwad; seed of alternative crops available at RSK."
        className="mt-1 w-full resize-none rounded-lg border border-line bg-surface-2 px-3 py-2 text-[13px] outline-none transition-colors placeholder:text-text-3 focus:border-focus" />
      <label className="mt-3 flex cursor-pointer items-start gap-2.5 rounded-lg border border-line px-3 py-2.5 text-[12.5px] text-text-2 has-checked:border-focus/60 has-checked:bg-focus/5">
        <input type="checkbox" checked={checked} onChange={(e) => setChecked(e.target.checked)} className="mt-0.5 h-4 w-4 accent-(--focus)" />
        I have read the message in the farmers’ language on the phone preview, and it fits local conditions.
      </label>
    </div>
  );
}

/* ----------------------------------------------------------------- step 3: track */

function TrackStep({ items, subs, log, errors, langName, simulator }: {
  items: ReturnType<typeof toContract>[]; subs: Record<string, Sub>; log: LogRow[]; errors: string[];
  langName: (c: string) => string; simulator: boolean;
}) {
  const decided = items.filter((a) => ok(subs[a.advisory_id]) && (subs[a.advisory_id] as Summary).state !== "pending_approval");
  const approved = decided.filter((a) => isSent(subs[a.advisory_id]));
  const n = log.length;
  const rank = (s: string) => DELIVERY.indexOf(s as (typeof DELIVERY)[number]);
  const reached = (k: number) => log.filter((r) => rank(r.status) >= k).length;
  const failed = log.filter((r) => r.status === "failed");
  const firstAt = (k: number) => {
    const t = log.filter((r) => rank(r.status) >= k).map((r) => r.ts).sort()[0];
    return t ? hhmm(t) : "";
  };
  const approvedAt = approved.map((a) => (subs[a.advisory_id] as Summary).approved_ts).filter(Boolean).sort()[0] ?? null;
  const approver = approved.map((a) => (subs[a.advisory_id] as Summary).approved_by).find(Boolean);

  const stages = [
    { label: "Approved", detail: approver ? `by ${approver}` : "", at: hhmm(approvedAt), count: approved.length, of: approved.length, unit: "advisories", icon: ShieldCheck },
    { label: "Preparing", detail: "card and voice note", at: firstAt(0), count: reached(0), of: n, unit: "farmers", icon: Clock },
    { label: "Sent", detail: "left our server", at: firstAt(1), count: reached(1), of: n, unit: "farmers", icon: Send },
    { label: "Delivered", detail: "on the phone", at: firstAt(2), count: reached(2), of: n, unit: "farmers", icon: CheckCheck },
    { label: "Read", detail: "opened by the farmer", at: firstAt(3), count: reached(3), of: n, unit: "farmers", icon: Radio },
  ];

  return (
    <div>
      <div className="flex items-end justify-between gap-4">
        <div>
          <h3 className="text-[14px] font-semibold">Delivery</h3>
          <p className="mt-0.5 text-[12.5px] text-text-3">
            {approved.length === 0 ? "Nothing was approved for sending."
              : n === 0 ? "Approved. No subscribed farmer grows these crops here yet; future subscribers will get new advisories."
              : <>Reached <b className="text-text">{reached(2)}</b> of {n} farmer{n === 1 ? "" : "s"}{simulator ? " (simulator)" : ""}.</>}
          </p>
        </div>
        {n > 0 && <span className="text-[26px] font-semibold tabular-nums">{Math.round((reached(2) / n) * 100)}%</span>}
      </div>

      {errors.length > 0 && (
        <div className="mt-3 flex items-start gap-2 rounded-lg bg-alert/10 px-3 py-2 text-[12px] text-text"><AlertTriangle size={14} className="mt-0.5 text-alert" />{errors.join(" · ")}</div>
      )}

      {/* the path every message takes, filled in as the log reports it */}
      <ol className="relative mt-5 space-y-0">
        {stages.map((s, i) => {
          const done = s.of > 0 && s.count >= s.of;
          const partial = s.count > 0 && !done;
          const Icon = s.icon;
          return (
            <li key={s.label} className="relative flex gap-3.5 pb-4 last:pb-0">
              {i < stages.length - 1 && <span aria-hidden className="absolute left-[15px] top-8 h-[calc(100%-24px)] w-px bg-line" />}
              <span className={`relative z-10 grid h-8 w-8 shrink-0 place-items-center rounded-full border transition-colors ${
                done ? "border-normal bg-normal/15 text-normal" : partial ? "border-focus bg-focus/10 text-focus" : "border-line bg-surface-2 text-text-3"}`}>
                {partial && i > 0 ? <Loader2 size={14} className="animate-spin" /> : <Icon size={14} />}
              </span>
              <div className="min-w-0 flex-1 pt-1">
                <div className="flex items-baseline justify-between gap-3">
                  <span className={`text-[13px] font-semibold ${s.count ? "text-text" : "text-text-3"}`}>{s.label}
                    <span className="ml-2 text-[11.5px] font-normal text-text-3">{s.detail}</span></span>
                  <span className="text-[11.5px] tabular-nums text-text-3">{s.at}</span>
                </div>
                {s.of > 0 && (
                  <div className="mt-1.5 flex items-center gap-2.5">
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-line">
                      <motion.div className={`h-full rounded-full ${done ? "bg-normal" : "bg-focus"}`} initial={false}
                        animate={{ width: `${(s.count / s.of) * 100}%` }} transition={{ duration: 0.5 }} />
                    </div>
                    <span className="shrink-0 whitespace-nowrap text-right text-[11.5px] tabular-nums text-text-2">{s.count} / {s.of} {s.of === 1 ? s.unit.replace(/ies$/, "y").replace(/s$/, "") : s.unit}</span>
                  </div>
                )}
                {i === 1 && partial && reached(1) === 0 && (
                  <p className="mt-1 text-[11.5px] text-text-3">Voice notes are made on the GPU while waiting; sending starts when they’re ready.</p>
                )}
              </div>
            </li>
          );
        })}
      </ol>

      {failed.length > 0 && (
        <div className="mt-2 flex items-start gap-2 rounded-lg bg-alert/10 px-3 py-2 text-[12px]"><AlertTriangle size={14} className="mt-0.5 text-alert" />
          {failed.length} failed: {failed[0].error}</div>
      )}

      {/* live feed: newest first; farmers shown by id only */}
      {n > 0 && (
        <div className="mt-5">
          <div className="mb-2 text-[11px] uppercase tracking-wide text-text-3">Activity</div>
          <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line">
            <AnimatePresence initial={false}>
              {[...log].sort((a, b) => b.ts.localeCompare(a.ts)).slice(0, 8).map((r) => (
                <motion.li key={`${r.advisory_id}|${r.subscriber_id}`} layout initial={{ opacity: 0, backgroundColor: "rgba(92,200,255,0.12)" }}
                  animate={{ opacity: 1, backgroundColor: "rgba(0,0,0,0)" }} transition={{ duration: 0.8 }}
                  className="grid grid-cols-[64px_1fr_auto] items-center gap-3 px-3 py-2 text-[12px]">
                  <span className="whitespace-nowrap tabular-nums text-text-3">{hhmm(r.ts)}</span>
                  <span className="min-w-0 truncate text-text-2">
                    Farmer ···{r.subscriber_id.slice(-4)} · {cropOf(items, r.advisory_id)} · {langName(r.language)}
                    {r.error && <span className="block truncate text-[11px] text-text-3">{r.error}</span>}
                  </span>
                  <StatusChip status={r.status} />
                </motion.li>
              ))}
            </AnimatePresence>
          </ul>
        </div>
      )}
    </div>
  );
}

function StatusChip({ status }: { status: string }) {
  const tone = status === "failed" ? "bg-alert/15 text-alert"
    : status === "read" || status === "delivered" ? "bg-normal/15 text-normal"
    : status === "sent" ? "bg-focus/15 text-focus" : "bg-surface-2 text-text-3";
  return <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium capitalize ${tone}`}>{status}</span>;
}

/* ----------------------------------------------------------------- phone */

// WhatsApp's own formatting: *bold*, _italic_, line breaks
function waText(t: string) {
  return t.split("\n").map((line, i) => (
    <Fragment key={i}>
      {i > 0 && <br />}
      {line.split(/(\*[^*\n]+\*|_[^_\n]+_)/g).map((part, j) =>
        part.startsWith("*") && part.endsWith("*") && part.length > 2 ? <b key={j}>{part.slice(1, -1)}</b>
          : part.startsWith("_") && part.endsWith("_") && part.length > 2 ? <i key={j}>{part.slice(1, -1)}</i>
          : part)}
    </Fragment>
  ));
}

function WhatsAppPreview({ pv, waiting }: { pv: { data: Preview | null; error?: string } | null; waiting: boolean }) {
  const now = new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
  return (
    <div className="flex h-full flex-col bg-[#efeae2] text-[#111b21]">
      <div className="flex items-center gap-2.5 bg-[#008069] px-3 pb-2.5 pt-7 text-white">
        <div className="grid h-8 w-8 place-items-center overflow-hidden rounded-full bg-[#f7efe0]">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/brand/mark.png" alt="" className="h-6 w-6" />
        </div>
        <div className="leading-tight">
          <div className="text-[14px] font-semibold">Meghmitra</div>
          <div className="text-[11px] opacity-80">Monsoon advice for your block</div>
        </div>
      </div>
      <div className="flex-1 space-y-2 overflow-y-auto p-2.5">
        {!pv ? (
          <div className="flex h-full items-center justify-center gap-2 text-[12px] text-[#667781]">
            <Loader2 size={14} className="animate-spin" /> {waiting ? "Preparing…" : "Rendering in this language…"}
          </div>
        ) : !pv.data ? (
          <div className="rounded-lg bg-white p-3 text-[12px] text-[#b3261e]">Couldn’t render: {pv.error}</div>
        ) : (
          <motion.div key={pv.data.card_url} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-2">
            {/* eslint-disable-next-line @next/next/no-img-element -- PNG rendered by the delivery service */}
            <img src={pv.data.card_url} alt={`Advisory card: ${pv.data.verdict}`} className="w-full rounded-lg bg-white p-1 shadow-sm" />
            <div className="flex items-center gap-2 rounded-lg bg-white px-2.5 py-2 shadow-sm">
              <div className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-[#00a884] text-white"><Mic size={15} /></div>
              {pv.data.voice_url ? (
                <audio controls src={pv.data.voice_url} className="h-8 w-full" />
              ) : (
                <span className="text-[12px] text-[#667781]">Voice note {pv.data.voice_state === "failed" ? "failed to render" : "being made (a few minutes)…"}</span>
              )}
            </div>
            <div className="rounded-lg bg-white px-2.5 pb-1 pt-2 text-[13px] leading-snug shadow-sm">
              {waText(pv.data.whatsapp_text)}
              <div className="mt-0.5 text-right text-[10px] text-[#667781]">{now}</div>
            </div>
            {pv.data.review_status !== "reviewed" && (
              <div className={`rounded px-2 py-1 text-center text-[10.5px] ${
                pv.data.review_status === "checked" ? "bg-[#e7f1ff] text-[#1b4568]" : "bg-[#fff4d6] text-[#6b5000]"}`}>
                {pv.data.review_status === "checked"
                  ? "Wording corrected in review · native-speaker sign-off still pending"
                  : "Machine translation, not yet checked by a native speaker"}
              </div>
            )}
          </motion.div>
        )}
      </div>
    </div>
  );
}
