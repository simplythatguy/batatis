import type { CompleteJsonRequest, CompleteJsonResult, TokenUsage } from "../providers";
import { EFFORT, MODEL } from "./config";
import { AdapterError, classifyErrorInfo, id, object, outputValidator, parseItem, parseTurn, parseUsage, type Item, type Turn } from "./protocol";
import type { Notification } from "./rpc";

export class CompletionTurn {
  readonly result: Promise<CompleteJsonResult>;
  private resolve!: (value: CompleteJsonResult) => void;
  private done = false;
  private turnId: string | null = null;
  private responseSeen = false;
  private terminal: Turn | null = null;
  private completed = new Map<string, Item>();
  private usage: TokenUsage | null = null;
  private count = 0;
  private byteCount = 0;
  private validate: ReturnType<typeof outputValidator>;
  readonly threadId: string;
  private readonly request: CompleteJsonRequest;
  private readonly violateContext: (error: AdapterError) => void;

  constructor(threadId: string, request: CompleteJsonRequest, violateContext: (error: AdapterError) => void) {
    this.threadId = threadId;
    this.request = request;
    this.violateContext = violateContext;
    this.validate = outputValidator(request.schema);
    this.result = new Promise((resolve) => { this.resolve = resolve; });
  }

  get currentTurnId(): string | null { return this.turnId; }
  get isDone(): boolean { return this.done; }

  startResponse(value: unknown): void {
    if (this.done) return;
    try {
      const turn = parseTurn(object(value).turn);
      if (this.turnId !== null && this.turnId !== turn.id) throw new AdapterError("runtime");
      this.turnId = turn.id;
      this.responseSeen = true;
      if (turn.status !== "inProgress" && this.terminal === null) throw new AdapterError("incomplete");
      this.finish();
    } catch (error) { this.fail(error); }
  }

  accept(event: Notification): void {
    if (this.done) return;
    try {
      const params = object(event.params);
      if (params.threadId !== this.threadId) return;
      if (++this.count > 16_384) throw new AdapterError("runtime");
      this.byteCount += Buffer.byteLength(JSON.stringify(event), "utf8");
      if (this.byteCount > 32 * 1024 * 1024) throw new AdapterError("runtime");
      if (event.method === "model/rerouted") throw new AdapterError("model_unavailable");
      if (event.method === "thread/compacted") throw new AdapterError("incomplete");
      if (event.method === "thread/status/changed") {
        const status = object(params.status);
        if (status.type === "active") {
          if (!Array.isArray(status.activeFlags) || status.activeFlags.length) throw new AdapterError("context_unverified");
        } else if (status.type !== "idle") throw new AdapterError("runtime");
        return;
      }
      if (event.method === "turn/started" || event.method === "turn/completed") {
        const turn = parseTurn(params.turn);
        if (this.turnId !== null && turn.id !== this.turnId) return;
        this.turnId = turn.id;
        if (event.method === "turn/started") {
          if (turn.status !== "inProgress") throw new AdapterError("runtime");
          for (const item of turn.items) this.checkItem(item);
        } else {
          if (this.terminal) throw new AdapterError("runtime");
          this.terminal = turn;
          this.finish();
        }
        return;
      }
      const turnId = id(params.turnId);
      if (this.turnId !== null && turnId !== this.turnId) return;
      this.turnId = turnId;
      switch (event.method) {
        case "item/started": this.checkItem(parseItem(params.item)); break;
        case "item/completed": {
          const item = parseItem(params.item);
          this.checkItem(item);
          if (this.completed.has(item.id) || this.completed.size >= 1024) throw new AdapterError("runtime");
          this.completed.set(item.id, item);
          break;
        }
        case "thread/tokenUsage/updated": this.usage = parseUsage(params.tokenUsage); break;
        case "error":
          if (typeof params.willRetry !== "boolean") throw new AdapterError("runtime");
          if (!params.willRetry) throw new AdapterError(classifyErrorInfo(object(params.error)));
          break;
        case "item/agentMessage/delta":
        case "item/reasoning/summaryTextDelta":
        case "item/reasoning/summaryPartAdded":
        case "item/reasoning/textDelta":
          id(params.itemId);
          break;
        case "model/verification":
        case "turn/moderationMetadata":
        case "model/safetyBuffering/updated": break;
        default: throw new AdapterError("context_unverified");
      }
    } catch (error) { this.fail(error); }
  }

  private checkItem(item: Item): void {
    if (item.type === "userMessage" && item.text !== this.request.user) throw new AdapterError("context_unverified");
  }

  fail(value: unknown): void {
    if (this.done) return;
    const error = value instanceof AdapterError ? value : new AdapterError("runtime");
    this.done = true;
    if (error.reason === "context_unverified") this.violateContext(error);
    const reason = error.reason === "runtime-missing" || error.reason === "unsupported-platform" || error.reason === "keyring-unavailable" ? "unavailable"
      : error.reason === "device-prerequisite" ? "auth" : error.reason;
    this.resolve({ ok: false, reason, message: error.message });
  }

  private finish(): void {
    if (this.done || !this.responseSeen || this.terminal === null) return;
    try {
      const turn = this.terminal;
      if (turn.error) throw new AdapterError(turn.error);
      if (turn.status !== "completed") throw new AdapterError("incomplete");
      const candidates = [...this.completed.values()].filter((item) => item.type === "agentMessage" && item.phase !== "commentary");
      if (candidates.length !== 1) throw new AdapterError("incomplete");
      const candidate = candidates[0];
      if (candidate.type !== "agentMessage") throw new AdapterError("incomplete");
      for (const item of turn.items) this.checkItem(item);
      const summary = turn.items.filter((item) => item.type === "agentMessage" && item.phase !== "commentary");
      const lastAgent = turn.items.findLast((item) => item.type === "agentMessage");
      if (summary.length !== 1 || lastAgent?.type !== "agentMessage" || lastAgent.id !== candidate.id || lastAgent.text !== candidate.text || lastAgent.phase !== candidate.phase)
        throw new AdapterError("incomplete");
      let json: unknown;
      try { json = JSON.parse(candidate.text); } catch { throw new AdapterError("refused_or_invalid"); }
      if (json === null || typeof json !== "object" || Array.isArray(json)) throw new AdapterError("refused_or_invalid");
      const payload = object(json);
      if (payload.refusal || payload.type === "refusal" || !this.validate(payload)) throw new AdapterError("refused_or_invalid");
      if (this.request.maxOutputTokens !== null && this.usage !== null && this.usage.outputTokens > this.request.maxOutputTokens) throw new AdapterError("incomplete");
      this.done = true;
      this.resolve({ ok: true, json: payload, model: MODEL, effort: EFFORT, usage: this.usage });
    } catch (error) { this.fail(error); }
  }
}
