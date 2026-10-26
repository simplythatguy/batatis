import assert from "node:assert/strict";
import test from "node:test";
import { emptyCase } from "../../intake.ts";
import { buildDocument } from "./document.ts";
import { groupFlags, officerFlags, signingFlags, workspaceFixHref } from "./readiness.ts";
import type { WorkspaceLoad } from "./useWorkspace.ts";

const ready: WorkspaceLoad = { phase: "ready", basis: "h", note: "", record: { content_hash: "h", consent: { agreed: true, at: "now" }, signers: [{ role: "owner", name: "Ada", required: true }, { role: "owner_rep", name: "Rep", required: false }], signatures: [{ role: "owner", name: "Ada", signed_on: "2026-10-26", method: "typed", image: "data:image/png;base64,eA==", current: true }], history: [] } };
test("consent and only required signers add signing flags; local changes immediately stale a signature", () => {
  assert.deepEqual(signingFlags(ready, true), []);
  assert.deepEqual(signingFlags(ready, false).map(f => f.label), ["Owner signed an older version"]);
  assert.equal(signingFlags({ ...ready, record: { ...ready.record, consent: null, signatures: [] } }, true).length, 2);
  assert.deepEqual(signingFlags({ phase: "failed", record: null, note: "Signing isn’t available on this server." }, false), [], "an unavailable service is not an invented officer finding");
});
test("officer flags reuse every shared gap and Fix opens the block or Sign", () => {
  const c = emptyCase("homebuilder"), gaps = [{ id: "risk", field: "process.risk", label: "Risk missing", href: "#/application?tab=alt&focus=field-risk", severity: "blocking" as const }];
  const sections = buildDocument(c, gaps), signing = signingFlags(ready, false);
  const flags = officerFlags(c, gaps, sections, signing);
  assert.deepEqual(flags.map(f => [f.label, f.href]), [["Risk missing", "#/application?focus=process.risk_assessment"], ["Owner signed an older version", "#/application?step=sign"]]);
  assert.equal(workspaceFixHref(c, sections, { id: "owner", field: "owner_name", href: "#/review" }), "#/application?focus=owner_name");
});
test("the same item asked five times is one row with its count, grouped by what the applicant fixes", () => {
  const same = (n: number) => ({ id: `q-from-c${n}`, label: "Does your design differ from this rule?", href: "#/questions", group: "rules" as const });
  const grouped = groupFlags([same(1), same(2), same(3), { id: "owner", label: "Owner's name", href: "#/a", group: "answers" }, { id: "consent", label: "Consent not given", href: "#/s", group: "signing" }]);
  assert.deepEqual(grouped.map(g => [g.group, g.rows.map(r => [r.label, r.count])]), [
    ["answers", [["Owner's name", 1]]], ["rules", [["Does your design differ from this rule?", 3]]], ["signing", [["Consent not given", 1]]],
  ]);
});
test("one question asked of several articles reads as one row naming the first", () => {
  const ask = (n: number) => ({ id: `q${n}`, label: `Answer whether your design differs from rule 9.27.5.1.(${n})`, href: `#/q${n}`, group: "rules" as const });
  const [rules] = groupFlags([ask(1), ask(2), ask(3)]);
  assert.deepEqual(rules.rows.map(r => [r.label, r.href, r.all.length]), [["Answer whether your design differs from rule 9.27.5.1.(1) and 2 more", "#/q1", 3]]);
});
