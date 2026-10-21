import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { BAND_LABEL, BAND_SHORT, bandFor, pct, type Band } from "./relevance";
import { scoreFor, useRelevance } from "./useRelevance";

const ESTIMATE = "Jev estimate from your description. Not a compliance decision.";

/**
 * A small glass tooltip pinned to an anchor, rendered in <body> so glass panels
 * (backdrop-filter) and scroll panes never clip it.
 */
export function Tip({ anchor, open, id, children }: { anchor: HTMLElement | null; open: boolean; id: string; children: ReactNode }) {
  const tip = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ left: number; top: number; below: boolean } | null>(null);
  useLayoutEffect(() => {
    if (!open || !anchor) return setPos(null);
    const r = anchor.getBoundingClientRect();
    const w = tip.current?.offsetWidth ?? 260;
    const h = tip.current?.offsetHeight ?? 80;
    const left = Math.min(Math.max(8, r.left + r.width / 2 - w / 2), window.innerWidth - w - 8);
    const below = r.top - h - 10 < 8;
    setPos({ left, top: below ? r.bottom + 8 : r.top - h - 8, below });
  }, [open, anchor]);
  if (!open || !anchor) return null;
  return createPortal(
    <div ref={tip} id={id} role="tooltip" className="cf-tip" style={pos ? { left: pos.left, top: pos.top } : { left: -9999, top: -9999 }}>
      {children}
    </div>,
    document.body,
  );
}

const R = { 16: { r: 6.25, w: 1.5 }, 22: { r: 9, w: 2 } } as const;

/** The ring itself, no interaction. `band` decides the colour; the arc length is p. */
export function RingGlyph({ p, band, size = 16 }: { p: number | undefined; band: Band; size?: 16 | 22 }) {
  const { r, w } = R[size];
  const c = 2 * Math.PI * r;
  const mid = size / 2;
  const arc = band === "unscored" || band === "zero" || p == null ? 0 : Math.max(0.04, Math.min(1, p)) * c;
  return (
    <svg className={`cf-ring-svg is-${band}`} width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
      <circle className="cf-ring-track" cx={mid} cy={mid} r={r} strokeWidth={w} strokeDasharray={band === "unscored" ? "2 2.2" : undefined} fill="none" />
      {arc > 0 && (
        <circle
          className="cf-ring-arc"
          cx={mid}
          cy={mid}
          r={r}
          strokeWidth={w}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={`${arc} ${c}`}
          transform={`rotate(-90 ${mid} ${mid})`}
        />
      )}
    </svg>
  );
}

/**
 * The one relevance ring. Pass an article or provision `id` (reads the shared scores) or a raw `p`.
 * `aggregate` marks a section/part ring that shows its highest article.
 * Focusable unless `focusable={false}` (tree rows show the same detail in their hover card).
 */
export function RelevanceRing({
  id,
  p: given,
  aggregate,
  size = 16,
  focusable = true,
}: {
  id?: string;
  p?: number;
  aggregate?: "section" | "part" | "subsection";
  size?: 16 | 22;
  focusable?: boolean;
}) {
  const rel = useRelevance();
  const p = given ?? (id ? scoreFor(rel.display, id) : undefined);
  // An unscored case shows dashed rings; a scored case without this article reads as not scored too.
  const band = bandFor(p, rel.cutoffs);
  const tipId = useId();
  const ref = useRef<HTMLSpanElement>(null);
  const [open, setOpen] = useState(false);
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(timer.current), []);
  const show = () => { window.clearTimeout(timer.current); timer.current = window.setTimeout(() => setOpen(true), 120); };
  const hide = () => { window.clearTimeout(timer.current); setOpen(false); };
  const label =
    band === "unscored"
      ? "Jev relevance: not scored"
      : `Jev relevance ${pct(p!)}${aggregate ? ` (highest in this ${aggregate})` : ""}: ${BAND_SHORT[band]}`;
  return (
    <>
      <span
        ref={ref}
        className={`cf-ring is-${size}`}
        role={focusable ? "button" : "img"}
        tabIndex={focusable ? 0 : -1}
        aria-label={label}
        aria-describedby={open ? tipId : undefined}
        onPointerEnter={show}
        onPointerLeave={hide}
        onFocus={focusable ? show : undefined}
        onBlur={hide}
        onKeyDown={(e) => { if (e.key === "Escape") hide(); }}
        onClick={focusable ? (e) => { e.stopPropagation(); setOpen((v) => !v); } : undefined}
      >
        <RingGlyph p={p} band={band} size={size} />
      </span>
      <Tip anchor={ref.current} open={open} id={tipId}>
        {band === "unscored" ? (
          <>
            <div className="cf-tip-head">Not scored</div>
            <p>{rel.result ? "This article has no Jev score for your project." : "Score relevance in the code library to see how likely each article applies."}</p>
          </>
        ) : (
          <>
            <div className="cf-tip-head">
              <span className="cf-mono">{aggregate ? `Highest in this ${aggregate}: ` : ""}{pct(p!, 1)}</span>
              <span className={`cf-band is-${band}`}>{BAND_LABEL[band]}</span>
            </div>
            <p>{ESTIMATE}</p>
            <p className="cf-faint cf-mono">{rel.result?.model ? `Model ${rel.result.model}` : ""}{rel.stale ? `${rel.result?.model ? " · " : ""}Out of date` : ""}</p>
          </>
        )}
      </Tip>
    </>
  );
}

/** The visible band label pill (never colour alone). */
export function BandPill({ id }: { id: string }) {
  const rel = useRelevance();
  const band = bandFor(scoreFor(rel.display, id), rel.cutoffs);
  return <span className={`cf-band is-${band}`}>{BAND_LABEL[band]}</span>;
}

/** The "?" legend: the four states and the cut-offs in use. */
export function RingLegend() {
  const rel = useRelevance();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLButtonElement>(null);
  const tipId = useId();
  const { x, y, fallback } = rel.cutoffs;
  const rows: { band: Band; p?: number; text: string }[] = [
    { band: "high", p: 0.8, text: `${BAND_LABEL.high}. ${pct(y)} or more.` },
    { band: "mid", p: 0.4, text: `${BAND_LABEL.mid}. ${pct(x)} to under ${pct(y)}.` },
    { band: "low", p: 0.1, text: `${BAND_LABEL.low}. Above 0 and under ${pct(x)}.` },
    { band: "zero", p: 0, text: "0%: no sign it applies." },
    { band: "unscored", text: "Dashed: not scored yet." },
  ];
  return (
    <>
      <button
        ref={ref}
        type="button"
        className="cf-icon-btn is-xs cf-legend-btn"
        aria-label="What the rings mean"
        aria-expanded={open}
        aria-controls={open ? tipId : undefined}
        onClick={() => setOpen((v) => !v)}
        onBlur={() => setOpen(false)}
        onKeyDown={(e) => { if (e.key === "Escape") setOpen(false); }}
      >
        ?
      </button>
      <Tip anchor={ref.current} open={open} id={tipId}>
        <div className="cf-tip-head">What the rings mean</div>
        <ul className="cf-legend">
          {rows.map((r) => (
            <li key={r.band}><RingGlyph p={r.p} band={r.band} /> {r.text}</li>
          ))}
        </ul>
        <p>{ESTIMATE} The arc shows the percentage.</p>
        {fallback && <p className="cf-faint">Cut-offs are placeholders until the benchmark study sets them.</p>}
      </Tip>
    </>
  );
}
