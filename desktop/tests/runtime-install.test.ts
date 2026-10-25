import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";
import { promisify } from "node:util";
import { RuntimeInstaller, type RuntimePin, type InstallerDeps } from "../src/main/runtime-install.ts";
import { codexPin } from "../src/main/codex/install.ts";
import { scratch } from "./helpers.ts";

const exec = promisify(execFile);
const TAR = process.platform === "win32" ? join(process.env.SystemRoot ?? "C:\\Windows", "System32", "tar.exe") : "/usr/bin/tar";
const tar = async (args: string[]) => (await exec(TAR, args, { windowsHide: true })).stdout;
const sha = (bytes: Buffer | string) => createHash("sha256").update(bytes).digest("hex");
const MEMBER = "codex-synthetic-target";
const EXECUTABLE = process.platform === "win32" ? "codex.exe" : "codex";

/** A small release archive made with the system tar, pinned the way release.ts pins the real one. */
async function release(root: string, contents = "synthetic runtime 9.9.9"): Promise<{ pin: RuntimePin; bytes: Buffer }> {
  const source = join(root, "source");
  mkdirSync(source, { recursive: true });
  writeFileSync(join(source, MEMBER), contents);
  const asset = process.platform === "win32" ? "codex-synthetic.exe.zip" : "codex-synthetic.tar.gz";
  const file = join(root, asset);
  await tar([process.platform === "win32" ? "-a" : "-z", "-c", "-f", file, "-C", source, MEMBER]);
  const bytes = readFileSync(file);
  return {
    bytes,
    pin: {
      version: "9.9.9", key: "test-platform", url: "https://github.com/openai/codex/releases/download/rust-v9.9.9/x",
      download: { asset, bytes: bytes.length, sha256: sha(bytes), member: MEMBER }, executable: EXECUTABLE,
      executables: [sha(contents)],
    },
  };
}

function installer(t: { after(fn: () => void): void }, pin: RuntimePin | null, bytes: Buffer, deps: Partial<InstallerDeps> = {}) {
  const root = scratch(t);
  const events: string[] = [];
  const instance = new RuntimeInstaller({
    root, pin, fetch: async () => new Response(bytes), tar, notify: () => events.push(JSON.stringify(instance.status())), log: (line) => events.push(`log:${line}`), ...deps,
  });
  return { instance, root, events, folder: join(root, "runtime", "test-platform") };
}

test("only supported platforms with a known executable digest can install", () => {
  assert.equal(codexPin("linux", "x64"), null);
  assert.equal(codexPin("darwin", "arm64")?.key, "darwin-arm64");
  assert.match(codexPin("win32", "x64")?.url ?? "", /^https:\/\/github\.com\/openai\/codex\/releases\/download\/rust-v/);
});

test("a missing runtime installs from the pinned release, with progress, and stops the old one before the swap", async (t) => {
  const { pin, bytes } = await release(scratch(t));
  const { instance, events, folder } = installer(t, pin, bytes);
  assert.deepEqual(await instance.refresh(), { state: "missing" });
  let stoppedWhileOldInPlace: boolean | null = null;
  const done = await instance.install(async () => { stoppedWhileOldInPlace = !existsSync(join(folder, EXECUTABLE)); });
  assert.deepEqual(done, { state: "installed", version: "9.9.9" });
  assert.equal(stoppedWhileOldInPlace, true);
  assert.equal(readFileSync(join(folder, EXECUTABLE), "utf8"), "synthetic runtime 9.9.9");
  const manifest = JSON.parse(readFileSync(join(folder, "codex-runtime.json"), "utf8"));
  assert.deepEqual(manifest, { version: "9.9.9", platform: "test-platform", archiveSha256: pin.download.sha256, executableSha256: pin.executables[0] });
  assert.ok(events.some((event) => event.includes('"installing"') && event.includes(`"total":${bytes.length}`)));
  assert.deepEqual(await instance.refresh(), { state: "installed", version: "9.9.9" });
});

test("an older runtime reads as outdated and is replaced in place", async (t) => {
  const { pin, bytes } = await release(scratch(t));
  const { instance, folder, root } = installer(t, pin, bytes);
  mkdirSync(folder, { recursive: true });
  writeFileSync(join(folder, EXECUTABLE), "old runtime");
  writeFileSync(join(folder, "codex-runtime.json"), JSON.stringify({ version: "0.1.0" }));
  assert.deepEqual(await instance.refresh(), { state: "outdated", installed: "0.1.0" });
  assert.deepEqual(await instance.install(async () => {}), { state: "installed", version: "9.9.9" });
  assert.equal(readFileSync(join(folder, EXECUTABLE), "utf8"), "synthetic runtime 9.9.9");
  assert.equal(existsSync(`${folder}.old`), false);
  assert.equal(existsSync(`${folder}.next`), false);
  assert.deepEqual(readdirSync(root).sort(), ["runtime"]);
});

for (const [name, change] of [
  ["a tampered archive", (pin: RuntimePin) => ({ ...pin, download: { ...pin.download, sha256: "0".repeat(64) } })],
  ["an executable with an unknown digest", (pin: RuntimePin) => ({ ...pin, executables: ["0".repeat(64)] })],
  ["an archive larger than pinned", (pin: RuntimePin) => ({ ...pin, download: { ...pin.download, bytes: pin.download.bytes - 1 } })],
] as const) {
  test(`${name} is refused before anything running is stopped or replaced`, async (t) => {
    const { pin, bytes } = await release(scratch(t));
    const { instance, folder } = installer(t, change(pin), bytes);
    let stopped = false;
    const failed = await instance.install(async () => { stopped = true; });
    assert.deepEqual(failed, { state: "failed", message: "The download didn’t match the expected file. Try again." });
    assert.equal(stopped, false);
    assert.equal(existsSync(folder), false);
  });
}

test("an archive naming a path outside its folder is refused without extracting", async (t) => {
  const { pin, bytes } = await release(scratch(t));
  const calls: string[][] = [];
  const { instance } = installer(t, pin, bytes, { tar: async (args) => { calls.push(args); return `${MEMBER}\n../outside\n`; } });
  assert.equal((await instance.install(async () => {})).state, "failed");
  assert.deepEqual(calls.map((args) => args[0]), ["-tf"]);
});

test("network failures show a fixed message and keep the earlier runtime", async (t) => {
  const { pin, bytes } = await release(scratch(t));
  const { instance, folder } = installer(t, pin, bytes, { fetch: async () => { throw new TypeError("getaddrinfo ENOTFOUND github.com /private/path"); } });
  mkdirSync(folder, { recursive: true });
  writeFileSync(join(folder, EXECUTABLE), "old runtime");
  const failed = await instance.install(async () => {});
  assert.deepEqual(failed, { state: "failed", message: "The install didn’t finish. Check your connection and free disk space, then try again." });
  assert.equal(readFileSync(join(folder, EXECUTABLE), "utf8"), "old runtime");
  const refused = installer(t, pin, bytes, { fetch: async () => new Response("no", { status: 404 }) });
  assert.match(JSON.stringify(await refused.instance.install(async () => {})), /The download failed \(404\)/);
});

test("unsupported platforms report it and never download", async (t) => {
  let fetched = false;
  const { instance } = installer(t, null, Buffer.alloc(0), { fetch: async () => { fetched = true; return new Response(""); } });
  assert.deepEqual(await instance.refresh(), { state: "unsupported" });
  assert.deepEqual(await instance.install(async () => {}), { state: "unsupported" });
  assert.equal(fetched, false);
});

test("a download that is the executable itself installs without unpacking", async (t) => {
  const contents = Buffer.from("synthetic single-file runtime 9.9.9");
  const pin: RuntimePin = {
    version: "9.9.9", key: "test-platform", url: "https://downloads.example.invalid/9.9.9/test-platform/runtime",
    download: { asset: "runtime", bytes: contents.length, sha256: sha(contents), member: null }, executable: EXECUTABLE, executables: [sha(contents)],
  };
  const calls: string[][] = [];
  const { instance, folder } = installer(t, pin, contents, { tar: async (args) => { calls.push(args); return ""; } });
  assert.deepEqual(await instance.install(async () => {}), { state: "installed", version: "9.9.9" });
  assert.deepEqual(readFileSync(join(folder, EXECUTABLE)), contents);
  assert.deepEqual(calls, [], "nothing is unpacked");
});
