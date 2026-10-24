import type { ApplicationSummary } from "../../api/accounts";
import type { Decision } from "../../api/types.gen";
import { useCase } from "../../store";
import { initials } from "../account";
import { authorityName } from "../applications";
import { openAssistant } from "../assistant/assistant";
import { noticeLine } from "../comments/thread";
import { Icon24 } from "../icons";
import { requestedItemRow, requestedMessageBody } from "../requestedItems";
import "../comments/comments.css";

export const messageWhen = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
};

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

/**
 * The current return decision in full, on the comments page. Each requested item shows its live
 * state from the shared gaps and acknowledged facts; a factual edit never claims the officer's
 * confirmation. Follow-up notices stay in the history below it.
 */
export function ReturnDecision({ app, decision, messageId }: { app: ApplicationSummary; decision: Decision; messageId?: string }) {
  const { c, gaps, saveStatus, gapsSource, checkStatus } = useCase();
  const checked = gapsSource === "engine" && (checkStatus === "ready" || checkStatus === "needs_answers");
  const rows = decision.items.map((it) => requestedItemRow(c, gaps, it, saveStatus === "saved", checked));
  const next = rows.find((row) => row.state === "open");
  const pending = rows.filter((row) => row.state === "pending").length;
  const body = requestedMessageBody(decision.message, decision.items);
  const who = decision.by_name || app.reviewer?.name || "The officer";
  const where = authorityName(app.authority);

  return (
    <section className="cf-returned" aria-labelledby="cf-returned-who">
      <span className="cf-returned-av" aria-hidden="true">{initials(who) || "?"}</span>
      <div className="cf-returned-body">
        <h2 className="cf-returned-who" id="cf-returned-who">
          {who} <span>· {where ? `Safety Codes Officer, ${where} · ` : ""}returned this <time dateTime={decision.at}>{messageWhen(decision.at)}</time></span>
        </h2>
        {body && <p className="cf-returned-msg">{body}</p>}
        {rows.length > 0 && (
          <ul className="cf-returned-items">
            {rows.map((r, index) => (
              <li key={`${decision.items[index].gap_id ?? ""}:${decision.items[index].field ?? ""}:${index}`}>
                <a href={r.href}>
                  <span className={`cf-dot is-${r.tone}`} aria-hidden="true" />
                  <span className="cf-returned-item-text"><span>{r.label}</span><span className="cf-returned-item-state">{r.status}</span></span>
                  <Icon24 name="right" size={14} />
                </a>
              </li>
            ))}
          </ul>
        )}
        <p className="cf-faint cf-small cf-returned-next">
          {pending > 0 ? `${pending} ${pending === 1 ? "item awaits" : "items await"} officer confirmation. ` : ""}
          {rows.length ? "Review your corrections, then choose Resubmit on Application. Only the officer can confirm the requested items." : "Follow the officer’s note. Review your corrections, then choose Resubmit on Application."}
        </p>
        <div className="cf-returned-acts">
          <a className="cf-btn is-primary is-sm" href={next?.href ?? "#/application"}>{next ? "Address next item" : "Review corrections"}</a>
          <button
            type="button"
            className="cf-btn is-ghost is-sm"
            onClick={() => openAssistant({ screen: "message", focus: messageId ? { kind: "message", id: messageId } : undefined, label: "the return decision", suggestions: ["What do I need to change?", "Explain this message"] }, "Explain the officer’s return decision in plain words. What do I need to change?")}
          >
            <Icon24 name="spark" size={15} />Explain this message
          </button>
        </div>
      </div>
    </section>
  );
}
