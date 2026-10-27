import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, text } from "../../scripts/component-harness.mjs";
import { emptyCase } from "../intake.ts";

test("document review stays hidden without files, including while intake reads", async () => {
  const h = await componentHarness(new URL("./DocumentReview.tsx", import.meta.url), "DocumentReview", {});
  for (const intakeStatus of ["idle", "running", "done", "error"]) {
    const tree = await h.render({ ...emptyCase(), intakeStatus });
    assert.equal(tree, null);
    assert.doesNotMatch(text(tree), /Document review|Not available/);
  }
  h.unmount();
});

test("files keep the running bar, but do not create an unavailable review bar", async () => {
  const h = await componentHarness(new URL("./DocumentReview.tsx", import.meta.url), "DocumentReview", {});
  const c = { ...emptyCase(), files: [{ id: "plans", name: "plans.pdf", read: false }] };
  assert.equal(await h.render({ ...c, intakeStatus: "done" }), null);
  const tree = await h.render({ ...c, intakeStatus: "running" });
  assert.match(text(tree), /Document review/);
  assert.match(text(tree), /Reading…/);
  h.unmount();
});
