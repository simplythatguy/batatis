import assert from "node:assert/strict";
import test from "node:test";
import { desktop, parseConfiguration, parseRows } from "./host.ts";

test("generation choices are opaque host data, with an explicit selection and separate screening", () => {
  const configured = { generation: "a", screening: false, choices: [{ value: "off", label: "Off" }, { value: "a", label: "Account" }], screeningLabel: "Optional screening", help: "Separate billing choices.", note: "" };
  assert.deepEqual(parseConfiguration(configured), configured);
  assert.equal(parseConfiguration({ ...configured, generation: "missing" }), null);
  assert.equal(parseConfiguration({ ...configured, screening: "yes" }), null);
});

test("web has no local provider selection and cannot invoke it", async () => {
  assert.equal(await desktop.configuration(), null);
  assert.equal((await desktop.selectGeneration("a")).ok, false);
  assert.equal((await desktop.selectScreening(true)).ok, false);
});

test("account status and workflow readiness stay separate", () => {
  const rows = parseRows([{ id: "a", kind: "account", label: "Account", description: "d", status: { state: "signed-in", plan: null }, workflow: { ready: false, message: "Request context is unverified." } }]);
  assert.equal(rows[0].kind, "account");
  if (rows[0].kind === "account") {
    assert.equal(rows[0].status.state, "signed-in"); assert.equal(rows[0].workflow, "Request context is unverified.");
  }
});
