"use client";

import { useEffect, useMemo, useState } from "react";
import { Search as SearchIcon } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useConsole, type BlockMeta } from "@/lib/store";

const norm = (s: string) =>
  s.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

interface Row { b: BlockMeta; score: number }

/** Rank: name prefix > word prefix in name > district/state match. */
function rank(blocks: BlockMeta[], q: string): Row[] {
  const t = norm(q.trim());
  if (!t) return [];
  const out: Row[] = [];
  for (const b of blocks) {
    const n = norm(b.name);
    const local = b.names ? Object.values(b.names).filter(Boolean) as string[] : [];
    let score = -1;
    if (n === t || local.includes(q.trim())) score = 100;
    else if (local.some((x) => x.startsWith(q.trim()))) score = 85;
    else if (n.startsWith(t)) score = 80 - n.length / 100;
    else if (n.split(/[\s-]/).some((w) => w.startsWith(t))) score = 60;
    else if (norm(b.district).startsWith(t)) score = 40;
    else if (n.includes(t)) score = 30;
    else if (norm(b.state).startsWith(t)) score = 10;
    if (score >= 0) out.push({ b, score });
  }
  return out.sort((a, z) => z.score - a.score).slice(0, 8);
}

export default function Search({ blocks }: { blocks: BlockMeta[] }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [cur, setCur] = useState(0);
  const results = useMemo(() => rank(blocks, q), [blocks, q]);

  // reset in the same event that opens it, not in an effect afterwards
  const openSearch = () => { setQ(""); setCur(0); setOpen(true); };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = (e.target as HTMLElement)?.closest("input,textarea");
      if ((e.key === "k" && (e.ctrlKey || e.metaKey)) || (e.key === "/" && !typing)) {
        e.preventDefault();
        setQ(""); setCur(0); setOpen(true);
      } else if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const choose = (b: BlockMeta) => {
    const s = useConsole.getState();
    s.setSelected(b.i);
    s.setFocus(b.bb);
    setOpen(false);
  };

  return (
    <>
      <button
        onClick={openSearch}
        className="panel pointer-events-auto flex min-h-11 cursor-pointer items-center gap-2.5 px-3.5 text-[13px] text-text-3 transition-colors hover:text-text-2"
        aria-label="Search blocks (Ctrl+K)"
      >
        <SearchIcon size={16} />
        <span className="whitespace-nowrap">Search blocks</span>
        <kbd className="ml-3 hidden whitespace-nowrap rounded border border-line px-1.5 py-0.5 text-[10px] text-text-3 min-[1500px]:inline">Ctrl K</kbd>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            key="scrim"
            className="fixed inset-0 z-40 bg-black/50"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, transition: { duration: 0.12 } }}
            onClick={() => setOpen(false)}
          >
            <motion.div
              role="dialog"
              aria-modal="true"
              aria-label="Search blocks"
              initial={{ opacity: 0, y: -8, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -6, transition: { duration: 0.12 } }}
              transition={{ type: "spring", stiffness: 500, damping: 36 }}
              onClick={(e) => e.stopPropagation()}
              className="panel mx-auto mt-[14vh] w-140 max-w-[calc(100vw-32px)] overflow-hidden"
            >
              <div className="flex items-center gap-3 border-b border-line px-4">
                <SearchIcon size={18} className="text-text-3" />
                <input
                  autoFocus
                  value={q}
                  onChange={(e) => { setQ(e.target.value); setCur(0); }}
                  onKeyDown={(e) => {
                    if (e.key === "ArrowDown") { e.preventDefault(); setCur((c) => Math.min(results.length - 1, c + 1)); }
                    else if (e.key === "ArrowUp") { e.preventDefault(); setCur((c) => Math.max(0, c - 1)); }
                    else if (e.key === "Enter" && results[cur]) choose(results[cur].b);
                  }}
                  placeholder="Kundgol, Dharwad, Karnataka…"
                  aria-label="Block, district or state"
                  className="h-14 flex-1 bg-transparent text-[16px] text-text outline-none placeholder:text-text-3"
                />
              </div>
              <ul role="listbox" aria-label="Matching blocks" className="max-h-90 overflow-y-auto py-1.5">
                {results.map((r, k) => (
                  <li
                    key={r.b.i}
                    role="option"
                    aria-selected={k === cur}
                    onMouseEnter={() => setCur(k)}
                    onClick={() => choose(r.b)}
                    className={`mx-1.5 flex cursor-pointer items-baseline justify-between rounded-md px-3 py-2.5 ${
                      k === cur ? "bg-surface-2" : ""
                    }`}
                  >
                    <span className="text-[14px] font-medium">
                      {r.b.name}
                      {r.b.names?.kn || r.b.names?.hi ? (
                        <span className="ml-2 font-normal text-text-3" style={{ fontFamily: "var(--font-indic)" }}>
                          {r.b.names.kn ?? r.b.names.hi}
                        </span>
                      ) : null}
                    </span>
                    <span className="text-[12px] text-text-3">{r.b.district} · {r.b.state}</span>
                  </li>
                ))}
                {q.trim() && results.length === 0 && (
                  <li className="px-4 py-6 text-center text-[13px] text-text-3">
                    No block matches “{q}”. Try the district name.
                  </li>
                )}
                {!q.trim() && (
                  <li className="px-4 py-5 text-[12px] text-text-3">
                    Search {blocks.length.toLocaleString("en-IN")} blocks across India. Press
                    <kbd className="mx-1 rounded border border-line px-1">↵</kbd> to fly there.
                  </li>
                )}
              </ul>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
