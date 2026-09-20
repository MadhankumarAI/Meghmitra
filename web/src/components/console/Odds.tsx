"use client";

/**
 * Chance, shown as chance. Ten cells: "if this week played out ten times, heavy rain in three of
 * them." The filled cells animate so the panel is alive, but nothing here depicts weather arriving
 * — animating rain on the map would tell a farmer it is going to rain, which is not what a 30%
 * chance means. The comparison with the normal rate is the point, so it sits right underneath.
 */
import { motion, useReducedMotion } from "motion/react";
import { Droplets, Sun, Sprout } from "lucide-react";

type Kind = "heavy" | "dry10" | "onset";

const STYLE: Record<Kind, { icon: typeof Droplets; colour: string; happens: string; drop: boolean }> = {
  heavy: { icon: Droplets, colour: "var(--wet)", happens: "heavy rain", drop: true },
  dry10: { icon: Sun, colour: "var(--dry)", happens: "a 10+ day dry spell", drop: false },
  onset: { icon: Sprout, colour: "var(--onset)", happens: "the monsoon arriving", drop: false },
};

export default function Odds({ kind, p, clim }: { kind: Kind; p: number; clim: number }) {
  const reduce = useReducedMotion();
  const s = STYLE[kind];
  const n = Math.max(0, Math.min(10, Math.round(p * 10)));
  const usual = Math.max(0, Math.min(10, Math.round(clim * 10)));
  const Icon = s.icon;

  return (
    <div>
      <div className="flex gap-1" role="img"
        aria-label={`${n} in 10 chance of ${s.happens}; normally ${usual} in 10`}>
        {Array.from({ length: 10 }, (_, i) => {
          const on = i < n;
          return (
            <span key={i} aria-hidden
              className="relative grid h-6 flex-1 place-items-center overflow-hidden rounded-[3px]"
              style={{ background: on ? `color-mix(in srgb, ${s.colour} 22%, transparent)` : "var(--line)" }}>
              {on ? (
                <motion.span style={{ color: s.colour }}
                  initial={reduce ? false : { y: s.drop ? -8 : 0, opacity: 0 }}
                  animate={{ y: 0, opacity: 1 }}
                  transition={reduce ? { duration: 0 } : {
                    delay: i * 0.06, duration: s.drop ? 0.5 : 0.35,
                    repeat: s.drop ? Infinity : 0, repeatDelay: 2.6, repeatType: "loop",
                  }}>
                  <Icon size={13} />
                </motion.span>
              ) : (
                <span className="h-[3px] w-[3px] rounded-full bg-text-3/50" />
              )}
            </span>
          );
        })}
      </div>
      <p className="mt-1.5 text-[11.5px] leading-snug text-text-2">
        If this week played out 10 times, {s.happens} in <b className="text-text">{n}</b> of them
        <span className="text-text-3"> — usually {usual}.</span>
      </p>
    </div>
  );
}
