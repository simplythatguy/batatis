import assert from "node:assert/strict";
import { constants, copyFileSync, existsSync, mkdirSync, realpathSync, writeFileSync } from "node:fs";
import { realpath } from "node:fs/promises";
import { join } from "node:path";
import test from "node:test";
import { KNOWN_EXECUTABLE_SHA256, platformKey } from "../src/main/codex/release.ts";
import { codexInstallRoot, codexRuntime, type RuntimePaths } from "../src/main/runtime.ts";
import { REPO, scratch } from "./helpers.ts";

test("a packaged app runs the Codex runtime installed in app data, with the catalog from its resources", async (t) => {
  const key = platformKey(process.platform, process.arch);
  assert.ok(key, "native desktop acceptance runs on a supported platform");
  const executableName = process.platform === "win32" ? "codex.exe" : "codex";
  const fetched = join(REPO, "desktop", "codex", "runtime", key);
  if (!existsSync(join(fetched, executableName)) && process.env.BATATIS_DESKTOP_REQUIRE_CODEX !== "1") {
    t.skip("prepare the pinned native Codex runtime to exercise real install resolution");
    return;
  }
  const root = realpathSync(scratch(t));
  const resources = join(root, "Application composée 100% #", "resources");
  const userData = join(root, "app data 100% #");
  mkdirSync(join(resources, "codex"), { recursive: true });
  copyFileSync(join(REPO, "desktop", "codex", "luna-models.json"), join(resources, "codex", "luna-models.json"));
  const paths: RuntimePaths = { userData, resources, packaged: true, platform: process.platform };
  const context = { resourcesDir: resources, stateDir: root, workDir: root, appVersion: "test", log: () => {} };
  await assert.rejects(codexRuntime(paths)(context, process.platform, process.arch), /verified local AI runtime isn’t installed/, "nothing is bundled");

  const installed = join(codexInstallRoot(paths), "runtime", key);
  mkdirSync(installed, { recursive: true });
  const executable = join(installed, executableName);
  copyFileSync(join(fetched, executableName), executable, constants.COPYFILE_FICLONE);
  copyFileSync(join(fetched, "codex-runtime.json"), join(installed, "codex-runtime.json"));
  const resolved = await codexRuntime(paths)(context, process.platform, process.arch);
  assert.equal(resolved.executable, await realpath(executable));
  assert.ok(KNOWN_EXECUTABLE_SHA256[key]?.includes(resolved.sha256), "the installed executable keeps its known digest");
  writeFileSync(executable, "synthetic unapproved executable");
  await assert.rejects(codexRuntime(paths)(context, process.platform, process.arch), /verified local AI runtime isn’t installed/);
});
