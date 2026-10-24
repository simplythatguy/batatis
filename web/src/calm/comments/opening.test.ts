import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness } from "../../../scripts/component-harness.mjs";

async function opener() {
  const location = { hash: "#/questions" };
  const listeners = new Set<() => void>();
  const observers = new Set<() => void>();
  const timers = new Map<number, () => void>();
  let shown: string | null = null;
  const h = await componentHarness(new URL("./opening.ts", import.meta.url), "useOpenProblem", {}, {
    location,
    document: { body: {}, querySelector: () => shown ? { getAttribute: () => shown } : null },
    window: { addEventListener: (_event, cb) => listeners.add(cb), removeEventListener: (_event, cb) => listeners.delete(cb), setTimeout: (cb) => { timers.set(1, cb); return 1; } },
    clearTimeout: (id) => timers.delete(id),
    MutationObserver: class {
      private callback: () => void;
      constructor(callback: () => void) { this.callback = callback; }
      observe() { observers.add(this.callback); }
      disconnect() { observers.delete(this.callback); }
    },
  });
  return {
    open: h.exports.openCommentsPage,
    location,
    render: (id: string) => { shown = id; for (const cb of observers) cb(); },
    leave: () => { location.hash = "#/review"; for (const cb of listeners) cb(); },
    expire: () => { for (const cb of timers.values()) cb(); },
    assertClean: () => { assert.equal(listeners.size, 0); assert.equal(observers.size, 0); assert.equal(timers.size, 0); },
  };
}

test("the real native opener acknowledges only the captured application rendering", async () => {
  const h = await opener();
  const pending = h.open("case A");
  assert.equal(h.location.hash, "#/comments?case=case%20A");
  h.render("case A");
  assert.equal(await pending, true);
  h.assertClean();
});

test("another application's rendered comments cannot count as success", async () => {
  const h = await opener();
  const pending = h.open("case-A");
  h.render("case-B");
  h.expire();
  assert.equal(await pending, false);
  h.assertClean();
});

test("a newer manual page choice cancels native opening", async () => {
  const h = await opener();
  const pending = h.open("case-A");
  h.leave();
  assert.equal(await pending, false);
  h.assertClean();
});

test("a destination that never renders reports failure and removes its listeners", async () => {
  const h = await opener();
  const pending = h.open("case-A");
  h.expire();
  assert.equal(await pending, false);
  h.assertClean();
});
