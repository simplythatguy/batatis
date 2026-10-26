import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness } from "../../../scripts/component-harness.mjs";
import * as requestDraft from "./requestDraft.ts";
import { reviewSession, indexFor, AccountsError } from "./tests/workspaceHarness.mjs";

async function harness(edit: (body: unknown) => Promise<unknown>) {
  let account = 1;
  const saved: unknown[] = [], writes: unknown[] = [];
  let conflicts = 0;
  const timers = new Map<number, () => void>(); let next = 0;
  const h = await componentHarness(new URL("./useRequestDraft.ts", import.meta.url), "useRequestDraft", {
    "../../api/accounts": { AccountsError },
    "../../api/packageReview": { packageReview: { edit: async (_target, _version, body) => { writes.push(body); return edit(body); } } },
    "../account": { accountSession: () => account }, "./requestDraft": requestDraft,
  }, { setTimeout: (fn: () => void) => { const id = ++next; timers.set(id, fn); return id; }, clearTimeout: (id: number) => timers.delete(id),
    window: { addEventListener() {}, removeEventListener() {} } });
  const session = reviewSession(2);
  const props = { target: { kind: "case", id: "c1" }, session, limits: { intro: 2000, item_text: 600, items: 50, text: 6000 }, enabled: true,
    onSaved: (index: unknown) => saved.push(index), onConflict: () => { conflicts++; } };
  return { ...h, props, writes, saved, get conflicts() { return conflicts; }, signOut: () => { account++; },
    fire: () => { const all = [...timers.values()]; timers.clear(); for (const fn of all) fn(); } };
}

test("autosave debounces edits, preserves typing in flight, and adopts the returned gate and preview", async () => {
  let resolve: (index: unknown) => void = () => {};
  const h = await harness(async () => new Promise(r => { resolve = r; }));
  let draft = await h.render(h.props);
  draft.dispatch({ type: "intro", value: "First" }); draft = await h.render();
  draft.dispatch({ type: "intro", value: "Second" }); draft = await h.render();
  assert.equal(h.writes.length, 0);
  h.fire(); draft = await h.render();
  assert.equal(h.writes.length, 1);
  assert.equal(h.writes[0].intro, "Second"); assert.equal(draft.state.save.kind, "saving");
  draft.dispatch({ type: "intro", value: "Typed during PUT" }); draft = await h.render();
  const returned = indexFor({ ...h.props.session, information_request: { ...h.props.session.information_request, intro: "Second", text: "Server rendering: Second" } });
  returned.workspace.gate = { can_accept: false, reason: "The server's new reason" };
  resolve(returned); draft = await h.render();
  assert.equal(draft.state.content.intro, "Typed during PUT");
  assert.equal(draft.pending, true); assert.equal(draft.state.save.kind, "dirty");
  assert.equal(h.saved[0], returned);
  draft = await h.render({ ...h.props, session: returned.latest });
  assert.equal(draft.state.content.intro, "Typed during PUT", "adopting the index must not reset newer typing");
  h.unmount();
});

test("a save conflict keeps the edit, refreshes once, and waits for an explicit retry", async () => {
  const h = await harness(async () => { throw new AccountsError(409, "This request is frozen"); });
  let draft = await h.render(h.props);
  draft.dispatch({ type: "intro", value: "Keep my edit" }); draft = await h.render();
  h.fire(); draft = await h.render();
  assert.equal(draft.state.save.kind, "error"); assert.equal(draft.state.content.intro, "Keep my edit");
  assert.equal(h.conflicts, 1); h.fire(); await h.render(); assert.equal(h.writes.length, 1);
  draft.dispatch({ type: "retry" }); await h.render(); h.fire(); await h.render(); assert.equal(h.writes.length, 2);
  h.unmount();
});

test("a late save cannot publish after the account changes", async () => {
  let resolve: (index: unknown) => void = () => {};
  const h = await harness(async () => new Promise(r => { resolve = r; }));
  let draft = await h.render(h.props);
  draft.dispatch({ type: "intro", value: "An edit" }); draft = await h.render();
  h.fire(); await h.render(); h.signOut(); resolve(indexFor(h.props.session)); await h.render();
  assert.equal(h.saved.length, 0); assert.equal(h.conflicts, 0);
  h.unmount();
});

test("request limit failures retain the server's exact explanation and the unsaved edit", async () => {
  const h = await harness(async () => { throw new AccountsError(422, "Some of what you entered isn’t valid.", { detail: "The request exceeds 6000 characters. Remove an item." }); });
  let draft = await h.render(h.props);
  draft.dispatch({ type: "intro", value: "Keep this wording" }); await h.render(); h.fire(); draft = await h.render();
  assert.equal(draft.state.save.kind, "error");
  assert.equal(draft.state.save.message, "The request exceeds 6000 characters. Remove an item.");
  assert.equal(draft.state.content.intro, "Keep this wording");
  h.unmount();
});
