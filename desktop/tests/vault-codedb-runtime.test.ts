import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";
import test from "node:test";
import { importCodeDb, inspectCodeDb } from "../src/main/codedb.ts";
import { KeyVault, type SecretBox } from "../src/main/credentials.ts";
import { engineCommand } from "../src/main/runtime.ts";
import { REPO, scratch } from "./helpers.ts";

const KEY = "sk-test-SYNTHETIC-not-a-real-key-0001";
const sealing: SecretBox = { available: async () => true, encrypt: async (plain) => Buffer.from(plain, "utf8").map((b) => b ^ 0x5a) };
const locked: SecretBox = { available: async () => false, encrypt: async () => { throw new Error("unavailable"); } };

test("a saved key is sealed, reported only as saved, and removable", async (t) => {
  const dir = scratch(t);
  const vault = new KeyVault(dir, sealing);
  assert.equal(await vault.status("openai"), "missing");
  assert.equal(await vault.save("openai", `  ${KEY}\n`), "saved");
  assert.equal(await vault.status("openai"), "saved");
  assert.equal(await vault.status("jev"), "missing");
  const stored = readFileSync(join(dir, "openai.key"));
  assert.ok(!stored.toString("latin1").includes(KEY), "never stored in the clear");
  await vault.remove("openai");
  assert.equal(await vault.status("openai"), "missing");
});

test("without OS encryption a key is refused and nothing is written", async (t) => {
  const dir = scratch(t);
  const vault = new KeyVault(dir, locked);
  assert.equal(await vault.save("jev", KEY), "secure-storage-unavailable");
  assert.equal(await vault.status("jev"), "secure-storage-unavailable");
  assert.deepEqual(readdirSync(dir), []);
});

test("listing missing or saved keys reads metadata without initializing the OS keyring", async (t) => {
  const dir = scratch(t);
  let lookups = 0;
  const vault = new KeyVault(dir, {
    available: async () => { lookups += 1; return true; },
    encrypt: async (value) => sealing.encrypt(value),
  });
  assert.equal(await vault.status("openai"), "missing");
  writeFileSync(join(dir, "openai.key"), Buffer.from("synthetic sealed bytes"));
  assert.equal(await vault.status("openai"), "saved");
  assert.equal(lookups, 0, "opening settings must not wait for a Keychain access prompt");
});

test("an OS encryption failure preserves the earlier sealed key and permits a later retry", async (t) => {
  const dir = scratch(t);
  let fail = false;
  const vault = new KeyVault(dir, { available: async () => true, encrypt: async (value) => {
    if (fail) throw new Error("Keychain access was denied");
    return sealing.encrypt(value);
  } });
  assert.equal(await vault.save("openai", KEY), "saved");
  const earlier = readFileSync(join(dir, "openai.key"));
  fail = true;
  assert.equal(await vault.save("openai", `${KEY}-replacement`), "secure-storage-unavailable");
  assert.equal(await vault.status("openai"), "secure-storage-unavailable");
  assert.deepEqual(readFileSync(join(dir, "openai.key")), earlier);
  assert.equal(existsSync(join(dir, "openai.key.partial")), false);
  fail = false;
  assert.equal(await vault.save("openai", `${KEY}-replacement`), "saved");
  assert.equal(await vault.status("openai"), "saved");
});

test("text that cannot be a key is refused before it is sealed", async (t) => {
  const vault = new KeyVault(scratch(t), sealing);
  for (const value of ["", "short", "has spaces in the middle of it", "tab\tinside-the-key-value", "x".repeat(600)]) {
    assert.equal(await vault.save("openai", value), "invalid", JSON.stringify(value));
  }
});

function fakeCodeDb(file: string, { build = "2", label = "NBC(AE) 2023 p2" } = {}) {
  const db = new DatabaseSync(file);
  db.exec("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT); CREATE TABLE docs (doc TEXT, label TEXT, kind TEXT, citable INTEGER);"
    + "CREATE TABLE provisions (id TEXT); CREATE VIRTUAL TABLE provisions_fts USING fts5(text); CREATE TABLE attributions (x);"
    + "CREATE TABLE definitions (x); CREATE TABLE intents (x);");
  db.prepare("INSERT INTO meta VALUES ('build_version', ?)").run(build);
  db.prepare("INSERT INTO docs VALUES ('NBC-AE', ?, 'code', 1)").run(label);
  db.close();
}

test("only a code database of the expected build and the 2023 2nd printing is accepted", (t) => {
  const dir = scratch(t);
  const good = join(dir, "good.sqlite");
  fakeCodeDb(good);
  assert.deepEqual(inspectCodeDb(good, "2"), { ok: true, build: "2" });
  const cases: [string, Parameters<typeof fakeCodeDb>[1]][] = [["old-build", { build: "1" }], ["first-printing", { label: "NBC(AE) 2023 p1" }], ["2019", { label: "NBC(AE) 2019 p2" }]];
  for (const [name, options] of cases) {
    const file = join(dir, `${name}.sqlite`);
    fakeCodeDb(file, options);
    assert.equal(inspectCodeDb(file, "2").ok, false, name);
  }
  writeFileSync(join(dir, "text.sqlite"), "not a database at all");
  assert.equal(inspectCodeDb(join(dir, "text.sqlite"), "2").ok, false);
  const repoDb = join(REPO, "codedb", "build", "codedb.sqlite");
  if (existsSync(repoDb)) assert.equal(inspectCodeDb(repoDb, "2").ok, true, "the checkout's real build passes");
});

test("a rejected import leaves the active code database untouched", async (t) => {
  const dir = scratch(t);
  const active = join(dir, "codedb", "codedb.sqlite");
  const good = join(dir, "good.sqlite");
  fakeCodeDb(good);
  const first = await importCodeDb(good, active, "2");
  assert.equal(first.ok, true);
  const before = readFileSync(active);
  const bad = join(dir, "bad.sqlite");
  fakeCodeDb(bad, { build: "9" });
  assert.equal((await importCodeDb(bad, active, "2")).ok, false);
  assert.deepEqual(readFileSync(active), before);
  assert.equal(existsSync(`${active}.partial`), false);
});

test("the engine gets only fixed paths and an allow-listed environment", () => {
  const parent = {
    PATH: "/usr/bin", OPENAI_API_KEY: "sk-live", JEV_API_KEY: "jev", VERCEL: "1", DATABASE_URL: "postgres://x", ELECTRON_RUN_AS_NODE: "1",
    BATATIS_REVIEWER_CODES: "{}", HOME: "/Users/someone", TMPDIR: "/tmp/x", SYSTEMROOT: "C:\\Windows",
  };
  const paths = { userData: "/data/Batatis", resources: "/Applications/Batatis.app/Contents/Resources", packaged: true, platform: "darwin" as const };
  const command = engineCommand(paths, "dev", parent);
  assert.equal(command.command, join(paths.resources, "engine", "batatis-engine"));
  assert.deepEqual(command.args, []);
  for (const name of ["OPENAI_API_KEY", "JEV_API_KEY", "VERCEL", "DATABASE_URL", "ELECTRON_RUN_AS_NODE", "BATATIS_REVIEWER_CODES", "PATH"]) {
    assert.equal(command.env[name], undefined, name);
  }
  assert.equal(command.env.HOME, join(paths.userData, "engine-home"));
  assert.equal(command.env.BATATIS_CASES, join(paths.userData, "workspaces", "dev", "cases.sqlite"));
  assert.equal(command.env.BATATIS_CODEDB, join(paths.userData, "codedb", "codedb.sqlite"));
  assert.equal(command.env.BATATIS_LIVE, "0");
  assert.equal(command.env.TMPDIR, "/tmp/x");
  const windows = engineCommand({ ...paths, platform: "win32", resources: "C:\\Program Files\\Batatis\\resources" }, "local", parent);
  assert.match(windows.command, /batatis-engine\.exe$/);
});
