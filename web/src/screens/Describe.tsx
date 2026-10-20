import { useRef, useState } from "react";
import { DetailFields, FactLedger, QuestionChips } from "../case-parts";
import { Icon, PanelHeader } from "../components";
import { DETAIL_FIELDS, factFor, valueText } from "../model";
import { useCase } from "../store";

function DropZone() {
  const { c, dispatch } = useCase();
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [error, setError] = useState("");

  function take(list: FileList | null) {
    if (!list) return;
    const all = [...list];
    const pdfs = all.filter((f) => f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf"));
    setError(pdfs.length < all.length ? "Only PDF files for now. Other formats were skipped." : "");
    if (pdfs.length) dispatch({ type: "addFiles", names: pdfs.map((f) => f.name) });
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
        <span>Drop PDFs: drawings, product literature, test reports, a filled SCC form</span>
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
              <span className="meta file-state">{f.read ? `Read · ${f.pages} pages` : "Listed, not read yet"}</span>
              <button
                type="button"
                className="btn btn-ghost btn-icon"
                aria-label={`Remove ${f.name}`}
                onClick={() => dispatch({ type: "removeFile", id: f.id })}
              >
                <Icon name="close" size={12} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function Describe() {
  const { c, dispatch } = useCase();
  const missingDetails = DETAIL_FIELDS.filter((d) => d.required && !valueText(factFor(c, d.id)).trim()).length;
  const toCheck = c.facts.filter((f) => f.status === "unconfirmed").length;
  return (
    <>
      <PanelHeader title="Describe" />
      <div className="pane scroll-body">
        <div className="column stack-8">
          <div className="field">
            <label htmlFor="description" className="lead-label">
              Describe your idea in a sentence or two
            </label>
            <textarea
              id="description"
              className="describe-text"
              rows={4}
              autoComplete="off"
              value={c.description}
              onChange={(e) => dispatch({ type: "setDescription", text: e.target.value })}
              placeholder="What are you building or selling, and what does it do differently?"
            />
          </div>
          <DropZone />
          <FactLedger />
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
      </div>
      <div className="footer-bar">
        <span className="status-note" role="status">
          Saved in this browser{toCheck ? ` · ${toCheck} fact${toCheck > 1 ? "s" : ""} still need you. You can come back.` : ""}
        </span>
        <a className="btn btn-primary" href="#/code-check">
          Continue to code check
        </a>
      </div>
    </>
  );
}
