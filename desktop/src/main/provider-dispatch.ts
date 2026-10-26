import { randomUUID } from "node:crypto";
import type { CallReply, HostCall } from "./engine";
import type { KeyVault } from "./credentials";
import { checkCompletion, KeyProviders } from "./provider-http";
import { HostedAi } from "./provider-hosted";
import { DEFAULT_SELECTION, MENU, isSlot, slotForTask, type AiSelection, type Pick } from "./models";
import { isModelId, isReasoningEffort, type AccountId, type CompleteJsonRequest, type HostProvider, type ModelId, type ReasoningEffort } from "./providers";

const MAX_TEXT = 2_500_000;
const TASKS = new Set(["intake", "document-review", "identify-picks", "assistant"]);
export const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const cancelled = (): CallReply => ({ ok: false, reason: "cancelled", message: "The AI selection or person changed. Run the check again." });

function abortable<T>(work: Promise<T>, signal: AbortSignal): Promise<T | null> {
  if (signal.aborted) return Promise.resolve(null);
  return new Promise<T | null>((resolve, reject) => {
    const cancel = () => { signal.removeEventListener("abort", cancel); resolve(null); };
    signal.addEventListener("abort", cancel, { once: true });
    work.then(resolve, reject).finally(() => signal.removeEventListener("abort", cancel));
  });
}

const billingOf = (pick: Pick) => (pick.source === "off" ? "none" : MENU[pick.source].billing);

/** One lease per selection/person/workspace. No ambient routing across engine worker threads. */
export class ProviderDispatch {
  #lease = randomUUID();
  #pending = new Set<AbortController>();
  #selection: AiSelection = { ...DEFAULT_SELECTION };
  #account: (id: AccountId) => HostProvider;
  #vault: KeyVault;
  #keys: KeyProviders;
  #hosted: HostedAi;
  #accepting: () => boolean;
  constructor(deps: { account: (id: AccountId) => HostProvider; vault: KeyVault; keys?: KeyProviders; hosted?: HostedAi; accepting: () => boolean }) {
    this.#account = deps.account; this.#vault = deps.vault; this.#keys = deps.keys ?? new KeyProviders(deps.vault);
    this.#hosted = deps.hosted ?? new HostedAi(deps.vault); this.#accepting = deps.accepting;
  }

  /** Screening runs on Batatis AI when the workflow does, otherwise on the person's own screening key. */
  #screensHosted(): boolean { return this.#selection.workflow.source === "batatis"; }
  get selection(): AiSelection { return structuredClone(this.#selection); }
  select(value: AiSelection) { this.invalidate(); this.#selection = structuredClone(value); }
  invalidate() {
    this.#lease = randomUUID();
    for (const pending of this.#pending) pending.abort();
    this.#pending.clear();
  }
  /** What the engine may do for one kind of work: whether AI is on for it, its billing, and screening. */
  async profile(args: unknown): Promise<CallReply> {
    if (!this.#accepting()) return cancelled();
    const lease = this.#lease;
    const slot = record(args) && isSlot(args.slot) ? args.slot : "workflow";
    const pick = this.#selection[slot];
    const screening = slot === "workflow" && pick.source !== "off" && this.#selection.screening
      && await this.#vault.status(this.#screensHosted() ? "batatis" : "jev") === "saved";
    if (lease !== this.#lease || !this.#accepting()) return cancelled();
    return { ok: true, value: { lease, generation: pick.source, screening, billing: billingOf(pick) } };
  }
  valid(lease: unknown): boolean { return lease === this.#lease && this.#accepting(); }

  readonly call: HostCall = async (op, args, signal) => {
    if (op === "provider.profile") return this.profile(args);
    if (!record(args) || !this.valid(args.lease) || signal.aborted) return cancelled();
    const lease = this.#lease;
    const abort = new AbortController();
    const detach = () => signal.removeEventListener("abort", cancel);
    const cancel = () => abort.abort();
    signal.addEventListener("abort", cancel, { once: true });
    this.#pending.add(abort);
    const timeout = setTimeout(cancel, op === "provider.jev" && typeof args.timeout === "number" ? Math.min(180_000, args.timeout * 1000) : 235_000);
    try {
      let reply: CallReply;
      if (op === "provider.completeJson") {
        const request = parseCompleteJson(args);
        if (!request) return { ok: false, reason: "refused_or_invalid", message: "The request was not valid." };
        if (!TASKS.has(request.task) || request.model !== "gpt-6-luna" || request.effort !== "medium") {
          return { ok: false, reason: "model_unavailable", message: "The request does not match the pinned desktop workflow profile." };
        }
        // The engine asks for its one workflow profile; the person's pick for this kind of work answers it.
        const pick = this.#selection[slotForTask(request.task)];
        if (pick.source === "off") return { ok: false, reason: "unavailable", message: "AI is off in Settings." };
        const routed: CompleteJsonRequest = { ...request, model: pick.model as ModelId, effort: pick.effort as ReasoningEffort };
        let completed;
        if (pick.source === "openai") completed = await abortable(this.#keys.complete(routed, abort.signal), abort.signal);
        else if (pick.source === "batatis") completed = await abortable(this.#hosted.complete(routed, abort.signal), abort.signal);
        else {
          const account = this.#account(pick.source);
          const readiness = await abortable(account.workflowReadiness(), abort.signal);
          if (!this.valid(lease) || abort.signal.aborted || !readiness) return cancelled();
          if (!readiness.ready) return { ok: false, reason: readiness.reason, message: readiness.message };
          completed = await abortable(account.completeJson(routed, abort.signal), abort.signal);
        }
        if (!completed) return cancelled();
        const result = checkCompletion(routed, completed);
        reply = result.ok ? { ok: true, value: { json: result.json, model: request.model, effort: request.effort, usage: result.usage,
          served: { source: pick.source, model: result.model, effort: result.effort }, billing: billingOf(pick) } } : result;
      } else if (op === "provider.jev") {
        if (this.#selection.workflow.source === "off" || !this.#selection.screening || typeof args.body !== "string" || typeof args.timeout !== "number"
          || !Number.isFinite(args.timeout) || args.timeout <= 0 || args.timeout > 180) return { ok: false, reason: "unavailable", message: "Optional screening is off or the request was invalid." };
        const body: unknown = JSON.parse(args.body);
        if (!record(body) || body.model !== "jev-1.13.0" || !record(body.questions) || Object.keys(body.questions).length < 1
          || Object.keys(body.questions).length > 400 || !("state" in body) || Buffer.byteLength(args.body) > MAX_TEXT) {
          return { ok: false, reason: "refused_or_invalid", message: "The screening request did not match its pinned profile." };
        }
        const response = await abortable((this.#screensHosted() ? this.#hosted : this.#keys).screen(args.body, abort.signal), abort.signal);
        reply = response ? { ok: true, value: response } : { ok: false, reason: "auth",
          message: this.#screensHosted() ? "Add your Batatis access code in Settings." : "Add the optional screening key in Settings." };
      } else return { ok: false, reason: "unavailable", message: "Unknown host call." };
      return this.valid(lease) && !abort.signal.aborted ? reply : cancelled();
    } catch {
      return { ok: false, reason: abort.signal.aborted ? "cancelled" : "runtime", message: "The selected connection could not complete this request." };
    } finally {
      clearTimeout(timeout); detach(); this.#pending.delete(abort);
    }
  };
}

export function parseCompleteJson(args: unknown): CompleteJsonRequest | null {
  if (!record(args)) return null;
  const { task, system, user, schema, model, effort, maxOutputTokens } = args;
  if (typeof task !== "string" || !/^[a-z][a-z0-9-]{0,40}$/.test(task)) return null;
  if (typeof system !== "string" || typeof user !== "string" || Buffer.byteLength(system + user) > MAX_TEXT) return null;
  if (!record(schema) || !isModelId(model) || !isReasoningEffort(effort)) return null;
  if (maxOutputTokens !== null && maxOutputTokens !== undefined && !(Number.isSafeInteger(maxOutputTokens) && Number(maxOutputTokens) > 0)) return null;
  return { task, system, user, schema, model, effort, maxOutputTokens: typeof maxOutputTokens === "number" ? maxOutputTokens : null };
}
