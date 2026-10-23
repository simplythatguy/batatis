import type { ApplicationSummary } from "../../api/accounts";
import { noticeLine } from "../comments/thread";
import { Icon24 } from "../icons";
import "../comments/comments.css";

/**
 * One line at the top of the workflow when the officer has written: what happened, how many are
 * new, and a link to the comments page, where the full reasons and items live. Showing this line
 * reads nothing and marks nothing read; only the comments page does, once it shows them.
 */
export function NoticeLine({ app }: { app: ApplicationSummary }) {
  const line = noticeLine(app.status);
  if (!line) return null;
  const n = Math.max(0, app.unread_messages);
  const who = app.reviewer?.name?.trim();
  const label = `${line}${who ? ` by ${who}` : ""}${n ? `, ${n} new ${n === 1 ? "comment" : "comments"}` : ""}. Open comments`;
  return (
    <a className={`cf-notice-line${app.status === "refused" ? " is-closed" : ""}`} href="#/comments" aria-label={label}>
      <Icon24 name="msg" size={16} />
      <span className="cf-notice-text">{line}</span>
      {n > 0 && <span className="cf-notice-count" aria-hidden="true">{n}</span>}
      <span className="cf-notice-open" aria-hidden="true">Comments<Icon24 name="chevRight" size={14} /></span>
    </a>
  );
}

/** The officer returned or refused the application: the one-line notice. */
export function ReturnedBanner({ app }: { app: ApplicationSummary }) {
  return <NoticeLine app={app} />;
}
