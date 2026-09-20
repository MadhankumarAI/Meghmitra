/** Shares the live MapLibre instance with overlay components (atmosphere layer). */
import type { Map as MLMap } from "maplibre-gl";
import { useSyncExternalStore } from "react";

let current: MLMap | null = null;
const listeners = new Set<() => void>();

export function setMap(m: MLMap | null) {
  current = m;
  listeners.forEach((l) => l());
}
export function useMap(): MLMap | null {
  return useSyncExternalStore(
    (l) => { listeners.add(l); return () => listeners.delete(l); },
    () => current,
    () => null,
  );
}
