import { useEffect, useState } from "react";
import { normalizeTitle, TITLE_EMPTY, TITLE_MAX } from "../rename";
import { Modal } from "../ui";

/** Rename from the application list (⋯ → Rename). Keeps the typed name and says why when a save fails. */
export function RenameDialog({ target, onSave, onClose }: {
  target: { id: string; title: string } | null;
  /** Resolves to an error text, or null when saved. */
  onSave: (id: string, title: string) => Promise<string | null>;
  onClose: () => void;
}) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // Reset when a new target opens, not when it closes: the typed name stays while the dialog fades out.
  useEffect(() => { if (target) { setName(target.title); setError(""); setBusy(false); } }, [target?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const close = () => { if (!busy) onClose(); };
  return (
    <Modal open={Boolean(target)} onClose={close} labelledBy="cf-rename-title" className="cf-confirm cf-rename">
      <form
        aria-busy={busy}
        onSubmit={(e) => {
          e.preventDefault();
          if (!target || busy) return;
          const next = normalizeTitle(name);
          if (!next) { setError(TITLE_EMPTY); return; }
          if (next === target.title) { onClose(); return; }
          setBusy(true);
          setError("");
          void onSave(target.id, next).then((err) => {
            setBusy(false);
            if (err) setError(err);
            else onClose();
          });
        }}
      >
        <div className="cf-modal-body">
          <h2 id="cf-rename-title" className="cf-modal-title">Rename</h2>
          <input className="cf-uline cf-rename-input" aria-label="Application name" value={name} maxLength={TITLE_MAX} autoFocus onChange={(e) => setName(e.target.value)} />
          {error && <p className="ac-error" role="alert">{error}</p>}
        </div>
        <div className="cf-modal-foot">
          <button type="button" className="cf-btn" disabled={busy} onClick={close}>Cancel</button>
          <button type="submit" className="cf-btn is-primary" disabled={busy}>{busy ? "Saving…" : "Save"}</button>
        </div>
      </form>
    </Modal>
  );
}
