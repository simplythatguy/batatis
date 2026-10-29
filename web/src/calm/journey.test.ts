import assert from "node:assert/strict";
import test from "node:test";
import { emptyCase } from "../intake.ts";
import { getGaps, reducer } from "../model.ts";
import { buildDeck } from "./deck.ts";
import { journeyAnswerAction, journeyProgress, routeChoice, understandingRows } from "./journey.ts";
import { DETAIL_IDS } from "../model.ts";

test("paperwork is one sheet with row counts and field focus aliases", () => {
  const items = buildDeck(emptyCase(), [], { today: "2026-10-26", includeDone: true });
  const paperwork = items.filter((item) => item.stage === "paperwork");
  assert.equal(paperwork.length, 1);
  const sheet = paperwork[0];
  assert.equal(sheet.title, "Last details for the form");
  assert.equal(sheet.paperworkRows?.filter((row) => !row.optional && !row.done).length, 7);
  assert.equal(journeyProgress([sheet]).open.you + journeyProgress([sheet]).open.batatis, 7);
  assert.equal(sheet.paperworkRows?.find((row) => row.ref === "permit")?.optional, true);
});

test("project decisions come before owner and mailing paperwork", () => {
  const c = reducer(emptyCase(), { type: "setDescription", text: "A house with larger windows." });
  const deck = buildDeck(c, getGaps(c), { includeDone: true });
  const owner = deck.findIndex((i) => i.kind === "paperwork");
  assert.ok(deck.findIndex((i) => i.kind === "storeys") < owner);
  assert.ok(deck[owner].paperworkRows?.some((i) => i.kind === "authority"));
});

test("Later is case data, stays open, and is not automatically asked again", () => {
  let c = emptyCase();
  const item = buildDeck(c, []).find((i) => i.kind === "paperwork")!.paperworkRows!.find((i) => i.key === "field-owner")!;
  c = reducer(c, journeyAnswerAction(item, "later"));
  const reopened = JSON.parse(JSON.stringify(c));
  assert.ok(!buildDeck(reopened, []).some((i) => i.key === item.key));
  const all = buildDeck(reopened, [], { includeDone: true });
  assert.equal(all.find((i) => i.kind === "paperwork")?.paperworkRows?.find((i) => i.key === item.key)?.settled, true);
  assert.equal(journeyProgress(all).yourPartDone, false);
});

test("a saved acceptable route keeps the evidence ladder and drops the variance package", () => {
  let c = emptyCase();
  c = reducer(c, { type: "setDetail", field: "journey.route", value: "standard", section: "B" });
  assert.equal(routeChoice(c), "standard");
  const deck = buildDeck(c, [], { includeDone: true });
  assert.ok(deck.some((i) => i.stage === "proof"));
  assert.ok(!deck.some((i) => i.stage === "case" || i.ref === "alternative" || i.ref === "scope"));
});

test("equal readings retain their sources in one row, while picture proposals stay individual", () => {
  const c = { ...emptyCase("owner"), files: [{ id: "photo", engineId: "photo", name: "wall.webp", read: true }], facts: [
    { id: "words", field: "storeys", value: 2, kind: "pointed" as const, status: "unconfirmed" as const, source: { type: "user_text" as const, ref: "intake:description", quote: "two storeys" } },
    { id: "plan", field: "building.storeys", value: 2, kind: "pointed" as const, status: "unconfirmed" as const, source: { type: "file" as const, ref: "plans", page: 3, quote: "2 storeys" } },
    { id: "picture", field: "sprinklered", value: "no", kind: "proposed" as const, status: "unconfirmed" as const, source: { type: "file" as const, ref: "photo", quote: "No sprinkler heads visible" } },
  ] };
  const rows = understandingRows(c, DETAIL_IDS);
  assert.deepEqual(rows.find((r) => r.field === "storeys")?.ids, ["words", "plan"]);
  assert.equal(rows.find((r) => r.field === "storeys")?.sources.length, 2);
  const items = buildDeck(c, []);
  assert.equal(items.filter((i) => i.kind === "understood").length, 1);
  assert.equal(items.filter((i) => i.kind === "fact").length, 1);
  assert.equal(items.find((i) => i.kind === "fact")?.ref, "picture");
});

test("a labelled legal description and its lot, block and plan show one Legal description row", () => {
  const read = (id: string, field: string, value: string) => ({ id, field, value, kind: "pointed" as const, status: "unconfirmed" as const, source: { type: "user_text" as const, ref: "intake:description", quote: value } });
  const c = { ...emptyCase("owner"), facts: [
    read("legal", "legal_description", "Lot 0, Block 0, Plan 0000000"), read("lot", "lot", "0"), read("block", "block", "0"), read("plan", "plan", "0000000"),
  ] };
  const legal = understandingRows(c, DETAIL_IDS).filter((r) => r.copy.title === "Legal description");
  assert.equal(legal.length, 1);
  assert.deepEqual([...legal[0].ids].sort(), ["block", "legal", "lot", "plan"], "Looks right still confirms every part");
});

test("derived confirmations are explicit suggestions and never silently fill the case", () => {
  const c = reducer(emptyCase("owner"), { type: "setDetail", field: "municipalAddress", value: "Synthetic site address", section: "B" });
  const items = buildDeck(c, [], { today: "2026-10-26", includeDone: true });
  const rows = items.find((i) => i.kind === "paperwork")!.paperworkRows!;
  const date = rows.find((i) => i.ref === "date")!;
  const mailing = rows.find((i) => i.ref === "mailingAddress")!;
  assert.equal(date.answerer, "batatis");
  assert.equal(date.suggestedValue, "2026-10-26");
  assert.equal(mailing.suggestedValue, "Synthetic site address");
  assert.equal(c.facts.filter((f) => f.field === "date" || f.field === "mailingAddress").length, 0);
});

test("nested professional questions contribute their open counts instead of one outer card", () => {
  const proof = { ...buildDeck(emptyCase("owner"), [])[0], stage: "proof" as const, counts: { you: { open: 2, done: 1 }, designer: { open: 3, done: 2 }, office: { open: 1, done: 0 } } };
  const progress = journeyProgress([proof]);
  assert.deepEqual(progress.open, { you: 2, designer: 3, office: 1, batatis: 0 });
  assert.equal(progress.stages.find((s) => s.stage === "proof")?.total, 9);
  assert.equal(progress.yourPartDone, false);
});

test("recorded designer uncertainty survives reload without inventing a technical answer", () => {
  const item = { ...buildDeck(emptyCase("owner"), [])[0], key: "rulein-part4_design", ref: "part4_design", field: "part4_design", kind: "question" as const, stage: "project" as const, answerer: "designer" as const, optional: false };
  let c = { ...emptyCase("owner"), questions: [{ id: "part4_design", field: "part4_design", text: "Part 4 design?", why: "Your designer determines the route." }] };
  const shown = buildDeck(c, []).find((i) => i.ref === "part4_design")!;
  c = reducer(c, journeyAnswerAction({ ...item, key: shown.key, title: shown.title }, "designer"));
  const saved = JSON.parse(JSON.stringify(c));
  assert.ok(!saved.facts.some((f) => f.field === "part4_design"));
  assert.ok(!buildDeck(saved, []).some((i) => i.ref === "part4_design"));
  assert.equal(journeyProgress(buildDeck(saved, [], { includeDone: true })).open.designer, 1);
});
