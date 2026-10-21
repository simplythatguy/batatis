/**
 * Typed client for the engine HTTP API (engine/api.py). The app calls `/api/...` unless
 * `VITE_ENGINE_URL` is set, in which case it calls that origin directly. In development, Vite
 * proxies `/api` to the same URL (vite.config.ts). The default is http://127.0.0.1:8000.
 * `createEngine(base)` serves scripts and tests outside Vite.
 */
import { credentialsMode } from "./engineAuth";
import { publicDetail, takeSseEvents } from "../rules";
import type { Case, EvidenceItem, FactInput, Jurisdiction, NewCase, SectionCRow } from "./types.gen";

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

/** JSON array routes come back as `{ items, meta }`. Objects keep their fields and gain `meta`. */
export interface ItemEnvelope<T> {
  items: T[];
  meta?: { notice: string };
}

export function unwrapItems<T>(body: T[] | ItemEnvelope<T>): T[] {
  return Array.isArray(body) ? body : body.items;
}

/** Every engine route whose JSON body is a list. */
export const ARRAY_ROUTES = [
  { name: "search", method: "GET", path: "/code/search" },
  { name: "sectionC", method: "POST", path: "/section-c" },
  { name: "gaps", method: "GET", path: "/cases/{caseId}/gaps" },
  { name: "processFields", method: "GET", path: "/cases/{caseId}/process-fields" },
  { name: "sectionDIssues", method: "GET", path: "/cases/{caseId}/section-d/issues" },
] as const;

/**
 * POST /cases/{id}/section-d. Omit `provisions` to rebuild the saved selection.
 * An explicit list, including [], must carry the last acknowledged Case version.
 */
export type SectionDBody =
  | { provisions: string[]; expected_version: number }
  | { expected_version?: number };

/** PUT /cases/{id}/jurisdiction. Both fields are required; null clears the authority. */
export interface JurisdictionBody {
  jurisdiction: Jurisdiction | null;
  expected_version: number;
}

/**
 * POST /cases/{id}/evidence: one applicant text listing, written atomically against
 * `expected_version`. Optional details: a string is saved, null withdraws, omission retains.
 * `scope` omitted retains links; null unlinks; `{ item_id }` links to one current plan task.
 */
export interface EvidenceWrite {
  operation: "create" | "update";
  evidence_id: string;
  expected_version: number;
  title: string;
  description: string;
  evidence_type: string;
  responsible_party?: string | null;
  date?: string | null;
  issuer?: string | null;
  scope?: { item_id: string } | null;
}

/** The engine's acknowledgement: the actual saved item, the full saved Case and its version. */
export interface EvidenceSaved {
  evidence: EvidenceItem;
  case: Case;
  case_version: number;
}

/** status 0 = the review service did not respond. `technical` keeps the raw HTTP text. */
export class EngineError extends Error {
  readonly status: number;
  readonly detail: string;
  readonly technical: string;
  constructor(status: number, detail: string, technical?: string) {
    super(status ? `Engine ${status}: ${detail}` : `Engine unreachable: ${detail}`);
    this.status = status;
    this.detail = detail;
    this.technical = technical ?? detail;
  }
}

/** The saved case was deleted or passed its 7-day limit. It is never recreated. */
export function isCaseGone(e: unknown): boolean {
  return e instanceof EngineError && e.status === 404 && /case not found/i.test(`${e.detail} ${e.technical}`);
}

/** Another write changed the saved case. Reload and reconcile before writing again. */
export function isCaseConflict(e: unknown): boolean {
  return e instanceof EngineError && e.status === 409;
}

const enc = encodeURIComponent;

export function createEngine(base: string) {
  async function call<T>(method: "GET" | "POST" | "PUT" | "DELETE", path: string, body?: unknown, signal?: AbortSignal, ms = ENGINE_WAIT_MS): Promise<T> {
    const timed = withTimeout(signal, ms);
    let res: Response;
    try {
      res = await fetch(`${base}${path}`, {
        method,
        credentials: credentialsMode(),
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
      throw new EngineError(res.status, publicDetail(res.status, detail), detail);
    }
    return (await res.json()) as T;
  }

  return {
    createCase: (body: NewCase = {}, signal?: AbortSignal) => call<Case>("POST", "/cases", body, signal),
    /**
     * PUT /cases/{id}/jurisdiction: `{ jurisdiction, expected_version }`, returning the full Case.
     * Engines without this route answer 404/405; the caller never treats that as saved.
     */
    setJurisdiction: (caseId: string, body: JurisdictionBody, signal?: AbortSignal) =>
      call<Case>("PUT", `/cases/${enc(caseId)}/jurisdiction`, body, signal),
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
    /** Administrative gaps. Mounted in engine/routes_case.py. */
    gaps: (caseId: string, signal?: AbortSignal) =>
      call<EngineGap[] | ItemEnvelope<EngineGap>>("GET", `/cases/${enc(caseId)}/gaps`, undefined, signal).then(unwrapItems),
    /**
     * POST /cases/{id}/completeness from PR #11. Body is empty until that route
     * accepts documents. 404 on today's dev. The caller shows an empty state.
     */
    completeness: (caseId: string, signal?: AbortSignal) =>
      call<CompletenessReport>("POST", `/cases/${enc(caseId)}/completeness`, {}, signal),
    processFields: (caseId: string, signal?: AbortSignal) =>
      call<EngineProcessField[] | ItemEnvelope<EngineProcessField>>("GET", `/cases/${enc(caseId)}/process-fields`, undefined, signal).then(unwrapItems),
    professional: (caseId: string, signal?: AbortSignal) =>
      call<ProfessionalResult>("GET", `/cases/${enc(caseId)}/professional`, undefined, signal),
    /** Saves the selection with a version check and returns the plan with the committed `case_version`. */
    sectionD: (caseId: string, body: SectionDBody, signal?: AbortSignal) =>
      call<SectionDPlan>("POST", `/cases/${enc(caseId)}/section-d`, body, signal),
    /** GET /cases/{id}/section-d/issues. A missing code database is a fixed 503, not a missing route. */
    sectionDIssues: (caseId: string, signal?: AbortSignal) =>
      call<SectionDIssue[] | ItemEnvelope<SectionDIssue>>("GET", `/cases/${enc(caseId)}/section-d/issues`, undefined, signal).then(unwrapItems),
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
     * Explicit start only. Missing routes fail without another provider attempt.
     */
    identify: (caseId: string, prose: string, answers: { field?: string | null; question_id?: string | null; answer: string }[] = [], signal?: AbortSignal, onStage?: (stage: string) => void) =>
      identifyCase(base, caseId, prose, answers, signal, onStage),
    /** GET /cases/{id}/identify. 404 detail `identify result not found` when nothing is stored. */
    storedIdentify: (caseId: string, signal?: AbortSignal) =>
      call<IdentifyResult>("GET", `/cases/${enc(caseId)}/identify`, undefined, signal),

    /**
     * POST /cases/{id}/identify/{provision}/decision.
     * Body is yes, no, or not_sure. The body may be a SectionCRow or the stored identify payload.
     */
    decide: (caseId: string, provisionId: string, decision: "yes" | "no" | "not_sure", signal?: AbortSignal) =>
      call<unknown>("POST", `/cases/${enc(caseId)}/identify/${enc(provisionId)}/decision`, { decision }, signal),
    /** GET /cases/{id}/information-request. Items are not_sure decisions. */
    informationRequest: (caseId: string, signal?: AbortSignal) =>
      call<InformationRequest>("GET", `/cases/${enc(caseId)}/information-request`, undefined, signal),
    /** POST /cases/{id}/evidence. 409 = stale version or existing ID; 404 = case gone or slot absent. */
    saveEvidence: (caseId: string, body: EvidenceWrite, signal?: AbortSignal) =>
      call<EvidenceSaved>("POST", `/cases/${enc(caseId)}/evidence`, body, signal),
    /** DELETE /cases/{id}/evidence/{evidence_id} with `{ expected_version }`. Removes exactly one
     * slot and returns the full saved Case; other slots and uploaded bytes stay. */
    deleteEvidence: (caseId: string, evidenceId: string, expectedVersion: number, signal?: AbortSignal) =>
      call<Case>("DELETE", `/cases/${enc(caseId)}/evidence/${enc(evidenceId)}`, { expected_version: expectedVersion }, signal),
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
  /** `info` is advice (for example Calgary's own form). It is not a missing item and never blocks export. */
  severity: "blocking" | "warning" | "info";
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
    /** `evidence_listed` only when a same-case uploaded file is attached. Typed text never counts. */
    status: "needed" | "evidence_listed";
    objective: string | null;
    function: string | null;
    performance_issue: string;
    recommended_types: string[];
    attachments: { id: string; title: string }[];
  }[];
  notices: string[];
  /** Committed Case version for this save. */
  case_version: number | null;
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

/**
 * The export's own notice (for example Calgary's form note), or "".
 * PR #24 also puts the privacy notice in this header; that one belongs to the privacy notice, not to the download.
 */
/** One 409 reason as text. PR #21 sends {label, fix_hint, ...}; older engines send strings. */
export function exportReason(reason: unknown): string {
  if (typeof reason === "string") return reason.trim();
  if (reason && typeof reason === "object") {
    const r = reason as { label?: unknown; message?: unknown; fix_hint?: unknown };
    const label = typeof r.label === "string" ? r.label.trim() : typeof r.message === "string" ? r.message.trim() : "";
    const hint = typeof r.fix_hint === "string" ? r.fix_hint.trim() : "";
    if (label && hint && !label.includes(hint)) return `${label} ${hint}`;
    return label || hint;
  }
  return "";
}

export function exportNotice(header: string | null): string {
  const text = header?.trim() ?? "";
  if (!text || /^Do not upload personal information/i.test(text)) return "";
  return text;
}

async function exportPdf(base: string, caseId: string, draft: boolean, signal?: AbortSignal) {
  const timed = withTimeout(signal, 20000);
  let res: Response;
  try {
    res = await fetch(`${base}/cases/${enc(caseId)}/export`, {
      credentials: credentialsMode(),
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
        reasons = raw.reasons.map(exportReason).filter(Boolean);
        detail = String(raw.message ?? "export blocked");
      } else {
        detail = typeof raw === "string" ? raw : JSON.stringify(raw);
      }
    } catch {
      /* keep statusText */
    }
    if (res.status === 409) throw new ExportBlockedError(reasons, detail);
    throw new EngineError(res.status, publicDetail(res.status, detail), detail);
  }
  const blob = await res.blob();
  const match = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") ?? "");
  return { blob, filename: match?.[1] ?? `${caseId}-scc-variance.pdf`, notice: exportNotice(res.headers.get("X-Batatis-Notice")) };
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
    res = await fetch(`${base}/cases/${enc(caseId)}/files`, { method: "POST", body, signal: timed.signal, credentials: credentialsMode() });
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
      credentials: credentialsMode(),
      method: "POST",
      signal: timed.signal,
      headers: { Accept: "text/event-stream", "Content-Type": "application/json" },
      body: JSON.stringify({ prose, answers }),
    });
    return await readIdentifyResponse(res, onStage);
  } catch (e) {
    if (signal?.aborted || e instanceof EngineError) throw e;
    if (timed.timedOut()) throw new EngineError(0, "The engine did not answer in time.");
    throw new EngineError(0, e instanceof Error ? e.message : String(e));
  } finally {
    timed.clear();
  }
}

export function failureText(e: unknown): string {
  if (e instanceof EngineError) return e.detail || e.message;
  return "The review service did not respond.";
}

export type Engine = ReturnType<typeof createEngine>;

export const engine: Engine = createEngine(import.meta.env?.VITE_ENGINE_URL ?? "/api");
