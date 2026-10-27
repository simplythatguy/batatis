import assert from "node:assert/strict";
import { execFile, spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { promisify } from "node:util";
import {
  archiveName, channelOf, expectedSum, installedApp, keepUninstaller, launchCommand, newer, noteItem, onlyApp, readReleases, swapCommand, trustedUpdateUrl, Updater,
  type UpdaterDeps,
} from "../src/main/updates.ts";
import { scratch, waitFor } from "./helpers.ts";

const exec = promisify(execFile);
const run = async (command: string, args: string[]) => (await exec(command, args, { windowsHide: true })).stdout;
const PAGE = "https://github.com/simplythatguy/batatis/releases/tag";
const DOWNLOAD = "https://github.com/simplythatguy/batatis/releases/download";

const GENERATED = `## What's Changed
* Add the update button by @someone in https://github.com/simplythatguy/batatis/pull/81
* Fix the [export](https://example.com) title by @someone in https://github.com/simplythatguy/batatis/pull/82

**Full Changelog**: https://github.com/simplythatguy/batatis/compare/desktop-v0.1.0...desktop-v0.2.0`;

const size = (bytes: Uint8Array | string) => (typeof bytes === "string" ? Buffer.byteLength(bytes) : bytes.byteLength);

function release(version: string, extra: Record<string, unknown> = {}, files: Record<string, Uint8Array | string> = {
  [`Batatis-${version}-mac-arm64.zip`]: "", [`Batatis-${version}-win-x64.zip`]: "", SHA256SUMS: "",
}) {
  return {
    tag_name: `v${version}`, html_url: `${PAGE}/v${version}`, draft: false, prerelease: version.includes("-beta."), body: GENERATED,
    assets: Object.entries(files).map(([name, bytes]) => ({ name, size: size(bytes), browser_download_url: `${DOWNLOAD}/v${version}/${name}` })),
    ...extra,
  };
}

test("versions compare numerically; a stable X.Y.Z sorts after its betas, and betas by date then run", () => {
  assert.equal(newer("0.2.0", "0.2.0-beta.20261026.40"), true);
  assert.equal(newer("0.2.0-beta.20261027.1", "0.2.0-beta.20261026.40"), true);
  assert.equal(newer("0.2.0-beta.20261026.41", "0.2.0-beta.20261026.40"), true);
  assert.equal(newer("0.2.0-beta.20261026.40", "0.1.9"), true);
  assert.equal(newer("0.1.9", "0.2.0-beta.20261026.40"), false);
  assert.equal(channelOf("0.2.0-beta.20261026.40"), "beta");
  assert.equal(channelOf("0.2.0"), "stable");
});

test("versions compare numerically and only plain x.y.z counts", () => {
  assert.equal(newer("0.10.0", "0.9.9"), true);
  assert.equal(newer("0.1.0", "0.1.0"), false);
  assert.equal(newer("1.0.0-beta.1", "0.1.0"), false);
  assert.equal(archiveName("0.2.0", "darwin", "arm64"), "Batatis-0.2.0-mac-arm64.zip");
  assert.equal(archiveName("0.2.0", "win32", "x64"), "Batatis-0.2.0-win-x64.zip");
  assert.equal(archiveName("0.2.0", "linux", "x64"), null);
});

test("generated notes read as plain items with pull request numbers", () => {
  assert.equal(noteItem("* Add the update button by @someone in https://github.com/simplythatguy/batatis/pull/81"), "Add the update button (#81)");
  assert.equal(noteItem("- **Bold** [link](https://example.com) `code`"), "Bold link code");
  assert.equal(noteItem("* **Full Changelog**: https://github.com/x/y/compare/a...b"), null);
  assert.equal(noteItem(`* ${"x".repeat(400)}`)?.length, 220);
});

test("the newest desktop release wins; drafts, prereleases, other tags and older versions are ignored", () => {
  const found = readReleases([
    release("0.3.0", { draft: true }),
    release("0.2.5", { prerelease: true }),
    { ...release("9.9.9"), tag_name: "desktop-v9.9.9" },
    { ...release("0.2.6"), prerelease: true },
    release("0.1.0"),
    release("0.2.0"),
    release("0.1.1"),
  ], "0.1.0", "darwin", "arm64");
  assert.ok(found);
  assert.equal(found.version, "0.2.0");
  assert.deepEqual(found.notes.map((note) => note.version), ["0.2.0", "0.1.1"]);
  assert.deepEqual(found.notes[0].items, ["Add the update button (#81)", "Fix the export title (#82)"]);
  assert.equal(found.archive?.name, "Batatis-0.2.0-mac-arm64.zip");
  assert.equal(found.sums, `${DOWNLOAD}/v0.2.0/SHA256SUMS`);
  assert.equal(readReleases([release("0.1.0")], "0.1.0", "darwin", "arm64"), null);
  assert.throws(() => readReleases({ message: "rate limited" }, "0.1.0", "darwin", "arm64"));
});

test("long histories keep five note groups, cap items and count the rest", () => {
  const many = Array.from({ length: 12 }, (_, i) => `* change ${i}`).join("\n");
  const found = readReleases(Array.from({ length: 7 }, (_, i) => release(`0.${i + 2}.0`, { body: many })), "0.1.0", "win32", "x64");
  assert.ok(found);
  assert.equal(found.version, "0.8.0");
  assert.equal(found.notes.length, 5);
  assert.equal(found.notes[0].items.length, 8);
  assert.equal(found.notes[0].more, 4);
  assert.equal(found.older, 2);
  assert.equal(found.archive?.name, "Batatis-0.8.0-win-x64.zip");
});

test("a release without this platform's archive is shown but not offered as a download", () => {
  const found = readReleases([release("0.2.0", {}, { "Batatis-0.2.0-win-x64.zip": "", SHA256SUMS: "" })], "0.1.0", "darwin", "arm64");
  assert.equal(found?.archive, null);
});

test("only the repository's releases API and release downloads are fetched", () => {
  assert.equal(trustedUpdateUrl(new URL("https://api.github.com/repos/simplythatguy/batatis/releases?per_page=30")), true);
  assert.equal(trustedUpdateUrl(new URL(`${DOWNLOAD}/v0.2.0/SHA256SUMS`)), true);
  assert.equal(trustedUpdateUrl(new URL("https://github.com/someone/else/releases/download/x/y")), false);
  assert.equal(trustedUpdateUrl(new URL("http://github.com/simplythatguy/batatis/releases/download/x/y")), false);
  assert.equal(trustedUpdateUrl(new URL("https://api.github.com/repos/simplythatguy/batatis/contents")), false);
  assert.equal(expectedSum(`${"a".repeat(64)}  other.zip\n${"B".repeat(64)} *Batatis.zip\n`, "Batatis.zip"), "b".repeat(64));
});

test("the installed app is the bundle on macOS and the executable's folder on Windows", () => {
  assert.equal(installedApp("/Applications/Batatis.app/Contents/MacOS/Batatis", "darwin"), "/Applications/Batatis.app");
  assert.equal(installedApp("/usr/local/bin/electron", "darwin"), null);
  assert.equal(launchCommand("darwin", "/Applications/Batatis.app")[0], "/usr/bin/open");
});

/** A releases feed and downloads served from memory, through the same Response type net.fetch returns. */
function feed(files: Record<string, Uint8Array | string>, releases: unknown[]) {
  const requested: string[] = [];
  const fetch: UpdaterDeps["fetch"] = async (url) => {
    requested.push(url);
    if (url.startsWith("https://api.github.com/")) return Response.json(releases);
    const name = url.split("/").pop() ?? "";
    return name in files ? new Response(files[name]) : new Response("missing", { status: 404 });
  };
  return { fetch, requested };
}

function updater(t: { after(fn: () => void): void }, deps: Partial<UpdaterDeps>) {
  const dir = scratch(t);
  const events: string[] = [];
  const instance = new Updater({
    current: "0.1.0", platform: process.platform, arch: process.arch, feed: "https://api.github.com/repos/simplythatguy/batatis/releases?per_page=30",
    trusted: trustedUpdateUrl, fetch: async () => new Response("unused"), dir: join(dir, "updates"), executable: join(dir, "missing"),
    replaceable: false, run, notify: () => events.push("changed"), log: (line) => events.push(`log:${line}`), ...deps,
  });
  return { instance, dir, events };
}

const sha = (bytes: Uint8Array | string) => createHash("sha256").update(bytes).digest("hex");

test("a download that matches its checksum is kept; a development run shows it instead of replacing anything", async (t) => {
  const name = archiveName("0.2.0", process.platform, process.arch) ?? "Batatis-0.2.0-other.zip";
  const zip = new TextEncoder().encode("archive bytes");
  const sums = `${sha(zip)}  ${name}\n`;
  const files = { [name]: zip, SHA256SUMS: sums };
  const { fetch } = feed(files, [release("0.2.0", {}, files)]);
  const { instance, events } = updater(t, { fetch, platform: process.platform === "win32" ? "win32" : "darwin" });
  assert.equal((await instance.check()).status, "available");
  const ready = await instance.download();
  assert.equal(ready.status, "ready");
  assert.equal(ready.status === "ready" && ready.install, "manual");
  const staged = instance.staged();
  assert.equal(staged?.kind, "manual");
  assert.deepEqual(readFileSync(staged.archive), Buffer.from(zip));
  assert.ok(events.length >= 4);
  assert.doesNotMatch(JSON.stringify(instance.view()), /[\\/]updates[\\/]|SHA256SUMS|releases\/download/);
});

test("a download that doesn't match its checksum fails and can be retried", async (t) => {
  const name = archiveName("0.2.0", "darwin", "arm64") ?? "";
  const files = { [name]: "tampered", SHA256SUMS: `${sha("original")}  ${name}\n` };
  const { fetch } = feed(files, [release("0.2.0", {}, files)]);
  const { instance } = updater(t, { fetch, platform: "darwin", arch: "arm64" });
  await instance.check();
  const failed = await instance.download();
  assert.equal(failed.status, "failed");
  assert.match(failed.status === "failed" ? failed.message : "", /checksum/);
  assert.equal(instance.staged(), null);
  assert.equal((await instance.download()).status, "failed");
});

test("a rate-limited or unreachable feed reports a failure and no release", async (t) => {
  const { instance } = updater(t, { fetch: async () => new Response("{}", { status: 403 }) });
  const view = await instance.check();
  assert.equal(view.status, "failed");
  assert.match(view.status === "failed" ? view.message : "", /limiting/);
  const offline = updater(t, { fetch: async () => { throw new TypeError("fetch failed"); } });
  assert.equal((await offline.instance.check()).status, "failed");
  const latest = updater(t, { fetch: feed({}, [release("0.1.0")]).fetch });
  assert.deepEqual(await latest.instance.check(), { status: "idle", current: "0.1.0", checked: true });
  const none = updater(t, { feed: null });
  assert.equal((await none.instance.check()).status, "unavailable");
});

/** A real archive of a fake installed app, made with the platform's own tools. */
async function packagedApp(root: string, version: string): Promise<{ zip: Uint8Array; executable: string; target: string }> {
  const build = join(root, `build-${version}`);
  const zipPath = join(root, `Batatis-${version}.zip`);
  if (process.platform === "darwin") {
    const contents = join(build, "Batatis.app", "Contents");
    mkdirSync(join(contents, "MacOS"), { recursive: true });
    writeFileSync(join(contents, "Info.plist"), `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>CFBundleIdentifier</key><string>ca.batatis.desktop</string><key>CFBundleShortVersionString</key><string>${version}</string></dict></plist>`);
    writeFileSync(join(contents, "MacOS", "Batatis"), version);
    await run("/usr/bin/ditto", ["-c", "-k", "--keepParent", join(build, "Batatis.app"), zipPath]);
    const target = join(root, "Applications", "Batatis.app");
    return { zip: readFileSync(zipPath), executable: join(target, "Contents", "MacOS", "Batatis"), target };
  }
  mkdirSync(build, { recursive: true });
  writeFileSync(join(build, "Batatis.exe"), version);
  await run(join(process.env.SystemRoot ?? "C:\\Windows", "System32", "tar.exe"), ["-a", "-c", "-f", zipPath, "-C", build, "Batatis.exe"]);
  const target = join(root, "Programs", "Batatis");
  return { zip: readFileSync(zipPath), executable: join(target, "Batatis.exe"), target };
}

function installed(target: string, version: string) {
  if (process.platform === "darwin") {
    mkdirSync(join(target, "Contents", "MacOS"), { recursive: true });
    writeFileSync(join(target, "Contents", "MacOS", "Batatis"), version);
  } else {
    mkdirSync(target, { recursive: true });
    writeFileSync(join(target, "Batatis.exe"), version);
  }
}

const binary = (target: string) => readFileSync(process.platform === "darwin" ? join(target, "Contents", "MacOS", "Batatis") : join(target, "Batatis.exe"), "utf8");

test("an installed app is unpacked beside itself and swapped by the script once the app has exited", { skip: process.platform !== "darwin" && process.platform !== "win32" }, async (t) => {
  const root = scratch(t);
  const next = await packagedApp(root, "0.2.0");
  installed(next.target, "0.1.0");
  const name = archiveName("0.2.0", process.platform, process.arch) ?? "";
  const files = { [name]: next.zip, SHA256SUMS: `${sha(next.zip)}  ${name}\n` };
  const { fetch } = feed(files, [release("0.2.0", {}, files)]);
  const { instance, dir } = updater(t, { fetch, executable: next.executable, replaceable: true });
  await instance.check();
  const ready = await instance.download();
  assert.equal(ready.status === "ready" && ready.install, "restart", JSON.stringify(ready));
  const staged = instance.staged();
  assert.ok(staged?.kind === "restart");
  assert.equal(binary(next.target), "0.1.0", "the running app is untouched until it exits");
  assert.equal(binary(staged.staged), "0.2.0");

  const app = spawn(process.execPath, ["-e", "setTimeout(() => {}, 700)"], { stdio: "ignore" });
  t.after(() => app.kill());
  const marker = join(root, "launched.txt");
  let launch: string[];
  if (process.platform === "win32") {
    const opener = join(root, "open.cmd");
    writeFileSync(opener, `@echo launched> "${marker}"\r\n`);
    launch = [opener];
  } else {
    launch = ["/bin/sh", "-c", `echo launched > "${marker}"`];
  }
  const swap = await swapCommand(join(dir, "updates"), process.platform, app.pid ?? 0, staged, launch);
  const script = spawn(swap.command, swap.args, { cwd: swap.cwd, stdio: "ignore", windowsHide: true });
  const exited = new Promise<number | null>((done) => script.on("exit", done));
  await new Promise((done) => setTimeout(done, 300));
  assert.equal(binary(next.target), "0.1.0", "nothing moves while the app is still running");
  await waitFor(() => existsSync(marker), 30_000);
  assert.equal(await exited, 0);
  assert.equal(binary(next.target), "0.2.0");
  assert.equal(existsSync(`${next.target}.previous`), false);
  assert.equal(existsSync(staged.stage), false);
});

test("a Windows folder holding anything besides the app is never swapped", async (t) => {
  const root = scratch(t);
  const staged = join(root, "staged"), target = join(root, "Downloads");
  for (const dir of [staged, target]) {
    mkdirSync(join(dir, "resources"), { recursive: true });
    writeFileSync(join(dir, "Batatis.exe"), "app");
  }
  assert.equal(await onlyApp(target, staged), true);
  writeFileSync(join(target, "tax return.pdf"), "the person's own file");
  assert.equal(await onlyApp(target, staged), false);
});

test("an installer's uninstaller travels with the update, but a person's own files still stop the swap", async (t) => {
  const root = scratch(t);
  const target = join(root, "Programs", "Batatis");
  const staged = join(root, "stage", "Batatis");
  for (const dir of [target, staged]) {
    mkdirSync(join(dir, "resources"), { recursive: true });
    writeFileSync(join(dir, "Batatis.exe"), "app");
  }
  writeFileSync(join(target, "Uninstall Batatis.exe"), "uninstaller");
  assert.equal(await onlyApp(target, staged), false, "without the carry-over the uninstaller would block the swap");
  await keepUninstaller(target, staged);
  assert.equal(await onlyApp(target, staged), true);
  assert.equal(readFileSync(join(staged, "Uninstall Batatis.exe"), "utf8"), "uninstaller", "and the swap keeps it");
  writeFileSync(join(target, "tax return.pdf"), "the person's own file");
  await keepUninstaller(target, staged);
  assert.equal(await onlyApp(target, staged), false);
  const plain = join(root, "Plain");
  mkdirSync(plain);
  await keepUninstaller(plain, staged);
  assert.equal(readdirSync(plain).length, 0, "a zip install has no uninstaller to carry");
});

test("a failed background check keeps the known update; a manual check after nothing known reports the failure", async (t) => {
  let online = true;
  const files = { SHA256SUMS: "" };
  const { fetch: serve } = feed(files, [release("0.2.0", {}, files)]);
  const { instance } = updater(t, { fetch: async (url, init) => { if (!online) throw new TypeError("fetch failed"); return serve(url, init); } });
  assert.equal((await instance.check()).status, "available");
  online = false;
  const kept = await instance.check();
  assert.equal(kept.status, "available");
  const fresh = updater(t, { fetch: async () => { throw new TypeError("fetch failed"); } });
  const failed = await fresh.instance.check();
  assert.equal(failed.status === "failed" && failed.release, null, "a failed check offers no download to retry");
});

test("unexpected failures reach the page as a fixed message; the details go to the log", { skip: process.platform !== "darwin" && process.platform !== "win32" }, async (t) => {
  const root = scratch(t);
  const target = process.platform === "darwin" ? join(root, "Applications", "Batatis.app") : join(root, "Programs", "Batatis");
  installed(target, "0.1.0");
  const name = archiveName("0.2.0", process.platform, process.arch) ?? "";
  const corrupt = "not a zip archive";
  const files = { [name]: corrupt, SHA256SUMS: `${sha(corrupt)}  ${name}\n` };
  const executable = process.platform === "darwin" ? join(target, "Contents", "MacOS", "Batatis") : join(target, "Batatis.exe");
  const { instance, events } = updater(t, { fetch: feed(files, [release("0.2.0", {}, files)]).fetch, executable, replaceable: true });
  await instance.check();
  const failed = await instance.download();
  assert.equal(failed.status === "failed" && failed.message, "Couldn’t download 0.2.0. The download couldn’t be unpacked.");
  assert.doesNotMatch(JSON.stringify(failed), new RegExp(root.replace(/[\\^$.*+?()[\]{}|]/g, "\\$&")));
  assert.equal(existsSync(join(dirname(target), ".batatis-update-0.2.0")), false);
  assert.equal(binary(target), "0.1.0");
  assert.ok(events.some((event) => event.startsWith("log:Update unpack failed")), "the cause is logged in the host");
});

test("startup cleanup removes kept downloads, unpacked copies and backups, and nothing else", async (t) => {
  const root = scratch(t);
  const target = join(root, "Applications", "Batatis.app");
  installed(target, "0.1.0");
  const { instance, dir } = updater(t, { executable: join(target, "Contents", "MacOS", "Batatis"), replaceable: true, platform: "darwin" });
  const updates = join(dir, "updates");
  mkdirSync(join(updates, "0.2.0"), { recursive: true });
  writeFileSync(join(updates, "swap.sh"), "script");
  mkdirSync(join(root, "Applications", ".batatis-update-0.2.0"));
  mkdirSync(`${target}.previous`);
  writeFileSync(join(root, "Applications", "Other.app"), "someone else's app");
  await instance.cleanup();
  assert.equal(existsSync(join(updates, "0.2.0")), false);
  assert.equal(existsSync(join(updates, "swap.sh")), true);
  assert.equal(existsSync(join(root, "Applications", ".batatis-update-0.2.0")), false);
  assert.equal(existsSync(`${target}.previous`), false);
  assert.equal(existsSync(join(root, "Applications", "Other.app")), true);
  assert.equal(binary(target), "0.1.0");
});

test("a stable install never sees betas; a beta install sees betas and stables, newest first", () => {
  const list = [release("0.2.0-beta.20261026.40"), release("0.1.1"), release("0.2.0-beta.20261027.41")];
  assert.equal(readReleases(list, "0.1.0", "darwin", "arm64")?.version, "0.1.1");
  assert.equal(readReleases(list, "0.1.1", "darwin", "arm64"), null);
  const beta = readReleases(list, "0.1.1-beta.20261020.3", "darwin", "arm64");
  assert.equal(beta?.version, "0.2.0-beta.20261027.41");
  assert.deepEqual(beta?.notes.map((note) => note.version), ["0.2.0-beta.20261027.41", "0.2.0-beta.20261026.40", "0.1.1"]);
  assert.equal(beta?.archive?.name, "Batatis-0.2.0-beta.20261027.41-mac-arm64.zip");
  assert.equal(readReleases([release("0.2.0")], "0.2.0-beta.20261027.41", "darwin", "arm64")?.version, "0.2.0", "a beta moves on to its stable");
  const mislabeled = { ...release("0.2.0-beta.20261027.42"), prerelease: false };
  assert.equal(readReleases([mislabeled], "0.1.1-beta.20261020.3", "darwin", "arm64")?.version ?? null, null, "a beta must be published as a prerelease");
});
