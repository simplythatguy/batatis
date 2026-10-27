/**
 * Keeps a closing popup, menu or disclosure mounted until its CSS exit transition ends. While
 * `leaving`, the element carries `data-leaving` so the stylesheet can fade it out; with no transition
 * (reduced motion, or no style for it) it unmounts at once.
 */
import { useLayoutEffect, useState, type RefObject } from "react";

export function usePresence(open: boolean, ref: RefObject<HTMLElement | null>) {
  const [mounted, setMounted] = useState(open);
  if (open && !mounted) setMounted(true);
  const leaving = mounted && !open;
  useLayoutEffect(() => {
    if (!leaving) return;
    // Reading the animations flushes style, so the transition to the data-leaving state has started.
    const running = ref.current?.getAnimations?.() ?? [];
    if (!running.length) { setMounted(false); return; }
    let live = true;
    void Promise.allSettled(running.map((a) => a.finished)).then(() => { if (live) setMounted(false); });
    return () => { live = false; };
  }, [leaving, ref]);
  return { mounted: open || mounted, leaving };
}
