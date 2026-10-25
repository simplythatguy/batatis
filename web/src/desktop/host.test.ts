import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import test from "node:test";
import { desktop, isDesktop, parseInfo, parseOutcome, parseRows } from "./host.ts";

const info = {
  version: "0.1.0", workspace: "dev", platform: "darwin",
  service: { state: "ready", detail: null },
  person: { profile: "reviewer:calgary", name: "Test reviewer, Calgary", kind: "reviewer", authority: "calgary" },
  people: [{ profile: "applicant", name: "Test applicant", kind: "applicant", authority: null }, { profile: "x", name: "Bad", kind: "admin", authority: null }],
  codeDb: { available: false }, voice: "unavailable",
};

test("host info is parsed into the page's own shape and malformed people are dropped", () => {
  const parsed = parseInfo(info);
  assert.equal(parsed?.workspace, "dev");
  assert.equal(parsed?.person?.authority, "calgary");
  assert.deepEqual(parsed?.people.map((p) => p.profile), ["applicant"]);
  assert.equal(parseInfo({ ...info, workspace: "admin" }), null);
  assert.equal(parseInfo({ ...info, service: { state: "running" } }), null);
  assert.equal(parseInfo("ready"), null);
});

test("connection rows show a device code only with an https sign-in address, and never a token", () => {
  const rows = parseRows([
    { id: "a1", kind: "account", label: "Account", description: "d", status: { state: "pending", loginId: "l1", userCode: "ABCD-1234", verificationUrl: "https://example.test/device", token: "secret" } },
    { id: "a2", kind: "account", label: "Account", description: "d", status: { state: "pending", userCode: "ABCD-1234", verificationUrl: "http://example.test/device" } },
    { id: "k1", kind: "key", label: "Key", description: "d", status: { state: "saved", key: "sk-should-not-matter" } },
    { id: "k2", kind: "key", label: "Key", description: "d", status: { state: "leaked" } },
    { id: "a3", kind: "account", label: "Account", description: "d", status: { state: "signed-out", last: { loginId: "l1", result: "cancelled" } } },
  ]);
  assert.deepEqual(rows.map((r) => r.id), ["a1", "k1", "a3"]);
  assert.deepEqual(rows[0].status, { state: "pending", userCode: "ABCD-1234", address: "example.test/device" });
  assert.equal(rows[1].status, "saved");
  assert.deepEqual(rows[2].status, { state: "signed-out", last: "Sign-in cancelled." });
  assert.doesNotMatch(JSON.stringify(rows), /secret|sk-should/);
});

test("outcomes default to a failure with a message", () => {
  assert.deepEqual(parseOutcome({ ok: true }), { ok: true });
  assert.deepEqual(parseOutcome({ ok: false, message: "Something is still running." }), { ok: false, message: "Something is still running." });
  assert.equal(parseOutcome(undefined).ok, false);
});

test("on the web there is no desktop host and nothing it offers can run", async () => {
  assert.equal(isDesktop(), false);
  assert.equal((await desktop.switchPerson("reviewer:calgary")).ok, false);
  assert.deepEqual(await desktop.providers("list"), []);
});

test("the desktop page code names no AI provider; labels come from the host", () => {
  for (const name of readdirSync(new URL(".", import.meta.url))) {
    if (name.endsWith(".test.ts")) continue;
    const source = readFileSync(new URL(name, import.meta.url), "utf8");
    assert.doesNotMatch(source, /jev|typesafe|openai|chatgpt|anthropic|claude|\bgpt/i, name);
  }
});
