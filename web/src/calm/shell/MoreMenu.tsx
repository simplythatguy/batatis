import { useEffect, useRef, useState } from "react";
import { Icon24 } from "../icons";
import { usePresence } from "../usePresence";

function useOutsideClose(open: boolean, close: () => void, ...refs: React.RefObject<HTMLElement | null>[]) {
  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      if (refs.some((r) => r.current?.contains(e.target as Node))) return;
      close();
    };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);
}

/** The `⋯` menu: links or actions, arrow keys move, Esc closes and returns focus. */
export function MoreMenu({ items, label = "More" }: { items: { label: string; href?: string; onClick?: () => void; hint?: string; separator?: boolean; disabled?: boolean }[]; label?: string }) {
  const [open, setOpen] = useState(false);
  const btn = useRef<HTMLButtonElement>(null);
  const pop = useRef<HTMLDivElement>(null);
  useOutsideClose(open, () => setOpen(false), btn, pop);
  // Stays on screen while it fades out (when the stylesheet gives it an exit transition).
  const { mounted, leaving } = usePresence(open, pop);
  const wasOpen = useRef(false);
  useEffect(() => {
    const at = document.activeElement;
    if (open) pop.current?.querySelector<HTMLElement>("[role=menuitem]:not(:disabled)")?.focus();
    else if (wasOpen.current && (!at || at === document.body || pop.current?.contains(at))) btn.current?.focus();
    wasOpen.current = open;
  }, [open]);
  const close = () => setOpen(false);
  function onMenuKey(e: React.KeyboardEvent) {
    const list = [...(pop.current?.querySelectorAll<HTMLElement>("[role=menuitem]:not(:disabled)") ?? [])];
    const at = list.indexOf(document.activeElement as HTMLElement);
    const to = (n: number) => { e.preventDefault(); list[(n + list.length) % list.length]?.focus(); };
    if (e.key === "ArrowDown") to(at + 1);
    else if (e.key === "ArrowUp") to(at - 1);
    else if (e.key === "Home") to(0);
    else if (e.key === "End") to(list.length - 1);
    else if (e.key === "Escape") { e.preventDefault(); e.nativeEvent.stopImmediatePropagation(); close(); btn.current?.focus(); }
    else if (e.key === "Tab") close();
  }
  return (
    <div className="cf-more">
      <button ref={btn} type="button" className="cf-icon-btn is-plain" aria-label={label} aria-expanded={open} aria-haspopup="menu" onClick={() => setOpen((v) => !v)}>
        <Icon24 name="more" size={18} />
      </button>
      {mounted && (
        <div ref={pop} className="cf-pop cf-menu" role="menu" aria-label={label} onKeyDown={onMenuKey} data-leaving={leaving || undefined}>
          {items.map((it) => (
            <div key={it.label} role="none">
              {it.separator && <hr role="separator" />}
              {it.href ? (
                <a role="menuitem" tabIndex={-1} href={it.href} onClick={close}>{it.label}{it.hint && <span className="cf-kbd is-dark" aria-hidden="true">{it.hint}</span>}</a>
              ) : (
                <button role="menuitem" tabIndex={-1} type="button" disabled={it.disabled} aria-disabled={it.disabled || undefined} onClick={() => { close(); it.onClick?.(); }}>{it.label}{it.hint && <span className="cf-kbd is-dark" aria-hidden="true">{it.hint}</span>}</button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
