import { createHash, randomUUID } from "node:crypto";
import { createReadStream } from "node:fs";
import { access, lstat, mkdir, readFile, readdir, realpath, rename, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import type { HostProviderContext } from "../providers";
import { ENVIRONMENT_POLICY, processConfig } from "./config";
import { AdapterError, object } from "./protocol";
import { CATALOG, CODEX_ARCHIVES, CODEX_VERSION, KNOWN_EXECUTABLE_SHA256, platformKey } from "./release";

export interface ResolvedRuntime { executable: string; sha256: string; catalog: Buffer }
export type RuntimeSource = (context: HostProviderContext, platform: NodeJS.Platform, arch: string) => Promise<ResolvedRuntime>;

export async function sha256File(path: string): Promise<string> {
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(path)) hash.update(chunk);
  return hash.digest("hex");
}

export function bundledRuntime(options: { executable?: string } = {}): RuntimeSource {
  return async (context, platform, arch) => {
    const key = platformKey(platform, arch);
    if (!key) throw new AdapterError("unsupported-platform");
    let root = join(context.resourcesDir, "codex");
    try { await access(join(root, CATALOG.file)); }
    catch { root = join(context.resourcesDir, "desktop", "codex"); }
    try {
      const catalog = await readFile(join(root, CATALOG.file));
      if (catalog.length !== CATALOG.bytes || createHash("sha256").update(catalog).digest("hex") !== CATALOG.sha256)
        throw new AdapterError("context_unverified");
      const pin = CODEX_ARCHIVES[key];
      const executable = await realpath(options.executable ?? join(root, "runtime", key, pin.executable));
      if (!(await lstat(executable)).isFile()) throw new AdapterError("runtime-missing");
      const sha256 = await sha256File(executable);
      // A self-reported manifest digest alone must never authorize an executable.
      if (!KNOWN_EXECUTABLE_SHA256[key]?.includes(sha256)) throw new AdapterError("runtime-missing");
      if (!options.executable) {
        const manifest = object(JSON.parse(await readFile(join(dirname(executable), "codex-runtime.json"), "utf8")));
        if (manifest.version !== CODEX_VERSION || manifest.platform !== key || manifest.archiveSha256 !== pin.sha256 || manifest.executableSha256 !== sha256)
          throw new AdapterError("runtime-missing");
      }
      return { executable, sha256, catalog };
    } catch (error) {
      if (error instanceof AdapterError) throw error;
      throw new AdapterError("runtime-missing");
    }
  };
}

function nested(a: string, b: string): boolean {
  const rel = relative(a, b);
  return rel === "" || (!rel.startsWith(`..${sep}`) && rel !== ".." && !isAbsolute(rel));
}

async function canonical(path: string): Promise<string> {
  if (!isAbsolute(path)) throw new AdapterError("context_unverified");
  await mkdir(path, { recursive: true, mode: 0o700 });
  return realpath(path);
}

export async function assertEmptyWorkDir(workDir: string): Promise<void> {
  if ((await readdir(workDir)).length) throw new AdapterError("context_unverified");
  for (let path = workDir;; path = dirname(path)) {
    try { await lstat(join(path, ".git")); throw new AdapterError("context_unverified"); }
    catch (error) {
      if (!(error instanceof Error && "code" in error && error.code === "ENOENT")) throw error;
    }
    if (dirname(path) === path) break;
  }
}

async function writeOwned(path: string, bytes: string | Buffer): Promise<void> {
  try {
    const existing = await lstat(path);
    if (!existing.isFile() || existing.isSymbolicLink()) throw new AdapterError("context_unverified");
    if ((await readFile(path)).equals(Buffer.from(bytes))) return;
  } catch (error) {
    if (!(error instanceof Error && "code" in error && error.code === "ENOENT")) throw error;
  }
  const temp = `${path}.${randomUUID()}.batatis-partial`;
  await writeFile(temp, bytes, { mode: 0o600, flag: "wx" });
  await rename(temp, path);
}

export async function prepareHome(context: HostProviderContext, environment: NodeJS.ProcessEnv, catalog: Buffer): Promise<{ home: string; cwd: string }> {
  const home = await canonical(context.stateDir);
  const cwd = await canonical(context.workDir);
  if (nested(home, cwd) || nested(cwd, home)) throw new AdapterError("context_unverified");
  for (const privateHome of [join(homedir(), ".codex"), environment.CODEX_HOME, environment.HOME && join(environment.HOME, ".codex"), environment.USERPROFILE && join(environment.USERPROFILE, ".codex")]) {
    if (!privateHome) continue;
    const forbidden = await realpath(privateHome).catch(() => resolve(privateHome));
    if (nested(forbidden, home)) throw new AdapterError("context_unverified");
  }
  await assertEmptyWorkDir(cwd);
  if (catalog.length !== CATALOG.bytes || createHash("sha256").update(catalog).digest("hex") !== CATALOG.sha256)
    throw new AdapterError("context_unverified");
  for (const name of ["auth.json", "AGENTS.md", "AGENTS.override.md", "instructions.md", "skills", "plugins", "memories"]) {
    try { await lstat(join(home, name)); throw new AdapterError(name === "auth.json" ? "keyring-unavailable" : "context_unverified"); }
    catch (error) {
      if (!(error instanceof Error && "code" in error && error.code === "ENOENT")) throw error;
    }
  }
  await writeOwned(join(home, CATALOG.file), catalog);
  await writeOwned(join(home, "config.toml"), processConfig(join(home, CATALOG.file)));
  return { home, cwd };
}

export function childEnvironment(home: string, platform: NodeJS.Platform, source: NodeJS.ProcessEnv): NodeJS.ProcessEnv {
  const env: NodeJS.ProcessEnv = { CODEX_HOME: home };
  const keys = platform === "win32" ? ENVIRONMENT_POLICY.windowsKeys : ENVIRONMENT_POLICY.darwinKeys;
  for (const key of keys) {
    const value = Object.entries(source).find(([name]) => platform === "win32" ? name.toLowerCase() === key.toLowerCase() : name === key)?.[1];
    if (value !== undefined) env[key] = value;
  }
  if (platform === "win32") {
    if (!env.SystemRoot || !isAbsolute(env.SystemRoot)) throw new AdapterError("runtime-missing");
    const root = env.SystemRoot;
    env.PATH = ENVIRONMENT_POLICY.windowsPath.map((part) => join(root, ...part.split("/"))).join(";");
  } else env.PATH = ENVIRONMENT_POLICY.darwinPath;
  return env;
}
