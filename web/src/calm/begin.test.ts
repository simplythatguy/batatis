import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness } from "../../scripts/component-harness.mjs";
import { emptyCase } from "../intake.ts";
import { reducer, type Action } from "../model.ts";
import { getSession, resetSession } from "./session.ts";

test("begin starts a files-only application without assuming the account's applicant type", async () => {
  const file = new File(["plan"], "plan.png", { type: "image/png" });
  resetSession({ draftFiles: [{ id: "plan", file }], startRequested: true });
  let c = emptyCase("manufacturer");
  const location = { hash: "#/" };
  const h = await componentHarness(new URL("./begin.ts", import.meta.url), "useBegin", {
    "../store": { useCase: () => ({ beginEmpty: (role: Parameters<typeof emptyCase>[0]) => { c = emptyCase(role); }, dispatch: (action: Action) => { c = reducer(c, action); } }) },
    "./account": { useAccount: () => ({ phase: "signed-in", user: { role: "applicant", onboarded: true, applicant_type: "manufacturer" } }) },
    "./session": { getSession, resetSession },
  }, { location });
  const hook = await h.render();
  assert.equal(hook.begin(), true);
  assert.equal(c.applicantType, null);
  assert.equal(c.title, "New application");
  assert.equal(c.description, "");
  assert.deepEqual(c.files.map((f) => [f.id, f.name]), [["plan", "plan.png"]]);
  assert.equal(getSession().held[0]?.file, file);
  assert.equal(getSession().readAfterStart, true);
  assert.equal(getSession().startRequested, false);
  assert.equal(location.hash, "#/questions");
  resetSession();
});

test("begin accepts a description, rejects empty or lost-file drafts, and waits for sign-in", async () => {
  let starts = 0;
  const account = { phase: "signed-out", user: null };
  const h = await componentHarness(new URL("./begin.ts", import.meta.url), "useBegin", {
    "../store": { useCase: () => ({ beginEmpty() { starts++; }, dispatch() {} }) },
    "./account": { useAccount: () => account },
    "./session": { getSession, resetSession },
  }, { location: { hash: "#/" } });
  resetSession({ draft: "My addition" });
  assert.equal((await h.render()).begin(), false);
  account.phase = "anonymous";
  resetSession();
  assert.equal((await h.render()).begin(), false);
  resetSession({ draft: "My addition", draftFilesLost: true });
  assert.equal((await h.render()).begin(), false);
  resetSession({ draft: "My addition" });
  assert.equal((await h.render()).begin(), true);
  assert.equal(starts, 1);
  resetSession();
});
