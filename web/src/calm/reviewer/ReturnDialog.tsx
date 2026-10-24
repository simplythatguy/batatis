/** Return with a message: ticked gap items + the officer's note (at least 10 characters). */
import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { accounts, AccountsError, type DecisionItemInput } from "../../api/accounts";
import type { EngineGap, ReviewQuestion } from "../../api/client";
import { accountSession } from "../account";
import { AcIcon } from "../auth/bits";
import { useThreadRequests } from "../threadRequests";
import { Modal } from "../ui";
import { decisionItems, draftQuestion, localDraft, messageProblem, returnChoices } from "./decision";

export function ReturnDialog({ open, caseId, applicant, gaps, questions, questionError, onClose, onSend }: {
  open: boolean;
  caseId: string;
  applicant: string;
  gaps: EngineGap[];
  questions: ReviewQuestion[];
  questionError: string;
  onClose: () => void;
  onSend: (message: string, items: DecisionItemInput[]) => Promise<void>;
}) {
  const id = useId();
  const { phase, user, startRequest, finishRequest } = useThreadRequests(caseId);
  const items = returnChoices(gaps, questions);
  const [ticked, setTicked] = useState<Set<string>>(new Set());
  const [message, setMessage] = useState("");
  const [drafting, setDrafting] = useState(false);
  const [draftNote, setDraftNote] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [tried, setTried] = useState(false);
  const activeDraft = useRef<AbortController | null>(null);
  const opening = useRef(0);

  const cancelDraft = useCallback(() => {
    const ctl = activeDraft.current;
    activeDraft.current = null;
    if (ctl) { ctl.abort(); finishRequest(ctl); }
  }, [finishRequest]);

  // Closing, switching cases, and replacing a session invalidate the whole draft request.
  // Ordinary parent renders keep this identity, so background refreshes retain the editor.
  useLayoutEffect(() => {
    opening.current++;
    cancelDraft();
    setDrafting(false);
    return () => { opening.current++; cancelDraft(); };
  }, [open, caseId, phase, user, cancelDraft]);

  useLayoutEffect(() => {
    setTicked(new Set());
    setMessage("");
    setDraftNote("");
    setError("");
    setTried(false);
  }, [caseId, phase, user]);

  useEffect(() => {
    if (!open) return;
    setError("");
    setTried(false);
  }, [open]);

  function edited() {
    cancelDraft();
    setDrafting(false);
    setDraftNote("");
  }
  const toggle = (gid: string) => {
    edited();
    setTicked((s) => {
      const n = new Set(s);
      if (n.has(gid)) n.delete(gid);
      else n.add(gid);
      return n;
    });
  };
  const labels = items.filter((g) => ticked.has(g.id)).map((g) => g.message);
  const problem = messageProblem(message);
  const selected = JSON.stringify(decisionItems(items, ticked).sort((a, b) => a.gap_id!.localeCompare(b.gap_id!)));

  // A changed selected instruction also invalidates its draft. Equivalent refreshed gap
  // objects do not: depend on the selected content, not the array or callback identity.
  useLayoutEffect(() => {
    cancelDraft();
    setDrafting(false);
    setDraftNote("");
  }, [selected, cancelDraft]);

  function close() {
    cancelDraft();
    setDrafting(false);
    onClose();
  }

  async function draft() {
    if (!open || sending || activeDraft.current) return;
    if (!labels.length) {
      setDraftNote("Tick at least one item to draft from.");
      return;
    }
    setDrafting(true);
    setDraftNote("");
    const ctl = startRequest(), context = opening.current, session = accountSession();
    activeDraft.current = ctl;
    const current = () => activeDraft.current === ctl && !ctl.signal.aborted
      && opening.current === context && accountSession() === session;
    try {
      const r = await accounts.assist({ case_id: caseId, screen: "review", question: draftQuestion(labels) }, ctl.signal);
      if (!current()) return;
      const text = r.answer?.trim();
      if (!text) throw new Error("empty");
      setMessage(text);
      setDraftNote("Draft written by the assistant. Read and edit it before sending.");
    } catch {
      if (!current()) return;
      setMessage(localDraft(labels));
      setDraftNote("Draft built from the ticked items. Edit it before sending.");
    } finally {
      finishRequest(ctl);
      if (activeDraft.current === ctl) { activeDraft.current = null; setDrafting(false); }
    }
  }

  async function send() {
    setTried(true);
    if (problem || sending) return;
    cancelDraft();
    setDrafting(false);
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
    <Modal open={open} onClose={close} labelledBy={`${id}-t`} className="ac-return">
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
                  <span className={`cf-dot is-${g.severity === "blocking" ? "blocking" : g.severity ? "warning" : "pending"}`} aria-hidden="true" />
                  {!g.severity && "Clarification · "}{g.message}
                </span>
              </label>
            ))}
          </fieldset>
        ) : (
          <p className="ac-faint ac-small ac-checks-none">No saved items to tick. Say in your message what the applicant should add.</p>
        )}
        {questionError && <p className="ac-faint ac-small" role="status">{questionError}</p>}
        <label htmlFor={`${id}-m`} className="cf-sr">Message to {applicant}</label>
        <textarea
          id={`${id}-m`}
          className="ac-ta"
          rows={6}
          maxLength={4000}
          placeholder="What should the applicant add or fix?"
          value={message}
          onChange={(e) => { edited(); setMessage(e.target.value); }}
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
          <button type="button" className="cf-btn is-ghost is-sm" disabled={drafting || sending} onClick={() => void draft()}>
            <AcIcon name="spark" size={15} />{drafting ? "Drafting…" : "Draft from ticked items"}
          </button>
        )}
        <span className="ac-grow" />
        <button type="button" className="cf-btn is-sm" onClick={close}>Cancel</button>
        <button type="button" className="cf-btn is-sm is-primary" disabled={sending} onClick={() => void send()}>{sending ? "Sending…" : "Send and return"}</button>
      </div>
    </Modal>
  );
}
