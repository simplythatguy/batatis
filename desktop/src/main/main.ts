/**
 * Electron entry: one hardened window per generation, the private engine, native dialogs and safeStorage.
 * Everything the window may ask for goes through validated IPC; the page never sees a path, key or cookie.
 */
import { app, BrowserWindow, dialog, ipcMain, net, protocol, safeStorage, session, shell, type IpcMainInvokeEvent, type Session, type WebContents } from "electron";
import { execFile, spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import { mkdir, mkdtemp, readFile, realpath, rm } from "node:fs/promises";
import { extname, join, resolve, sep } from "node:path";
import { DesktopHost, type Outcome } from "./controller";
import { KeyVault, type SecretBox } from "./credentials";
import { createAppProtocol, ORIGIN } from "./protocol";
import { unavailableProvider, type AccountId, type HostProvider, type KeyProviderId } from "./providers";
import { isSlot, parsePick } from "./models";
import { record } from "./provider-dispatch";
import { RuntimeInstaller, type RuntimePin } from "./runtime-install";
import { claudePin } from "./claude/release";
import { claudeProviderFactory } from "./claude/provider";
import { codexPin } from "./codex/install";
import { codexProviderFactory } from "./codex";
import { reviewedContextForPlatform } from "./trusted-context";
import { workflowFixture } from "./workflow-fixture";
import { withProviderCancellation } from "./provider-protocol";
import { codexInstallRoot, codexRuntime, engineCommand, webDist, workspaceDir, type RuntimePaths } from "./runtime";
import { SealedTokenStore, type SessionBox } from "./session";
import { startEngine, type Engine } from "./engine";
import { monitorSmoke, runSmoke, smokeOptions } from "./smoke";
import { launchCommand, RELEASES_FEED, swapCommand, trustedUpdateUrl, Updater } from "./updates";

const KEY_ORIGIN = "batatis-key://dialog";
const KEY_CSP = "default-src 'none'; script-src 'self'; style-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'";

protocol.registerSchemesAsPrivileged([
  { scheme: "batatis", privileges: { standard: true, secure: true, supportFetchAPI: true, stream: true } },
  { scheme: "batatis-key", privileges: { standard: true, secure: true } },
]);
app.enableSandbox();
if (process.platform === "win32" && process.env.LOCALAPPDATA) {
  // Workspaces and code data stay on this machine, not in the roaming profile.
  const userData = join(process.env.LOCALAPPDATA, "Batatis");
  mkdirSync(userData, { recursive: true });
  app.setPath("userData", userData);
}
const smoke = smokeOptions();
const smokeMonitor = monitorSmoke(smoke);
if (smoke) app.setPath("userData", smoke.userData);

const packaged = app.isPackaged;
const paths: RuntimePaths = {
  userData: app.getPath("userData"),
  resources: packaged ? process.resourcesPath : resolve(__dirname, "..", "..", ".."),
  packaged,
  platform: process.platform,
};

/** safeStorage is the only encryption; on Linux a plain-text backend counts as unavailable. */
const os: SecretBox & SessionBox = {
  available: async () => (await safeStorage.isAsyncEncryptionAvailable())
    && (process.platform !== "linux" || safeStorage.getSelectedStorageBackend() !== "basic_text"),
  encrypt: (plain) => safeStorage.encryptStringAsync(plain),
  decrypt: async (sealed) => (await safeStorage.decryptStringAsync(sealed)).result,
};

const vault = new KeyVault(join(paths.userData, "providers"), os);
let current: BrowserWindow | null = null;
let keyDialog: { id: KeyProviderId; window: BrowserWindow; done: (outcome: string) => void } | null = null;

function log(line: string) {
  if (!packaged || smoke) process.stderr.write(`${line}\n`);
}

const fixture = smoke ? workflowFixture() : null;
const smokeEngines: Engine[] = [];

const runTool = (command: string, args: string[]) => new Promise<string>((done, fail) => {
  execFile(command, args, { windowsHide: true, maxBuffer: 1 << 20 }, (error, stdout) => (error ? fail(error) : done(stdout)));
});

/** Each managed connection's pinned runtime, downloaded into app data on request; the package carries neither. */
const installer = (root: string, pin: RuntimePin | null) => new RuntimeInstaller({
  root, pin,
  fetch: (url, init) => net.fetch(url, init),
  tar: (args) => runTool(process.platform === "win32" ? join(process.env.SystemRoot ?? "C:\\Windows", "System32", "tar.exe") : "/usr/bin/tar", args),
  notify: () => current?.webContents.send("batatis:changed"),
  log: (line) => process.stderr.write(`${line}\n`),
});
const installers: Record<AccountId, RuntimeInstaller> = {
  chatgpt: installer(codexInstallRoot(paths), codexPin(process.platform, process.arch)),
  claude: installer(join(paths.userData, "claude"), claudePin(process.platform, process.arch)),
};
const makeProviders: Partial<Record<AccountId, () => HostProvider>> = {};
const providerWorkDirs: string[] = [];

/** The running runtime stops before the new one moves into place, and a fresh connection starts after. */
async function installRuntime(id: AccountId) {
  const make = makeProviders[id];
  if (!make) return;
  let stopped = false;
  await installers[id].install(async () => {
    stopped = true;
    await host.installProvider(unavailableProvider("The local AI runtime is being installed.", id));
  });
  if (stopped) await host.installProvider(make());
}

const host = new DesktopHost({
  paths,
  version: app.getVersion(),
  runtime: (id) => installers[id].status(),
  ...(smoke ? { start: async (...args: Parameters<typeof startEngine>) => {
    const started = await startEngine(...args);
    if (started.kind === "ready") smokeEngines.push(started.engine);
    return started;
  } } : {}),
  command: (kind) => {
    mkdirSync(workspaceDir(paths, kind), { recursive: true });
    mkdirSync(join(paths.userData, "engine-home"), { recursive: true });
    return engineCommand(paths, kind, process.env);
  },
  vault,
  localSession: new SealedTokenStore(join(workspaceDir(paths, "local"), "session.bin"), os),
  provider: fixture?.provider ?? unavailableProvider(),
  log,
  remount: (generation, route) => openWindow(generation, route),
  notify: () => current?.webContents.send("batatis:changed"),
});

const UPDATE_CHECK_MS = 4 * 60 * 60 * 1000;
/** Packaged builds read the repository's releases; a smoke run or a development run with a named feed reads a stand-in. */
const updateFeed = smoke ? smoke.updateFeed : packaged ? RELEASES_FEED : process.env.BATATIS_DESKTOP_UPDATE_FEED ?? null;
const updater = new Updater({
  current: app.getVersion(),
  platform: process.platform,
  arch: process.arch,
  feed: updateFeed,
  trusted: (url) => trustedUpdateUrl(url) || (updateFeed !== null && updateFeed !== RELEASES_FEED && url.href.startsWith(new URL(".", updateFeed).href)),
  fetch: (url, init) => net.fetch(url, init),
  dir: join(paths.userData, "updates"),
  executable: process.execPath,
  replaceable: packaged,
  run: runTool,
  notify: () => current?.webContents.send("batatis:update-changed"),
  log: (line) => process.stderr.write(`${line}\n`),
});

/** After the person confirms, a detached script swaps the app once this process has exited, then opens it. */
async function installUpdate(): Promise<Outcome> {
  const staged = updater.staged();
  const view = updater.view();
  if (!staged || !current || view.status !== "ready") return refused;
  if (staged.kind === "manual") {
    shell.showItemInFolder(staged.archive);
    return { ok: true };
  }
  const { response } = await dialog.showMessageBox(current, {
    type: "question", buttons: ["Restart", "Not now"], defaultId: 0, cancelId: 1,
    message: `Restart Batatis to update to ${view.release.version}?`,
    detail: "Your applications stay on this computer.",
  });
  if (response !== 0) return { ok: false, message: "" };
  const swap = await swapCommand(join(paths.userData, "updates"), process.platform, process.pid, staged, launchCommand(process.platform, staged.target));
  const script = spawn(swap.command, swap.args, { cwd: swap.cwd, detached: true, stdio: "ignore", windowsHide: true });
  const started = await new Promise<boolean>((done) => {
    script.once("spawn", () => done(true));
    script.once("error", () => done(false));
  });
  if (!started) return { ok: false, message: "Batatis couldn’t start the update. Try again, or download it from GitHub." };
  script.unref();
  app.quit();
  return { ok: true };
}

function harden(ses: Session) {
  const allowed = (permission: string) => permission === "clipboard-sanitized-write";
  ses.setPermissionRequestHandler((_contents, permission, grant) => grant(allowed(permission)));
  ses.setPermissionCheckHandler((_contents, permission) => allowed(permission));
  ses.on("will-download", (event, item) => {
    if (!item.getURL().startsWith(`blob:${ORIGIN}/`)) event.preventDefault();
  });
}

function httpsUrl(value: string): string | null {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password ? url.toString() : null;
  } catch {
    return null;
  }
}

/** Links leave the app only as https in the system browser; the app's own PDFs download through a save dialog. */
function leave(contents: WebContents, url: string) {
  if (url.startsWith(`blob:${ORIGIN}/`)) {
    contents.downloadURL(url);
    return;
  }
  const page = httpsUrl(url);
  if (page) void shell.openExternal(page);
}

app.on("web-contents-created", (_event, contents) => {
  contents.setWindowOpenHandler(({ url }) => {
    leave(contents, url);
    return { action: "deny" };
  });
  const stay = (event: Electron.Event, url: string) => {
    const own = url.startsWith(`${ORIGIN}/`) || url.startsWith(`${KEY_ORIGIN}/`);
    if (!own) {
      event.preventDefault();
      leave(contents, url);
    }
  };
  contents.on("will-navigate", stay);
  contents.on("will-redirect", stay);
  contents.on("will-attach-webview", (event) => event.preventDefault());
});

function openWindow(generation: number, route: string | null) {
  const previous = current;
  const partition = `batatis-app-${generation}`;
  const ses = session.fromPartition(partition);
  harden(ses);
  ses.protocol.handle("batatis", withProviderCancellation(createAppProtocol({ distDir: webDist(paths), gate: () => host.gate(generation) }), (kind) => {
    if (host.generation === generation) {
      if (kind === "identity") host.prepareSessionChange();
      else host.cancelAI();
    }
  }));
  const bounds = previous?.getBounds();
  const window = new BrowserWindow({
    ...(bounds ?? { width: 1360, height: 880 }),
    minWidth: 900,
    minHeight: 600,
    show: false,
    title: "Batatis",
    backgroundColor: "#ffffff",
    webPreferences: {
      partition,
      preload: join(__dirname, "..", "preload", "app.js"),
      sandbox: true,
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: true,
      spellcheck: false,
      devTools: !packaged,
    },
  });
  const hash = route ?? hashOf(previous) ?? "#/";
  void window.loadURL(`${ORIGIN}/${hash}`);
  window.once("ready-to-show", () => {
    window.show();
    if (previous && !previous.isDestroyed()) previous.destroy();
  });
  window.on("closed", () => {
    if (current === window) current = null;
  });
  current = window;
}

function hashOf(window: BrowserWindow | null): string | null {
  if (!window || window.isDestroyed()) return null;
  try {
    return new URL(window.webContents.getURL()).hash || null;
  } catch {
    return null;
  }
}

/** Only the current window's top frame, on the app origin, may call the host. */
function fromApp(event: IpcMainInvokeEvent): boolean {
  const window = current;
  return Boolean(window && !window.isDestroyed() && event.sender === window.webContents
    && event.senderFrame === window.webContents.mainFrame && event.senderFrame.url.startsWith(`${ORIGIN}/`));
}

const refused: Outcome = { ok: false, message: "Not allowed." };
const isKeyProvider = (value: unknown): value is KeyProviderId => value === "openai" || value === "jev" || value === "batatis";
const isAccount = (value: unknown): value is AccountId => value === "chatgpt" || value === "claude";

function answer<T>(channel: string, work: (event: IpcMainInvokeEvent, arg: unknown) => Promise<T> | T, fallback: T) {
  ipcMain.handle(channel, (event, arg: unknown) => (fromApp(event) ? work(event, arg) : fallback));
}

function registerIpc() {
  answer("batatis:info", () => host.info(), null);
  answer("batatis:restart", () => host.restart(), refused);
  answer("batatis:switch-workspace", (_e, kind) => (kind === "local" || kind === "dev" ? host.switchWorkspace(kind) : refused), refused);
  answer("batatis:switch-person", (_e, profile) => (typeof profile === "string" ? host.switchPerson(profile) : refused), refused);
  answer("batatis:providers", () => host.providerRows(), []);
  answer("batatis:ai-configuration", () => host.configuration(), null);
  answer("batatis:ai-model", (_e, value) => {
    const slot = record(value) ? value.slot : null, pick = record(value) ? parsePick(value.pick) : null;
    return isSlot(slot) && pick ? host.selectModel(slot, pick) : refused;
  }, refused);
  answer("batatis:ai-screening", (_e, value) => typeof value === "boolean" ? host.selectScreening(value) : refused, refused);
  answer("batatis:key-enter", async (_e, id) => {
    if (isKeyProvider(id)) await enterKey(id);
    return host.providerRows();
  }, []);
  answer("batatis:key-remove", async (_e, id) => {
    if (isKeyProvider(id)) await host.removeKey(id);
    return host.providerRows();
  }, []);
  answer("batatis:runtime-install", async (_e, id) => {
    if (isAccount(id)) await installRuntime(id);
    return host.providerRows();
  }, []);
  answer("batatis:connect", async (_e, id) => {
    if (isAccount(id)) await host.account(id).startLogin();
    return host.providerRows();
  }, []);
  answer("batatis:open-login", async (_e, id) => {
    const status = isAccount(id) ? await host.account(id).status() : null;
    const page = status?.state === "pending" ? httpsUrl(status.verificationUrl) : null;
    if (page) await shell.openExternal(page);
    return null;
  }, null);
  answer("batatis:login-code", async (_e, arg) => {
    const { id, code } = typeof arg === "object" && arg !== null ? arg as Record<string, unknown> : {};
    const status = isAccount(id) ? await host.account(id).status() : null;
    if (isAccount(id) && status?.state === "pending" && status.acceptsCode && typeof code === "string") {
      await host.account(id).submitLoginCode?.(status.loginId, code.trim());
    }
    return host.providerRows();
  }, []);
  answer("batatis:cancel-login", async (_e, id) => {
    const status = isAccount(id) ? await host.account(id).status() : null;
    if (isAccount(id) && status?.state === "pending") await host.account(id).cancelLogin(status.loginId);
    return host.providerRows();
  }, []);
  answer("batatis:disconnect", async (_e, id) => {
    if (isAccount(id)) await host.disconnectProvider(id);
    return host.providerRows();
  }, []);
  answer("batatis:update", () => updater.view(), null);
  answer("batatis:update-check", () => updater.check(), null);
  answer("batatis:update-download", () => updater.download(), null);
  answer("batatis:update-install", () => installUpdate(), refused);
  answer("batatis:update-beta", (_e, beta) => (typeof beta === "boolean" ? updater.setBeta(beta) : updater.view()), null);
  answer("batatis:choose-codedb", async () => {
    if (!current) return refused;
    const picked = await dialog.showOpenDialog(current, {
      title: "Choose a Batatis code database", properties: ["openFile"],
      filters: [{ name: "Code database", extensions: ["sqlite", "db"] }],
    });
    if (picked.canceled || picked.filePaths.length !== 1) return { ok: false, message: "" } satisfies Outcome;
    return host.addCodeDb(picked.filePaths[0]);
  }, refused);

  const fromDialog = (event: IpcMainInvokeEvent) => Boolean(keyDialog && event.sender === keyDialog.window.webContents
    && event.senderFrame === keyDialog.window.webContents.mainFrame && event.senderFrame.url.startsWith(`${KEY_ORIGIN}/`));
  ipcMain.handle("key:info", (event) => (fromDialog(event) && keyDialog ? { label: labelFor(keyDialog.id) } : null));
  ipcMain.handle("key:submit", async (event, value: unknown) => {
    if (!fromDialog(event) || !keyDialog || typeof value !== "string") return "invalid";
    const outcome = await host.saveKey(keyDialog.id, value);
    if (outcome !== "invalid") keyDialog.done(outcome);
    return outcome;
  });
  ipcMain.handle("key:cancel", (event) => {
    if (fromDialog(event) && keyDialog) keyDialog.done("cancelled");
  });
}

function labelFor(id: KeyProviderId): string {
  return id === "openai" ? "OpenAI API key" : id === "batatis" ? "Batatis access code" : "Jev API key";
}

/** A separate, sandboxed window with its own origin; the key never enters the app window. */
function enterKey(id: KeyProviderId): Promise<string> {
  if (keyDialog || !current) {
    keyDialog?.window.focus();
    return Promise.resolve("busy");
  }
  const ses = session.fromPartition("batatis-key");
  harden(ses);
  if (!ses.protocol.isProtocolHandled("batatis-key")) ses.protocol.handle("batatis-key", serveKeyDialog);
  const window = new BrowserWindow({
    parent: current, modal: true, width: 440, height: 248, resizable: false, minimizable: false, maximizable: false,
    fullscreenable: false, show: false, title: labelFor(id), backgroundColor: "#ffffff",
    webPreferences: {
      partition: "batatis-key", preload: join(__dirname, "..", "preload", "keyDialog.js"), sandbox: true,
      contextIsolation: true, nodeIntegration: false, spellcheck: false, devTools: false,
    },
  });
  window.setMenu(null);
  return new Promise((done) => {
    keyDialog = {
      id, window,
      done: (outcome) => {
        keyDialog = null;
        if (!window.isDestroyed()) window.destroy();
        done(outcome);
      },
    };
    window.on("closed", () => keyDialog?.window === window && keyDialog.done("cancelled"));
    window.once("ready-to-show", () => window.show());
    void window.loadURL(`${KEY_ORIGIN}/index.html`);
  });
}

async function serveKeyDialog(request: Request): Promise<Response> {
  const root = join(__dirname, "..", "static", "key-dialog");
  const name = new URL(request.url).pathname.replace(/^\//, "") || "index.html";
  const file = resolve(root, name);
  const types: Record<string, string> = { ".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript" };
  if (!file.startsWith(root + sep) || !types[extname(file)]) return new Response("Not found", { status: 404 });
  try {
    return new Response(new Uint8Array(await readFile(file)), { headers: { "Content-Type": types[extname(file)], "Content-Security-Policy": KEY_CSP } });
  } catch {
    return new Response("Not found", { status: 404 });
  }
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (!current) return;
    if (current.isMinimized()) current.restore();
    current.focus();
  });
  void app.whenReady().then(async () => {
    const root = join(paths.userData, "providers");
    await mkdir(join(root, "codex-state"), { recursive: true, mode: 0o700 });
    const providerWorkDir = await realpath(await mkdtemp(join(root, "codex-work-")));
    providerWorkDirs.push(providerWorkDir);
    const runtime = codexRuntime(paths);
    const providerContext = {
      stateDir: await realpath(join(root, "codex-state")), workDir: providerWorkDir,
      resourcesDir: paths.resources, appVersion: app.getVersion(), log,
    };
    const factory = codexProviderFactory({ runtime, verifiedContext: reviewedContextForPlatform(process.platform) });
    const installed = factory(providerContext);
    await Promise.all([installers.chatgpt.refresh(), installers.claude.refresh()]);
    if (fixture) { fixture.adapterConstructed = true; await installed.dispose(); }
    else {
      makeProviders.chatgpt = () => factory(providerContext);
      await host.installProvider(installed);
      // Claude gets its own state and working folders; the Codex adapter requires its working folder to stay empty.
      await mkdir(join(root, "claude-state"), { recursive: true, mode: 0o700 });
      const claudeWork = await realpath(await mkdtemp(join(root, "claude-work-")));
      providerWorkDirs.push(claudeWork);
      const claudeContext = { ...providerContext, stateDir: await realpath(join(root, "claude-state")), workDir: claudeWork };
      const claude = claudeProviderFactory({ runtimeRoot: join(paths.userData, "claude") });
      makeProviders.claude = () => claude(claudeContext);
      await host.installProvider(makeProviders.claude());
    }
    registerIpc();
    // The saved channel is read before the first window, which asks for the update state as it paints.
    await updater.load();
    await host.boot();
    host.openWindow(null);
    if (updateFeed && !smoke) {
      await updater.cleanup();
      setTimeout(() => void updater.check(), 15_000).unref();
      setInterval(() => void updater.check(), UPDATE_CHECK_MS).unref();
    }
    if (smoke) void runSmoke({ options: smoke, host, current: () => current, engines: smokeEngines, monitor: smokeMonitor, fixture: fixture ?? undefined, updater,
      runtime: () => runtime(providerContext, process.platform, process.arch) });
  });
  app.on("activate", () => {
    if (!current) host.openWindow(null);
  });
  app.on("window-all-closed", () => app.quit());
  let quitting = false;
  app.on("before-quit", (event) => {
    if (quitting) return;
    quitting = true;
    event.preventDefault();
    updater.cancel();
    installers.chatgpt.cancel();
    installers.claude.cancel();
    void host.dispose().finally(async () => {
      await Promise.all(providerWorkDirs.map((dir) => rm(dir, { recursive: true, force: true })));
      app.quit();
    });
  });
}
