/**
 * After a final decision: the copy to the Safety Codes Council is due 10 days later. Shows the due
 * date, the record package as a checklist, and "Mark as sent", which records the officer's own
 * statement. Batatis never sends, registers or decides anything.
 */
import { useId, useState } from "react";
import { AccountsError } from "../../api/accounts";
import { packageReview } from "../../api/packageReview";
import type { CloseOut, RecordItem } from "../../api/types.gen";
import { ConfirmDialog } from "../ui";
import { dayLabel, dueView, pointerLabel } from "./packageView";
import "./review.css";

function Items({ items }: { items: RecordItem[] }) {
  return (
    <ul className="pr-list">
      {items.map((r) => (
        <li key={r.label} className="pr-item">
          <span className={`cf-dot is-${r.present ? "done" : "warning"}`} aria-hidden="true" />
          <div className="pr-item-body">
            <p className="pr-item-title">{r.label}<span className="cf-sr">{r.present ? " (on file)" : " (confirm it)"}</span></p>
            <p className="pr-item-msg">{r.detail}</p>
            {r.source && pointerLabel(r.source) && <p className="pr-src"><span>{pointerLabel(r.source)}</span></p>}
          </div>
        </li>
      ))}
    </ul>
  );
}

/** The compact due line and "Mark as sent", for the side panel. */
export function CloseOutDue({ c, canMark, onChange }: { c: CloseOut; canMark: boolean; onChange: (c: CloseOut) => void }) {
  const id = useId();
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const due = dueView(c);

  async function mark() {
    setConfirm(false);
    setBusy(true);
    setError("");
    try {
      onChange(await packageReview.markSent(c.case_id));
    } catch (e) {
      setError(e instanceof AccountsError ? e.detail : "That didn’t save. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="ac-side-sec pr-due-sec" aria-labelledby={`${id}-h`}>
      <h3 id={`${id}-h`} className="ac-side-h">Copy to the Council</h3>
      <p className="pr-due"><span className={`cf-dot is-${due.tone}`} aria-hidden="true" />{due.text}</p>
      {!c.sent && (
        <>
          <p className="ac-faint ac-small">Decided {dayLabel(c.decided_at)}. You send the copy and register it; Batatis doesn’t send anything.</p>
          {canMark ? (
            <button type="button" className="cf-btn is-sm pr-mark" disabled={busy} onClick={() => setConfirm(true)}>{busy ? "Saving…" : "Mark as sent"}</button>
          ) : (
            <p className="ac-faint ac-small">Only the officer who decided can mark it as sent.</p>
          )}
        </>
      )}
      {error && <p className="ac-error" role="alert">{error}</p>}
      <ConfirmDialog
        open={confirm}
        title="Record that you sent the copy?"
        body={<p>This records your statement that you sent the copy of the variance to the Safety Codes Council today. Batatis doesn’t send it or check that it arrived.</p>}
        cancel="Not yet"
        confirm="Record it"
        onClose={() => setConfirm(false)}
        onConfirm={() => void mark()}
      />
    </section>
  );
}

/** The full close-out: due date, what to send, what to keep on file, and the bulletins. */
export function CloseOutPanel({ c }: { c: CloseOut }) {
  const id = useId();
  const due = dueView(c);
  const outcome = c.outcome === "accept" ? "Accepted as administratively complete" : c.outcome === "refuse" ? "Refused" : c.outcome;
  return (
    <section className="pr" aria-labelledby={`${id}-h`}>
      <header className="pr-head">
        <div className="pr-head-txt">
          <h2 id={`${id}-h`} className="pr-head-title">Close-out</h2>
          <p className="pr-faint">{outcome} · {dayLabel(c.decided_at)}</p>
        </div>
      </header>
      <div className="pr-body">
        <h2 className="pr-title">{c.sent ? "Copy recorded as sent" : "Send a copy to the Council within 10 days"}</h2>
        <p className="pr-due is-lg"><span className={`cf-dot is-${due.tone}`} aria-hidden="true" />{due.text}</p>
        <section className="pr-group" aria-label="Send to the Council">
          <h3 className="pr-group-h">Send to the Council</h3>
          <Items items={c.record_package.send_to_council} />
        </section>
        <section className="pr-group" aria-label="Keep on file">
          <h3 className="pr-group-h">Keep on file</h3>
          <Items items={c.record_package.retain_on_file} />
        </section>
        <section className="pr-group" aria-label="Basis">
          <h3 className="pr-group-h">Basis</h3>
          <ul className="pr-plain pr-basis">
            {c.record_package.basis.map((b) => <li key={b}>{/^https?:/.test(b) ? <a className="ac-link" href={b} target="_blank" rel="noopener noreferrer">{b.replace(/^https?:\/\//, "")}</a> : b}</li>)}
          </ul>
          <p className="pr-fine">{c.record_package.note}</p>
        </section>
      </div>
    </section>
  );
}
