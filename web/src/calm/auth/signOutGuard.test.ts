import assert from "node:assert/strict";
import test from "node:test";
import { guardedSignOut, registerSignOutGuard, resetSignOutStatus, signOutStatus } from "./signOutGuard";

test("an account replacement retires a pending voluntary signout and its old save error", async () => {
  resetSignOutStatus();
  let release!: (value: string | null) => void, leaves = 0;
  const waiting = new Promise<string | null>(resolve => { release = resolve; });
  const stop = registerSignOutGuard(() => waiting);
  const result = guardedSignOut(async () => { leaves++; });
  resetSignOutStatus();
  release("Old account private error");
  assert.equal(await result, false);
  assert.equal(leaves, 0);
  assert.deepEqual(signOutStatus(), { pending: false, error: "" });
  stop();
});
