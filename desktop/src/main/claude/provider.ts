/**
 * The managed Claude connection: the pinned Claude Code executable, run once per request with an
 * app-owned config dir, signed in with the person's Claude subscription, answering JSON-schema
 * completions with every tool, setting source and customization off.
 */
import { spawn as nodeSpawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { randomUUID } from "node:crypto";
import { chmod, mkdir, readFile, realpath, stat } from "node:fs/promises";
import { dirname, isAbsolute, join } from "node:path";
import { sha256File } from "../codex/binary";
import { ENVIRONMENT_POLICY } from "../codex/config";
import { outputValidator } from "../codex/protocol";
import {
  isModelId, isReasoningEffort, type CompleteJsonRequest, type CompleteJsonResult, type CompletionFailure, type ConnectionState,
  type HostModel, type HostProvider, type HostProviderContext, type HostProviderFactory, type LoginOutcome, type ModelId,
  type ReasoningEffort, type TokenUsage, type WorkflowReadiness,
} from "../providers";
import type { RuntimePin } from "../runtime-install";
import { claudePin } from "./release";

export type ClaudeSpawn = (command: string, args: readonly string[], options: {
  cwd: string; env: NodeJS.ProcessEnv; shell: false; windowsHide: true; stdio: ["pipe", "pipe", "pipe"];
}) => ChildProcessWithoutNullStreams;

export interface ClaudeTiming { completionMs: number; commandMs: number; loginMs: number; urlMs: number; stopMs: number }

export interface ClaudeProviderOptions {
  /** The installer's root: runtime/<platform>/claude[.exe] beside its codex-runtime.json. */
  runtimeRoot: string;
  /** The release to accept; defaults to claudePin for this computer. */
  pin?: RuntimePin | null;
  spawn?: ClaudeSpawn;
  environment?: NodeJS.ProcessEnv;
  platform?: NodeJS.Platform;
  arch?: string;
  timing?: Partial<ClaudeTiming>;
}

type Failure = CompletionFailure | "runtime-missing" | "unsupported-platform";
const MESSAGES: Record<Failure, string> = {
  unavailable: "The local AI runtime is unavailable.",
  "runtime-missing": "The verified local AI runtime isn’t installed.",
  "unsupported-platform": "This computer is not supported by the Claude runtime.",
  context_unverified: "Application work is unavailable until this local runtime is verified.",
  auth: "Sign in to Claude to continue.",
  quota: "Your Claude plan has reached a usage limit. Try again when the limit resets.",
  model_unavailable: "The requested model and reasoning setting are unavailable. No other model was selected.",
  cancelled: "The request was cancelled.",
  incomplete: "Claude didn’t return a complete answer in time. Try again.",
  refused_or_invalid: "Claude didn’t return an answer that matches the required format.",
  runtime: "The local AI runtime stopped or returned an invalid response. Try again.",
};
const STATUS_FAILED = "Couldn’t read the Claude sign-in status. Try again.";
const LOGIN_FAILED = "Claude sign-in didn’t finish. Try again.";
const LOGIN_TIMED_OUT = "Claude sign-in timed out. Try again.";
const LOGOUT_FAILED = "Couldn’t sign out of Claude. Try again.";

class ClaudeError extends Error {
  readonly reason: Failure;
  constructor(reason: Failure) { super(MESSAGES[reason]); this.reason = reason; }
}

const MAX_STDOUT = 4 * 1024 * 1024;
const MAX_STDERR = 64 * 1024;
const LOGIN_HOSTS = new Set(["claude.com", "claude.ai", "platform.claude.com", "console.anthropic.com"]);

function model(id: string, label: string, defaultEffort: string): HostModel {
  const efforts = ["low", "medium", "high"];
  if (!isModelId(id) || !efforts.every(isReasoningEffort) || !isReasoningEffort(defaultEffort)) throw new Error("Invalid Claude model");
  return Object.freeze({ id, label, efforts: Object.freeze(efforts as ReasoningEffort[]), defaultEffort, structuredOutput: true });
}

const MODELS: readonly HostModel[] = Object.freeze([
  model("claude-haiku-5-5", "Haiku 5.5", "low"),
  model("claude-sonnet-5-5", "Sonnet 5.5", "medium"),
  model("claude-opus-5-5", "Opus 5.5", "medium"),
]);

/** Everything Claude Code would otherwise load from the machine stays off; the answer is the schema's JSON. */
function completionArgs(request: { system: string; schema: Record<string, unknown>; model: ModelId; effort: ReasoningEffort }): string[] {
  return [
    "-p", "--output-format", "json", "--json-schema", JSON.stringify(request.schema), "--tools", "", "--safe-mode",
    "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence",
    "--permission-mode", "dontAsk", "--system-prompt", request.system, "--model", request.model, "--effort", request.effort,
  ];
}

/** The first sign-in page the CLI prints, once the line holding it is complete. */
function loginUrl(output: string): string | null {
  const plain = output.replace(/\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)/g, " ").replace(/\x1b\[[0-9;?]*[ -/]*[@-~]/g, "");
  for (const [candidate] of plain.matchAll(/https:\/\/[^\s"'<>]+(?=\s)/g)) {
    try {
      const url = new URL(candidate);
      if (url.protocol === "https:" && LOGIN_HOSTS.has(url.hostname) && !url.port && !url.username && !url.password) return url.href;
    } catch {}
  }
  return null;
}

function record(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function parseOutput(stdout: string): Record<string, unknown> | null {
  const text = stdout.trim();
  for (const candidate of [text, text.slice(text.lastIndexOf("\n") + 1)]) {
    try { return record(JSON.parse(candidate)); } catch {}
  }
  return null;
}

function usageOf(value: unknown): TokenUsage | null {
  const usage = record(value);
  const count = (n: unknown) => typeof n === "number" && Number.isSafeInteger(n) && n >= 0 ? n : null;
  const inputTokens = count(usage?.input_tokens), outputTokens = count(usage?.output_tokens);
  return inputTokens === null || outputTokens === null ? null : { inputTokens, outputTokens };
}

function classify(result: Record<string, unknown> | null, stderr: string): ClaudeError {
  const status = result?.api_error_status;
  const errors = Array.isArray(result?.errors) ? result.errors : [];
  const text = [result?.result, ...errors, stderr].filter((part) => typeof part === "string").join("\n");
  if (status === 401 || status === 403 || /not logged in|run \/login|claude auth login|oauth token (?:has )?(?:expired|been revoked)/i.test(text)) return new ClaudeError("auth");
  if (status === 429 || /usage limit|rate.?limit|hit your (?:\S+ )?limit|limit reached|out of (?:extra )?usage|quota/i.test(text)) return new ClaudeError("quota");
  if (status === 404 || /issue with the selected model|model.{0,60}(?:not found|not available|unavailable|not supported|does not exist)/i.test(text)) return new ClaudeError("model_unavailable");
  if (result?.subtype === "error_max_structured_output_retries") return new ClaudeError("refused_or_invalid");
  return new ClaudeError("runtime");
}

type End = "exit" | "aborted" | "timeout" | "overflow" | "failed";
interface Outcome { code: number | null; stdout: string; stderr: string; end: End }
interface Run { kill(end: End): void; done: Promise<Outcome> }
interface LaunchOptions { input?: string; keepStdinOpen?: boolean; timeoutMs?: number; signal?: AbortSignal; onOutput?: (text: string) => void }
type PendingLogin = Extract<ConnectionState, { state: "pending" }>;
interface LoginSlot { pending: PendingLogin; run: Run }

export function claudeProviderFactory(options: ClaudeProviderOptions): HostProviderFactory {
  return (context) => new ClaudeProvider(context, options);
}

class ClaudeProvider implements HostProvider {
  readonly id = "claude";
  private readonly context: HostProviderContext;
  private readonly options: ClaudeProviderOptions;
  private readonly environment: NodeJS.ProcessEnv;
  private readonly platform: NodeJS.Platform;
  private readonly pin: RuntimePin | null;
  private readonly timing: ClaudeTiming;
  private readonly listeners = new Set<() => void>();
  private readonly runs = new Set<Run>();
  private readonly active = new Set<AbortController>();
  private tail: Promise<unknown> = Promise.resolve();
  private login: LoginSlot | null = null;
  private loginStarting: Promise<ConnectionState> | null = null;
  private lastLogin: LoginOutcome | null = null;
  private disposed = false;

  constructor(context: HostProviderContext, options: ClaudeProviderOptions) {
    this.context = context;
    this.options = options;
    this.environment = { ...(options.environment ?? process.env) };
    this.platform = options.platform ?? process.platform;
    this.pin = options.pin === undefined ? claudePin(this.platform, options.arch ?? process.arch) : options.pin;
    this.timing = { completionMs: 170_000, commandMs: 30_000, loginMs: 15 * 60_000, urlMs: 10_000, stopMs: 2000, ...options.timing };
    for (const value of Object.values(this.timing)) if (!Number.isFinite(value) || value < 1 || value > 30 * 60_000) throw new Error("Invalid Claude deadline");
  }

  onChange(listener: () => void): () => void { this.listeners.add(listener); return () => this.listeners.delete(listener); }

  private emit(): void {
    if (this.disposed) return;
    for (const listener of this.listeners) {
      try { listener(); } catch { this.context.log("Claude connection listener failed."); }
    }
  }

  /** The pinned executable, re-hashed before every start: an install manifest alone never authorizes it. */
  private async executable(): Promise<string> {
    const pin = this.pin;
    if (!pin) throw new ClaudeError("unsupported-platform");
    try {
      const path = await realpath(join(this.options.runtimeRoot, "runtime", pin.key, pin.executable));
      if (!(await stat(path)).isFile()) throw new ClaudeError("runtime-missing");
      const sha256 = await sha256File(path);
      const manifest = record(JSON.parse(await readFile(join(dirname(path), "codex-runtime.json"), "utf8")));
      if (!pin.executables.includes(sha256) || manifest?.version !== pin.version || manifest.platform !== pin.key ||
        manifest.archiveSha256 !== pin.download.sha256 || manifest.executableSha256 !== sha256) throw new ClaudeError("runtime-missing");
      return path;
    } catch (error) {
      if (error instanceof ClaudeError) throw error;
      throw new ClaudeError("runtime-missing");
    }
  }

  private async childEnvironment(): Promise<NodeJS.ProcessEnv> {
    const configDir = join(this.context.stateDir, "claude-config");
    if (!isAbsolute(configDir)) throw new ClaudeError("runtime");
    await mkdir(configDir, { recursive: true, mode: 0o700 });
    if (this.platform !== "win32") await chmod(configDir, 0o700);
    // HOME stays the person's own on macOS: the CLI finds its keychain item through it.
    const env: NodeJS.ProcessEnv = { CLAUDE_CONFIG_DIR: configDir, DISABLE_UPDATES: "1", DISABLE_AUTOUPDATER: "1" };
    const keys = this.platform === "win32" ? ENVIRONMENT_POLICY.windowsKeys : [...ENVIRONMENT_POLICY.darwinKeys, "LANG"];
    for (const key of keys) {
      const value = Object.entries(this.environment).find(([name]) => this.platform === "win32" ? name.toLowerCase() === key.toLowerCase() : name === key)?.[1];
      if (value !== undefined) env[key] = value;
    }
    if (this.platform === "win32") {
      const root = env.SystemRoot;
      if (!root || !isAbsolute(root)) throw new ClaudeError("runtime-missing");
      env.PATH = ENVIRONMENT_POLICY.windowsPath.map((part) => join(root, ...part.split("/"))).join(";");
    } else env.PATH = ENVIRONMENT_POLICY.darwinPath;
    return env;
  }

  private async launch(args: readonly string[], options: LaunchOptions = {}): Promise<Run> {
    if (this.disposed) throw new ClaudeError("cancelled");
    const executable = await this.executable();
    const env = await this.childEnvironment();
    await mkdir(this.context.workDir, { recursive: true, mode: 0o700 });
    if (this.disposed || options.signal?.aborted) throw new ClaudeError("cancelled");
    const child = (this.options.spawn ?? nodeSpawn)(executable, args, { cwd: this.context.workDir, env, shell: false, windowsHide: true, stdio: ["pipe", "pipe", "pipe"] });
    let end: End | null = null, stdout = "", stderr = "", settled = false;
    let escalate: ReturnType<typeof setTimeout> | undefined, deadline: ReturnType<typeof setTimeout> | undefined;
    const kill = (why: End) => {
      if (settled || end) return;
      end = why;
      child.kill();
      escalate = setTimeout(() => { if (!settled) child.kill("SIGKILL"); }, this.timing.stopMs);
    };
    const onAbort = () => kill("aborted");
    const run: Run = {
      kill,
      done: new Promise<Outcome>((resolve) => {
        const finish = (code: number | null) => {
          if (settled) return;
          settled = true;
          clearTimeout(escalate);
          clearTimeout(deadline);
          options.signal?.removeEventListener("abort", onAbort);
          this.runs.delete(run);
          resolve({ code, stdout, stderr, end: end ?? "exit" });
        };
        child.once("error", () => { end ??= "failed"; if (child.pid === undefined) finish(null); });
        child.once("close", (code) => finish(code));
      }),
    };
    this.runs.add(run);
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk: string) => {
      if (stdout.length + chunk.length > MAX_STDOUT) return kill("overflow");
      stdout += chunk;
      options.onOutput?.(chunk);
    });
    child.stderr.on("data", (chunk: string) => {
      if (stderr.length < MAX_STDERR) stderr += chunk.slice(0, MAX_STDERR - stderr.length);
      options.onOutput?.(chunk);
    });
    child.stdin.on("error", () => {});
    if (options.input !== undefined) child.stdin.end(options.input);
    else if (!options.keepStdinOpen) child.stdin.end();
    if (options.timeoutMs !== undefined) deadline = setTimeout(() => kill("timeout"), options.timeoutMs);
    options.signal?.addEventListener("abort", onAbort, { once: true });
    return run;
  }

  /** True only for a Claude subscription sign-in; an API key or long-lived token never counts. */
  private async subscribed(signal?: AbortSignal): Promise<boolean> {
    const out = await (await this.launch(["auth", "status", "--json"], { timeoutMs: this.timing.commandMs, signal })).done;
    if (out.end === "aborted") throw new ClaudeError("cancelled");
    const parsed = parseOutput(out.stdout);
    if (out.end !== "exit" || (out.code !== 0 && out.code !== 1) || typeof parsed?.loggedIn !== "boolean" || parsed.loggedIn !== (out.code === 0)) {
      this.context.log(`Claude sign-in status check failed (${out.end}, exit ${out.code}).`);
      throw new ClaudeError("runtime");
    }
    return parsed.loggedIn && parsed.authMethod === "claude.ai";
  }

  private stateError(error: unknown, message = STATUS_FAILED): ConnectionState {
    if (error instanceof ClaudeError && (error.reason === "runtime-missing" || error.reason === "unsupported-platform"))
      return { state: "unavailable", reason: error.reason, message: error.message };
    return { state: "error", message };
  }

  async status(): Promise<ConnectionState> {
    if (this.login) return { ...this.login.pending };
    try {
      return await this.subscribed() ? { state: "signed-in", plan: null } : { state: "signed-out", last: this.lastLogin };
    } catch (error) { return this.stateError(error); }
  }

  async workflowReadiness(): Promise<WorkflowReadiness> {
    const state = await this.status();
    if (state.state === "signed-in") return { ready: true };
    if (state.state === "signed-out" || state.state === "pending") return { ready: false, reason: "signed-out", message: MESSAGES.auth };
    return { ready: false, reason: "unavailable", message: state.message };
  }

  async startLogin(): Promise<ConnectionState> {
    if (this.login) return { ...this.login.pending };
    this.loginStarting ??= this.beginLogin().catch((error) => this.stateError(error, LOGIN_FAILED)).finally(() => { this.loginStarting = null; });
    return this.loginStarting;
  }

  /**
   * The CLI opens the browser itself and waits on its own localhost callback. Pending carries the page
   * it prints for a manual open; when none appears within urlMs, pending has no page until one does.
   */
  private async beginLogin(): Promise<ConnectionState> {
    if (await this.subscribed()) return { state: "signed-in", plan: null };
    this.lastLogin = null;
    const pending: PendingLogin = { state: "pending", loginId: randomUUID(), verificationUrl: "", userCode: "" };
    let output = "", seen!: (url: string) => void;
    const found = new Promise<string>((done) => { seen = done; });
    // stdin stays open: the CLI abandons sign-in when its paste-a-code input closes.
    const run = await this.launch(["auth", "login", "--claudeai"], {
      keepStdinOpen: true, timeoutMs: this.timing.loginMs,
      onOutput: (text) => {
        if (pending.verificationUrl) return;
        output = (output + text).slice(-16_384);
        const url = loginUrl(output);
        if (!url) return;
        pending.verificationUrl = url;
        seen(url);
        if (this.login?.pending === pending && !this.loginStarting) this.emit();
      },
    });
    const slot: LoginSlot = { pending, run };
    this.login = slot;
    void run.done.then((out) => this.loginEnded(slot, out));
    let wait: ReturnType<typeof setTimeout> | undefined;
    await Promise.race([found, run.done, new Promise((done) => { wait = setTimeout(done, this.timing.urlMs); })]);
    clearTimeout(wait);
    return this.login === slot ? { ...pending } : this.status();
  }

  private async loginEnded(slot: LoginSlot, out: Outcome): Promise<void> {
    if (this.login !== slot) return;
    this.login = null;
    const loginId = slot.pending.loginId;
    if (out.end === "exit" && out.code === 0) {
      const ok = await this.subscribed().catch(() => false);
      this.lastLogin = ok ? null : { loginId, result: "failed", message: LOGIN_FAILED };
    } else {
      this.context.log(`Claude sign-in ended (${out.end}, exit ${out.code}).`);
      this.lastLogin = { loginId, result: "failed", message: out.end === "timeout" ? LOGIN_TIMED_OUT : LOGIN_FAILED };
    }
    this.emit();
  }

  async cancelLogin(loginId: string): Promise<ConnectionState> {
    const slot = this.login;
    if (slot?.pending.loginId === loginId) {
      this.login = null;
      this.lastLogin = { loginId, result: "cancelled" };
      slot.run.kill("aborted");
      await slot.run.done;
      this.emit();
    }
    return this.status();
  }

  async logout(): Promise<ConnectionState> {
    for (const controller of this.active) controller.abort();
    const slot = this.login;
    this.login = null;
    if (slot) { slot.run.kill("aborted"); await slot.run.done; }
    try {
      const out = await (await this.launch(["auth", "logout"], { timeoutMs: this.timing.commandMs })).done;
      if (out.end !== "exit" || out.code !== 0) this.context.log(`Claude sign-out ended (${out.end}, exit ${out.code}).`);
      if (await this.subscribed()) return { state: "error", message: LOGOUT_FAILED };
      this.lastLogin = null;
      return { state: "signed-out", last: null };
    } catch (error) { return this.stateError(error, LOGOUT_FAILED); }
    finally { this.emit(); }
  }

  async models(): Promise<readonly HostModel[]> { return MODELS; }

  async completeJson(request: CompleteJsonRequest, signal: AbortSignal): Promise<CompleteJsonResult> {
    const abort = new AbortController();
    const forward = () => abort.abort();
    const deadline = setTimeout(() => abort.abort(new ClaudeError("incomplete")), this.timing.completionMs);
    signal.addEventListener("abort", forward, { once: true });
    if (signal.aborted) forward();
    this.active.add(abort);
    try {
      const entry = MODELS.find((item) => item.id === request.model);
      if (!entry || !entry.efforts.includes(request.effort)) throw new ClaudeError("model_unavailable");
      if (typeof request.system !== "string" || typeof request.user !== "string" || !record(request.schema)) throw new ClaudeError("runtime");
      let valid: (value: unknown) => boolean;
      try { valid = outputValidator(request.schema); } catch { throw new ClaudeError("runtime"); }
      const args = completionArgs(request);
      return await this.serialize(abort.signal, async () => {
        if (!(await this.subscribed(abort.signal))) throw new ClaudeError("auth");
        const out = await (await this.launch(args, { input: request.user, signal: abort.signal })).done;
        if (out.end === "aborted") throw this.abortReason(abort.signal);
        if (out.end !== "exit") {
          this.context.log(`Claude completion stopped (${out.end}).`);
          throw new ClaudeError("runtime");
        }
        const result = parseOutput(out.stdout);
        if (out.code !== 0 || result?.is_error !== false || result.subtype !== "success") {
          const error = classify(result, out.stderr);
          this.context.log(`Claude completion failed (${error.reason}, exit ${out.code}).`);
          throw error;
        }
        const json = record(result.structured_output);
        if (!json || !valid(json)) throw new ClaudeError("refused_or_invalid");
        return { ok: true, json, model: request.model, effort: request.effort, usage: usageOf(result.usage) } as const;
      });
    } catch (error) {
      const failure = abort.signal.aborted ? this.abortReason(abort.signal) : error instanceof ClaudeError ? error : new ClaudeError("runtime");
      const reason = failure.reason === "runtime-missing" || failure.reason === "unsupported-platform" ? "unavailable" : failure.reason;
      return { ok: false, reason, message: failure.message };
    } finally {
      clearTimeout(deadline);
      signal.removeEventListener("abort", forward);
      this.active.delete(abort);
    }
  }

  private abortReason(signal: AbortSignal): ClaudeError {
    return signal.reason instanceof ClaudeError ? signal.reason : new ClaudeError("cancelled");
  }

  /** One completion at a time; a waiting one leaves the line as soon as it is cancelled. */
  private serialize<T>(signal: AbortSignal, task: () => Promise<T>): Promise<T> {
    const previous = this.tail;
    const result = (async () => {
      await new Promise<void>((done, fail) => {
        const onAbort = () => fail(this.abortReason(signal));
        if (signal.aborted) return onAbort();
        signal.addEventListener("abort", onAbort, { once: true });
        void previous.then(() => { signal.removeEventListener("abort", onAbort); done(); });
      });
      if (this.disposed) throw new ClaudeError("cancelled");
      return task();
    })();
    this.tail = Promise.allSettled([previous, result]);
    return result;
  }

  async dispose(): Promise<void> {
    this.disposed = true;
    for (const controller of this.active) controller.abort();
    this.login = null;
    for (const run of this.runs) run.kill("aborted");
    await Promise.all([...this.runs].map((run) => run.done));
    await this.loginStarting?.catch(() => undefined);
    await this.tail;
    this.listeners.clear();
  }
}
