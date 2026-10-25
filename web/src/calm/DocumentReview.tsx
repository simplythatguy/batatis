import type { ReactNode } from "react";
import type { DocumentReview as Review, EvidenceRef, ReviewFact, ReviewFlag } from "../api/types.gen";
import { CODE_EDITION } from "../config";
import type { Reading } from "../store";
import type { Case } from "../types";
import { Icon24 } from "./icons";
import { CIcon } from "./ui";
import "./DocumentReview.css";

export type DocumentReviewProps = Pick<Case, "intake" | "files" | "description"> & {
  intakeStatus: Reading["intake"];
};

const STATES = {
  live: { label: "Model checked", note: "Source findings are not applicant-confirmed project answers." },
  fake: { label: "Test output", note: "Test output only. No live document review was run." },
  off: { label: "Off", note: "Document review was turned off for this intake." },
  gate_closed: { label: "Unavailable", note: "Document review could not run for this intake. No model findings are available." },
  failed: { label: "Failed", note: "Document review failed for this intake. No model findings are available." },
  not_needed: { label: "Not run", note: "No document review was needed for this intake. No model findings are available." },
} satisfies Record<Review["status"], { label: string; note: string }>;

const FACT_STATUS = {
  stated: "Stated", existing: "Existing", proposed: "Proposed", assumed: "Assumed",
  decided: "Decision reported", argued: "Argument", condition: "Condition",
  recommended: "Recommended", tested: "Test reported",
} satisfies Record<ReviewFact["status"], string>;

const FLAG_KIND = {
  outside_alberta: "Outside Alberta", code_edition: "Code edition", other_discipline: "Other discipline",
  record_status: "Record status", outcome_known: "Reported outcome", not_read: "Not read",
} satisfies Record<ReviewFlag["kind"], string>;

function Group({ label, count, children, open = false }: { label: string; count: number; children: ReactNode; open?: boolean }) {
  if (!count) return null;
  return (
    <details className="cf-doc-group" open={open}>
      <summary><span>{label}</span><span className="cf-doc-count">{count}</span><Icon24 name="down" size={14} /></summary>
      {children}
    </details>
  );
}

function Sources({ evidence, nameFor, compare = false }: { evidence: EvidenceRef[]; nameFor: (ref: string) => string; compare?: boolean }) {
  if (!evidence.length) return <p className="cf-doc-meta">No source excerpt supplied.</p>;
  return (
    <details className="cf-doc-sources">
      <summary><CIcon name="doc" size={14} />{compare ? "Compare sources" : "Sources"}<span className="cf-doc-count">{evidence.length}</span></summary>
      {evidence.map((source, i) => (
        <figure key={i}>
          <figcaption>{nameFor(source.source_ref)}{source.page !== null && ` · p. ${source.page}`}</figcaption>
          <blockquote>{source.quote}</blockquote>
        </figure>
      ))}
    </details>
  );
}

/** Read-only source findings. Confirmation cards and the shared completeness gaps stay authoritative. */
export function DocumentReview({ intake, files, description, intakeStatus }: DocumentReviewProps) {
  const record = intake?.record;
  const review = record?.review;
  const pending = intakeStatus === "running";
  const failedIntake = intakeStatus === "error";
  // Reopened cases can omit browser file metadata; the intake record still holds the source names.
  const unverifiedInput = intake?.text === null;
  const outdated = Boolean(intake && (intake.filesChanged || (intake.text !== null && intake.text !== description.trim())
    || files.some((file) => !record?.files.some((report) => report.file_id === file.engineId))
    || (files.length > 0 && record?.files.some((report) => !files.some((file) => file.engineId === report.file_id)))));
  const state = pending
    ? { label: "Reading…", note: "The current intake is still reading. Document findings are not available yet." }
    : failedIntake
      ? { label: "Unavailable", note: "Intake did not finish. A document review of the current input is unavailable." }
      : outdated
        ? { label: "Previous input", note: "These findings belong to an earlier description or file list." }
        : unverifiedInput
          ? { label: "Input unverified", note: "The saved review cannot be matched to this description. Read the input again before using its findings." }
        : review
          ? Object.hasOwn(STATES, review.status) ? STATES[review.status] : { label: "Unknown", note: "The document review status is unknown. These findings cannot be shown as model checked." }
          : { label: "Not available", note: "No document review is attached to this intake." };
  const available = !pending && !failedIntake;
  const findings = available && (review?.status === "live" || review?.status === "fake") ? review : null;
  const flags = !available ? [] : findings ? findings.flags
    : review?.status === "failed" || review?.status === "gate_closed"
      ? review.flags.filter((flag) => flag.kind === "not_read") : [];
  const reports = available ? record?.files ?? [] : [];
  const unread = flags.some((flag) => flag.kind === "not_read") || reports.some((report) => report.status !== "read");
  const fileIds = [...new Set([...reports.map((report) => report.file_id), ...(findings?.documents.map((doc) => doc.file_id) ?? [])])];
  const hasFindings = findings && [findings.facts, flags, findings.conflicts, findings.provisions, findings.missing, findings.questions, findings.documents].some((items) => items.length);
  const nameFor = (ref: string) => ref === "description" ? "Your description"
    : record?.files.find((file) => file.file_id === ref)?.name
      ?? files.find((file) => file.engineId === ref)?.name
      ?? `Unknown source (${ref})`;

  return (
    <details className="cf-document-review">
      <summary className="cf-doc-heading">
        <span className="cf-doc-title"><Icon24 name="file" size={16} />Document review</span>
        <span className="cf-doc-meta">{state.label}</span>
        {unread && <span className="cf-doc-caution"><CIcon name="warn" size={14} />Unread content</span>}
        {flags.length > 0 && <span className="cf-doc-meta" aria-label={`${flags.length} flags`} title={`${flags.length} flags`}><CIcon name="info" size={14} />{flags.length}</span>}
        <Icon24 name="down" size={14} />
      </summary>
      <div className="cf-doc-body" role="region" aria-label="Document review findings" tabIndex={0}>
        <p className="cf-doc-notice" role="status">{state.note}</p>
        <p className="cf-doc-meta">Administrative completeness only; not a design approval.</p>
        {hasFindings && <p className="cf-doc-meta">Findings about reference projects and reported outcomes remain source information.</p>}
        {findings && !hasFindings && <p className="cf-doc-notice">No findings were returned. This does not establish that the documents or application are complete.</p>}

        <Group label="Flags" count={flags.length} open>
          <ul className="cf-doc-list">
            {flags.map((flag, i) => <li key={i}>
              <span className="cf-doc-tag">{FLAG_KIND[flag.kind] ?? "Flag"}</span>
              <p>{flag.text}</p>
              <Sources evidence={flag.evidence} nameFor={nameFor} />
            </li>)}
          </ul>
        </Group>

        <Group label="Source facts" count={findings?.facts.length ?? 0} open>
          <ul className="cf-doc-list">
            {findings?.facts.map((fact, i) => <li key={i}>
              <span className="cf-doc-tag">{FACT_STATUS[fact.status] ?? "Source statement"}</span>
              <p>{fact.text}</p>
              <Sources evidence={fact.evidence} nameFor={nameFor} />
            </li>)}
          </ul>
        </Group>

        <Group label="Conflicts" count={findings?.conflicts.length ?? 0}>
          <ul className="cf-doc-list">
            {findings?.conflicts.map((conflict, i) => <li key={i}>
              <p>{conflict.text}</p>
              <Sources evidence={conflict.evidence} nameFor={nameFor} compare />
            </li>)}
          </ul>
        </Group>

        <Group label="Cited provisions" count={findings?.provisions.length ?? 0}>
          <p className="cf-doc-meta">Number lookup only; applicability still needs confirmation in Section C.</p>
          <ul className="cf-doc-list">
            {findings?.provisions.map((provision, i) => <li key={i}>
              <p className="cf-doc-citation">{provision.cited}</p>
              <dl className="cf-doc-properties">
                <dt>Source edition</dt><dd>{provision.code ?? "Not stated"}</dd>
                <dt>Alberta lookup</dt><dd>{provision.resolves_to
                  ? `${CODE_EDITION} · ${provision.division ? `Div. ${provision.division} · ` : ""}${provision.resolves_to}`
                  : `No match established in ${CODE_EDITION}`}</dd>
              </dl>
              <Sources evidence={provision.evidence} nameFor={nameFor} />
            </li>)}
          </ul>
        </Group>

        <Group label="Evidence to request" count={findings?.missing.length ?? 0}>
          <p className="cf-doc-meta">Model suggestions; these do not add blocking gaps. Professional analysis must come from your engineer or architect.</p>
          <ul className="cf-doc-list">
            {findings?.missing.map((item, i) => <li key={i}><p>{item.text}</p>{item.why && <p className="cf-doc-meta">{item.why}</p>}</li>)}
          </ul>
        </Group>

        <Group label="Next questions" count={findings?.questions.length ?? 0}>
          <p className="cf-doc-meta">Model suggestions; these do not add blocking gaps.</p>
          <ul className="cf-doc-list">
            {findings?.questions.map((item, i) => <li key={i}><p>{item.text}</p>{item.why && <p className="cf-doc-meta">{item.why}</p>}</li>)}
          </ul>
        </Group>

        <Group label="Documents" count={fileIds.length}>
          <p className="cf-doc-meta">Text extraction coverage is separate from model review. Any unread review pages are flagged above.</p>
          <ul className="cf-doc-list">
            {fileIds.map((id) => {
              const report = reports.find((file) => file.file_id === id);
              const doc = findings?.documents.find((file) => file.file_id === id);
              return <li key={id}>
                <p className="cf-doc-filename">{nameFor(id)}</p>
                {doc && <p className="cf-doc-meta">{[doc.title, doc.kind, doc.author, doc.date, doc.status].filter(Boolean).join(" · ")}</p>}
                <p>Text extraction: {report ? { read: "Read", partly_read: "Partly read", not_read: "Not read" }[report.status] : "Not reported"}</p>
                {report?.reason && <p>{report.reason}</p>}
                {Boolean(report?.pages_read.length) && <p className="cf-doc-meta">Text pages read: {report?.pages_read.join(", ")}</p>}
                {Boolean(report?.pages_not_read.length) && <p>Pages not read: {report?.pages_not_read.join(", ")}</p>}
              </li>;
            })}
          </ul>
        </Group>
      </div>
    </details>
  );
}
