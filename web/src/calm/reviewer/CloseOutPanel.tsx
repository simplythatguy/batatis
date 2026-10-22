/**
 * After a final decision: the copy to the Safety Codes Council is due 10 days later. Shows the due
 * date, the record package as a checklist, and "Mark as sent", which records the officer's own
 * statement. Batatis never sends, registers or decides anything.
 */
import { useId, useState, type ReactNode } from "react";
import { AccountsError } from "../../api/accounts";
import { packageReview } from "../../api/packageReview";
import type { CloseOut, RecordItem } from "../../api/types.gen";
import { AcIcon } from "../auth/bits";
import { ConfirmDialog } from "../ui";
import { StepTitle } from "./PackageReview";
import { dayLabel, dueView, pointerLabel } from "./packageView";
import "./review.css";

function Items({ items }: { items: RecordItem[] }) {
  return (
    <ul className="pr-list">
      {items.map((r) => (
        <li key={r.label} className="pr-item">
          <span className={`cf-dot is-${r.present ? "done" : "warning"}`} aria-hidden="true" />
          <details className="pr-item-body pr-fold">
            <summary className="pr-item-title">{r.label}<span className="cf-sr">{r.present ? " (on file)" : " (confirm it)"}</span></summary>
            <p className="pr-item-msg">{r.detail}</p>
            {r.source && pointerLabel(r.source) && <p className="pr-src"><span>{pointerLabel(r.source)}</span></p>}
          </details>
        </li>
      ))}
    </ul>
  );
}

/** The compact due line and "Mark as sent", for the side panel. */
export function CloseOutDue({ c, canMark, onChange, inline = false }: { c: CloseOut; canMark: boolean; onChange: (c: CloseOut) => void; /** Inside the close-out itself: only the note and "Mark as sent". */ inline?: boolean }) {
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
    <section className={`ac-side-sec pr-due-sec${inline ? " is-inline" : ""}`} aria-labelledby={`${id}-h`}>
      <h3 id={`${id}-h`} className={inline ? "cf-sr" : "ac-side-h"}>Copy to the Council</h3>
      {!inline && <p className="pr-due"><span className={`cf-dot is-${due.tone}`} aria-hidden="true" />{due.text}</p>}
      {!c.sent && (
        <>
          {!inline && <p className="ac-faint ac-small">Decided {dayLabel(c.decided_at)} · you send it, Batatis doesn’t</p>}
          {canMark ? (
            <button type="button" className="cf-btn is-sm pr-mark" disabled={busy} onClick={() => setConfirm(true)}>{busy ? "Saving…" : "Mark as sent"}</button>
          ) : (
            <p className="ac-faint ac-small">Only the deciding officer can mark it sent</p>
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
export function CloseOutPanel({ c, bare = false, children }: { c: CloseOut; /** Inside the review path: no header of its own. */ bare?: boolean; /** Under the due line: "Mark as sent". */ children?: ReactNode }) {
  const id = useId();
  const due = dueView(c);
  const outcome = c.outcome === "accept" ? "Accepted as administratively complete" : c.outcome === "refuse" ? "Refused" : c.outcome;
  return (
    <section className="pr" aria-labelledby={`${id}-h`}>
      {bare ? (
        <h2 id={`${id}-h`} className="cf-sr">Close-out · {outcome} · {dayLabel(c.decided_at)}</h2>
      ) : (
        <header className="pr-head">
          <div className="pr-head-txt">
            <h2 id={`${id}-h`} className="pr-head-title">Close-out</h2>
            <p className="pr-faint">{outcome} · {dayLabel(c.decided_at)}</p>
          </div>
        </header>
      )}
      <div className={bare ? undefined : "pr-body"}>
        <StepTitle step="final" icon="flag">{c.sent ? "Copy sent to the Council" : "Send a copy to the Council"}</StepTitle>
        <div className={`co-due is-${{ done: "green", blocking: "rose", warning: "amber", pending: "blue" }[due.tone]}`}>
          <span className="pr-ico" aria-hidden="true"><AcIcon name={c.sent ? "check" : "clock"} size={20} /></span>
          <div className="co-due-txt">
            <b>{due.text}</b>
            {!c.sent && <span>You send it · Batatis doesn’t</span>}
          </div>
          {children}
        </div>
        <section className="pr-group" aria-label="Send to the Council">
          <h3 className="pr-group-h"><AcIcon name="send" size={14} />Send</h3>
          <Items items={c.record_package.send_to_council} />
        </section>
        <section className="pr-group" aria-label="Keep on file">
          <h3 className="pr-group-h"><AcIcon name="files" size={14} />Keep on file</h3>
          <Items items={c.record_package.retain_on_file} />
        </section>
        <details className="pr-group pr-basis-fold" aria-label="Basis">
          <summary className="pr-group-h">Basis</summary>
          <ul className="pr-plain pr-basis">
            {c.record_package.basis.map((b) => <li key={b}>{/^https?:/.test(b) ? <a className="ac-link" href={b} target="_blank" rel="noopener noreferrer">{b.replace(/^https?:\/\//, "")}</a> : b}</li>)}
          </ul>
          <p className="pr-fine">{c.record_package.note}</p>
        </details>
      </div>
    </section>
  );
}
