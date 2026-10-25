import { lstat } from "node:fs/promises";
import { join } from "node:path";
import {
  isModelId, isReasoningEffort, type CompleteJsonRequest, type CompleteJsonResult, type ConnectionState,
  type HostModel, type HostProvider, type HostProviderContext, type HostProviderFactory, type LoginOutcome,
} from "./providers";
import { assertEmptyWorkDir, bundledRuntime, childEnvironment, prepareHome, type RuntimeSource } from "./codex/binary";
import { CODEX_CONTEXT_FINGERPRINT, EFFORT, MODEL, RUNTIME_ARGS, initializeParams, threadParams, turnParams } from "./codex/config";
import {
  AdapterError, assertRequirements, id, isExpectedRuntimeNotice, object, outputValidator, parseAccount, parseAccountUpdate,
  parseItem, parseLogin, parseLoginComplete, parseModels, parseThread, parseTurn,
} from "./codex/protocol";
import { JsonLineRpc, MAX_FRAME_BYTES, type Notification, type SpawnFn } from "./codex/rpc";
import { CompletionTurn } from "./codex/turn";

export { bundledRuntime, CODEX_CONTEXT_FINGERPRINT };
export type { RuntimeSource, SpawnFn };

/** Reviewed local request-boundary evidence, never a claim about hidden provider policy or every internal handler. */
export interface VerifiedContext { evidence: string; runtimeSha256: string; contextFingerprint: string }
export interface CodexTiming { requestMs: number; completionMs: number; interruptMs: number; stopMs: number; loginMs: number }
export interface CodexProviderOptions {
  runtime?: RuntimeSource;
  verifiedContext?: VerifiedContext;
  spawn?: SpawnFn;
  environment?: NodeJS.ProcessEnv;
  platform?: NodeJS.Platform;
  arch?: string;
  timing?: Partial<CodexTiming>;
}

interface Runtime { rpc: JsonLineRpc; home: string; cwd: string; sha256: string; tainted: boolean }
type PendingLogin = Extract<ConnectionState, { state: "pending" }>;
interface LoginSlot { pending: PendingLogin; timer: ReturnType<typeof setTimeout> }

function failure(value: unknown): AdapterError { return value instanceof AdapterError ? value : new AdapterError("runtime"); }
function completionFailure(value: unknown): CompleteJsonResult {
  const error = failure(value);
  const reason = error.reason === "runtime-missing" || error.reason === "unsupported-platform" || error.reason === "keyring-unavailable" ? "unavailable"
    : error.reason === "device-prerequisite" ? "auth" : error.reason;
  return { ok: false, reason, message: error.message };
}

export function codexProviderFactory(options: CodexProviderOptions = {}): HostProviderFactory {
  return (context) => new CodexProvider(context, options);
}

class CodexProvider implements HostProvider {
  readonly id = "chatgpt";
  private readonly context: HostProviderContext;
  private readonly options: CodexProviderOptions;
  private readonly timing: CodexTiming;
  private runtime: Runtime | null = null;
  private starting: Promise<Runtime> | null = null;
  private login: LoginSlot | null = null;
  private loginStarting = false;
  private earlyLogins: ReturnType<typeof parseLoginComplete>[] = [];
  private lastLogin: LoginOutcome | null = null;
  private listeners = new Set<() => void>();
  private serial: Promise<void> | null = null;
  private queued = new Set<() => Promise<void>>();
  private disposed = false;
  private active: AbortController | null = null;
  private logoutEpoch = 0;
  private signedOutEpoch = 0;
  private cancellationEpoch = 0;

  constructor(context: HostProviderContext, options: CodexProviderOptions) {
    this.context = context;
    this.options = { ...options, environment: { ...(options.environment ?? process.env) }, verifiedContext: options.verifiedContext && { ...options.verifiedContext } };
    this.timing = { requestMs: 15_000, completionMs: 170_000, interruptMs: 5_000, stopMs: 1000, loginMs: 15 * 60_000, ...options.timing };
    for (const value of Object.values(this.timing)) if (!Number.isFinite(value) || value < 1 || value > 30 * 60_000) throw new Error("Invalid Codex deadline");
  }

  private emit(): void {
    for (const listener of this.listeners) {
      try { listener(); } catch { this.context.log("Local AI connection listener failed."); }
    }
  }

  onChange(listener: () => void): () => void { this.listeners.add(listener); return () => this.listeners.delete(listener); }

  private enqueue<T>(operation: () => Promise<T>, signal?: AbortSignal): Promise<T> {
    const abortError = () => signal?.reason instanceof AdapterError ? signal.reason : new AdapterError("cancelled");
    if (this.disposed) return Promise.reject(new AdapterError("cancelled"));
    if (signal?.aborted) return Promise.reject(abortError());
    if (this.queued.size >= 8) return Promise.reject(new AdapterError("runtime"));
    const promise = new Promise<T>((resolve, reject) => {
      let state: "waiting" | "running" | "settled" = "waiting";
      const abort = () => {
        if (state !== "waiting") return;
        state = "settled";
        this.queued.delete(run);
        signal?.removeEventListener("abort", abort);
        reject(abortError());
      };
      const run = async () => {
        state = "running";
        signal?.removeEventListener("abort", abort);
        try {
          if (this.disposed) throw new AdapterError("cancelled");
          resolve(await operation());
        } catch (error) { reject(error); }
        finally { state = "settled"; this.queued.delete(run); }
      };
      this.queued.add(run);
      signal?.addEventListener("abort", abort, { once: true });
    });
    if (!this.serial) this.serial = Promise.resolve().then(async () => {
      try { for (const run of this.queued) await run(); }
      finally { this.serial = null; }
    });
    return promise;
  }

  private gateDeclared(): boolean {
    const proof = this.options.verifiedContext;
    return !!proof && proof.evidence.trim().length > 0 && /^[a-f0-9]{64}$/.test(proof.runtimeSha256) && proof.contextFingerprint === CODEX_CONTEXT_FINGERPRINT;
  }

  private async getRuntime(): Promise<Runtime> {
    if (this.disposed) throw new AdapterError("cancelled");
    if (this.runtime && !this.runtime.rpc.failure) return this.runtime;
    if (this.starting) return this.starting;
    this.starting = this.startRuntime();
    try { return await this.starting; } finally { this.starting = null; }
  }

  private async startRuntime(): Promise<Runtime> {
    if (this.runtime) await this.runtime.rpc.close();
    this.runtime = null;
    const environment = this.options.environment ?? {};
    const platform = this.options.platform ?? process.platform;
    const source = await (this.options.runtime ?? bundledRuntime())(this.context, platform, this.options.arch ?? process.arch);
    const { home, cwd } = await prepareHome(this.context, environment, source.catalog);
    if (this.disposed) throw new AdapterError("cancelled");
    const rpc = new JsonLineRpc({ executable: source.executable, args: RUNTIME_ARGS, cwd, env: childEnvironment(home, platform, environment) }, this.options.spawn, this.timing.stopMs);
    const runtime: Runtime = { rpc, home, cwd, sha256: source.sha256, tainted: false };
    this.runtime = runtime;
    rpc.onNotification((event) => this.notification(runtime, event));
    rpc.onFailure(() => {
      if (this.runtime !== runtime) return;
      if (this.login) {
        const loginId = this.login.pending.loginId;
        this.clearLogin();
        this.lastLogin = { loginId, result: "failed", message: new AdapterError("runtime").message };
      }
      this.emit();
    });
    try {
      const initialized = object(await rpc.request("initialize", initializeParams(this.context.appVersion), this.timing.requestMs));
      if (initialized.codexHome !== home || typeof initialized.userAgent !== "string" || typeof initialized.platformFamily !== "string" || typeof initialized.platformOs !== "string") throw new AdapterError("context_unverified");
      rpc.notify("initialized");
      return runtime;
    } catch (error) { rpc.fail(failure(error)); await rpc.close(); throw error; }
  }

  private poison(runtime: Runtime, error = new AdapterError("context_unverified")): void {
    runtime.tainted = true;
    runtime.rpc.fail(error);
  }

  private notification(runtime: Runtime, event: Notification): void {
    if (this.runtime !== runtime) return;
    try {
      if (isExpectedRuntimeNotice(event.method, event.params, runtime.home)) return;
      switch (event.method) {
        case "account/login/completed": {
          const result = parseLoginComplete(event.params);
          if (this.loginStarting) {
            if (this.earlyLogins.length >= 8) throw new AdapterError("runtime");
            this.earlyLogins.push(result);
          } else this.finishLogin(result);
          return;
        }
        case "account/updated": {
          const update = parseAccountUpdate(event.params);
          if (update.signedOut) this.signedOutEpoch = this.logoutEpoch;
          this.emit();
          return;
        }
        case "thread/started":
        case "account/rateLimits/updated": return;
        case "thread/status/changed": {
          const status = object(object(event.params).status);
          if (status.type === "active" && (!Array.isArray(status.activeFlags) || status.activeFlags.length)) this.poison(runtime);
          return;
        }
        case "item/started":
        case "item/completed":
          parseItem(object(event.params).item);
          return;
        case "turn/started":
        case "turn/completed":
          parseTurn(object(event.params).turn);
          return;
        case "model/rerouted":
          this.poison(runtime, new AdapterError("model_unavailable"));
          return;
        case "thread/tokenUsage/updated":
        case "item/agentMessage/delta":
        case "item/reasoning/summaryTextDelta":
        case "item/reasoning/summaryPartAdded":
        case "item/reasoning/textDelta":
        case "error":
        case "thread/compacted":
        case "model/verification":
        case "turn/moderationMetadata":
        case "model/safetyBuffering/updated":
        case "thread/closed": return;
        default: this.poison(runtime);
      }
    } catch (error) { this.poison(runtime, failure(error)); }
  }

  private clearLogin(): void { if (this.login) clearTimeout(this.login.timer); this.login = null; }

  private finishLogin(result: ReturnType<typeof parseLoginComplete>): void {
    if (!this.login || result.loginId !== this.login.pending.loginId) return;
    const loginId = this.login.pending.loginId;
    this.clearLogin();
    this.lastLogin = result.success ? null : result.prerequisite
      ? { loginId, result: "prerequisite", message: new AdapterError("device-prerequisite").message }
      : { loginId, result: "failed", message: new AdapterError("auth").message };
    this.emit();
  }

  private stateError(value: unknown): ConnectionState {
    const error = failure(value);
    if (error.reason === "runtime-missing" || error.reason === "unsupported-platform" || error.reason === "keyring-unavailable")
      return { state: "unavailable", reason: error.reason, message: error.message };
    return { state: "error", message: error.message };
  }

  private async readAccount(runtime: Runtime, signal?: AbortSignal): Promise<ConnectionState> {
    // Plaintext credentials are never imported into the managed keyring connection.
    try { await lstat(join(runtime.home, "auth.json")); throw new AdapterError("keyring-unavailable"); }
    catch (error) {
      if (!(error instanceof Error && "code" in error && error.code === "ENOENT")) throw error;
    }
    const account = parseAccount(await runtime.rpc.request("account/read", { refreshToken: false }, this.timing.requestMs, signal));
    return account.state === "signed-in" ? account : { state: "signed-out", last: this.lastLogin };
  }

  async status(): Promise<ConnectionState> {
    try {
      return await this.enqueue(async () => this.login ? { ...this.login.pending } : this.readAccount(await this.getRuntime()));
    } catch (error) { return this.stateError(error); }
  }

  async workflowReadiness() {
    if (!this.gateDeclared()) return { ready: false, reason: "context_unverified", message: new AdapterError("context_unverified").message } as const;
    try {
      return await this.enqueue(async () => {
        const runtime = await this.getRuntime();
        if (runtime.tainted || runtime.sha256 !== this.options.verifiedContext?.runtimeSha256) return { ready: false, reason: "context_unverified", message: new AdapterError("context_unverified").message } as const;
        const state = this.login ? this.login.pending : await this.readAccount(runtime);
        return state.state === "signed-in" ? { ready: true } as const
          : { ready: false, reason: state.state === "signed-out" || state.state === "pending" ? "signed-out" : "unavailable", message: new AdapterError("auth").message } as const;
      });
    } catch (error) { return { ready: false, reason: "unavailable", message: failure(error).message } as const; }
  }

  async startLogin(): Promise<ConnectionState> {
    try {
      return await this.enqueue(async () => {
        if (this.login) return { ...this.login.pending };
        const runtime = await this.getRuntime();
        const before = await this.readAccount(runtime);
        if (before.state === "signed-in") return before;
        this.lastLogin = null;
        this.loginStarting = true;
        this.earlyLogins = [];
        let raw: unknown;
        try {
          raw = await runtime.rpc.request("account/login/start", { type: "chatgptDeviceCode" }, this.timing.requestMs);
          const pending = parseLogin(raw);
          const timer = setTimeout(() => {
            void this.cancelLogin(pending.loginId);
          }, this.timing.loginMs);
          this.login = { pending, timer };
          for (const result of this.earlyLogins) this.finishLogin(result);
          return this.login ? { ...this.login.pending } : this.readAccount(runtime);
        } catch (error) {
          if (raw !== undefined) {
            try {
              const loginId = id(object(raw).loginId);
              await runtime.rpc.request("account/login/cancel", { loginId }, this.timing.requestMs);
            } catch { this.poison(runtime, new AdapterError("auth")); }
            this.poison(runtime, new AdapterError("auth"));
          }
          const parsed = failure(error);
          if (parsed.reason === "device-prerequisite") {
            this.lastLogin = { loginId: null, result: "prerequisite", message: parsed.message };
            return { state: "signed-out", last: this.lastLogin };
          }
          throw parsed;
        } finally { this.loginStarting = false; this.earlyLogins = []; }
      });
    } catch (error) { return this.stateError(error); }
  }

  async cancelLogin(loginId: string): Promise<ConnectionState> {
    try {
      return await this.enqueue(async () => {
        const runtime = await this.getRuntime();
        if (this.login?.pending.loginId === loginId) {
          const result = object(await runtime.rpc.request("account/login/cancel", { loginId }, this.timing.requestMs));
          if (result.status !== "canceled" && result.status !== "notFound") throw new AdapterError("runtime");
          this.clearLogin();
          this.lastLogin = { loginId, result: "cancelled" };
          this.emit();
        }
        return this.login ? { ...this.login.pending } : this.readAccount(runtime);
      });
    } catch (error) { return this.stateError(error); }
  }

  async logout(): Promise<ConnectionState> {
    this.cancellationEpoch++;
    this.active?.abort();
    try {
      return await this.enqueue(async () => {
        const runtime = await this.getRuntime();
        if (this.login) {
          const loginId = this.login.pending.loginId;
          const cancel = object(await runtime.rpc.request("account/login/cancel", { loginId }, this.timing.requestMs));
          if (cancel.status !== "canceled" && cancel.status !== "notFound") throw new AdapterError("runtime");
          this.clearLogin();
        }
        const epoch = ++this.logoutEpoch;
        let confirm!: () => void;
        const updated = new Promise<void>((done) => { confirm = done; });
        const unlisten = runtime.rpc.onNotification((event) => {
          if (event.method === "account/updated" && parseAccountUpdate(event.params).signedOut) confirm();
        });
        let timer: ReturnType<typeof setTimeout> | undefined;
        try {
          const result = object(await runtime.rpc.request("account/logout", {}, this.timing.requestMs));
          if (Object.keys(result).length) throw new AdapterError("runtime");
          if (this.signedOutEpoch !== epoch) await Promise.race([updated, new Promise<never>((_, reject) => {
            timer = setTimeout(() => reject(new AdapterError("runtime")), this.timing.requestMs);
          })]);
          const state = await this.readAccount(runtime);
          if (state.state !== "signed-out") throw new AdapterError("auth");
          this.lastLogin = null;
          this.emit();
          return { state: "signed-out", last: null };
        } finally {
          clearTimeout(timer);
          unlisten();
          await runtime.rpc.close();
          if (this.runtime === runtime) this.runtime = null;
        }
      });
    } catch (error) { return this.stateError(error); }
  }

  private async listModels(runtime: Runtime, signal?: AbortSignal): Promise<readonly HostModel[]> {
    const cursors = new Set<string>();
    const found: HostModel[] = [];
    let cursor: string | null = null;
    let count = 0;
    for (let page = 0; page < 32; page++) {
      const result = parseModels(await runtime.rpc.request("model/list", { includeHidden: true, limit: 100, ...(cursor ? { cursor } : {}) }, this.timing.requestMs, signal));
      count += result.count;
      if (count > 512 || found.length + result.models.length > 1) throw new AdapterError("runtime");
      found.push(...result.models);
      if (result.cursor === null) return found;
      if (cursors.has(result.cursor)) throw new AdapterError("runtime");
      cursors.add(result.cursor);
      cursor = result.cursor;
    }
    throw new AdapterError("runtime");
  }

  async models(): Promise<readonly HostModel[]> {
    try { return await this.enqueue(async () => this.listModels(await this.getRuntime())); }
    catch { return []; }
  }

  async completeJson(request: CompleteJsonRequest, signal: AbortSignal): Promise<CompleteJsonResult> {
    if (!this.gateDeclared()) return completionFailure(new AdapterError("context_unverified"));
    try {
      const snapshot: CompleteJsonRequest = structuredClone(request);
      if (!isModelId(snapshot.model) || !isReasoningEffort(snapshot.effort) || snapshot.model !== MODEL || snapshot.effort !== EFFORT) throw new AdapterError("model_unavailable");
      if (typeof snapshot.task !== "string" || snapshot.task.length > 128 || typeof snapshot.system !== "string" || typeof snapshot.user !== "string" ||
        (snapshot.maxOutputTokens !== null && (!Number.isSafeInteger(snapshot.maxOutputTokens) || snapshot.maxOutputTokens <= 0))) throw new AdapterError("runtime");
      object(snapshot.schema);
      outputValidator(snapshot.schema);
      if (Buffer.byteLength(JSON.stringify(snapshot), "utf8") > MAX_FRAME_BYTES - 4096) throw new AdapterError("runtime");
      const epoch = this.cancellationEpoch;
      const abort = new AbortController();
      const forward = () => abort.abort();
      signal.addEventListener("abort", forward, { once: true });
      if (signal.aborted) forward();
      const deadline = setTimeout(() => abort.abort(new AdapterError("incomplete")), this.timing.completionMs);
      try {
        return await this.enqueue(async () => {
          if (epoch !== this.cancellationEpoch) throw new AdapterError("cancelled");
          if (abort.signal.aborted) throw abort.signal.reason instanceof AdapterError ? abort.signal.reason : new AdapterError("cancelled");
          this.active = abort;
          try { return await this.runCompletion(snapshot, abort.signal); }
          catch (error) {
            if (abort.signal.aborted) throw abort.signal.reason instanceof AdapterError ? abort.signal.reason : new AdapterError("cancelled");
            throw error;
          } finally { this.active = null; }
        }, abort.signal);
      } finally {
        clearTimeout(deadline);
        signal.removeEventListener("abort", forward);
      }
    } catch (error) { return completionFailure(error); }
  }

  private async runCompletion(request: CompleteJsonRequest, signal: AbortSignal): Promise<CompleteJsonResult> {
    const runtime = await this.getRuntime();
    if (runtime.tainted || runtime.sha256 !== this.options.verifiedContext?.runtimeSha256) throw new AdapterError("context_unverified");
    await assertEmptyWorkDir(runtime.cwd);
    const abortError = () => signal.reason instanceof AdapterError ? signal.reason : new AdapterError("cancelled");
    const checkAbort = () => { if (signal.aborted) throw abortError(); };
    checkAbort();
    if ((await this.readAccount(runtime, signal)).state !== "signed-in") throw new AdapterError("auth");
    checkAbort();
    if (!(await this.listModels(runtime, signal)).some((model) => model.id === request.model && model.efforts.includes(request.effort))) throw new AdapterError("model_unavailable");
    checkAbort();
    try { assertRequirements(await runtime.rpc.request("configRequirements/read", {}, this.timing.requestMs, signal)); }
    catch (error) {
      if (failure(error).reason === "context_unverified") this.poison(runtime);
      throw error;
    }
    checkAbort();
    let threadId: string;
    try { threadId = parseThread(await runtime.rpc.request("thread/start", threadParams(runtime.cwd, request.system), this.timing.requestMs, signal), runtime.cwd); }
    catch (error) {
      if (failure(error).reason === "context_unverified") this.poison(runtime);
      throw error;
    }
    const tracker = new CompletionTurn(threadId, request, (error) => this.poison(runtime, error));
    const unlisten = runtime.rpc.onNotification((event) => {
      if (!isExpectedRuntimeNotice(event.method, event.params, runtime.home)) tracker.accept(event);
    });
    const unfail = runtime.rpc.onFailure((error) => tracker.fail(error));
    let cancelling: Promise<void> | null = null;
    const interrupt = (): Promise<void> => {
      if (cancelling) return cancelling;
      tracker.fail(abortError());
      cancelling = (async () => {
        const turnId = tracker.currentTurnId;
        if (turnId === null || runtime.rpc.failure) { await runtime.rpc.close(); return; }
        let remove = () => {};
        let timer: ReturnType<typeof setTimeout> | undefined;
        let acknowledged = false;
        try {
          const stopped = new Promise<void>((done) => {
            remove = runtime.rpc.onNotification((event) => {
              if (event.method !== "turn/completed") return;
              const params = object(event.params);
              if (params.threadId === threadId && object(params.turn).id === turnId) { acknowledged = true; done(); }
            });
            timer = setTimeout(done, this.timing.interruptMs);
          });
          await runtime.rpc.request("turn/interrupt", { threadId, turnId }, this.timing.interruptMs);
          await stopped;
          if (!acknowledged) await runtime.rpc.close();
        } catch { await runtime.rpc.close(); }
        finally { clearTimeout(timer); remove(); }
      })();
      return cancelling;
    };
    const onAbort = () => { void interrupt(); };
    signal.addEventListener("abort", onAbort, { once: true });
    try {
      checkAbort();
      const response = await runtime.rpc.request("turn/start", turnParams(threadId, request), this.timing.requestMs);
      tracker.startResponse(response);
      if (signal.aborted) await interrupt();
      const result = await tracker.result;
      if (cancelling) await cancelling;
      if (!result.ok && !runtime.rpc.failure) await runtime.rpc.close();
      return result;
    } catch (error) { tracker.fail(signal.aborted ? abortError() : error); return await tracker.result; }
    finally {
      signal.removeEventListener("abort", onAbort);
      if (cancelling) await cancelling;
      unlisten();
      unfail();
      // Ephemeral threads are never resumed, even if unsubscribing fails.
      if (!runtime.rpc.failure) {
        try { await runtime.rpc.request("thread/unsubscribe", { threadId }, Math.min(this.timing.requestMs, this.timing.interruptMs)); }
        catch { await runtime.rpc.close(); }
      }
      if (runtime.rpc.failure && runtime.rpc.failure.reason !== "cancelled" && !signal.aborted) throw runtime.rpc.failure;
    }
  }

  async dispose(): Promise<void> {
    this.disposed = true;
    this.active?.abort();
    this.clearLogin();
    if (this.runtime) await this.runtime.rpc.close();
    if (this.starting) { try { await (await this.starting).rpc.close(); } catch {} }
    await this.serial;
    this.listeners.clear();
    this.runtime = null;
  }
}
