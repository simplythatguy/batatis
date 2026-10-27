import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness } from "../../scripts/component-harness.mjs";

function storage() {
  const values = new Map<string, string>();
  return {
    values,
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value); },
    removeItem: (key: string) => { values.delete(key); },
  };
}

test("the Start draft and intent survive a reload; files need reattaching and case state stays visit-local", async () => {
  const sessionStorage = storage();
  const globals = { sessionStorage, localStorage: { setItem() { assert.fail("case content must never use localStorage"); } } };
  const first = await componentHarness(new URL("./session.ts", import.meta.url), "getSession", { "./applicationEditing": { applicationEditsPaused: () => false } }, globals);
  const file = new File(["plan"], "private-plan.png", { type: "image/png" });
  first.exports.updateSession({ draft: "A rear addition", draftFiles: [{ id: "plan", file }], startRequested: true, queue: ["private-answer"], held: [{ id: "other", file }] });
  const second = await componentHarness(new URL("./session.ts", import.meta.url), "getSession", { "./applicationEditing": { applicationEditsPaused: () => false } }, globals);
  const restored = second.exports.getSession();
  assert.equal(restored.draft, "A rear addition");
  assert.equal(restored.startRequested, true);
  assert.equal(restored.draftFilesLost, true);
  assert.deepEqual(Array.from(restored.draftFiles), []);
  assert.deepEqual(Array.from(restored.queue), []);
  assert.deepEqual(Array.from(restored.held), []);
  assert.doesNotMatch([...sessionStorage.values.values()].join(""), /private-plan|private-answer|image\/png/);
  second.exports.resetSession();
  const third = await componentHarness(new URL("./session.ts", import.meta.url), "getSession", { "./applicationEditing": { applicationEditsPaused: () => false } }, globals);
  assert.equal(third.exports.getSession().draft, "");
  assert.equal(third.exports.getSession().startRequested, false);
  assert.equal(sessionStorage.values.size, 0, "starting or clearing removes the stored draft");
});

test("a text-only OAuth draft can continue, and unavailable storage keeps the page usable", async () => {
  const sessionStorage = storage();
  const first = await componentHarness(new URL("./session.ts", import.meta.url), "getSession", { "./applicationEditing": { applicationEditsPaused: () => false } }, { sessionStorage });
  first.exports.updateSession({ draft: "Two-storey infill", startRequested: true });
  const reloaded = await componentHarness(new URL("./session.ts", import.meta.url), "getSession", { "./applicationEditing": { applicationEditsPaused: () => false } }, { sessionStorage });
  assert.equal(reloaded.exports.getSession().draft, "Two-storey infill");
  assert.equal(reloaded.exports.getSession().draftFilesLost, false);
  const unavailable = await componentHarness(new URL("./session.ts", import.meta.url), "getSession", { "./applicationEditing": { applicationEditsPaused: () => false } }, {
    sessionStorage: { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); }, removeItem() { throw new Error("blocked"); } },
  });
  assert.doesNotThrow(() => unavailable.exports.updateSession({ draft: "Still editable" }));
  assert.equal(unavailable.exports.getSession().draft, "Still editable");
});
