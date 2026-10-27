/** API-shaped unit fixtures only. No model, engine, network or applicant data is used. */
import { useState } from "react";
import { createRoot } from "react-dom/client";
import type { DocumentReview as Review, FileReport, IntakeRecord } from "../api/types.gen";
import { DocumentReview, type DocumentReviewProps } from "./DocumentReview";
import "./calm.css";

const proposed = { source_ref: "plans", page: 3, quote: "UNIT FIXTURE — Proposed projection: 450 mm.\nKeep this exact excerpt." };
const earlier = { source_ref: "reference", page: 2, quote: "UNIT FIXTURE — Previous proposal: 600 mm." };

const review = {
  status: "live", model: "unit-fixture", effort: null, reason: null,
  pages_sent: 5, input_tokens: 0, output_tokens: 0, dropped: 0,
  documents: [
    { file_id: "plans", kind: "drawing", title: "Unit proposal", author: "Fixture author", date: "2026-01-01", status: "Proposed" },
    { file_id: "reference", kind: "reference decision", title: "Unit reference", author: null, date: null, status: "Historical decision" },
  ],
  facts: [
    { status: "proposed", text: "The source proposes a 450 mm projection.", evidence: [proposed] },
    { status: "decided", text: "A reference project received a historical decision.", evidence: [{ ...earlier, quote: "UNIT FIXTURE — Reference project decision, not this project." }] },
    { status: "assumed", text: "The source assumes a dry location.", evidence: [{ source_ref: "description", page: null, quote: "UNIT FIXTURE — Assume a dry location." }] },
  ],
  flags: [
    { kind: "not_read", text: "UNIT FIXTURE — scan.pdf pages 1–2 were not read: no text layer.", evidence: [] },
    { kind: "outside_alberta", text: "The reference project is outside Alberta.", evidence: [{ ...earlier, quote: "UNIT FIXTURE — Reference project is in Ontario." }] },
    { kind: "code_edition", text: "The reference uses an earlier code edition.", evidence: [{ ...earlier, quote: "UNIT FIXTURE — NBC 2015, 9.9.8.2.(1)." }] },
  ],
  conflicts: [{ text: "The two sources state different projections.", evidence: [proposed, earlier] }],
  provisions: [
    { cited: "9.9.8.2.(1)", code: "NBC 2015", division: null, resolves_to: null, evidence: [{ ...earlier, quote: "UNIT FIXTURE — NBC 2015, 9.9.8.2.(1)." }] },
    { cited: "9.9.8.2.(1)", code: "NBC(AE) 2023, 2nd printing", division: "B", resolves_to: "9.9.8.2.", evidence: [{ ...proposed, quote: "UNIT FIXTURE — NBC(AE) 2023, 2nd printing: 9.9.8.2.(1)." }] },
  ],
  missing: [{ text: "Ask for supporting test documentation.", why: "Discuss the scope of evidence with the responsible professional." }],
  questions: [{ text: "Which projection is proposed for this project?", why: "Distinguish the current proposal from the reference." }],
} satisfies Review;

const report = (file_id: string, name: string, unread = false): FileReport => ({
  file_id, name, status: unread ? "not_read" : "read", reason: unread ? "No text layer" : null,
  pages: unread ? 2 : 3, pages_read: unread ? [] : [1, 2, 3], pages_not_read: unread ? [1, 2] : [],
  form: null, form_fields_read: 0, form_fields_skipped: [], facts: 0, project_pages: [],
});

function propsFor(value: Review | null): DocumentReviewProps {
  const record = {
    review: value, files: [report("plans", "proposal.pdf"), report("reference", "reference.pdf"), report("scan", "scan.pdf", true)],
    model: { status: "off", model: null, reason: null, pointed: 0, proposed: 0, dropped: 0, input_tokens: 0, output_tokens: 0 },
    pointers: [], conflicts: [], plan: null, ran_at: "2026-01-01T00:00:00Z", text_sha256: null, unresolved_citations: [],
  } satisfies IntakeRecord;
  const description = "UNIT FIXTURE — Assume a dry location.";
  return {
    description, intakeStatus: "done", intake: { text: description, record, factIds: [], facts: [] },
    files: record.files.map((file) => ({ id: file.file_id, engineId: file.file_id, name: file.name, read: true })),
  };
}

const unknown = structuredClone(review);
Reflect.set(unknown, "status", "future_status"); // Deliberately malformed runtime input.
const noFindings: Review = { ...review, facts: [], flags: [], conflicts: [], provisions: [], documents: [], missing: [], questions: [] };
const live = propsFor(review);
const longName = "UNIT-FIXTURE-" + "long-filename-".repeat(24) + ".pdf";
const long = propsFor({ ...review, facts: [{ ...review.facts[0], evidence: [{ ...proposed, quote: "x".repeat(400) + "<script>window.injected=true</script>" }] }] });
if (long.intake) long.intake.record.files[0].name = longName;
const unknownSource = propsFor({ ...review, facts: [{ ...review.facts[0], evidence: [{ ...proposed, source_ref: "unavailable-file" }] }] });

const fixtures = {
  live,
  failed: propsFor({ ...review, status: "failed" }),
  gate_closed: propsFor({ ...review, status: "gate_closed" }),
  off: propsFor({ ...review, status: "off" }),
  not_needed: propsFor({ ...review, status: "not_needed" }),
  fake: propsFor({ ...review, status: "fake" }),
  unknown: propsFor(unknown),
  no_review: propsFor(null),
  no_intake: { ...live, intake: undefined, intakeStatus: "idle" },
  reopened: { ...live, files: [] },
  unverified_input: { ...live, intake: live.intake && { ...live.intake, text: null } },
  empty: propsFor(noFindings),
  reading: { ...live, intakeStatus: "running" },
  intake_error: { ...live, intakeStatus: "error" },
  changed_description: { ...live, description: "UNIT FIXTURE — Edited input." },
  added_file: { ...live, files: [...live.files, { id: "new", name: "new.pdf", read: false }] },
  removed_file: { ...live, files: live.files.slice(0, 1) },
  removed_all_files: { ...live, files: [], intake: live.intake && { ...live.intake, filesChanged: true } },
  unknown_source: unknownSource,
  long,
} satisfies Record<string, DocumentReviewProps>;

function Fixture() {
  const [selected, setSelected] = useState("live");
  const current = Object.entries(fixtures).find(([key]) => key === selected)?.[1] ?? fixtures.live;
  return <div className="cf-app" style={{ flexDirection: "column" }}>
    <label style={{ padding: "12px 22px" }}>Unit fixture · document review <select aria-label="Unit fixture" value={selected} onChange={(event) => setSelected(event.target.value)}>
      {Object.keys(fixtures).map((name) => <option key={name}>{name}</option>)}
    </select></label>
    <main className="cf-main">
      <div className="cf-deck-page">
        <DocumentReview key={selected} {...current} />
        <div className="cf-q-stage"><div className="cf-q-wrap"><h2 className="cf-q-text">Unit fixture question</h2><p>Component fixture only; whole-app acceptance is separate.</p></div></div>
      </div>
    </main>
  </div>;
}

const target = document.getElementById("fixture");
if (target) createRoot(target).render(<Fixture />);
