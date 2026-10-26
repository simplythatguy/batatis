import assert from "node:assert/strict";
import test from "node:test";
import type { CloseOut, Finding, ReviewSession } from "../../api/types.gen.ts";
import { review } from "../../api/accounts.ts";
import {
  citationView, diffView, documentView, dueView, fileItemsView, missingView, officerVoice, parseCitation,
  peerView, pointerLabel, refusalDecision, refusalMessage, reasonsProblem, APPEAL_NOTICE, sectionCView, summaryView,
} from "./packageView.ts";

const P = (file = "case:c1", over = {}) => ({ file, page: null, form_field: null, bbox: null, quote: null, ...over });
const F = (over: Partial<Finding>): Finding => ({
  key: "k", section: "A", field: "f", label: "thing", status: "blank", problem: null, defect_class: null, message: "Your application appears to be missing the thing.",
  severity: "blocking", routed_to: "applicant", pointers: [P()], citations: [], ...over,
});
const attr = (value: string | null) => (value ? { value, known: true, source: P("report.pdf", { page: 1 }) } : { value: "unknown", known: false, source: null });

function session(findings: Finding[], over: Partial<ReviewSession> = {}): ReviewSession {
  const asked = findings.filter((f) => f.routed_to === "applicant" && f.field !== "division_c_2_3_1");
  return {
    administrative_only: true, not_a_compliance_determination: true, notice: "", schema_version: "batatis.package_review.v1",
    authority: "edmonton", case_id: "c1", case_version: 4, package_id: "c1", version: 1, created_at: "2026-10-21T10:00:00Z", created_by_name: "Morgan Lee",
    input_kind: "case", lookup_skipped: false, diff: null, files: [{ name: "case:c1", sha256: null, size: 0, pages: 0, role: "case_record", form_version: null, note: "" }],
    fields: [
      { field: "owner_name", label: "owner name", section: "A", status: "present", value: "Priya Natarajan", reason: "", pointer: P("Your description") },
      { field: "civic_address", label: "civic address", section: "B", status: "present", value: "10432 82 Avenue NW", reason: "", pointer: P() },
      { field: "alternative_description", label: "alternative", section: "B", status: "present", value: "A listed window well.", reason: "", pointer: P() },
      { field: "signature", label: "signature", section: "A", status: "blank", value: "", reason: "", pointer: P() },
    ],
    findings,
    documents: [{ id: "d1", file: "report.pdf", listed_in_section_d: true, note: "", title: attr("Test report"), type: attr("test report"), issuer: attr(null), date: attr("2026-09-14"), evidence_rung: attr(null), seal: attr(null), responsible: attr("Northline Wells Ltd.") }],
    citations: [{ text: "9.9.10.1.(1)", provision_id: "9.9.10.1.(1)", exists: true, edition_ok: true, page_ok: true, canonical_citation: "NBC(AE) 2023 p2, Div B, Sentence 9.9.10.1.(1) [PDF p.873]", pdf_page: 873, issues: [], pointer: P() }],
    section_c: [{ row: 1, provision_id: "9.9.10.1.(1)", form_objective: "OS3.7", form_function: "F10", table_pairs: ["F10-OS3.7"], status: "match", message: "ok", pointer: P() }],
    information_request: {
      intro: "Please provide the items below.", edited: false, message_id: null, sent_at: null, sent_by_name: null, text: "",
      items: asked.map((f) => ({ id: `ir_${f.key}`, finding_key: f.key, section: f.section, field: f.field, text: `Please provide the ${f.label}.`, authored_by: "batatis" as const, included: f.status !== "not_found", officer_check: f.status === "not_found" })),
    },
    ...over,
  };
}

const sig = F({ key: "signature:presence", field: "signature", label: "applicant signature", severity: "warning" });
const legal = F({ key: "legal:presence", section: "B", field: "legal_description", label: "legal description" });
const stamp = F({ key: "seal:presence", section: "D", field: "seal", label: "seal", status: "not_found", severity: "warning", pointers: [P("form.pdf", { page: 2, form_field: "Seal" })] });
const reg = F({ key: "division_c_2_3_1:presence", section: "B", field: "division_c_2_3_1", label: "Division C Section 2.3.1 documentation", severity: "warning" });
const testing = F({ key: "div_c.testing_procedures:presence", section: "process", field: "div_c.testing_procedures", label: "testing procedures", status: "missing", citations: ["NBC(AE) 2023 p2, Div C, Sentence 2.3.1.1.(3) [PDF p.739]"] });
const failure = F({ key: "demonstrate.failure_conditions:not_mentioned", section: "process", field: "demonstrate.failure_conditions", status: "unclear", severity: "warning" });
const peer = F({ key: "peer_review:signal", section: "D", field: "peer_review", routed_to: "officer", status: "unclear", severity: "warning",
  message: "Peer review may be warranted: a registered professional is stated to be required; a Part 3 provision is cited (3.2.5.7.(1)). This is the officer's call; it is not a finding about the design." });
const all = [sig, legal, stamp, reg, testing, failure, peer];

test("what's missing: applicant gaps grouped in form order (Div C items with the alternative path), officer checks apart", () => {
  const v = missingView(session(all));
  assert.deepEqual(v.groups.map((g) => [g.section, g.items.map((i) => i.key)]), [["A", ["signature:presence"]], ["B", ["legal:presence"]], ["process", ["div_c.testing_procedures:presence", "demonstrate.failure_conditions:not_mentioned"]]]);
  assert.deepEqual(v.officer.map((i) => i.key), ["seal:presence", "division_c_2_3_1:presence"]);
  assert.equal(v.officer[0].tone, "pending");
  assert.equal(v.officer[0].where, "form.pdf · page 2 · field “Seal”");
  assert.equal(v.groups[1].items[0].message, "The application appears to be missing the thing.");
});



test("summary reads who, where, proposal and counts", () => {
  const v = summaryView(session(all));
  assert.equal(v.headline, "Priya Natarajan asks for a variance at 10432 82 Avenue NW.");
  assert.equal(v.proposal, "A listed window well.");
  assert.deepEqual(v.provisions, ["9.9.10.1.(1)"]);
  assert.deepEqual(v.documents, ["Test report"]);
  assert.equal(v.readFrom, "Read from the saved application.");
  assert.equal(v.peer, true);
  const pdf = summaryView(session([], { input_kind: "upload", files: [
    { name: "form.pdf", sha256: "x", size: 1, pages: 7, role: "scc_form_flattened", form_version: "scc_2026-10", note: "" },
    { name: "report.pdf", sha256: "y", size: 1, pages: 1, role: "attachment", form_version: null, note: "" },
  ] }));
  assert.equal(pdf.readFrom, "Read from 2 PDFs: the SCC form (flattened, 7 pages) and 1 attachment.");
});

test("pointers say where in words", () => {
  assert.equal(pointerLabel(P()), "Saved application");
  assert.equal(pointerLabel(P("Your description")), "Applicant’s description");
  assert.equal(pointerLabel(P("plans.pdf", { page: 3, form_field: "Date2" })), "plans.pdf · page 3 · field “Date2”");
  assert.equal(pointerLabel(P("case:c1", { form_field: "section_c[0]" })), "Saved application");
  assert.equal(pointerLabel(null), "");
});

test("documents: unknown is shown as unknown, never guessed", () => {
  const d = documentView(session([]).documents[0]);
  assert.equal(d.title, "Test report");
  const issuer = d.cells.find((c) => c.label === "Issued by")!;
  assert.deepEqual([issuer.value, issuer.known, issuer.where], ["unknown", false, ""]);
  assert.equal(d.cells.find((c) => c.label === "Date")!.where, "report.pdf · page 1");
});

test("code checks map to plain statuses", () => {
  const c = session([]).citations[0];
  assert.equal(citationView(c).status, "Found in NBC(AE) 2023, 2nd printing");
  assert.equal(citationView({ ...c, exists: false }).tone, "blocking");
  assert.equal(citationView({ ...c, edition_ok: false }).tone, "warning");
  assert.equal(citationView({ ...c, exists: null, issues: [{ code: "lookup_skipped", message: "skipped" }] }).status, "Not looked up");
  const r = session([]).section_c[0];
  assert.deepEqual([sectionCView(r).tone, sectionCView(r).form, sectionCView(r).table], ["done", "OS3.7 · F10", "F10-OS3.7"]);
  assert.equal(sectionCView({ ...r, status: "mismatch" }).status, "Differs from the Division B table");
});

test("file items: missing, no gap found, or not checked when nothing was read", () => {
  const v = fileItemsView(session(all));
  assert.equal(v.items.find((i) => i.key === "div_c.testing_procedures")!.status, "Missing");
  assert.equal(v.items.find((i) => i.key === "div_c.code_analysis")!.status, "No gap found");
  assert.equal(v.demonstrate.find((i) => i.key === "demonstrate.failure_conditions")!.status, "Not mentioned");
  const unread = fileItemsView(session([], { fields: [] }));
  assert.ok(unread.items.every((i) => i.status === "Not checked"));
});

test("peer review: reasons for the officer, never a finding", () => {
  assert.deepEqual(peerView(session(all)).reasons, ["A registered professional is stated to be required", "A Part 3 provision is cited (3.2.5.7.(1))"]);
  assert.deepEqual(peerView(session([])), { signal: false, reasons: [] });
});





test("re-upload diff", () => {
  const s = session([legal], { version: 2, diff: { previous_version: 1, previous_gaps: 3, statement: "2 of 3 gaps resolved, 1 still open", resolved: [{ key: "signature:presence", label: "applicant signature", message: "m", section: "A" }, { key: "x", label: "x", message: "m", section: "A" }], still_open: [{ key: "legal:presence", label: "legal description", message: "m", section: "B" }], new: [] } });
  const d = diffView(s)!;
  assert.equal(d.statement, "2 of 3 gaps resolved, 1 still open");
  assert.equal(d.from, 1);
  assert.deepEqual(d.resolved.map((r) => r.tone), ["done", "done"]);
  assert.equal(d.stillOpen[0].where, "Saved application");
  assert.ok(Math.abs(d.ratio - 2 / 3) < 1e-9);
  assert.equal(diffView(session([])), null);
});

test("refusal: the officer's reasons verbatim with the 30-day appeal notice; no drafted reasons", () => {
  const m = refusalMessage("  The fire separation drawings were not provided after two requests.  ");
  assert.ok(m.includes("The fire separation drawings were not provided after two requests."));
  assert.ok(m.endsWith(APPEAL_NOTICE));
  assert.match(APPEAL_NOTICE, /30 days/);
  assert.equal(reasonsProblem(""), "Write your reasons for the refusal.");
  assert.equal(reasonsProblem("short"), "At least 10 characters · 5 so far.");
  assert.equal(reasonsProblem("Long enough reasons"), "");
  assert.doesNotMatch(m + APPEAL_NOTICE, /\b(complies|compliant|approved|adequate|safe)\b/i);
});

test("refusal posts a distinct decision with the officer's reasons and appeal notice", async (t) => {
  const calls: { url: string; method: string | undefined; body: unknown }[] = [];
  t.mock.method(globalThis, "fetch", async (url: string, init: RequestInit) => {
    calls.push({ url, method: init.method, body: JSON.parse(String(init.body)) });
    return new Response(JSON.stringify({ status: "refused", outcome: "refuse" }), { status: 200 });
  });
  const reasons = "The requested fire separation drawings were not provided.";
  await review.decide("case/refusal", refusalDecision(reasons, 7));
  // The displayed version pins the refusal (a newer save is a conflict); a refusal has no correction list.
  assert.deepEqual(calls, [{
    url: "/api/review/case%2Frefusal/decision", method: "POST",
    body: { outcome: "refuse", message: refusalMessage(reasons), expected_version: 7 },
  }]);
  assert.equal("items" in (calls[0].body as object), false);
  assert.ok(refusalMessage(reasons).includes(reasons));
  assert.ok(refusalMessage(reasons).endsWith(APPEAL_NOTICE));
  assert.doesNotMatch(refusalMessage(reasons), /returned|fix and resubmit/i);
});

test("close-out due line", () => {
  const base: CloseOut = { case_id: "c1", outcome: "accept", decided_at: "2026-10-21T10:00:00Z", issued_on: "2026-10-21", issued_by_name: "Morgan", due_date: "2026-10-31", days_remaining: 10, overdue: false, sent: false, sent_at: null, sent_by_name: null, notice: "", record_package: { basis: [], note: "", send_to_council: [], retain_on_file: [] } };
  assert.deepEqual(dueView({ ...base, issued_on: null, issued_by_name: null, due_date: null, days_remaining: null }), { tone: "pending", text: "Variance not issued yet" });
  assert.match(dueView({ ...base, outcome: "refuse" }).text, /Nothing to send/);
  assert.deepEqual(dueView(base), { tone: "pending", text: "Due Oct 31, 2026 · 10 days left" });
  assert.equal(dueView({ ...base, days_remaining: 2 }).tone, "warning");
  assert.deepEqual(dueView({ ...base, days_remaining: -3, overdue: true }), { tone: "blocking", text: "Due Oct 31, 2026 · 3 days overdue" });
  assert.equal(dueView({ ...base, sent: true, sent_at: "2026-10-22T09:00:00Z", sent_by_name: "Morgan Lee" }).text, "You recorded sending it on Oct 22, 2026 (Morgan Lee).");
});



test("citations parse for the code reveal; officer voice", () => {
  assert.deepEqual(parseCitation("NBC(AE) 2023 p2, Div C, Sentence 2.3.1.1.(3) [PDF p.739]"), { division: "C", id: "2.3.1.1.(3)" });
  assert.deepEqual(parseCitation("NBC(AE) 2023 p2, Div C, Clause 2.3.1.1.(2)(b) [PDF p.739]"), { division: "C", id: "2.3.1.1.(2)(b)" });
  assert.equal(parseCitation("see the appendix"), null);
  assert.equal(officerVoice("Your application appears to be missing x."), "The application appears to be missing x.");
});

test("co-ordinator row: officer voice, and not found stays an officer check", () => {
  const coord = F({ key: "div_c.coordinator:presence", section: "process", field: "div_c.coordinator", label: "single co-ordinator", status: "missing", message: "Your application names 2 firms and no co-ordinator." });
  const row = fileItemsView(session([coord])).items.find((i) => i.key === "div_c.coordinator")!;
  assert.deepEqual([row.status, row.tone, row.message], ["Missing", "blocking", "The application names 2 firms and no co-ordinator."]);
  const unsure = fileItemsView(session([{ ...coord, status: "not_found" }])).items.find((i) => i.key === "div_c.coordinator")!;
  assert.deepEqual([unsure.status, unsure.tone], ["Not found · check it", "pending"]);
  assert.equal(fileItemsView(session([])).items.some((i) => i.key === "div_c.coordinator"), false);
});


