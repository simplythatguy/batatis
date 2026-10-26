import assert from "node:assert/strict";
import test from "node:test";
import { desktop, parseConfiguration, parseRows } from "./host.ts";

const sources = [
  { value: "a", label: "Account", models: [{ id: "m1", label: "Model one", efforts: ["low", "high"] }], default: { model: "m1", effort: "low" } },
];

test("model picks are opaque host data: a pick must name a model and effort on the host's menu", () => {
  const configured = { workflow: { source: "a", model: "m1", effort: "high" }, chat: { source: "off" }, screening: false, sources,
    screeningLabel: "Optional screening", help: "Separate billing choices.", note: "" };
  assert.deepEqual(parseConfiguration(configured), configured);
  assert.equal(parseConfiguration({ ...configured, workflow: { source: "a", model: "m1", effort: "medium" } }), null);
  assert.equal(parseConfiguration({ ...configured, chat: { source: "missing", model: "m1", effort: "low" } }), null);
  assert.equal(parseConfiguration({ ...configured, screening: "yes" }), null);
});

test("web has no local model selection and cannot invoke it", async () => {
  assert.equal(await desktop.configuration(), null);
  assert.equal((await desktop.selectModel("chat", { source: "a", model: "m1", effort: "low" })).ok, false);
  assert.equal((await desktop.selectScreening(true)).ok, false);
});

test("account status and workflow readiness stay separate", () => {
  const rows = parseRows([{ id: "a", kind: "account", label: "Account", description: "d", status: { state: "signed-in", plan: null }, workflow: { ready: false, message: "Request context is unverified." } }]);
  assert.equal(rows[0].kind, "account");
  if (rows[0].kind === "account") {
    assert.equal(rows[0].status.state, "signed-in"); assert.equal(rows[0].workflow, "Request context is unverified.");
  }
});
