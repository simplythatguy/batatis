/** A human-owned requirement determination, separate from credentials and technical evidence. */
import { useEffect, useId, useState } from "react";
import { AccountsError } from "../../api/accounts";
import { engine, type ProfessionalResult } from "../../api/client";
import type { Case, ProfessionalRequirementRequest } from "../../api/types.gen";
import { Modal } from "../ui";
import { sentLabel } from "./queue";

export function ProfessionalRequirement({ c, editable, busy, unresolved, onResolve, onEditingChange }: {
  c: Case;
  editable: boolean;
  busy: boolean;
  unresolved: boolean;
  onResolve: (body: ProfessionalRequirementRequest) => Promise<void>;
  onEditingChange?: (editing: boolean) => void;
}) {
  const id = useId();
  const [screen, setScreen] = useState<ProfessionalResult | null>(null);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [loadError, setLoadError] = useState("");
  const [open, setOpen] = useState(false);
  const [required, setRequired] = useState<boolean | null>(null);
  const [scope, setScope] = useState("");
  const [basis, setBasis] = useState("");
  const [reference, setReference] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setScreen(null);
    setLoadError("");
    engine.professional(c.id).then(result => { if (active) setScreen(result); }, () => {
      if (active) setLoadError("The professional check didn’t load.");
    });
    return () => { active = false; };
  }, [c.id, c.version, loadAttempt]);
  useEffect(() => { if (!editable) setOpen(false); }, [editable]);
  useEffect(() => {
    onEditingChange?.(open);
    return () => onEditingChange?.(false);
  }, [open, onEditingChange]);

  const resolution = screen?.resolution;
  const mandatory = screen?.mandatory_required ?? (screen?.required === "yes");
  const history = c.professional_resolutions ?? [];
  if (!unresolved && !history.length && screen?.required !== "yes") return null;
  const problem = required === null ? "Choose whether a professional is required."
    : scope.trim().length < 3 ? "Describe the scope you reviewed."
    : basis.trim().length < 10 ? "Record the basis for this determination."
    : reference.trim().length < 3 ? "Add the authority record or reference you relied on." : "";

  function begin() {
    setRequired(null); setScope(""); setBasis(""); setReference(""); setError(""); setOpen(true);
  }
  async function save() {
    if (problem || busy || required === null || !editable) return;
    setError("");
    try {
      await onResolve({ expected_version: c.version, required, scope: scope.trim(), basis: basis.trim(), reference: reference.trim() });
      setOpen(false);
    } catch (e) {
      setError(e instanceof AccountsError ? e.detail : "The determination wasn’t saved. Try again.");
    }
  }

  return (
    <section className="ac-side-sec" aria-labelledby={`${id}-h`}>
      <h3 id={`${id}-h`} className="ac-side-h">Professional requirement</h3>
      {resolution ? (
        <div className="ac-small">
          <p>{resolution.required ? "Required" : "Not required"} for {resolution.scope}.</p>
          <p className="ac-faint">{resolution.basis}</p>
          <p className="ac-faint">{resolution.reference} · recorded by {resolution.by_name} · {sentLabel(resolution.at)}</p>
        </div>
      ) : (
        <p className="ac-faint ac-small">{loadError || (history.length
          ? "Earlier determination · decide again for this version"
          : "Left for you · needed before accepting")}</p>
      )}
      {loadError && <button type="button" className="cf-btn is-xs" onClick={() => setLoadAttempt(attempt => attempt + 1)}>Try again</button>}
      {editable && <button type="button" className="cf-btn is-sm" disabled={busy || !screen} onClick={begin}>{resolution ? "Update determination" : "Record determination"}</button>}
      <Modal open={open} onClose={() => { if (!busy) setOpen(false); }} labelledBy={`${id}-title`} className="ac-return">
        <div className="cf-modal-body">
          <h2 id={`${id}-title`} className="cf-modal-title">Record the professional requirement</h2>
          <p className="ac-faint ac-small">Mandatory duties still apply. Not a design approval or a check of the professional.</p>
          <div role="group" aria-label="Is a registered professional required?" className="cf-chip-row">
            <button type="button" className="cf-chip" aria-pressed={required === true} disabled={busy} onClick={() => setRequired(true)}>Required</button>
            <button type="button" className="cf-chip" aria-pressed={required === false} disabled={busy || mandatory} onClick={() => setRequired(false)}>Not required for this scope</button>
          </div>
          {mandatory && <p className="ac-help">A mandatory requirement cannot be waived here.</p>}
          <div className="ac-field">
            <label htmlFor={`${id}-scope`}>Scope reviewed</label>
            <input id={`${id}-scope`} className="ac-in" value={scope} maxLength={1000} disabled={busy} onChange={e => setScope(e.target.value)} />
          </div>
          <div className="ac-field">
            <label htmlFor={`${id}-basis`}>Basis for the determination</label>
            <textarea id={`${id}-basis`} className="ac-ta" rows={4} value={basis} maxLength={4000} disabled={busy} onChange={e => setBasis(e.target.value)} />
          </div>
          <div className="ac-field">
            <label htmlFor={`${id}-reference`}>Authority record or reference</label>
            <input id={`${id}-reference`} className="ac-in" value={reference} maxLength={1000} disabled={busy} onChange={e => setReference(e.target.value)} />
          </div>
          {problem && <p className="ac-help" role="note">{problem}</p>}
          {error && <p className="ac-error" role="alert">{error}</p>}
        </div>
        <div className="cf-modal-foot">
          <button type="button" className="cf-btn is-sm" disabled={busy} onClick={() => setOpen(false)}>Cancel</button>
          <button type="button" className="cf-btn is-sm is-primary" disabled={busy || Boolean(problem)} onClick={() => void save()}>{busy ? "Saving…" : "Record determination"}</button>
        </div>
      </Modal>
    </section>
  );
}
