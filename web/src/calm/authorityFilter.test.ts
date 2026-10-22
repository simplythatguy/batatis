import assert from "node:assert/strict";
import test from "node:test";
import { AUTHORITY_LIST_LIMIT, filterAuthorities, type AuthorityOption } from "./authorityFilter.ts";

/** Hundreds of synthetic offices; none of these exist as configured authorities. */
const MANY: AuthorityOption[] = Array.from({ length: 430 }, (_, i) => ({ id: `synthetic-${i}`, name: `Town ${String(i).padStart(3, "0")}` }));
const REAL: AuthorityOption[] = [{ id: "calgary", name: "Calgary" }, { id: "edmonton", name: "Edmonton" }];

test("an empty search lists the options in their given order, capped", () => {
  assert.deepEqual(filterAuthorities(REAL, "  ").shown, REAL);
  const all = filterAuthorities(MANY, "");
  assert.equal(all.shown.length, AUTHORITY_LIST_LIMIT);
  assert.equal(all.total, 430);
  assert.equal(all.shown[0].id, "synthetic-0");
});

test("the current few real authorities filter by name, case and accents ignored", () => {
  assert.deepEqual(filterAuthorities(REAL, "edm").shown.map((o) => o.id), ["edmonton"]);
  assert.deepEqual(filterAuthorities(REAL, "CALG").shown.map((o) => o.id), ["calgary"]);
  assert.deepEqual(filterAuthorities([{ id: "qc", name: "Montréal" }], "montreal").shown.map((o) => o.id), ["qc"]);
  assert.equal(filterAuthorities(REAL, "zzz").total, 0);
});

test("every typed word must match, and the id counts", () => {
  const list: AuthorityOption[] = [{ id: "cb", name: "County of Barrhead" }, { id: "mdb", name: "MD of Bonnyville" }, { id: "x", name: "Barrhead Village" }];
  assert.deepEqual(filterAuthorities(list, "barrhead county").shown.map((o) => o.id), ["cb"]);
  assert.deepEqual(filterAuthorities(list, "mdb").shown.map((o) => o.id), ["mdb"]);
});

test("names that start with the search come before words and substrings inside other names", () => {
  const list: AuthorityOption[] = [{ id: "a", name: "Pine Grove" }, { id: "b", name: "Springfield" }, { id: "c", name: "Town of Spring Lake" }, { id: "d", name: "Spring Hill" }];
  assert.deepEqual(filterAuthorities(list, "spring").shown.map((o) => o.id), ["b", "d", "c"]);
});

test("a narrow search over hundreds finds one office and reports the real total", () => {
  const hit = filterAuthorities(MANY, "town 417");
  assert.deepEqual(hit.shown.map((o) => o.id), ["synthetic-417"]);
  const broad = filterAuthorities(MANY, "town");
  assert.equal(broad.shown.length, AUTHORITY_LIST_LIMIT);
  assert.equal(broad.total, 430);
});
