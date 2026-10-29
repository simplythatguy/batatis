import assert from "node:assert/strict";
import test from "node:test";
import { calmHref } from "./calm/routes.ts";
import { hrefFor } from "./gapHref.ts";

test("every engine finding opens the card that fixes it, never Describe", () => {
  // QA 2026-10-28: these six kinds of Review links all opened Describe (#/).
  const cases: [string, string, string][] = [
    ["supporting_doc", "D", "#/application?focus=evidence"],
    ["signature", "A", "#/application?step=sign"],
    ["section_b.consistency", "B", "#/application?focus=section-B"],
    ["permit_number", "B", "#/application?focus=section-B"],
    ["citation.9.10.15.4.", "B", "#/application?focus=section-C"],
    ["div_c.testing_procedures", "process", "#/application?focus=evidence"],
    ["demonstrate.lapsed_maintenance", "process", "#/application?focus=field-maintenance"],
    ["attachment.fire-rated-window", "D", "#/application?focus=evidence"],
    ["owner_rep_signature_date", "A", "#/application?step=sign"],
    ["something_new", "", "#/application"],
  ];
  for (const [field, section, expected] of cases) assert.equal(calmHref(hrefFor(field, section)), expected, field);
  assert.equal(calmHref(hrefFor("owner_name")), "#/application?focus=field-owner");
  assert.equal(calmHref(hrefFor("jurisdiction")), "#/questions?focus=authority");
});
