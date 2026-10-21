/** Return with a message: ticked gap items + the officer's note (at least 10 characters). */
import { useEffect, useId, useState } from "react";
import { accounts, AccountsError, type DecisionItemInput } from "../../api/accounts";
import type { EngineGap } from "../../api/client";
import { AcIcon } from "../auth/bits";
import { Modal } from "../ui";
import { decisionItems, draftQuestion, localDraft, messageProblem, returnableGaps } from "./decision";

export function ReturnDialog({ open, caseId, applicant, gaps, onClose, onSend }: {
  open: boolean;
  caseId: string;
  applicant: string;
  gaps: EngineGap[];
  onClose: () => void;
  onSend: (message: string, items: DecisionItemInput[]) => Promise<void>;
}) {
  const id = useId();
  const items = returnableGaps(gaps);
  const [ticked, setTicked] = useState<Set<string>>(new Set());
  const [message, setMessage] = useState("");
  const [drafting, setDrafting] = useState(false);
  const [draftNote, setDraftNote] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [tried, setTried] = useState(false);

  useEffect(() => {
    if (!open) return;
    setError("");
    setTried(false);
  }, [open]);

  const toggle = (gid: string) => setTicked((s) => {
    const n = new Set(s);
    if (n.has(gid)) n.delete(gid);
    else n.add(gid);
    return n;
  });
  const labels = items.filter((g) => ticked.has(g.id)).map((g) => g.message);
  const problem = messageProblem(message);

  async function draft() {
    if (drafting) return;
    if (!labels.length) {
      setDraftNote("Tick at least one item to draft from.");
      return;
    }
    setDrafting(true);
    setDraftNote("");
    try {
      const r = await accounts.assist({ case_id: caseId, screen: "review", question: draftQuestion(labels) });
      const text = r.answer?.trim();
      if (!text) throw new Error("empty");
      setMessage(text);
      setDraftNote("Draft written by the assistant. Read and edit it before sending.");
    } catch {
      setMessage(localDraft(labels));
      setDraftNote("Draft built from the ticked items. Edit it before sending.");
    } finally {
      setDrafting(false);
    }
  }

  async function send() {
    setTried(true);
    if (problem || sending) return;
    setSending(true);
    setError("");
    try {
      await onSend(message.trim(), decisionItems(items, ticked));
      setTicked(new Set());
      setMessage("");
      setDraftNote("");
    } catch (e) {
      setError(e instanceof AccountsError ? e.detail : "That didn’t send. Try again.");
    } finally {
      setSending(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} labelledBy={`${id}-t`} className="ac-return">
      <div className="cf-modal-body">
        <h2 id={`${id}-t`} className="cf-modal-title">Return with a message</h2>
        <p className="ac-faint ac-return-sub">{applicant} sees this note and the items you tick, and can fix and resend.</p>
        {items.length > 0 ? (
          <fieldset className="ac-checks">
            <legend className="cf-sr">Items to address</legend>
            {items.map((g) => (
              <label key={g.id} className="ac-check">
                <input type="checkbox" checked={ticked.has(g.id)} onChange={() => toggle(g.id)} />
                <span className="ac-box" aria-hidden="true"><AcIcon name="check" size={12} stroke={2.4} /></span>
                <span className="ac-check-text">
                  <span className={`cf-dot is-${g.severity === "blocking" ? "blocking" : "warning"}`} aria-hidden="true" />
                  {g.message}
                </span>
              </label>
            ))}
          </fieldset>
        ) : (
          <p className="ac-faint ac-small ac-checks-none">The completeness check found nothing to tick. Say in your message what the applicant should add.</p>
        )}
        <label htmlFor={`${id}-m`} className="cf-sr">Message to {applicant}</label>
        <textarea
          id={`${id}-m`}
          className="ac-ta"
          rows={6}
          maxLength={4000}
          placeholder="What should the applicant add or fix?"
          value={message}
          onChange={(e) => { setMessage(e.target.value); setDraftNote(""); }}
          aria-describedby={`${id}-rule`}
          aria-invalid={tried && problem ? true : undefined}
          autoFocus
        />
        <p id={`${id}-rule`} className={`ac-rule${!problem ? " is-met" : tried ? " is-unmet" : ""}`}>
          <span className="ac-rule-dot" aria-hidden="true" />
          {draftNote || (problem ? problem : `${message.trim().length} characters`)}
        </p>
        {error && <p className="ac-error" role="alert">{error}</p>}
      </div>
      <div className="cf-modal-foot ac-return-foot">
        {items.length > 0 && (
          <button type="button" className="cf-btn is-ghost is-sm" disabled={drafting} onClick={() => void draft()}>
            <AcIcon name="spark" size={15} />{drafting ? "Drafting…" : "Draft from ticked items"}
          </button>
        )}
        <span className="ac-grow" />
        <button type="button" className="cf-btn is-sm" onClick={onClose}>Cancel</button>
        <button type="button" className="cf-btn is-sm is-primary" disabled={sending} onClick={() => void send()}>{sending ? "Sending…" : "Send and return"}</button>
      </div>
    </Modal>
  );
}
