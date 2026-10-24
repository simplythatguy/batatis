import { useEffect, useState } from "react";
import { Modal } from "../ui";

/**
 * Confirm a permanent delete by name. Cancel has the focus; a failure keeps the dialog open with the
 * reason and changes nothing.
 */
export function DeleteDialog({ target, onDelete, onClose }: {
  target: { id: string; title: string } | null;
  /** Resolves to an error text, or null once deleted. */
  onDelete: (id: string) => Promise<string | null>;
  onClose: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { setBusy(false); setError(""); }, [target?.id]);
  const close = () => { if (!busy) onClose(); };
  const name = target?.title || "Untitled application";
  return (
    <Modal open={Boolean(target)} onClose={close} labelledBy="cf-delete-title" className="cf-confirm cf-delete">
      <div className="cf-modal-body" aria-busy={busy}>
        <h2 id="cf-delete-title" className="cf-modal-title">Delete “{name}”?</h2>
        <p className="cf-muted">Its answers and files go for good. This can’t be undone.</p>
        {error && <p className="ac-error" role="alert">{error}</p>}
      </div>
      <div className="cf-modal-foot">
        <button type="button" className="cf-btn" disabled={busy} onClick={close} autoFocus>Cancel</button>
        <button
          type="button"
          className="cf-btn is-danger"
          disabled={busy}
          onClick={() => {
            if (!target) return;
            setBusy(true);
            setError("");
            void onDelete(target.id).then((err) => {
              setBusy(false);
              if (err) setError(err);
              else onClose();
            });
          }}
        >
          {busy ? "Deleting…" : "Delete"}
        </button>
      </div>
    </Modal>
  );
}
