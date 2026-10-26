/** Standalone third-party packages only: edit a draft, save, and copy the server rendering out. */
import { useEffect, useId, useRef, useState } from "react";
import { AccountsError } from "../../api/accounts";
import { packageReview } from "../../api/packageReview";
import type { RequestLimits, RequestTarget, ReviewSession } from "../../api/types.gen";
import { TargetPicker } from "./RequestEditor";
import { draftReducer, editBody, initialDraft, officerItem } from "./requestDraft";
import { targetOptions } from "./workspaceView";
import "./review.css";

export function InfoRequest({ target, session, latest, canEdit, onChange, limits }: {
  target: { kind: "package"; id: string }; session: ReviewSession; latest: boolean; canEdit: boolean; applicant?: string;
  onChange: (session: ReviewSession) => void; limits?: RequestLimits;
}) {
  const id = useId();
  const [draft, setDraft] = useState(() => initialDraft(session));
  const [adding, setAdding] = useState("");
  const [destination, setDestination] = useState<RequestTarget | null>(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const pending = useRef(false);
  const editable = canEdit && latest && !session.information_request.sent_at;
  const busy = draft.save.kind === "saving";
  const dirty = draft.save.kind !== "saved";
  useEffect(() => { setDraft(initialDraft(session)); setError(""); }, [session.package_id, session.version]);
  async function save(): Promise<ReviewSession | null> {
    if (!dirty) return session;
    if (!editable || pending.current) return null;
    pending.current = true; setDraft(state => draftReducer(state, { type: "start" })); setError("");
    try {
      const index = await packageReview.edit(target, session.version, editBody(draft.content));
      if (!index.latest || index.latest.version !== session.version) throw new Error("The package version changed. Reload the latest review.");
      const saved = index.latest;
      setDraft(state => draftReducer(state, { type: "saved", session: saved, at: new Date().toISOString() }));
      onChange(saved); setNote("Draft saved."); return saved;
    } catch (e) {
      const message = e instanceof AccountsError ? e.detail : e instanceof Error ? e.message : "The draft didn’t save. Try again.";
      setDraft(state => draftReducer(state, { type: "failed", message, conflict: e instanceof AccountsError && e.status === 409 }));
      setError(message); return null;
    } finally { pending.current = false; }
  }
  async function copy() {
    const saved = await save();
    if (!saved) return;
    try { await navigator.clipboard.writeText(saved.information_request.text); setNote("Copied. Paste it into your email to the applicant."); }
    catch { setNote("Select the saved text below and copy it."); }
  }
  const edit = (event: Parameters<typeof draftReducer>[1]) => { setDraft(state => draftReducer(state, event)); setNote(""); setError(""); };
  return <section className="pr rw-package-request" aria-labelledby={`${id}-h`}>
    <h2 id={`${id}-h`} className="pr-title">Information request</h2><p className="rw-meta">Version {session.version}{latest ? "" : " · earlier version, read-only"} · copy out</p>
    <fieldset disabled={!editable || busy} className="rw-package-fields">
      <div className="rw-field"><label htmlFor={`${id}-intro`}>Opening line</label><textarea id={`${id}-intro`} className="ac-ta" rows={3} maxLength={limits?.intro} value={draft.content.intro} onChange={e => edit({ type: "intro", value: e.target.value })} /></div>
      {draft.content.items.map(item => <div className="rw-officer-item" key={item.key}>
        <div className="rw-field"><label htmlFor={`${id}-${item.key}`}>Item text</label><textarea id={`${id}-${item.key}`} className="ac-ta" rows={3} maxLength={limits?.item_text} value={item.text} onChange={e => edit({ type: "item", key: item.key, patch: { text: e.target.value } })} /></div>
        <button type="button" className="cf-btn is-xs" aria-pressed={item.included} onClick={() => edit({ type: "item", key: item.key, patch: { included: !item.included } })}>{item.included ? "Included" : "Left out"}</button>
        {!item.finding_key && <button type="button" className="cf-btn is-xs is-ghost" onClick={() => edit({ type: "remove", key: item.key })}>Remove</button>}
      </div>)}
      <div className="rw-field"><label htmlFor={`${id}-add`}>Your item</label><textarea id={`${id}-add`} className="ac-ta" rows={2} maxLength={limits?.item_text} value={adding} onChange={e => setAdding(e.target.value)} /></div>
      <TargetPicker options={targetOptions(session, [])} value={destination} onChange={setDestination} />
      <button type="button" className="cf-btn is-xs" disabled={!adding.trim() || !destination} onClick={() => { if (destination) { edit({ type: "add", item: officerItem(adding.trim(), destination) }); setAdding(""); setDestination(null); } }}>Add item</button>
    </fieldset>
    <p className="rw-meta">{dirty ? "Unsaved changes · the preview is the last save" : "Saved text"}</p><pre className="rw-letter" aria-label="Saved request text">{session.information_request.text}</pre>
    {error && <p className="rw-hint" role="alert">{error}</p>}{note && <p className="rw-meta" role="status">{note}</p>}
    <footer className="pr-foot"><button type="button" className="cf-btn is-sm" disabled={!editable || !dirty || busy} onClick={() => void save()}>{busy ? "Saving…" : "Save draft"}</button><button type="button" className="cf-btn is-sm is-primary" disabled={busy || (dirty && !editable)} onClick={() => void copy()}>Copy the text</button></footer>
  </section>;
}
