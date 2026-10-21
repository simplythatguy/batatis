import { useEffect, useRef, useState } from "react";
import { codeHref } from "../routes";
import { articleOf } from "../useRelevance";
import { Icon24 } from "../icons";
import { MOD_KEY } from "../ui";
import { useAccount } from "../account";
import { answerBlocks, ask, closeAssistant, useAssistant } from "./assistant";

const DISCLAIMER = "Plain-language explanation, not code text. It doesn’t say whether your design complies or is safe.";

/** Right-hand assistant column. It sits beside the main column and pushes it; it never covers it. */
export function AssistantPanel() {
  const a = useAssistant();
  const account = useAccount();
  // The engine answers signed-in users only; anonymous visits never call it.
  const signedOut = account.phase !== "signed-in" && account.phase !== "probing";
  const [draft, setDraft] = useState("");
  const body = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!a.error?.retryAt) return;
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, [a.error?.retryAt]);
  useEffect(() => { input.current?.focus(); }, []);
  useEffect(() => { body.current?.scrollTo({ top: body.current.scrollHeight }); }, [a.turns.length, a.pending]);
  const wait = a.error?.retryAt ? Math.max(0, Math.ceil((a.error.retryAt - now) / 1000)) : 0;
  const unavailable = a.error && (a.error.status === 503 || a.error.status === 404 || a.error.status === 0);
  const send = (q: string) => {
    if (!q.trim() || a.pending || wait > 0 || signedOut) return;
    setDraft("");
    void ask(q);
  };
  return (
    <aside className="cf-assist" aria-label="Assistant" onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); closeAssistant(); } }}>
      <div className="cf-assist-head">
        <span className="cf-assist-title"><Icon24 name="spark" size={16} />Assistant</span>
        <button type="button" className="cf-icon-btn is-plain" aria-label={`Close the assistant (${MOD_KEY} J)`} onClick={closeAssistant}>
          <Icon24 name="x" size={16} />
        </button>
      </div>
      <div ref={body} className="cf-assist-body" aria-live="polite">
        <p className="cf-assist-ctx">Looking at <b>{a.context.label}</b></p>
        {signedOut && account.phase === "anonymous" && (
          <div className="cf-assist-error" role="status">
            <p>The assistant isn’t available on this server.</p>
            <p className="cf-fine">You can still read the code yourself in the code library.</p>
          </div>
        )}
        {signedOut && account.phase === "signed-out" && (
          <div className="cf-assist-error" role="status">
            <p><a className="cf-inline-link" href="#/signin">Sign in</a> to use the assistant.</p>
            <p className="cf-fine">It explains questions, code references and officer messages for your own applications. You can still read the code yourself in the code library.</p>
          </div>
        )}
        {!signedOut && a.turns.length === 0 && !a.error && (
          <p className="cf-assist-intro">Ask about this question, a code reference, a message from the officer, or what to do next. Answers explain; they never decide whether your design complies.</p>
        )}
        {a.turns.map((t, n) =>
          t.role === "user" ? (
            <div key={n} className="cf-msg-user">{t.text}</div>
          ) : (
            <div key={n} className="cf-msg-ai">
              {answerBlocks(t.text).map((b, i) => (b.kind === "quote" ? <blockquote key={i} className="cf-code-text is-inline">{b.text}</blockquote> : <p key={i}>{b.text}</p>))}
              {t.cited && t.cited.length > 0 && (
                <div className="cf-chip-row">
                  {t.cited.map((id) => <a key={id} className="cf-code-chip is-link" href={codeHref(articleOf(id) ?? id)}>{id}</a>)}
                </div>
              )}
              {t.removed && t.removed.length > 0 && <p className="cf-fine">{t.removed.length === 1 ? "One reference" : `${t.removed.length} references`} could not be checked against the code and {t.removed.length === 1 ? "was" : "were"} left out.</p>}
              <p className="cf-fine">{t.notice || DISCLAIMER}</p>
            </div>
          ),
        )}
        {a.pending && <p className="cf-assist-pending" role="status"><span className="cf-dot is-pending cf-pulse" aria-hidden="true" />Thinking…</p>}
        {a.error && (
          <div className="cf-assist-error" role="status">
            <p>{a.error.text}{wait > 0 ? ` Try again in ${wait} s.` : ""}</p>
            {unavailable && <p className="cf-fine">Nothing is made up instead. You can still read the code yourself in the code library.</p>}
            <details className="cf-tech"><summary>Technical detail</summary><p>{a.error.technical}</p></details>
          </div>
        )}
      </div>
      <form className="cf-composer-box" onSubmit={(e) => { e.preventDefault(); send(draft); }}>
        <label className="cf-sr" htmlFor="cf-assist-input">Ask the assistant</label>
        <textarea
          id="cf-assist-input"
          ref={input}
          rows={2}
          disabled={signedOut}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(draft); } }}
          placeholder="Ask about this question, a code, or your application…"
        />
        <div className="cf-composer-box-foot">
          <div className="cf-chips">
            {(a.context.suggestions ?? []).slice(0, 2).map((s) => (
              <button key={s} type="button" className="cf-suggest" disabled={a.pending || wait > 0 || signedOut} onClick={() => send(s)}>{s}</button>
            ))}
          </div>
          <button type="submit" className="cf-icon-btn is-plain" aria-label="Send" disabled={!draft.trim() || a.pending || wait > 0 || signedOut}>
            <Icon24 name="send" size={16} />
          </button>
        </div>
      </form>
    </aside>
  );
}
