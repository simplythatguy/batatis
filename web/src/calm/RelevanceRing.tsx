import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { BAND_LABEL, BAND_SHORT, pct, type Band, type Shown } from "./relevance";
import { useRelevance } from "./useRelevance";

const ESTIMATE = "Batatis estimate from your description. Not a compliance decision.";

/**
 * A small glass tooltip pinned to an anchor, rendered in <body> so glass panels
 * (backdrop-filter) and scroll panes never clip it.
 */
export function Tip({ anchor, open, id, children, side = "top" }: { anchor: HTMLElement | null; open: boolean; id: string; children: ReactNode; side?: "top" | "right" | "bottom" }) {
  const tip = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);
  useLayoutEffect(() => {
    if (!open || !anchor) return setPos(null);
    const r = anchor.getBoundingClientRect();
    const w = tip.current?.offsetWidth ?? 260;
    const h = tip.current?.offsetHeight ?? 80;
    if (side === "right") {
      setPos({ left: r.right + 10, top: Math.min(Math.max(8, r.top + r.height / 2 - h / 2), window.innerHeight - h - 8) });
      return;
    }
    const left = Math.min(Math.max(8, r.left + r.width / 2 - w / 2), window.innerWidth - w - 8);
    const below = side === "bottom" || r.top - h - 10 < 8;
    setPos({ left, top: below ? r.bottom + 8 : r.top - h - 8 });
  }, [open, anchor, side]);
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
  shown: given,
  aggregate,
  size = 16,
  focusable = true,
}: {
  /** Article or sentence id: reads the shared scores through the guard. */
  id?: string;
  /** A precomputed score (section rings pass their strongest article). */
  shown?: Shown;
  aggregate?: "section" | "part" | "subsection";
  size?: 16 | 22;
  focusable?: boolean;
}) {
  const rel = useRelevance();
  const s: Shown = given ?? (id ? rel.shown(id) : { p: undefined, band: "unscored", screenedOnly: false });
  const { p, band } = s;
  const tipId = useId();
  const ref = useRef<HTMLSpanElement>(null);
  const [open, setOpen] = useState(false);
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(timer.current), []);
  const show = () => { window.clearTimeout(timer.current); timer.current = window.setTimeout(() => setOpen(true), 120); };
  const hide = () => { window.clearTimeout(timer.current); setOpen(false); };
  const label =
    band === "unscored"
      ? "Relevance estimate: not scored"
      : `Relevance estimate ${pct(p!)}${aggregate ? ` (highest in this ${aggregate})` : ""}: ${BAND_SHORT[band]}`;
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
            <p>{rel.result ? "This article has no relevance score for your project." : "Score relevance in the code library to see how likely each article applies."}</p>
          </>
        ) : (
          <>
            <div className="cf-tip-head">
              <span className="cf-mono">{aggregate ? `Highest in this ${aggregate}: ` : ""}{pct(p!, 1)}</span>
              <span className={`cf-band is-${band}`}>{BAND_LABEL[band]}</span>
            </div>
            {s.screenedOnly && <p>Screened only: the closer second look did not judge this article, so it never shows yellow or red.</p>}
            <p>{ESTIMATE}</p>
            <p className="cf-faint cf-mono">{rel.result?.model ? `Estimate version ${rel.result.model}` : ""}{rel.stale ? `${rel.result?.model ? " · " : ""}Out of date` : ""}</p>
          </>
        )}
      </Tip>
    </>
  );
}

/** The visible band label pill (never colour alone). */
export function BandPill({ id }: { id: string }) {
  const rel = useRelevance();
  const { band } = rel.shown(id);
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
    { band: "unscored", text: "Dashed: not scored yet, or no relevance score." },
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
        <p>{ESTIMATE} The arc shows the percentage. Only the 60 articles the closer second look judged can be yellow or red.</p>
        {fallback && <p className="cf-faint">Cut-offs are placeholders until the benchmark study sets them.</p>}
      </Tip>
    </>
  );
}
