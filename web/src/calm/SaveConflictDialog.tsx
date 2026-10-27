import { useEffect, useState } from "react";
import { useCase } from "../store";
import type { ReconciliationChoices } from "./reconcileDraft";
import { Modal } from "./ui";

export function SaveConflictDialog() {
  const { saveConflictReview: review, saveReviewedChanges, closeSaveConflictReview, reviewSaveConflict } = useCase();
  const [choices, setChoices] = useState<ReconciliationChoices>({});
  const open = review?.kind === "review";
  useEffect(() => { if (!open) setChoices({}); }, [open]);
  if (!open) return null;
  const missing = review.conflicts.some(item => !choices[item.id]);
  return <Modal open onClose={closeSaveConflictReview} labelledBy="cf-save-review-title" className="cf-save-review">
    <div className="cf-modal-body">
      <h2 id="cf-save-review-title" className="cf-modal-title">Review saved changes</h2>
      <p className="cf-muted">Another device saved changes. Changes to different answers are kept together. Choose which value to keep where both changed.</p>
      {review.conflicts.map(item => <section key={item.id} className="cf-save-review-item" role="group" aria-label={item.label}>
        <h3>{item.label}</h3>
        <div className="cf-save-review-values">
          <div><span className="cf-faint">Your draft</span><pre>{item.mine}</pre>
            <button type="button" className="cf-btn is-sm" aria-pressed={choices[item.id] === "mine"} onClick={() => setChoices(before => ({ ...before, [item.id]: "mine" }))}>Keep mine</button>
          </div>
          <div><span className="cf-faint">Saved on another device</span><pre>{item.saved}</pre>
            <button type="button" className="cf-btn is-sm" aria-pressed={choices[item.id] === "saved"} onClick={() => setChoices(before => ({ ...before, [item.id]: "saved" }))}>Use saved</button>
          </div>
        </div>
      </section>)}
      {!review.conflicts.length && <p className="cf-note">Your changes can be saved together with the saved answers.</p>}
      <p className="cf-faint cf-small">Unfinished text stays unfinished. Your current draft is kept until the reviewed save succeeds.</p>
      {review.note && <p className="cf-note" role="alert">{review.note}</p>}
      {missing && <p className="cf-faint cf-small">Choose a value for each changed answer to save.</p>}
    </div>
    <div className="cf-modal-foot">
      <button type="button" className="cf-btn" disabled={review.saving} onClick={closeSaveConflictReview} autoFocus>Keep reviewing later</button>
      {review.note && <button type="button" className="cf-btn" disabled={review.saving} onClick={() => { setChoices({}); void reviewSaveConflict(); }}>Review latest</button>}
      <button type="button" className="cf-btn is-primary" disabled={review.saving || missing} onClick={() => void saveReviewedChanges(choices)}>{review.saving ? "Saving…" : "Save reviewed changes"}</button>
    </div>
  </Modal>;
}
