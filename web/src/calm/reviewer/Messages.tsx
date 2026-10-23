/** The application's message thread (GET/POST /cases/{id}/messages). One way: only the officer writes. Bodies render as text, never HTML. */
import { useEffect, useId, useState, type Dispatch, type SetStateAction } from "react";
import { accounts, AccountsError, type Message } from "../../api/accounts";
import { Avatar } from "../auth/bits";
import { MOD_KEY } from "../ui";
import { clock, sentLabel } from "./queue";

function when(iso: string, now: number): string {
  const day = sentLabel(iso, now);
  return day.startsWith("Today") ? clock(iso) : `${day}, ${clock(iso)}`;
}

export function Messages({ caseId, me, messages, onChange, canWrite, hideTitle = false, draft: outerDraft, onDraft }: { caseId: string; me: string | null; messages: Message[] | null; onChange: Dispatch<SetStateAction<Message[] | null>>; canWrite: boolean; /** Inside a drawer that already says "Messages". */ hideTitle?: boolean; /** Held by the caller so closing a drawer keeps an unsent message. */ draft?: string; onDraft?: (d: string) => void }) {
  const id = useId();
  const [ownDraft, setOwnDraft] = useState("");
  const draft = outerDraft ?? ownDraft;
  const setDraft = onDraft ?? setOwnDraft;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [now] = useState(() => Date.now());

  useEffect(() => {
    if (messages?.some((m) => !m.read_by_me)) void accounts.markRead(caseId).catch(() => undefined);
  }, [caseId, messages]);

  async function send() {
    const body = draft.trim();
    if (!body || busy) return;
    setBusy(true);
    setError("");
    try {
      const m = await accounts.postMessage(caseId, body);
      onChange((prev) => [...(prev ?? []), m]);
      setDraft("");
    } catch (e) {
      setError(e instanceof AccountsError ? e.detail : "The message didn’t send. Try again.");
    } finally {
      setBusy(false);
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
                  <p className="ac-msg-body">{m.body}</p>
                  {/* An information request already lists its items in the body; show them once. */}
                  {m.items.length > 0 && !m.items.every((it) => it.note && m.body.includes(it.note.trim())) && (
                    <ul className="ac-msg-items">
                      {m.items.map((it, i) => <li key={i}>{it.note || it.field}</li>)}
                    </ul>
                  )}
                </>
              )}
            </li>
          ))}
        </ol>
      )}
      {canWrite && (
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
            {error ? <span className="ac-error is-row" role="alert">{error}</span> : <span className="ac-faint ac-small">One way · they can’t reply · {MOD_KEY} ↵</span>}
            <button type="button" className="cf-btn is-xs" disabled={!draft.trim() || busy} onClick={() => void send()}>{busy ? "Sending…" : "Send"}</button>
          </div>
        </div>
      )}
    </section>
  );
}
