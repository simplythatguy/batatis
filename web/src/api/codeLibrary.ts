/**
 * Code library and relevance routes (branch api/code-library). Typed by hand from the contract
 * until engine.schema.json is regenerated. Every failure is an EngineError with a plain `detail`
 * and the raw text in `technical`; 429 carries `retryAfter` seconds when the engine sends it.
 */
import { EngineError } from "./client";

export type Division = "A" | "B" | "C";

export interface TocArticle {
  id: string;
  title: string | null;
}

export interface TocSubsection {
  id: string;
  title: string | null;
  articles: TocArticle[];
}

export interface TocSection {
  id: string;
  title: string | null;
  subsections: TocSubsection[];
  articles: TocArticle[];
}

export interface TocPart {
  part: number;
  title: string | null;
  sections: TocSection[];
}

export interface CodeToc {
  division: Division;
  edition: string;
  parts: TocPart[];
}

export interface CodeTerm {
  code: string;
  title: string | null;
}

export interface CodeContext {
  id: string;
  level: string;
  title: string | null;
  citation: string | null;
  pdf_page: number | null;
  path: { id: string; level: string; title: string | null }[];
  objectives: CodeTerm[];
  functions: CodeTerm[];
  attribution_status: string | null;
  inherited_from: string | null;
  intent: { objective: string | null; text: string }[];
  intent_differs: boolean;
  intent_differs_detail: string | null;
  notes: { id: string; title: string | null; excerpt: string }[];
  references: string[];
  referenced_by: string[];
}

export interface RelevanceBands {
  x: number;
  y: number;
  status?: string;
}

export interface RelevanceResult {
  status: string;
  model: string | null;
  scored_at: string | null;
  description_sha256: string | null;
  stale: boolean;
  scores: Record<string, number>;
  rerank: Record<string, number>;
  /** What the rings show. */
  display: Record<string, number>;
  bands?: RelevanceBands | null;
}

export class CodeLibraryError extends EngineError {
  readonly retryAfter: number | null;
  constructor(status: number, detail: string, technical: string, retryAfter: number | null = null) {
    super(status, detail, technical);
    this.retryAfter = retryAfter;
  }
}

const BASE: string = import.meta.env?.VITE_ENGINE_URL ?? "/api";
const enc = encodeURIComponent;

/** Plain words for each failure the contract names. Raw text stays in `technical`. */
function plain(status: number, raw: string, path: string): string {
  if (status === 0) return "The code service did not respond.";
  if (status === 429) return "Too many requests right now. Try again in a moment.";
  if (status === 503) return /relevance/.test(path) ? "Relevance scoring is unavailable right now." : "The code library is unavailable right now.";
  if (status === 409 && /describe/i.test(raw)) return "Describe your project first. Scores are estimated from your description.";
  if (status === 404 && /relevance/.test(path)) return "Not scored yet.";
  if (status === 404 && /\/code\//.test(path)) return /provision not found/i.test(raw) ? "That provision was not found." : "The code library is not available on this server yet.";
  return raw || `Request failed (${status}).`;
}

async function call<T>(method: "GET" | "POST", path: string, signal?: AbortSignal, ms = 15000): Promise<T> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), ms);
  const onAbort = () => ctl.abort();
  if (signal?.aborted) ctl.abort();
  else signal?.addEventListener("abort", onAbort, { once: true });
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      method,
      signal: ctl.signal,
      headers: method === "POST" ? { "Content-Type": "application/json" } : undefined,
      body: method === "POST" ? "{}" : undefined,
    });
  } catch (e) {
    if (signal?.aborted) throw e;
    const timedOut = ctl.signal.aborted;
    throw new CodeLibraryError(0, timedOut ? "The code service did not answer in time." : plain(0, "", path), e instanceof Error ? e.message : String(e));
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onAbort);
  }
  if (!res.ok) {
    let raw = res.statusText;
    try {
      const j = await res.json();
      raw = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j);
    } catch {
      /* keep statusText */
    }
    const after = Number(res.headers.get("Retry-After"));
    throw new CodeLibraryError(res.status, plain(res.status, raw, path), `${res.status} ${raw}`, Number.isFinite(after) && after > 0 ? after : null);
  }
  return (await res.json()) as T;
}

export const codeLibrary = {
  toc: (division: Division = "B", signal?: AbortSignal) => call<CodeToc>("GET", `/code/toc?division=${division}`, signal),
  context: (id: string, division: Division = "B", signal?: AbortSignal) =>
    call<CodeContext>("GET", `/code/${enc(id)}/context?division=${division}`, signal),
  /** 404 "not scored" is a state, not an error: it resolves to null. */
  relevance: async (caseId: string, signal?: AbortSignal): Promise<RelevanceResult | null> => {
    try {
      return await call<RelevanceResult>("GET", `/cases/${enc(caseId)}/relevance`, signal);
    } catch (e) {
      if (e instanceof CodeLibraryError && e.status === 404 && /not scored/i.test(e.technical)) return null;
      throw e;
    }
  },
  /** Explicit user action only: it costs money and can take tens of seconds. */
  score: (caseId: string, signal?: AbortSignal) => call<RelevanceResult>("POST", `/cases/${enc(caseId)}/relevance`, signal, 180000),
};
