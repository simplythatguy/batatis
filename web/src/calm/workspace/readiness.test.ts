import assert from "node:assert/strict";
import test from "node:test";
import { emptyCase } from "../../intake.ts";
import { buildDocument } from "./document.ts";
import { officerFlags, signingFlags, workspaceFixHref } from "./readiness.ts";
import type { WorkspaceLoad } from "./useWorkspace.ts";

const ready: WorkspaceLoad = { phase: "ready", basis: "h", note: "", record: { content_hash: "h", consent: { agreed: true, at: "now" }, signers: [{ role: "owner", name: "Ada", required: true }, { role: "owner_rep", name: "Rep", required: false }], signatures: [{ role: "owner", name: "Ada", signed_on: "2026-10-26", method: "typed", image: "data:image/png;base64,eA==", current: true }], history: [] } };
test("consent and only required signers add signing flags; local changes immediately stale a signature", () => {
  assert.deepEqual(signingFlags(ready, true), []);
  assert.deepEqual(signingFlags(ready, false).map(f => f.label), ["Owner · changed since signed"]);
  assert.equal(signingFlags({ ...ready, record: { ...ready.record, consent: null, signatures: [] } }, true).length, 2);
  assert.deepEqual(signingFlags({ phase: "failed", record: null, note: "Signing isn’t available on this server." }, false), [], "an unavailable service is not an invented officer finding");
});
test("officer flags reuse every shared gap and Fix opens the block or Sign", () => {
  const c = emptyCase("homebuilder"), gaps = [{ id: "risk", field: "process.risk", label: "Risk missing", href: "#/application?tab=alt&focus=field-risk", severity: "blocking" as const }];
  const sections = buildDocument(c, gaps), signing = signingFlags(ready, false);
  const flags = officerFlags(c, gaps, sections, signing);
  assert.deepEqual(flags.map(f => [f.label, f.href]), [["Risk missing", "#/application?focus=process.risk_assessment"], ["Owner · changed since signed", "#/application?step=sign"]]);
  assert.equal(workspaceFixHref(c, sections, { id: "owner", field: "owner_name", href: "#/review" }), "#/application?focus=owner_name");
});
