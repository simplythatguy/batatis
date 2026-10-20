import { useRef, useState } from "react";
import { engine, failureText } from "../api/client";
import { ensureEngineCase } from "../api/sync";
import { DetailFields, FactLedger, QuestionChips } from "../case-parts";
import { DemoFallback, DraftNote, GapStrip, Icon, PanelHeader } from "../components";
import { applicantLabel } from "../intake";
import { DETAIL_FIELDS, factFor, valueText } from "../model";
import { useCase } from "../store";

let fileSeq = 0;
const fileId = () => `file-${Date.now().toString(36)}-${(fileSeq++).toString(36)}`;

function uploadMessage(e: unknown): string {
  const text = failureText(e);
  if (text.includes("no route")) return "The engine has no file upload route, so this PDF was not read.";
  if (text.includes("time")) return "The engine did not answer in time, so this PDF was not read.";
  return "The engine could not be reached, so this PDF was not read.";
}

function DropZone() {
  const { c, dispatch } = useCase();
  const input = useRef<HTMLInputElement>(null);
  const held = useRef(new Map<string, File>());
  const [over, setOver] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  async function transmit(id: string, name: string) {
    dispatch({ type: "setFileResult", id, error: null });
    setBusy(id);
    try {
      const caseId = await ensureEngineCase(c.title || "New application", c.authority);
      await engine.upload(caseId, name);
      dispatch({ type: "setFileResult", id, error: null, read: true });
    } catch (e) {
      dispatch({ type: "setFileResult", id, error: uploadMessage(e) });
    } finally {
      setBusy((cur) => (cur === id ? null : cur));
    }
  }

  function take(list: FileList | null) {
    if (!list) return;
    const all = [...list];
    const pdfs = all.filter((f) => f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf"));
    setError(pdfs.length < all.length ? "Only PDF files for now. Other formats were skipped." : "");
    const added = pdfs.map((file) => ({ id: fileId(), name: file.name, file }));
    if (!added.length) return;
    for (const item of added) held.current.set(item.id, item.file);
    dispatch({ type: "addFiles", files: added.map(({ id, name }) => ({ id, name })) });
    for (const item of added) void transmit(item.id, item.name);
  }

  return (
    <div className="drop-wrap">
      <div
        className="drop-zone"
        data-over={over}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          take(e.dataTransfer.files);
        }}
      >
        <Icon name="upload" size={16} />
        <span>Upload your plans (PDF). The file is sent to the engine. If that fails, you get an error and a retry.</span>
        <button type="button" className="btn" onClick={() => input.current?.click()}>
          Choose PDFs
        </button>
        <input
          ref={input}
          type="file"
          accept="application/pdf,.pdf"
          multiple
          hidden
          onChange={(e) => {
            take(e.target.files);
            e.target.value = "";
          }}
        />
      </div>
      {error && (
        <p className="field-note" role="status">
          <span className="status-dot warning" />
          {error}
        </p>
      )}
      {c.files.length > 0 && (
        <ul className="plain-list file-list" aria-label="Attached files">
          {c.files.map((f) => (
            <li key={f.id} className="file-row">
              <Icon name="file" />
              <span className="file-name" title={f.name}>{f.name}</span>
              <span className="meta file-state">
                {busy === f.id ? "Sending…" : f.read ? `Read · ${f.pages ?? "the"} file` : f.error ? "Not read" : "Sending…"}
              </span>
              <button
                type="button"
                className="btn btn-ghost btn-icon"
                aria-label={`Remove ${f.name}`}
                onClick={() => dispatch({ type: "removeFile", id: f.id })}
              >
                <Icon name="close" size={12} />
              </button>
              {f.error && (
                <div className="file-error">
                  <DemoFallback
                    reason={f.error}
                    onRetry={() => {
                      if (!held.current.has(f.id)) {
                        dispatch({
                          type: "setFileResult",
                          id: f.id,
                          error: "Choose the PDF again. It is not kept after a refresh.",
                        });
                        return;
                      }
                      void transmit(f.id, f.name);
                    }}
                  />
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function Describe() {
  const { c, gaps, gapsNote, dispatch, saveDraft } = useCase();
  const missingDetails = DETAIL_FIELDS.filter((d) => d.required && !valueText(factFor(c, d.id)).trim()).length;
  return (
    <>
      <PanelHeader title="What are you building?" meta={`${applicantLabel(c.applicantType)} · ${c.title}`} />
      <GapStrip gaps={gaps} />
      <div className="describe">
        <div className="describe-main pane">
          <div className="field">
            <label htmlFor="description" className="lead-label">
              What are you building?
            </label>
            <textarea
              id="description"
              className="describe-text"
              rows={5}
              value={c.description}
              onChange={(e) => dispatch({ type: "setDescription", text: e.target.value })}
              placeholder={
                c.applicantType === "manufacturer"
                  ? "Name the product and what it does differently from the acceptable solution."
                  : c.applicantType === "contractor"
                    ? "What are you building, and which requirement can you not follow as written?"
                    : "What house or suite are you building? Include storeys if you know them."
              }
            />
          </div>
          <div className="field">
            <label htmlFor="authority">Which authority will review this?</label>
            <select
              id="authority"
              value={c.authority}
              data-empty={!c.authority}
              onChange={(e) => dispatch({ type: "setAuthority", authority: e.target.value as typeof c.authority })}
            >
              <option value="">Select…</option>
              <option value="calgary">Calgary</option>
              <option value="edmonton">Edmonton</option>
            </select>
            <p className="field-note">Sent with the case when it is first saved. The engine has no route to change it later.</p>
          </div>
          <DropZone />
          <section aria-labelledby="missing-title">
            <div className="ledger-head">
              <h2 id="missing-title" className="section-title">
                What is missing
              </h2>
            </div>
            <p className="meta">{gapsNote}</p>
            {gaps.length ? (
              <ul className="plain-list gap-grid">
                {gaps.map((g) => (
                  <li key={g.id}>
                    <a className="gap-chip" href={g.href}>
                      <span className={`status-dot ${g.severity}`} />
                      {g.label}
                    </a>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="empty">Nothing in this list is open.</p>
            )}
          </section>
          <QuestionChips />
          <details className="disclosure">
            <summary>
              <Icon name="chevron" size={12} />
              <span className="disclosure-title">Applicant and site details</span>
              <span className="meta">Sections A and B · {missingDetails ? `${missingDetails} missing` : "complete"}</span>
            </summary>
            <p className="meta disclosure-hint">Filled only from your files or your typing. Batatis never guesses these.</p>
            <h3 className="sub-title">Section A · Applicant</h3>
            <DetailFields section="A" />
            <h3 className="sub-title">Section B · Project</h3>
            <DetailFields section="B" />
          </details>
        </div>
        <aside className="describe-side pane">
          <FactLedger />
        </aside>
      </div>
      <div className="footer-bar">
        <DraftNote />
        <button type="button" className="btn" onClick={() => void saveDraft()}>
          Save draft
        </button>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => {
            void saveDraft().then(() => {
              location.hash = "#/code-check";
            });
          }}
        >
          Continue to code check
        </button>
      </div>
    </>
  );
}
