/**
 * Typed client for the engine HTTP API (engine/api.py). The app calls `/api/...`; in development
 * Vite proxies `/api` to the engine at http://127.0.0.1:8000 (vite.config.ts). Set VITE_ENGINE_URL
 * to call another engine directly. `createEngine(base)` serves scripts and tests outside Vite.
 */
import { failureKind, publicDetail, takeSseEvents } from "../rules";
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
  async function call<T>(method: "GET" | "POST" | "PUT", path: string, body?: unknown, signal?: AbortSignal, ms = ENGINE_WAIT_MS): Promise<T> {
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
      throw new EngineError(res.status, publicDetail(res.status, detail));
    }
    return (await res.json()) as T;
  }

  return {
    createCase: (body: NewCase = {}, signal?: AbortSignal) => call<Case>("POST", "/cases", body, signal),
    /**
     * PUT /cases/{id}/jurisdiction from backend/case-api. Body is the Jurisdiction model.
     * Today's dev returns 404. The caller keeps the case working when that happens.
     */
    setJurisdiction: (caseId: string, jurisdiction: { id: string; name: string; authority: null }, signal?: AbortSignal) =>
      call<Case>("PUT", `/cases/${enc(caseId)}/jurisdiction`, jurisdiction, signal),
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
    /** Administrative gaps. Mounted in engine/routes_case.py. */
    gaps: (caseId: string, signal?: AbortSignal) =>
      call<EngineGap[]>("GET", `/cases/${enc(caseId)}/gaps`, undefined, signal),
    /**
     * POST /cases/{id}/completeness from PR #11. Body is empty until that route
     * accepts documents. 404 on today's dev. The caller shows an empty state.
     */
    completeness: (caseId: string, signal?: AbortSignal) =>
      call<CompletenessReport>("POST", `/cases/${enc(caseId)}/completeness`, {}, signal),
    processFields: (caseId: string, signal?: AbortSignal) =>
      call<EngineProcessField[]>("GET", `/cases/${enc(caseId)}/process-fields`, undefined, signal),
    professional: (caseId: string, signal?: AbortSignal) =>
      call<ProfessionalResult>("GET", `/cases/${enc(caseId)}/professional`, undefined, signal),
    /** Persists confirmed provisions, re-looks up Section C, and returns the Section D plan on today's dev. */
    sectionD: (caseId: string, provisions?: string[], signal?: AbortSignal) =>
      call<SectionDPlan>("POST", `/cases/${enc(caseId)}/section-d`, provisions ? { provisions } : {}, signal),
    /** GET /cases/{id}/section-d/issues. A missing code database is a fixed 503, not a missing route. */
    sectionDIssues: (caseId: string, signal?: AbortSignal) =>
      call<SectionDIssue[]>("GET", `/cases/${enc(caseId)}/section-d/issues`, undefined, signal),
    /**
     * Official SCC PDF. 200 is bytes. 409 lists blocking reasons.
     * A missing code database is not turned into a 503 on this branch.
     */
    exportPdf: (caseId: string, draft = false, signal?: AbortSignal) => exportPdf(base, caseId, draft, signal),
    /**
     * Multipart PDF upload (FormData field `file`). Not served on today's dev.
     * When backend/case-api lands, this sends the PDF bytes and reads {id, name, pages, sha256, read}.
     */
    upload: (caseId: string, file: File, signal?: AbortSignal) => uploadPdf(base, caseId, file, signal),
    /**
     * POST /cases/{id}/identify with Accept: text/event-stream, from PR #12.
     * 404 on today's dev. The caller keeps the description cards.
     */
    /**
     * POST /cases/{id}/identify. When that route is missing and there are no answers,
     * GET /cases/{id}/identify/stream is tried once.
     */
    identify: (caseId: string, prose: string, answers: { field?: string | null; question_id?: string | null; answer: string }[] = [], signal?: AbortSignal, onStage?: (stage: string) => void) =>
      rankCase(base, caseId, prose, answers, signal, onStage),
    /** GET /cases/{id}/identify. 404 detail `identify result not found` when nothing is stored. */
    storedIdentify: (caseId: string, signal?: AbortSignal) =>
      call<IdentifyResult>("GET", `/cases/${enc(caseId)}/identify`, undefined, signal),
    /** GET /cases/{id}/identify/stream?prose= */
    identifyStream: (caseId: string, prose: string, signal?: AbortSignal, onStage?: (stage: string) => void) =>
      identifyStream(base, caseId, prose, signal, onStage),
    /**
     * POST /cases/{id}/identify/{provision}/decision.
     * Body is yes, no, or not_sure. The body may be a SectionCRow or the stored identify payload.
     */
    decide: (caseId: string, provisionId: string, decision: "yes" | "no" | "not_sure", signal?: AbortSignal) =>
      call<unknown>("POST", `/cases/${enc(caseId)}/identify/${enc(provisionId)}/decision`, { decision }, signal),
    /** GET /cases/{id}/information-request. Items are not_sure decisions. */
    informationRequest: (caseId: string, signal?: AbortSignal) =>
      call<InformationRequest>("GET", `/cases/${enc(caseId)}/information-request`, undefined, signal),
    /** POST /cases/{id}/identify/confirm. Writes provisions after a code-database check. */
    confirmIdentify: (caseId: string, provisions: string[], signal?: AbortSignal) =>
      call<Case>("POST", `/cases/${enc(caseId)}/identify/confirm`, { provisions }, signal),
  };
}

/** Fields that exist on PR #11 CompletenessResponse. Extra keys are ignored. */
export interface CompletenessReport {
  notice?: string;
  reviews?: {
    export_reasons?: unknown;
    sections?: {
      elements?: {
        label?: unknown;
        reason?: unknown;
        lookup_skipped?: unknown;
      }[];
    }[];
  }[];
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

/** One issue from GET /cases/{id}/section-d/issues (PR #8). */
export interface SectionDIssue {
  id: string;
  provision: { provision_id: string; division: "A" | "B" | "C"; citation: string } | null;
  entered_reference: string | null;
  question: string | null;
  objective: string | null;
  function: string | null;
  at_stake: string;
  recommended_types: string[];
  practice_of_engineering: {
    value: boolean | "unknown";
    rule: string | null;
    division: "A" | "B" | "C" | null;
    citation: string | null;
    reason: string;
    question: string | null;
  };
  empty_process_fields: { id: string; label: string; citation: string }[];
  status: "open" | "addressed" | "evidence_listed" | "needs_professional";
}

export interface IdentifyArticle {
  provision: string;
  provision_id?: string | null;
  division?: string;
  title: string | null;
  part?: number;
  quote?: string | null;
  snippet?: string | null;
  reason?: string | null;
  why?: string | null;
  citation?: string | null;
  /** Ranking hint. Not an acceptance. */
  status?: "suggested" | "candidate" | "unknown" | string;
  decision?: "yes" | "no" | "not_sure" | null;
  open_question_id?: string | null;
}

export interface IdentifyResult {
  mode?: "live" | "cached_demo" | "bm25_fallback" | string | null;
  cached?: boolean;
  source?: string | null;
  articles: IdentifyArticle[];
  section_c?: SectionCRow[];
  questions?: string[];
  open_questions?: { id?: string; field?: string; text?: string; why?: string; status?: string }[];
  persisted?: boolean;
}

export interface InformationRequest {
  case_id: string;
  items: { id: string; provision_id: string; text: string }[];
}

export interface UploadedFile {
  id: string;
  name: string;
  pages: number;
  sha256: string;
  read: boolean;
}

export interface SectionDPlan {
  items: {
    id: string;
    provision_id: string;
    citation: string;
    status: "not provided" | "provided" | "evidence_listed";
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
    throw new EngineError(res.status, publicDetail(res.status, detail));
  }
  const blob = await res.blob();
  const match = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") ?? "");
  return { blob, filename: match?.[1] ?? `${caseId}-scc-variance.pdf` };
}

async function readError(res: Response): Promise<string> {
  let detail = res.statusText;
  try {
    const j = await res.json();
    detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j);
  } catch {
    /* keep statusText */
  }
  return publicDetail(res.status, detail);
}

async function uploadPdf(base: string, caseId: string, file: File, signal?: AbortSignal): Promise<UploadedFile> {
  const timed = withTimeout(signal, ENGINE_WAIT_MS);
  const body = new FormData();
  body.append("file", file, file.name);
  let res: Response;
  try {
    res = await fetch(`${base}/cases/${enc(caseId)}/files`, { method: "POST", body, signal: timed.signal });
  } catch (e) {
    if (signal?.aborted) throw e;
    if (timed.timedOut()) throw new EngineError(0, "The engine did not answer in time.");
    throw new EngineError(0, e instanceof Error ? e.message : String(e));
  } finally {
    timed.clear();
  }
  if (!res.ok) throw new EngineError(res.status, await readError(res));
  return (await res.json()) as UploadedFile;
}

async function readIdentifyResponse(res: Response, onStage?: (stage: string) => void): Promise<IdentifyResult> {
  if (!res.ok) throw new EngineError(res.status, await readError(res));
  const type = res.headers.get("content-type") ?? "";
  if (!type.includes("text/event-stream")) return (await res.json()) as IdentifyResult;
  const reader = res.body?.getReader();
  if (!reader) throw new EngineError(0, "The engine did not answer.");
  const dec = new TextDecoder();
  let buf = "";
  let donePayload: IdentifyResult | null = null;
  while (true) {
    const step = await reader.read();
    if (step.done) break;
    buf += dec.decode(step.value, { stream: true });
    const parsed = takeSseEvents(buf);
    buf = parsed.rest;
    for (const ev of parsed.events) {
      onStage?.(ev.event);
      if (ev.event === "error") throw new EngineError(503, "Article ranking failed.");
      if (ev.event === "done") {
        try {
          donePayload = JSON.parse(ev.data) as IdentifyResult;
        } catch {
          donePayload = null;
        }
      }
    }
  }
  if (!donePayload) throw new EngineError(0, "Article ranking did not finish.");
  return donePayload;
}

async function identifyCase(
  base: string,
  caseId: string,
  prose: string,
  answers: { field?: string | null; question_id?: string | null; answer: string }[],
  signal?: AbortSignal,
  onStage?: (stage: string) => void,
): Promise<IdentifyResult> {
  const timed = withTimeout(signal, 25000);
  let res: Response;
  try {
    res = await fetch(`${base}/cases/${enc(caseId)}/identify`, {
      method: "POST",
      signal: timed.signal,
      headers: { Accept: "text/event-stream", "Content-Type": "application/json" },
      body: JSON.stringify({ prose, answers }),
    });
  } catch (e) {
    if (signal?.aborted) throw e;
    if (timed.timedOut()) throw new EngineError(0, "The engine did not answer in time.");
    throw new EngineError(0, e instanceof Error ? e.message : String(e));
  } finally {
    timed.clear();
  }
  return readIdentifyResponse(res, onStage);
}

async function identifyStream(
  base: string,
  caseId: string,
  prose: string,
  signal?: AbortSignal,
  onStage?: (stage: string) => void,
): Promise<IdentifyResult> {
  const timed = withTimeout(signal, 25000);
  const q = new URLSearchParams({ prose });
  let res: Response;
  try {
    res = await fetch(`${base}/cases/${enc(caseId)}/identify/stream?${q}`, {
      method: "GET",
      signal: timed.signal,
      headers: { Accept: "text/event-stream" },
    });
  } catch (e) {
    if (signal?.aborted) throw e;
    if (timed.timedOut()) throw new EngineError(0, "The engine did not answer in time.");
    throw new EngineError(0, e instanceof Error ? e.message : String(e));
  } finally {
    timed.clear();
  }
  return readIdentifyResponse(res, onStage);
}

async function rankCase(
  base: string,
  caseId: string,
  prose: string,
  answers: { field?: string | null; question_id?: string | null; answer: string }[],
  signal?: AbortSignal,
  onStage?: (stage: string) => void,
): Promise<IdentifyResult> {
  try {
    return await identifyCase(base, caseId, prose, answers, signal, onStage);
  } catch (e) {
    if (signal?.aborted) throw e;
    if (e instanceof EngineError && failureKind(e.status, e.detail) === "missing-route" && answers.length === 0) {
      return identifyStream(base, caseId, prose, signal, onStage);
    }
    throw e;
  }
}

export function failureText(e: unknown): string {
  if (e instanceof EngineError) return e.detail || e.message;
  return "The engine could not be reached.";
}

export type Engine = ReturnType<typeof createEngine>;

export const engine: Engine = createEngine(import.meta.env?.VITE_ENGINE_URL ?? "/api");
