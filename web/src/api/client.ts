/**
 * Typed client for the engine HTTP API (engine/api.py). The app calls `/api/...` unless
 * `VITE_API_BASE` or `VITE_ENGINE_URL` is set, in which case it calls that origin.
 * `VITE_API_BASE` wins; the default is `/api`. In development, Vite proxies `/api` to
 * `VITE_ENGINE_URL`, or http://127.0.0.1:8000 when that is unset (vite.config.ts).
 * `createEngine(base)` serves scripts and tests outside Vite.
 */
import type { Case, FactInput, Gap, NewCase, SectionCRow } from "./types.gen";

/** A provision returned by GET /code/search (engine/codes.py `Codes.search`). */
export interface CodeHit {
  id: string;
  division: "A" | "B" | "C";
  level: string;
  article_title: string | null;
  title: string | null;
  text: string;
  citation: string | null;
}

/** GET /code/{id}: the codedb lookup record. Only the fields the web reads are typed. */
export interface CodeRecord {
  id: string;
  division: "A" | "B" | "C";
  level: string;
  part: number;
  article_title: string | null;
  title: string | null;
  text: string;
  citation: string;
  pdf_page: number;
  children: { id: string; level: string; text: string }[];
  [key: string]: unknown;
}

type Division = "A" | "B" | "C";

/** GET /cases/{id}/process-fields. The engine list is wrapped as `{ items, meta }`. */
export interface ProcessField {
  id: string;
  label: string;
  prompt: string;
  citation: string;
  required: true;
  answer: { value: string } | null;
}

/** GET /cases/{id}/section-d/issues. The engine list is wrapped as `{ items, meta }`. */
export interface SectionDIssue {
  id: string;
  question: string | null;
  at_stake: string;
  status: string;
}

/** JSON array routes are `{ items, meta }`. Objects that also carry other fields are not envelopes. */
export interface ItemEnvelope<T> {
  items: T[];
  meta?: { notice: string };
}

export function unwrapItems<T>(body: T[] | ItemEnvelope<T>): T[] {
  return Array.isArray(body) ? body : body.items;
}

/** Every engine route whose JSON body is a list. Middleware wraps each one as `{ items, meta }`. */
export const ARRAY_ROUTES = [
  { name: "search", method: "GET", path: "/code/search" },
  { name: "sectionC", method: "POST", path: "/section-c" },
  { name: "gaps", method: "GET", path: "/cases/{caseId}/gaps" },
  { name: "processFields", method: "GET", path: "/cases/{caseId}/process-fields" },
  { name: "sectionDIssues", method: "GET", path: "/cases/{caseId}/section-d/issues" },
] as const;

/** status 0 = the engine could not be reached. */
export class EngineError extends Error {
  readonly status: number;
  readonly detail: string;
  constructor(status: number, detail: string) {
    super(status ? `Engine ${status}: ${detail}` : `Engine unreachable: ${detail}`);
    this.status = status;
    this.detail = detail;
  }
}

const enc = encodeURIComponent;

export function createEngine(base: string) {
  async function call<T>(method: "GET" | "POST", path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
    let res: Response;
    try {
      res = await fetch(`${base}${path}`, {
        method,
        signal,
        headers: body === undefined ? undefined : { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch (e) {
      if (signal?.aborted) throw e;
      throw new EngineError(0, e instanceof Error ? e.message : String(e));
    }
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const j = await res.json();
        detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j);
      } catch {
        /* keep statusText */
      }
      throw new EngineError(res.status, detail);
    }
    return (await res.json()) as T;
  }

  return {
    createCase: (body: NewCase = {}, signal?: AbortSignal) => call<Case>("POST", "/cases", body, signal),
    getCase: (id: string, signal?: AbortSignal) => call<Case>("GET", `/cases/${enc(id)}`, undefined, signal),
    addFact: (caseId: string, fact: FactInput, signal?: AbortSignal) =>
      call<Case>("POST", `/cases/${enc(caseId)}/facts`, fact, signal),
    provision: (id: string, division?: Division, signal?: AbortSignal) =>
      call<CodeRecord>("GET", `/code/${enc(id)}${division ? `?division=${division}` : ""}`, undefined, signal),
    search: (q: string, opts: { division?: Division; limit?: number } = {}, signal?: AbortSignal) => {
      const p = new URLSearchParams({ q, division: opts.division ?? "B", limit: String(opts.limit ?? 20) });
      return call<CodeHit[] | ItemEnvelope<CodeHit>>("GET", `/code/search?${p}`, undefined, signal).then(unwrapItems);
    },
    /** Section C rows by deterministic lookup, in input order (an article expands to its sentences). */
    sectionC: (provisions: string[], signal?: AbortSignal) =>
      call<SectionCRow[] | ItemEnvelope<SectionCRow>>("POST", "/section-c", { provisions }, signal).then(unwrapItems),
    gaps: (caseId: string, signal?: AbortSignal) =>
      call<Gap[] | ItemEnvelope<Gap>>("GET", `/cases/${enc(caseId)}/gaps`, undefined, signal).then(unwrapItems),
    processFields: (caseId: string, signal?: AbortSignal) =>
      call<ProcessField[] | ItemEnvelope<ProcessField>>(
        "GET",
        `/cases/${enc(caseId)}/process-fields`,
        undefined,
        signal,
      ).then(unwrapItems),
    sectionDIssues: (caseId: string, signal?: AbortSignal) =>
      call<SectionDIssue[] | ItemEnvelope<SectionDIssue>>(
        "GET",
        `/cases/${enc(caseId)}/section-d/issues`,
        undefined,
        signal,
      ).then(unwrapItems),
  };
}

export type Engine = ReturnType<typeof createEngine>;

const env = import.meta.env ?? {};
const apiBase = env.VITE_API_BASE || env.VITE_ENGINE_URL || "/api";
export const engine: Engine = createEngine(apiBase);
