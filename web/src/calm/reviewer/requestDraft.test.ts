import assert from "node:assert/strict";
import test from "node:test";
import type { ReviewSession } from "../../api/types.gen.ts";
import { draftProblem, draftReducer, editBody, initialDraft, officerItem } from "./requestDraft.ts";

const target = { section: "A" as const, field: "owner_name", label: "Section A · Owner" };
const session: ReviewSession = {
  administrative_only: true, not_a_compliance_determination: true, schema_version: "batatis.package_review.v1", notice: "", authority: "edmonton", case_id: "c", case_version: 1,
  package_id: "c", version: 1, created_at: "2026-10-26T10:00:00Z", created_by_name: "Morgan", input_kind: "case", lookup_skipped: false,
  fields: [], files: [], documents: [], findings: [], dispositions: [], citations: [], section_c: [], diff: null,
  information_request: { intro: "Opening", text: "Server rendering", items: [], edited: false, sent_at: null, sent_by_name: null, message_id: null },
};
const limits = { intro: 20, item_text: 60, items: 3, text: 100 };

test("a PUT carries changed dispositions and exact officer targets", () => {
  let state = draftReducer(initialDraft(session), { type: "add", item: officerItem("Name the owner", target) });
  state = draftReducer(state, { type: "finding", edit: { key: "k", state: "dismissed", reason: "checked", note: "I read page 3." } });
  assert.deepEqual(editBody(state.content), { intro: "Opening", items: [{ text: "Name the owner", included: true, target }], findings: [{ key: "k", state: "dismissed", reason: "checked", note: "I read page 3." }] });
});

test("save adoption preserves typing during the PUT and adopts new item IDs before the next write", () => {
  const item = officerItem("First wording", target);
  let state = draftReducer(initialDraft(session), { type: "add", item });
  state = draftReducer(state, { type: "start" });
  state = draftReducer(state, { type: "item", key: item.key, patch: { text: "Edited while saving" } });
  const saved: ReviewSession = { ...session, information_request: { ...session.information_request, intro: "Canonical opening", items: [{ ...item, id: "ir_server" }], text: "Canonical text" } };
  state = draftReducer(state, { type: "saved", session: saved, at: "now" });
  assert.equal(state.save.kind, "dirty");
  assert.equal(state.content.intro, "Canonical opening");
  assert.equal(state.content.items[0].key, item.key);
  assert.deepEqual(editBody(state.content).items, [{ id: "ir_server", text: "Edited while saving", included: true, target }]);
  state = draftReducer(state, { type: "start" });
  state = draftReducer(state, { type: "saved", session: { ...saved, information_request: { ...saved.information_request, items: [{ ...item, id: "ir_server", text: "Edited while saving" }] } }, at: "later" });
  assert.equal(state.save.kind, "saved");
});

test("new disposition edits stay pending after save; acknowledged changes clear", () => {
  let state = draftReducer(initialDraft(session), { type: "finding", edit: { key: "k", state: "ask" } });
  state = draftReducer(state, { type: "start" });
  state = draftReducer(state, { type: "finding", edit: { key: "k", state: "dismissed", reason: "not_needed", note: "Scope checked" } });
  state = draftReducer(state, { type: "saved", session, at: "now" });
  assert.equal(state.content.findings[0].state, "dismissed");
  state = draftReducer(state, { type: "start" });
  state = draftReducer(state, { type: "saved", session, at: "now" });
  assert.deepEqual(state.content.findings, []);
});

test("failed saves keep the draft and conflicts require an explicit retry", () => {
  let state = draftReducer(initialDraft(session), { type: "intro", value: "My opening" });
  state = draftReducer(state, { type: "failed", message: "The case changed", conflict: true });
  state = draftReducer(state, { type: "intro", value: "Still here" });
  assert.deepEqual(state.save, { kind: "error", message: "The case changed", conflict: true });
  assert.equal(state.content.intro, "Still here");
  assert.equal(draftReducer(state, { type: "retry" }).save.kind, "dirty");
});

test("a dismissal needs only its reason; request limits wait for a valid draft", () => {
  const blocking: ReviewSession = { ...session, findings: [{ key: "k", severity: "blocking" } as never] };
  let state = draftReducer(initialDraft(blocking), { type: "finding", edit: { key: "k", state: "dismissed", reason: null, note: "" } });
  assert.match(draftProblem(state.content, blocking, limits), /Choose why/);
  state = draftReducer(state, { type: "finding", edit: { key: "k", state: "dismissed", reason: "checked", note: "" } });
  assert.equal(draftProblem(state.content, blocking, limits), "", "a required item needs no note, only why");
  state = draftReducer(state, { type: "intro", value: "x".repeat(21) });
  assert.match(draftProblem(state.content, blocking, limits), /20 characters/);
});
