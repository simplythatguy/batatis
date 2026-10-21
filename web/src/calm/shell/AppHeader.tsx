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
  const label = `${s.label}, ${pct}% done${s.disabled ? `. ${s.disabled}` : ""}`;
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
      </Tip>
    </>
  );
}

/** The four stages as icon buttons wrapped in progress rings. */
export function StageRings({ stages }: { stages: StageRingItem[] }) {
  return <nav className="cf-stage-rings" aria-label="Stages">{stages.map((s) => <StageRing key={s.id} s={s} />)}</nav>;
}

/**
 * Header of the work area: application title and authority on the left, stage rings in the
 * middle, actions on the right. On phones a menu button opens the rail and list as a sheet.
 */
export function AppHeader({ title, meta, stages, right, onMenu, menuLabel = "Applications" }: { title: ReactNode; meta?: ReactNode; stages?: StageRingItem[]; right?: ReactNode; onMenu?: () => void; menuLabel?: string }) {
  return (
    <header className="cf-head">
      <div className="cf-head-left">
        {onMenu && (
          <button type="button" className="cf-icon-btn is-plain cf-head-menu" aria-label={`Open ${menuLabel.toLowerCase()}`} onClick={onMenu}>
            <Icon24 name="menu" size={18} />
          </button>
        )}
        <h1 className="cf-head-title">
          <span className="cf-head-name">{title}</span>
          {meta && <span className="cf-head-meta">{meta}</span>}
        </h1>
      </div>
      {stages && <StageRings stages={stages} />}
      <div className="cf-head-right">{right}</div>
    </header>
  );
}
