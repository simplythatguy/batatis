import assert from "node:assert/strict";
import test from "node:test";
import type { FieldReading, Finding, InputFile, Pointer, OfficerWorkspace, ReviewSession } from "../../api/types.gen.ts";
import { changeLabel, formValue } from "./formFields.ts";
import type { SheetView } from "./sheet.ts";
import { visibleSubmissionChanges } from "./submissionChanges.ts";
import { allAnchors, anchoredItems, anchorFor, changedFields, findingSources, localTally, sheetRows, sinceReturn, targetOptions, visibleFinding, withThe, workspaceDecision, type SheetAnchor } from "./workspaceView.ts";

const anchors: SheetAnchor[] = [
  { id: "owner", section: "A", field: "owner_name", label: "Owner" },
  { id: "risk", section: "process", field: "process.risk_assessment", label: "Risk assessment" },
  { id: "ref", section: "C", field: "section_c.9.10.9.16.(1)", label: "9.10.9.16.(1)" },
  { id: "doc", section: "D", field: "evidence.report", label: "Test report" },
];
const workspace: OfficerWorkspace = { version: 3, case_version: 9, current: true, states: [], rulebook: [],
  tally: { required: 7, to_check: 2, dismissed: 4, asked: 3, verify: 1, rulebook: 2 },
  gate: { can_accept: false, reason: "The server says this review is out of date." }, limits: { intro: 2000, item_text: 600, items: 50, text: 6000 } };

test("findings and rulebook gaps anchor by aliases, document/reference families, or their section end", () => {
  assert.equal(anchorFor({ section: "A", field: "section_a.owner_name" }, anchors), "owner");
  assert.equal(anchorFor({ section: "process", field: "risk" }, anchors), "risk");
  assert.equal(anchorFor({ section: "D", field: "evidence.report.responsible_party" }, anchors), "doc");
  assert.equal(anchorFor({ section: "C", field: "citation.0" }, anchors), "ref");
  assert.equal(anchorFor({ section: "C", field: "section_c.9.10.9.16.(1).objective" }, anchors), "ref");
  assert.equal(anchorFor({ section: "B", field: "a_new_field" }, anchors), "B:end");
  const gaps = [{ section: "A" as const, field: "owner", id: "g" }, { section: "A" as const, field: "unmapped", id: "fallback" }];
  assert.deepEqual([...anchoredItems(gaps, anchors)].map(([key, values]) => [key, values.map(g => g.id)]), [["owner", ["g"]], ["A:end", ["fallback"]]]);
});

test("every pointer keeps its full quote and maps only an exactly named retained file", () => {
  const quote = "A complete quoted passage. ".repeat(30);
  const pointers: Pointer[] = [
    { file: "form.pdf", page: 2, quote, form_field: "Date", bbox: null },
    { file: "plans.pdf", page: 4, quote: "The second source", form_field: null, bbox: null },
    { file: "other.pdf", page: 1, quote: null, form_field: null, bbox: null },
  ];
  const files: InputFile[] = [{ name: "form.pdf", file_id: "file/form", form_version: null, note: "", pages: 2, role: "attachment", sha256: null, size: 10 },
    { name: "plans.pdf", file_id: null, form_version: null, note: "Not retained", pages: 4, role: "attachment", sha256: null, size: 10 }];
  const sources = findingSources(pointers, files, "case/1");
  assert.equal(sources.length, 3);
  assert.equal(sources[0].quote, quote);
  assert.equal(sources[0].href, "/cases/case%2F1/files/file%2Fform#page=2");
  assert.equal(sources[1].quote, "The second source");
  assert.equal(sources[1].href, null);
  assert.equal(sources[2].href, null);
});

test("officer targets include sections and sheet fields without duplicated alias destinations", () => {
  const targets = targetOptions(null, [...anchors, { ...anchors[0], id: "alias", field: "owner" }]);
  assert.equal(targets.filter(t => t.field === null).length, 5);
  assert.equal(targets.filter(t => t.section === "A" && t.field).length, 1);
  assert.ok(targets.some(t => t.field === "evidence.report" && t.label.includes("Test report")));
});

test("changed fields use only the latest submission, canonicalizing aliases and retaining request answers", () => {
  const changes = changedFields({ submissions: [
    { changes: [{ field: "owner", before: "First", after: "Second" }] },
    { changes: [{ field: "civic_address", before: "Old", after: "New" }, { field: "request_answer.ir_1", before: null, after: "Answer" }] },
  ] } as never);
  assert.equal(changes.has("owner"), false);
  assert.equal(changes.get("municipalAddress")?.before, "Old");
  assert.equal(changes.get("request_answer.ir_1")?.after, "Answer");
});

test("acceptance uses the server gate; local tally values never redefine it", () => {
  const base = { workspace, editable: true, pending: false, busy: false };
  assert.deepEqual([workspaceDecision(base).canAccept, workspaceDecision(base).acceptReason], [false, workspace.gate.reason]);
  assert.equal(workspaceDecision({ ...base, workspace: { ...workspace, gate: { can_accept: true, reason: "" } } }).canAccept, true);
  assert.equal(workspaceDecision({ ...base, pending: true }).canReturn, false);
  assert.equal(workspaceDecision({ ...base, workspace: { ...workspace, tally: { ...workspace.tally, asked: 0 } } }).canReturn, false);
  assert.equal(workspaceDecision({ ...base, editable: false }).canRefuse, false);
});

test("the Required filter retains unreadable verify findings", () => {
  const f = { severity: "blocking" } as Finding;
  const state = { key: "x", state: "verify", locked: false, note: "", reason: null, at: null, by_name: null } as const;
  assert.equal(visibleFinding(f, state, "required"), true);
  assert.equal(visibleFinding(f, { ...state, state: "dismissed" }, "required"), false);
});

test("the officer's application view shows form fields once, never raw case answers or form widget names", () => {
  // QA 2026-10-28: the view listed "Journey.answer.plan-intake.building area m2" with raw JSON, "Office.choice",
  // "Ebf area m2", True/False, and the form's own copies of Owner, Lot, Block, Plan and Permit beside the case's.
  const row = (field: string, label: string, value: string | null) => ({ field, label, value, required: true });
  const sheet: SheetView = {
    applicant: [row("owner_name", "Owner", "Larkspur Example Ltd"), row("representative", "Representative", "Priya Natarajan"),
      row("mailing_address", "Mailing address", "0000 Example Way NW"), row("application_date", "Date of request", "2026-10-28")],
    project: [row("authority", "Reviewing authority", "Edmonton"), row("scope", "Jurisdiction-wide variance", "No, one site"),
      row("permit", "Permit number", "Not yet issued"), row("civic_address", "Municipal address", "0000 Example Crescent NW"),
      row("legal_description", "Legal description", "Lot 0, Block 0, Plan 0000000")],
    alternative: row("alternative_description", "Proposed alternative", "A rated window assembly."),
    references: [], process: [row("process.rationale", "Rationale", "Daylight."), row("process.qualifications", "Qualifications", "Example Engineer.")],
    supporting: [row("professional.role", "Registered professional", "engineer"),
      row("professional.registration_number", "Registration or seal", "EXAMPLE-0000"), row("documents", "Documents listed", "1 document")],
    documents: [], questions: [],
  };
  const reading = (section: FieldReading["section"], field: string, label: string, value: string | null, formField: string | null = null): FieldReading =>
    ({ section, field, label, value, status: value ? "present" : "not_found", reason: "",
      pointer: { file: formField ? "application.pdf" : "case:1", page: null, quote: null, bbox: null, form_field: formField } });
  const session = { fields: [
    reading("B", "journey.answer.plan-intake.building_area_m2", "journey.answer.plan-intake.building area m2", '{"key":"plan-intake.building_area_m2"}'),
    reading("B", "office.choice", "office.choice", "edmonton"),
    reading("B", "ebf_area_m2", "ebf area m2", "40"),
    reading("B", "glass_blocks", "glass blocks", "False"),
    reading("D", "professional.part4_design", "professional.part4 design", "False"),
    reading("B", "lot", "lot", "0"),
    reading("B", "permit_number", "permit number", "Not yet issued"),
    reading("C", "code_or_standard", "code or standard", "NBC(AE) 2023 p2, Div B [PDF p.901]"),
    reading("A", "Owner", "Owner's Name", "Larkspur Example Ltd", "Owner"),
    reading("A", "Date of Reqeuest", "Date of Request", "2026-10-28", "Date of Reqeuest"),
    reading("B", "Lot", "Lot", "0", "Lot"),
    reading("B", "MER", "ATS MER", null, "MER"),
    reading("B", "Permit", "Permit Number (if applicable)", "Not yet issued", "Permit"),
    reading("B", "Check Box", "Proposed alternative solution is for a jurisdiction and is not site-specific", null, "Check Box"),
    reading("C", "Code or Standard", "Applicable Code or Standard", "National Building Code - 2023 Alberta Edition (2nd printing)", "Code or Standard"),
    reading("C", "Article(s)", "Section C row 1 article", "9.10.15.4.(1)", "Article(s)"),
    reading("D", "Supporting Doc", "Supporting documents and responsible persons", "D-1: Report - Example Engineer", "Supporting Doc"),
    reading("A", "Signature1", "owner signature", "Signed in the application by Larkspur Example Ltd", "Signature1"),
    reading("D", "professional_name", "responsible professional", null),
    reading("D", "professional_qualifications", "qualifications of the responsible professional", "Example Engineer."),
    reading("B", "storeys", "storeys", "2"),
  ] } as unknown as ReviewSession;
  const rows = sheetRows(sheet, session);
  const extra = rows.slice(rows.findIndex(r => r.field === "documents") + 1);
  assert.deepEqual(extra.map(r => [r.label, r.reading.value]), [
    ["Code or standard", "National Building Code - 2023 Alberta Edition (2nd printing)"],
    ["Owner signature", "Signed in the application by Larkspur Example Ltd"],
    ["Storeys", "2"],
  ]);
  assert.equal(new Set(rows.map(r => r.label)).size, rows.length);
  const targets = targetOptions(session, allAnchors(rows, sheet, session)).map(t => t.label);
  assert.ok(!targets.some(t => /journey|office|ebf|part4|Owner's Name|ATS/i.test(t)), targets.join("\n"));
});

test("booleans and saved slugs read as words; only form fields are named in the submission history", () => {
  assert.equal(formValue("False"), "No");
  assert.equal(formValue("true"), "Yes");
  assert.equal(formValue("single_family"), "Single family");
  assert.equal(formValue("EXAMPLE-0000"), "EXAMPLE-0000");
  const title = (id: string) => (id === "ev_1" ? "Assembly listing" : null);
  assert.equal(changeLabel("journey.answer.understood%3A7222da7704cc11b", title), null);
  assert.equal(changeLabel("evidence.ev_1.auto_link", title), null);
  assert.equal(changeLabel("evidence.ev_1.file_ref", title), "Assembly listing · attachment");
  assert.equal(changeLabel("building_area_m2", title), "Building area (m²)");
  assert.equal(changeLabel("civic_address", title), "Municipal address");
  const changes = [{ field: "journey.answer.understood%3A7222da7704cc11b", before: null, after: '{"key":"understood"}' },
    { field: "building_area_m2", before: null, after: "120" }];
  assert.deepEqual(visibleSubmissionChanges(changes).map(c => c.field), ["building_area_m2"]);
});

test("the change line speaks of the return, and an officer's own re-run adds no counter", () => {
  // QA 2026-10-28: "Since version 6: 3 new" grew with every officer save.
  const entry = (key: string) => ({ key, section: "D" as const, label: key, message: "" });
  const diff = { previous_version: 6, previous_gaps: 3, resolved: [entry("a"), entry("b")], still_open: [], new: [entry("c")], unverified: [], statement: "" };
  const versions = [{ version: 5, sent_at: null }, { version: 6, sent_at: "2026-10-29T01:46:00Z" }, { version: 7, sent_at: null }];
  assert.equal(sinceReturn(diff, versions), "Since the return: 2 fixed · 1 new");
  assert.equal(sinceReturn({ ...diff, previous_version: 7 }, versions), "");
  assert.equal(sinceReturn(null, versions), "");
  assert.equal(withThe("a named registered professional"), "a named registered professional");
  assert.equal(withThe("applicant signature"), "the applicant signature");
});

test("the headline counts follow the officer's ✕ before the save returns", () => {
  const f = (key: string, severity: Finding["severity"]) => ({ key, severity } as Finding);
  const findings = [f("a", "warning"), f("b", "warning"), f("pro", "warning"), f("gap", "blocking")];
  const items = [{ finding_key: "a", included: true, text: "A" }, { finding_key: "b", included: true, text: "B" },
    { finding_key: null, included: true, text: "Own item" }, { finding_key: null, included: true, text: " " }];
  const states = new Map([["a", { state: "ask" as const, locked: false }], ["b", { state: "ask" as const, locked: false }],
    ["pro", { state: "verify" as const, locked: true }], ["gap", { state: "verify" as const, locked: false }]]);
  assert.deepEqual(localTally(findings, states, items, 1), { required: 3, asked: 3 }, "an empty own item is not an ask yet");
  states.set("a", { state: "dismissed", locked: false });
  states.set("b", { state: "dismissed", locked: false });
  states.set("gap", { state: "dismissed", locked: false });
  assert.deepEqual(localTally(findings, states, items.slice(0, 2), 0), { required: 1, asked: 0 });
});

test("a study listed twice anchors both listings to its one row", () => {
  const sheet = { applicant: [], project: [], alternative: { label: "Proposed alternative", value: null, required: true }, references: [], process: [], supporting: [],
    documents: [{ id: "os", ids: ["os", "op"], title: "Study", fileId: "file_a", fileName: "study.pdf", type: null, author: null, date: null }], questions: [] } as SheetView;
  const session = { documents: [{ id: "os", title: { known: true, value: "Study" } }, { id: "op", title: { known: true, value: "Study" } }], citations: [], section_c: [] } as unknown as ReviewSession;
  const all = allAnchors([], sheet, session);
  assert.deepEqual(all.filter(a => a.section === "D").map(a => a.id), ["D:document:os"]);
  assert.equal(anchorFor({ section: "D", field: "evidence.op.date" }, all), "D:document:os");
});
