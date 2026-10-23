/** Small shared pieces for the account, reviewer, settings and notification screens. */
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { initials } from "../account";
import { AskButton } from "../assistant/AskButton";

/** 24px line icons, currentColor only (same grid and stroke as calm/icons.tsx). */
const P = {
  bell: <><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" /></>,
  hand: <><path d="M18 11V6a2 2 0 0 0-4 0v5M14 10V4a2 2 0 0 0-4 0v6M10 10.5V6a2 2 0 0 0-4 0v8" /><path d="M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.9-6-2.4l-3.6-3.6a2 2 0 0 1 2.8-2.8L7 15" /></>,
  out: <><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><path d="m16 17 5-5-5-5M21 12H9" /></>,
  cog: <><circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M2 12h3M19 12h3M4.9 19.1 7 17M17 7l2.1-2.1" /></>,
  check: <path d="M20 6 9 17l-5-5" />,
  right: <path d="M5 12h14M13 6l6 6-6 6" />,
  back: <path d="M19 12H5M11 18l-6-6 6-6" />,
  search: <><circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" /></>,
  spark: <><path d="M12 3.5l1.8 4.7L18.5 10l-4.7 1.8L12 16.5l-1.8-4.7L5.5 10l4.7-1.8z" /><path d="M19 15.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z" /></>,
  send: <><path d="m22 2-7 20-4-9-9-4z" /><path d="M22 2 11 13" /></>,
  x: <path d="M18 6 6 18M6 6l12 12" />,
  table: <><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M3 9h18M3 15h18M9 3v18" /></>,
  doc: <><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" /><path d="M14 3v5h5M9 13h6M9 17h6" /></>,
  chat: <path d="M21 12a8 8 0 0 1-11.8 7L4 20.5l1.5-5A8 8 0 1 1 21 12z" />,
  chev: <path d="m9 6 6 6-6 6" />,
  list: <path d="m3 17 2 2 4-4M3 7l2 2 4-4M13 6h8M13 12h8M13 18h8" />,
  scale: <><path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1zM2 16l3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1z" /><path d="M7 21h10M12 3v18M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2" /></>,
  alert: <><circle cx="12" cy="12" r="9" /><path d="M12 8v4M12 16h.01" /></>,
  files: <><path d="M20 7h-3a2 2 0 0 1-2-2V2" /><path d="M9 18a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h7l4 4v10a2 2 0 0 1-2 2z" /><path d="M3 7.6v12.8A1.6 1.6 0 0 0 4.6 22h9.8" /></>,
  book: <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2zM22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />,
  clipboard: <><rect x="8" y="2" width="8" height="4" rx="1" /><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2M9 14l2 2 4-4" /></>,
  users: <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" /></>,
  eye: <><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="3" /></>,
  diff: <path d="M12 3v14M5 10h14M5 21h14" />,
  flag: <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1zM4 22v-7" />,
  upload: <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12" />,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  inbox: <><path d="M22 12h-6l-2 3h-4l-2-3H2" /><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" /></>,
  ban: <><circle cx="12" cy="12" r="9" /><path d="m5.6 5.6 12.8 12.8" /></>,
} as const;

export type AcIconName = keyof typeof P;

export function AcIcon({ name, size = 16, stroke = 1.7 }: { name: AcIconName; size?: number; stroke?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {P[name]}
    </svg>
  );
}

/** Provider marks drawn as single-colour glyphs (no brand colours in the calm system). */
export function ProviderMark({ id }: { id: string }) {
  if (id === "microsoft") {
    return (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
        <rect x="1" y="1" width="6.5" height="6.5" rx="0.5" />
        <rect x="8.5" y="1" width="6.5" height="6.5" rx="0.5" opacity="0.75" />
        <rect x="1" y="8.5" width="6.5" height="6.5" rx="0.5" opacity="0.75" />
        <rect x="8.5" y="8.5" width="6.5" height="6.5" rx="0.5" opacity="0.5" />
      </svg>
    );
  }
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
      <path d="M20.5 12.2c0-.6-.1-1.2-.2-1.7H12v3.3h4.8a4.2 4.2 0 0 1-1.8 2.7" />
      <path d="M15 16.5A6.5 6.5 0 1 1 16.4 7" />
    </svg>
  );
}

export function Avatar({ name, size = "md" }: { name: string | null | undefined; size?: "sm" | "md" }) {
  return <span className={`ac-av is-${size}`} aria-hidden="true">{initials(name) || "?"}</span>;
}

/** Seconds left from a Retry-After value, counting down once a second. */
export function useCountdown(): [number, (seconds: number | null) => void] {
  const [until, setUntil] = useState(0);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (until <= now) return;
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, [until, now]);
  const left = Math.max(0, Math.ceil((until - now) / 1000));
  const start = useCallback((seconds: number | null) => {
    const n = Date.now();
    setNow(n);
    setUntil(n + 1000 * (seconds && seconds > 0 ? seconds : 30));
  }, []);
  return [left, start];
}

export function clockText(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m ? `${m}:${String(s).padStart(2, "0")}` : `${s} s`;
}

/**
 * A popover anchored to a trigger: opens beside the rail (to the right, bottom-aligned) or below
 * a header button (right-aligned). Outside pointer and Escape close it and return focus.
 */
export function usePopover() {
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<React.CSSProperties>({});

  useLayoutEffect(() => {
    if (!open || !trigger.current) return;
    const r = trigger.current.getBoundingClientRect();
    // Beside the rail: align to the rail's edge, not the button's, so the panel never covers the rail.
    const rail = trigger.current.closest(".cf-rail, .cf-sidebar, .ac-rail-dock")?.getBoundingClientRect();
    if (r.left < 120) setPos({ left: Math.max(r.right, rail ? Math.min(rail.right, 80) : r.right) + 8, bottom: Math.max(8, window.innerHeight - r.bottom) });
    else setPos({ right: Math.max(8, window.innerWidth - r.right), top: r.bottom + 8 });
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      const t = e.target as Node;
      if (trigger.current?.contains(t) || panel.current?.contains(t)) return;
      setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      e.preventDefault();
      setOpen(false);
      trigger.current?.focus();
    };
    document.addEventListener("pointerdown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return { open, setOpen, trigger, panel, style: pos };
}

/** Page header for the in-app pages (queue, review, settings, notifications). `right` holds actions. */
/** `center` sits in the middle of the bar (the review's step tabs), like the applicant's stage tabs. */
export function PageHead({ title, meta, right, phoneTools, center }: { title: ReactNode; meta?: ReactNode; right?: ReactNode; phoneTools?: ReactNode; center?: ReactNode }) {
  return (
    <header className={`ac-head${center ? " has-center" : ""}`}>
      <h1 className="ac-head-title">
        <span className="ac-head-name">{title}</span>
        {meta && <span className="ac-head-meta">{meta}</span>}
      </h1>
      {center}
      <div className="ac-head-right">
        {right}
        <AskButton />
        {phoneTools && <span className="ac-phone-tools">{phoneTools}</span>}
      </div>
    </header>
  );
}
