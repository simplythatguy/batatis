/**
 * The desktop host: which workspace runs, who is signed in to it, and every change between them.
 *
 * A change of person or workspace closes /api, waits for in-flight requests, switches the session (or
 * the engine), and then replaces the window. A window from before the change can no longer reach /api,
 * and a late answer cannot change the session. Nothing is retried after the engine goes away.
 * Electron stays outside: windows, dialogs and safeStorage arrive as dependencies.
 */
import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { importCodeDb, inspectCodeDb, installBundledCodeDb } from "./codedb";
import type { KeyVault, KeyStatus, SaveOutcome } from "./credentials";
import { isDevProfileId, startEngine, type CallReply, type DevProfile, type DevProfileId, type Engine, type EngineCommand, type EngineStart, type HostCall, type WorkspaceKind } from "./engine";
import type { ApiGate } from "./protocol";
import { PROVIDER_LABELS, unavailableProvider, type AccountId, type ConnectionState, type HostProvider, type KeyProviderId, type ProviderId, type WorkflowReadiness } from "./providers";
import { codeDbPath, type RuntimePaths } from "./runtime";
import { SessionJar, type TokenStore } from "./session";
import { ProviderDispatch } from "./provider-dispatch";
import { DEFAULT_SELECTION, MENU, defaultPick, parseSelection, type AiSelection, type Pick, type Slot, type Source } from "./models";
import { ProviderRpc } from "./provider-rpc";
import type { InstallState } from "./runtime-install";
import type { KeyProviders } from "./provider-http";
export { parseCompleteJson } from "./provider-dispatch";

const DRAIN_MS = 15_000;

export interface DesktopSettings {
  version: 1;
  workspace: WorkspaceKind;
  devProfile: DevProfileId | null;
  ai?: AiSelection;
}

export type ServiceState = "starting" | "ready" | "busy" | "failed";

export interface PersonInfo {
  profile: DevProfileId;
  name: string;
  kind: "applicant" | "reviewer";
  authority: string | null;
}

export interface DesktopInfo {
  version: string;
  platform: NodeJS.Platform;
  workspace: WorkspaceKind;
  service: { state: ServiceState; detail: string | null };
  person: PersonInfo | null;
  people: readonly PersonInfo[];
  codeDb: { available: boolean };
  voice: "unavailable";
}

export type ProviderRow =
  | { id: AccountId; kind: "account"; label: string; description: string; status: ConnectionState; workflow: WorkflowReadiness | null; runtime: InstallState | null }
  | { id: KeyProviderId; kind: "key"; label: string; description: string; status: { state: KeyStatus } };

export type Outcome = { ok: true } | { ok: false; message: string };

type Activity = "switching-person" | "switching-workspace" | "importing" | "restarting";

type HostState =
  | { kind: "starting"; workspace: WorkspaceKind }
  | { kind: "ready"; workspace: WorkspaceKind; engine: Engine; jar: SessionJar; person: DevProfileId | null }
  | { kind: "busy"; workspace: WorkspaceKind; engine: Engine | null; jar: SessionJar | null; person: DevProfileId | null; activity: Activity }
  | { kind: "failed"; workspace: WorkspaceKind; detail: string };

export interface HostDeps {
  paths: RuntimePaths;
  version: string;
  command: (kind: WorkspaceKind) => EngineCommand;
  start?: typeof startEngine;
  vault: KeyVault;
  /** The normal workspace's persisted session; Local development never persists one. */
  localSession: TokenStore & { load(): Promise<string | null> };
  /** The managed ChatGPT connection. */
  provider: HostProvider;
  /** The managed Claude connection; unavailable when omitted. */
  claude?: HostProvider;
  keys?: KeyProviders;
  log: (line: string) => void;
  /** Replace the window with a fresh one for `generation`, opening `route` (or the current one when null). */
  remount: (generation: number, route: string | null) => void;
  /** Something the window shows changed (service state, a provider's status). */
  notify: () => void;
  /** Each managed connection's downloadable runtime, when this build installs one. */
  runtime?: (id: AccountId) => InstallState | null;
}

const BUSY_DETAIL: Record<Activity, string> = {
  "switching-person": "Switching person…",
  "switching-workspace": "Switching workspace…",
  importing: "Adding the code database…",
  restarting: "Restarting…",
};

export class DesktopHost {
  #deps: HostDeps;
  #settings: DesktopSettings = { version: 1, workspace: "local", devProfile: null };
  #state: HostState = { kind: "starting", workspace: "local" };
  #generation = 0;
  #changing = false;
  #accounts: Record<AccountId, HostProvider>;
  #dispatch: ProviderDispatch;
  #rpc: ProviderRpc;
  #accountStops: Record<AccountId, () => void>;
  #engineRun = 0;
  #aiNote = "";
  /** Whether each account was signed in when last read; null until the first read. */
  #signedIn: Record<AccountId, boolean | null> = { chatgpt: null, claude: null };
  #picking: Promise<unknown> = Promise.resolve();
  #authReset = false;
  #disposed = false;
  #starting: Promise<EngineStart> | null = null;
  /** Engines this host is stopping on purpose; their exit is not a crash. */
  #stopping = new WeakSet<Engine>();
  #lost = new WeakSet<Engine>();

  constructor(deps: HostDeps) {
    this.#deps = deps;
    this.#accounts = { chatgpt: deps.provider, claude: deps.claude ?? unavailableProvider("This connection isn’t available in this version.", "claude") };
    this.#dispatch = new ProviderDispatch({ account: (id) => this.#accounts[id], vault: deps.vault, keys: deps.keys,
      accepting: () => !this.#disposed && !this.#changing && !this.#authReset && this.#state.kind === "ready" && this.#state.jar.token !== null });
    this.#rpc = new ProviderRpc(this.#dispatch.call, (lease) => this.#dispatch.valid(lease));
    const watch = (provider: HostProvider) => provider.onChange(() => { this.#invalidate(); deps.notify(); void this.#turnOnAfterSignIn(provider.id); });
    this.#accountStops = { chatgpt: watch(this.#accounts.chatgpt), claude: watch(this.#accounts.claude) };
  }

  get generation(): number {
    return this.#generation;
  }

  /** Load settings and start the last workspace. The first window opens after this. */
  async boot(): Promise<void> {
    this.#settings = await readSettings(this.#settingsFile());
    this.#dispatch.select(this.#settings.ai ?? DEFAULT_SELECTION);
    for (const id of ["chatgpt", "claude"] as const) {
      this.#signedIn[id] = await this.#accounts[id].status().then((status) => status.state === "signed-in", () => null);
    }
    if (this.#deps.paths.packaged) {
      await installBundledCodeDb(join(this.#deps.paths.resources, "codedb", "codedb.sqlite"), codeDbPath(this.#deps.paths))
        .catch(() => this.#deps.log("The bundled code database couldn’t be installed."));
    }
    await this.#run(this.#settings.workspace);
  }

  /** What /api may do for the window of `generation` right now. */
  gate(generation: number): ApiGate {
    if (this.#disposed) return { kind: "closed", detail: "Batatis is closing." };
    if (generation !== this.#generation) return { kind: "closed", detail: "This window was replaced. Use the current Batatis window." };
    const state = this.#state;
    if (this.#changing) return { kind: "closed", detail: "Updating the local workspace or AI connection…" };
    if (state.kind === "ready") return { kind: "open", engine: state.engine, jar: state.jar };
    if (state.kind === "busy") return { kind: "closed", detail: BUSY_DETAIL[state.activity] };
    if (state.kind === "starting") return { kind: "closed", detail: "Batatis is starting…" };
    return { kind: "closed", detail: state.detail };
  }

  /** The first window, or a window reopened on macOS after all were closed. */
  openWindow(route: string | null = null): number {
    if (this.#disposed) return this.#generation;
    this.#generation += 1;
    this.#deps.remount(this.#generation, route);
    return this.#generation;
  }

  info(): DesktopInfo {
    const state = this.#state;
    const engine = state.kind === "ready" || state.kind === "busy" ? state.engine : null;
    const people = (engine?.hello.profiles ?? []).map(personOf);
    const person = state.kind === "ready" || state.kind === "busy" ? people.find((p) => p.profile === state.person) ?? null : null;
    return {
      version: this.#deps.version,
      platform: this.#deps.paths.platform,
      workspace: state.workspace,
      service: {
        state: this.#changing && state.kind === "ready" ? "busy" : state.kind,
        detail: this.#changing && state.kind === "ready" ? "Updating AI connection…" : state.kind === "failed" ? state.detail : state.kind === "busy" ? BUSY_DETAIL[state.activity] : null,
      },
      person,
      people,
      codeDb: { available: engine?.hello.codedb.available ?? false },
      voice: "unavailable",
    };
  }

  /** Called after the window saved its work. Never claims, submits or edits anything as either person. */
  switchPerson(profile: string): Promise<Outcome> {
    return this.#exclusive(async () => {
      const state = this.#state;
      if (state.kind !== "ready" || state.workspace !== "dev") return refuse("People switch only in Local development.");
      const target = state.engine.hello.profiles.find((p) => p.profile === profile);
      if (!target) return refuse("That person isn’t in this workspace.");
      if (target.profile === state.person) return { ok: true };
      this.#invalidate();
      const { engine, jar } = state;
      this.#state = { ...state, kind: "busy", activity: "switching-person" };
      this.#deps.notify();
      if (!(await engine.idle(DRAIN_MS))) {
        this.#restore(state);
        return refuse("Something is still running. Try again in a moment.");
      }
      const session = await engine.control("dev.session", { profile: target.profile, ...(jar.token ? { revoke: jar.token } : {}) });
      const token = session.ok ? tokenOf(session.value) : null;
      if (!token) {
        this.#restore(state);
        return refuse("The switch didn’t complete. You are still signed in as before.");
      }
      jar.replace(token);
      this.#settings = { ...this.#settings, devProfile: target.profile };
      await writeSettings(this.#settingsFile(), this.#settings);
      this.#engineRun += 1;
      await this.#stopEngine(engine);
      const restarted = await this.#run("dev");
      this.openWindow(target.kind === "reviewer" ? "#/review" : "#/");
      return restarted ? { ok: true } : refuse("The local service needs a restart.");
    });
  }

  switchWorkspace(kind: WorkspaceKind): Promise<Outcome> {
    return this.#exclusive(async () => {
      if (this.#state.workspace === kind && this.#state.kind === "ready") return { ok: true };
      const drained = await this.#stopCurrent("switching-workspace");
      if (!drained) return refuse("Something is still running. Try again in a moment.");
      this.#settings = { ...this.#settings, workspace: kind };
      await writeSettings(this.#settingsFile(), this.#settings);
      await this.#run(kind);
      this.openWindow("#/");
      return this.#state.kind === "ready" ? { ok: true } : refuse(this.#state.kind === "failed" ? this.#state.detail : "Batatis didn’t start.");
    });
  }

  /** After the engine stopped, or on request. Saved work is read back; nothing is replayed. */
  restart(): Promise<Outcome> {
    return this.#exclusive(async () => {
      const drained = await this.#stopCurrent("restarting");
      if (!drained) return refuse("Something is still running. Try again in a moment.");
      await this.#run(this.#state.workspace);
      this.openWindow(null);
      return this.#state.kind === "ready" ? { ok: true } : refuse(this.#state.kind === "failed" ? this.#state.detail : "Batatis didn’t start.");
    });
  }

  /** A file the person picked in the native open dialog. */
  addCodeDb(file: string): Promise<Outcome> {
    return this.#exclusive(async () => {
      const state = this.#state;
      if (state.kind !== "ready") return refuse("Batatis isn’t ready yet.");
      const expected = state.engine.hello.codedb.expectedBuild;
      const checked = inspectCodeDb(file, expected);
      if (!checked.ok) return refuse(checked.reason);
      const drained = await this.#stopCurrent("importing");
      if (!drained) return refuse("Something is still running. Try again in a moment.");
      const imported = await importCodeDb(file, codeDbPath(this.#deps.paths), expected).catch(() => ({ ok: false as const, reason: "The code database couldn’t be copied." }));
      await this.#run(state.workspace);
      this.openWindow(null);
      if (!imported.ok) return refuse(imported.reason);
      return this.#state.kind === "ready" ? { ok: true } : refuse("Batatis didn’t restart after adding the code database.");
    });
  }

  async providerRows(): Promise<ProviderRow[]> {
    const row = <T extends ProviderId>(id: T) => ({ id, ...PROVIDER_LABELS[id] });
    const account = async (id: AccountId): Promise<ProviderRow> => {
      const status = await this.#accounts[id].status();
      const workflow = status.state === "signed-in" ? await this.#accounts[id].workflowReadiness() : null;
      return { ...row(id), kind: "account", status, workflow, runtime: this.#deps.runtime?.(id) ?? null };
    };
    return [
      await account("chatgpt"),
      await account("claude"),
      { ...row("batatis"), kind: "key", status: { state: await this.#deps.vault.status("batatis") } },
      { ...row("openai"), kind: "key", status: { state: await this.#deps.vault.status("openai") } },
      { ...row("jev"), kind: "key", status: { state: await this.#deps.vault.status("jev") } },
    ];
  }

  account(id: AccountId): HostProvider {
    return this.#accounts[id];
  }

  /** Replace a managed connection (an installed adapter); the old one is disposed. */
  async installProvider(next: HostProvider): Promise<void> {
    if (this.#disposed) { await next.dispose(); return; }
    const previous = this.#accounts[next.id];
    this.#invalidate();
    this.#accountStops[next.id]();
    this.#accounts[next.id] = next;
    this.#accountStops[next.id] = next.onChange(() => { this.#invalidate(); this.#deps.notify(); void this.#turnOnAfterSignIn(next.id); });
    await previous.dispose();
    this.#deps.notify();
  }

  configuration() {
    const sources = (Object.keys(MENU) as Source[]).map((source) => ({
      value: source, label: MENU[source].label, models: MENU[source].models, default: MENU[source].default,
    }));
    return { ...this.#dispatch.selection, sources, note: this.#aiNote,
      screeningLabel: "Optional Jev screening", help: "Off sends no AI work. A subscription is used only when chosen; an API key uses separate API billing only when chosen. Missing optional screening uses the labeled keyword fallback. Errors never change your choice." };
  }

  /**
   * Picks what answers one kind of work. Choosing a source while the other kind is off picks it for both,
   * with that source's default model, so one choice turns the app on.
   *
   * Unlike a key or screening change this keeps the engine and window: the engine reads the pick per
   * request, and the new lease cancels work still running under the old one.
   */
  selectModel(slot: Slot, pick: Pick): Promise<Outcome> {
    const run = async (): Promise<Outcome> => {
      if (this.#disposed) return refuse("Batatis is closing.");
      if (this.#changing) return refuse("Another change is still running.");
      const current = this.#dispatch.selection;
      const other: Slot = slot === "workflow" ? "chat" : "workflow";
      const ai: AiSelection = { ...current, [slot]: pick,
        ...(pick.source !== "off" && current[other].source === "off" ? { [other]: defaultPick(pick.source) } : {}) };
      const settings = { ...this.#settings, ai };
      await writeSettings(this.#settingsFile(), settings);
      this.#settings = settings;
      this.#dispatch.select(ai);
      this.#aiNote = "";
      this.#deps.notify();
      return { ok: true };
    };
    const next = this.#picking.then(run, run).catch((): Outcome => refuse("The AI change could not be saved. Try again."));
    this.#picking = next;
    return next;
  }

  selectScreening(screening: boolean): Promise<Outcome> {
    return this.#changeAI(async () => {
      const ai = { ...this.#dispatch.selection, screening };
      const settings = { ...this.#settings, ai };
      await writeSettings(this.#settingsFile(), settings);
      this.#settings = settings; this.#dispatch.select(ai);
    });
  }

  removeKey(id: KeyProviderId): Promise<Outcome> {
    return this.#changeAI(() => this.#deps.vault.remove(id));
  }

  async saveKey(id: KeyProviderId, key: string): Promise<SaveOutcome> {
    let saved: SaveOutcome = "invalid";
    await this.#changeAI(async () => { saved = await this.#deps.vault.save(id, key); });
    return saved;
  }

  disconnectProvider(id: AccountId): Promise<Outcome> {
    return this.#changeAI(async () => { await this.#accounts[id].logout(); });
  }

  readonly onCall: HostCall = (op, args, signal): Promise<CallReply> => this.#rpc.call(op, args, signal);

  cancelAI() { this.#invalidate(); }

  prepareSessionChange() {
    const state = this.#state;
    if (state.kind === "ready" && state.jar.token !== null) this.#authReset = true;
    this.#invalidate();
  }

  /**
   * Signing in is the person's request to use that account, so a first sign-in while both kinds of work
   * are Off turns them on with that account's default model. A later sign-in never overrides a pick.
   */
  async #turnOnAfterSignIn(id: AccountId): Promise<void> {
    const before = this.#signedIn[id];
    try {
      const signedIn = (await this.#accounts[id].status()).state === "signed-in";
      this.#signedIn[id] = signedIn;
      if (!signedIn || before !== false || this.#disposed) return;
      const { workflow, chat } = this.#dispatch.selection;
      if (workflow.source === "off" && chat.source === "off") await this.selectModel("workflow", defaultPick(id));
    } catch { /* the sign-in itself already reported; the pickers stay as they were */ }
  }

  #invalidate() { this.#dispatch.invalidate(); this.#rpc.clear(); }

  async #changeAI(work: () => Promise<void>): Promise<Outcome> {
    const outcome = await this.#exclusive(async () => {
      this.#invalidate();
      const state = this.#state;
      if (state.kind !== "ready") return refuse("The local service is not ready.");
      if (!(await state.engine.idle(DRAIN_MS))) return refuse("A check is still stopping. Try again in a moment.");
      const localToken = state.jar.token;
      await work();
      if (this.#disposed) return refuse("Batatis is closing.");
      this.#engineRun += 1;
      await this.#stopEngine(state.engine);
      const restarted = await this.#run(state.workspace, localToken);
      this.openWindow(null);
      return restarted ? { ok: true } : refuse("The local service needs a restart.");
    }).catch((): Outcome => refuse("The AI change could not be saved. Try again."));
    this.#aiNote = outcome.ok ? "" : outcome.message;
    this.#deps.notify();
    return outcome;
  }

  async dispose(): Promise<void> {
    this.#disposed = true;
    const state = this.#state;
    this.#generation += 1;
    this.#engineRun += 1;
    this.#changing = true;
    this.#invalidate();
    this.#accountStops.chatgpt();
    this.#accountStops.claude();
    if ((state.kind === "ready" || state.kind === "busy") && state.engine) {
      await this.#stopEngine(state.engine);
    }
    const starting = this.#starting;
    if (starting) {
      const started = await starting;
      if (started.kind === "ready") await this.#stopEngine(started.engine);
    }
    await Promise.all([this.#accounts.chatgpt.dispose(), this.#accounts.claude.dispose()]);
  }

  async #stopEngine(engine: Engine): Promise<void> {
    if (this.#stopping.has(engine)) { await engine.exited; return; }
    this.#stopping.add(engine);
    await engine.stop();
  }

  #settingsFile(): string {
    return join(this.#deps.paths.userData, "settings.json");
  }

  async #exclusive(work: () => Promise<Outcome>): Promise<Outcome> {
    if (this.#disposed) return refuse("Batatis is closing.");
    if (this.#changing) return refuse("Another change is still running.");
    this.#changing = true;
    this.#deps.notify();
    try {
      return await work();
    } finally {
      this.#changing = this.#disposed;
      this.#deps.notify();
    }
  }

  /** Close /api, wait for in-flight requests, stop the engine. False (and nothing stopped) if work kept running. */
  async #stopCurrent(activity: Activity): Promise<boolean> {
    this.#invalidate();
    const state = this.#state;
    if (state.kind !== "ready") {
      this.#state = { kind: "busy", workspace: state.workspace, engine: null, jar: null, person: null, activity };
      return true;
    }
    this.#state = { ...state, kind: "busy", activity };
    this.#deps.notify();
    if (!(await state.engine.idle(DRAIN_MS))) {
      this.#restore(state);
      return false;
    }
    await this.#stopEngine(state.engine);
    return true;
  }

  /** Back to the state before a change that did not happen, unless its engine died meanwhile. */
  #restore(state: Extract<HostState, { kind: "ready" }>) {
    this.#state = this.#lost.has(state.engine) ? crashed(state.workspace) : state;
    this.#deps.notify();
  }

  async #run(kind: WorkspaceKind, localToken?: string | null): Promise<boolean> {
    const run = ++this.#engineRun;
    this.#state = { kind: "starting", workspace: kind };
    this.#deps.notify();
    const onCall: HostCall = (op, args, signal) => run === this.#engineRun && !this.#disposed
      ? this.onCall(op, args, signal) : Promise.resolve({ ok: false, reason: "cancelled", message: "This engine was replaced." });
    const pending = (this.#deps.start ?? startEngine)(this.#deps.command(kind), { onCall, log: this.#deps.log });
    this.#starting = pending;
    const started = await pending;
    if (this.#starting === pending) this.#starting = null;
    if (this.#disposed || run !== this.#engineRun) {
      if (started.kind === "ready") await this.#stopEngine(started.engine);
      return false;
    }
    if (started.kind !== "ready") {
      this.#state = { kind: "failed", workspace: kind, detail: started.kind === "refused" ? `This workspace can’t open: ${started.reason}` : started.detail };
      this.#deps.log(`engine did not start: ${started.kind}`);
      return false;
    }
    const engine = started.engine;
    if (engine.hello.workspace.kind !== kind) {
      await this.#stopEngine(engine);
      this.#state = { kind: "failed", workspace: kind, detail: "The local service opened the wrong workspace." };
      return false;
    }
    let jar: SessionJar;
    let person: DevProfileId | null = null;
    if (kind === "dev") {
      const remembered = engine.hello.profiles.find((p) => p.profile === this.#settings.devProfile);
      const profile = (remembered ?? engine.hello.profiles.find((p) => p.kind === "applicant"))?.profile ?? "applicant";
      const session = await engine.control("dev.session", { profile });
      const token = session.ok ? tokenOf(session.value) : null;
      if (!token) {
        await this.#stopEngine(engine);
        this.#state = { kind: "failed", workspace: kind, detail: "Local development couldn’t sign in its test person." };
        return false;
      }
      jar = new SessionJar(token);
      person = profile;
    } else {
      jar = new SessionJar(localToken === undefined ? await this.#deps.localSession.load() : localToken, {
        save: async (token) => {
          this.#invalidate();
          const reset = this.#authReset || token === null;
          if (reset) this.#authReset = true;
          await this.#deps.localSession.save(token);
          if (reset) setTimeout(() => { if (!this.#changing && !this.#disposed) void this.#changeAI(async () => {}); }, 0);
        },
      });
    }
    if (this.#disposed || run !== this.#engineRun) { await this.#stopEngine(engine); return false; }
    this.#authReset = false;
    this.#state = { kind: "ready", workspace: kind, engine, jar, person };
    void engine.exited.then(() => {
      if (this.#stopping.has(engine)) return;
      this.#lost.add(engine);
      const current = this.#state;
      if (current.kind === "ready" && current.engine === engine) {
        this.#state = crashed(kind);
        this.#deps.log("engine exited unexpectedly");
        this.#deps.notify();
      }
    });
    return true;
  }
}

function crashed(workspace: WorkspaceKind): HostState {
  return { kind: "failed", workspace, detail: "The local service stopped unexpectedly. Restart to read your saved work again." };
}

function refuse(message: string): Outcome {
  return { ok: false, message };
}

function personOf(profile: DevProfile): PersonInfo {
  return { profile: profile.profile, name: profile.name, kind: profile.kind, authority: profile.authority };
}

function tokenOf(value: unknown): string | null {
  if (typeof value !== "object" || value === null || !("token" in value)) return null;
  return typeof value.token === "string" ? value.token : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export async function readSettings(file: string): Promise<DesktopSettings> {
  try {
    const raw: unknown = JSON.parse(await readFile(file, "utf8"));
    if (!isRecord(raw) || raw.version !== 1) throw new Error("unknown settings");
    const workspace = raw.workspace === "dev" ? "dev" : "local";
    return { version: 1, workspace, devProfile: isDevProfileId(raw.devProfile) ? raw.devProfile : null,
      ...(parseSelection(raw.ai) ? { ai: parseSelection(raw.ai) ?? undefined } : {}) };
  } catch {
    return { version: 1, workspace: "local", devProfile: null };
  }
}

async function writeSettings(file: string, settings: DesktopSettings): Promise<void> {
  await mkdir(dirname(file), { recursive: true });
  await writeFile(`${file}.partial`, JSON.stringify(settings, null, 2));
  await rename(`${file}.partial`, file);
}
