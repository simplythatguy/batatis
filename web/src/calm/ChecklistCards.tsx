/**
 * Standing-package pieces for the deck (docs/api/checklists.md): the offer, one condition at a time
 * with its source wording behind a disclosure, and the tally with what to ask the office. A checklist
 * is the applicant's declaration; the officer decides. Never "complete", "passed" or "complies".
 */
import { useId, useState } from "react";
import type { CaseChecklist, CaseCondition } from "../api/types.gen";
import { askTheOffice, followedInFull, NOT_REVIEWED_PERSON, tallyLine } from "./checklistView";
import { CIcon, Dot } from "./ui";

/** Link to the checklist’s published source in a separate tab. */
function SourceLink({ cl }: { cl: CaseChecklist }) {
  return (
    <a className="cf-inline-link" href={cl.source.url} target="_blank" rel="noreferrer">
      {cl.source.title} <CIcon name="external" size={12} />
    </a>
  );
}

/** Quiet footer on package cards: the full notice on the offer and the tally, one short line per condition. */
function PackageFoot({ cl, short = false }: { cl: CaseChecklist; short?: boolean }) {
  return (
    <p className="cf-pkg-foot">
      {short ? "Your declaration, not a decision: the officer decides." : cl.notice} {!cl.reviewed && <span className="cf-faint">Checklist {NOT_REVIEWED_PERSON.toLowerCase()}</span>}
    </p>
  );
}

/** "Your city has a pre-reviewed path": what the standing package is, and where it was published. */
export function PackageOffer({ cl }: { cl: CaseChecklist }) {
  return (
    <div className="cf-pkg">
      <p className="cf-pkg-summary">{cl.summary}</p>
      <p className="cf-faint cf-small">
        {cl.conditions.length} conditions, one at a time. Published as <SourceLink cl={cl} />{cl.revision ? ` · ${cl.revision}` : ""} · issued {cl.issued}.
      </p>
      <PackageFoot cl={cl} />
    </div>
  );
}

/** The verbatim item behind a disclosure: label, page, the sentence it hangs from, and any figure. */
function SourceWording({ cl, row }: { cl: CaseChecklist; row: CaseCondition }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const s = row.source;
  return (
    <div className="cf-showcode">
      <button type="button" className="cf-link-btn cf-showcode-toggle" aria-expanded={open} aria-controls={id} onClick={() => setOpen((v) => !v)}>
        <CIcon name="doc" size={14} />{open ? "Hide the source wording" : "Source wording"}
      </button>
      {open && (
        <div id={id} className="cf-codebox">
          <div className="cf-codebox-head">
            <span className="cf-mono">{cl.code}{s.label ? ` ${s.label}` : ""}</span>
            <span className="cf-codebox-title">page {s.page}</span>
          </div>
          {s.lead_in && <p className="cf-faint cf-small">{s.lead_in}</p>}
          <blockquote className="cf-code-text">{s.quote}</blockquote>
          {s.diagram && <p className="cf-faint cf-small">Shown in the figure: {s.diagram}</p>}
          <div className="cf-code-src"><SourceLink cl={cl} /></div>
        </div>
      )}
    </div>
  );
}

/** One condition: progress, the choices (from the deck), a reason for "does not apply", and the source. */
export function ConditionBody({ cl, row, position, children, reasonOpen, reason, setReason, note, busy, onReload }: {
  cl: CaseChecklist;
  row: CaseCondition;
  position: number;
  children: React.ReactNode;
  reasonOpen: boolean;
  reason: string;
  setReason: (v: string) => void;
  note: string;
  busy: boolean;
  onReload?: () => void;
}) {
  const id = useId();
  const quick = row.when ? "It isn’t part of my project." : "";
  return (
    <div className="cf-pkg">
      <p className="cf-pkg-progress" aria-label={`Condition ${position} of ${cl.conditions.length}`}>
        <span className="cf-pkg-bar" aria-hidden="true"><i style={{ width: `${Math.round((100 * (cl.counts.total - cl.counts.unanswered)) / Math.max(cl.counts.total, 1))}%` }} /></span>
        <span className="cf-faint">Condition {position} of {cl.conditions.length} · {tallyLine(cl)}</span>
      </p>
      {children}
      {reasonOpen && (
        <div className="cf-pkg-reason">
          <label className="cf-small" htmlFor={id}>Why doesn’t it apply? A short reason is enough.</label>
          <textarea id={id} className="cf-uline is-area" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="For example: there is no balcony on that side." />
          {quick && !reason.trim() && <button type="button" className="cf-chip" onClick={() => setReason(quick)}>{quick}</button>}
        </div>
      )}
      {row.answer?.state === "does_not_apply" && row.answer.reason && !reasonOpen && <p className="cf-note"><Dot tone="pending" />Does not apply: {row.answer.reason}</p>}
      {row.answer?.state === "not_yet" && <p className="cf-note"><Dot tone="warning" />Not yet. Until it is, the package is not followed in full.</p>}
      {busy && <p className="cf-note" role="status"><Dot tone="pending" />Saving your answer…</p>}
      {!busy && note && (
        <p className="cf-note" role="alert">
          <Dot tone="warning" />{note}
          {onReload && <> <button type="button" className="cf-link-btn" onClick={onReload}>Reload and answer again</button></>}
        </p>
      )}
      <SourceWording cl={cl} row={row} />
      <PackageFoot cl={cl} short />
    </div>
  );
}

/** After the last condition: the tally, what to ask the office, and the source. */
export function PackageEnd({ cl }: { cl: CaseChecklist }) {
  const ask = askTheOffice(cl);
  const warn = cl.source_notes.filter((n) => n.kind === "warning");
  return (
    <div className="cf-pkg">
      {!followedInFull(cl) && <p className="cf-note"><Dot tone="warning" />A condition marked Not yet, or one left unanswered, means the package is not yet followed in full.</p>}
      {ask.length > 0 && (
        <section className="cf-pkg-ask" aria-labelledby="cf-pkg-ask-h">
          <h3 id="cf-pkg-ask-h" className="cf-list-label">Ask the office</h3>
          <ul>
            {ask.map((n) => <li key={n.id}>{n.plain} <span className="cf-faint">(page {n.page})</span></li>)}
          </ul>
        </section>
      )}
      {warn.map((n) => <p key={n.id} className="cf-faint cf-small">{n.plain}</p>)}
      <p className="cf-faint cf-small">Source: <SourceLink cl={cl} /></p>
      <PackageFoot cl={cl} />
    </div>
  );
}
