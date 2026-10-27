import { useEffect, useRef, type ReactNode } from "react";

/** Thin-stroke icons drawn at 16px, `currentColor` only. */
const PATHS: Record<string, ReactNode> = {
  clip: <path d="M10.5 4.5 5.8 9.2a1.5 1.5 0 0 0 2.1 2.1l5-5a3 3 0 0 0-4.2-4.2l-5 5a4.5 4.5 0 0 0 6.4 6.4l4.2-4.2" />,
  doc: <><path d="M3.5 2.5h6l3 3v8h-9z" /><path d="M5.5 7.5h5M5.5 10h5" /></>,
  close: <path d="m4.5 4.5 7 7m0-7-7 7" />,
  warn: <><path d="M8 1.8 15 14H1z" /><path d="M8 6.5v3.3M8 11.8v.1" /></>,
  arrow: <path d="M3 8h10M9 4l4 4-4 4" />,
  chev: <path d="m6 4 4 4-4 4" />,
  back: <path d="M13 8H3M7 4 3 8l4 4" />,
  check: <path d="m3.5 8.5 3 3 6-7" />,
  search: <><circle cx="7" cy="7" r="4.5" /><path d="m10.5 10.5 3 3" /></>,
  upload: <path d="M8 11V3.5M5 6.5l3-3 3 3M3 12.5h10" />,
  external: <path d="M6.5 3.5h-3v9h9v-3M9 3.5h3.5V7M12.5 3.5 7.5 8.5" />,
  retry: <><path d="M13 8a5 5 0 1 1-1.5-3.5" /><path d="M13 2.5v3h-3" /></>,
  plus: <path d="M8 3.5v9M3.5 8h9" />,
  info: <><circle cx="8" cy="8" r="6" /><path d="M8 7.2v3.6M8 5v.1" /></>,
};

export function CIcon({ name, size = 16 }: { name: keyof typeof PATHS; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {PATHS[name]}
    </svg>
  );
}

export function MoreIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <circle cx="3" cy="8" r="1.3" />
      <circle cx="8" cy="8" r="1.3" />
      <circle cx="13" cy="8" r="1.3" />
    </svg>
  );
}

export function Eyebrow({ children, plain = false, as: Tag = "span", id }: { children: ReactNode; plain?: boolean; as?: "span" | "p" | "h2"; id?: string }) {
  return <Tag id={id} className={`cf-eyebrow${plain ? " is-plain" : ""}`}>{children}</Tag>;
}

/** The one standing boundary: a short chip that opens a short explanation (touch, keyboard and pointer). */
export function CompletenessNote() {
  return (
    <details className="cf-complete">
      <summary>Completeness only</summary>
      <p>Checks administrative completeness. It never says the design complies or is safe.</p>
    </details>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return <span className="cf-kbd" aria-hidden="true">{children}</span>;
}

export type DotTone = "blocking" | "warning" | "pending" | "done";

export function Dot({ tone }: { tone: DotTone }) {
  return <span className={`cf-dot is-${tone}`} aria-hidden="true" />;
}

/** True on Apple platforms, for the ⌘ / Ctrl hint. */
export const MOD_KEY = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform) ? "⌘" : "Ctrl";

/** A modal `<dialog>` driven by `open`. Esc and the backdrop close it through `onClose`. */
export function Modal({ open, onClose, labelledBy, className = "", children }: { open: boolean; onClose: () => void; labelledBy: string; className?: string; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open) {
      delete d.dataset.closing;
      if (!d.open) d.showModal();
      return;
    }
    if (!d.open) return;
    // Let a stylesheet's exit transition (keyed on data-closing) finish before leaving the top layer.
    d.dataset.closing = "";
    const running = d.getAnimations?.() ?? [];
    const finish = () => { delete d.dataset.closing; if (d.open) d.close(); };
    if (!running.length) { finish(); return; }
    let live = true;
    void Promise.allSettled(running.map((a) => a.finished)).then(() => { if (live) finish(); });
    return () => { live = false; };
  }, [open]);
  return (
    <dialog
      ref={ref}
      className={`cf-modal ${className}`.trim()}
      aria-labelledby={labelledBy}
      onClose={onClose}
      onCancel={(e) => { e.preventDefault(); onClose(); }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      {children}
    </dialog>
  );
}

export function ConfirmDialog({ open, title, body, confirm, cancel, onConfirm, onClose }: { open: boolean; title: string; body: ReactNode; confirm: string; cancel: string; onConfirm: () => void; onClose: () => void }) {
  return (
    <Modal open={open} onClose={onClose} labelledBy="cf-confirm-title" className="cf-confirm">
      <div className="cf-modal-body">
        <h2 id="cf-confirm-title" className="cf-modal-title">{title}</h2>
        <div className="cf-muted">{body}</div>
      </div>
      <div className="cf-modal-foot">
        <button type="button" className="cf-btn" onClick={onClose} autoFocus>{cancel}</button>
        <button type="button" className="cf-btn is-primary" onClick={onConfirm}>{confirm}</button>
      </div>
    </Modal>
  );
}
