import { useRef, useState, type ReactNode } from "react";
import { Icon24, type IconName } from "../icons";
import { Tip } from "../RelevanceRing";

export interface StageRingItem {
  id: string;
  label: string;
  icon: IconName;
  href: string;
  /** 0–100. 100 draws the ring green. */
  pct: number;
  current?: boolean;
  disabled?: string;
  /** One quiet line in the tooltip (for example "Nothing here yet"). */
  hint?: string;
}

const R = 18;
const C = 2 * Math.PI * R;

function StageRing({ s }: { s: StageRingItem }) {
  const ref = useRef<HTMLAnchorElement & HTMLSpanElement>(null);
  const [tip, setTip] = useState(false);
  const pct = Math.max(0, Math.min(100, Math.round(s.pct)));
  const full = pct >= 100;
  const ring = (
    <svg className="cf-stage-ring" viewBox="0 0 40 40" aria-hidden="true">
      <circle cx="20" cy="20" r={R} className="cf-stage-trk" />
      {pct > 0 && <circle cx="20" cy="20" r={R} className={`cf-stage-arc${full ? " is-full" : ""}`} strokeDasharray={`${(pct / 100) * C} ${C}`} transform="rotate(-90 20 20)" />}
    </svg>
  );
  const label = `${s.label}, ${pct}% done${s.disabled ? `. ${s.disabled}` : ""}${s.hint ? `. ${s.hint}` : ""}`;
  const events = { onPointerEnter: () => setTip(true), onPointerLeave: () => setTip(false), onFocus: () => setTip(true), onBlur: () => setTip(false) };
  return (
    <>
      {s.disabled ? (
        <span ref={ref} className="cf-stage-btn is-disabled" role="link" aria-disabled="true" tabIndex={0} aria-label={label} {...events}>{ring}<Icon24 name={s.icon} size={17} /></span>
      ) : (
        <a ref={ref} className="cf-stage-btn" href={s.href} aria-label={label} aria-current={s.current ? "step" : undefined} {...events}>{ring}<Icon24 name={s.icon} size={17} /></a>
      )}
      <Tip anchor={ref.current} open={tip} id={`stage-tip-${s.id}`} side="bottom">
        <span>{s.label}</span> <span className="cf-faint cf-mono">{pct}%</span>
        {s.disabled && <p>{s.disabled}</p>}
        {s.hint && !s.disabled && <p>{s.hint}</p>}
      </Tip>
    </>
  );
}

/** The four stages as icon buttons wrapped in progress rings. */
export function StageRings({ stages }: { stages: StageRingItem[] }) {
  return <nav className="cf-stage-rings" aria-label="Stages">{stages.map((s) => <StageRing key={s.id} s={s} />)}</nav>;
}

/**
 * Header of the work area: the sidebar toggle at the far left (always visible), the application
 * title and authority, the stage rings centred in the remaining width, actions on the right.
 * On phones the same toggle opens the rail and list as a sheet.
 */
export function AppHeader({ title, meta, stages, right, onToggleList, listOpen, toggleHint }: { title: string; meta?: string; stages?: StageRingItem[]; right?: ReactNode; onToggleList?: () => void; listOpen?: boolean; toggleHint?: string }) {
  const ref = useRef<HTMLButtonElement>(null);
  const [tip, setTip] = useState(false);
  const label = listOpen ? "Hide the sidebar" : "Show the sidebar";
  return (
    <header className="cf-head">
      <div className="cf-head-left">
        {onToggleList && (
          <>
            <button
              ref={ref}
              type="button"
              className="cf-icon-btn is-plain cf-head-toggle"
              aria-label={label}
              aria-expanded={listOpen}
              onClick={onToggleList}
              onPointerEnter={() => setTip(true)}
              onPointerLeave={() => setTip(false)}
              onFocus={() => setTip(true)}
              onBlur={() => setTip(false)}
            >
              <Icon24 name="panel" size={18} />
            </button>
            <Tip anchor={ref.current} open={tip} id="cf-head-toggle-tip" side="bottom">
              <span>{label}</span>
              {toggleHint && <span className="cf-kbd is-dark cf-tip-kbd">{toggleHint}</span>}
            </Tip>
          </>
        )}
        <h1 className="cf-head-title" title={meta ? `${title} · ${meta}` : title}>
          <span className="cf-head-name">{title}</span>
          {meta && <span className="cf-head-meta">{meta}</span>}
        </h1>
      </div>
      {stages && <StageRings stages={stages} />}
      <div className="cf-head-right">{right}</div>
    </header>
  );
}
