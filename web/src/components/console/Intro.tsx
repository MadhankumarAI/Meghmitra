"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { BRAND, Wordmark } from "@/components/Brand";

const SEEN = "mungaru.intro";
const MIN_MS = 1600;
const noop = () => () => {};
const seenThisSession = () => { try { return sessionStorage.getItem(SEEN) === "1"; } catch { return false; } };

/** Brand reveal while the national map and season index load. Once per browser session. */
export default function Intro({ ready }: { ready: boolean }) {
  const reduce = useReducedMotion();
  // read on the client after hydration (the server always renders the intro)
  const skip = useSyncExternalStore(noop, seenThisSession, () => false);
  const [minDone, setMinDone] = useState(false);
  useEffect(() => { const t = setTimeout(() => setMinDone(true), reduce ? 300 : MIN_MS); return () => clearTimeout(t); }, [reduce]);
  const show = !skip && !(ready && minDone);
  useEffect(() => { if (!show && !skip) try { sessionStorage.setItem(SEEN, "1"); } catch { /* private window */ } }, [show, skip]);

  return (
    <AnimatePresence>
      {show && (
        <motion.div key="intro" className="fixed inset-0 z-[60] grid place-items-center overflow-hidden bg-(--bg)"
          exit={{ opacity: 0, transition: { duration: skip ? 0 : 0.55, ease: "easeInOut" } }} aria-label="Loading Mungaru" role="status">
          {/* monsoon light: a slow warm-to-cool sky behind the mark */}
          <motion.div aria-hidden className="absolute inset-0"
            style={{ background: "radial-gradient(60% 50% at 50% 42%, rgba(92,200,255,0.16), transparent 70%), radial-gradient(40% 35% at 62% 70%, rgba(240,170,90,0.10), transparent 70%)" }}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 1.2 }} />
          <div className="relative flex flex-col items-center text-center">
            <motion.div initial={{ scale: 0.82, opacity: 0, y: 8 }} animate={{ scale: 1, opacity: 1, y: 0 }}
              transition={{ type: "spring", stiffness: 140, damping: 18 }}
              className="relative h-40 w-40 overflow-hidden rounded-full shadow-[0_20px_60px_rgba(0,0,0,0.55),0_0_0_1px_rgba(255,255,255,0.06)]">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/brand/badge-640.png" alt="" className="h-full w-full" />
              {/* a raindrop of light sweeping across once */}
              {!reduce && (
                <motion.div aria-hidden className="absolute inset-0 bg-gradient-to-r from-transparent via-white/35 to-transparent"
                  initial={{ x: "-120%" }} animate={{ x: "120%" }} transition={{ delay: 0.5, duration: 1.1, ease: "easeInOut" }} />
              )}
            </motion.div>
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25, duration: 0.5 }}
              className="mt-6">
              <Wordmark className="text-[40px] leading-none text-text" />
            </motion.div>
            <motion.div className="mt-3 flex gap-2.5 text-[12px] uppercase tracking-[0.28em] text-text-2"
              initial="h" animate="s" variants={{ s: { transition: { staggerChildren: 0.12, delayChildren: 0.45 } } }}>
              {BRAND.tagline.split(" · ").map((w, i) => (
                <motion.span key={w} variants={{ h: { opacity: 0, y: 6 }, s: { opacity: 1, y: 0 } }} className="flex items-center gap-2.5">
                  {i > 0 && <span className="h-1 w-1 rounded-full bg-focus/70" />}{w}
                </motion.span>
              ))}
            </motion.div>
            <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.9 }}
              className="mt-5 max-w-sm text-[13px] leading-relaxed text-text-3">
              Monsoon onset, dry spells and heavy rain, 1–4 weeks ahead, for every block in India.
            </motion.p>
            <div className="mt-6 h-0.5 w-44 overflow-hidden rounded-full bg-line">
              <motion.div className="h-full bg-focus" initial={{ width: "8%" }}
                animate={{ width: ready ? "100%" : "72%" }} transition={{ duration: ready ? 0.4 : 2.4, ease: "easeOut" }} />
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
