import { useRef, useState, type ReactNode } from "react";
import { Icon24, type IconName } from "../icons";
import { Tip } from "../RelevanceRing";
import { EditableTitle } from "./EditableTitle";

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

const RING = { size: 34, r: 15 } as const;

/**
 * One stage or review step as an icon in a progress ring: the ring fills with progress and a done
 * stage gets a check badge; the current one is at full opacity, the others dimmed (no fill). Its name
 * is the accessible name and a label on hover or keyboard focus, never visible text.
 */
export function StageButton({ id, label, ariaLabel, icon, pct, current, done, disabled, count, hue, note, href, onClick }: {
  id: string;
  label: string;
  ariaLabel: string;
  icon: ReactNode;
  pct: number;
  current?: boolean;
  done?: boolean;
  /** Why the stage cannot open yet; it renders as a non-link. */
  disabled?: string;
  /** Items still open, as a small badge on the icon. */
  count?: number;
  /** A section hue for the current tint; the accent otherwise. */
  hue?: string;
  /** One quiet line in the label (for example "Nothing here yet"). */
  note?: string;
  href?: string;
  onClick?: () => void;
}) {
  const ref = useRef<HTMLAnchorElement & HTMLButtonElement & HTMLSpanElement>(null);
  const [tip, setTip] = useState(false);
  const p = Math.max(0, Math.min(100, Math.round(pct)));
  const c = 2 * Math.PI * RING.r;
  const mid = RING.size / 2;
  const events = { onPointerEnter: () => setTip(true), onPointerLeave: () => setTip(false), onFocus: () => setTip(true), onBlur: () => setTip(false) };
  const className = `cf-stage${hue ? ` is-${hue}` : ""}${done ? " is-done" : ""}${disabled ? " is-disabled" : ""}`;
  const body = (
    <span className="cf-stage-ring" aria-hidden="true">
      <svg width={RING.size} height={RING.size} viewBox={`0 0 ${RING.size} ${RING.size}`}>
        <circle className="cf-stage-track" cx={mid} cy={mid} r={RING.r} />
        {p > 0 && <circle className="cf-stage-arc" cx={mid} cy={mid} r={RING.r} strokeDasharray={`${(p / 100) * c} ${c}`} transform={`rotate(-90 ${mid} ${mid})`} />}
      </svg>
      <span className="cf-stage-ico">{icon}</span>
      {done ? <span className="cf-stage-done"><Icon24 name="check" size={9} stroke={3.2} /></span> : count ? <span className="cf-stage-count">{count}</span> : null}
    </span>
  );
  const common = { ref, className, "aria-label": ariaLabel, "aria-current": current ? ("step" as const) : undefined, ...events };
  return (
    <>
      {disabled ? (
        <span {...common} role="link" aria-disabled="true" tabIndex={0}>{body}</span>
      ) : href ? (
        <a {...common} href={href}>{body}</a>
      ) : (
        <button {...common} type="button" onClick={onClick}>{body}</button>
      )}
      <Tip anchor={ref.current} open={tip} id={`stage-tip-${id}`} side="bottom">
        <span>{label}</span>{done ? " ✓" : p > 0 && p < 100 ? <span className="cf-faint cf-mono"> {p}%</span> : null}
        {(disabled || note) && <p>{disabled || note}</p>}
      </Tip>
    </>
  );
}

/** The four applicant stages as icons in progress rings, in order, joined by a hairline. */
export function StageRings({ stages }: { stages: StageRingItem[] }) {
  return (
    <nav className="cf-stages" aria-label="Stages">
      {stages.map((s, i) => {
        const pct = Math.max(0, Math.min(100, Math.round(s.pct)));
        const done = pct >= 100;
        return (
          <StageButton
            key={s.id}
            id={s.id}
            label={s.label}
            ariaLabel={`${i + 1} ${s.label}, ${done ? "done" : `${pct}% done`}${s.disabled ? `. ${s.disabled}` : ""}${s.hint ? `. ${s.hint}` : ""}`}
            icon={<Icon24 name={s.icon} size={16} />}
            pct={pct}
            current={s.current}
            done={done}
            disabled={s.disabled}
            note={s.hint}
            href={s.href}
          />
        );
      })}
    </nav>
  );
}

/**
 * Header of the work area: the sidebar toggle at the far left (always visible), the application
 * title and authority, the stage tabs centred in the remaining width, actions on the right.
 * On phones the same toggle opens the rail and list as a sheet.
 */
export function AppHeader({ title, onRename, renameDisabled, stages, right, onToggleList, listOpen, toggleHint }: {
  title: string;
  /** Renames the open application in place; resolves to an error text, or null when saved. */
  onRename?: (title: string) => Promise<string | null>;
  /** A sent or closed application keeps its name. */
  renameDisabled?: boolean;
  stages?: StageRingItem[];
  right?: ReactNode;
  onToggleList?: () => void;
  listOpen?: boolean;
  toggleHint?: string;
}) {
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
        {/* Just the name: where it goes lives in the application, not beside its title. */}
        <h1 className="cf-head-title">
          {onRename ? <EditableTitle value={title} label="Application name" disabled={renameDisabled} onCommit={onRename} /> : <span className="cf-title-text" title={title}>{title}</span>}
        </h1>
      </div>
      {stages && <StageRings stages={stages} />}
      <div className="cf-head-right">{right}</div>
    </header>
  );
}
