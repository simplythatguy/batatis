/**
 * A pinned AI runtime (Codex, Claude), downloaded on first use instead of shipped inside the app, after
 * T3 Code's managed Codex. Only the pinned release installs: the download's size and SHA-256 and the
 * executable's SHA-256 must all match. A newer app that pins a newer release offers Update.
 */
import { createHash, randomUUID } from "node:crypto";
import { createWriteStream } from "node:fs";
import { chmod, mkdir, readFile, rename, rm, stat, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { Readable, Transform } from "node:stream";
import { pipeline } from "node:stream/promises";
import { sha256File } from "./codex/binary";

export type InstallState =
  | { state: "unsupported" }
  | { state: "missing" }
  | { state: "outdated"; installed: string }
  | { state: "installing"; received: number; total: number }
  | { state: "installed"; version: string }
  | { state: "failed"; message: string };

/** The release this app installs; tests pass a small synthetic one. */
export interface RuntimePin {
  version: string;
  /** The platform folder under runtime/, for example darwin-arm64. */
  key: string;
  url: string;
  /** What is downloaded. `member` is the executable inside an archive; null when the download is the executable. */
  download: { asset: string; bytes: number; sha256: string; member: string | null };
  /** The installed executable's file name. */
  executable: string;
  /** Accepted SHA-256 digests of the executable. */
  executables: readonly string[];
}

export interface InstallerDeps {
  /** The folder holding runtime/<platform>/, the layout bundledRuntime({ runtimeRoot }) reads. */
  root: string;
  pin: RuntimePin | null;
  fetch: (url: string, init?: { signal?: AbortSignal; headers?: Record<string, string> }) => Promise<Response>;
  /** Runs the system tar and resolves to its standard output; rejects on a nonzero exit. */
  tar: (args: string[]) => Promise<string>;
  notify: () => void;
  log: (line: string) => void;
}

const STALL_MS = 60_000;

class InstallError extends Error {}

export class RuntimeInstaller {
  private current: InstallState = { state: "missing" };
  private work: AbortController | null = null;
  private readonly deps: InstallerDeps;

  constructor(deps: InstallerDeps) {
    this.deps = deps;
  }

  status(): InstallState {
    return this.current;
  }

  private set(next: InstallState) {
    this.current = next;
    this.deps.notify();
  }

  private folder(pin: RuntimePin): string {
    return join(this.deps.root, "runtime", pin.key);
  }

  /** Reads what is installed. The executable's digest is checked again each time the runtime starts. */
  async refresh(): Promise<InstallState> {
    if (this.current.state === "installing") return this.current;
    const pin = this.deps.pin;
    if (!pin) return (this.current = { state: "unsupported" });
    try {
      const manifest = JSON.parse(await readFile(join(this.folder(pin), "codex-runtime.json"), "utf8")) as { version?: unknown };
      await stat(join(this.folder(pin), pin.executable));
      const version = typeof manifest.version === "string" ? manifest.version : "unknown";
      this.current = version === pin.version ? { state: "installed", version } : { state: "outdated", installed: version };
    } catch {
      this.current = { state: "missing" };
    }
    return this.current;
  }

  /**
   * Downloads, checks and unpacks the pinned release. `stop` runs just before the new runtime replaces
   * the old one: Windows can't rename a folder whose executable is still running.
   */
  async install(stop: () => Promise<void>): Promise<InstallState> {
    const pin = this.deps.pin;
    if (!pin || this.current.state === "installing") return this.current;
    const work = new AbortController();
    this.work = work;
    const scratch = join(this.deps.root, `install-${randomUUID()}`);
    this.set({ state: "installing", received: 0, total: pin.download.bytes });
    try {
      await mkdir(scratch, { recursive: true });
      const archive = join(scratch, pin.download.asset);
      if ((await this.download(pin, archive, work)) !== pin.download.sha256) throw new InstallError("The download didn’t match the expected file. Try again.");
      const executable = pin.download.member === null ? await this.checked(pin, archive) : await this.unpack(pin, pin.download.member, archive, scratch);
      const next = `${this.folder(pin)}.next`;
      await rm(next, { recursive: true, force: true });
      await mkdir(next, { recursive: true });
      await rename(executable, join(next, pin.executable));
      await chmod(join(next, pin.executable), 0o755);
      await writeFile(join(next, "codex-runtime.json"), `${JSON.stringify({
        version: pin.version, platform: pin.key, archiveSha256: pin.download.sha256, executableSha256: await sha256File(join(next, pin.executable)),
      }, null, 2)}\n`);
      await stop();
      const old = `${this.folder(pin)}.old`;
      await rm(old, { recursive: true, force: true });
      await rename(this.folder(pin), old).catch((error: NodeJS.ErrnoException) => { if (error.code !== "ENOENT") throw error; });
      await rename(next, this.folder(pin));
      await rm(old, { recursive: true, force: true });
      this.set({ state: "installed", version: pin.version });
    } catch (error) {
      this.set({ state: "failed", message: this.messageOf(work.signal.reason ?? error) });
    } finally {
      this.work = null;
      await rm(scratch, { recursive: true, force: true }).catch(() => undefined);
    }
    return this.current;
  }

  cancel() {
    this.work?.abort();
  }

  private messageOf(error: unknown): string {
    if (error instanceof InstallError) return error.message;
    if (error instanceof Error && (error.name === "AbortError" || error.name === "TimeoutError")) return "The download stopped. Check your connection and try again.";
    this.deps.log(`Runtime install failed: ${error instanceof Error ? error.message : String(error)}`);
    return "The install didn’t finish. Check your connection and free disk space, then try again.";
  }

  private async download(pin: RuntimePin, file: string, work: AbortController): Promise<string> {
    let stall: ReturnType<typeof setTimeout> | undefined;
    const watch = () => {
      clearTimeout(stall);
      stall = setTimeout(() => work.abort(new InstallError("The download stalled. Try again.")), STALL_MS);
    };
    watch();
    try {
      const reply = await this.deps.fetch(pin.url, { signal: work.signal });
      if (!reply.ok || !reply.body) throw new InstallError(`The download failed (${reply.status}). Try again.`);
      const hash = createHash("sha256");
      let received = 0, shown = -1;
      const count = new Transform({
        transform: (chunk: Buffer, _encoding, done) => {
          watch();
          received += chunk.length;
          if (received > pin.download.bytes) return done(new InstallError("The download didn’t match the expected file. Try again."));
          hash.update(chunk);
          const percent = Math.floor((received / pin.download.bytes) * 100);
          if (percent !== shown) {
            shown = percent;
            this.set({ state: "installing", received, total: pin.download.bytes });
          }
          done(null, chunk);
        },
      });
      await pipeline(Readable.fromWeb(reply.body as import("node:stream/web").ReadableStream), count, createWriteStream(file));
      if (received !== pin.download.bytes) throw new InstallError("The download was incomplete. Try again.");
      return hash.digest("hex");
    } finally {
      clearTimeout(stall);
    }
  }

  /** Extracts only the release's executable, after checking the archive names nothing outside it. */
  private async unpack(pin: RuntimePin, member: string, archive: string, scratch: string): Promise<string> {
    const members = (await this.deps.tar(["-tf", archive])).trim().split(/\r?\n/);
    if (!members.includes(member) || members.some((name) => name.startsWith("/") || name.split(/[\\/]/).includes(".."))) {
      throw new InstallError("The download didn’t match the expected file. Try again.");
    }
    const out = join(scratch, "unpacked");
    await mkdir(out);
    await this.deps.tar(["-xf", archive, "-C", out, member]);
    return this.checked(pin, join(out, member));
  }

  private async checked(pin: RuntimePin, executable: string): Promise<string> {
    if (!(await stat(executable)).isFile() || !pin.executables.includes(await sha256File(executable))) {
      throw new InstallError("The download didn’t match the expected file. Try again.");
    }
    return executable;
  }
}
