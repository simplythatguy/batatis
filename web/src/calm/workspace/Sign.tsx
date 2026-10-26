import { useEffect, useRef, useState, type PointerEvent } from "react";
import { useCase } from "../../store";
import { useCurrentApplication } from "../begin";
import { Icon24 } from "../icons";
import { CIcon, Modal } from "../ui";
import { workspaceApi, workspaceFailure, type Signature, type Signer } from "./api";
import { albertaDate, signatureImage } from "./signature";
import type { WorkspaceController } from "./useWorkspace";

/** Transcribed from challenge_2026-09-15.pdf, page 2, Signatures and Disclosures. */
export const DISCLOSURE = "The collection of personal information is authorized under section 4(c) of the Protection of Privacy Act. This personal information will be used to review and assess the variance application, including verifying information provided. I understand that the information provided will be shared with the Safety Codes Council in accordance with the municipality's Quality Management System agreement. The following information may also be published on the Safety Codes Council website under section of the Protection of Privacy Act: permit number, municipality, issue date and completion date, permit type, project type, work class, address, description of the project, total square footage, and project value range. By checking this box, I acknowledge and agree to the described use of the information provided.";
export const ATTESTATION = "By signing below, the owner and/or owner’s agent expressly acknowledges and agrees that the proposed alternative design, installation or process will provide an alternative that provides equal or better performance to the provisions of the Code, Standard, and/or regulation stated above.";
const roleLabel = (s: Pick<Signer, "role">) => s.role === "owner" ? "Owner" : "Owner’s representative";
const dateLabel = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });

/** The form's signature block: consent, then one signature per required signer. Nobody signs for anyone else. */
export function Sign({ workspace }: { workspace: WorkspaceController }) {
  const { saveDraft, readSync, refreshCurrentCase } = useCase();
  const { locked } = useCurrentApplication();
  const { state } = workspace;
  const [signer, setSigner] = useState<Signer | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const pending = useRef(false);
  const live = useRef({ locked });
  live.current = { locked };

  /** Save the draft first so the signature binds to exactly what was saved, then refresh both records. */
  async function write(operation: (id: string, signal: AbortSignal) => Promise<unknown>): Promise<boolean> {
    if (live.current.locked || pending.current) return false;
    pending.current = true;
    setBusy(true);
    setNote("");
    const signal = workspace.getSignal();
    try {
      await workspace.flushHistory();
      const id = await saveDraft();
      if (signal.aborted || live.current.locked) return false;
      if (!id || !readSync().saved) { setNote("Save your application before signing."); return false; }
      await operation(id, signal);
      if (signal.aborted) return false;
      await refreshCurrentCase();
      if (signal.aborted) return false;
      await workspace.reload();
      return true;
    } catch (e) {
      if (!signal.aborted) setNote(workspaceFailure(e, "Signing"));
      return false;
    } finally {
      pending.current = false;
      if (!signal.aborted) setBusy(false);
    }
  }

  if (state.phase !== "ready") {
    return (
      <div className="aw-scroll"><div className="aw-sign">
        <div className="aw-card aw-empty-card" role="status">
          <p>{state.note}</p>
          {state.phase === "failed" && <button type="button" className="cf-btn is-sm" onClick={workspace.retry}>Try again</button>}
        </div>
      </div></div>
    );
  }

  const { record } = state;
  const required = record.signers.filter(s => s.required);
  const isCurrent = (sig?: Signature) => sig?.current === true && workspace.signaturesCurrent;
  const agreed = record.consent?.agreed === true;
  const done = agreed && required.every(s => isCurrent(record.signatures.find(sig => sig.role === s.role)));

  return (
    <div className="aw-scroll"><div className="aw-sign">
      <h1 className="aw-title">Sign</h1>

      <div className="aw-card aw-consent">
        <label>
          <input type="checkbox" className="aw-check" checked={agreed} disabled={locked || busy}
            onChange={e => { const next = e.target.checked; void write((id, signal) => workspaceApi.consent(id, next, signal)); }} />
          <span>I agree to the described use of the information provided.</span>
        </label>
        <details>
          <summary>Read the disclosure</summary>
          <p>{DISCLOSURE}</p>
        </details>
      </div>

      {required.map(s => {
        const sig = record.signatures.find(saved => saved.role === s.role);
        const current = isCurrent(sig);
        const state = current ? "Signed" : sig ? "Changed since signed" : "Not signed";
        return (
          <section key={s.role} className="aw-card aw-signer" aria-label={`${roleLabel(s)} signature`}>
            <header>
              <div>
                <h2>{s.name || roleLabel(s)}</h2>
                <p>{roleLabel(s)}</p>
              </div>
              <span className={`aw-chip${current ? " is-done" : sig ? " is-warning" : ""}`}>
                <span className={`cf-dot is-${current ? "done" : sig ? "warning" : "pending"}`} aria-hidden="true" />{state}
              </span>
            </header>
            {sig ? (
              <div className={`aw-slot is-signed${current ? "" : " is-stale"}`}>
                <img src={sig.image} alt={`${roleLabel(s)}’s signature`} />
                <div className="aw-slot-line">
                  <span>{sig.name}</span>
                  <span className="aw-mono">{dateLabel(sig.signed_on)}</span>
                </div>
              </div>
            ) : (
              <button type="button" className="aw-slot" disabled={locked || busy} onClick={() => setSigner(s)}>
                <Icon24 name="sign" size={18} />Sign here
              </button>
            )}
            {sig && !locked && (
              <div className="aw-signer-actions">
                {!current && <span className="aw-hint">The application changed after this signature.</span>}
                <button type="button" className="cf-link-btn" disabled={busy} onClick={() => setSigner(s)}>Sign again</button>
                <button type="button" className="cf-link-btn" disabled={busy} onClick={() => void write((id, signal) => workspaceApi.remove(id, s.role, signal))}>Remove</button>
              </div>
            )}
          </section>
        );
      })}

      {note && <p className="aw-note" role="status">{note}<button type="button" className="cf-link-btn" onClick={() => { setNote(""); workspace.retry(); }}>Try again</button></p>}
      <p className="aw-fine">Professionals sign their own documents. Batatis never signs or seals for anyone.</p>
      <div className="aw-sign-foot">
        <a className={`cf-btn${done ? " is-primary" : ""}`} href="#/application?step=send">
          <Icon24 name="send" size={15} />Continue to Send
        </a>
      </div>

      {signer && (
        <SigningDialog key={signer.role} signer={signer} busy={busy} locked={locked} note={note}
          onClose={() => { if (!busy) setSigner(null); }}
          onSign={async body => { if (await write((id, signal) => workspaceApi.sign(id, signer.role, body, signal))) setSigner(null); }} />
      )}
    </div></div>
  );
}

function SigningDialog({ signer, busy, locked, note, onSign, onClose }: {
  signer: Signer; busy: boolean; locked: boolean; note: string; onClose: () => void;
  onSign: (body: { name: string; method: Signature["method"]; image: string }) => Promise<void>;
}) {
  const [method, setMethod] = useState<Signature["method"]>("drawn");
  const [name, setName] = useState(signer.name);
  const [hasInk, setHasInk] = useState(false);
  const [error, setError] = useState("");
  const canvas = useRef<HTMLCanvasElement>(null);
  const pointer = useRef<number | null>(null);
  const day = albertaDate();

  // Size the pad to its box at the device's pixel ratio; Type draws the printed name in a signature face.
  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    const frame = requestAnimationFrame(() => {
      const rect = el.getBoundingClientRect(), ratio = window.devicePixelRatio || 1;
      const w = Math.max(rect.width, 280), h = 160;
      el.width = Math.round(w * ratio);
      el.height = Math.round(h * ratio);
      const ctx = el.getContext("2d");
      if (!ctx) { setError("The signing pad isn’t available in this browser."); return; }
      ctx.scale(ratio, ratio);
      Object.assign(ctx, { lineWidth: 2.2, lineCap: "round", lineJoin: "round", strokeStyle: "#14161b", fillStyle: "#14161b" });
      if (method === "typed" && name.trim()) {
        ctx.font = 'italic 44px "Snell Roundhand", "Segoe Script", "Brush Script MT", cursive';
        ctx.fillText(name.trim(), 24, 100, w - 48);
        setHasInk(true);
      } else setHasInk(false);
    });
    return () => cancelAnimationFrame(frame);
  }, [method, name]);

  const at = (e: PointerEvent<HTMLCanvasElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  };
  function down(e: PointerEvent<HTMLCanvasElement>) {
    if (method !== "drawn" || busy || locked || pointer.current !== null) return;
    e.preventDefault();
    pointer.current = e.pointerId;
    e.currentTarget.setPointerCapture(e.pointerId);
    const ctx = e.currentTarget.getContext("2d"), p = at(e);
    if (!ctx) return;
    ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(p.x + 0.1, p.y + 0.1); ctx.stroke();
    setHasInk(true);
  }
  function move(e: PointerEvent<HTMLCanvasElement>) {
    if (pointer.current !== e.pointerId || method !== "drawn" || busy || locked) return;
    const p = at(e), ctx = e.currentTarget.getContext("2d");
    ctx?.lineTo(p.x, p.y);
    ctx?.stroke();
  }
  const up = () => { pointer.current = null; };
  function clear() {
    const el = canvas.current, ctx = el?.getContext("2d");
    if (el && ctx) { ctx.save(); ctx.resetTransform(); ctx.clearRect(0, 0, el.width, el.height); ctx.restore(); }
    setHasInk(false);
    setError("");
    if (method === "typed") setMethod("drawn");
  }
  async function sign() {
    if (busy || locked || !canvas.current || !name.trim()) return;
    try {
      setError("");
      await onSign({ name: name.trim(), method, image: signatureImage(canvas.current) });
    } catch (e) {
      setError(e instanceof Error ? e.message : "The signature wasn’t saved. Try again.");
    }
  }

  return (
    <Modal open onClose={onClose} labelledBy="aw-sign-title" className="aw-sign-dialog">
      <div className="cf-modal-body">
        <div className="aw-dialog-head">
          <h2 id="aw-sign-title" className="cf-modal-title">Sign as {roleLabel(signer).toLowerCase()}</h2>
          <button type="button" className="cf-icon-btn" aria-label="Close" title="Close" disabled={busy} onClick={onClose}><CIcon name="close" /></button>
        </div>
        <div className="aw-sign-fields">
          <label className="aw-field">
            <span>Printed name</span>
            <input value={name} maxLength={300} disabled={busy || locked} onChange={e => setName(e.target.value)} autoComplete="name" />
          </label>
          <div className="aw-field">
            <span>Date</span>
            <output className="aw-mono">{dateLabel(day)}</output>
          </div>
        </div>
        <div className="aw-seg" role="radiogroup" aria-label="How to sign">
          <button type="button" role="radio" aria-checked={method === "drawn"} disabled={busy} onClick={() => setMethod("drawn")}>Draw</button>
          <button type="button" role="radio" aria-checked={method === "typed"} disabled={busy || !name.trim()} onClick={() => setMethod("typed")}>Type</button>
        </div>
        <div className="aw-pad">
          <canvas ref={canvas} role="img" aria-label={method === "drawn" ? "Signature pad. Draw with a mouse, finger or pen, or choose Type." : "Your typed signature"}
            onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up} onLostPointerCapture={up} />
          <span className="aw-pad-x" aria-hidden="true">×</span>
          {!hasInk && method === "drawn" && <span className="aw-pad-hint" aria-hidden="true">Sign here</span>}
          {hasInk && <button type="button" className="aw-pad-clear" disabled={busy} onClick={clear}>Clear</button>}
        </div>
        <p className="aw-attest">{ATTESTATION}</p>
        {(error || note) && <p className="cf-hint" role="alert">{error || note}</p>}
      </div>
      <div className="cf-modal-foot">
        <button type="button" className="cf-btn" disabled={busy} onClick={onClose}>Cancel</button>
        <button type="button" className="cf-btn is-primary" disabled={busy || locked || !hasInk || !name.trim()} onClick={() => void sign()}>
          {busy ? "Saving…" : "Sign"}
        </button>
      </div>
    </Modal>
  );
}
