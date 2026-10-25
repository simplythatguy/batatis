import assert from "node:assert/strict";
import { constants, copyFileSync, existsSync, mkdirSync, realpathSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";
import { KNOWN_EXECUTABLE_SHA256, platformKey } from "../src/main/codex/release.ts";
import { codexRuntime, type RuntimePaths } from "../src/main/runtime.ts";
import { REPO, scratch } from "./helpers.ts";

test("the app resolves and verifies Codex from electron-builder's flat resources layout", async (t) => {
  const key = platformKey(process.platform, process.arch);
  assert.ok(key, "native desktop acceptance runs on a supported platform");
  const executableName = process.platform === "win32" ? "codex.exe" : "codex";
  const source = join(REPO, "desktop", "codex", "runtime", key, executableName);
  if (!existsSync(source) && process.env.BATATIS_DESKTOP_REQUIRE_CODEX !== "1") {
    t.skip("prepare the pinned native Codex runtime to exercise real bundle resolution");
    return;
  }
  const root = realpathSync(scratch(t));
  const resources = join(root, "Application composée 100% #", "resources");
  mkdirSync(join(resources, "codex"), { recursive: true });
  const executable = join(resources, "codex", executableName);
  copyFileSync(source, executable, constants.COPYFILE_FICLONE);
  copyFileSync(join(REPO, "desktop", "codex", "luna-models.json"), join(resources, "codex", "luna-models.json"));
  const paths: RuntimePaths = { userData: root, resources, packaged: true, platform: process.platform };
  const context = { resourcesDir: resources, stateDir: root, workDir: root, appVersion: "test", log: () => {} };
  const resolved = await codexRuntime(paths)(context, process.platform, process.arch);
  assert.equal(resolved.executable, executable);
  assert.ok(KNOWN_EXECUTABLE_SHA256[key]?.includes(resolved.sha256), "the actual bundled executable retains its known digest");
  writeFileSync(executable, "synthetic unapproved executable");
  await assert.rejects(codexRuntime(paths)(context, process.platform, process.arch), /verified local AI runtime is missing/);
});
