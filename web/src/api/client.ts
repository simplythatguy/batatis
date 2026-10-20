/**
 * Typed client for the engine HTTP API (engine/api.py). The app calls `/api/...`; in development
 * Vite proxies `/api` to the engine at http://127.0.0.1:8000 (vite.config.ts). Set VITE_ENGINE_URL
 * to call another engine directly. `createEngine(base)` serves scripts and tests outside Vite.
 */
import type { Case, FactInput, NewCase, SectionCRow } from "./types.gen";

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
  async function call<T>(method: "GET" | "POST", path: string, body?: unknown, signal?: AbortSignal, ms = ENGINE_WAIT_MS): Promise<T> {
    const timed = withTimeout(signal, ms);
    let res: Response;
    try {
      res = await fetch(`${base}${path}`, {
        method,
        signal: timed.signal,
        headers: body === undefined ? undefined : { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch (e) {
      if (signal?.aborted) throw e;
      if (timed.timedOut()) throw new EngineError(0, "The engine did not answer in time.");
      throw new EngineError(0, e instanceof Error ? e.message : String(e));
    } finally {
      timed.clear();
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
      return call<CodeHit[]>("GET", `/code/search?${p}`, undefined, signal);
    },
    /** Section C rows by deterministic lookup, in input order (an article expands to its sentences). */
    sectionC: (provisions: string[], signal?: AbortSignal) =>
      call<SectionCRow[]>("POST", "/section-c", { provisions }, signal),
    /** Administrative gaps. Mounted in engine/routes_case.py, not POST /completeness. */
    gaps: (caseId: string, signal?: AbortSignal) =>
      call<EngineGap[]>("GET", `/cases/${enc(caseId)}/gaps`, undefined, signal),
    processFields: (caseId: string, signal?: AbortSignal) =>
      call<EngineProcessField[]>("GET", `/cases/${enc(caseId)}/process-fields`, undefined, signal),
    professional: (caseId: string, signal?: AbortSignal) =>
      call<ProfessionalResult>("GET", `/cases/${enc(caseId)}/professional`, undefined, signal),
    /** Persists confirmed provisions, re-looks up Section C, and returns the Section D plan. */
    sectionD: (caseId: string, provisions?: string[], signal?: AbortSignal) =>
      call<SectionDPlan>("POST", `/cases/${enc(caseId)}/section-d`, provisions ? { provisions } : {}, signal),
    /**
     * Official SCC PDF. 200 is bytes. 409 lists blocking reasons. 503 means the blank form file is missing.
     * TODO(engine): identify is CLI-only (engine/cli_sut.py). There is no rank route to call.
     * TODO(engine): no file-upload route. PDF names stay in the browser.
     * TODO(engine): no route updates jurisdiction after POST /cases.
     */
    exportPdf: (caseId: string, draft = false, signal?: AbortSignal) => exportPdf(base, caseId, draft, signal),
    /**
     * There is no file route. The call still goes out so a missing engine fails fast
     * instead of leaving the row on "Waiting for the engine".
     */
    upload: (caseId: string, name: string, signal?: AbortSignal) =>
      call<{ name: string }>("POST", `/cases/${enc(caseId)}/files`, { name }, signal),
  };
}

export interface EngineGap {
  id: string;
  section: "A" | "B" | "C" | "D" | "process";
  field: string;
  message: string;
  severity: "blocking" | "warning";
  fix_hint?: string;
  citation?: string | null;
}

export interface EngineProcessField {
  id: string;
  label: string;
  prompt: string;
  reviewer_looks_for: string[];
  citation: string;
  required: true;
  answer: { value: string } | null;
}

export interface ProfessionalResult {
  required: "yes" | "no" | "depends";
  general_required: "yes" | "no" | "depends";
  reasons: { code: string; required: "yes" | "no" | "depends"; message: string; citation: string }[];
  questions: string[];
  scope_note: string;
}

export interface SectionDPlan {
  items: {
    id: string;
    provision_id: string;
    citation: string;
    status: string;
    objective: string | null;
    function: string | null;
    performance_issue: string;
    recommended_types: string[];
  }[];
  notices: string[];
}

export class ExportBlockedError extends EngineError {
  readonly reasons: string[];
  constructor(reasons: string[], detail: string) {
    super(409, detail);
    this.reasons = reasons;
  }
}

/** Bound so a slow engine cannot leave the screen on "waiting". */
const ENGINE_WAIT_MS = 8000;

function withTimeout(parent: AbortSignal | undefined, ms: number) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), ms);
  if (parent?.aborted) ctl.abort();
  else parent?.addEventListener("abort", () => ctl.abort(), { once: true });
  return { signal: ctl.signal, clear: () => clearTimeout(timer), timedOut: () => ctl.signal.aborted && !parent?.aborted };
}

async function exportPdf(base: string, caseId: string, draft: boolean, signal?: AbortSignal) {
  const timed = withTimeout(signal, 20000);
  let res: Response;
  try {
    res = await fetch(`${base}/cases/${enc(caseId)}/export`, {
      method: "POST",
      signal: timed.signal,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ draft }),
    });
  } catch (e) {
    if (signal?.aborted) throw e;
    if (timed.timedOut()) throw new EngineError(0, "The engine did not answer in time.");
    throw new EngineError(0, e instanceof Error ? e.message : String(e));
  } finally {
    timed.clear();
  }
  if (!res.ok) {
    let detail = res.statusText;
    let reasons: string[] = [];
    try {
      const j = await res.json();
      const raw = j.detail ?? j;
      if (raw && typeof raw === "object" && Array.isArray(raw.reasons)) {
        reasons = raw.reasons.map(String);
        detail = String(raw.message ?? "export blocked");
      } else {
        detail = typeof raw === "string" ? raw : JSON.stringify(raw);
      }
    } catch {
      /* keep statusText */
    }
    if (res.status === 409) throw new ExportBlockedError(reasons, detail);
    throw new EngineError(res.status, detail);
  }
  const blob = await res.blob();
  const match = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") ?? "");
  return { blob, filename: match?.[1] ?? `${caseId}-scc-variance.pdf` };
}

export function failureText(e: unknown): string {
  if (e instanceof EngineError) {
    if (e.status === 0) return e.detail;
    if (e.status === 404) return "The engine has no route for this request.";
    return e.message;
  }
  return "The engine could not be reached.";
}

export type Engine = ReturnType<typeof createEngine>;

export const engine: Engine = createEngine(import.meta.env?.VITE_ENGINE_URL ?? "/api");
