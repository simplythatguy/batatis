import type { Case } from "../../api/types.gen";
import { sentLabel } from "./queue";
import { visibleSubmissionChanges } from "./submissionChanges";

const LABELS: Record<string, string> = {
  legal_description: "Legal description", legalDescription: "Legal description", owner_name: "Owner", owner: "Owner",
  civic_address: "Municipal address", municipalAddress: "Municipal address", application_date: "Application date",
  alternative_description: "Proposed alternative", mailing_address: "Mailing address", provisions: "Code references",
};
const decisionLabel = (outcome: string) => ({ return: "Returned", accept: "Accepted as administratively complete", refuse: "Refused" })[outcome] ?? "Decision recorded";
const label = (field: string, c: Case) => {
  if (field.startsWith("clarification.")) return "Applicant clarification";
  if (field.startsWith("codecheck.")) return "Applicant code check answer";
  if (field.startsWith("identify.")) return "Applicant code question answer";
  const document = /^evidence\.([^.]+)\.(?:listing\.)?(.*)$/.exec(field);
  if (document) {
    const title = [...c.facts].reverse().find(fact => fact.field === `evidence.${document[1]}.title`)?.value;
    const attribute = document[2] === "file_ref" ? "attachment" : document[2].replace(/_/g, " ");
    return `${title || "Document"} · ${attribute}`;
  }
  return LABELS[field] ?? field.replace(/^process\./, "").replace(/_/g, " ").replace(/([a-z])([A-Z])/g, "$1 $2");
};

/** Stored deltas describe edits; they never say an officer's requested item was resolved. */
export function SubmissionHistory({ c }: { c: Case }) {
  const latest = c.submissions?.at(-1);
  const changes = visibleSubmissionChanges(latest?.changes ?? []);
  const number = c.submission_number ?? latest?.number ?? 0;
  const decisions = c.decision_history?.length ? c.decision_history : c.decision ? [c.decision] : [];
  if (!number && !decisions.length) return null;
  return <section className="ac-side-sec" aria-label="Submission history">
    <h3 className="ac-side-h">{number > 1 ? `Resubmitted · submission ${number}` : "First submission"}</h3>
    {number > 1 && <>
      <p className="ac-faint ac-small">Changed since the return{latest?.returned_at ? ` on ${sentLabel(latest.returned_at)}` : ""}</p>
      {!latest?.comparison_available
        ? <p className="ac-faint ac-small">No comparison for this return</p>
        : changes.length === 0
          ? <p className="ac-faint ac-small">Nothing changed since the return</p>
          : <details>
            <summary className="ac-small">{changes.length} changed {changes.length === 1 ? "item" : "items"}</summary>
            <dl className="ac-small">
              {changes.map(change => <div key={change.field}>
                <dt>{label(change.field, c)}</dt>
                <dd>{change.field.endsWith(".file_ref")
                  ? change.before && change.after ? "The attached file was replaced." : change.after ? "A file was attached." : "The file attachment was removed."
                  : <>Before: {change.before || "—"}<br />Now: {change.after || "—"}</>}</dd>
              </div>)}
            </dl>
          </details>}
    </>}
    {decisions.length > 0 && <details>
      <summary className="ac-small">Decisions · {decisions.length}</summary>
      {decisions.map((decision, index) => <div key={`${decision.at}-${index}`} className="ac-small">
        <p>{decisionLabel(decision.outcome)} · {decision.by_name} · {sentLabel(decision.at)}</p>
      </div>)}
    </details>}
  </section>;
}
