/** The application's message thread (GET/POST /cases/{id}/messages). Bodies render as text, never HTML. */
import { useEffect, useId, useState } from "react";
import { accounts, AccountsError, type Message } from "../../api/accounts";
import { Avatar } from "../auth/bits";
import { clock, sentLabel } from "./queue";

function when(iso: string, now: number): string {
  const day = sentLabel(iso, now);
  return day.startsWith("Today") ? clock(iso) : `${day}, ${clock(iso)}`;
}

export function Messages({ caseId, me, messages, onChange, canWrite }: { caseId: string; me: string | null; messages: Message[] | null; onChange: (m: Message[]) => void; canWrite: boolean }) {
  const id = useId();
  const [draft, setDraft] = useState("");
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
      onChange([...(messages ?? []), m]);
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
      <h3 id={`${id}-h`} className="ac-side-h">Messages</h3>
      {messages == null ? (
        <p className="ac-faint ac-small">Loading messages…</p>
      ) : !thread.length ? (
        <p className="ac-faint ac-small">No messages yet. Returning the application sends your note to the applicant.</p>
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
                  {m.items.length > 0 && (
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
            {error ? <span className="ac-error is-row" role="alert">{error}</span> : <span className="ac-faint ac-small">⌘↵ to send</span>}
            <button type="button" className="cf-btn is-xs" disabled={!draft.trim() || busy} onClick={() => void send()}>{busy ? "Sending…" : "Send"}</button>
          </div>
        </div>
      )}
    </section>
  );
}
