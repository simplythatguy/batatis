import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../scripts/component-harness.mjs";
import { emptyCase } from "../intake.ts";
import * as model from "../model.ts";
import type { Action } from "../model.ts";
import * as config from "../config.ts";
import * as journey from "./journey.ts";
import { aliasKey, buildDeck, gapKey, paperworkRowKey } from "./deck.ts";

async function mounted(extra: Action[] = []) {
  let c = model.reducer(emptyCase(), { type: "setDetail", field: "municipalAddress", value: "10234 87 Ave NW, Edmonton", section: "B" });
  c = model.reducer(c, { type: "setDetail", field: "owner", value: "Dana Whitfield", section: "A" });
  c = model.reducer(c, { type: "setDetail", field: "pathway", value: "alternative", section: "B" });
  c = extra.reduce(model.reducer, c);
  const actions: Action[] = [];
  let done = 0;
  const h = await componentHarness(new URL("./PaperworkSheet.tsx", import.meta.url), "PaperworkSheet", {
    "../store": { useCase: () => ({ c, dispatch: (a: Action) => { actions.push(a); c = model.reducer(c, a); } }) },
    "../model": model, "../config": config, "./journey": journey,
    "../intakeView": await import("../intakeView.ts"),
    "./AuthorityPicker": { AuthorityPicker: "authority-picker" }, "./DatePicker": { DatePicker: "date-picker" },
    "./icons": { Icon24: "icon" }, "./ui": { Dot: "dot" }, "./JurisdictionNote": { JurisdictionNote: "jurisdiction-note" },
  });
  const sheet = () => buildDeck(c, model.getGaps(c), { includeDone: true, today: "2026-10-26", confirmAuthority: true }).find((i) => i.kind === "paperwork")!;
  const render = (focusRow: string | null = null) => h.render({ item: sheet(), focusRow, extras: {}, onDone: () => done++ });
  return { h, render, sheet, actions, case: () => c, done: () => done };
}
const button = (tree, label: string) => nodes(tree, (n) => n.type === "button" && text(n).replace(/default$/, "").trim() === label)[0];
const submit = (tree) => tree.props.onSubmit({ preventDefault() {} });

test("rendering and Done never accept untapped paperwork defaults", async () => {
  const m = await mounted();
  const tree = await m.render();
  for (const label of ["Today", "Same as the site address", "Same as the owner", "No representative"]) assert.ok(button(tree, label), label);
  assert.equal(nodes(tree, (n) => n.type === "button" && n.props.type === "submit").length, 1);
  assert.equal(m.actions.length, 0);
  submit(tree);
  for (const field of ["date", "mailingAddress", "representative"]) assert.equal(model.factFor(m.case(), field), undefined);
  assert.equal(m.actions.length, 0);
  assert.equal(m.done(), 1);
  m.h.unmount();
});

test("Done saves chosen defaults, role and office together; Later remains one honest open row", async () => {
  const m = await mounted();
  let tree = await m.render();
  for (const label of ["Today", "Same as the site address", "Same as the owner"]) button(tree, label).props.onClick();
  button(tree, "Designer or architect").props.onClick({ currentTarget: { closest: () => null } });
  button(tree, "One building site").props.onClick({ currentTarget: { closest: () => null } });
  nodes(tree, (n) => n.type === "button" && n.props["aria-label"] === "Later: Legal description")[0].props.onClick();
  button(tree, "Edmonton").props.onClick();
  assert.equal(m.actions.length, 0, "all edits remain buffered until Done");
  tree = await m.render();
  assert.match(text(tree), /Later/);
  submit(tree);
  const c = JSON.parse(JSON.stringify(m.case()));
  assert.equal(model.factFor(c, "date")?.value, "2026-10-26");
  assert.equal(model.factFor(c, "mailingAddress")?.value, "10234 87 Ave NW, Edmonton");
  assert.equal(model.factFor(c, "representative")?.value, "Dana Whitfield");
  assert.equal(model.factFor(c, "applicant_role")?.value, "designer");
  assert.equal(c.authority, "edmonton");
  assert.equal(config.authorityUnsure(c), false);
  assert.equal(journey.journeyAnswers(c).get("field-legalDescription")?.value, "later");
  assert.ok(model.getGaps(c).some((g) => g.field === "legalDescription"));
  assert.equal(journey.journeyProgress([m.sheet()]).open.you, 1);
  assert.equal(journey.journeyProgress([m.sheet()]).open.batatis, 0);
  assert.equal(m.sheet().done, true, "Later is not automatically asked again");
  assert.equal(m.sheet().paperworkRows?.find((r) => r.key === "authority")?.done, true);
  m.h.unmount();
});

test("field links and gap links resolve to the sheet and focus its requested inline control", async () => {
  const m = await mounted();
  const c = m.case();
  assert.equal(aliasKey(c, "field-legalDescription"), "paperwork");
  assert.equal(paperworkRowKey(c, "field-legalDescription"), "field-legalDescription");
  assert.equal(gapKey(c, { id: "legal", field: "legalDescription", label: "Legal description", severity: "blocking", href: "#/questions?focus=field-legalDescription" }), "field-legalDescription");
  const tree = await m.render();
  let focused = false, scrolled = false;
  tree.props.ref.current = { querySelectorAll: () => [{ dataset: { paperworkRow: "field-legalDescription" }, querySelector: () => ({ focus: () => { focused = true; } }), scrollIntoView: () => { scrolled = true; } }] };
  await m.render("field-legalDescription");
  assert.equal(focused, true);
  assert.equal(scrolled, true);
  m.h.unmount();
});

test("an office Later and a later correction both persist through ordinary case actions", async () => {
  const m = await mounted();
  let tree = await m.render();
  nodes(tree, (n) => n.type === "button" && n.props["aria-label"] === "Later: Office")[0].props.onClick();
  tree = await m.render();
  assert.equal(nodes(tree, (n) => n.type === "authority-picker")[0].props.placeholder, "Later");
  submit(tree);
  assert.equal(journey.journeyAnswers(m.case()).get("authority")?.value, "later");
  assert.equal(config.authorityUnsure(m.case()), true);
  tree = await m.render("authority");
  nodes(tree, (n) => n.type === "authority-picker")[0].props.onPick("edmonton");
  tree = await m.render("authority");
  submit(tree);
  assert.equal(journey.journeyAnswers(m.case()).has("authority"), false);
  assert.equal(config.authorityUnsure(m.case()), false);
  assert.equal(m.case().authority, "edmonton");
  assert.equal(m.sheet().paperworkRows?.find((row) => row.key === "authority")?.done, true);
  m.h.unmount();
});

test("a paperwork row asked by the planner shows and saves its form field, not the question id", async () => {
  let c = emptyCase();
  const questions = ["owner_name", "municipal_address"].map((field) => ({ id: `intake.${field}`, field, text: `${field}?`, why: "Section A.", unblocks: [], splits: [], priority: "administrative" as const, kind: "missing" as const, provision: null }));
  c = { ...c, description: "A house.", facts: [
    { id: "f-owner", field: "owner_name", value: "Dana Whitfield", kind: "pointed", status: "confirmed", confidence: 0.8, source: { type: "user_text", ref: "intake:description", quote: "Dana Whitfield" } },
    { id: "f-site", field: "municipal_address", value: "10234 87 Ave NW, Edmonton", kind: "pointed", status: "confirmed", confidence: 0.8, source: { type: "user_text", ref: "intake:description", quote: "10234 87 Ave NW, Edmonton" } },
  ] as never, intake: { text: "A house.", facts: [], factIds: [], record: {
    ran_at: "2026-10-26", text_sha256: null, pointers: [], files: [], conflicts: [], unresolved_citations: [], model: { status: "off", model: null, reason: null, pointed: 0, proposed: 0, dropped: 0, input_tokens: 0, output_tokens: 0 },
    plan: { next: "questions", scope: { status: "in_scope", regime: null, message: null, cue: null, start: null, end: null, scores: {}, override_allowed: true }, fork: { variance_needed: "unknown", explanation: "", cues: [], halves: [] }, questions, asked: questions, not_sure: [], pre_application: { jurisdiction_id: null, jurisdiction_name: null, resolved_by: null, steps: [] }, route_notice: null, candidates_seen: 0 },
  } } as never };
  const actions: Action[] = [];
  const h = await componentHarness(new URL("./PaperworkSheet.tsx", import.meta.url), "PaperworkSheet", {
    "../store": { useCase: () => ({ c, dispatch: (a: Action) => { actions.push(a); c = model.reducer(c, a); } }) },
    "../model": model, "../config": config, "./journey": journey,
    "../intakeView": await import("../intakeView.ts"), "../intakeFields": await import("../intakeFields.ts"),
    "./AuthorityPicker": { AuthorityPicker: "authority-picker" }, "./DatePicker": { DatePicker: "date-picker" },
    "./icons": { Icon24: "icon" }, "./JurisdictionNote": { JurisdictionNote: "jurisdiction-note" },
  });
  const sheet = buildDeck(c, model.getGaps(c), { includeDone: true, today: "2026-10-26" }).find((i) => i.kind === "paperwork")!;
  const tree = await h.render({ item: sheet, focusRow: null, extras: {}, onDone: () => {} });
  const values = nodes(tree, (n) => n.type === "input").map((n) => n.props.value);
  assert.ok(values.includes("Dana Whitfield") && values.includes("10234 87 Ave NW, Edmonton"), JSON.stringify(values));
  assert.ok(button(tree, "Same as the site address"), "the site address offers itself as the mailing address");
  button(tree, "Same as the site address").props.onClick();
  submit(await h.render({ item: sheet, focusRow: null, extras: {}, onDone: () => {} }));
  assert.ok(actions.every((a) => !("field" in a) || !String(a.field).startsWith("intake.")), "never saved under a question id");
  h.unmount();
});

test("the Office row says Batatis prepares applications only for Calgary and Edmonton", async () => {
  for (const [authority, line] of [
    ["Lacombe County", "Batatis prepares applications only for Calgary and Edmonton."],
    ["Red Deer", "Batatis prepares applications only for Calgary and Edmonton."],
    ["edmonton", ""],
    ["calgary", ""],
  ] as const) {
    const m = await mounted([{ type: "setAuthority", authority }]);
    const office = nodes(await m.render(), (n) => typeof n.props?.className === "string" && n.props.className.startsWith("cf-pw-office"));
    assert.equal(text(office), line, authority);
    m.h.unmount();
  }
});
