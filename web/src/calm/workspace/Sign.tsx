import { useEffect, useRef, useState, type PointerEvent } from "react";
import { useCase } from "../../store";
import { useCurrentApplication } from "../begin";
import { Icon24 } from "../icons";
import { CIcon, Dot, Modal } from "../ui";
import { workspaceApi, workspaceFailure, type Signer, type Signature } from "./api";
import { albertaDate, signatureImage } from "./signature";
import type { WorkspaceController } from "./useWorkspace";

/** Transcribed from challenge_2026-09-15.pdf, page 2, Signatures and Disclosures. */
export const DISCLOSURE = "The collection of personal information is authorized under section 4(c) of the Protection of Privacy Act. This personal information will be used to review and assess the variance application, including verifying information provided. I understand that the information provided will be shared with the Safety Codes Council in accordance with the municipality's Quality Management System agreement. The following information may also be published on the Safety Codes Council website under section of the Protection of Privacy Act: permit number, municipality, issue date and completion date, permit type, project type, work class, address, description of the project, total square footage, and project value range. By checking this box, I acknowledge and agree to the described use of the information provided.";
export const ATTESTATION = "By signing below, the owner and/or owner’s agent expressly acknowledges and agrees that the proposed alternative design, installation or process will provide an alternative that provides equal or better performance to the provisions of the Code, Standard, and/or regulation stated above.";
const roleLabel = (s: Signer) => s.role === "owner" ? "Owner" : "Owner’s representative";

export function Sign({ workspace }: { workspace: WorkspaceController }) {
  const { saveDraft, readSync, refreshCurrentCase } = useCase();
  const { locked } = useCurrentApplication();
  const { state } = workspace;
  const [signer, setSigner] = useState<Signer | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const pending = useRef(false);
  const live = useRef({ locked, workspace });
  live.current = { locked, workspace };

  async function write(operation: (id: string, signal: AbortSignal) => Promise<unknown>): Promise<boolean> {
    if (live.current.locked || pending.current) return false;
    pending.current = true; setBusy(true); setNote("");
    const signal = workspace.getSignal();
    try {
      await workspace.flushHistory();
      const id = await saveDraft();
      if (signal.aborted || live.current.locked) return false;
      if (!id || !readSync().saved) { setNote("Save your application before signing."); return false; }
      await operation(id, signal);
      if (signal.aborted) return false;
      // The workspace write may advance the saved version; refresh through the store's guarded seam.
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

  return <div className="aw-step-scroll"><div className="aw-sign">
    <h1 className="aw-step-title">Signatures and disclosures</h1>
    {state.phase !== "ready" ? <div className="aw-card" role="status"><p>{state.note}</p>{state.phase === "failed" && <button type="button" className="cf-btn is-sm" onClick={workspace.retry}>Try again</button>}</div> : <>
      <div className="aw-card aw-consent">
        <label className="aw-check-label"><input type="checkbox" checked={state.record.consent?.agreed === true} disabled={locked || busy}
          onChange={e => { const agreed = e.target.checked; void write((id, signal) => workspaceApi.consent(id, agreed, signal)); }} />
          <span>I acknowledge and agree to the described use of the information provided.</span>
        </label>
        <details><summary>Read the disclosure</summary><p>{DISCLOSURE}</p></details>
      </div>
      {state.record.signers.filter(s => s.required).map(s => {
        const signature = state.record.signatures.find(saved => saved.role === s.role);
        const current = signature?.current === true && workspace.signaturesCurrent;
        return <section className="aw-card aw-signer" key={s.role} aria-label={`${roleLabel(s)} signature`}>
          <div><h2>{s.name || roleLabel(s)}</h2><p className="cf-faint cf-small">{roleLabel(s)}</p></div>
          <span className="aw-sign-state"><Dot tone={current ? "done" : signature ? "warning" : "pending"} />{current ? "Signed" : signature ? "Changed since signed" : "Unsigned"}</span>
          {signature && <div className={`aw-saved-signature${current ? "" : " is-stale"}`}><img src={signature.image} alt={`${roleLabel(s)}’s signature`} /><span>{signature.name} · {signature.signed_on}</span></div>}
          {!locked && <div className="aw-signer-actions"><button type="button" className="cf-btn is-sm" disabled={busy} onClick={() => setSigner(s)}><Icon24 name="pencil" size={15} />{signature ? "Sign again" : "Sign here"}</button>
            {signature && <button type="button" className="cf-btn is-ghost is-sm" disabled={busy} onClick={() => void write((id, signal) => workspaceApi.remove(id, s.role, signal))}>Remove</button>}
          </div>}
        </section>;
      })}
      {state.record.signers.every(s => !s.required) && <p className="cf-faint">No signer requirements were returned. Review the applicant details.</p>}
    </>}
    {note && <p className="cf-hint" role="status">{note} <button type="button" className="cf-link-btn" onClick={() => { setNote(""); workspace.retry(); }}>Try again</button></p>}
    {locked && <p className="cf-faint cf-small">This application is read-only.</p>}
    <p className="cf-faint cf-small">Professionals sign their own documents. Batatis never signs or seals for them.</p>
    <a className="cf-btn is-ghost aw-next" href="#/application?step=send">Review package <CIcon name="arrow" size={14} /></a>
    {signer && <SigningDialog key={signer.role} signer={signer} busy={busy} locked={locked} note={note} onClose={() => { if (!busy) setSigner(null); }} onSign={async body => {
      const saved = await write((id, signal) => workspaceApi.sign(id, signer.role, body, signal));
      if (saved) setSigner(null);
    }} />}
  </div></div>;
}

function SigningDialog({ signer, busy, locked, note, onSign, onClose }: {
  signer: Signer; busy: boolean; locked: boolean; note: string; onClose: () => void;
  onSign: (body: { name: string; method: Signature["method"]; image: string }) => Promise<void>;
}) {
  const [method, setMethod] = useState<Signature["method"]>("drawn");
  const [name, setName] = useState(signer.name);
  const [typed, setTyped] = useState(signer.name);
  const [hasInk, setHasInk] = useState(false);
  const [error, setError] = useState("");
  const canvas = useRef<HTMLCanvasElement>(null);
  const pointer = useRef<number | null>(null);
  const day = albertaDate();

  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    const frame = requestAnimationFrame(() => {
      const rect = el.getBoundingClientRect(), ratio = window.devicePixelRatio || 1;
      el.width = Math.round(Math.max(rect.width, 280) * ratio); el.height = Math.round(150 * ratio);
      const ctx = el.getContext("2d");
      if (!ctx) { setError("The signing pad isn’t available in this browser."); return; }
      ctx.scale(ratio, ratio); ctx.lineWidth = 2; ctx.lineCap = "round"; ctx.lineJoin = "round"; ctx.strokeStyle = "#14161b"; ctx.fillStyle = "#14161b";
      if (method === "typed" && typed.trim()) {
        ctx.font = 'italic 42px "Brush Script MT", "Segoe Script", cursive';
        ctx.fillText(typed.trim(), 18, 98, Math.max(rect.width, 280) - 36);
        setHasInk(true);
      } else setHasInk(false);
    });
    return () => cancelAnimationFrame(frame);
  }, [method, typed]);

  function point(e: PointerEvent<HTMLCanvasElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }
  function start(e: PointerEvent<HTMLCanvasElement>) {
    if (method !== "drawn" || busy || locked || pointer.current !== null) return;
    e.preventDefault(); pointer.current = e.pointerId; e.currentTarget.setPointerCapture(e.pointerId);
    const ctx = e.currentTarget.getContext("2d"), p = point(e);
    if (!ctx) return;
    ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(p.x + .1, p.y + .1); ctx.stroke(); setHasInk(true);
  }
  function draw(e: PointerEvent<HTMLCanvasElement>) {
    if (pointer.current !== e.pointerId || method !== "drawn" || busy || locked) return;
    const p = point(e), ctx = e.currentTarget.getContext("2d");
    ctx?.lineTo(p.x, p.y); ctx?.stroke();
  }
  function clear() {
    const el = canvas.current;
    if (!el) return;
    const ctx = el.getContext("2d");
    if (ctx) { ctx.save(); ctx.resetTransform(); ctx.clearRect(0, 0, el.width, el.height); ctx.restore(); }
    setTyped(""); setHasInk(false); setError("");
  }
  async function sign() {
    if (busy || locked || !canvas.current || !name.trim()) return;
    try { setError(""); await onSign({ name: name.trim(), method, image: signatureImage(canvas.current) }); }
    catch (e) { setError(e instanceof Error ? e.message : "The signature wasn’t saved. Try again."); }
  }
  return <Modal open onClose={onClose} labelledBy="aw-sign-title" className="aw-sign-dialog">
    <div className="cf-modal-body">
      <div className="aw-dialog-head"><h2 id="aw-sign-title" className="cf-modal-title">Sign as {roleLabel(signer).toLowerCase()}</h2><button type="button" className="cf-icon-btn" title="Close" aria-label="Close signing dialog" disabled={busy} onClick={onClose}><CIcon name="close" /></button></div>
      <p className="cf-faint cf-small">Date · {day} · Alberta</p>
      <label className="aw-input-label">Printed name<input value={name} maxLength={300} disabled={busy || locked} onChange={e => setName(e.target.value)} autoComplete="name" /></label>
      <div className="aw-sign-modes" aria-label="Signature method"><button type="button" aria-pressed={method === "drawn"} disabled={busy} onClick={() => setMethod("drawn")}>Draw</button><button type="button" aria-pressed={method === "typed"} disabled={busy} onClick={() => setMethod("typed")}>Type</button></div>
      {method === "typed" && <label className="aw-input-label">Type your signature<input value={typed} maxLength={300} disabled={busy || locked} onChange={e => setTyped(e.target.value)} autoComplete="off" /></label>}
      <canvas ref={canvas} className="aw-sign-pad" aria-label={method === "drawn" ? "Draw your signature here, or choose Type" : "Your typed signature"} role="img" onPointerDown={start} onPointerMove={draw}
        onPointerUp={() => { pointer.current = null; }} onPointerCancel={() => { pointer.current = null; }} onLostPointerCapture={() => { pointer.current = null; }} />
      <button type="button" className="cf-link-btn" disabled={busy} onClick={clear}>Clear signature</button>
      <p className="aw-attestation">{ATTESTATION}</p>
      {(error || note) && <p className="cf-hint" role="alert">{error || note}</p>}
    </div>
    <div className="cf-modal-foot"><button type="button" className="cf-btn" disabled={busy} onClick={onClose}>Cancel</button><button type="button" className="cf-btn is-primary" disabled={busy || locked || !hasInk || !name.trim()} onClick={() => void sign()}>{busy ? "Saving…" : "Sign"}</button></div>
  </Modal>;
}
