/**
 * Refuse: the officer writes the reasons; the 30-day appeal notice is added below them.
 * Batatis never drafts refusal reasons. A refusal closes the application. The decision is pinned
 * to the version on screen: when the application changed first, the error offers a refresh and the
 * written reasons stay in the box for the current version.
 */
import { useEffect, useId, useState } from "react";
import { AccountsError } from "../../api/accounts";
import { Modal } from "../ui";
import { APPEAL_NOTICE, APPEAL_SOURCE, reasonsProblem } from "./packageView";
import "./review.css";

export function RefuseDialog({ open, applicant, onClose, onSend, onRefresh }: {
  open: boolean;
  applicant: string;
  onClose: () => void;
  onSend: (reasons: string) => Promise<void>;
  /** Read the application again after a stale-version or availability error. */
  onRefresh: () => void;
}) {
  const id = useId();
  const [reasons, setReasons] = useState("");
  const [tried, setTried] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    setTried(false);
    setError("");
  }, [open]);

  const problem = reasonsProblem(reasons);

  async function send() {
    setTried(true);
    if (problem || sending) return;
    setSending(true);
    setError("");
    try {
      await onSend(reasons.trim());
      setReasons("");
    } catch (e) {
      setError(e instanceof AccountsError ? e.detail : "The refusal didn’t send. Try again.");
    } finally {
      setSending(false);
    }
  }

  return (
    <Modal open={open} onClose={sending ? () => {} : onClose} labelledBy={`${id}-t`} className="ac-return pr-refuse">
      <div className="cf-modal-body">
        <h2 id={`${id}-t`} className="cf-modal-title">Refuse the variance</h2>
        <label htmlFor={`${id}-r`} className="pr-group-h pr-label">Your reasons</label>
        <textarea
          id={`${id}-r`}
          className="ac-ta"
          rows={6}
          maxLength={3200}
          value={reasons}
          disabled={sending}
          onChange={(e) => setReasons(e.target.value)}
          aria-describedby={`${id}-rule`}
          aria-invalid={tried && problem ? true : undefined}
          autoFocus
        />
        <p id={`${id}-rule`} className={`ac-rule${!problem ? " is-met" : tried ? " is-unmet" : ""}`}>
          <span className="ac-rule-dot" aria-hidden="true" />
          {problem || `${reasons.trim().length} characters`}
        </p>
        <div className="pr-appeal">
          <p className="pr-group-h">Appeal notice · sent below your reasons</p>
          <p>{APPEAL_NOTICE}</p>
          <a className="ac-link pr-small" href={APPEAL_SOURCE} target="_blank" rel="noopener noreferrer">Safety Codes Council, Variances</a>
        </div>
        <p className="pr-note pr-small"><span className="cf-dot is-pending" aria-hidden="true" />Goes to {applicant} and closes the application. Send the written notice through your authority’s usual process.</p>
        {error && <p className="ac-error" role="alert">{error} <button type="button" className="cf-btn is-xs" disabled={sending} onClick={onRefresh}>Refresh</button></p>}
      </div>
      <div className="cf-modal-foot">
        <button type="button" className="cf-btn is-sm" disabled={sending} onClick={onClose}>Cancel</button>
        <button type="button" className="cf-btn is-sm is-primary" disabled={sending} onClick={() => void send()}>{sending ? "Sending…" : "Refuse"}</button>
      </div>
    </Modal>
  );
}
