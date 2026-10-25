import { spawn as nodeSpawn, type ChildProcessByStdio } from "node:child_process";
import type { Readable, Writable } from "node:stream";
import { AdapterError, object, rpcFailure } from "./protocol";

export const MAX_FRAME_BYTES = 4 * 1024 * 1024;
export type SpawnFn = (command: string, args: readonly string[], options: {
  cwd: string; env: NodeJS.ProcessEnv; shell: false; windowsHide: true; stdio: ["pipe", "pipe", "ignore"];
}) => ChildProcessByStdio<Writable, Readable, null>;
export const spawnRuntime: SpawnFn = (command, args, options) => nodeSpawn(command, args, options);
export interface Notification { method: string; params: unknown }

interface Pending {
  resolve(value: unknown): void;
  reject(error: AdapterError): void;
  cleanup(): void;
}

export class JsonLineRpc {
  private buffer = Buffer.alloc(0);
  private nextId = 1;
  private pending = new Map<number, Pending>();
  private listeners = new Set<(event: Notification) => void>();
  private failureListeners = new Set<(error: AdapterError) => void>();
  private ended: AdapterError | null = null;
  private exited = false;
  private closePromise: Promise<void> | null = null;
  private readonly exitPromise: Promise<void>;
  private readonly child: ChildProcessByStdio<Writable, Readable, null>;
  private readonly stopMs: number;

  constructor(command: { executable: string; args: readonly string[]; cwd: string; env: NodeJS.ProcessEnv },
    spawn: SpawnFn = spawnRuntime, stopMs = 1000) {
    this.stopMs = stopMs;
    this.child = spawn(command.executable, command.args, { cwd: command.cwd, env: command.env, shell: false, windowsHide: true, stdio: ["pipe", "pipe", "ignore"] });
    this.exitPromise = new Promise((resolve) => {
      this.child.once("close", () => {
        this.exited = true;
        this.fail(new AdapterError("runtime"));
        resolve();
      });
    });
    this.child.once("error", () => this.fail(new AdapterError("unavailable")));
    this.child.stdin.on("error", () => this.fail(new AdapterError("runtime")));
    this.child.stdout.on("error", () => this.fail(new AdapterError("runtime")));
    this.child.stdout.on("data", (data: Buffer) => this.receive(data));
    this.child.stdout.once("end", () => this.fail(new AdapterError("runtime")));
  }

  get failure(): AdapterError | null { return this.ended; }

  onNotification(listener: (event: Notification) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  onFailure(listener: (error: AdapterError) => void): () => void {
    if (this.ended) listener(this.ended);
    else this.failureListeners.add(listener);
    return () => this.failureListeners.delete(listener);
  }

  request(method: string, params: unknown, timeoutMs: number, signal?: AbortSignal): Promise<unknown> {
    if (this.ended) return Promise.reject(this.ended);
    if (signal?.aborted) return Promise.reject(new AdapterError("cancelled"));
    if (this.pending.size >= 32 || this.nextId >= Number.MAX_SAFE_INTEGER) return Promise.reject(new AdapterError("runtime"));
    const requestId = this.nextId++;
    return new Promise((resolve, reject) => {
      const abort = () => this.fail(new AdapterError("cancelled"));
      const timer = setTimeout(() => this.fail(new AdapterError("incomplete")), timeoutMs);
      const cleanup = () => { clearTimeout(timer); signal?.removeEventListener("abort", abort); };
      this.pending.set(requestId, { resolve, reject, cleanup });
      signal?.addEventListener("abort", abort, { once: true });
      try { this.write({ id: requestId, method, params }); }
      catch (error) { this.fail(error instanceof AdapterError ? error : new AdapterError("runtime")); }
    });
  }

  notify(method: string): void { this.write({ method }); }

  private write(value: unknown): void {
    if (this.ended) throw this.ended;
    const bytes = Buffer.from(JSON.stringify(value) + "\n", "utf8");
    if (bytes.length - 1 > MAX_FRAME_BYTES || this.child.stdin.writableLength + bytes.length > MAX_FRAME_BYTES * 2)
      throw new AdapterError("runtime");
    this.child.stdin.write(bytes);
  }

  private receive(bytes: Buffer): void {
    if (this.ended) return;
    try {
      let offset = 0;
      while (offset < bytes.length && !this.ended) {
        const newline = bytes.indexOf(10, offset);
        const end = newline === -1 ? bytes.length : newline;
        const part = bytes.subarray(offset, end);
        if (this.buffer.length + part.length > MAX_FRAME_BYTES) throw new AdapterError("runtime");
        this.buffer = this.buffer.length ? Buffer.concat([this.buffer, part]) : Buffer.from(part);
        if (newline === -1) break;
        let frame = this.buffer;
        this.buffer = Buffer.alloc(0);
        if (frame.at(-1) === 13) frame = frame.subarray(0, -1);
        if (!frame.length) throw new AdapterError("runtime");
        const raw = new TextDecoder("utf-8", { fatal: true }).decode(frame);
        this.dispatch(JSON.parse(raw));
        offset = newline + 1;
      }
    } catch (error) { this.fail(error instanceof AdapterError ? error : new AdapterError("runtime")); }
  }

  private dispatch(value: unknown): void {
    const envelope = object(value);
    const hasId = Object.hasOwn(envelope, "id");
    if (Object.hasOwn(envelope, "jsonrpc")) throw new AdapterError("runtime");
    if (typeof envelope.method === "string") {
      if (!/^[A-Za-z][A-Za-z0-9_./-]{0,255}$/.test(envelope.method) || "result" in envelope || "error" in envelope) throw new AdapterError("runtime");
      if (hasId) {
        if (!(typeof envelope.id === "string" && envelope.id.length <= 256) && !(typeof envelope.id === "number" && Number.isSafeInteger(envelope.id))) throw new AdapterError("runtime");
        this.write({ id: envelope.id, error: { code: -32601, message: "This client does not support server requests." } });
        this.fail(new AdapterError("context_unverified"));
        return;
      }
      for (const listener of this.listeners) listener({ method: envelope.method, params: envelope.params });
      return;
    }
    if (!hasId || typeof envelope.id !== "number" || !Number.isSafeInteger(envelope.id) || envelope.id < 1 ||
      Object.hasOwn(envelope, "result") === Object.hasOwn(envelope, "error") || Object.hasOwn(envelope, "params") || Object.hasOwn(envelope, "method")) throw new AdapterError("runtime");
    const pending = this.pending.get(envelope.id);
    if (!pending) throw new AdapterError("runtime");
    const error = Object.hasOwn(envelope, "error") ? rpcFailure(envelope.error) : null;
    this.pending.delete(envelope.id);
    pending.cleanup();
    if (error) pending.reject(error);
    else pending.resolve(envelope.result);
  }

  fail(error: AdapterError): void {
    if (this.ended) return;
    this.ended = error;
    for (const pending of this.pending.values()) { pending.cleanup(); pending.reject(error); }
    this.pending.clear();
    for (const listener of this.failureListeners) listener(error);
    this.failureListeners.clear();
    this.listeners.clear();
    void this.close().catch(() => {});
  }

  close(): Promise<void> {
    if (this.closePromise) return this.closePromise;
    this.closePromise = this.shutdown();
    return this.closePromise;
  }

  private async shutdown(): Promise<void> {
    if (!this.ended) {
      this.ended = new AdapterError("cancelled");
      for (const pending of this.pending.values()) { pending.cleanup(); pending.reject(this.ended); }
      this.pending.clear();
      for (const listener of this.failureListeners) listener(this.ended);
      this.failureListeners.clear();
      this.listeners.clear();
    }
    this.child.stdin.end();
    const wait = async () => {
      let timer: ReturnType<typeof setTimeout> | undefined;
      await Promise.race([this.exitPromise, new Promise<void>((done) => { timer = setTimeout(done, this.stopMs); })]);
      clearTimeout(timer);
    };
    await wait();
    if (!this.exited) { this.child.kill("SIGTERM"); await wait(); }
    if (!this.exited) { this.child.kill("SIGKILL"); await wait(); }
    if (!this.exited) throw new AdapterError("runtime");
  }
}
