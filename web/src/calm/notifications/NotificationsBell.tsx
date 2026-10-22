/** Rail bell with an unread dot and a popover list; #/notifications shows the same list full-page (phones). */
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useAccount } from "../account";
import { AcIcon, Avatar, PageHead, usePopover } from "../auth/bits";
import { Tip } from "../RelevanceRing";
import { loadNotifications, notificationHref, notificationText, openedPanel, rowKeys, shortTime, startPolling, useNotifications } from "./notifications";

/** Poll while signed in (shared across every bell and the page). */
function useNotificationPolling(enabled: boolean) {
  useEffect(() => (enabled ? startPolling() : undefined), [enabled]);
}

function NotificationList({ onPick, now }: { onPick?: () => void; now: number }) {
  const n = useNotifications();
  const role = useAccount().user?.role;
  if (n.phase === "unavailable") return <p className="ac-note-empty">Notifications aren’t available on this server yet.</p>;
  if (n.phase === "error") {
    return (
      <p className="ac-note-empty">
        Notifications didn’t load. <button type="button" className="ac-link" onClick={() => void loadNotifications()}>Try again</button>
      </p>
    );
  }
  if (n.phase === "idle" || (n.phase === "loading" && !n.items.length)) return <p className="ac-note-empty">Loading…</p>;
  if (!n.items.length) {
    return <p className="ac-note-empty">Nothing yet. When a reviewer changes an application’s status or sends a message, it shows up here.</p>;
  }
  const fresh = new Set(n.fresh);
  const keys = rowKeys(n.items);
  return (
    <ul className="ac-notes" role="list">
      {n.items.map((item, i) => (
        <li key={keys[i]}>
          <a className={`ac-note${fresh.has(item.id) || !item.read ? " is-new" : ""}`} href={notificationHref(item, role)} onClick={onPick}>
            <Avatar name={item.actor?.name} size="sm" />
            <span className="ac-note-text">{notificationText(item)}</span>
            <span className="ac-note-time">{shortTime(item.created_at, now)}</span>
            {(fresh.has(item.id) || !item.read) && <span className="ac-note-dot" aria-label="New" />}
          </a>
        </li>
      ))}
    </ul>
  );
}

export function NotificationsBell() {
  const account = useAccount();
  const signedIn = Boolean(account.user);
  useNotificationPolling(signedIn);
  const n = useNotifications();
  const pop = usePopover();
  const [tip, setTip] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const wasOpen = useRef(false);

  useEffect(() => {
    if (pop.open && !wasOpen.current) {
      setNow(Date.now());
      void openedPanel();
    }
    wasOpen.current = pop.open;
  }, [pop.open]);

  if (!signedIn) return null;
  const unread = n.unread > 0;
  const label = unread ? `Notifications, ${n.unread} new` : "Notifications";
  return (
    <>
      <button
        ref={pop.trigger}
        type="button"
        className="cf-rail-btn ac-bell"
        aria-label={label}
        aria-expanded={pop.open}
        aria-haspopup="dialog"
        onClick={() => { setTip(false); pop.setOpen((v) => !v); }}
        onPointerEnter={() => setTip(true)}
        onPointerLeave={() => setTip(false)}
        onFocus={() => setTip(true)}
        onBlur={() => setTip(false)}
      >
        <AcIcon name="bell" size={18} />
        {unread && <span className="cf-rail-badge" aria-hidden="true" />}
      </button>
      <Tip anchor={pop.trigger.current} open={tip && !pop.open} id="rail-tip-notifications" side="right">
        <span>{label}</span>
      </Tip>
      {pop.open && (
        <div ref={pop.panel} className="ac-pop ac-notes-pop" role="dialog" aria-label="Notifications" style={pop.style}>
          <div className="ac-pop-head">Notifications</div>
          <div className="ac-pop-body">
            <NotificationList now={now} onPick={() => pop.setOpen(false)} />
          </div>
        </div>
      )}
    </>
  );
}

/** #/notifications: the same list as a page (the bell lives in the rail, which phones hide). */
export function NotificationsPage({ phoneTools }: { phoneTools?: ReactNode }) {
  const signedIn = Boolean(useAccount().user);
  useNotificationPolling(signedIn);
  const [now] = useState(() => Date.now());
  useEffect(() => { void openedPanel(); }, []);
  return (
    <div className="ac-page">
      <PageHead title="Notifications" phoneTools={phoneTools} />
      <div className="ac-page-body is-narrow">
        <NotificationList now={now} />
      </div>
    </div>
  );
}


/** Phone header: a link to #/notifications with the unread dot (the rail and its popover are hidden there). */
export function NotificationsLink() {
  const signedIn = Boolean(useAccount().user);
  useNotificationPolling(signedIn);
  const n = useNotifications();
  if (!signedIn) return null;
  return (
    <a className="cf-icon-btn is-plain ac-bell-link" href="#/notifications" aria-label={n.unread ? `Notifications, ${n.unread} new` : "Notifications"}>
      <AcIcon name="bell" size={18} />
      {n.unread > 0 && <span className="cf-rail-badge" aria-hidden="true" />}
    </a>
  );
}
