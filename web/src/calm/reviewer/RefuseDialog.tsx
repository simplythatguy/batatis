/**
 * Refuse: the officer writes the reasons; the 30-day appeal notice is added below them.
 * Batatis never drafts refusal reasons. A refusal closes the application.
 */
import { useEffect, useId, useState } from "react";
import { AccountsError } from "../../api/accounts";
import { Modal } from "../ui";
import { APPEAL_NOTICE, APPEAL_SOURCE, reasonsProblem } from "./packageView";
import "./review.css";

export function RefuseDialog({ open, applicant, onClose, onSend }: {
  open: boolean;
  applicant: string;
  onClose: () => void;
  onSend: (reasons: string) => Promise<void>;
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
      await onSend(reasons);
      setReasons("");
    } catch (e) {
      setError(e instanceof AccountsError ? e.detail : "That didn’t send. Try again.");
    } finally {
      setSending(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} labelledBy={`${id}-t`} className="ac-return pr-refuse">
      <div className="cf-modal-body">
        <h2 id={`${id}-t`} className="cf-modal-title">Refuse the variance</h2>
        <p className="ac-faint ac-return-sub">Write your reasons in your own words. Batatis doesn’t draft refusal reasons.</p>
        <label htmlFor={`${id}-r`} className="pr-group-h pr-label">Your reasons</label>
        <textarea
          id={`${id}-r`}
          className="ac-ta"
          rows={6}
          maxLength={3200}
          value={reasons}
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
        <p className="pr-note pr-small"><span className="cf-dot is-pending" aria-hidden="true" />{applicant} gets your reasons and the appeal notice in the application’s messages. The application is closed and read-only. Issue the written notice of refusal through your authority’s usual process.</p>
        {error && <p className="ac-error" role="alert">{error}</p>}
      </div>
      <div className="cf-modal-foot">
        <button type="button" className="cf-btn is-sm" onClick={onClose}>Cancel</button>
        <button type="button" className="cf-btn is-sm is-primary" disabled={sending} onClick={() => void send()}>{sending ? "Sending…" : "Send the refusal"}</button>
      </div>
    </Modal>
  );
}
