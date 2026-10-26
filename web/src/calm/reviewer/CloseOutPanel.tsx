/** Administrative acceptance and recording an externally issued variance are separate events. */
import { useId, useState, type ReactNode } from "react";
import { AccountsError } from "../../api/accounts";
import { packageReview } from "../../api/packageReview";
import type { CloseOut, RecordItem } from "../../api/types.gen";
import { AcIcon } from "../auth/bits";
import { DatePicker } from "../DatePicker";
import { ConfirmDialog, Modal } from "../ui";
import { dayLabel, dueView, pointerLabel } from "./packageView";
import "./review.css";

function Items({ items }: { items: RecordItem[] }) {
  return <ul className="pr-list">{items.map(item => <li className="pr-item" key={item.label}>
    <span className={`cf-dot is-${item.present ? "done" : "warning"}`} aria-hidden="true" />
    <details className="pr-item-body pr-fold"><summary className="pr-item-title">{item.label}<span className="cf-sr">{item.present ? " (on file)" : " (confirm it)"}</span></summary>
      <p className="pr-item-msg">{item.detail}</p>{item.source && <p className="pr-src">{pointerLabel(item.source)}</p>}
    </details>
  </li>)}</ul>;
}

export function CloseOutDue({ c, canMark, onChange, inline = false }: { c: CloseOut; canMark: boolean; onChange: (c: CloseOut) => void; inline?: boolean }) {
  const id = useId();
  const [confirm, setConfirm] = useState(false);
  const [issuing, setIssuing] = useState(false);
  const [issuedOn, setIssuedOn] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (c.outcome === "refuse") return null;
  async function record(kind: "issued" | "sent") {
    if (busy || !canMark || (kind === "issued" && !issuedOn)) return;
    setBusy(true); setError("");
    try {
      onChange(kind === "issued" ? await packageReview.recordIssued(c.case_id, issuedOn) : await packageReview.markSent(c.case_id));
      setConfirm(false); setIssuing(false);
    } catch (e) { setError(e instanceof AccountsError ? e.detail : "That didn’t save. Try again."); }
    finally { setBusy(false); }
  }
  const due = dueView(c);
  return <section className={`pr-due-sec${inline ? " is-inline" : " ac-side-sec"}`} aria-labelledby={`${id}-h`}>
    <h3 id={`${id}-h`} className={inline ? "cf-sr" : "ac-side-h"}>{c.issued_on ? "Copy to the Council" : "Variance issuance"}</h3>
    {!inline && <p className="rw-meta">{due.text}</p>}
    {!c.issued_on ? <>
      <p className="rw-meta">The copy is due 10 days after the variance is issued.</p>
      {canMark && <button type="button" className="cf-btn is-sm" disabled={busy} onClick={() => { setIssuedOn(""); setError(""); setIssuing(true); }}>Record variance issued</button>}
    </> : !c.sent && (canMark ? <button type="button" className="cf-btn is-sm" disabled={busy} onClick={() => setConfirm(true)}>Mark as sent</button> : <p className="rw-meta">Only the deciding officer can mark it sent</p>)}
    {error && !issuing && <p className="rw-hint" role="alert">{error}</p>}
    <Modal open={issuing} onClose={() => { if (!busy) setIssuing(false); }} labelledBy={`${id}-issued`} className="ac-return">
      <div className="cf-modal-body"><h2 className="cf-modal-title" id={`${id}-issued`}>Record variance issued</h2>
        <p className="rw-meta">Record the date you issued the variance outside Batatis. This does not issue a variance.</p>
        <DatePicker label="Date issued" value={issuedOn} onChange={setIssuedOn} />
        {error && <p className="rw-hint" role="alert">{error}</p>}
      </div>
      <div className="cf-modal-foot"><button type="button" className="cf-btn" disabled={busy} onClick={() => setIssuing(false)}>Cancel</button>
        <button type="button" className="cf-btn is-primary" disabled={busy || !issuedOn} onClick={() => void record("issued")}>{busy ? "Saving…" : "Record date"}</button>
      </div>
    </Modal>
    <ConfirmDialog open={confirm} title="Record that you sent the copy?" body={<p>This records your statement that you sent the variance copy to the Safety Codes Council. Batatis doesn’t send it or check that it arrived.{error && <span role="alert"> {error}</span>}</p>}
      cancel="Not yet" confirm={busy ? "Saving…" : "Record it"} onClose={() => { if (!busy) setConfirm(false); }} onConfirm={() => void record("sent")} />
  </section>;
}

export function CloseOutPanel({ c, bare = false, children }: { c: CloseOut; bare?: boolean; children?: ReactNode }) {
  const id = useId();
  const refusal = c.outcome === "refuse";
  const due = dueView(c);
  return <section className="pr rw-close-out" aria-labelledby={`${id}-h`}>
    <h2 className={bare ? "rw-close-title" : "pr-head-title"} id={`${id}-h`}>{refusal ? "Refusal recorded" : "Administratively complete · technical review next"}</h2>
    <p className="rw-meta">{dayLabel(c.decided_at)}{refusal ? " · keep the record on file" : " · not a variance or a design approval"}</p>
    {!refusal && <div className="rw-close-status"><span className={`cf-dot is-${due.tone}`} aria-hidden="true" /><div>
      <b>{c.issued_on ? `Variance issued ${dayLabel(c.issued_on)}` : "Variance not issued yet"}</b>
      {c.issued_by_name && <p className="rw-meta">Recorded by {c.issued_by_name}</p>}
      {c.issued_on && <p className="rw-meta">{due.text}</p>}
    </div></div>}
    {children}
    {!refusal && c.issued_on && <section className="pr-group" aria-label="Send to the Council"><h3 className="pr-group-h"><AcIcon name="send" size={14} /> Send</h3><Items items={c.record_package.send_to_council} /></section>}
    <section className="pr-group" aria-label="Keep on file"><h3 className="pr-group-h"><AcIcon name="files" size={14} /> Keep on file</h3><Items items={c.record_package.retain_on_file} /></section>
    <details className="pr-group pr-basis-fold"><summary>Basis</summary><ul className="pr-plain pr-basis">{c.record_package.basis.map(basis => <li key={basis}>{/^https?:/.test(basis) ? <a className="ac-link" href={basis} target="_blank" rel="noopener noreferrer">{basis.replace(/^https?:\/\//, "")}</a> : basis}</li>)}</ul><p className="pr-fine">{c.record_package.note}</p></details>
  </section>;
}
