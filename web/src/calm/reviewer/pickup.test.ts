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
import * as packageView from "./packageView.ts";
import * as queue from "./queue.ts";
import * as threadMessages from "./threadMessages.ts";

class EngineError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail = "Synthetic failure") { super(detail); this.status = status; this.detail = detail; }
}
class AccountsError extends EngineError {
  body: unknown;
  constructor(status: number, detail: string, body: unknown = null) { super(status, detail); this.body = body; }
}

const me = { id: "officer", name: "Morgan" };
const session = (version: number) => ({ package_id: "c1", version, case_version: 1, findings: [], information_request: { items: [] } });

type Case = { id: string; title: string; status: string; version: number; claim: null | { reviewer_id: string; reviewer_name: string; claimed_at: string } };

async function harness(start: Partial<Case>, opts: { claim?: () => Promise<unknown>; getCase?: () => Promise<unknown> } = {}) {
  const current: Case = { id: "c1", title: "Synthetic pick-up", status: "submitted", version: 1, claim: null, ...start };
  const calls = { claim: 0, release: 0, run: 0 };
  let reviewed: ReturnType<typeof session> | null = null;
  const location = { hash: "#/review/c1" };
  const claimed = async () => {
    current.status = "in_review";
    current.claim = { reviewer_id: me.id, reviewer_name: me.name, claimed_at: "2026-10-22T12:00:00Z" };
    return current.claim;
  };
  const h = await componentHarness(new URL("./ReviewDetail.tsx", import.meta.url), "ReviewDetail", {
    "../../api/client": { EngineError, engine: { getCase: opts.getCase ?? (async () => ({ ...current })), gaps: async () => [] } },
    "../../api/accounts": {
      AccountsError,
      accounts: { messages: async () => [] },
      claimConflict: (e: unknown) => (e instanceof AccountsError && e.status === 409 ? (e.body as { claim?: Case["claim"] })?.claim ?? null : null),
      review: {
        claim: async () => { calls.claim++; return (opts.claim ?? claimed)(); },
        release: async () => { calls.release++; current.status = "submitted"; current.claim = null; },
      },
    },
    "../../api/packageReview": { packageReview: {
      index: async () => ({ latest: reviewed, sessions: reviewed ? [reviewed] : [], close_out: null }),
      run: async () => { calls.run++; reviewed = session(1); return reviewed; },
    } },
    "../account": { useAccount: () => ({ user: me }), accountSession: () => "officer-session" },
    // The page reads the case, its gaps, questions and thread as one snapshot (reviewSnapshot.ts).
    "./reviewSnapshot": { readReviewSnapshot: async () => ({ c: await (opts.getCase ?? (async () => ({ ...current })))(), gaps: [], information: null, messages: [], gapError: "", questionError: "" }) },
    "./threadMessages": threadMessages,
    "./sheet": { sheetFromEngine: () => ({ questions: [] }) },
    "./reviewData": { useQueue: () => ({ rows: [] }), setBlocking() {}, patchRow() {}, loadQueue: async () => {} },
    "./queue": queue,
    "./packageView": packageView,
    "./PackageReview": { PackageReview: "PackageReview", StepTitle: "StepTitle" },
    "../shell/MoreMenu": { MoreMenu: "MoreMenu" },
    "./InfoRequest": { InfoRequest: "InfoRequest" },
  }, { window: { location } });
  return { ...h, calls, current, location };
}

const button = (tree, label: RegExp) => nodes(tree, (n) => n.type === "button" && label.test(text(n)));
const menuItem = (tree, label: string) => {
  const head = nodes(tree, (n) => n.props?.right)[0];
  return nodes(head.props.right, (n) => n.type === "MoreMenu")[0]?.props.items.find((i) => i.label === label);
};

test("opening a file nobody has picked up picks it up once and goes straight to the review", async () => {
  const h = await harness({});
  let tree = await h.render({ caseId: "c1" });
  for (let i = 0; i < 3; i++) tree = await h.render();
  assert.equal(h.calls.claim, 1, "claimed exactly once, however often the page renders");
  assert.equal(h.calls.run, 1, "the review then runs by itself");
  assert.equal(nodes(tree, (n) => n.type === "PackageReview").length, 1, "the review is on screen");
  assert.equal(button(tree, /Pick up/).length, 0, "no second button to start the review");
  h.unmount();
});

test("while the pick-up is pending the page says so, with no Pick up button to press twice", async () => {
  let resolve: (v: unknown) => void = () => {};
  const h = await harness({}, { claim: () => new Promise((r) => { resolve = r; }) });
  let tree = await h.render({ caseId: "c1" });
  assert.match(text(tree), /Opening the review…/);
  assert.equal(button(tree, /Pick up/).length, 0);
  h.current.status = "in_review";
  h.current.claim = { reviewer_id: me.id, reviewer_name: me.name, claimed_at: "2026-10-22T12:00:00Z" };
  resolve(h.current.claim);
  tree = await h.render();
  tree = await h.render();
  assert.equal(nodes(tree, (n) => n.type === "PackageReview").length, 1);
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
