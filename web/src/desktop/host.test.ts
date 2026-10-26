import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import test from "node:test";
import { desktop, isDesktop, parseInfo, parseOutcome, parseRows, parseUpdate } from "./host.ts";

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
  assert.deepEqual(rows[0].status, { state: "pending", userCode: "ABCD-1234", address: "example.test/device", acceptsCode: false });
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

test("update state keeps GitHub pages only and drops anything the page can't show", () => {
  const release = {
    version: "0.2.0", url: "https://github.com/simplythatguy/batatis/releases/tag/desktop-v0.2.0", history: "https://github.com/simplythatguy/batatis/releases",
    older: 2, downloadable: true,
    notes: [{ version: "0.2.0", url: "https://github.com/simplythatguy/batatis/releases/tag/desktop-v0.2.0", items: ["Add the update button (#81)", 3], more: 4 }],
  };
  assert.deepEqual(parseUpdate({ status: "available", current: "0.1.0", release }), {
    status: "available", current: "0.1.0",
    release: { ...release, notes: [{ ...release.notes[0], items: ["Add the update button (#81)"] }] },
  });
  assert.equal(parseUpdate({ status: "available", current: "0.1.0", release: { ...release, url: "https://example.com/x" } }), null);
  assert.equal(parseUpdate({ status: "available", current: "0.1.0", release: { ...release, url: "javascript:alert(1)" } }), null);
  const downloading = parseUpdate({ status: "downloading", current: "0.1.0", release, percent: 140 });
  assert.equal(downloading?.status === "downloading" && downloading.percent, 100);
  assert.equal(parseUpdate({ status: "ready", current: "0.1.0", release, install: "somewhere" }), null);
  assert.deepEqual(parseUpdate({ status: "failed", current: "0.1.0", release: null, message: "Couldn’t check." }),
    { status: "failed", current: "0.1.0", release: null, message: "Couldn’t check." });
});

test("the account row carries its runtime's install state; malformed progress is dropped", () => {
  const account = { id: "a", kind: "account", label: "Account", description: "", status: { state: "signed-out", last: null }, workflow: null };
  const runtime = (value: unknown) => parseRows([{ ...account, runtime: value }])[0];
  assert.deepEqual(runtime({ state: "installing", received: 5, total: 10 })?.kind === "account" && runtime({ state: "installing", received: 5, total: 10 }).runtime,
    { state: "installing", received: 5, total: 10 });
  const row = runtime({ state: "installing", received: 5, total: 0 });
  assert.equal(row?.kind === "account" && row.runtime, null);
  const outdated = runtime({ state: "outdated", installed: "0.1.0" });
  assert.deepEqual(outdated?.kind === "account" && outdated.runtime, { state: "outdated", installed: "0.1.0" });
  const none = parseRows([account])[0];
  assert.equal(none?.kind === "account" && none.runtime, null);
});

test("a browser sign-in is pending without a code, with its page only when it is https", () => {
  const pending = (verificationUrl: string) => {
    const row = parseRows([{ id: "c", kind: "account", label: "Account", description: "", workflow: null,
      status: { state: "pending", loginId: "l", userCode: "", verificationUrl } }])[0];
    return row?.kind === "account" ? row.status : null;
  };
  assert.deepEqual(pending(""), { state: "pending", userCode: null, address: null, acceptsCode: false });
  assert.deepEqual(pending("https://claude.com/cai/oauth/authorize"), { state: "pending", userCode: null, address: "claude.com/cai/oauth/authorize", acceptsCode: false });
  assert.deepEqual(pending("http://claude.com/x"), { state: "pending", userCode: null, address: null, acceptsCode: false });
});

test("a browser sign-in that offers a pasted code says so; anything but true is no", () => {
  const accepts = (acceptsCode: unknown) => {
    const row = parseRows([{ id: "c", kind: "account", label: "Account", description: "", workflow: null,
      status: { state: "pending", loginId: "l", userCode: "", verificationUrl: "https://claude.com/x", acceptsCode } }])[0];
    return row?.kind === "account" && row.status.state === "pending" ? row.status.acceptsCode : null;
  };
  assert.equal(accepts(true), true);
  assert.equal(accepts("true"), false);
  assert.equal(accepts(undefined), false);
});
