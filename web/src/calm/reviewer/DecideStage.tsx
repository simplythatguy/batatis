/**
 * Decide: the request exactly as the applicant will receive it (the server's text from the last save),
 * the officer's own items, and the decision for the version on screen. One primary action: Return when
 * something is asked, Accept when the server's gate allows it. After a decision: the outcome.
 */
import { useEffect, useId, useState, type ReactNode } from "react";
import type { RequestLimits, RequestTarget, ReviewDiff, ReviewSession, Workspace } from "../../api/types.gen";
import type { ReviewQuestion } from "../../api/client";
import { AcIcon } from "../auth/bits";
import { Icon24 } from "../icons";
import { clock, sentPhrase } from "./queue";
import { officerItem } from "./requestDraft";
import { TargetSelect } from "./TargetSelect";
import type { useRequestDraft } from "./useRequestDraft";
import { clarificationSuggestions } from "./workspaceView";

type Draft = ReturnType<typeof useRequestDraft>;

export interface Choices {
  canReturn: boolean;
  canAccept: boolean;
  canRefuse: boolean;
  /** Why the main action is off, in a few words. */
  why: string;
  busy: boolean;
  onReturn: () => void;
  onAccept: () => void;
  onRefuse: () => void;
}

const plural = (n: number, one: string) => `${n} ${n === 1 ? one : `${one}s`}`;

function Since({ diff }: { diff: ReviewDiff }) {
  const parts: [number, string, string][] = [
    [diff.resolved.length, "fixed", "done"],
    [diff.still_open.length, "still open", "warning"],
    [diff.new.length, "new", "blocking"],
    [diff.unverified?.length ?? 0, "can’t tell", "pending"],
  ];
  return (
    <p className="rw-since" aria-label={`Since version ${diff.previous_version}`}>
      <span className="rw-since-v">Since v{diff.previous_version}</span>
      {parts.filter(([n]) => n).map(([n, label, tone]) => <span key={label}><span className={`cf-dot is-${tone}`} aria-hidden="true" />{n} {label}</span>)}
    </p>
  );
}

function SaveState({ draft }: { draft: Draft }) {
  const s = draft.state.save;
  if (s.kind === "error") {
    return <span className="rw-save is-error" role="alert">{s.message} <button type="button" className="cf-link-btn" onClick={() => draft.dispatch({ type: "retry" })}>Retry</button></span>;
  }
  if (draft.problem && s.kind !== "saved") return <span className="rw-save is-error" role="status">{draft.problem}</span>;
  return <span className="rw-save" role="status">{s.kind === "saved" ? (draft.state.savedAt ? `Saved ${clock(draft.state.savedAt)}` : "Saved") : "Saving…"}</span>;
}

function OwnItems({ draft, limits, targets, questions }: { draft: Draft; limits: RequestLimits; targets: RequestTarget[]; questions: ReviewQuestion[] }) {
  const id = useId();
  const [opening, setOpening] = useState(false);
  const [adding, setAdding] = useState(false);
  const [text, setText] = useState("");
  const [target, setTarget] = useState<RequestTarget | null>(null);
  const items = draft.state.content.items.filter((i) => !i.finding_key);
  const full = draft.state.content.items.length >= limits.items;
  const suggestions = clarificationSuggestions(questions, draft.state.content.items);
  const add = (t: string, where: RequestTarget) => {
    draft.dispatch({ type: "add", item: officerItem(t.trim(), where) });
    setAdding(false); setText(""); setTarget(null);
  };
  return (
    <div className="rw-own">
      {items.map((item) => (
        <div key={item.key} className="rw-own-item">
          <label htmlFor={`${id}-${item.key}`} className="cf-sr">Your item</label>
          <textarea id={`${id}-${item.key}`} className="cf-uline is-area" rows={1} maxLength={limits.item_text} value={item.text}
            onChange={(e) => draft.dispatch({ type: "item", key: item.key, patch: { text: e.target.value } })} />
          <div className="rw-own-row">
            <TargetSelect options={targets} value={item.target} onChange={(t) => draft.dispatch({ type: "item", key: item.key, patch: { target: t } })} />
            <button type="button" className="cf-icon-btn" aria-label="Remove this item" title="Remove" onClick={() => draft.dispatch({ type: "remove", key: item.key })}>
              <Icon24 name="trash" size={16} />
            </button>
          </div>
        </div>
      ))}
      {adding && (
        <div className="rw-own-item">
          <label htmlFor={`${id}-new`} className="cf-sr">New item</label>
          <textarea id={`${id}-new`} className="cf-uline is-area" rows={1} maxLength={limits.item_text} value={text} autoFocus placeholder="Please provide…" onChange={(e) => setText(e.target.value)} />
          <div className="rw-own-row">
            <TargetSelect options={targets} value={target} onChange={setTarget} />
            <button type="button" className="cf-btn" disabled={!text.trim() || !target} title={!target ? "Choose where they answer" : undefined} onClick={() => target && add(text, target)}>Add</button>
            <button type="button" className="cf-link-btn" onClick={() => { setAdding(false); setText(""); setTarget(null); }}>Cancel</button>
          </div>
        </div>
      )}
      {opening && (
        <div className="rw-own-item">
          <label htmlFor={`${id}-o`} className="cf-sr">Opening line</label>
          <textarea id={`${id}-o`} className="cf-uline is-area" rows={2} maxLength={limits.intro} value={draft.state.content.intro}
            onChange={(e) => draft.dispatch({ type: "intro", value: e.target.value })} />
        </div>
      )}
      <div className="rw-links">
        {!adding && <button type="button" className="cf-link-btn" disabled={full} title={full ? `At most ${limits.items} items` : undefined} onClick={() => setAdding(true)}><Icon24 name="compose" size={15} />Add item</button>}
        <button type="button" className="cf-link-btn" aria-expanded={opening} onClick={() => setOpening(!opening)}>{opening ? "Done" : "Opening line"}</button>
        {suggestions.length > 0 && (
          <details className="rw-fold">
            <summary className="cf-link-btn">Applicant questions · {suggestions.length}</summary>
            <ul className="rw-suggest">
              {suggestions.map((s) => (
                <li key={s.target.field}>
                  <span>{s.target.label.replace(/^Applicant question · /, "")}</span>
                  <button type="button" className="cf-btn is-sm" disabled={full} onClick={() => add(s.text.slice(0, limits.item_text), s.target)}>Ask</button>
                </li>
              ))}
            </ul>
          </details>
        )}
        <SaveState draft={draft} />
      </div>
    </div>
  );
}

export function DecideStage({ session, workspace, applicant, status, decidedAt, draft, editable, targets, questions, choices, outcome, messages, unread, messagesAsk }: {
  session: ReviewSession;
  workspace: Workspace | null;
  applicant: string;
  status: string;
  decidedAt: string | null;
  /** Present while the request can be edited. */
  draft: Draft | null;
  editable: boolean;
  targets: RequestTarget[];
  questions: ReviewQuestion[];
  /** Present while the decision is the officer's to make. */
  choices: Choices | null;
  /** The close-out, once decided. */
  outcome: ReactNode;
  messages: ReactNode;
  unread: number;
  /** Changes when the header's message button asks for the messages: they unfold. */
  messagesAsk: number;
}) {
  const [showMessages, setShowMessages] = useState(messagesAsk > 0);
  useEffect(() => { if (messagesAsk > 0) setShowMessages(true); }, [messagesAsk]);
  const asked = workspace?.tally.asked ?? 0;
  const ir = session.information_request;
  const acceptFirst = Boolean(choices?.canAccept);
  const title = status === "accepted" ? "Administratively complete"
    : status === "refused" ? "Refused"
    : status === "returned" ? "Returned"
    : acceptFirst ? "Ready to accept"
    : asked ? `Return with ${plural(asked, "item")}`
    : "Nothing to ask";
  const day = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString("en-CA", { month: "short", day: "numeric" }) : "");
  const lede = status === "accepted" ? `${day(decidedAt)} · technical review next · not a variance`
    : status === "refused" ? `${day(decidedAt)} · with the appeal notice · nothing goes to the Council`
    : status === "returned" ? `${decidedAt ? `${sentPhrase(decidedAt)[0].toUpperCase()}${sentPhrase(decidedAt).slice(1)} · ` : ""}read-only until ${applicant} sends it again`
    : choices && !acceptFirst ? choices.why : "";

  return (
    <div className="cf-q-wrap is-wide rw-decide">
      <p className="cf-eyebrow">Decide · v{session.version}</p>
      <h2 className="cf-q-text rw-step-t" tabIndex={-1}>{title}</h2>
      {lede && <p className="cf-q-help">{lede}</p>}
      {session.diff && !outcome && <Since diff={session.diff} />}

      {outcome ?? (
        <>
          {(ir.text || ir.sent_at) && <pre className="rw-letter" aria-label={ir.sent_at ? "Sent request" : "Request text"}>{ir.text}</pre>}
          {draft && editable && workspace && <OwnItems draft={draft} limits={workspace.limits} targets={targets} questions={questions} />}
          {choices && (
            <div className="rw-acts">
              {acceptFirst ? (
                <>
                  <button type="button" className="cf-btn is-primary is-lg" disabled={choices.busy} onClick={choices.onAccept}><AcIcon name="check" size={16} />Accept</button>
                  <button type="button" className="cf-btn is-lg" disabled={!choices.canReturn || choices.busy} onClick={choices.onReturn}>Return</button>
                </>
              ) : (
                <>
                  <button type="button" className="cf-btn is-primary is-lg" disabled={!choices.canReturn || choices.busy} onClick={choices.onReturn}>
                    <AcIcon name="send" size={16} />Return
                  </button>
                  <button type="button" className="cf-btn is-lg" disabled data-requires-no-blocking-gaps="true" title={choices.why}>Accept</button>
                </>
              )}
              <button type="button" className="cf-btn is-lg is-ghost" disabled={!choices.canRefuse || choices.busy} onClick={choices.onRefuse}>Refuse</button>
            </div>
          )}
        </>
      )}

      <p className="rw-scope">Completeness only · not a design approval</p>

      <details className="rw-fold rw-msgs" open={showMessages} onToggle={(e) => setShowMessages(e.currentTarget.open)}>
        <summary className="cf-link-btn"><Icon24 name="msg" size={15} />Messages{unread > 0 && <span className="rw-n">{unread}</span>}</summary>
        {messages}
      </details>
    </div>
  );
}
