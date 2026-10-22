import { useRef, useState, type ReactNode } from "react";
import { Icon24, type IconName } from "../icons";
import { Tip } from "../RelevanceRing";

export interface RailDestination {
  id: string;
  label: string;
  icon: IconName;
  /** Navigate with a link, or run an action (open the assistant). */
  href?: string;
  onClick?: () => void;
  current?: boolean;
  /** Small accent dot (unread, returned). */
  badge?: boolean;
  /** Keyboard hint shown in the tooltip, e.g. "⌘B". */
  shortcut?: string;
}

function RailButton({ d }: { d: RailDestination }) {
  const ref = useRef<HTMLElement>(null);
  const [tip, setTip] = useState(false);
  const common = {
    className: "cf-rail-btn",
    "aria-label": d.badge ? `${d.label} (new)` : d.label,
    "aria-current": d.current ? ("page" as const) : undefined,
    onPointerEnter: () => setTip(true),
    onPointerLeave: () => setTip(false),
    onFocus: () => setTip(true),
    onBlur: () => setTip(false),
  };
  const body = (
    <>
      <Icon24 name={d.icon} />
      {d.badge && <span className="cf-rail-badge" aria-hidden="true" />}
    </>
  );
  return (
    <>
      {d.href ? (
        <a ref={ref as React.RefObject<HTMLAnchorElement>} href={d.href} onClick={d.onClick} {...common}>{body}</a>
      ) : (
        <button ref={ref as React.RefObject<HTMLButtonElement>} type="button" onClick={d.onClick} {...common}>{body}</button>
      )}
      <Tip anchor={ref.current} open={tip} id={`rail-tip-${d.id}`} side="right">
        <span>{d.label}</span>
        {d.shortcut && <span className="cf-kbd is-dark cf-tip-kbd">{d.shortcut}</span>}
      </Tip>
    </>
  );
}

/**
 * The far-left icon rail: brand, then the destinations; at the bottom the notifications bell and
 * the account avatar. Destinations are a prop, so the applicant (Applications, Code library)
 * and the reviewer (Queue, Code library) share one component. The two
 * bottom slots are filled by the accounts UI (routes.extra.tsx).
 */
export function Rail({ destinations, notificationsSlot, accountSlot }: { destinations: RailDestination[]; notificationsSlot?: ReactNode; accountSlot?: ReactNode }) {
  return (
    <nav className="cf-rail" aria-label="Main">
      <a className="cf-rail-mark" href="#/" aria-label="Batatis home"><span className="cf-mark" aria-hidden="true" /></a>
      {destinations.map((d) => <RailButton key={d.id} d={d} />)}
      <span className="cf-rail-spacer" />
      <div className="cf-rail-foot">
        {notificationsSlot}
        {accountSlot}
      </div>
    </nav>
  );
}

/** The plain avatar (initials), used until the accounts UI supplies its menu. */
export function RailAvatar({ initials, label }: { initials: string; label: string }) {
  return <span className="cf-avatar" role="img" aria-label={label}>{initials}</span>;
}
