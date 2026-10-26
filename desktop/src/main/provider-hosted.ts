/**
 * Batatis AI: the team's AI behind an access code. The desktop app sends one pinned workflow request
 * with the code to the Batatis website, which holds the keys and answers it (engine/routes_hosted_ai.py).
 * The code stays in the OS-protected vault and is sent only to that address.
 */
import type { KeyVault } from "./credentials";
import { httpsPost, type HttpReply } from "./provider-http";
import type { CompleteJsonRequest, CompleteJsonResult } from "./providers";

export const HOSTED_AI = "https://batatis-vert.vercel.app/api/hosted-ai";

export type HostedPost = (path: "complete" | "screen", code: string, body: string, signal: AbortSignal) => Promise<HttpReply>;

const fixedHostedPost: HostedPost = (path, code, body, signal) =>
  httpsPost(`${HOSTED_AI}/${path}`, { "X-Batatis-Access-Code": code }, body, signal);

const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const count = (value: unknown): value is number => Number.isSafeInteger(value) && Number(value) >= 0;

function failure(status: number): CompleteJsonResult {
  if (status === 403) return { ok: false, reason: "auth", message: "The Batatis access code isn’t valid. Replace it in Settings." };
  if (status === 429) return { ok: false, reason: "quota", message: "Batatis AI is busy. Try again in a few minutes." };
  if (status === 503) return { ok: false, reason: "unavailable", message: "Batatis AI is unavailable right now. Try again later." };
  return { ok: false, reason: "runtime", message: "Batatis AI could not complete this request." };
}

export class HostedAi {
  #vault: KeyVault;
  #post: HostedPost;
  constructor(vault: KeyVault, post: HostedPost = fixedHostedPost) { this.#vault = vault; this.#post = post; }

  async complete(request: CompleteJsonRequest, signal: AbortSignal): Promise<CompleteJsonResult> {
    const body = JSON.stringify({ task: request.task, system: request.system, user: request.user, schema: request.schema,
      model: request.model, effort: request.effort, maxOutputTokens: request.maxOutputTokens });
    try {
      const reply = await this.#vault.use("batatis", async (code) => (signal.aborted ? null : this.#post("complete", code, body, signal)));
      if (signal.aborted) return { ok: false, reason: "cancelled", message: "The work was cancelled." };
      if (!reply) return { ok: false, reason: "auth", message: "Add your Batatis access code in Settings." };
      if (reply.status !== 200) return failure(reply.status);
      const data: unknown = JSON.parse(reply.body);
      if (!record(data) || !record(data.json) || data.model !== request.model || data.effort !== request.effort) throw new Error("answer");
      const usage = record(data.usage) && count(data.usage.inputTokens) && count(data.usage.outputTokens)
        ? { inputTokens: data.usage.inputTokens, outputTokens: data.usage.outputTokens } : null;
      return { ok: true, json: data.json, model: request.model, effort: request.effort, usage };
    } catch {
      return { ok: false, reason: signal.aborted ? "cancelled" : "refused_or_invalid", message: "Batatis AI returned no usable answer." };
    }
  }

  /** Optional screening on the team's key, in the same reply shape as a screening key's. */
  async screen(body: string, signal: AbortSignal): Promise<HttpReply | null> {
    return this.#vault.use("batatis", async (code) => {
      if (signal.aborted) return null;
      const reply = await this.#post("screen", code, JSON.stringify({ body }), signal);
      if (reply.status !== 200) return { status: reply.status, body: "{}" };
      const data: unknown = JSON.parse(reply.body);
      return record(data) && typeof data.status === "number" && typeof data.body === "string" ? { status: data.status, body: data.body } : null;
    });
  }
}
