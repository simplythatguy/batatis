import assert from "node:assert/strict";
import test from "node:test";
import { saveBeforeSwitch, type VisitState } from "./switching.ts";

const idle: VisitState = { phase: "case", saveStatus: "saved", submitting: false, submissionDispatched: false, uploading: 0, held: 0, unstarted: false };

function deps(state: Partial<VisitState>, save: { id: string | null; acknowledged: boolean; after?: Partial<VisitState> } = { id: "case_1", acknowledged: true }) {
  let current: VisitState = { ...idle, ...state };
  let saves = 0;
  return {
    get saves() { return saves; },
    read: () => current,
    saveDraft: async () => {
      saves += 1;
      current = { ...current, ...(save.after ?? {}) };
      return save.id;
    },
    saved: () => save.acknowledged,
  };
}

test("unsaved answers are saved and acknowledged before the switch goes ahead", async () => {
  const d = deps({ saveStatus: "unsaved" });
  assert.equal(await saveBeforeSwitch(d), null);
  assert.equal(d.saves, 1);
});

test("a save the engine did not acknowledge keeps the current person", async () => {
  for (const save of [{ id: null, acknowledged: false }, { id: "case_1", acknowledged: false }]) {
    const d = deps({ saveStatus: "failed" }, save);
    assert.match((await saveBeforeSwitch(d)) ?? "", /didn’t save/);
  }
});

test("nothing is saved again when the application is already saved", async () => {
  const d = deps({ saveStatus: "saved" });
  assert.equal(await saveBeforeSwitch(d), null);
  assert.equal(d.saves, 0);
});

test("a submission, an upload or files waiting for their application hold the switch", async () => {
  assert.match((await saveBeforeSwitch(deps({ submitting: true }))) ?? "", /submission/);
  assert.match((await saveBeforeSwitch(deps({ submissionDispatched: true }))) ?? "", /submission/);
  assert.match((await saveBeforeSwitch(deps({ uploading: 1 }))) ?? "", /upload/);
  const held = deps({ saveStatus: "unsaved", held: 2 }, { id: "case_1", acknowledged: true, after: { held: 2 } });
  assert.match((await saveBeforeSwitch(held)) ?? "", /uploading/);
  assert.equal(held.saves, 1, "the save that creates the application still runs first");
});

test("an unstarted description and a gone application are never silently dropped", async () => {
  assert.match((await saveBeforeSwitch(deps({ phase: "who", saveStatus: "idle", unstarted: true }))) ?? "", /Start or clear/);
  assert.equal(await saveBeforeSwitch(deps({ phase: "who", saveStatus: "idle", unstarted: false })), null);
  const gone = deps({ saveStatus: "gone" });
  assert.match((await saveBeforeSwitch(gone)) ?? "", /can’t be saved/);
  assert.equal(gone.saves, 0);
});
