import { useState } from "react";
import { AUTHORITIES } from "../config";
import { UPLOAD_UPFRONT } from "../rules";
import { DetailFields, FactLedger, QuestionChips } from "../case-parts";
import { DraftNote, GapStrip, Icon, PanelHeader, RoleNote } from "../components";
import { applicantLabel } from "../intake";
import { DETAIL_FIELDS, factFor, valueText } from "../model";
import { useCase } from "../store";

function PastePlans() {
  const { c, dispatch } = useCase();
  const [text, setText] = useState("");
  const [note, setNote] = useState("");
  return (
    <div className="field">
      <p className="field-note" role="status">
        {UPLOAD_UPFRONT}
      </p>
      <label htmlFor="paste-plans">Paste text from your plans</label>
      <textarea id="paste-plans" rows={4} value={text} onChange={(e) => setText(e.target.value)} />
      <button
        type="button"
        className="btn"
        disabled={!text.trim()}
        onClick={() => {
          const next = [c.description.trim(), text.trim()].filter(Boolean).join("\n\n");
          dispatch({ type: "setDescription", text: next });
          setText("");
          setNote("Added to your description.");
        }}
      >
        Add this text
      </button>
      {note && <p className="meta">{note}</p>}
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
          <RoleNote />
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
              {AUTHORITIES.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
            <p className="field-note">Nothing is sent until you pick. You can change it later.</p>
          </div>
          <PastePlans />
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
