import { useEffect, useId, useState } from "react";
import type { RequestLimits, RequestTarget } from "../../api/types.gen";
import type { ReviewQuestion } from "../../api/client";
import { AcIcon } from "../auth/bits";
import { CIcon, Modal } from "../ui";
import { officerItem } from "./requestDraft";
import type { useRequestDraft } from "./useRequestDraft";
import { clarificationSuggestions } from "./workspaceView";

export function TargetPicker({ options, value, onChange }: { options: RequestTarget[]; value: RequestTarget | null; onChange: (target: RequestTarget) => void }) {
  const id = useId();
  return <details className="rw-target-picker">
    <summary aria-controls={`${id}-options`} title={value?.label}><span>{value?.label || "Choose a place to answer"}</span><AcIcon name="chev" size={14} /></summary>
    <div id={`${id}-options`} className="rw-target-options" aria-label="Where they answer">{options.map(option => <button type="button" key={`${option.section}:${option.field ?? ""}`} title={option.label}
      aria-pressed={value?.section === option.section && value.field === option.field}
      onClick={event => { onChange(option); const details = event.currentTarget.closest("details"); if (details) { details.open = false; details.querySelector("summary")?.focus(); } }}>{option.label}</button>)}</div>
  </details>;
}

export function RequestEditor({ draft, targets, questions, limits, onEditing }: { onEditing?: (open: boolean) => void; draft: ReturnType<typeof useRequestDraft>; targets: RequestTarget[]; questions: ReviewQuestion[]; limits: RequestLimits }) {
  const id = useId();
  const [opening, setOpening] = useState(false);
  const [adding, setAdding] = useState(false);
  const [text, setText] = useState("");
  const [target, setTarget] = useState<RequestTarget | null>(null);
  useEffect(() => { onEditing?.(adding); return () => onEditing?.(false); }, [adding, onEditing]);
  const cap = draft.state.content.items.length >= limits.items;
  const suggestions = clarificationSuggestions(questions, draft.state.content.items);
  const add = (text: string, target: RequestTarget) => { draft.dispatch({ type: "add", item: officerItem(text, target) }); setAdding(false); setText(""); setTarget(null); };
  return <>
    <div className="rw-editor-tools">
      <button type="button" className="cf-btn is-xs is-ghost" aria-expanded={opening} onClick={() => setOpening(!opening)}>Edit opening line</button>
      <button type="button" className="cf-btn is-xs" disabled={cap} onClick={() => setAdding(true)}><CIcon name="plus" size={13} />Add item</button>
    </div>
    {cap && <p className="rw-hint">At most {limits.items} items · remove one to add another</p>}
    {opening && <div className="rw-field"><label htmlFor={`${id}-intro`}>Opening line</label>
      <textarea className="ac-ta" id={`${id}-intro`} rows={4} maxLength={limits.intro} value={draft.state.content.intro} onChange={e => draft.dispatch({ type: "intro", value: e.target.value })} />
      <small className="rw-meta">{draft.state.content.intro.length} / {limits.intro}</small>
    </div>}
    {draft.state.content.items.filter(i => !i.finding_key).map(item => <div className="rw-officer-item" key={item.key}>
      <div className="rw-field"><label htmlFor={`${id}-${item.key}`}>{item.authored_by === "officer" ? "Your item" : "Request item"}</label>
        <textarea id={`${id}-${item.key}`} className="ac-ta" rows={3} maxLength={limits.item_text} value={item.text} onChange={e => draft.dispatch({ type: "item", key: item.key, patch: { text: e.target.value } })} />
      </div>
      <TargetPicker options={targets} value={item.target} onChange={target => draft.dispatch({ type: "item", key: item.key, patch: { target } })} />
      <div className="rw-editor-tools">
        <button type="button" className="cf-btn is-xs is-ghost" aria-pressed={item.included} onClick={() => draft.dispatch({ type: "item", key: item.key, patch: { included: !item.included } })}>{item.included ? "In request" : "Left out"}</button>
        {item.authored_by === "officer" && <button type="button" className="cf-btn is-xs is-ghost" onClick={() => draft.dispatch({ type: "remove", key: item.key })}>Remove</button>}
      </div>
    </div>)}
    {suggestions.length > 0 && <details className="rw-suggestions"><summary>Applicant questions · {suggestions.length}</summary>
      {suggestions.map(suggestion => <div key={suggestion.target.field}><p>{suggestion.target.label}</p>
        <button type="button" className="cf-btn is-xs" disabled={cap} onClick={() => { if (suggestion.text.length <= limits.item_text) add(suggestion.text, suggestion.target); else { setText(suggestion.text); setTarget(suggestion.target); setAdding(true); } }}>Add to request</button>
      </div>)}
    </details>}
    <Modal open={adding} onClose={() => setAdding(false)} labelledBy={`${id}-add-title`} className="ac-return">
      <div className="cf-modal-body">
        <h2 id={`${id}-add-title`} className="cf-modal-title">Add an item</h2>
        <div className="rw-field"><label htmlFor={`${id}-add-text`}>They read</label><textarea className="ac-ta" id={`${id}-add-text`} rows={4} maxLength={limits.item_text} value={text} onChange={e => setText(e.target.value)} /></div>
        <p className="rw-meta">{text.length} / {limits.item_text}{text.length > limits.item_text ? " · shorten this item" : ""}</p>
        <p className="rw-label">They answer at</p><TargetPicker options={targets} value={target} onChange={setTarget} />
      </div>
      <div className="cf-modal-foot"><button type="button" className="cf-btn" onClick={() => setAdding(false)}>Cancel</button>
        <button type="button" className="cf-btn is-primary" disabled={!text.trim() || !target || cap || text.length > limits.item_text} onClick={() => { if (target) add(text.trim(), target); }}>Add item</button>
      </div>
    </Modal>
  </>;
}
