import assert from "node:assert/strict";
import test from "node:test";
import { AUTHORITIES, authorityUnsure, officeChoiceAction, officeCoverage, officeSuggestion, resolveOffice, submissionOfficeReason } from "../config.ts";
import { emptyCase } from "../intake.ts";
import { reducer } from "../model.ts";
import { jurisdictionBody } from "../rules.ts";
import { filterAuthorities } from "./authorityFilter.ts";
import placeIndex from "../../../engine/data/jurisdictions/place_index.json" with { type: "json" };

for (const [place, pack, reviewer, shown] of [
  ["Calgary", "calgary", "calgary", "Calgary"], ["Edmonton", "edmonton", "edmonton", "Edmonton"],
  ["Red Deer", "red-deer", null, "Red Deer"], ["City of Red Deer", "red-deer", null, "Red Deer"],
  ["Lacombe County", "lacombe-county", null, "Lacombe County"], ["Vancouver", "vancouver", null, "Vancouver"],
  ["St. Johns", "st-johns", null, "St. John's"],
  ["Example Hamlet", "alberta-other", null, "Example Hamlet"],
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

test("only Calgary and Edmonton are covered; everywhere else says who to ask, from the place data", () => {
  assert.deepEqual(officeCoverage("Calgary"), { covered: true, ask: "Ask City of Calgary about its intake steps and fees." });
  assert.equal(officeCoverage("Edmonton")?.covered, true);
  assert.deepEqual(officeCoverage("City of Red Deer"), { covered: false, ask: "Ask City of Red Deer about its variance steps and forms." });
  assert.deepEqual(officeCoverage("Lacombe County"), { covered: false, ask: "Ask the Alberta Safety Codes Authority or one of its contracted agencies." });
  assert.deepEqual(officeCoverage("Vancouver"), { covered: false, ask: "Ask City of Vancouver." });
  assert.equal(officeCoverage("Example Hamlet")?.covered, false);
  assert.match(officeCoverage("Example Hamlet")!.ask, /Where to get a Permit/);
  assert.equal(officeCoverage("unsure"), null);
  assert.deepEqual(placeIndex.places.filter((p) => p.covered).map((p) => p.id).sort(), ["calgary", "edmonton"]);
});

test("each place shows a shorter form of its own name, never a community inside it", () => {
  const label = (id: string) => AUTHORITIES.find((a) => a.id === id)?.name;
  assert.equal(label("red-deer"), "Red Deer");
  assert.equal(label("strathcona-county"), "Strathcona County");
  assert.equal(label("wood-buffalo"), "Wood Buffalo");
  assert.equal(label("calgary-international-airport"), "Calgary International Airport");
  assert.equal(label("maskwacis"), "Maskwacis");
});

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

test("every place the engine knows can be picked, by every one of its names", () => {
  assert.equal(AUTHORITIES.length, placeIndex.places.length);
  for (const option of AUTHORITIES) for (const name of [option.id, ...option.aliases]) assert.equal(resolveOffice(name)?.id, option.id, name);
});

test("the picker finds a place by its legal name, not only the short one", () => {
  assert.equal(filterAuthorities(AUTHORITIES, "City of Red Deer").shown[0]?.id, "red-deer");
  assert.equal(filterAuthorities(AUTHORITIES, "lacombe county").shown[0]?.id, "lacombe-county");
});
