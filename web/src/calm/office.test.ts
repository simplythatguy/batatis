import assert from "node:assert/strict";
import test from "node:test";
import { AUTHORITIES, authorityUnsure, officeChoiceAction, officeCovered, officeSuggestion, resolveOffice, submissionOfficeReason } from "../config.ts";
import { emptyCase } from "../intake.ts";
import { reducer } from "../model.ts";
import { jurisdictionBody } from "../rules.ts";
import { filterAuthorities } from "./authorityFilter.ts";

for (const [place, pack, reviewer, shown] of [
  ["Calgary", "calgary", "calgary", "Calgary"], ["City of Calgary", "calgary", "calgary", "Calgary"],
  ["Calgary, AB", "calgary", "calgary", "Calgary"], ["Edmonton", "edmonton", "edmonton", "Edmonton"],
  ["City of Edmonton", "edmonton", "edmonton", "Edmonton"],
  ["Red Deer", "alberta-other", null, "Red Deer"], ["Lacombe County", "alberta-other", null, "Lacombe County"],
  ["Vancouver", "alberta-other", null, "Vancouver"], ["Example Hamlet", "alberta-other", null, "Example Hamlet"],
] as const) {
  test(`${place} resolves without inventing a reviewing account`, () => {
    const choice = resolveOffice(place);
    assert.equal(choice?.packId, pack);
    assert.equal(choice?.reviewerCode, reviewer);
    assert.equal(jurisdictionBody(choice!.id).name, shown);
    const c = reducer(emptyCase("owner"), { type: "setAuthority", authority: choice!.id });
    assert.equal(Boolean(submissionOfficeReason(c)), !reviewer);
  });
}

test("the picker offers only Calgary and Edmonton, the offices whose own steps are checked", () => {
  assert.deepEqual(AUTHORITIES.map((a) => [a.id, a.name]), [["calgary", "Calgary"], ["edmonton", "Edmonton"]]);
  for (const option of AUTHORITIES) for (const name of [option.id, ...option.aliases]) assert.equal(resolveOffice(name)?.id, option.id, name);
  assert.equal(filterAuthorities(AUTHORITIES, "City of Edmonton").shown[0]?.id, "edmonton");
});

test("only Calgary and Edmonton are covered; every other place says Batatis does not prepare it", () => {
  assert.equal(officeCovered("Calgary"), true);
  assert.equal(officeCovered("City of Edmonton"), true);
  for (const place of ["Red Deer", "Lacombe County", "Vancouver", "Example Hamlet"]) assert.equal(officeCovered(place), false, place);
  assert.equal(officeCovered("unsure"), null);
  const c = reducer(emptyCase("owner"), { type: "setAuthority", authority: "Red Deer" });
  assert.equal(submissionOfficeReason(c), "Batatis does not prepare applications for Red Deer.");
});

test("Not sure is a confirmed case fact and survives a JSON round trip", () => {
  const c = reducer(emptyCase("owner"), officeChoiceAction("unsure"));
  assert.equal(c.authority, "");
  assert.equal(authorityUnsure(JSON.parse(JSON.stringify(c))), true);
  assert.equal(c.facts.find((fact) => fact.field === "office.choice")?.source.quote, "Not sure");
  assert.equal(authorityUnsure(reducer(c, officeChoiceAction("edmonton"))), false);
});

test("the site suggests Calgary or Edmonton, and never another place", () => {
  let c = reducer(emptyCase("owner"), { type: "setDetail", field: "municipalAddress", value: "0000 Example Crescent NW, Edmonton, AB", section: "B" });
  assert.equal(officeSuggestion(c)?.id, "edmonton");
  c = reducer(emptyCase("owner"), { type: "setDetail", field: "municipalAddress", value: "0000 Example Road, Red Deer, AB", section: "B" });
  assert.equal(officeSuggestion(c), null);
  c = reducer(c, { type: "setRuleInput", field: "municipality", value: "Calgary", rule: "intake", quote: "Calgary" });
  assert.equal(officeSuggestion(c)?.id, "calgary");
  c = reducer(emptyCase("owner"), { type: "setRuleInput", field: "municipality", value: "Example Hamlet", rule: "intake", quote: "Example Hamlet" });
  assert.equal(officeSuggestion(c), null);
});
