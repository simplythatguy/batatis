import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";
import { codeHref } from "../routes";
import { articleOf } from "../useRelevance";
import { Icon24 } from "../icons";
import { MOD_KEY } from "../ui";
import { useAccount } from "../account";
import {
  answerBlocks, answerSpans, ask, assistantKey, cancelQuestion, closeAssistant, goBack, MAX_QUESTION, retry, setDraft, useAssistant,
  type Turn,
} from "./assistant";
import { AttachButton, Attachments } from "./Attachments";
import { ChatFollow, savedPosition, savePosition } from "./follow";
import { ToolButton } from "./ToolButton";
import "./assistant.css";

const DISCLAIMER = "Plain-language explanation, not code text. It doesn’t say whether your design complies or is safe.";

/** Right-hand assistant column. It sits beside the main column and pushes it; it never covers it. */
export function AssistantPanel() {
  const a = useAssistant();
  const account = useAccount();
  // The engine answers signed-in users only; anonymous visits never call it.
  const signedOut = account.phase !== "signed-in" && account.phase !== "probing";
  const c = a.conv;
  const body = useRef<HTMLDivElement>(null);
  const transcript = useRef<HTMLDivElement>(null);
  const follow = useRef<ChatFollow | null>(null);
  const conversationKey = assistantKey();
  const [following, setFollowing] = useState(true);
  const initialTurns = useRef({ key: conversationKey, ids: new Set(c.turns.map((t) => t.id)) });
  if (initialTurns.current.key !== conversationKey) initialTurns.current = { key: conversationKey, ids: new Set(c.turns.map((t) => t.id)) };
  const input = useRef<HTMLTextAreaElement>(null);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!c.error?.retryAt) return;
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, [c.error?.retryAt]);
  // No scroll on focus: the panel is still sliding in from beyond the edge, and scrolling to it shifts the page.
  useEffect(() => { input.current?.focus({ preventScroll: true }); }, []);
  useLayoutEffect(() => {
    const node = body.current;
    if (!node) return;
    const controller = new ChatFollow(node, {
      raf: (fn) => requestAnimationFrame(fn), caf: (id) => cancelAnimationFrame(id), now: Date.now,
      reduced: () => matchMedia("(prefers-reduced-motion: reduce)").matches,
      onWindow: (type, fn) => { window.addEventListener(type, fn); return () => window.removeEventListener(type, fn); },
    }, (pinned) => { setFollowing(pinned); savePosition(conversationKey, controller.position()); });
    follow.current = controller;
    controller.restore(savedPosition(conversationKey));
    const detach = controller.attach();
    const observer = new ResizeObserver(() => controller.grew());
    if (transcript.current) observer.observe(transcript.current);
    observer.observe(node);
    return () => {
      // Positions are captured as scrolling happens, before another application's DOM arrives.
      observer.disconnect(); detach(); follow.current = null;
    };
  }, [conversationKey]);
  useLayoutEffect(() => { follow.current?.grew(); }, [c.turns, c.pending, c.error]);
  const wait = c.error?.retryAt ? Math.max(0, Math.ceil((c.error.retryAt - now) / 1000)) : 0;
  const busy = c.pending || c.attachments.some((f) => f.status === "uploading") || wait > 0 || signedOut;
  const send = (q: string) => {
    if (!q.trim() || busy) return;
    void ask(q);
  };
  const onKey = (e: ReactKeyboardEvent) => {
    if (e.key !== "Escape") return;
    e.stopPropagation();
    closeAssistant();
  };
  return (
    <aside className="cf-assist" aria-label="Assistant" onKeyDown={onKey}>
      <div className="cf-assist-head">
        <span className="cf-assist-title"><Icon24 name="spark" size={16} />Assistant</span>
        <ToolButton type="button" className="cf-icon-btn is-plain" aria-label={`Close the assistant (${MOD_KEY} J)`} title="Close assistant" onClick={closeAssistant}>
          <Icon24 name="x" size={16} />
        </ToolButton>
      </div>
      <div className="cf-av-scroll">
      <div ref={body} className="cf-assist-body" role="log" tabIndex={0} aria-label="Conversation" aria-live="polite">
      <div ref={transcript} className="cf-assist-transcript">
        {signedOut && account.phase === "anonymous" && (
          <div className="cf-assist-error" role="status">
            <p>The assistant isn’t available on this server.</p>
            <p className="cf-fine">You can still read the code yourself in the code library.</p>
          </div>
        )}
        {signedOut && account.phase === "signed-out" && (
          <div className="cf-assist-error" role="status">
            <p><a className="cf-inline-link" href="#/signin">Sign in</a> to use the assistant.</p>
          </div>
        )}
        {!signedOut && c.turns.length === 0 && !c.error && c.attachments.some((f) => f.status === "ready") && (
          <p className="cf-assist-intro">Only limited text is available from the selected PDFs; scans aren’t read.</p>
        )}
        {c.turns.map((t) => <div key={t.id} className="cf-av-turn" data-enter={!initialTurns.current.ids.has(t.id) || undefined}><TurnView t={t} /></div>)}
        {c.pending && (
          <div className="cf-av-pending" role="status">
            <span className="cf-av-shimmer">Thinking…</span>
            <button type="button" className="cf-btn is-xs is-ghost" onClick={cancelQuestion}>Stop</button>
          </div>
        )}
        {c.error && (
          <div className="cf-assist-error" role="status">
            <p>{c.error.text}{wait > 0 ? ` Try again in ${wait} s.` : ""}</p>
            {c.failed && <button type="button" className="cf-btn is-xs" disabled={busy} onClick={retry}>Retry</button>}
          </div>
        )}
      </div>
      </div>
      {!following && <button type="button" className="cf-btn is-xs cf-av-latest" onClick={() => follow.current?.toEnd(false, true)}>Latest message <Icon24 name="down" size={13} /></button>}
      </div>
      <form className="cf-composer-box" onSubmit={(e) => { e.preventDefault(); send(c.draft); }}>
        <Attachments a={a} />
        <label className="cf-sr" htmlFor="cf-assist-input">Ask the assistant</label>
        <textarea
          id="cf-assist-input"
          ref={input}
          rows={2}
          maxLength={MAX_QUESTION}
          disabled={signedOut}
          value={c.draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(c.draft); } }}
          placeholder="Ask about this question, a code, or your application…"
        />
        <div className="cf-composer-box-foot">
          <div className="cf-chips">
            {c.turns.length === 0 && (a.context.suggestions ?? []).slice(0, 2).map((s) => (
              <button key={s} type="button" className="cf-suggest" disabled={busy} onClick={() => send(s)}>{s}</button>
            ))}
          </div>
          <div className="cf-av-tools">
            {!signedOut && <AttachButton a={a} />}
            <ToolButton type="submit" className="cf-icon-btn is-plain" aria-label="Send" disabled={!c.draft.trim() || busy}>
              <Icon24 name="send" size={16} />
            </ToolButton>
          </div>
        </div>
      </form>
    </aside>
  );
}

const NAV_TEXT: Record<NonNullable<Turn["nav"]>["state"], (label: string) => string> = {
  opening: (l) => `Opening ${l}…`,
  opened: (l) => `Opened ${l}`,
  failed: (l) => `Couldn’t open ${l}`,
  "moved-on": (l) => `Not opened · you moved on (${l})`,
  "not-offered": (l) => `${l} isn’t available here`,
};

/** Plain text with bold runs. React escapes every span; no HTML from the answer is ever parsed. */
function Spans({ text }: { text: string }) {
  return <>{answerSpans(text).map((s, i) => (s.bold ? <strong key={i}>{s.text}</strong> : s.text))}</>;
}

function TurnView({ t }: { t: Turn }) {
  if (t.nav) {
    const n = t.nav;
    const ok = n.state === "opened";
    return (
      <div className={`cf-av-nav${ok ? "" : " is-quiet"}`} role="status">
        <Icon24 name={ok ? "right" : n.state === "opening" ? "clock" : "x"} size={14} />
        <span>{NAV_TEXT[n.state](n.label)}</span>
        {ok && n.back && (
          n.backState === "returned" ? <span className="cf-av-nav-note">Back at {n.back.label}</span>
            : <button type="button" className="cf-btn is-xs is-ghost" disabled={n.backState === "returning"} onClick={() => void goBack(t.id)}>
                {n.backState === "failed" ? "Try going back again" : `Back to ${n.back.label}`}
              </button>
        )}
      </div>
    );
  }
  if (t.role === "user") {
    return (
      <div className={`cf-msg-user${t.unanswered ? " is-unanswered" : ""}`}>
        {t.text}
        {t.unanswered && <span className="cf-sr"> (not answered)</span>}
      </div>
    );
  }
  return (
    <div className="cf-msg-ai">
      {answerBlocks(t.text).map((b, i) => (b.kind === "quote" ? <blockquote key={i} className="cf-code-text is-inline">{b.text}</blockquote>
        : b.kind === "list" ? <ul key={i}>{b.items.map((item, j) => <li key={j}><Spans text={item} /></li>)}</ul>
        : <p key={i}><Spans text={b.text} /></p>))}
      {t.cited && t.cited.length > 0 && (
        <div className="cf-chip-row">
          {t.cited.map((id) => <a key={id} className="cf-code-chip is-link" href={codeHref(articleOf(id) ?? id)}>{id}</a>)}
        </div>
      )}
      {t.removed && t.removed.length > 0 && <p className="cf-fine">{t.removed.length === 1 ? "One reference" : `${t.removed.length} references`} couldn’t be checked against the code and {t.removed.length === 1 ? "was" : "were"} left out.</p>}
      {t.documents && <DocumentSources documents={t.documents} />}
      {/* The notice is one step away on every answer (never repeated as a paragraph). */}
      <details className="cf-av-about">
        <summary aria-label="About this answer" title="About this answer">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden="true"><circle cx="8" cy="8" r="6.25" /><path d="M8 7.2v3.8M8 5.1v.1" strokeLinecap="round" /></svg>
        </summary>
        <p className="cf-fine">{t.notice || DISCLAIMER}</p>
      </details>
    </div>
  );
}

function DocumentSources({ documents: { attachments, references } }: { documents: NonNullable<Turn["documents"]> }) {
  return (
    <details className="cf-av-sources">
      <summary>PDF sources <span className="cf-fine">· {references.length ? `${new Set(references.map((r) => r.file_id)).size} referenced` : "no excerpt found"}</span></summary>
      <ul>
        {attachments.map((a) => {
          const used = references.filter((r) => r.file_id === a.file_id);
          return <li key={a.file_id}>
            <b>{a.name}</b>
            <p className="cf-fine" title={a.reason ?? undefined}>{a.content_state === "not_read" ? "Not read" : `Text excerpts · ${a.pages.length === 1 ? "page" : "pages"} ${a.pages.join(", ")}`}{a.truncated ? " · truncated" : ""}{a.content_state === "text_excerpt" && !used.length ? " · not referenced in this answer" : ""}</p>
            {used.map((r, i) => <p className="cf-fine" key={i} title={r.quote}>Referenced: page {r.page}</p>)}
          </li>;
        })}
      </ul>
    </details>
  );
}
