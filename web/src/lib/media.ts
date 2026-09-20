"use client";

/**
 * Viewport width as React state, read correctly on the first client render (no flash from an
 * effect running a frame later). Server and pre-hydration render assume the wide layout, which
 * is the one the desktop console was designed for.
 */
import { useSyncExternalStore } from "react";

const WIDE = "(min-width: 768px)";

function subscribe(cb: () => void) {
  const m = window.matchMedia(WIDE);
  m.addEventListener("change", cb);
  return () => m.removeEventListener("change", cb);
}

/** true on tablet and desktop, false on a phone. */
export const useWide = () =>
  useSyncExternalStore(subscribe, () => window.matchMedia(WIDE).matches, () => true);
