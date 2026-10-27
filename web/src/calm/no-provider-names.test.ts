import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { PRIVACY_NOTICE } from "../privacy.ts";
import { BAND_LABEL, BAND_SHORT } from "./relevance.ts";

/** The scoring provider by name and by vendor, and the other AI providers the privacy notice must not name. */
const PROVIDER = /jev|typesafe|openai|anthropic|claude|gpt/i;
const BANDS = ["estimate", "high", "low", "mid", "unscored", "zero"];

test("the relevance label maps name no provider", () => {
  for (const [name, labels] of Object.entries({ BAND_LABEL, BAND_SHORT })) {
    assert.deepEqual(Object.keys(labels).sort(), BANDS, `${name} has every band`);
    for (const [band, label] of Object.entries(labels)) {
      assert.ok(label.trim().length > 0, `${name}.${band} is not empty`);
      assert.doesNotMatch(label, PROVIDER, `${name}.${band}: ${label}`);
    }
  }
});

test("an unscored or zero band reads as a relevance estimate, not as a vendor's score", () => {
  assert.equal(BAND_LABEL.unscored, "Not scored");
  assert.equal(BAND_LABEL.zero, "No relevance score");
  assert.equal(BAND_SHORT.unscored, "not scored");
  assert.equal(BAND_SHORT.zero, "no relevance score");
});

test("the privacy notice names no provider, carries no link, and keeps its three disclosures", () => {
  assert.doesNotMatch(PRIVACY_NOTICE, PROVIDER);
  assert.doesNotMatch(PRIVACY_NOTICE, /https?:\/\/|\(|\)/, "no URL, so Settings has no link to build");
  assert.match(PRIVACY_NOTICE, /removes the names, contact details and addresses it recognizes before any text is sent to an AI provider/);
  assert.match(PRIVACY_NOTICE, /In live mode, the remaining text is processed in the United States by third-party AI service providers under their API data-use terms/);
  assert.match(PRIVACY_NOTICE, /account drafts after 180 inactive days/);
  assert.match(PRIVACY_NOTICE, /Deleting an application removes its stored data, files and background work\.$/);
});

/** Evaluation evidence stays in contributor docs after its applicant page is removed. */
test("the contributor accuracy report names no provider", () => {
  const names = /jev|typesafe|openai|anthropic|claude|\bgpt|\bluna\b|sonnet|opus|haiku|gemini/i;
  for (const file of ["../../../docs/accuracy/report.json", "../../../docs/accuracy/report.md"]) {
    assert.doesNotMatch(readFileSync(new URL(file, import.meta.url), "utf8"), names, file);
  }
});
