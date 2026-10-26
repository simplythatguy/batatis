import { request as httpsRequest } from "node:https";
import { rootCertificates } from "node:tls";
import Ajv from "ajv";
import type { KeyVault } from "./credentials";
import type { CompleteJsonRequest, CompleteJsonResult, KeyProviderId } from "./providers";

type ApiKeyId = Exclude<KeyProviderId, "batatis">;
const ENDPOINTS = {
  openai: "https://api.openai.com/v1/chat/completions",
  jev: "https://api.typesafe.ai/v1/systemone",
} satisfies Record<ApiKeyId, string>;
const LIMIT = 1_000_000;
export interface HttpReply { status: number; body: string }
export type ProviderPost = (id: ApiKeyId, key: string, body: string, signal: AbortSignal) => Promise<HttpReply>;

export const fixedProviderPost: ProviderPost = (id, key, body, signal) => httpsPost(ENDPOINTS[id], {
  Authorization: `Bearer ${key}`, ...(id === "jev" ? { "User-Agent": "hermes-jev-skills/0.1" } : {}),
}, body, signal);

/** Node HTTPS ignores proxy environment configuration. No redirects, retries or alternate origins. */
export const httpsPost = (url: string, headers: Record<string, string>, body: string, signal: AbortSignal): Promise<HttpReply> => new Promise((resolve, reject) => {
  const request = httpsRequest(url, {
    method: "POST", agent: false, signal, rejectUnauthorized: true, ca: [...rootCertificates],
    headers: { ...headers, "Content-Type": "application/json", Accept: "application/json", "Content-Length": Buffer.byteLength(body) },
  }, (response) => {
    const pieces: Buffer[] = [];
    let size = 0;
    response.on("data", (piece: Buffer) => {
      size += piece.length;
      if (size > LIMIT) { response.destroy(); request.destroy(new Error("response limit")); }
      else pieces.push(piece);
    });
    response.on("error", () => reject(new Error("provider response unavailable")));
    response.on("end", () => {
      try { resolve({ status: response.statusCode ?? 0, body: new TextDecoder("utf-8", { fatal: true }).decode(Buffer.concat(pieces)) }); }
      catch { reject(new Error("provider response unavailable")); }
    });
  });
  request.on("error", () => reject(new Error("provider connection unavailable")));
  request.end(body);
});

const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const count = (value: unknown): value is number => Number.isSafeInteger(value) && Number(value) >= 0;
const ajv = new Ajv({ strict: false, allErrors: false, validateFormats: false });

export function checkCompletion(request: CompleteJsonRequest, result: CompleteJsonResult): CompleteJsonResult {
  if (!result.ok) return result;
  if (result.model !== request.model || result.effort !== request.effort) {
    return { ok: false, reason: "model_unavailable", message: "A different model or effort answered; the answer was discarded." };
  }
  if (result.usage !== null && (!record(result.usage) || !count(result.usage.inputTokens) || !count(result.usage.outputTokens))) {
    return { ok: false, reason: "refused_or_invalid", message: "The reported usage was invalid." };
  }
  if (request.maxOutputTokens !== null && result.usage !== null && result.usage.outputTokens > request.maxOutputTokens) {
    return { ok: false, reason: "incomplete", message: "The answer exceeded this workflow’s output budget." };
  }
  try {
    if (!record(result.json) || !ajv.validate(request.schema, result.json)) throw new Error("schema");
  } catch {
    return { ok: false, reason: "refused_or_invalid", message: "The answer did not match the workflow’s schema." };
  }
  return result;
}

export class KeyProviders {
  #vault: KeyVault;
  #post: ProviderPost;
  constructor(vault: KeyVault, post: ProviderPost = fixedProviderPost) { this.#vault = vault; this.#post = post; }

  async complete(request: CompleteJsonRequest, signal: AbortSignal): Promise<CompleteJsonResult> {
    const body = JSON.stringify({ model: request.model, reasoning_effort: request.effort,
      ...(request.maxOutputTokens === null ? {} : { max_completion_tokens: request.maxOutputTokens }),
      messages: [{ role: "system", content: request.system }, { role: "user", content: request.user }],
      response_format: { type: "json_schema", json_schema: { name: request.task.replaceAll("-", "_"), strict: true, schema: request.schema } } });
    try {
      const reply = await this.#vault.use("openai", async (key) => {
        if (signal.aborted) return null;
        const response = await this.#post("openai", key, body, signal);
        if (response.body.includes(key)) throw new Error("credential in response");
        return response;
      });
      if (signal.aborted) return { ok: false, reason: "cancelled", message: "The work was cancelled." };
      if (!reply) return { ok: false, reason: "auth", message: "The selected key could not be opened. Add or replace it in Settings, and check OS secure storage." };
      if (reply.status !== 200) return { ok: false, reason: reply.status === 429 || reply.status === 402 ? "quota" : reply.status === 401 || reply.status === 403 ? "auth" : "runtime", message: "The selected API connection could not complete this request." };
      const data: unknown = JSON.parse(reply.body);
      if (!record(data) || data.model !== request.model) return { ok: false, reason: "model_unavailable", message: "The API returned a different model; the answer was discarded." };
      const choice: unknown = Array.isArray(data.choices) ? data.choices[0] : null;
      if (!record(choice) || choice.finish_reason !== "stop") return { ok: false, reason: "incomplete", message: "The API did not return a completed answer." };
      const message = choice.message;
      if (!record(message) || message.refusal || message.tool_calls || typeof message.content !== "string") throw new Error("answer");
      const json: unknown = JSON.parse(message.content);
      if (!record(json)) throw new Error("answer");
      const reported = data.usage;
      let usage = null;
      if (reported !== undefined && reported !== null) {
        if (!record(reported) || !count(reported.prompt_tokens) || !count(reported.completion_tokens)) throw new Error("usage");
        usage = { inputTokens: reported.prompt_tokens, outputTokens: reported.completion_tokens };
      }
      return checkCompletion(request, { ok: true, json, model: request.model, effort: request.effort, usage });
    } catch {
      return { ok: false, reason: signal.aborted ? "cancelled" : "refused_or_invalid", message: "The selected API connection returned no usable answer." };
    }
  }

  async screen(body: string, signal: AbortSignal): Promise<HttpReply | null> {
    return this.#vault.use("jev", async (key) => {
      if (signal.aborted) return null;
      const response = await this.#post("jev", key, body, signal);
      if (response.body.includes(key)) throw new Error("credential in response");
      return response.status === 200 ? response : { status: response.status, body: "{}" };
    });
  }
}
