import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import type { EngineCommand, WorkspaceKind } from "../src/main/engine.ts";
import { engineCommand, type RuntimePaths } from "../src/main/runtime.ts";
import { defaultPick, OFF, type AiSelection, type Source } from "../src/main/models.ts";

/** The same pick for the workflow and chat, as the single choice before the two pickers. */
export function both(source: Source | "off", screening = false): AiSelection {
  const pick = source === "off" ? OFF : defaultPick(source);
  return { workflow: pick, chat: pick, screening };
}

export const DESKTOP = resolve(import.meta.dirname, "..");
export const REPO = resolve(DESKTOP, "..");

export function scratch(t: { after(fn: () => void): void }): string {
  const dir = mkdtempSync(join(tmpdir(), "batatis-desktop-test-"));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  return dir;
}

/** The scripted stand-in engine (tests/fixtures/fake-engine.ts), started the way the host starts any engine. */
export function fakeCommand(kind: WorkspaceKind, mode = ""): EngineCommand {
  return {
    command: process.execPath,
    args: ["--experimental-strip-types", "--disable-warning=MODULE_TYPELESS_PACKAGE_JSON", join(DESKTOP, "tests", "fixtures", "fake-engine.ts"), kind, ...(mode ? [mode] : [])],
    cwd: DESKTOP,
    env: { PATH: process.env.PATH ?? "" },
  };
}

/** The real engine from this checkout, with a scratch app-data directory. */
export function pythonPaths(userData: string): RuntimePaths {
  return { userData, resources: REPO, packaged: false, platform: process.platform };
}

export function pythonCommand(userData: string, kind: WorkspaceKind, extraEnv: Record<string, string> = {}): EngineCommand {
  const command = engineCommand(pythonPaths(userData), kind, process.env);
  return { ...command, env: { ...command.env, ...extraEnv } };
}

export async function text(stream: ReadableStream<Uint8Array>): Promise<string> {
  return new Response(stream).text();
}

export function waitFor(predicate: () => boolean, timeoutMs = 5000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  return new Promise((done, fail) => {
    const tick = () => {
      if (predicate()) return done();
      if (Date.now() > deadline) return fail(new Error("timed out waiting"));
      setTimeout(tick, 10);
    };
    tick();
  });
}
