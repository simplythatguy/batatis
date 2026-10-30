import assert from "node:assert/strict";
import test from "node:test";
import { emptyCase } from "../intake.ts";
import type { Gap } from "../types.ts";
import { sectionTone } from "./preparation.ts";

const gap = (id: string, severity: Gap["severity"], over: Partial<Gap> = {}): Gap => ({ id, label: id, section: "D", severity, href: "#/questions", ...over } as Gap);

test("a section is red only for what the applicant still owes; the officer's part is amber", () => {
  const c = emptyCase("owner");
  const officer = gap("professional-requirement", "blocking", { submissionBlocking: false });
  assert.equal(sectionTone(c, [officer, gap("risk-open", "warning")]), "warning", "Ready to submit never sits next to a red section");
  assert.equal(sectionTone(c, [officer, gap("documents-missing", "blocking")]), "blocking");
  assert.equal(sectionTone(c, []), "done");
});
