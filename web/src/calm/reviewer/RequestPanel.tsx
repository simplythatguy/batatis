/**
 * The request as the applicant will receive it. The letter is always the server's rendering of the
 * last save, so what the officer reads here is exactly what is sent; edits save on their own and the
 * letter follows. Findings join or leave it from their cards; the officer's own items live here.
 */
import { useId, useState } from "react";
import type { RequestLimits, RequestTarget, ReviewSession } from "../../api/types.gen";
import type { ReviewQuestion } from "../../api/client";
import { AcIcon } from "../auth/bits";
import { CIcon } from "../ui";
import { clock, sentLabel } from "./queue";
import { officerItem } from "./requestDraft";
import { TargetSelect } from "./TargetSelect";
import type { useRequestDraft } from "./useRequestDraft";
import { clarificationSuggestions } from "./workspaceView";

type Draft = ReturnType<typeof useRequestDraft>;

/** "Saved 2:14 PM", "Saving…", or the save error with its retry. */
function SaveState({ draft }: { draft: Draft }) {
  const s = draft.state.save;
  if (s.kind === "error") {
    return (
      <span className="rw-save is-error" role="alert">
        {s.message}
        <button type="button" className="cf-link-btn" onClick={() => draft.dispatch({ type: "retry" })}>Retry</button>
      </span>
    );
  }
  if (draft.problem) return <span className="rw-save is-error" role="status">{draft.problem}</span>;
  const text = s.kind === "saving" || s.kind === "dirty" ? "Saving…" : draft.state.savedAt ? `Saved ${clock(draft.state.savedAt)}` : "Saved";
  return <span className="rw-save" role="status">{text}</span>;
}

export function RequestPanel({ session, applicant, draft, limits, asked, targets, questions, editable }: {
  session: ReviewSession;
  applicant: string;
  /** Absent when this request can't be edited (sent, earlier version, not yours). */
  draft: Draft | null;
  limits: RequestLimits | null;
  asked: number;
  targets: RequestTarget[];
  questions: ReviewQuestion[];
  editable: boolean;
}) {
  const id = useId();
  const [opening, setOpening] = useState(false);
  const [adding, setAdding] = useState(false);
  const [text, setText] = useState("");
  const [target, setTarget] = useState<RequestTarget | null>(null);
  const ir = session.information_request;
  const letter = ir.text;
  const items = draft?.state.content.items.filter((i) => !i.finding_key) ?? [];
  const full = Boolean(limits && draft && draft.state.content.items.length >= limits.items);
  const suggestions = draft ? clarificationSuggestions(questions, draft.state.content.items) : [];

  function add(t: string, where: RequestTarget) {
    draft?.dispatch({ type: "add", item: officerItem(t.trim(), where) });
    setAdding(false);
    setText("");
    setTarget(null);
  }

  return (
    <div className="rw-req">
      <div className="rw-req-h">
        <h3>{ir.sent_at ? `Sent ${sentLabel(ir.sent_at)}` : editable ? `What ${applicant} receives` : "Draft · not sent"}</h3>
        {editable && draft && (
          <button type="button" className="cf-btn is-xs" disabled={full || adding} onClick={() => setAdding(true)}>
            <CIcon name="plus" size={13} />Add item
          </button>
        )}
      </div>

      <pre className="rw-letter" aria-label="Request text">{letter || "Nothing to ask yet."}</pre>

      {editable && draft && limits && (
        <p className="rw-req-meta">
          <SaveState draft={draft} />
          <span>{asked} {asked === 1 ? "item" : "items"} · {letter.length.toLocaleString()} / {limits.text.toLocaleString()}</span>
        </p>
      )}

      {editable && draft && limits && (
        <>
          {opening ? (
            <div className="rw-edit">
              <label htmlFor={`${id}-o`}>Opening line</label>
              <textarea id={`${id}-o`} className="ac-ta" rows={3} maxLength={limits.intro} value={draft.state.content.intro}
                onChange={(e) => draft.dispatch({ type: "intro", value: e.target.value })} />
              <button type="button" className="cf-btn is-xs" onClick={() => setOpening(false)}>Done</button>
            </div>
          ) : (
            <button type="button" className="cf-link-btn rw-req-link" onClick={() => setOpening(true)}>Edit the opening line</button>
          )}

          {items.map((item) => (
            <div key={item.key} className="rw-edit is-item">
              <label htmlFor={`${id}-${item.key}`} className="cf-sr">Your item</label>
              <textarea id={`${id}-${item.key}`} className="ac-ta" rows={2} maxLength={limits.item_text} value={item.text}
                onChange={(e) => draft.dispatch({ type: "item", key: item.key, patch: { text: e.target.value } })} />
              <div className="rw-edit-row">
                <TargetSelect options={targets} value={item.target} onChange={(t) => draft.dispatch({ type: "item", key: item.key, patch: { target: t } })} />
                <button type="button" className="cf-btn is-xs is-ghost" aria-label="Remove this item" title="Remove"
                  onClick={() => draft.dispatch({ type: "remove", key: item.key })}><AcIcon name="x" size={14} /></button>
              </div>
            </div>
          ))}

          {adding && (
            <div className="rw-edit is-item is-new">
              <label htmlFor={`${id}-new`} className="cf-sr">New item</label>
              <textarea id={`${id}-new`} className="ac-ta" rows={2} maxLength={limits.item_text} value={text} autoFocus
                placeholder="Please provide…" onChange={(e) => setText(e.target.value)} />
              <div className="rw-edit-row">
                <TargetSelect options={targets} value={target} onChange={setTarget} />
                <button type="button" className="cf-btn is-xs is-ghost" onClick={() => { setAdding(false); setText(""); setTarget(null); }}>Cancel</button>
                <button type="button" className="cf-btn is-xs is-primary" disabled={!text.trim() || !target}
                  title={!target ? "Choose where they answer" : undefined} onClick={() => target && add(text, target)}>Add</button>
              </div>
            </div>
          )}

          {suggestions.length > 0 && (
            <details className="rw-fold">
              <summary>Open applicant questions · {suggestions.length}</summary>
              <ul className="rw-suggest">
                {suggestions.map((s) => (
                  <li key={s.target.field}>
                    <span>{s.target.label.replace(/^Applicant question · /, "")}</span>
                    <button type="button" className="cf-btn is-xs" disabled={full} onClick={() => add(s.text.slice(0, limits.item_text), s.target)}>Ask</button>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
    </div>
  );
}
