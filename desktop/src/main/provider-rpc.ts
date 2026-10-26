import { randomUUID } from "node:crypto";
import type { CallReply, HostCall } from "./engine";
import { record } from "./provider-dispatch";

const CHUNK = 24_000;
const LIMIT = 4_000_000;
type Transfer = { lease: string; expires: number; body: string; operation: string; output: boolean };

/** Chunk large document requests/answers within the frozen bridge's 64 KiB header limit. */
export class ProviderRpc {
  #transfers = new Map<string, Transfer>();
  #dispatch: HostCall;
  #valid: (lease: unknown) => boolean;
  constructor(dispatch: HostCall, valid: (lease: unknown) => boolean) { this.#dispatch = dispatch; this.#valid = valid; }
  clear() { this.#transfers.clear(); }
  readonly call: HostCall = async (op, args, signal) => {
    for (const [id, transfer] of this.#transfers) if (transfer.expires < Date.now()) this.#transfers.delete(id);
    const failure: CallReply = { ok: false, reason: "cancelled", message: "The request transfer expired or the AI selection changed." };
    if (!record(args) || signal.aborted) return failure;
    if (op === "provider.transfer.begin") {
      if (!this.#valid(args.lease) || typeof args.lease !== "string" || this.#transfers.size >= 32
        || (args.operation !== "provider.completeJson" && args.operation !== "provider.jev")) return failure;
      const id = randomUUID();
      this.#transfers.set(id, { lease: args.lease, expires: Date.now() + 180_000, body: "", operation: args.operation, output: false });
      return { ok: true, value: { id } };
    }
    if (op.startsWith("provider.transfer.")) {
      const id = typeof args.id === "string" ? args.id : "";
      const transfer = this.#transfers.get(id);
      if (!transfer || transfer.lease !== args.lease || !this.#valid(args.lease)) return failure;
      if (op === "provider.transfer.chunk" && !transfer.output && typeof args.chunk === "string"
        && args.chunk.length <= CHUNK && transfer.body.length + args.chunk.length <= LIMIT) {
        transfer.body += args.chunk;
        return { ok: true, value: {} };
      }
      if (op === "provider.transfer.read" && transfer.output && Number.isInteger(args.offset) && Number(args.offset) >= 0) {
        const offset = Number(args.offset);
        const chunk = transfer.body.slice(offset, offset + CHUNK);
        const more = offset + CHUNK < transfer.body.length;
        if (!more) this.#transfers.delete(id);
        return { ok: true, value: { chunk, more } };
      }
      if (op !== "provider.transfer.finish" || transfer.output) return failure;
      this.#transfers.delete(id);
      try {
        const decoded: unknown = JSON.parse(Buffer.from(transfer.body, "base64").toString("utf8"));
        if (!record(decoded) || decoded.lease !== args.lease) return failure;
        return this.#answer(await this.#dispatch(transfer.operation, decoded, signal), transfer.lease);
      } catch { return failure; }
    }
    const reply = await this.#dispatch(op, args, signal);
    return this.#answer(reply, typeof args.lease === "string" ? args.lease : "");
  };

  #answer(reply: CallReply, lease: string): CallReply {
    const body = Buffer.from(JSON.stringify(reply)).toString("base64");
    if (body.length <= CHUNK) return reply;
    if (!this.#valid(lease) || body.length > LIMIT || this.#transfers.size >= 32) return { ok: false, reason: "refused_or_invalid", message: "The answer exceeded the private bridge’s limit." };
    const id = randomUUID();
    this.#transfers.set(id, { lease, expires: Date.now() + 180_000, body, operation: "", output: true });
    return { ok: true, value: { transfer: id } };
  }
}
