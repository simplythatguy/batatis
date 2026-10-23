/**
 * An officer's item links to the place that fixes it, or to nothing: never to a page that cannot fix
 * it. A signature or a free-text request item has no question in Batatis; linking it to Start (the
 * fallback for unknown fields) told the applicant to "fix" it where nothing can be fixed.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness } from "../../../scripts/component-harness.mjs";
import * as routes from "../routes.ts";

const KNOWN: Record<string, string> = { risk_assessment: "#/application?tab=alt&focus=field-risk", owner_name: "#/describe?focus=fact-owner_name" };
const h = await componentHarness(new URL("./Comments.tsx", import.meta.url), "Comments", {
  "../../store": { hrefFor: (field: string) => KNOWN[field] ?? "#/describe", useCase: () => ({}) },
  "../../model": { factLabel: (f: string) => f },
  "../deck": { gapKey: (_c: unknown, g: { id: string }) => (g.id === "g-risk" ? "field-risk" : null) },
  "../routes": routes,
});
const itemLink = h.exports.itemLink as (c: unknown, gaps: unknown[], item: Record<string, string>) => { label: string; href: string | null };

test("an item with no question to fix it is listed without a link", () => {
  for (const field of ["signature", "representative_signature_date", "information_request"]) {
    const row = itemLink({}, [], { field, note: `Please provide the ${field}.` });
    assert.equal(row.label, `Please provide the ${field}.`, "the officer's own words stay");
    assert.equal(row.href, null, `${field} has nowhere in Batatis to fix it`);
  }
});

test("an item that matches a gap opens its question; a mapped field opens its card", () => {
  assert.equal(itemLink({}, [{ id: "g-risk", field: "risk_assessment", href: "#/application?tab=alt" }], { field: "risk_assessment", note: "Expand the risk assessment." }).href, "#/questions?focus=field-risk");
  assert.equal(itemLink({}, [], { field: "owner_name", note: "Owner name" }).href, "#/questions?focus=fact-owner_name");
});
