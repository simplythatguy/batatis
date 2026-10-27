/**
 * Opening an application nobody has picked up picks it up (there is no second "Pick up" button on a
 * page the officer is already in). These pin the full flow at the ReviewDetail seam, with the engine
 * and accounts calls stubbed: pending, success, another officer first, a refused claim, a case that
 * isn't the officer's to review, read-only states, and "Stop reviewing" going back to the queue
 * without picking the file straight up again.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../../scripts/component-harness.mjs";
import { workspaceHarness as harness, EngineError, AccountsError, officer as me, workspaceNode, menuItem } from "./tests/workspaceHarness.mjs";

const button = (tree, label: RegExp) => nodes(tree, (n) => n.type === "button" && label.test(text(n)));
test("opening a file nobody has picked up picks it up once and goes straight to the review", async () => {
  const h = await harness({});
  let tree = await h.render({ caseId: "c1" });
  for (let i = 0; i < 3; i++) tree = await h.render();
  assert.equal(h.calls.claim, 1, "claimed exactly once, however often the page renders");
  assert.equal(h.calls.run, 1, "the review then runs by itself");
  assert.equal(Number(Boolean(workspaceNode(tree))), 1, "the review is on screen");
  assert.equal(button(tree, /Pick up/).length, 0, "no second button to start the review");
  h.unmount();
});

test("while the pick-up is pending the page says so, with no Pick up button to press twice", async () => {
  let resolve: (v: unknown) => void = () => {};
  const h = await harness({}, { claim: () => new Promise((r) => { resolve = r; }) });
  let tree = await h.render({ caseId: "c1" });
  assert.match(text(tree), /Opening…/);
  assert.equal(button(tree, /Pick up/).length, 0);
  h.current.status = "in_review";
  h.current.claim = { reviewer_id: me.id, reviewer_name: me.name, claimed_at: "2026-10-22T12:00:00Z" };
  resolve(h.current.claim);
  tree = await h.render();
  tree = await h.render();
  assert.equal(Number(Boolean(workspaceNode(tree))), 1);
  assert.equal(h.calls.claim, 1);
  h.unmount();
});

test("another officer got there first: their name and Take over, no retry loop and no review run", async () => {
  const theirs = { reviewer_id: "riley", reviewer_name: "Riley", claimed_at: "2026-10-22T11:00:00Z" };
  const h = await harness({}, {
    claim: async () => {
      h.current.status = "in_review";
      h.current.claim = theirs;
      throw new AccountsError(409, "Already being reviewed", { claim: theirs });
    },
  });
  let tree = await h.render({ caseId: "c1" });
  for (let i = 0; i < 3; i++) tree = await h.render();
  assert.equal(h.calls.claim, 1, "one attempt, never retried on its own");
  assert.match(text(tree), /Riley is reviewing this/);
  assert.equal(button(tree, /^Take over$/).length, 1, "taking over stays the officer's choice");
  assert.equal(button(tree, /Pick up/).length, 0);
  assert.equal(h.calls.run, 0, "someone else's file is not reviewed by this officer");
  assert.doesNotMatch(text(tree), /No review was run|Someone else is deciding/, "one line says who has it; nothing repeats it");
  h.unmount();
});

test("a refused pick-up shows the server's reason and one Pick up to retry; it never retries by itself", async () => {
  const h = await harness({}, { claim: async () => { throw new AccountsError(404, "case not found"); } });
  let tree = await h.render({ caseId: "c1" });
  for (let i = 0; i < 3; i++) tree = await h.render();
  assert.equal(h.calls.claim, 1, "no effect loop");
  const alert = nodes(tree, (n) => n.props?.role === "alert");
  assert.ok(alert.some((n) => text(n).includes("case not found")), "the API error is shown, not swallowed");
  const retry = button(tree, /Pick up/);
  assert.equal(retry.length, 1, "the bar is the fallback when picking up failed");
  retry[0].props.onClick();
  await h.render();
  assert.equal(h.calls.claim, 2, "retrying is a deliberate press");
  h.unmount();
});

test("a stale page whose file was decided meanwhile: the reason shows and the page settles on the decision", async () => {
  const h = await harness({}, {
    claim: async () => { h.current.status = "accepted"; throw new AccountsError(409, "Only submitted applications may be claimed"); },
  });
  let tree = await h.render({ caseId: "c1" });
  for (let i = 0; i < 3; i++) tree = await h.render();
  assert.equal(h.calls.claim, 1);
  assert.ok(nodes(tree, (n) => n.props?.role === "alert").some((n) => text(n).includes("Only submitted applications may be claimed")));
  assert.equal(button(tree, /Pick up/).length, 0, "nothing left to pick up once the file reloads as decided");
  h.unmount();
});

test("a file that isn't the officer's to review (own case, other authority) never gets a pick-up", async () => {
  const h = await harness({}, { getCase: async () => { throw new EngineError(404); } });
  const tree = await h.render({ caseId: "c1" });
  assert.equal(h.calls.claim, 0);
  assert.match(text(tree), /isn’t available to you/);
  h.unmount();
});

for (const status of ["accepted", "refused", "returned", "withdrawn"]) {
  test(`a ${status} file opens read-only, without a pick-up`, async () => {
    const h = await harness({ status });
    await h.render({ caseId: "c1" });
    await h.render();
    assert.equal(h.calls.claim, 0);
    h.unmount();
  });
}

test("Stop reviewing releases and goes back to the queue, without picking the file straight up again", async () => {
  const h = await harness({ status: "in_review", claim: { reviewer_id: me.id, reviewer_name: me.name, claimed_at: "2026-10-22T12:00:00Z" } });
  let tree = await h.render({ caseId: "c1" });
  const stop = menuItem(tree, "Stop reviewing");
  assert.ok(stop, "the officer can stop reviewing from ⋯");
  stop.onClick();
  tree = await h.render();
  for (let i = 0; i < 3; i++) tree = await h.render();
  assert.equal(h.calls.release, 1);
  assert.equal(h.location.hash, "#/review", "back to the queue");
  assert.equal(h.calls.claim, 0, "no re-pickup loop");
  h.unmount();
});

test("a kept reservation after resubmission waits for Resume review", async () => {
  const h = await harness({ status: "submitted", submission_number: 2, claim: { reviewer_id: me.id, reviewer_name: me.name, claimed_at: "2026-10-22T12:00:00Z" } });
  let tree = await h.render({ caseId: "c1" });
  assert.equal(h.calls.claim, 0); assert.equal(h.calls.run, 0);
  button(tree, /^Resume review$/)[0].props.onClick(); tree = await h.render();
  assert.equal(h.calls.claim, 1); assert.equal(h.calls.run, 1);
  assert.ok(workspaceNode(tree));
  h.unmount();
});

test("older review versions are read-only and never expose a decision foot", async () => {
  const { reviewSession, indexFor } = await import("./tests/workspaceHarness.mjs");
  const latest = reviewSession(3);
  const h = await harness({ status: "in_review", claim: { reviewer_id: me.id, reviewer_name: me.name, claimed_at: "2026-10-22T12:00:00Z" } }, {
    index: async () => indexFor(latest, { sessions: [{ version: 1, required: 2 }, { version: 3, required: 0 }] }),
  });
  let tree = await h.render({ caseId: "c1" });
  const { menuItem } = await import("./tests/workspaceHarness.mjs");
  const version = menuItem(tree, "Version 1");
  assert.ok(version, "earlier versions open from the ⋯ menu"); version.onClick(); tree = await h.render(); tree = await h.render();
  assert.deepEqual([workspaceNode(tree).props.session.version, workspaceNode(tree).props.editable, workspaceNode(tree).props.historical, workspaceNode(tree).props.showDecision], [1, false, true, false]);
  h.unmount();
});
