import { useEffect, useRef, useState, type ReactNode } from "react";
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

const STAGE_TIP = "cf-stage-tip";

/**
 * One stage or review step (user decision 2026-10-22, "Option A+B"): no fill, pill or shadow in any
 * state. The current one shows its one-word name beside its icon at full opacity; the others are the
 * icon alone, dimmed and brighter on hover or keyboard focus, a locked one fainter still. Compact cues
 * keep the state: a small check mark once done, a thin line at the foot while part of the way through,
 * and the open count as a quiet number. Name and progress are also the accessible name and a label on
 * hover or keyboard focus.
 */
export function StageButton({ id, label, ariaLabel, icon, pct, current, done, disabled, count, note, href, onClick }: {
  id: string;
  label: string;
  ariaLabel: string;
  icon: ReactNode;
  pct: number;
  current?: boolean;
  done?: boolean;
  /** Why the stage cannot open yet; it renders as a non-link. */
  disabled?: string;
  /** Items still open, as a quiet number beside the icon. */
  count?: number;
  /** One quiet line in the label (for example "Nothing here yet"). */
  note?: string;
  href?: string;
  onClick?: () => void;
}) {
  const ref = useRef<HTMLAnchorElement & HTMLButtonElement & HTMLSpanElement>(null);
  const [tip, setTip] = useState(false);
  // One stage label at a time: keyboard focus on one stage and the pointer on another would overlap.
  useEffect(() => {
    const other = (e: Event) => { if ((e as CustomEvent<string>).detail !== id) setTip(false); };
    window.addEventListener(STAGE_TIP, other);
    return () => window.removeEventListener(STAGE_TIP, other);
  }, [id]);
  const show = () => { window.dispatchEvent(new CustomEvent(STAGE_TIP, { detail: id })); setTip(true); };
  const p = Math.max(0, Math.min(100, Math.round(pct)));
  const events = { onPointerEnter: show, onPointerLeave: () => setTip(false), onFocus: show, onBlur: () => setTip(false) };
  const className = `cf-stage${done ? " is-done" : ""}${disabled ? " is-disabled" : ""}`;
  const body = (
    <>
      <span className="cf-stage-glyph" aria-hidden="true">
        <span className="cf-stage-ico">{icon}</span>
        {done && <span className="cf-stage-done"><Icon24 name="check" size={8} stroke={3.4} /></span>}
      </span>
      {current && <span className="cf-stage-word">{label}</span>}
      {count ? <span className="cf-stage-count" aria-hidden="true">{count}</span> : null}
      {!done && p > 0 && p < 100 && <span className="cf-stage-bar" aria-hidden="true"><span style={{ width: `${p}%` }} /></span>}
    </>
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

/** The four applicant stages as icons, in order. */
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
  /** Omitted where another control names the page (the code library's application picker). */
  title?: string;
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
        {title != null && (
          <h1 className="cf-head-title">
            {onRename ? <EditableTitle value={title} label="Application name" disabled={renameDisabled} onCommit={onRename} /> : <span className="cf-title-text" title={title}>{title}</span>}
          </h1>
        )}
      </div>
      {stages && <StageRings stages={stages} />}
      <div className="cf-head-right">{right}</div>
    </header>
  );
}
