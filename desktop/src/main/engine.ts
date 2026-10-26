/**
 * One owned engine process per running workspace, spoken to over private pipes (engine/desktop/bridge.py).
 * A request whose engine goes away fails with EngineLost; nothing is ever replayed.
 */
import { spawn } from "node:child_process";
import { chunks, encodeFrame, FrameDecoder, FrameError, type FrameHeader } from "./frames";

export const PROTOCOL = "batatis.bridge.v1";
const START_TIMEOUT_MS = 60_000;

export type WorkspaceKind = "local" | "dev";
export type DevProfileId = "applicant" | `reviewer:${string}`;

export function isDevProfileId(value: unknown): value is DevProfileId {
  return value === "applicant" || (typeof value === "string" && /^reviewer:[a-z][a-z-]{0,39}$/.test(value));
}

export interface DevProfile {
  profile: DevProfileId;
  userId: string;
  name: string;
  kind: "applicant" | "reviewer";
  authority: string | null;
}

export interface EngineHello {
  workspace: { kind: WorkspaceKind; id: string };
  codedb: { available: boolean; build: string | null; expectedBuild: string };
  /** The test people of Local development, in engine order; empty in the normal workspace. */
  profiles: readonly DevProfile[];
}

export interface EngineCommand {
  command: string;
  args: readonly string[];
  cwd: string;
  env: Readonly<Record<string, string>>;
}

export interface EngineRequest {
  method: string;
  path: string;
  query: string;
  headers: readonly (readonly [string, string])[];
  body: Uint8Array;
}

export interface EngineReply {
  status: number;
  headers: [string, string][];
  body: ReadableStream<Uint8Array>;
}

export class EngineLost extends Error {}
export class EngineFailed extends Error {}

export type ControlResult = { ok: true; value: unknown } | { ok: false; error: string };
export type CallReply = { ok: true; value: unknown } | { ok: false; reason: string; message: string };
export type HostCall = (op: string, args: unknown, signal: AbortSignal) => Promise<CallReply>;

export type EngineStart =
  | { kind: "ready"; engine: Engine }
  | { kind: "refused"; reason: string }
  | { kind: "failed"; detail: string };

interface Pending {
  started: boolean;
  resolve: (reply: EngineReply) => void;
  reject: (error: Error) => void;
  controller: ReadableStreamDefaultController<Uint8Array> | null;
  detach: () => void;
  calls: Set<AbortController>;
}

type Child = ReturnType<typeof spawn>;

export class Engine {
  readonly hello: EngineHello;
  /** Resolves with the exit code (null when killed) once the process is gone. */
  readonly exited: Promise<number | null>;
  #child: Child;
  #pending = new Map<string, Pending>();
  #controls = new Map<string, (result: ControlResult) => void>();
  #calls = new Map<string, AbortController>();
  #idle = new Set<() => void>();
  #ids = 0;
  #gone = false;
  #onCall: HostCall;

  constructor(child: Child, hello: EngineHello, exited: Promise<number | null>, onCall: HostCall) {
    this.#child = child;
    this.hello = hello;
    this.exited = exited;
    this.#onCall = onCall;
    void exited.then(() => this.#lose());
  }

  get busy(): number {
    return this.#pending.size;
  }

  get pid(): number | undefined {
    return this.#child.pid;
  }

  request(request: EngineRequest, signal?: AbortSignal): Promise<EngineReply> {
    if (this.#gone) return Promise.reject(new EngineLost("engine stopped"));
    if (signal?.aborted) return Promise.reject(new DOMException("The request was cancelled.", "AbortError"));
    const id = `r${++this.#ids}`;
    return new Promise<EngineReply>((resolve, reject) => {
      const abort = () => this.#cancel(id, new DOMException("The request was cancelled.", "AbortError"));
      signal?.addEventListener("abort", abort, { once: true });
      this.#pending.set(id, { started: false, resolve, reject, controller: null, detach: () => signal?.removeEventListener("abort", abort), calls: new Set() });
      this.#write({ t: "req", id, method: request.method, path: request.path, query: request.query, headers: request.headers.map(([k, v]) => [k, v]) });
      const pieces = chunks(request.body);
      pieces.forEach((piece, n) => this.#write({ t: "body", id, more: n < pieces.length - 1 }, piece));
    });
  }

  control(op: string, args: Record<string, unknown> = {}): Promise<ControlResult> {
    if (this.#gone) return Promise.resolve({ ok: false, error: "engine-lost" });
    const id = `k${++this.#ids}`;
    return new Promise((resolve) => {
      this.#controls.set(id, resolve);
      this.#write({ t: "ctl", id, op, args });
    });
  }

  /** True once nothing is in flight; false if work is still running at the deadline. */
  idle(timeoutMs: number): Promise<boolean> {
    if (this.#pending.size === 0) return Promise.resolve(true);
    return new Promise((resolve) => {
      const done = () => { clearTimeout(timer); this.#idle.delete(done); resolve(true); };
      const timer = setTimeout(() => { this.#idle.delete(done); resolve(this.#pending.size === 0); }, timeoutMs);
      this.#idle.add(done);
    });
  }

  /** Ask the engine to stop, close its input, and kill it if it is still running at the deadline. */
  async stop(timeoutMs = 5000): Promise<void> {
    if (!this.#gone) {
      this.#write({ t: "ctl", id: `k${++this.#ids}`, op: "shutdown", args: {} });
      this.#child.stdin?.end();
    }
    const timer = setTimeout(() => this.#child.kill("SIGKILL"), timeoutMs);
    await this.exited;
    clearTimeout(timer);
  }

  receive(header: FrameHeader, body: Uint8Array): void {
    const id = typeof header.id === "string" ? header.id : "";
    switch (header.t) {
      case "start": return this.#start(id, header);
      case "body": return this.#body(id, header.more === true, body);
      case "fail": return this.#fail(id, typeof header.detail === "string" ? header.detail : "engine error");
      case "ctl.res": return this.#controlResult(id, header);
      case "call": return this.#call(id, header);
      default: return;
    }
  }

  #start(id: string, header: FrameHeader) {
    const entry = this.#pending.get(id);
    if (!entry || entry.started) return;
    const status = typeof header.status === "number" ? header.status : 502;
    const headers = Array.isArray(header.headers) ? header.headers.filter(isPair) : [];
    const body = new ReadableStream<Uint8Array>({
      start: (controller) => { entry.controller = controller; },
      cancel: () => this.#cancel(id, null),
    });
    entry.started = true;
    entry.resolve({ status, headers, body });
  }

  #body(id: string, more: boolean, body: Uint8Array) {
    const entry = this.#pending.get(id);
    if (!entry?.started || !entry.controller) return;
    if (body.length) entry.controller.enqueue(body);
    if (!more) {
      entry.controller.close();
      this.#finish(id);
    }
  }

  #fail(id: string, detail: string) {
    const entry = this.#pending.get(id);
    if (!entry) return;
    if (entry.started) entry.controller?.error(new EngineFailed(detail));
    else entry.reject(new EngineFailed(detail));
    this.#finish(id);
  }

  #controlResult(id: string, header: FrameHeader) {
    const resolve = this.#controls.get(id);
    if (!resolve) return;
    this.#controls.delete(id);
    resolve(header.ok === true ? { ok: true, value: header.value } : { ok: false, error: typeof header.error === "string" ? header.error : "failed" });
  }

  #call(id: string, header: FrameHeader) {
    const op = typeof header.op === "string" ? header.op : "";
    const request = typeof header.requestId === "string" ? this.#pending.get(header.requestId) : undefined;
    const cancelled: CallReply = { ok: false, reason: "cancelled", message: "The originating request is no longer active." };
    if (op.startsWith("provider.") && (!request || this.#gone)) {
      this.#write({ t: "call.res", id, ...cancelled });
      return;
    }
    const abort = new AbortController();
    this.#calls.set(id, abort);
    request?.calls.add(abort);
    this.#onCall(op, header.args, abort.signal)
      .catch((): CallReply => ({ ok: false, reason: "runtime", message: "The host could not answer." }))
      .then((reply) => { if (!this.#gone) this.#write({ t: "call.res", id, ...(abort.signal.aborted ? cancelled : reply) }); })
      .finally(() => { this.#calls.delete(id); request?.calls.delete(abort); });
  }

  /** A consumer that stops reading (null) or a caller abort before the response started. */
  #cancel(id: string, reason: Error | null) {
    const entry = this.#pending.get(id);
    if (!entry) return;
    if (!this.#gone) this.#write({ t: "cancel", id });
    if (!entry.started) entry.reject(reason ?? new DOMException("The request was cancelled.", "AbortError"));
    else if (reason) entry.controller?.error(reason);
    this.#finish(id);
  }

  #finish(id: string) {
    const entry = this.#pending.get(id);
    entry?.detach();
    this.#pending.delete(id);
    for (const call of entry?.calls ?? []) call.abort();
    entry?.calls.clear();
    if (this.#pending.size === 0) for (const done of [...this.#idle]) done();
  }

  #write(header: { t: string } & Record<string, unknown>, body?: Uint8Array) {
    if (this.#gone || !this.#child.stdin?.writable) return;
    this.#child.stdin.write(encodeFrame(header, body));
  }

  #lose() {
    if (this.#gone) return;
    this.#gone = true;
    for (const [id, entry] of this.#pending) {
      if (entry.started) entry.controller?.error(new EngineLost("engine stopped"));
      else entry.reject(new EngineLost("engine stopped"));
      entry.detach();
      this.#pending.delete(id);
    }
    for (const resolve of this.#controls.values()) resolve({ ok: false, error: "engine-lost" });
    this.#controls.clear();
    for (const abort of this.#calls.values()) abort.abort();
    for (const done of [...this.#idle]) done();
  }
}

function isPair(value: unknown): value is [string, string] {
  return Array.isArray(value) && value.length === 2 && typeof value[0] === "string" && typeof value[1] === "string";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseProfile(value: unknown): DevProfile | null {
  if (!isRecord(value)) return null;
  const { profile, userId, name, kind, authority } = value;
  if (typeof profile !== "string" || typeof userId !== "string" || typeof name !== "string") return null;
  if (kind === "applicant" && profile === "applicant" && authority === null) return { profile, userId, name, kind, authority };
  if (kind === "reviewer" && typeof authority === "string" && isDevProfileId(profile) && profile === `reviewer:${authority}`) {
    return { profile, userId, name, kind, authority };
  }
  return null;
}

/** The engine's handshake, parsed at the process boundary. */
export function parseHello(header: FrameHeader): EngineHello | null {
  const { protocol, workspace, codedb, dev } = header;
  if (protocol !== PROTOCOL || !isRecord(workspace) || !isRecord(codedb)) return null;
  const kind = workspace.kind;
  if ((kind !== "local" && kind !== "dev") || typeof workspace.id !== "string") return null;
  if (typeof codedb.available !== "boolean" || typeof codedb.expectedBuild !== "string") return null;
  const build = typeof codedb.build === "string" ? codedb.build : null;
  const rawProfiles = kind === "dev" && isRecord(dev) && Array.isArray(dev.profiles) ? dev.profiles : [];
  const profiles = rawProfiles.map(parseProfile);
  if (profiles.some((p) => p === null)) return null;
  if (kind === "dev" && !profiles.some((p) => p?.kind === "applicant")) return null;
  return {
    workspace: { kind, id: workspace.id },
    codedb: { available: codedb.available, build, expectedBuild: codedb.expectedBuild },
    profiles: profiles.filter((p): p is DevProfile => p !== null),
  };
}

/** Start the engine and wait for its handshake. Never attaches to anything it did not start. */
export function startEngine(command: EngineCommand, options: { onCall: HostCall; log: (line: string) => void; startTimeoutMs?: number }): Promise<EngineStart> {
  const child = spawn(command.command, [...command.args], {
    cwd: command.cwd, env: { ...command.env }, stdio: ["pipe", "pipe", "pipe"], shell: false, windowsHide: true,
  });
  const exited = new Promise<number | null>((resolve) => {
    child.once("exit", (code) => resolve(code));
    child.once("error", () => resolve(null));
  });
  child.stdin?.on("error", () => {});
  let stderrTail = "";
  child.stderr?.on("data", (chunk: Buffer) => {
    const text = (stderrTail + chunk.toString("utf8")).split(/\r?\n/);
    stderrTail = text.pop() ?? "";
    for (const line of text) if (line.trim()) options.log(`engine: ${line.slice(0, 500)}`);
  });
  const decoder = new FrameDecoder();
  let engine: Engine | null = null;

  return new Promise<EngineStart>((resolve) => {
    let settled = false;
    const settle = (result: EngineStart) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(result);
    };
    const timer = setTimeout(() => {
      child.kill("SIGKILL");
      settle({ kind: "failed", detail: "The local service did not start in time." });
    }, options.startTimeoutMs ?? START_TIMEOUT_MS);
    child.stdout?.on("data", (chunk: Buffer) => {
      let frames;
      try {
        frames = decoder.push(chunk);
      } catch (error) {
        options.log(`engine: protocol error: ${error instanceof FrameError ? error.message : "unknown"}`);
        child.kill("SIGKILL");
        settle({ kind: "failed", detail: "The local service broke its protocol." });
        return;
      }
      for (const frame of frames) {
        if (engine) {
          engine.receive(frame.header, frame.body);
          continue;
        }
        if (frame.header.t === "refused") {
          settle({ kind: "refused", reason: typeof frame.header.reason === "string" ? frame.header.reason : "refused" });
          continue;
        }
        const hello = frame.header.t === "hello" ? parseHello(frame.header) : null;
        if (!hello) {
          child.kill("SIGKILL");
          settle({ kind: "failed", detail: "The local service is a different version." });
          return;
        }
        engine = new Engine(child, hello, exited, options.onCall);
        settle({ kind: "ready", engine });
      }
    });
    void exited.then((code) => settle({ kind: "failed", detail: `The local service stopped (${code ?? "killed"}).` }));
  });
}
