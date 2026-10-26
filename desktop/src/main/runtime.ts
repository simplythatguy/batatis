/** Fixed, app-owned paths and the engine's command line. Nothing here comes from a renderer. */
import { existsSync, readFileSync } from "node:fs";
import { dirname, isAbsolute, join, resolve } from "node:path";
import { bundledRuntime, type RuntimeSource } from "./codex";
import type { EngineCommand, WorkspaceKind } from "./engine";

export interface RuntimePaths {
  /** App-owned data root (LocalAppData on Windows, Application Support on macOS). */
  userData: string;
  /** Packaged resources directory, or the repository root in development. */
  resources: string;
  packaged: boolean;
  platform: NodeJS.Platform;
}

export function workspaceDir(paths: RuntimePaths, kind: WorkspaceKind): string {
  return join(paths.userData, "workspaces", kind);
}

export const codeDbPath = (paths: RuntimePaths): string => join(paths.userData, "codedb", "codedb.sqlite");
export const webDist = (paths: RuntimePaths): string => paths.packaged ? join(paths.resources, "web") : join(paths.resources, "web", "dist");

/** Where the installer keeps the Codex runtime: app data when packaged, the checkout's desktop/codex otherwise. */
export const codexInstallRoot = (paths: RuntimePaths): string => paths.packaged ? join(paths.userData, "codex") : join(paths.resources, "desktop", "codex");

export function codexRuntime(paths: RuntimePaths): RuntimeSource {
  return bundledRuntime({ runtimeRoot: codexInstallRoot(paths) });
}

/** Only what Python and the OS need; no inherited keys, hosted settings or shell configuration. */
const PASSED_THROUGH = ["SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE"];

export function engineCommand(paths: RuntimePaths, kind: WorkspaceKind, parentEnv: NodeJS.ProcessEnv): EngineCommand {
  const home = join(paths.userData, "engine-home");
  const env: Record<string, string> = {};
  for (const name of PASSED_THROUGH) {
    const value = parentEnv[name];
    if (value) env[name] = value;
  }
  Object.assign(env, {
    HOME: home, USERPROFILE: home,
    BATATIS_DESKTOP_WORKSPACE: kind,
    BATATIS_CASES: join(workspaceDir(paths, kind), "cases.sqlite"),
    BATATIS_CODEDB: codeDbPath(paths),
    BATATIS_STORE: "file", BATATIS_LIVE: "0", BATATIS_LIVE_ELEPHANT: "0",
    PYTHONDONTWRITEBYTECODE: "1", PYTHONUNBUFFERED: "1", PYTHONUTF8: "1", PYTHONNOUSERSITE: "1",
  });
  if (paths.packaged) {
    const dir = join(paths.resources, "engine");
    return { command: join(dir, paths.platform === "win32" ? "batatis-engine.exe" : "batatis-engine"), args: [], cwd: dir, env };
  }
  return { command: developmentPython(paths.resources, parentEnv), args: ["-m", "engine.desktop"], cwd: paths.resources, env };
}

/**
 * Development runs only: BATATIS_DESKTOP_PYTHON, then this checkout's .venv, then the main checkout's
 * .venv for a git worktree (as scripts/verify.sh does), then python3 on PATH.
 */
export function developmentPython(repo: string, env: NodeJS.ProcessEnv): string {
  const configured = env.BATATIS_DESKTOP_PYTHON;
  if (configured && isAbsolute(configured) && existsSync(configured)) return configured;
  const venv = (root: string) => process.platform === "win32" ? join(root, ".venv", "Scripts", "python.exe") : join(root, ".venv", "bin", "python");
  if (existsSync(venv(repo))) return venv(repo);
  const main = mainCheckout(repo);
  if (main && existsSync(venv(main))) return venv(main);
  return process.platform === "win32" ? "python" : "python3";
}

function mainCheckout(repo: string): string | null {
  try {
    const pointer = readFileSync(join(repo, ".git"), "utf8").match(/^gitdir:\s*(.+)$/m)?.[1]?.trim();
    if (!pointer) return null;
    const gitdir = resolve(repo, pointer);
    const common = readFileSync(join(gitdir, "commondir"), "utf8").trim();
    return dirname(resolve(gitdir, common));
  } catch {
    return null;
  }
}
