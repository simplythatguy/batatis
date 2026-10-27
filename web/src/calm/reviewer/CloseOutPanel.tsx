/**
 * After a final decision. Accepting as administratively complete is not issuing a variance: the
 * file goes on to technical review. When the officer issues the variance (outside Batatis) they
 * record the date here, and only then is the copy to the Safety Codes Council due, 10 days later.
 * A refusal sends nothing to the Council. Batatis never sends, registers or decides anything.
 */
import { useState, type ReactNode } from "react";
import { AccountsError } from "../../api/accounts";
import { packageReview } from "../../api/packageReview";
import type { CloseOut, RecordItem } from "../../api/types.gen";
import { AcIcon } from "../auth/bits";
import { DatePicker } from "../DatePicker";
import { ConfirmDialog } from "../ui";
import { dayLabel, dueView } from "./packageView";

function Records({ label, items }: { label: string; items: RecordItem[] }) {
  if (!items.length) return null;
  return (
    <details className="rw-fold">
      <summary>{label} · {items.length}</summary>
      <ul className="rw-records">
        {items.map((r) => (
          <li key={r.label}>
            <span className={`cf-dot is-${r.present ? "done" : "warning"}`} aria-hidden="true" />
            <span><b>{r.label}</b>{r.detail && <small>{r.detail}</small>}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}

function Step({ tone, title, children }: { tone: string; title: string; children?: ReactNode }) {
  return (
    <li className="rw-step-row">
      <span className={`cf-dot is-${tone}`} aria-hidden="true" />
      <div><b>{title}</b>{children}</div>
    </li>
  );
}

export function CloseOutPanel({ c, canRecord, onChange }: { c: CloseOut; canRecord: boolean; onChange: (c: CloseOut) => void }) {
  const [picking, setPicking] = useState(false);
  const [date, setDate] = useState("");
  const [confirmSent, setConfirmSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const refused = c.outcome === "refuse";
  const due = dueView(c);

  async function save(kind: "issued" | "sent") {
    setBusy(true);
    setError("");
    try {
      onChange(kind === "issued" ? await packageReview.recordIssued(c.case_id, date) : await packageReview.markSent(c.case_id));
      setPicking(false);
      setConfirmSent(false);
    } catch (e) {
      setError(e instanceof AccountsError ? e.detail : "That didn’t save. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rw-close" aria-label="Close-out">
      <ol className="rw-steps">
        {!refused && (
          <>
            {c.issued_on ? (
              <Step tone="done" title={`Variance issued ${dayLabel(c.issued_on)}`}>
                {c.issued_by_name && <small>Recorded by {c.issued_by_name}</small>}
              </Step>
            ) : (
              <Step tone="pending" title="Variance not issued">
                <small>The Council copy is due 10 days after you issue it.</small>
                {canRecord && !picking && (
                  <button type="button" className="cf-btn" onClick={() => { setDate(""); setPicking(true); }}>Record the issue date</button>
                )}
                {picking && (
                  <div className="rw-issue">
                    <DatePicker label="Issued on" value={date} onChange={setDate} />
                    <div className="rw-own-row">
                      <button type="button" className="cf-btn is-primary" disabled={busy || !date} onClick={() => void save("issued")}>{busy ? "Saving…" : "Save"}</button>
                      <button type="button" className="cf-link-btn" disabled={busy} onClick={() => setPicking(false)}>Cancel</button>
                    </div>
                  </div>
                )}
              </Step>
            )}
            {c.issued_on && (
              <Step tone={due.tone} title={c.sent ? "Copy sent to the Council" : "Copy to the Council"}>
                <small>{due.text}</small>
                {!c.sent && canRecord && (
                  <button type="button" className="cf-btn" disabled={busy} onClick={() => setConfirmSent(true)}>
                    <AcIcon name="check" size={15} />Mark as sent
                  </button>
                )}
              </Step>
            )}
          </>
        )}
      </ol>
      {error && <p className="rw-hint is-error" role="alert">{error}</p>}
      {!refused && c.issued_on && <Records label="To send" items={c.record_package.send_to_council} />}
      <Records label="Keep on file" items={c.record_package.retain_on_file} />
      <ConfirmDialog
        open={confirmSent}
        title="Record that you sent the copy?"
        body={<p>Batatis doesn’t send it or check that it arrived.</p>}
        cancel="Not yet"
        confirm="Record it"
        onClose={() => setConfirmSent(false)}
        onConfirm={() => void save("sent")}
      />
    </section>
  );
}
