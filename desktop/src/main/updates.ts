/**
 * App updates from the repository's GitHub releases, for unsigned builds.
 *
 * Squirrel.Mac only installs Developer ID signed apps, and the package ships ad hoc signed, so the
 * host does the work itself: it reads the releases, downloads this platform's archive, checks it
 * against the release's SHA256SUMS, unpacks it next to the installed app, and after the app quits a
 * small script swaps the two folders and opens the new one. When the installed app cannot be
 * replaced in place, the verified archive is shown in its folder instead.
 */
import { createHash } from "node:crypto";
import { createWriteStream } from "node:fs";
import { access, constants, mkdir, readdir, readFile, rm, stat, writeFile } from "node:fs/promises";
import { basename, dirname, join } from "node:path";
import { pipeline } from "node:stream/promises";
import { Readable, Transform } from "node:stream";

export const REPOSITORY = "simplythatguy/batatis";
export const RELEASES_PAGE = `https://github.com/${REPOSITORY}/releases`;
export const RELEASES_FEED = `https://api.github.com/repos/${REPOSITORY}/releases?per_page=30`;
const TAG = /^v(.+)$/;
const SUMS = "SHA256SUMS";
const CHANNEL_FILE = "channel.json";
const MAX_NOTE_GROUPS = 5;
const MAX_NOTE_ITEMS = 8;
const MAX_NOTE_LENGTH = 220;
const CHECK_TIMEOUT_MS = 20_000;
const STALL_MS = 60_000;

/** A failure whose message may be shown on the page. Anything else is logged and shown generically. */
class UpdateError extends Error {}

export interface ReleaseNote { version: string; items: string[]; more: number; url: string }

export interface Release {
  version: string;
  url: string;
  notes: ReleaseNote[];
  /** Newer releases beyond the ones with notes. */
  older: number;
  archive: { name: string; url: string; size: number } | null;
  sums: string | null;
}

/** What the page sees. No path or download address leaves the host. `beta` is whether betas are offered. */
export type UpdateView = UpdateState & { beta: boolean };
type UpdateState =
  | { status: "unavailable"; current: string; message: string }
  | { status: "idle"; current: string; checked: boolean }
  | { status: "checking"; current: string }
  | { status: "available"; current: string; release: PublicRelease }
  | { status: "downloading"; current: string; release: PublicRelease; percent: number | null }
  | { status: "ready"; current: string; release: PublicRelease; install: "restart" | "manual" }
  | { status: "failed"; current: string; release: PublicRelease | null; message: string };

export interface PublicRelease { version: string; url: string; notes: ReleaseNote[]; older: number; history: string; downloadable: boolean }

export type Staged =
  | { kind: "restart"; archive: string; target: string; staged: string; stage: string }
  | { kind: "manual"; archive: string };

type State =
  | { status: "idle"; checked: boolean }
  | { status: "checking" }
  | { status: "available"; release: Release }
  | { status: "downloading"; release: Release; percent: number | null }
  | { status: "ready"; release: Release; staged: Staged }
  | { status: "failed"; release: Release | null; message: string };

export interface UpdaterDeps {
  current: string;
  platform: NodeJS.Platform;
  arch: string;
  /** Releases API address; null when this build cannot update (an unpackaged development run). */
  feed: string | null;
  /** May this address be fetched? The feed and release downloads only. */
  trusted: (url: URL) => boolean;
  fetch: (url: string, init?: { headers?: Record<string, string>; signal?: AbortSignal }) => Promise<Response>;
  /** Where archives are kept while they wait (userData/updates). */
  dir: string;
  /** The running executable; locates the installed app. */
  executable: string;
  /** Packaged builds replace themselves; development runs only show the archive. */
  replaceable: boolean;
  /** Runs a system tool (ditto, plutil, tar) and rejects on a nonzero exit. */
  run: (command: string, args: string[]) => Promise<string>;
  notify: () => void;
  /** Details of unexpected failures; the page only sees a generic message for them. */
  log: (line: string) => void;
}

/**
 * Release versions, after T3 Code's stable and nightly builds: stable is X.Y.Z; beta is
 * X.Y.Z-beta.YYYYMMDD.RUN, a preview of the stable X.Y.Z, built from main.
 */
export interface Version { core: [number, number, number]; beta: [number, number] | null }
export type Channel = "stable" | "beta";

export function parseVersion(value: string): Version | null {
  const match = /^(\d+)\.(\d+)\.(\d+)(?:-beta\.(\d{8})\.(\d+))?$/.exec(value.trim());
  if (!match) return null;
  const core: [number, number, number] = [Number(match[1]), Number(match[2]), Number(match[3])];
  return { core, beta: match[4] ? [Number(match[4]), Number(match[5])] : null };
}

/** Semantic-version order: a stable release sorts after every beta of the same X.Y.Z. */
export function compareVersions(a: Version, b: Version): number {
  for (let i = 0; i < 3; i++) if (a.core[i] !== b.core[i]) return a.core[i] - b.core[i];
  if (!a.beta || !b.beta) return (a.beta ? -1 : 0) - (b.beta ? -1 : 0);
  return a.beta[0] - b.beta[0] || a.beta[1] - b.beta[1];
}

export function newer(candidate: string, current: string): boolean {
  const a = parseVersion(candidate), b = parseVersion(current);
  return a !== null && b !== null && compareVersions(a, b) > 0;
}

/** Without a saved choice an install follows the channel its own version came from; a beta also takes stable releases. */
export function channelOf(version: string): Channel {
  return parseVersion(version)?.beta ? "beta" : "stable";
}

export function archiveName(version: string, platform: NodeJS.Platform, arch: string): string | null {
  const os = platform === "darwin" ? "mac" : platform === "win32" ? "win" : null;
  return os ? `Batatis-${version}-${os}-${arch}.zip` : null;
}

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);

/** One bullet of generated release notes as plain text: links become their text, PR links become #n. */
export function noteItem(line: string): string | null {
  const text = line
    .replace(/^\s*[-*]\s+/, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/https:\/\/github\.com\/[^/\s]+\/[^/\s]+\/pull\/(\d+)/g, "#$1")
    .replace(/\s+by @[\w-]+ in (#\d+)$/, " ($1)")
    .replace(/[*_`]/g, "")
    .replace(/\s+/g, " ")
    .trim();
  if (!text || /^full changelog:/i.test(text)) return null;
  return text.length > MAX_NOTE_LENGTH ? `${text.slice(0, MAX_NOTE_LENGTH - 1).trimEnd()}…` : text;
}

export function noteItems(body: string): string[] {
  return body.split(/\r?\n/).filter((line) => /^\s*[-*]\s+/.test(line)).map(noteItem).filter((item): item is string => item !== null);
}

/** Newer desktop releases from the releases API, newest first, with this platform's archive. */
export function readReleases(value: unknown, current: string, platform: NodeJS.Platform, arch: string, beta = channelOf(current) === "beta"): Release | null {
  if (!Array.isArray(value)) throw new Error("The release list could not be read.");
  const found: { version: string; url: string; body: string; assets: unknown[] }[] = [];
  for (const item of value) {
    if (!isRecord(item) || item.draft === true || typeof item.tag_name !== "string") continue;
    const version = TAG.exec(item.tag_name)?.[1] ?? "";
    const parsed = parseVersion(version);
    // A beta is published as a prerelease and a stable as a release; anything else is not ours to install.
    if (!parsed || Boolean(parsed.beta) !== (item.prerelease === true) || (parsed.beta && !beta)) continue;
    if (!newer(version, current) || typeof item.html_url !== "string") continue;
    found.push({ version, url: item.html_url, body: typeof item.body === "string" ? item.body : "", assets: Array.isArray(item.assets) ? item.assets : [] });
  }
  if (found.length === 0) return null;
  found.sort((a, b) => (newer(a.version, b.version) ? -1 : 1));
  const latest = found[0];
  const asset = (name: string | null) => {
    const hit = name ? latest.assets.find((a) => isRecord(a) && a.name === name) : undefined;
    return isRecord(hit) && typeof hit.browser_download_url === "string" && typeof hit.size === "number"
      ? { name: hit.name as string, url: hit.browser_download_url, size: hit.size } : null;
  };
  const notes = found.slice(0, MAX_NOTE_GROUPS).map((release) => {
    const items = noteItems(release.body);
    return { version: release.version, items: items.slice(0, MAX_NOTE_ITEMS), more: Math.max(0, items.length - MAX_NOTE_ITEMS), url: release.url };
  });
  return {
    version: latest.version, url: latest.url, notes, older: Math.max(0, found.length - MAX_NOTE_GROUPS),
    archive: asset(archiveName(latest.version, platform, arch)), sums: asset(SUMS)?.url ?? null,
  };
}

export function expectedSum(sums: string, name: string): string | null {
  for (const line of sums.split(/\r?\n/)) {
    const match = /^([0-9a-f]{64})\s+\*?(.+)$/i.exec(line.trim());
    if (match && match[2] === name) return match[1].toLowerCase();
  }
  return null;
}

function publicRelease(release: Release): PublicRelease {
  return { version: release.version, url: release.url, notes: release.notes, older: release.older, history: RELEASES_PAGE, downloadable: release.archive !== null && release.sums !== null };
}

/** The installed app folder this executable belongs to, when the platform has one. */
export function installedApp(executable: string, platform: NodeJS.Platform): string | null {
  if (platform === "darwin") {
    const bundle = dirname(dirname(dirname(executable)));
    return bundle.endsWith(".app") && basename(dirname(executable)) === "MacOS" ? bundle : null;
  }
  return platform === "win32" ? dirname(executable) : null;
}

export class Updater {
  private state: State = { status: "idle", checked: false };
  private work: AbortController | null = null;

  private readonly deps: UpdaterDeps;

  constructor(deps: UpdaterDeps) {
    this.deps = deps;
  }

  /** The saved choice to get betas; null follows the installed version. */
  private beta: boolean | null = null;

  /** Betas are offered when chosen, or by default when this install is itself a beta. */
  get betaUpdates(): boolean {
    return this.beta ?? channelOf(this.deps.current) === "beta";
  }

  private channelFile(): string {
    return join(this.deps.dir, CHANNEL_FILE);
  }

  /** Reads the saved choice; a missing or unreadable file means none. */
  async load(): Promise<void> {
    try {
      const saved: unknown = JSON.parse(await readFile(this.channelFile(), "utf8"));
      this.beta = isRecord(saved) && typeof saved.beta === "boolean" ? saved.beta : null;
    } catch {
      this.beta = null;
    }
  }

  /** Saves the choice and looks again, so an offer from the other channel does not stay on screen. */
  async setBeta(beta: boolean): Promise<UpdateView> {
    const s = this.state;
    if (!this.deps.feed || s.status === "checking" || s.status === "downloading" || beta === this.betaUpdates) return this.view();
    this.beta = beta;
    try {
      await mkdir(this.deps.dir, { recursive: true });
      await writeFile(this.channelFile(), JSON.stringify({ beta }));
    } catch (error) {
      this.deps.log(`update channel not saved: ${this.messageOf(error)}`);
    }
    if (s.status === "available") this.state = { status: "idle", checked: false };
    return this.check();
  }

  view(): UpdateView {
    return { ...this.stateView(), beta: this.betaUpdates };
  }

  private stateView(): UpdateState {
    const current = this.deps.current;
    if (!this.deps.feed) return { status: "unavailable", current, message: "Updates are available in the installed app." };
    const s = this.state;
    switch (s.status) {
      case "idle": return { status: "idle", current, checked: s.checked };
      case "checking": return { status: "checking", current };
      case "available": return { status: "available", current, release: publicRelease(s.release) };
      case "downloading": return { status: "downloading", current, release: publicRelease(s.release), percent: s.percent };
      case "ready": return { status: "ready", current, release: publicRelease(s.release), install: s.staged.kind };
      case "failed": return { status: "failed", current, release: s.release && publicRelease(s.release), message: s.message };
    }
  }

  /** The verified, unpacked update waiting for a restart; null until one is ready. */
  staged(): Staged | null {
    return this.state.status === "ready" ? this.state.staged : null;
  }

  private set(next: State) {
    this.state = next;
    this.deps.notify();
  }

  /**
   * Reads the releases. A known update stays on screen through a failed check; a newer release
   * than the one already unpacked replaces it.
   */
  async check(): Promise<UpdateView> {
    const feed = this.deps.feed;
    const before = this.state;
    if (!feed || before.status === "checking" || before.status === "downloading") return this.view();
    const quiet = before.status === "available" || before.status === "ready";
    if (!quiet) this.set({ status: "checking" });
    try {
      const reply = await this.get(feed, AbortSignal.timeout(CHECK_TIMEOUT_MS), { Accept: "application/vnd.github+json" });
      const release = readReleases(await reply.json(), this.deps.current, this.deps.platform, this.deps.arch, this.betaUpdates);
      if (before.status === "ready" && release?.version === before.release.version) this.set({ ...before, release });
      else {
        if (before.status === "ready") await this.discard(before.staged);
        this.set(release ? { status: "available", release } : { status: "idle", checked: true });
      }
    } catch (error) {
      this.set(quiet ? before : { status: "failed", release: null, message: `Couldn’t check for updates. ${this.messageOf(error)}` });
    }
    return this.view();
  }

  async download(): Promise<UpdateView> {
    const s = this.state;
    const release = s.status === "available" || s.status === "failed" ? s.release : null;
    if (!release) return this.view();
    if (!release.archive || !release.sums) {
      this.set({ status: "failed", release, message: "This release has no download for this computer." });
      return this.view();
    }
    const { archive, sums } = release;
    const work = new AbortController();
    this.work = work;
    this.set({ status: "downloading", release, percent: 0 });
    try {
      const expected = expectedSum(await (await this.get(sums, work.signal)).text(), archive.name);
      if (!expected) throw new UpdateError("The release has no checksum for this download.");
      const folder = join(this.deps.dir, release.version);
      await rm(folder, { recursive: true, force: true });
      await mkdir(folder, { recursive: true });
      const file = join(folder, archive.name);
      const actual = await this.save(archive.url, file, archive.size, release, work);
      if (actual !== expected) throw new UpdateError("The download didn’t match its checksum.");
      const staged = await this.stage(file, release.version);
      if (staged.kind === "restart") await rm(folder, { recursive: true, force: true });
      this.set({ status: "ready", release, staged });
    } catch (error) {
      this.set({ status: "failed", release, message: `Couldn’t download ${release.version}. ${this.messageOf(work.signal.reason ?? error)}` });
    } finally {
      this.work = null;
    }
    return this.view();
  }

  /**
   * Removes what earlier runs left: kept downloads, and unpacked copies or backups beside the app.
   * Runs at startup, before any download, so nothing it removes is in use.
   */
  async cleanup(): Promise<void> {
    const remove = (path: string) => rm(path, { recursive: true, force: true }).catch(() => undefined);
    for (const entry of await readdir(this.deps.dir).catch(() => [] as string[])) {
      if (parseVersion(entry)) await remove(join(this.deps.dir, entry));
    }
    const target = this.deps.replaceable ? installedApp(this.deps.executable, this.deps.platform) : null;
    if (!target) return;
    await remove(`${target}.previous`);
    for (const entry of await readdir(dirname(target)).catch(() => [] as string[])) {
      if (/^\.batatis-update-\d+\.\d+\.\d+(?:-beta\.\d{8}\.\d+)?$/.test(entry)) await remove(join(dirname(target), entry));
    }
  }

  private async discard(staged: Staged) {
    await rm(staged.kind === "restart" ? staged.stage : dirname(staged.archive), { recursive: true, force: true }).catch(() => undefined);
  }

  private messageOf(error: unknown): string {
    if (error instanceof UpdateError) return error.message;
    if (error instanceof Error && (error.name === "AbortError" || error.name === "TimeoutError")) return "The connection stopped. Try again.";
    this.deps.log(`Update failed: ${error instanceof Error ? error.message : String(error)}`);
    return "Something went wrong. Try again.";
  }

  /** Stops a download in progress (the app is quitting). */
  cancel() {
    this.work?.abort();
  }

  private async get(url: string, signal: AbortSignal, headers: Record<string, string> = {}): Promise<Response> {
    if (!this.deps.trusted(new URL(url))) throw new UpdateError("The update address isn’t trusted.");
    const reply = await this.deps.fetch(url, { headers: { "User-Agent": `Batatis/${this.deps.current}`, ...headers }, signal });
    if (!reply.ok || !reply.body) throw new UpdateError(reply.status === 403 || reply.status === 429 ? "GitHub is limiting requests. Try again later." : `GitHub answered ${reply.status}.`);
    return reply;
  }

  /** Streams to disk while hashing; a download that sends nothing for a minute is stopped. */
  private async save(url: string, file: string, size: number, release: Release, work: AbortController): Promise<string> {
    let stall: ReturnType<typeof setTimeout> | undefined;
    const watch = () => {
      clearTimeout(stall);
      stall = setTimeout(() => work.abort(new UpdateError("The download stalled. Try again.")), STALL_MS);
    };
    watch();
    try {
      return await this.stream(url, file, size, release, work.signal, watch);
    } finally {
      clearTimeout(stall);
    }
  }

  private async stream(url: string, file: string, size: number, release: Release, signal: AbortSignal, progress: () => void): Promise<string> {
    const reply = await this.get(url, signal);
    const hash = createHash("sha256");
    let received = 0, shown = -1;
    const count = new Transform({
      transform: (chunk: Buffer, _encoding, done) => {
        progress();
        hash.update(chunk);
        received += chunk.length;
        const percent = size > 0 ? Math.min(100, Math.floor((received / size) * 100)) : null;
        if (percent !== null && percent !== shown) {
          shown = percent;
          this.set({ status: "downloading", release, percent });
        }
        done(null, chunk);
      },
    });
    await pipeline(Readable.fromWeb(reply.body as import("node:stream/web").ReadableStream), count, createWriteStream(file));
    if (size > 0 && received !== size) throw new UpdateError("The download was incomplete.");
    return hash.digest("hex");
  }

  /** Unpacks next to the installed app so the swap is a rename on one volume; otherwise keeps the archive. */
  private async stage(archive: string, version: string): Promise<Staged> {
    const target = this.deps.replaceable ? installedApp(this.deps.executable, this.deps.platform) : null;
    if (!target || target.includes("/AppTranslocation/") || !(await writable(dirname(target))) || !(await writable(target))) {
      return { kind: "manual", archive };
    }
    const stage = join(dirname(target), `.batatis-update-${version}`);
    try {
      await rm(stage, { recursive: true, force: true });
      await mkdir(stage, { recursive: true });
    } catch {
      // Windows access checks can pass for a folder that still refuses new entries (Program Files).
      return { kind: "manual", archive };
    }
    try {
      if (this.deps.platform === "darwin") await this.deps.run("/usr/bin/ditto", ["-x", "-k", archive, stage]);
      else await this.deps.run(join(process.env.SystemRoot ?? "C:\\Windows", "System32", "tar.exe"), ["-xf", archive, "-C", stage]);
      const staged = await this.unpacked(stage, version);
      if (this.deps.platform === "win32" && !(await onlyApp(target, staged))) {
        await rm(stage, { recursive: true, force: true });
        return { kind: "manual", archive };
      }
      return { kind: "restart", archive, target, staged, stage };
    } catch (error) {
      await rm(stage, { recursive: true, force: true });
      if (error instanceof UpdateError) throw error;
      this.deps.log(`Update unpack failed: ${error instanceof Error ? error.message : String(error)}`);
      throw new UpdateError("The download couldn’t be unpacked.");
    }
  }

  private async unpacked(stage: string, version: string): Promise<string> {
    if (this.deps.platform === "darwin") {
      const app = join(stage, "Batatis.app");
      const plist = join(app, "Contents", "Info.plist");
      const read = (key: string) => this.deps.run("/usr/bin/plutil", ["-extract", key, "raw", "-o", "-", plist]).then((v) => v.trim());
      if ((await read("CFBundleIdentifier")) !== "ca.batatis.desktop" || (await read("CFBundleShortVersionString")) !== version) {
        throw new UpdateError("The download isn’t the expected Batatis version.");
      }
      return app;
    }
    if (await exists(join(stage, "Batatis.exe"))) return stage;
    const entries = await readdir(stage, { withFileTypes: true });
    const inner = entries.length === 1 && entries[0].isDirectory() ? join(stage, entries[0].name) : null;
    if (inner && await exists(join(inner, "Batatis.exe"))) return inner;
    throw new UpdateError("The download isn’t a Batatis app.");
  }
}

async function writable(path: string): Promise<boolean> {
  try {
    await access(path, constants.W_OK);
    return true;
  } catch {
    return false;
  }
}

async function exists(path: string): Promise<boolean> {
  try {
    await stat(path);
    return true;
  } catch {
    return false;
  }
}

/**
 * The Windows archive has no top folder, so a person may have unpacked it into a folder of their own
 * files. The swap replaces the whole folder, so it runs only when every entry also ships in the update.
 */
export async function onlyApp(target: string, staged: string): Promise<boolean> {
  const shipped = new Set((await readdir(staged)).map((name) => name.toLowerCase()));
  return (await readdir(target)).every((name) => shipped.has(name.toLowerCase()));
}

const SWAP_SH = `#!/bin/sh
# Batatis update: wait for the app to quit, swap the folders, open the result.
pid="$1"; target="$2"; staged="$3"; stage="$4"; shift 4
cd / || exit 1
i=0
while kill -0 "$pid" 2>/dev/null; do
  i=$((i + 1)); [ "$i" -gt 1200 ] && exit 1
  sleep 0.1
done
backup="$target.previous"
rm -rf "$backup"
if [ ! -e "$backup" ] && mv "$target" "$backup"; then
  if mv "$staged" "$target"; then rm -rf "$backup"; else mv "$backup" "$target"; fi
fi
rm -rf "$stage"
exec "$@"
`;

const SWAP_PS1 = `# Batatis update: wait for the app to quit, swap the folders, open the result.
param([int]$ProcessId, [string]$Target, [string]$Staged, [string]$Stage, [string]$Launch)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $env:SystemRoot
try { Wait-Process -Id $ProcessId -Timeout 120 } catch { }
function Move-Retry([string]$From, [string]$To) {
  for ($i = 0; $i -lt 50; $i++) {
    try { Move-Item -LiteralPath $From -Destination $To; return $true } catch { Start-Sleep -Milliseconds 200 }
  }
  return $false
}
$backup = "$Target.previous"
Remove-Item -LiteralPath $backup -Recurse -Force -ErrorAction SilentlyContinue
if (-not (Test-Path -LiteralPath $backup) -and (Move-Retry $Target $backup)) {
  if (Move-Retry $Staged $Target) { Remove-Item -LiteralPath $backup -Recurse -Force -ErrorAction SilentlyContinue }
  else { [void](Move-Retry $backup $Target) }
}
Remove-Item -LiteralPath $Stage -Recurse -Force -ErrorAction SilentlyContinue
Start-Process -FilePath $Launch
`;

export interface SwapCommand { command: string; args: string[]; cwd: string }

/**
 * Writes the swap script and returns how to start it; `launch` opens the app once it is in place.
 * On Windows `launch` is a single executable path.
 */
export async function swapCommand(dir: string, platform: NodeJS.Platform, pid: number, staged: Extract<Staged, { kind: "restart" }>, launch: string[]): Promise<SwapCommand> {
  await mkdir(dir, { recursive: true });
  if (platform === "win32") {
    const script = join(dir, "swap.ps1");
    await writeFile(script, SWAP_PS1);
    return {
      command: join(process.env.SystemRoot ?? "C:\\Windows", "System32", "WindowsPowerShell", "v1.0", "powershell.exe"),
      args: ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", script,
        "-ProcessId", String(pid), "-Target", staged.target, "-Staged", staged.staged, "-Stage", staged.stage,
        "-Launch", launch[0]],
      cwd: dir,
    };
  }
  const script = join(dir, "swap.sh");
  await writeFile(script, SWAP_SH, { mode: 0o700 });
  return { command: "/bin/sh", args: [script, String(pid), staged.target, staged.staged, staged.stage, ...launch], cwd: dir };
}

/** The command that opens the installed app after the swap. */
export function launchCommand(platform: NodeJS.Platform, target: string): string[] {
  return platform === "darwin" ? ["/usr/bin/open", "-n", target] : [join(target, "Batatis.exe")];
}

/** The releases API and this repository's release downloads; GitHub's redirects from there are followed. */
export function trustedUpdateUrl(url: URL): boolean {
  if (url.protocol !== "https:" || url.username || url.password) return false;
  if (url.hostname === "api.github.com") return url.pathname === `/repos/${REPOSITORY}/releases`;
  if (url.hostname === "github.com") return url.pathname.startsWith(`/${REPOSITORY}/releases/download/`);
  return false;
}
