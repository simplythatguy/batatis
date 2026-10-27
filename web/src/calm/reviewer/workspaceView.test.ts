import assert from "node:assert/strict";
import test from "node:test";
import type { Finding, InputFile, Pointer, OfficerWorkspace } from "../../api/types.gen.ts";
import { anchoredItems, anchorFor, changedFields, findingSources, targetOptions, visibleFinding, workspaceDecision, type SheetAnchor } from "./workspaceView.ts";

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
