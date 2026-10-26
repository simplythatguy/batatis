import assert from "node:assert/strict";
import test from "node:test";
import { AUTHORITIES, authorityUnsure, officeChoiceAction, officeSuggestion, resolveOffice, submissionOfficeReason } from "../config.ts";
import { emptyCase } from "../intake.ts";
import { reducer } from "../model.ts";
import { jurisdictionBody } from "../rules.ts";

for (const [place, pack, reviewer] of [["Calgary", "calgary", "calgary"], ["Edmonton", "edmonton", "edmonton"], ["Red Deer", "alberta-other", null], ["Example Hamlet", "alberta-other", null]] as const) {
  test(`${place} resolves without inventing a reviewing account`, () => {
    const choice = resolveOffice(place);
    assert.equal(choice?.packId, pack);
    assert.equal(choice?.reviewerCode, reviewer);
    assert.equal(jurisdictionBody(choice!.id).name, place);
    const c = reducer(emptyCase("owner"), { type: "setAuthority", authority: choice!.id });
    assert.equal(Boolean(submissionOfficeReason(c)), !reviewer);
  });
}

test("Not sure is a confirmed case fact and survives a JSON round trip", () => {
  const c = reducer(emptyCase("owner"), officeChoiceAction("unsure"));
  assert.equal(c.authority, "");
  assert.equal(authorityUnsure(JSON.parse(JSON.stringify(c))), true);
  assert.equal(c.facts.find((fact) => fact.field === "office.choice")?.source.quote, "Not sure");
  assert.equal(authorityUnsure(reducer(c, officeChoiceAction("red-deer"))), false);
});

test("the same Alberta place data supplies suggestions and a site confirmation", () => {
  assert.ok(AUTHORITIES.some((place) => place.name === "Red Deer"));
  let c = reducer(emptyCase("owner"), { type: "setDetail", field: "municipalAddress", value: "123 Example Road, Red Deer, AB", section: "B" });
  assert.equal(officeSuggestion(c)?.name, "Red Deer");
  c = reducer(c, { type: "setRuleInput", field: "municipality", value: "Example Hamlet", rule: "intake", quote: "Example Hamlet" });
  assert.equal(officeSuggestion(c)?.name, "Example Hamlet");
});
