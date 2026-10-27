/**
 * The managed OpenCode connection: the pinned OpenCode executable, run once per request with app-owned
 * state, every tool and permission denied, answering JSON-schema completions with OpenCode's free models.
 * It needs no sign-in, so a verified install is a ready connection.
 */
import { spawn as nodeSpawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { mkdir, readFile, realpath, stat } from "node:fs/promises";
import { dirname, isAbsolute, join } from "node:path";
import { sha256File } from "../codex/binary";
import { ENVIRONMENT_POLICY } from "../codex/config";
import { outputValidator } from "../codex/protocol";
import {
  isModelId, isReasoningEffort, type CompleteJsonRequest, type CompleteJsonResult, type CompletionFailure, type ConnectionState,
  type HostModel, type HostProvider, type HostProviderContext, type HostProviderFactory, type ReasoningEffort,
  type TokenUsage, type WorkflowReadiness,
} from "../providers";
import type { RuntimePin } from "../runtime-install";
import { opencodePin } from "./release";

export type OpencodeSpawn = (command: string, args: readonly string[], options: {
  cwd: string; env: NodeJS.ProcessEnv; shell: false; windowsHide: true; stdio: ["pipe", "pipe", "pipe"];
}) => ChildProcessWithoutNullStreams;

export interface OpencodeProviderOptions {
  /** The installer's root: runtime/<platform>/opencode[.exe] beside its codex-runtime.json. */
  runtimeRoot: string;
  pin?: RuntimePin | null;
  spawn?: OpencodeSpawn;
  environment?: NodeJS.ProcessEnv;
  platform?: NodeJS.Platform;
  arch?: string;
  completionMs?: number;
  /** Runs `work` with the person's OpenCode API key, or null when they have none. */
  withKey?: <T>(work: (key: string | null) => Promise<T>) => Promise<T>;
}

type Failure = CompletionFailure | "runtime-missing" | "unsupported-platform";
const MESSAGES: Record<Failure, string> = {
  unavailable: "The local AI runtime is unavailable.",
  "runtime-missing": "The verified local AI runtime isn’t installed.",
  "unsupported-platform": "This computer is not supported by the OpenCode runtime.",
  context_unverified: "Application work is unavailable until this local runtime is verified.",
  auth: "OpenCode didn’t accept the request.",
  quota: "OpenCode’s free usage limit is reached. Try again later, or pick another AI in Settings.",
  model_unavailable: "OpenCode no longer offers this free model. Pick another model in Settings.",
  cancelled: "The request was cancelled.",
  incomplete: "OpenCode didn’t return a complete answer in time. Try again.",
  refused_or_invalid: "OpenCode didn’t return an answer that matches the required format.",
  runtime: "The local AI runtime stopped or returned an invalid response. Try again.",
};

class OpencodeError extends Error {
  readonly reason: Failure;
  constructor(reason: Failure) { super(MESSAGES[reason]); this.reason = reason; }
}

const MAX_STDOUT = 4 * 1024 * 1024;

function model(id: string, label: string): HostModel {
  if (!isModelId(id) || !isReasoningEffort("medium")) throw new Error("Invalid OpenCode model");
  return Object.freeze({ id, label, efforts: Object.freeze(["medium" as ReasoningEffort]), defaultEffort: "medium" as ReasoningEffort, structuredOutput: false });
}

const MODELS: readonly HostModel[] = Object.freeze([
  model("nemotron-3.5-super-vl-free", "Nemotron 3.5 Super VL (free)"),
  model("nemotron-3.5-lightning-free", "Nemotron 3.5 Lightning (free)"),
]);

/** OpenCode has no schema mode, so the agent's prompt carries the schema and the answer is checked against it. */
function configFor(request: CompleteJsonRequest): string {
  const prompt = `${request.system}\n\nAnswer with exactly one JSON object and nothing else: no prose, no code fence. It must satisfy this JSON Schema:\n${JSON.stringify(request.schema)}`;
  return JSON.stringify({
    share: "disabled", autoupdate: false, permission: { "*": "deny" },
    agent: { batatis: { mode: "primary", prompt, tools: { "*": false } } },
  });
}

const record = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;

interface Events { text: string; error: Record<string, unknown> | null; usage: TokenUsage | null }

/** OpenCode's `--format json` prints one event per line; the answer is its text parts, a failure its error event. */
function readEvents(stdout: string): Events {
  const events: Events = { text: "", error: null, usage: null };
  for (const line of stdout.split(/\r?\n/)) {
    let event: Record<string, unknown> | null;
    try { event = record(JSON.parse(line)); } catch { continue; }
    if (!event) continue;
    const part = record(event.part);
    if (event.type === "text" && typeof part?.text === "string") events.text += part.text;
    else if (event.type === "error") events.error = record(event.error) ?? {};
    else if (event.type === "step_finish") {
      const tokens = record(part?.tokens);
      const count = (n: unknown) => typeof n === "number" && Number.isSafeInteger(n) && n >= 0 ? n : null;
      const inputTokens = count(tokens?.input), outputTokens = count(tokens?.output);
      if (inputTokens !== null && outputTokens !== null) events.usage = { inputTokens: (events.usage?.inputTokens ?? 0) + inputTokens, outputTokens: (events.usage?.outputTokens ?? 0) + outputTokens };
    }
  }
  return events;
}

function classify(error: Record<string, unknown>): OpencodeError {
  const type = typeof error.type === "string" ? error.type : "";
  const text = `${type} ${typeof error.message === "string" ? error.message : ""}`;
  if (error.status === 429 || /free-limit|free usage limit|rate.?limit/i.test(text)) return new OpencodeError("quota");
  if (error.status === 401 || error.status === 403) return new OpencodeError("auth");
  if (/model is unavailable|model.{0,40}(?:not found|not available|unsupported)/i.test(text)) return new OpencodeError("model_unavailable");
  return new OpencodeError("runtime");
}

/** The first JSON object in the model's text, tolerating a code fence around it. */
function jsonObject(text: string): Record<string, unknown> | null {
  const start = text.indexOf("{"), end = text.lastIndexOf("}");
  if (start < 0 || end <= start) return null;
  try { return record(JSON.parse(text.slice(start, end + 1))); } catch { return null; }
}

export function opencodeProviderFactory(options: OpencodeProviderOptions): HostProviderFactory {
  return (context) => new OpencodeProvider(context, options);
}

class OpencodeProvider implements HostProvider {
  readonly id = "opencode";
  private readonly context: HostProviderContext;
  private readonly options: OpencodeProviderOptions;
  private readonly environment: NodeJS.ProcessEnv;
  private readonly platform: NodeJS.Platform;
  private readonly pin: RuntimePin | null;
  private readonly active = new Set<AbortController>();
  private readonly children = new Set<ChildProcessWithoutNullStreams>();
  private tail: Promise<unknown> = Promise.resolve();
  private disposed = false;
  private verified: { path: string; identity: string; sha256: string } | null = null;

  constructor(context: HostProviderContext, options: OpencodeProviderOptions) {
    this.context = context;
    this.options = options;
    this.environment = { ...(options.environment ?? process.env) };
    this.platform = options.platform ?? process.platform;
    this.pin = options.pin === undefined ? opencodePin(this.platform, options.arch ?? process.arch) : options.pin;
  }

  onChange(): () => void { return () => {}; }

  /** The pinned executable, re-hashed whenever its file changes: an install manifest alone never authorizes it. */
  private async executable(): Promise<string> {
    const pin = this.pin;
    if (!pin) throw new OpencodeError("unsupported-platform");
    try {
      const path = await realpath(join(this.options.runtimeRoot, "runtime", pin.key, pin.executable));
      const info = await stat(path);
      if (!info.isFile()) throw new OpencodeError("runtime-missing");
      const identity = `${info.dev}:${info.ino}:${info.size}:${info.mtimeMs}:${info.ctimeMs}`;
      const manifest = record(JSON.parse(await readFile(join(dirname(path), "codex-runtime.json"), "utf8")));
      const sha256 = this.verified?.path === path && this.verified.identity === identity ? this.verified.sha256 : await sha256File(path);
      if (!pin.executables.includes(sha256) || manifest?.version !== pin.version || manifest.platform !== pin.key ||
        manifest.archiveSha256 !== pin.download.sha256 || manifest.executableSha256 !== sha256) {
        this.verified = null;
        throw new OpencodeError("runtime-missing");
      }
      this.verified = { path, identity, sha256 };
      return path;
    } catch (error) {
      if (error instanceof OpencodeError) throw error;
      throw new OpencodeError("runtime-missing");
    }
  }

  /** Its own home, so nothing of the person's own OpenCode settings, sign-ins or history is read or written. */
  private async childEnvironment(config: string): Promise<NodeJS.ProcessEnv> {
    const home = join(this.context.stateDir, "opencode-home");
    if (!isAbsolute(home)) throw new OpencodeError("runtime");
    await mkdir(home, { recursive: true, mode: 0o700 });
    const env: NodeJS.ProcessEnv = {
      HOME: home, USERPROFILE: home, APPDATA: join(home, "appdata"), LOCALAPPDATA: join(home, "localappdata"),
      XDG_CONFIG_HOME: join(home, "config"), XDG_DATA_HOME: join(home, "data"), XDG_STATE_HOME: join(home, "state"), XDG_CACHE_HOME: join(home, "cache"),
      OPENCODE_CONFIG_CONTENT: config, OPENCODE_DISABLE_AUTOUPDATE: "1",
    };
    const keys = this.platform === "win32" ? ENVIRONMENT_POLICY.windowsKeys.filter((key) => !["USERPROFILE", "APPDATA", "LOCALAPPDATA"].includes(key)) : ["LANG", "TMPDIR"];
    for (const key of keys) {
      const value = Object.entries(this.environment).find(([name]) => this.platform === "win32" ? name.toLowerCase() === key.toLowerCase() : name === key)?.[1];
      if (value !== undefined) env[key] = value;
    }
    if (this.platform === "win32") {
      const root = env.SystemRoot;
      if (!root || !isAbsolute(root)) throw new OpencodeError("runtime-missing");
      env.PATH = ENVIRONMENT_POLICY.windowsPath.map((part) => join(root, ...part.split("/"))).join(";");
    } else env.PATH = ENVIRONMENT_POLICY.darwinPath;
    return env;
  }

  async status(): Promise<ConnectionState> {
    try {
      await this.executable();
      return { state: "signed-in", plan: "Free models" };
    } catch (error) {
      const failure = error instanceof OpencodeError ? error : new OpencodeError("runtime-missing");
      return { state: "unavailable", reason: failure.reason === "unsupported-platform" ? "unsupported-platform" : "runtime-missing", message: failure.message };
    }
  }

  async workflowReadiness(): Promise<WorkflowReadiness> {
    const state = await this.status();
    return state.state === "signed-in" ? { ready: true } : { ready: false, reason: "unavailable", message: state.state === "unavailable" ? state.message : MESSAGES.unavailable };
  }

  async startLogin(): Promise<ConnectionState> { return this.status(); }
  async cancelLogin(): Promise<ConnectionState> { return this.status(); }
  async logout(): Promise<ConnectionState> { return this.status(); }
  async models(): Promise<readonly HostModel[]> { return MODELS; }

  async completeJson(request: CompleteJsonRequest, signal: AbortSignal): Promise<CompleteJsonResult> {
    const abort = new AbortController();
    const forward = () => abort.abort();
    const deadline = setTimeout(() => abort.abort(new OpencodeError("incomplete")), this.options.completionMs ?? 225_000);
    signal.addEventListener("abort", forward, { once: true });
    if (signal.aborted) forward();
    this.active.add(abort);
    try {
      const entry = MODELS.find((item) => item.id === request.model);
      if (!entry || !entry.efforts.includes(request.effort)) throw new OpencodeError("model_unavailable");
      let valid: (value: unknown) => boolean;
      try { valid = outputValidator(request.schema); } catch { throw new OpencodeError("runtime"); }
      return await this.serialize(abort.signal, async () => {
        const executable = await this.executable();
        const env = await this.childEnvironment(configFor(request));
        await mkdir(this.context.workDir, { recursive: true, mode: 0o700 });
        const args = ["run", "--standalone", "--agent", "batatis", "--format", "json", "-m", `opencode/${request.model}`, request.user];
        const withKey = this.options.withKey ?? ((work) => work(null));
        const out = await withKey(async (key) => {
          if (key !== null) env.OPENCODE_API_KEY = key;
          const printed = await this.run(executable, args, env, abort.signal);
          if (key !== null && printed.includes(key)) throw new OpencodeError("runtime");
          return printed;
        });
        const events = readEvents(out);
        if (events.error) {
          const failure = classify(events.error);
          this.context.log(`OpenCode completion failed (${failure.reason}).`);
          throw failure;
        }
        const json = jsonObject(events.text);
        if (!json || !valid(json)) throw new OpencodeError("refused_or_invalid");
        return { ok: true, json, model: request.model, effort: request.effort, usage: events.usage } as const;
      });
    } catch (error) {
      const failure = abort.signal.aborted ? this.abortReason(abort.signal) : error instanceof OpencodeError ? error : new OpencodeError("runtime");
      const reason = failure.reason === "runtime-missing" || failure.reason === "unsupported-platform" ? "unavailable" : failure.reason;
      return { ok: false, reason, message: failure.message };
    } finally {
      clearTimeout(deadline);
      signal.removeEventListener("abort", forward);
      this.active.delete(abort);
    }
  }

  /** Runs one command to its end; a stop, an overflow or a failed start rejects instead of returning partial output. */
  private run(executable: string, args: readonly string[], env: NodeJS.ProcessEnv, signal: AbortSignal): Promise<string> {
    return new Promise((resolve, reject) => {
      if (signal.aborted) return reject(this.abortReason(signal));
      const child = (this.options.spawn ?? nodeSpawn)(executable, args, { cwd: this.context.workDir, env, shell: false, windowsHide: true, stdio: ["pipe", "pipe", "pipe"] });
      this.children.add(child);
      let stdout = "", ending: OpencodeError | null = null, escalate: ReturnType<typeof setTimeout> | undefined;
      // The child is stopped first and the call settles once it has exited, so nothing outlives a cancel.
      const stop = (why: OpencodeError) => {
        if (ending) return;
        ending = why;
        child.kill();
        escalate = setTimeout(() => child.kill("SIGKILL"), 2000);
      };
      const onAbort = () => stop(this.abortReason(signal));
      child.stdout.setEncoding("utf8");
      child.stdout.on("data", (chunk: string) => {
        if (stdout.length + chunk.length > MAX_STDOUT) return stop(new OpencodeError("runtime"));
        stdout += chunk;
      });
      child.stderr.resume();
      child.stdin.on("error", () => {});
      child.stdin.end();
      let ended = false;
      const end = () => {
        if (ended) return;
        ended = true;
        clearTimeout(escalate);
        signal.removeEventListener("abort", onAbort);
        this.children.delete(child);
        if (ending) reject(ending); else resolve(stdout);
      };
      child.once("error", () => { ending ??= new OpencodeError("runtime"); if (child.pid === undefined) end(); });
      child.once("close", end);
      signal.addEventListener("abort", onAbort, { once: true });
    });
  }

  private abortReason(signal: AbortSignal): OpencodeError {
    return signal.reason instanceof OpencodeError ? signal.reason : new OpencodeError("cancelled");
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
      if (this.disposed) throw new OpencodeError("cancelled");
      return task();
    })();
    this.tail = Promise.allSettled([previous, result]);
    return result;
  }

  async dispose(): Promise<void> {
    this.disposed = true;
    for (const controller of this.active) controller.abort();
    await this.tail;
  }
}
