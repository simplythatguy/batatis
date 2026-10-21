import assert from "node:assert/strict";
import test from "node:test";
import { sheetFromEngine } from "./sheet.ts";

const fact = (field: string, value: unknown, over: Record<string, unknown> = {}) => ({
  id: field, field, value, kind: "pointed", status: "confirmed", source: { type: "user_text", ref: "t", quote: "" },
  confidence: null, formula: null, inputs: [], ...over,
});

test("the officer's sheet reads API and web field names and keeps missing values empty", () => {
  const c = {
    authority: "edmonton", jurisdiction: null, submitted_at: "2026-10-21T08:00:00Z",
    facts: [
      fact("owner_name", "Mira Kaur"),
      fact("mailingAddress", "1 Example St"),
      fact("scope", "site"),
      fact("civic_address", "2 Example St"),
      fact("process.risk_assessment", "Risk text"),
      fact("mitigation", "Measures text"),
      fact("representative", "Old rep"),
      fact("representative", "", { source: { type: "user_text", ref: "Answer withdrawn by applicant" } }),
      fact("evidence.e1.title", "Test report"),
      fact("professional_status", "not_engaged"),
    ],
    section_c: [{ provision_id: "9.10.9.16.(1)", pairs: [{ objective: "OS1.2", function: "F03" }] }, { provision_id: "9.27.3.4.(1)", pairs: [] }],
  } as never;
  const s = sheetFromEngine(c);
  const val = (rows: { label: string; value: string | null }[], label: string) => rows.find((r) => r.label === label)?.value ?? null;
  assert.equal(val(s.applicant, "Owner"), "Mira Kaur");
  assert.equal(val(s.applicant, "Mailing address"), "1 Example St");
  assert.equal(val(s.applicant, "Representative"), null, "a withdrawn answer is missing, not the old value");
  assert.equal(val(s.applicant, "Date of request"), null);
  assert.equal(val(s.project, "Reviewing authority"), "Edmonton");
  assert.equal(val(s.project, "Jurisdiction-wide variance"), "No, one site");
  assert.equal(val(s.project, "Municipal address"), "2 Example St");
  assert.equal(s.alternative.value, null);
  assert.equal(val(s.process, "Risk assessment"), "Risk text");
  assert.equal(val(s.process, "Mitigating measures"), "Measures text");
  assert.equal(val(s.process, "Rationale"), null);
  assert.equal(val(s.supporting, "Documents listed"), "Test report");
  assert.equal(val(s.supporting, "Registered professional"), "Not engaged yet");
  assert.deepEqual(s.references, [
    { provision: "9.10.9.16.(1)", codes: "Objectives OS1.2 · Functions F03" },
    { provision: "9.27.3.4.(1)", codes: "No row in the attribution table" },
  ]);
});
