import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../../scripts/component-harness.mjs";
import { AccountsError, submitBlockers } from "../../api/accounts.ts";
import { EngineError } from "../../api/client.ts";
import { emptyCase } from "../../intake.ts";
import { preparationGaps } from "../preparation.ts";
import { buildDocument } from "./document.ts";
import { workspaceFixHref } from "./readiness.ts";

async function panel(signingReason = "", fail = false) {
  const c = { ...emptyCase("homebuilder"), authority: "edmonton" };
  const calls: string[] = [];
  const h = await componentHarness(new URL("./SubmitPanel.tsx", import.meta.url), "SubmitPanel", {
    "../../api/accounts": { submitBlockers }, "../../api/client": { EngineError },
    "../../store": { useCase: () => ({ c, gaps: [], engineId: "c1", saveStatus: "saved", submitting: false, checkStatus: "ready", submitDraft: async (id: string) => { calls.push(`submit:${id}`); if (fail) throw new AccountsError(409, "Missing", "409 Missing", { detail: { gaps: [{ id: "new-risk", field: "process.risk", message: "Risk still missing" }] } }); } }) },
    "../account": { useAccount: () => ({ phase: "signed-in" }) }, "../applications": { authorityName: () => "Edmonton" }, "../begin": { useCurrentApplication: () => ({ app: { id: "c1", status: "returned", authority: "edmonton" } }) },
    "../preparation": { preparationGaps }, "../ui": { CIcon: "CIcon", Dot: "Dot" }, "./readiness": { workspaceFixHref }, "../../config": { submissionOfficeReason: () => "" },
  });
  const props = { signingReason, beforeSubmit: async () => { calls.push("flush history"); }, sections: buildDocument(c, []) };
  let tree = await h.render(props);
  return { h, calls, get tree() { return tree; }, async render() { tree = await h.render(props); return tree; } };
}
test("submission waits for workspace edits, retains resubmit wording, and remains gated by signing", async () => {
  const blocked = await panel("Review consent and signatures.");
  assert.equal(nodes(blocked.tree, n => n.type === "button")[0].props.disabled, true);
  assert.match(text(blocked.tree), /Review consent and signatures/);
  blocked.h.unmount();
  const p = await panel();
  const submit = nodes(p.tree, n => n.type === "button")[0];
  assert.match(text(submit), /Resubmit to Edmonton/);
  await submit.props.onClick(); await p.render();
  assert.deepEqual(p.calls, ["flush history", "submit:c1"]);
  p.h.unmount();
});
test("a 409 retains the engine's blocker and Edit links it to the actual paper block", async () => {
  const p = await panel("", true);
  await nodes(p.tree, n => n.type === "button")[0].props.onClick();
  const tree = await p.render();
  assert.match(text(tree), /Risk still missing/);
  assert.equal(nodes(tree, n => n.type === "a" && text(n).includes("Edit"))[0].props.href, "#/application?focus=process.risk_assessment");
  p.h.unmount();
});
