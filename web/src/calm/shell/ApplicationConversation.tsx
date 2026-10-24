/**
 * The officer's side of one application, for the applicant (on the comments page): the current
 * decision in full (a return with its live correction rows, or a refusal with the officer's reasons
 * and appeal notice), any information request sent while the officer still has the file, then the
 * preserved messages and history. Messages are one way: the applicant answers a return by fixing and
 * resending, never by replying here.
 *
 * Only messages on screen in a visible tab are acknowledged, by id: a notice folded away or arriving
 * later stays unread. Reads and receipts belong to this application and sign-in and are aborted when
 * either changes or the page closes.
 */
import { useEffect, useId, useState } from "react";
import { accounts, type ApplicationSummary, type Conversation, type Message } from "../../api/accounts";
import { EngineError } from "../../api/client";
import type { SentInformationRequest } from "../../api/types.gen";
import { refreshApplications } from "../account";
import { authorityName } from "../applications";
import { openAssistant } from "../assistant/assistant";
import { unshownRequests } from "../comments/thread";
import { Icon24 } from "../icons";
import { requestedItemLabel, requestedMessageBody } from "../requestedItems";
import { CIcon } from "../ui";
import { useThreadRequests } from "../threadRequests";
import { messageWhen, ReturnDecision } from "./ReturnedBanner";

/** ISO instants can have different offsets. Stable ties retain the server's append order. */
export function chronologicalMessages(messages: Message[]): Message[] {
  return [...messages].sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at));
}

/** Whether this tab is on screen: a background tab acknowledges nothing. */
export function useVisible(): boolean {
  const [visible, setVisible] = useState(() => typeof document === "undefined" || document.visibilityState !== "hidden");
  useEffect(() => {
    const on = () => setVisible(document.visibilityState !== "hidden");
    document.addEventListener("visibilitychange", on);
    return () => document.removeEventListener("visibilitychange", on);
  }, []);
  return visible;
}

export function ApplicationConversation({ app, sent = [] }: { app: ApplicationSummary; sent?: readonly SentInformationRequest[] }) {
  const id = useId();
  const visible = useVisible();
  const { phase, user, startRequest, finishRequest } = useThreadRequests(app.id);
  // Everything shown belongs to this sign-in and this application; another one starts empty.
  const key = phase === "signed-in" && user ? `${user.id}:${app.id}` : null;
  const [loaded, setLoaded] = useState<{ key: string; conversation: Conversation } | null>(null);
  const [failed, setFailed] = useState<{ key: string; text: string } | null>(null);
  const [attempt, setAttempt] = useState(0);
  // A return leads with what to fix; the history waits one click away (with its unread count).
  const [open, setOpen] = useState<{ key: string; value: boolean } | null>(null);
  const conversation = loaded && loaded.key === key ? loaded.conversation : null;
  const error = failed && failed.key === key ? failed.text : "";
  const expanded = open && open.key === key ? open.value : app.status !== "returned";

  useEffect(() => {
    if (!key) return;
    const ctl = startRequest();
    setFailed(null);
    accounts.conversation(app.id, ctl.signal).then((snapshot) => {
      if (!ctl.signal.aborted) setLoaded({ key, conversation: { ...snapshot, messages: chronologicalMessages(snapshot.messages) } });
    }).catch((e: unknown) => {
      if (!ctl.signal.aborted) setFailed({ key, text: e instanceof EngineError ? e.detail : "The officer’s comments did not load." });
    }).finally(() => finishRequest(ctl));
    return () => { ctl.abort(); finishRequest(ctl); };
  // `user` too: signing in again as the same person is a new session (useThreadRequests aborted the old reads).
  }, [key, user, app.id, app.status, app.updated_at, app.unread_messages, attempt, startRequest, finishRequest]);

  const decision = (app.status === "returned" && conversation?.decision?.outcome === "return"
    || app.status === "refused" && conversation?.decision?.outcome === "refuse") ? conversation.decision : null;
  // Old decisions used a separately generated message timestamp. Match their immutable content,
  // never substitute the timestamp/body/items of the newest follow-up for the decision.
  const decisionMessage = decision ? conversation?.messages.slice().reverse().find((m) =>
    m.kind === "decision" && m.author.id === decision.by_id && m.body === decision.message) : undefined;
  // The current return/refusal is already shown in full above the history; earlier decisions stay in it.
  const history = conversation?.messages.filter((m) => m.id !== decisionMessage?.id) ?? [];
  const displayed = visible
    ? (expanded ? conversation?.messages ?? [] : decisionMessage ? [decisionMessage] : []).filter((m) => !m.read_by_me)
    : [];
  const receiptIds = displayed.map((m) => m.id).join(",");

  // Effects run after the displayed content commits. A concurrent, unseen notice is excluded.
  useEffect(() => {
    if (!receiptIds || !key) return;
    const ctl = startRequest();
    const ids = receiptIds.split(",");
    accounts.markRead(app.id, ids, ctl.signal).then(() => {
      if (ctl.signal.aborted) return;
      setLoaded((current) => current && current.key === key ? { key, conversation: { ...current.conversation, messages: current.conversation.messages.map((m) =>
        ids.includes(m.id) ? { ...m, read_by_me: true } : m) } } : current);
      // Obtain the real count: never clear a newer message with an unconditional zero patch.
      void refreshApplications();
    }).catch(() => undefined).finally(() => finishRequest(ctl));
    // A newer thread snapshot may already contain these read flags while this 204 is still in
    // flight. Let it finish and reconcile the list; useThreadRequests still aborts it on
    // case/account replacement or unmount, protecting the session cookie.
  }, [app.id, key, user, receiptIds, startRequest, finishRequest]);

  const unread = conversation?.messages.filter((m) => !m.read_by_me && m.kind !== "status" && m.author.role === "reviewer").length ?? app.unread_messages;
  const requests = conversation ? unshownRequests(sent, conversation.messages) : [];
  const retry = () => setAttempt((n) => n + 1);

  if (!key) return null;
  return (
    <div className="cf-correspondence">
      {decision?.outcome === "return" && <ReturnDecision app={app} decision={decision} messageId={decisionMessage?.id} />}
      {decision?.outcome === "refuse" && (
        <section className="cf-returned cf-refused" aria-labelledby={`${id}-refusal`}>
          <div className="cf-returned-body">
            <h2 id={`${id}-refusal`} className="cf-returned-who">Refused by {authorityName(app.authority) || "the reviewing authority"}</h2>
            <p className="cf-faint cf-small">{decision.by_name} · <time dateTime={decision.at}>{messageWhen(decision.at)}</time></p>
            <p className="cf-returned-msg">{decision.message}</p>
            <p className="cf-faint cf-small">This application is closed and read-only. Later notices stay in Messages and history.</p>
            <div className="cf-returned-acts">
              <button
                type="button"
                className="cf-btn is-ghost is-sm"
                onClick={() => openAssistant({ screen: "message", focus: decisionMessage ? { kind: "message", id: decisionMessage.id } : undefined, label: "the officer’s refusal", suggestions: ["Explain this refusal", "Explain the appeal notice"] }, "Explain the officer’s refusal and appeal notice in plain words.")}
              >
                <Icon24 name="spark" size={15} />Explain
              </button>
            </div>
          </div>
        </section>
      )}

      {requests.length > 0 && (
        <section className="cf-comment-group" aria-label="Information requested">
          {[...requests].reverse().map((r) => (
            <div key={r.sent_at} className="cf-comment">
              <p className="cf-comment-meta">{r.sent_by_name || app.reviewer?.name || "The officer"} · {messageWhen(r.sent_at)}</p>
              <p className="cf-comment-body">{r.intro}</p>
              <ol className="cf-comment-plain">{r.items.map((t, i) => <li key={i}>{t}</li>)}</ol>
              <p className="cf-faint cf-small">Comes back to you to update</p>
            </div>
          ))}
        </section>
      )}

      <section className="cf-conversation" aria-labelledby={`${id}-heading`}>
        <h2 id={`${id}-heading`} className="cf-sr">Messages and application history</h2>
        <details open={expanded} onToggle={(e) => { if (key) setOpen({ key, value: e.currentTarget.open }); }}>
          <summary className="cf-comment-earlier-h">Messages and history{unread > 0 ? ` · ${unread} unread` : ""}</summary>
          <button type="button" className="cf-btn is-ghost is-xs" onClick={retry}><CIcon name="retry" size={13} />Refresh messages</button>
          {error && <p className="cf-small" role="status">{error} <button type="button" className="cf-btn is-xs" onClick={retry}>Try again</button></p>}
          {!conversation && !error && <p className="cf-faint cf-small" role="status">Loading messages…</p>}
          {conversation && !conversation.messages.length && <p className="cf-faint cf-small">No messages yet</p>}
          {conversation && <ol className="ac-thread">
            {history.map((m) => <li key={m.id} className={`ac-msg is-${m.kind}`}>
              <div className="ac-msg-head">
                {!m.read_by_me && m.kind !== "status" && m.author.role === "reviewer" && <span className="cf-comment-new" aria-label="New" />}
                <span className="ac-msg-who">{m.author.name || (m.author.role === "reviewer" ? "Officer" : "Applicant")}</span>
                <span className="cf-faint">{m.kind === "decision" ? "Decision · " : m.author.role === "reviewer" ? "Officer · " : ""}<time dateTime={m.created_at}>{messageWhen(m.created_at)}</time></span>
              </div>
              <p className="ac-msg-body">{requestedMessageBody(m.body, m.items)}</p>
              {m.items.length > 0 && <ul className="ac-msg-items">{m.items.map((item, n) => <li key={`${item.gap_id ?? ""}:${item.field ?? ""}:${n}`}>{requestedItemLabel(item)}</li>)}</ul>}
            </li>)}
          </ol>}
        </details>
        {error && !expanded && <p className="cf-faint cf-small" role="status">{error} <button type="button" className="cf-btn is-xs" onClick={retry}>Try again</button></p>}
      </section>
    </div>
  );
}
