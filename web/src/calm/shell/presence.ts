import { useEffect, useRef, useState } from "react";

/**
 * Where a panel that slides in and out is: `entering` after it opens during the visit (so it plays its
 * entrance once, never on page load), `open`, `closing` for `exitMs` after it closes (so it can play its
 * exit before it unmounts), then `closed`. Reduced motion skips straight to `closed`.
 */
export type Presence = "entering" | "open" | "closing" | "closed";

const reduced = () => typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;

export function usePresence(open: boolean, exitMs: number): Presence {
  const [prev, setPrev] = useState(open);
  const [phase, setPhase] = useState<Presence>(open ? "open" : "closed");
  // Derived during render, not in an effect: a closing panel must never drop out for one commit.
  if (prev !== open) {
    setPrev(open);
    setPhase(open ? "entering" : reduced() ? "closed" : "closing");
  }
  useEffect(() => {
    if (phase !== "closing") return;
    const t = window.setTimeout(() => setPhase("closed"), exitMs);
    return () => window.clearTimeout(t);
  }, [phase, exitMs]);
  return phase;
}

/** The latest non-null value, so a dialog keeps showing what it was about while it fades out. */
export function useLast<T>(value: T | null | undefined): T | null {
  const last = useRef<T | null>(value ?? null);
  if (value != null) last.current = value;
  return value ?? last.current;
}
