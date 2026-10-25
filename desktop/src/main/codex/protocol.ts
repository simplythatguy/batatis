import Ajv from "ajv";
import { join } from "node:path";
import { isReasoningEffort, type CompletionFailure, type ConnectionState, type HostModel, type TokenUsage } from "../providers";
import { DEVICE_URL, EFFORT, MODEL } from "./config";

export type AdapterFailure = CompletionFailure | "runtime-missing" | "unsupported-platform" | "keyring-unavailable" | "device-prerequisite";
const MESSAGES: Record<AdapterFailure, string> = {
  unavailable: "The local AI runtime is unavailable.",
  "runtime-missing": "The verified local AI runtime is missing. Reinstall the desktop app.",
  "unsupported-platform": "This computer is not supported by the bundled AI runtime.",
  "keyring-unavailable": "Secure credential storage is unavailable. The connection requires the operating system keyring.",
  "device-prerequisite": "Enable device-code sign-in in your ChatGPT security settings or ask your workspace administrator to allow it.",
  context_unverified: "Application work is unavailable until this exact local runtime and context configuration are verified.",
  auth: "Sign in to the local ChatGPT connection to continue.",
  quota: "The account has reached a usage limit. Try again when the limit resets.",
  model_unavailable: "The requested model and reasoning setting are unavailable. No other model was selected.",
  cancelled: "The request was cancelled.",
  incomplete: "The runtime did not return a complete answer. Try again.",
  refused_or_invalid: "The runtime did not return an answer that matches the required format.",
  runtime: "The local AI runtime stopped or returned an invalid response. Try again.",
};

export class AdapterError extends Error {
  readonly reason: AdapterFailure;
  constructor(reason: AdapterFailure) { super(MESSAGES[reason]); this.reason = reason; }
}

export function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new AdapterError("runtime");
  return value as Record<string, unknown>;
}

export function id(value: unknown): string {
  if (typeof value !== "string" || !/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$/.test(value)) throw new AdapterError("runtime");
  return value;
}

export function rpcFailure(value: unknown): AdapterError {
  const error = object(value);
  if (!Number.isSafeInteger(error.code) || typeof error.message !== "string") return new AdapterError("runtime");
  const text = error.message;
  if (/device.?code/i.test(text) && /disabled|not enabled|enable|not allowed/i.test(text)) return new AdapterError("device-prerequisite");
  if (/keyring|keychain|credential store|secure storage/i.test(text)) return new AdapterError("keyring-unavailable");
  const reason = classifyErrorInfo(error.data);
  if (reason !== "runtime") return new AdapterError(reason);
  if (/usage.?limit|rate.?limit|quota|budget exceeded|\b429\b/i.test(text)) return new AdapterError("quota");
  if (/unauthorized|unauthenticated|sign.?in required|account verification|\b40[13]\b/i.test(text)) return new AdapterError("auth");
  if (/model.{0,80}(unavailable|not found|not supported|not allowed)|unsupported.{0,30}(model|effort)/i.test(text)) return new AdapterError("model_unavailable");
  return new AdapterError("runtime");
}

export function classifyErrorInfo(value: unknown): CompletionFailure {
  const data = typeof value === "object" && value !== null && !Array.isArray(value) ? object(value) : null;
  const info = data && "codexErrorInfo" in data ? data.codexErrorInfo : value;
  if (info === "usageLimitExceeded" || info === "rateLimitExceeded" || info === "sessionBudgetExceeded") return "quota";
  if (info === "unauthorized") return "auth";
  if (info === "contextWindowExceeded") return "incomplete";
  if (info === "cyberPolicy" || info === "misalignmentPolicyViolation") return "refused_or_invalid";
  if (info === "modelNotFound" || info === "modelUnavailable") return "model_unavailable";
  if (typeof info === "object" && info !== null && !Array.isArray(info)) {
    for (const entry of [info, ...Object.values(info)]) {
      if (typeof entry !== "object" || entry === null || Array.isArray(entry)) continue;
      const status = object(entry).httpStatusCode;
      if (status === 401 || status === 403) return "auth";
      if (status === 429) return "quota";
    }
  }
  return "runtime";
}

export function parseAccount(value: unknown): { state: "signed-out" } | { state: "signed-in"; plan: string | null } {
  const reply = object(value);
  if (!Object.hasOwn(reply, "account") || typeof reply.requiresOpenaiAuth !== "boolean") throw new AdapterError("runtime");
  if (reply.account === null) return { state: "signed-out" };
  const account = object(reply.account);
  if (account.type !== "chatgpt") throw new AdapterError("auth");
  if (typeof account.planType !== "string" || !/^[a-z0-9_+-]{1,64}$/.test(account.planType)) throw new AdapterError("runtime");
  return { state: "signed-in", plan: account.planType };
}

export function parseLogin(value: unknown): Extract<ConnectionState, { state: "pending" }> {
  const reply = object(value);
  if (reply.type !== "chatgptDeviceCode" || reply.verificationUrl !== DEVICE_URL || typeof reply.userCode !== "string" || !/^[A-Z0-9-]{4,32}$/.test(reply.userCode))
    throw new AdapterError("auth");
  return { state: "pending", loginId: id(reply.loginId), verificationUrl: DEVICE_URL, userCode: reply.userCode };
}

export function parseLoginComplete(value: unknown): { loginId: string | null; success: boolean; prerequisite: boolean } {
  const reply = object(value);
  if (typeof reply.success !== "boolean" || (reply.error !== null && reply.error !== undefined && typeof reply.error !== "string")) throw new AdapterError("runtime");
  return {
    loginId: reply.loginId === null ? null : id(reply.loginId), success: reply.success,
    prerequisite: typeof reply.error === "string" && /device.?code/i.test(reply.error) && /disabled|enable|not allowed/i.test(reply.error),
  };
}

export function parseAccountUpdate(value: unknown): { signedOut: boolean } {
  const reply = object(value);
  if (reply.authMode !== null && reply.authMode !== "chatgpt" && reply.authMode !== "apiKey" && reply.authMode !== "chatgptAuthTokens" && reply.authMode !== "amazonBedrock")
    throw new AdapterError("runtime");
  return { signedOut: reply.authMode === null };
}

export function parseModels(value: unknown): { models: HostModel[]; cursor: string | null; count: number } {
  const reply = object(value);
  if (!Array.isArray(reply.data) || reply.data.length > 100) throw new AdapterError("runtime");
  const cursor = reply.nextCursor === null || reply.nextCursor === undefined ? null : reply.nextCursor;
  if (cursor !== null && (typeof cursor !== "string" || cursor.length < 1 || cursor.length > 4096)) throw new AdapterError("runtime");
  const models: HostModel[] = [];
  const seen = new Set<string>();
  for (const raw of reply.data) {
    const model = object(raw);
    const modelId = id(model.id);
    if (seen.has(modelId) || typeof model.model !== "string" || typeof model.displayName !== "string" || typeof model.hidden !== "boolean" || typeof model.isDefault !== "boolean" || typeof model.description !== "string" || typeof model.defaultReasoningEffort !== "string" || !Array.isArray(model.supportedReasoningEfforts))
      throw new AdapterError("runtime");
    seen.add(modelId);
    const efforts = model.supportedReasoningEfforts.map((raw) => {
      const effort = object(raw);
      if (!isReasoningEffort(effort.reasoningEffort) || typeof effort.description !== "string") throw new AdapterError("runtime");
      return effort.reasoningEffort;
    });
    if (modelId !== MODEL && model.model !== MODEL) continue;
    if (modelId !== MODEL || model.model !== MODEL) throw new AdapterError("model_unavailable");
    if (efforts.includes(EFFORT)) models.push({ id: MODEL, label: "GPT-6 Luna", efforts: [EFFORT], defaultEffort: EFFORT, structuredOutput: true });
  }
  return { models, cursor, count: reply.data.length };
}

export function assertRequirements(value: unknown): void {
  const reply = object(value);
  if (!Object.hasOwn(reply, "requirements")) throw new AdapterError("context_unverified");
  if (reply.requirements === null) return;
  const requirements = object(reply.requirements);
  if (requirements.additionalDeveloperInstructions !== "" && requirements.additionalDeveloperInstructions !== null)
    throw new AdapterError("context_unverified");
}

export function parseThread(value: unknown, cwd: string): string {
  const reply = object(value);
  if (reply.model !== MODEL) throw new AdapterError("model_unavailable");
  const thread = object(reply.thread);
  const sandbox = object(reply.sandbox);
  if (reply.modelProvider !== "openai" || reply.cwd !== cwd || reply.approvalPolicy !== "never" || reply.approvalsReviewer !== "user" ||
      sandbox.type !== "readOnly" || (sandbox.networkAccess !== undefined && sandbox.networkAccess !== false) || reply.reasoningEffort !== EFFORT ||
      !Array.isArray(reply.instructionSources) || reply.instructionSources.length !== 0 ||
      !Array.isArray(reply.runtimeWorkspaceRoots) || reply.runtimeWorkspaceRoots.length !== 0 ||
      thread.ephemeral !== true || thread.cwd !== cwd || thread.modelProvider !== "openai" || thread.model !== MODEL || thread.reasoningEffort !== EFFORT ||
      !Array.isArray(thread.environments) || thread.environments.length !== 0 || !Array.isArray(thread.turns) || thread.turns.length !== 0 ||
      (thread.forkedFromId !== undefined && thread.forkedFromId !== null) || (thread.parentThreadId !== undefined && thread.parentThreadId !== null))
    throw new AdapterError("context_unverified");
  return id(thread.id);
}

export type Item =
  | { type: "userMessage"; id: string; text: string }
  | { type: "reasoning"; id: string }
  | { type: "agentMessage"; id: string; text: string; phase: "final_answer" | "commentary" | null };

export function parseItem(value: unknown): Item {
  const item = object(value);
  const itemId = id(item.id);
  switch (item.type) {
    case "reasoning": return { type: "reasoning", id: itemId };
    case "userMessage": {
      if (!Array.isArray(item.content) || item.content.length !== 1) throw new AdapterError("context_unverified");
      const input = object(item.content[0]);
      if (input.type !== "text" || typeof input.text !== "string" || (input.text_elements !== undefined && (!Array.isArray(input.text_elements) || input.text_elements.length !== 0))) throw new AdapterError("context_unverified");
      return { type: "userMessage", id: itemId, text: input.text };
    }
    case "agentMessage": {
      if (typeof item.text !== "string") throw new AdapterError("runtime");
      if (item.phase === "partial_answer") throw new AdapterError("incomplete");
      if (item.phase !== undefined && item.phase !== null && item.phase !== "final_answer" && item.phase !== "commentary") throw new AdapterError("runtime");
      if ((item.delivery !== undefined && item.delivery !== null) || (item.memoryCitation !== undefined && item.memoryCitation !== null) || (item.questions !== undefined && item.questions !== null && (!Array.isArray(item.questions) || item.questions.length))) throw new AdapterError("context_unverified");
      return { type: "agentMessage", id: itemId, text: item.text, phase: item.phase ?? null };
    }
    case "contextCompaction": throw new AdapterError("incomplete");
    default: throw new AdapterError("context_unverified");
  }
}

export interface Turn { id: string; status: "inProgress" | "completed" | "interrupted" | "failed"; items: Item[]; error: CompletionFailure | null }
export function parseTurn(value: unknown): Turn {
  const turn = object(value);
  const turnId = id(turn.id);
  if (turn.status !== "inProgress" && turn.status !== "completed" && turn.status !== "interrupted" && turn.status !== "failed") throw new AdapterError("runtime");
  if (!Array.isArray(turn.items) || turn.items.length > 1024 || (turn.itemsView !== undefined && turn.itemsView !== "full" && turn.itemsView !== "summary" && !(turn.itemsView === "notLoaded" && turn.items.length === 0))) throw new AdapterError("incomplete");
  const error = turn.error === null || turn.error === undefined ? null : classifyErrorInfo(object(turn.error));
  return { id: turnId, status: turn.status, items: turn.items.map(parseItem), error };
}

export function parseUsage(value: unknown): TokenUsage {
  const usage = object(object(value).total);
  if (!Number.isSafeInteger(usage.inputTokens) || typeof usage.inputTokens !== "number" || usage.inputTokens < 0 ||
      !Number.isSafeInteger(usage.outputTokens) || typeof usage.outputTokens !== "number" || usage.outputTokens < 0) throw new AdapterError("runtime");
  return { inputTokens: usage.inputTokens, outputTokens: usage.outputTokens };
}

export function outputValidator(schema: Record<string, unknown>): (value: unknown) => value is Record<string, unknown> {
  try {
    const ajv = new Ajv({ strict: true, allowUnionTypes: true, validateFormats: true, allErrors: false, coerceTypes: false, useDefaults: false, removeAdditional: false });
    return ajv.compile<Record<string, unknown>>(schema);
  } catch { throw new AdapterError("runtime"); }
}

export function isExpectedRuntimeNotice(method: string, value: unknown, home: string): boolean {
  if (method !== "warning" && method !== "deprecationNotice" && method !== "remoteControl/status/changed") return false;
  const params = object(value);
  if (method === "remoteControl/status/changed") return params.status === "disabled";
  if (method === "deprecationNotice") return params.summary === "`[features].memory_tool` is deprecated. Use `[features].memories` instead."
    && params.details === "Enable it with `--enable memories` or `[features].memories` in config.toml. See https://developers.openai.com/codex/config-basic#feature-flags for details.";
  return params.message === "Under-development features enabled: skip_host_skill_discovery. Under-development features are incomplete and may behave unpredictably. To suppress this warning, set `suppress_unstable_features_warning = true` in " + join(home, "config.toml") + ".";
}
