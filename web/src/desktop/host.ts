/**
 * The desktop host, when this page runs in the Batatis desktop app (desktop/src/preload/app.ts); absent on
 * the web. Every answer is parsed here. Provider ids and labels are opaque host data: this file names none.
 */
import { useSyncExternalStore } from "react";

export type WorkspaceKind = "local" | "dev";
export type ServiceState = "starting" | "ready" | "busy" | "failed";

export interface Person {
  profile: string;
  name: string;
  kind: "applicant" | "reviewer";
  authority: string | null;
}

export interface DesktopInfo {
  version: string;
  workspace: WorkspaceKind;
  service: { state: ServiceState; detail: string | null };
  person: Person | null;
  people: Person[];
  codeDb: { available: boolean };
}

export type Outcome = { ok: true } | { ok: false; message: string };
export type Slot = "workflow" | "chat";
/** What answers one kind of AI work. Sources and models are opaque host data. */
export interface PickOn { source: string; model: string; effort: string }
export type Pick = { source: "off" } | PickOn;
export const isOn = (pick: Pick): pick is PickOn => pick.source !== "off";
export interface MenuModel { id: string; label: string; efforts: string[] }
export interface SourceMenu { value: string; label: string; models: MenuModel[]; default: { model: string; effort: string } }

export interface AiConfiguration {
  workflow: Pick;
  chat: Pick;
  screening: boolean;
  sources: SourceMenu[];
  screeningLabel: string;
  help: string;
  note: string;
}

export type Connection =
  | { state: "unavailable"; message: string }
  | { state: "signed-out"; last: string | null }
  /**
   * Sign-in in progress. Device sign-in: the person enters userCode at the address shown. Browser sign-in:
   * no code, and the address (when known) reopens the page. The host opens the address on request.
   * acceptsCode: a page opened by hand may end by showing a code to paste back here.
   */
  | { state: "pending"; userCode: string | null; address: string | null; acceptsCode: boolean }
  | { state: "signed-in"; plan: string | null }
  | { state: "error"; message: string };

/** The account connection's downloadable runtime, as the host reports it. */
export type Runtime =
  | { state: "unsupported" }
  | { state: "missing" }
  | { state: "outdated"; installed: string }
  | { state: "installing"; received: number; total: number }
  | { state: "installed"; version: string }
  | { state: "failed"; message: string };

export type ProviderRow =
  | { id: string; kind: "account"; label: string; description: string; status: Connection; workflow: string | null; runtime: Runtime | null }
  | { id: string; kind: "key"; label: string; description: string; status: "missing" | "saved" | "secure-storage-unavailable" };

export interface ReleaseNote { version: string; items: string[]; more: number; url: string }
export interface UpdateRelease { version: string; url: string; notes: ReleaseNote[]; older: number; history: string; downloadable: boolean }

/** The app's own update, as the host reports it. Links are https pages on GitHub. `beta` is whether betas are offered. */
export type UpdateView = UpdateState & { beta: boolean };
type UpdateState =
  | { status: "unavailable"; current: string; message: string }
  | { status: "idle"; current: string; checked: boolean }
  | { status: "checking"; current: string }
  | { status: "available"; current: string; release: UpdateRelease }
  | { status: "downloading"; current: string; release: UpdateRelease; percent: number | null }
  | { status: "ready"; current: string; release: UpdateRelease; install: "restart" | "manual" }
  | { status: "failed"; current: string; release: UpdateRelease | null; message: string };

interface Bridge {
  version: number;
  info(): Promise<unknown>;
  restart(): Promise<unknown>;
  switchWorkspace(kind: string): Promise<unknown>;
  switchPerson(profile: string): Promise<unknown>;
  providers: Record<"list" | "enterKey" | "removeKey" | "install" | "connect" | "openLogin" | "cancelLogin" | "disconnect", (id?: string) => Promise<unknown>> & {
    configuration(): Promise<unknown>;
    selectModel(slot: Slot, pick: Pick): Promise<unknown>;
    selectScreening(value: boolean): Promise<unknown>;
    submitLoginCode(id: string, code: string): Promise<unknown>;
  };
  codeDb: { choose(): Promise<unknown> };
  updates?: Record<"state" | "check" | "download" | "install", () => Promise<unknown>> & { setBeta(beta: boolean): Promise<unknown>; onChange(listener: () => void): () => void };
  onChange(listener: () => void): () => void;
}

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const str = (value: unknown): string | null => (typeof value === "string" ? value : null);

function isBridge(value: unknown): value is Bridge {
  return isRecord(value) && value.version === 1 && typeof value.info === "function" && isRecord(value.providers) && isRecord(value.codeDb);
}

function bridge(): Bridge | null {
  const candidate: unknown = typeof window === "undefined" ? undefined : Reflect.get(window, "batatisDesktop");
  return isBridge(candidate) ? candidate : null;
}

function parsePerson(value: unknown): Person | null {
  if (!isRecord(value)) return null;
  const profile = str(value.profile), name = str(value.name);
  if (!profile || !name || (value.kind !== "applicant" && value.kind !== "reviewer")) return null;
  return { profile, name, kind: value.kind, authority: str(value.authority) };
}

export function parseInfo(value: unknown): DesktopInfo | null {
  if (!isRecord(value) || !isRecord(value.service) || !isRecord(value.codeDb)) return null;
  const workspace = value.workspace, state = value.service.state;
  if (workspace !== "local" && workspace !== "dev") return null;
  if (state !== "starting" && state !== "ready" && state !== "busy" && state !== "failed") return null;
  const people = Array.isArray(value.people) ? value.people.map(parsePerson).filter((p): p is Person => p !== null) : [];
  return {
    version: str(value.version) ?? "",
    workspace,
    service: { state, detail: str(value.service.detail) },
    person: parsePerson(value.person),
    people,
    codeDb: { available: value.codeDb.available === true },
  };
}

export function parseOutcome(value: unknown): Outcome {
  if (isRecord(value) && value.ok === true) return { ok: true };
  const message = isRecord(value) ? str(value.message) : null;
  return { ok: false, message: message ?? "That didn’t work. Try again." };
}

function parseSources(value: unknown): SourceMenu[] | null {
  if (!Array.isArray(value)) return null;
  const sources: SourceMenu[] = [];
  for (const item of value) {
    if (!isRecord(item) || !Array.isArray(item.models) || !isRecord(item.default)) return null;
    const source = str(item.value), label = str(item.label), model = str(item.default.model), effort = str(item.default.effort);
    if (!source || !label || !model || !effort) return null;
    const models: MenuModel[] = [];
    for (const entry of item.models) {
      const id = isRecord(entry) ? str(entry.id) : null, name = isRecord(entry) ? str(entry.label) : null;
      if (!isRecord(entry) || !id || !name || !Array.isArray(entry.efforts)) return null;
      models.push({ id, label: name, efforts: entry.efforts.filter((e): e is string => typeof e === "string") });
    }
    sources.push({ value: source, label, models, default: { model, effort } });
  }
  return sources;
}

/** A pick is kept only when it names a model and effort on the host's own menu. */
function parsePick(value: unknown, sources: SourceMenu[]): Pick | null {
  if (!isRecord(value)) return null;
  if (value.source === "off") return { source: "off" };
  const menu = sources.find((item) => item.value === value.source);
  const model = menu?.models.find((item) => item.id === value.model);
  return menu && model && typeof value.effort === "string" && model.efforts.includes(value.effort)
    ? { source: menu.value, model: model.id, effort: value.effort } : null;
}

export function parseConfiguration(value: unknown): AiConfiguration | null {
  if (!isRecord(value) || typeof value.screening !== "boolean" || typeof value.screeningLabel !== "string" || typeof value.help !== "string") return null;
  const sources = parseSources(value.sources);
  const workflow = sources && parsePick(value.workflow, sources), chat = sources && parsePick(value.chat, sources);
  if (!sources || !workflow || !chat) return null;
  return { workflow, chat, screening: value.screening, sources, screeningLabel: value.screeningLabel, help: value.help, note: str(value.note) ?? "" };
}

/** Live AI configuration for React, so the chat picker follows Settings; null on the web. */
let configuration: AiConfiguration | null = null;
let configurationStarted = false;
const configurationListeners = new Set<() => void>();

async function refreshConfiguration() {
  const host = bridge();
  if (!host) return;
  configuration = parseConfiguration(await host.providers.configuration().catch(() => null));
  for (const listener of configurationListeners) listener();
}

function subscribeConfiguration(listener: () => void) {
  configurationListeners.add(listener);
  if (!configurationStarted && bridge()) {
    configurationStarted = true;
    bridge()?.onChange(() => void refreshConfiguration());
    void refreshConfiguration();
  }
  return () => { configurationListeners.delete(listener); };
}

export function useAiConfiguration(): AiConfiguration | null {
  return useSyncExternalStore(subscribeConfiguration, () => configuration, () => null);
}

function parseConnection(value: unknown): Connection | null {
  if (!isRecord(value)) return null;
  switch (value.state) {
    case "unavailable": return { state: "unavailable", message: str(value.message) ?? "Not available." };
    case "pending": {
      const userCode = str(value.userCode) || null, address = displayAddress(value.verificationUrl);
      return userCode && !address ? null : { state: "pending", userCode, address, acceptsCode: value.acceptsCode === true };
    }
    case "signed-in": return { state: "signed-in", plan: str(value.plan) };
    case "error": return { state: "error", message: str(value.message) ?? "Something went wrong." };
    case "signed-out": {
      const last = isRecord(value.last) ? value.last : null;
      const note = last?.result === "cancelled" ? "Sign-in cancelled." : last ? str(last.message) : null;
      return { state: "signed-out", last: note };
    }
    default: return null;
  }
}

function displayAddress(value: unknown): string | null {
  try {
    const url = new URL(str(value) ?? "");
    return url.protocol === "https:" ? `${url.host}${url.pathname === "/" ? "" : url.pathname}` : null;
  } catch {
    return null;
  }
}

function parseRuntime(value: unknown): Runtime | null {
  if (!isRecord(value)) return null;
  const count = (n: unknown) => (typeof n === "number" && Number.isFinite(n) && n >= 0 ? n : null);
  switch (value.state) {
    case "unsupported": case "missing": return { state: value.state };
    case "outdated": return { state: "outdated", installed: str(value.installed) ?? "" };
    case "installed": return { state: "installed", version: str(value.version) ?? "" };
    case "failed": return { state: "failed", message: str(value.message) ?? "The install didn’t finish." };
    case "installing": {
      const received = count(value.received), total = count(value.total);
      return received !== null && total ? { state: "installing", received: Math.min(received, total), total } : null;
    }
    default: return null;
  }
}

export function parseRows(value: unknown): ProviderRow[] {
  if (!Array.isArray(value)) return [];
  const rows: ProviderRow[] = [];
  for (const item of value) {
    if (!isRecord(item)) continue;
    const id = str(item.id), label = str(item.label), description = str(item.description) ?? "";
    if (!id || !label) continue;
    if (item.kind === "account") {
      const status = parseConnection(item.status);
      if (status) rows.push({ id, kind: "account", label, description, status,
        workflow: isRecord(item.workflow) && item.workflow.ready === false ? str(item.workflow.message) : null, runtime: parseRuntime(item.runtime) });
    } else if (item.kind === "key" && isRecord(item.status)) {
      const state = item.status.state;
      if (state === "missing" || state === "saved" || state === "secure-storage-unavailable") rows.push({ id, kind: "key", label, description, status: state });
    }
  }
  return rows;
}

const github = (value: unknown): string | null => {
  try {
    const url = new URL(str(value) ?? "");
    return url.protocol === "https:" && url.hostname === "github.com" ? url.toString() : null;
  } catch {
    return null;
  }
};

function parseRelease(value: unknown): UpdateRelease | null {
  if (!isRecord(value) || !Array.isArray(value.notes)) return null;
  const version = str(value.version), url = github(value.url), history = github(value.history);
  if (!version || !url || !history) return null;
  const notes: ReleaseNote[] = [];
  for (const note of value.notes) {
    const noteVersion = isRecord(note) ? str(note.version) : null, noteUrl = isRecord(note) ? github(note.url) : null;
    if (!isRecord(note) || !noteVersion || !noteUrl || !Array.isArray(note.items)) continue;
    notes.push({ version: noteVersion, url: noteUrl, items: note.items.filter((item): item is string => typeof item === "string"),
      more: typeof note.more === "number" && note.more > 0 ? Math.floor(note.more) : 0 });
  }
  const older = typeof value.older === "number" && value.older > 0 ? Math.floor(value.older) : 0;
  return { version, url, notes, older, history, downloadable: value.downloadable === true };
}

export function parseUpdate(value: unknown): UpdateView | null {
  if (!isRecord(value)) return null;
  const state = parseUpdateState(value);
  return state && { ...state, beta: value.beta === true };
}

function parseUpdateState(value: Record<string, unknown>): UpdateState | null {
  const current = str(value.current) ?? "";
  const release = parseRelease(value.release);
  switch (value.status) {
    case "unavailable": return { status: "unavailable", current, message: str(value.message) ?? "" };
    case "idle": return { status: "idle", current, checked: value.checked === true };
    case "checking": return { status: "checking", current };
    case "available": return release && { status: "available", current, release };
    case "downloading": {
      const percent = typeof value.percent === "number" && Number.isFinite(value.percent) ? Math.min(100, Math.max(0, value.percent)) : null;
      return release && { status: "downloading", current, release, percent };
    }
    case "ready": return release && (value.install === "restart" || value.install === "manual") ? { status: "ready", current, release, install: value.install } : null;
    case "failed": return { status: "failed", current, release, message: str(value.message) ?? "Something went wrong." };
    default: return null;
  }
}

/** Live update state for React; null on the web and until the host first answers. */
let update: UpdateView | null = null;
let updateStarted = false;
const updateListeners = new Set<() => void>();

function publishUpdate(next: UpdateView | null) {
  update = next;
  for (const listener of updateListeners) listener();
}

async function refreshUpdate() {
  const updates = bridge()?.updates;
  if (updates) publishUpdate(parseUpdate(await updates.state().catch(() => null)));
}

function subscribeUpdate(listener: () => void) {
  updateListeners.add(listener);
  const updates = bridge()?.updates;
  if (!updateStarted && updates) {
    updateStarted = true;
    updates.onChange(() => void refreshUpdate());
    void refreshUpdate();
  }
  return () => { updateListeners.delete(listener); };
}

export function useUpdate(): UpdateView | null {
  return useSyncExternalStore(subscribeUpdate, () => update, () => null);
}

const setBetaUpdates = async (beta: boolean): Promise<void> => {
  const updates = bridge()?.updates;
  if (!updates) return;
  const next = parseUpdate(await updates.setBeta(beta).catch(() => null));
  if (next) publishUpdate(next);
};

const updateAction = (action: "check" | "download") => async (): Promise<void> => {
  const updates = bridge()?.updates;
  if (!updates) return;
  const next = parseUpdate(await updates[action]().catch(() => null));
  if (next) publishUpdate(next);
};

/** Live desktop info for React; null on the web and until the host first answers. */
let info: DesktopInfo | null = null;
let started = false;
const listeners = new Set<() => void>();

async function refresh() {
  const host = bridge();
  if (!host) return;
  info = parseInfo(await host.info().catch(() => null));
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  if (!started && bridge()) {
    started = true;
    bridge()?.onChange(() => void refresh());
    void refresh();
  }
  return () => { listeners.delete(listener); };
}

export function useDesktop(): DesktopInfo | null {
  return useSyncExternalStore(subscribe, () => info, () => null);
}

export const isDesktop = (): boolean => bridge() !== null;

const call = async <T>(work: (host: Bridge) => Promise<unknown>, parse: (value: unknown) => T, fallback: T): Promise<T> => {
  const host = bridge();
  if (!host) return fallback;
  try {
    return parse(await work(host));
  } catch {
    return fallback;
  }
};

const failed: Outcome = { ok: false, message: "That didn’t work. Try again." };

export const desktop = {
  switchPerson: (profile: string) => call((h) => h.switchPerson(profile), parseOutcome, failed),
  switchWorkspace: (kind: WorkspaceKind) => call((h) => h.switchWorkspace(kind), parseOutcome, failed),
  restart: () => call((h) => h.restart(), parseOutcome, failed),
  chooseCodeDb: () => call((h) => h.codeDb.choose(), parseOutcome, failed),
  providers: (action: "list" | "enterKey" | "removeKey" | "install" | "connect" | "openLogin" | "cancelLogin" | "disconnect", id?: string) => call((h) => h.providers[action](id), parseRows, []),
  submitLoginCode: (id: string, code: string) => call((h) => h.providers.submitLoginCode(id, code), parseRows, []),
  configuration: () => call((h) => h.providers.configuration(), parseConfiguration, null),
  refreshConfiguration,
  selectModel: async (slot: Slot, pick: Pick) => {
    const outcome = await call((h) => h.providers.selectModel(slot, pick), parseOutcome, failed);
    await refreshConfiguration();
    return outcome;
  },
  selectScreening: (value: boolean) => call((h) => h.providers.selectScreening(value), parseOutcome, failed),
  onChange: (listener: () => void): (() => void) => bridge()?.onChange(listener) ?? (() => {}),
  updates: {
    check: updateAction("check"),
    download: updateAction("download"),
    setBeta: setBetaUpdates,
    install: () => call((h) => h.updates ? h.updates.install() : Promise.resolve(null), parseOutcome, failed),
  },
};
