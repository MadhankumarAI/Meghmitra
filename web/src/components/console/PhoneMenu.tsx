"use client";

/**
 * The phone's menu. A desktop has room for every control along the top; a phone has room for the
 * map, a search box and one button. Everything else lives here: which layer is on the map, replay
 * or live, the atmosphere, delivery and the evidence pages.
 *
 * Only rendered below the md breakpoint; the desktop header is untouched.
 */
import { useEffect } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import { Menu, X, Wind, Send, ChevronRight } from "lucide-react";
import { useConsole, type EventKey } from "@/lib/store";

const EVENTS: { key: EventKey; label: string; hint: string }[] = [
  { key: "cmri", label: "Risk (CMRI)", hint: "The combined monsoon risk class" },
  { key: "onset", label: "Onset", hint: "Chance the monsoon arrives" },
  { key: "dry10", label: "Dry spell", hint: "Chance of 10 or more dry days" },
  { key: "heavy", label: "Heavy rain", hint: "Chance of a 64.5 mm day" },
];

export default function PhoneMenu({ open, onOpen, onClose }: {
  open: boolean; onOpen: () => void; onClose: () => void;
}) {
  const event = useConsole((s) => s.event);
  const setEvent = useConsole((s) => s.setEvent);
  const mode = useConsole((s) => s.mode);
  const setMode = useConsole((s) => s.setMode);
  const understand = useConsole((s) => s.understand);
  const setUnderstand = useConsole((s) => s.setUnderstand);
  const setDelivery = useConsole((s) => s.setDelivery);

  // The sheet goes to <body>, not into the header it is triggered from: that header is
  // pointer-events-none (so the map can be dragged through it) and carries its own stacking
  // context, which would both swallow every tap here and let the block sheet paint over it.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <>
      <button
        onClick={open ? onClose : onOpen}
        aria-label={open ? "Close menu" : "Open menu"}
        aria-expanded={open}
        className="panel pointer-events-auto grid h-11 w-11 shrink-0 cursor-pointer place-items-center text-text-2 md:hidden"
      >
        {open ? <X size={20} /> : <Menu size={20} />}
      </button>

      {typeof document !== "undefined" && createPortal(
      <AnimatePresence>
        {open && (
          <motion.div key="scrim" className="pointer-events-auto fixed inset-0 z-[60] bg-black/35 md:hidden"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, transition: { duration: 0.12 } }}
            onClick={onClose}>
            <motion.div
              role="dialog" aria-modal="true" aria-label="Menu"
              onClick={(e) => e.stopPropagation()}
              initial={{ y: -12, opacity: 0 }} animate={{ y: 0, opacity: 1 }}
              exit={{ y: -8, opacity: 0, transition: { duration: 0.14 } }}
              transition={{ type: "spring", stiffness: 460, damping: 38 }}
              className="panel-solid absolute inset-x-2 top-2 overflow-hidden rounded-xl"
            >
              <div className="flex items-center justify-between px-4 pb-2 pt-3.5">
                <span className="text-[12px] font-semibold uppercase tracking-wider text-text-3">Menu</span>
                <button onClick={onClose} aria-label="Close menu"
                  className="-mr-1.5 grid h-10 w-10 cursor-pointer place-items-center rounded-md text-text-2">
                  <X size={20} />
                </button>
              </div>

              <Group label="Layer on the map">
                <div className="grid grid-cols-2 gap-1.5">
                  {EVENTS.map((e) => (
                    <button key={e.key} onClick={() => { setEvent(e.key); onClose(); }}
                      aria-pressed={event === e.key}
                      className={`min-h-11 cursor-pointer rounded-lg px-3 text-left text-[14px] font-medium transition-colors ${
                        event === e.key ? "bg-focus text-white" : "bg-surface-2 text-text-2"}`}>
                      {e.label}
                    </button>
                  ))}
                </div>
              </Group>

              <Group label="Data">
                <div className="grid grid-cols-2 gap-1.5">
                  {([["replay", "2023 replay"], ["live", "Live"]] as const).map(([m, label]) => (
                    <button key={m} onClick={() => { setMode(m); onClose(); }} aria-pressed={mode === m}
                      className={`flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-lg px-3 text-[14px] font-medium transition-colors ${
                        mode === m ? "bg-focus text-white" : "bg-surface-2 text-text-2"}`}>
                      {m === "live" && <span className="h-1.5 w-1.5 rounded-full bg-current opacity-80" />}
                      {label}
                    </button>
                  ))}
                </div>
              </Group>

              <Group label="More">
                <Row icon={<Wind size={17} />} label="Understand the weather"
                  note={understand ? "on" : undefined}
                  onClick={() => { setUnderstand(!understand); onClose(); }} />
                <Row icon={<Send size={17} />} label="Delivery"
                  onClick={() => { setDelivery(true); onClose(); }} />
                <Link href="/science" onClick={onClose}
                  className="flex min-h-12 items-center gap-3 rounded-lg px-2 text-[14px] text-text">
                  <span className="grid w-5 shrink-0 place-items-center text-text-3">
                    <ChevronRight size={17} />
                  </span>
                  Evidence and model card
                </Link>
              </Group>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>, document.body)}
    </>
  );
}

function Group({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="border-t border-line px-4 py-3">
      <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-text-3">{label}</div>
      {children}
    </div>
  );
}

function Row({ icon, label, note, onClick }: {
  icon: React.ReactNode; label: string; note?: string; onClick: () => void;
}) {
  return (
    <button onClick={onClick}
      className="flex min-h-12 w-full cursor-pointer items-center gap-3 rounded-lg px-2 text-left text-[14px] text-text">
      <span className="grid w-5 shrink-0 place-items-center text-text-3">{icon}</span>
      {label}
      {note && <span className="ml-auto text-[12px] font-medium text-focus">{note}</span>}
    </button>
  );
}
