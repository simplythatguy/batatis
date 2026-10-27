/** The application's message thread (GET/POST /cases/{id}/messages). One way: only the officer writes. Bodies render as text, never HTML. */
import { useEffect, useId, useRef, useState, type Dispatch, type SetStateAction } from "react";
import { accounts, AccountsError, type Message } from "../../api/accounts";
import { Avatar } from "../auth/bits";
import { useThreadRequests } from "../threadRequests";
import { requestedItemLabel, requestedMessageBody } from "../requestedItems";
import { MOD_KEY } from "../ui";
import { clock, sentLabel } from "./queue";
import { mergeThreadMessages } from "./threadMessages";

function when(iso: string, now: number): string {
  const day = sentLabel(iso, now);
  return day.startsWith("Today") ? clock(iso) : `${day}, ${clock(iso)}`;
}

export function Messages({ caseId, me, messages, onChange, canWrite, hideTitle = false, draft: outerDraft, onDraft, reading = true }: { caseId: string; me: string | null; messages: Message[] | null; onChange: Dispatch<SetStateAction<Message[] | null>>; canWrite: boolean; /** Inside a drawer that already says "Messages". */ hideTitle?: boolean; /** Held by the caller so closing a drawer keeps an unsent message. */ draft?: string; onDraft?: (d: string) => void; /** Shown to the reader now: only then are its unread messages acknowledged. */ reading?: boolean }) {
  const id = useId();
  const { phase, user, startRequest, finishRequest } = useThreadRequests(caseId);
  const [ownDraft, setOwnDraft] = useState("");
  const draft = outerDraft ?? ownDraft;
  const setDraft = onDraft ?? setOwnDraft;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [now] = useState(() => Date.now());
  const mayWrite = canWrite && phase === "signed-in" && user?.id === me && user.role === "reviewer";

  // Another case or sign-in never inherits an unsent message. Reopening the drawer (a remount) keeps
  // the caller's draft, so only an actual change clears it.
  const scope = useRef({ caseId, me, phase, user });
  useEffect(() => {
    const shown = scope.current;
    if (shown.caseId === caseId && shown.me === me && shown.phase === phase && shown.user === user) return;
    scope.current = { caseId, me, phase, user };
    setDraft("");
    setBusy(false);
    setError("");
  }, [caseId, me, phase, user, setDraft]);

  useEffect(() => {
    if (!reading || phase !== "signed-in" || user?.id !== me) return;
    const displayed = messages?.filter((m) => !m.read_by_me).map((m) => m.id) ?? [];
    if (!displayed.length) return;
    const ctl = startRequest();
    void accounts.markRead(caseId, displayed, ctl.signal).then(() => {
      if (ctl.signal.aborted) return;
      const read = new Set(displayed);
      onChange(previous => ctl.signal.aborted ? previous : previous && previous.map(message => read.has(message.id)
        ? { ...message, read_by_me: true } : message));
    }).catch(() => undefined).finally(() => finishRequest(ctl));
    return () => { ctl.abort(); finishRequest(ctl); };
  }, [caseId, messages, me, phase, user, startRequest, finishRequest, onChange, reading]);

  async function send() {
    const body = draft.trim();
    if (!body || busy || !mayWrite) return;
    const ctl = startRequest();
    setBusy(true);
    setError("");
    try {
      const m = await accounts.postMessage(caseId, body, ctl.signal);
      if (ctl.signal.aborted) return;
      onChange(prev => ctl.signal.aborted ? prev : mergeThreadMessages(prev, [...(prev ?? []), m]));
      setDraft("");
    } catch (e) {
      if (ctl.signal.aborted) return;
      setError(e instanceof AccountsError ? e.detail : "The message didn’t send. Try again.");
    } finally {
      finishRequest(ctl);
      if (!ctl.signal.aborted) setBusy(false);
    }
  }

  const thread = (messages ?? []).filter((m) => m.kind !== "status" || m.body.trim());
  return (
    <section className="ac-side-sec" aria-labelledby={`${id}-h`}>
      <h3 id={`${id}-h`} className={hideTitle ? "cf-sr" : "ac-side-h"}>Messages</h3>
      {messages == null ? (
        <p className="ac-faint ac-small">Loading messages…</p>
      ) : !thread.length ? (
        <p className="ac-faint ac-small">No messages yet</p>
      ) : (
        <ol className="ac-thread">
          {thread.map((m) => (
            <li key={m.id} className={`ac-msg is-${m.kind}${m.author.id === me ? " is-mine" : ""}`}>
              {m.kind === "status" ? (
                <p className="ac-msg-status"><span>{m.author.name}</span> · {m.body} <span className="ac-faint">{when(m.created_at, now)}</span></p>
              ) : (
                <>
                  <div className="ac-msg-head">
                    <Avatar name={m.author.name} size="sm" />
                    <span className="ac-msg-who">{m.author.id === me ? "You" : m.author.name}</span>
                    <span className="ac-faint">{when(m.created_at, now)}</span>
                    {!m.read_by_me && m.author.id !== me && <span className="ac-note-dot" aria-label="New" />}
                  </div>
                  <p className="ac-msg-body">{requestedMessageBody(m.body, m.items)}</p>
                  {m.items.length > 0 && (
                    <ul className="ac-msg-items">
                      {m.items.map((it, i) => <li key={`${it.gap_id ?? ""}:${it.field ?? ""}:${i}`}>{requestedItemLabel(it)}</li>)}
                    </ul>
                  )}
                </>
              )}
            </li>
          ))}
        </ol>
      )}
      {mayWrite && (
        <div className="ac-composer">
          <label htmlFor={`${id}-in`} className="cf-sr">Message to the applicant</label>
          <textarea
            id={`${id}-in`}
            className="ac-composer-in"
            rows={2}
            placeholder="Write to the applicant…"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); void send(); } }}
            maxLength={4000}
          />
          <div className="ac-composer-foot">
            {error ? <span className="ac-error is-row" role="alert">{error}</span> : <span className="ac-faint ac-small">They can’t reply · {MOD_KEY} ↵</span>}
            <button type="button" className="cf-btn is-xs" disabled={!draft.trim() || busy} onClick={() => void send()}>{busy ? "Sending…" : "Send"}</button>
          </div>
        </div>
      )}
    </section>
  );
}
