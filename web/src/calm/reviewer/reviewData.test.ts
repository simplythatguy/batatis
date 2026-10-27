import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness } from "../../../scripts/component-harness.mjs";
import { EngineError } from "./tests/workspaceHarness.mjs";

test("the queue uses the server workspace tally and refreshes it when only a disposition changed", async () => {
  let required = 8, reads = 0, gapReads = 0;
  const user = { id: "officer", role: "reviewer", authority: "edmonton" };
  const h = await componentHarness(new URL("./reviewData.ts", import.meta.url), "useQueue", {
    "../../api/accounts": { review: { queue: async () => [{ id: "c1", updated_at: "unchanged" }] }, QueueSessionChanged: class extends Error {} },
    "../../api/client": { EngineError, engine: { gaps: async () => { gapReads++; return []; } } },
    "../../api/packageReview": { packageReview: { index: async () => { reads++; return { workspace: { current: true, tally: { required } } }; } } },
    "../account": { accountSession: () => 1, getAccountState: () => ({ phase: "signed-in", user }), subscribeAccount() {} },
    "../notifications/notifications": { subscribeNotifications() {}, getNotificationsState: () => ({ items: [] }) },
  });
  await h.exports.loadQueue(); let state = await h.render({});
  assert.equal(state.blocking.c1, 8); assert.equal(gapReads, 0);
  required = 2; await h.exports.loadQueue(); state = await h.render();
  assert.equal(state.blocking.c1, 2, "Case.updated_at does not cache away a disposition edit");
  assert.equal(reads, 2);
  h.unmount();
});
