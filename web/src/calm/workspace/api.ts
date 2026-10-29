import { call } from "../../api/accounts";
import { EngineError } from "../../api/client";
import { acknowledgeWrite } from "../../api/sync";
import type { HistoryEntry } from "./history";
import type { RewriteResult } from "./suggestions";

export type SignerRole = "owner" | "owner_rep";
export interface Signer { role: SignerRole; name: string; required: boolean }
export interface Signature { role: SignerRole; name: string; signed_on: string; method: "drawn" | "typed"; image: string; current: boolean }
export interface Consent { agreed: boolean; at: string | null }
export interface WorkspaceRecord { content_hash: string; signers: Signer[]; signatures: Signature[]; consent: Consent | null; history: HistoryEntry[] }
export interface PreviewPage { width: number; height: number; image: string }
export interface PackagePreview { filename: string; page_count: number; start: number; pages: PreviewPage[]; pdf?: string }

const invalid = (): never => { throw new EngineError(502, "The server returned an unreadable workspace. Try again."); };
function isRecord(value: unknown): value is Record<string, unknown> { return value !== null && typeof value === "object" && !Array.isArray(value); }
function object(value: unknown): Record<string, unknown> { return isRecord(value) ? value : invalid(); }
function string(value: unknown): string { return typeof value === "string" ? value : invalid(); }
function bool(value: unknown): boolean { return typeof value === "boolean" ? value : invalid(); }
function list(value: unknown): unknown[] { return Array.isArray(value) ? value : invalid(); }
function role(value: unknown): SignerRole { return value === "owner" || value === "owner_rep" ? value : invalid(); }
function method(value: unknown): Signature["method"] { return value === "drawn" || value === "typed" ? value : invalid(); }
function consent(value: unknown): Consent { const c = object(value); return { agreed: bool(c.agreed), at: c.at === null ? null : string(c.at) }; }
function history(value: unknown): HistoryEntry {
  const e = object(value);
  const by = e.by === "you" || e.by === "ai" || e.by === "restore" ? e.by : invalid();
  return { id: string(e.id), at: string(e.at), block: string(e.block), label: string(e.label), before: string(e.before), after: string(e.after), by };
}
export function parseWorkspace(value: unknown): WorkspaceRecord {
  const w = object(value);
  return { content_hash: string(w.content_hash),
    signers: list(w.signers).map(v => { const s = object(v); return { role: role(s.role), name: string(s.name), required: bool(s.required) }; }),
    signatures: list(w.signatures).map(v => { const s = object(v), image = string(s.image); if (!image.startsWith("data:image/png;base64,")) invalid();
      return { role: role(s.role), name: string(s.name), signed_on: string(s.signed_on), method: method(s.method), image, current: bool(s.current) }; }),
    consent: w.consent === null ? null : consent(w.consent), history: list(w.history).map(history),
  };
}
export function parsePreview(value: unknown): PackagePreview {
  const p = object(value);
  const count = p.page_count, start = p.start;
  if (typeof count !== "number" || !Number.isInteger(count) || count < 1 || typeof start !== "number" || !Number.isInteger(start) || start < 0) return invalid();
  return { filename: string(p.filename), page_count: count, start, pages: list(p.pages).map(v => {
    const page = object(v), width = page.width, height = page.height, image = string(page.image);
    if (typeof width !== "number" || !Number.isFinite(width) || width <= 0 || typeof height !== "number" || !Number.isFinite(height) || height <= 0 || !/^data:image\/(?:png|jpeg);base64,/.test(image)) return invalid();
    return { width, height, image };
  }), ...(typeof p.pdf === "string" && p.pdf.startsWith("data:application/pdf;base64,") ? { pdf: p.pdf } : {}) };
}
const base = (id: string) => `/cases/${encodeURIComponent(id)}`;
/** Workspace writes move the case version. Record it, or the next draft save, Section D read or submit
 * sends the old version and reads as a conflict with another device. Callers run these in the save queue. */
function committed<T>(id: string, value: T): T {
  acknowledgeWrite(id, isRecord(value) ? value.case_version : undefined);
  return value;
}
export const workspaceApi = {
  get: async (id: string, signal?: AbortSignal) => parseWorkspace(await call<unknown>("GET", `${base(id)}/workspace`, undefined, signal)),
  sign: async (id: string, signer: SignerRole, body: { name: string; method: Signature["method"]; image: string }, signal?: AbortSignal) =>
    committed(id, await call<unknown>("PUT", `${base(id)}/signatures/${signer}`, body, signal)),
  remove: async (id: string, signer: SignerRole, signal?: AbortSignal) => committed(id, await call<unknown>("DELETE", `${base(id)}/signatures/${signer}`, undefined, signal)),
  consent: async (id: string, agreed: boolean, signal?: AbortSignal) => consent(committed(id, await call<unknown>("PUT", `${base(id)}/consent`, { agreed }, signal))),
  history: async (id: string, entries: HistoryEntry[], signal?: AbortSignal) => committed(id, await call<unknown>("POST", `${base(id)}/history`, { entries }, signal)),
  rewrite: async (id: string, body: { field: string; text: string; start: number; end: number; instruction: string }, signal?: AbortSignal): Promise<RewriteResult> => {
    const r = object(await call<unknown>("POST", `${base(id)}/rewrite`, body, signal, 60000));
    return { replacement: string(r.replacement), cited: list(r.cited).map(string), removed_citations: list(r.removed_citations).map(string), notice: r.notice === null ? null : string(r.notice) };
  },
  preview: async (id: string, start: number, count: number, official: boolean, signal?: AbortSignal) =>
    parsePreview(await call<unknown>("GET", `${base(id)}/export/preview?start=${start}&count=${count}&official=${official}`, undefined, signal, 60000)),
};
export function workspaceFailure(error: unknown, feature: "Signing" | "History" | "Rewriting" | "Package preview"): string {
  if (error instanceof EngineError && [404, 405, 501].includes(error.status)) return `${feature} isn’t available on this server.`;
  if (error instanceof EngineError && error.status === 503 && feature === "Rewriting") return "AI rewriting isn’t available right now.";
  if (error instanceof EngineError && (error.status === 0 || error.status >= 500)) return `${feature} couldn’t finish. Try again.`;
  return error instanceof EngineError ? error.detail : `${feature} couldn’t finish. Try again.`;
}
