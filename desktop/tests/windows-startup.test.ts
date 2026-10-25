import assert from "node:assert/strict";
import { existsSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";
import { componentHarness } from "../../web/scripts/component-harness.mjs";
import { REPO, scratch } from "./helpers.ts";

for (const existing of [false, true]) {
  test(`the Windows entry satisfies Electron's userData directory precondition (${existing ? "existing" : "first use"})`, async (t) => {
    const localAppData = scratch(t);
    if (existing) mkdirSync(join(localAppData, "Batatis"));
    let observed: { name: string; directory: string; existedAtCall: boolean } | undefined;
    await assert.rejects(componentHarness(pathToFileURL(join(REPO, "desktop", "src", "main", "main.ts")), "unused", {
      electron: {
        app: {
          enableSandbox() {},
          setPath(name: string, directory: string) {
            observed = { name, directory, existedAtCall: existsSync(directory) };
            throw new Error("stopped at the native startup boundary");
          },
        },
        protocol: { registerSchemesAsPrivileged() {} },
      },
      "node:path": { join },
      "node:fs": { mkdirSync },
    }, { process: { platform: "win32", env: { LOCALAPPDATA: localAppData } } }), /stopped at the native startup boundary/);
    assert.deepEqual(observed, { name: "userData", directory: join(localAppData, "Batatis"), existedAtCall: true });
  });
}
