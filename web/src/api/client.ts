/**
 * Typed client for the engine HTTP API (engine/api.py). The app calls `/api/...` unless
 * `VITE_ENGINE_URL` is set, in which case it calls that origin directly. In development, Vite
 * proxies `/api` to the same URL (vite.config.ts). The default is http://127.0.0.1:8000.
 * `createEngine(base)` serves scripts and tests outside Vite.
 */
import { credentialsMode } from "./engineAuth";
import { accountRequestSignal } from "./requestLifetime";
import { publicDetail, takeSseEvents } from "../rules";
import type { RuleDef, RuleIndex } from "../rules/evaluate";
import type {
  CaseChecklists,
  CaseJurisdictionPack,
  CaseRules,
  ChecklistAnswerRequest,
  ChecklistAnswerResult,
  DraftingRecord,
  ExportPreview,
  ExportPreviewTooLarge,
  JurisdictionDetail,
  JurisdictionsResult,
} from "./types.gen";
import type {
  Case,
  EvidenceItem,
  FactInput,
  IdentifyDecisionResponse,
  IdentifyResult,
  IntakeRequest,
  IntakeResult,
  FileReport,
  Jurisdiction,
  NewCase,
  RequirementDecisionRequest,
  SectionCRow,
  SelectedArticlesRequest,
} from "./types.gen";
import { PRIVACY_NOTICE } from "../privacy";
import type { Job, WorkerHealth } from "./types.gen";
import type { DraftPatch } from "./types.gen";
export type { DraftPatch } from "./types.gen";

export type SavedCase = Case;

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
 * POST /cases/{id}/evidence: applicant metadata and owned-file binding, written atomically against
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
  /** Owned upload id; null removes only the binding, omission retains it. */
  file_ref?: string | null;
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
  async function call<T>(method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE", path: string, body?: unknown, signal?: AbortSignal, ms = ENGINE_WAIT_MS, headers: Record<string, string> = {}): Promise<T> {
    const timed = withTimeout(signal, ms);
    let res: Response;
    try {
      res = await fetch(`${base}${path}`, {
        method,
        credentials: credentialsMode(),
        signal: timed.signal,
        headers: { ...(body === undefined ? {} : { "Content-Type": "application/json" }), ...headers },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch (e) {
      if (timed.canceled()) throw e;
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
    patchDraft: (caseId: string, body: DraftPatch, signal?: AbortSignal) =>
      call<SavedCase>("PATCH", `/cases/${enc(caseId)}/draft`, body, signal, CASE_WAIT_MS),
    /**
     * PUT /cases/{id}/jurisdiction: `{ jurisdiction, expected_version }`, returning the full Case.
     * Engines without this route answer 404/405; the caller never treats that as saved.
     */
    setJurisdiction: (caseId: string, body: JurisdictionBody, signal?: AbortSignal) =>
      call<Case>("PUT", `/cases/${enc(caseId)}/jurisdiction`, body, signal, CASE_WAIT_MS),
    /**
     * PUT /cases/{id}/selected-articles: replace the saved code-check selection (docs/api/selected-articles.md),
     * returning the full saved Case. A snapshot only: it never confirms a reference or changes Section C/D.
     */
    setSelectedArticles: (caseId: string, body: SelectedArticlesRequest, signal?: AbortSignal) =>
      call<Case>("PUT", `/cases/${enc(caseId)}/selected-articles`, body, signal, CASE_WAIT_MS),
    getCase: (id: string, signal?: AbortSignal) => call<SavedCase>("GET", `/cases/${enc(id)}`, undefined, signal, CASE_WAIT_MS),
    applicantDrafts: (caseId: string, signal?: AbortSignal) =>
      call<DraftingRecord | null>("GET", `/cases/${enc(caseId)}/drafts`, undefined, signal),
    generateApplicantDrafts: (caseId: string, expectedVersion: number, signal?: AbortSignal) =>
      call<Case>("POST", `/cases/${enc(caseId)}/drafts`, { expected_version: expectedVersion }, signal, APPLICANT_DRAFT_WAIT_MS),
    decideApplicantDraft: (caseId: string, draftId: string, expectedVersion: number, decision: "accept" | "reject", signal?: AbortSignal) =>
      call<Case>("POST", `/cases/${enc(caseId)}/drafts/${enc(draftId)}/decision`, { expected_version: expectedVersion, decision }, signal),
    jobs: (caseId: string, signal?: AbortSignal) => call<ItemEnvelope<Job>>("GET", `/cases/${enc(caseId)}/jobs`, undefined, signal).then(unwrapItems),
    workerHealth: (caseId: string, signal?: AbortSignal) => call<WorkerHealth>("GET", `/cases/${enc(caseId)}/jobs/health`, undefined, signal),
    job: (caseId: string, id: string, signal?: AbortSignal) => call<Job>("GET", `/cases/${enc(caseId)}/jobs/${enc(id)}`, undefined, signal),
    startIntakeJob: (caseId: string, body: IntakeRequest, key: string, signal?: AbortSignal) =>
      call<Job>("POST", `/cases/${enc(caseId)}/intake/jobs`, body, signal, ENGINE_WAIT_MS, { "Idempotency-Key": key }),
    startIdentifyJob: (caseId: string, body: { prose: string; answers?: { field?: string; question_id?: string; answer: string }[]; expected_version: number }, key: string, signal?: AbortSignal) =>
      call<Job>("POST", `/cases/${enc(caseId)}/identify/jobs`, body, signal, ENGINE_WAIT_MS, { "Idempotency-Key": key }),
    retryJob: (caseId: string, id: string, signal?: AbortSignal) => call<Job>("POST", `/cases/${enc(caseId)}/jobs/${enc(id)}/retry`, {}, signal),
    cancelJob: (caseId: string, id: string, signal?: AbortSignal) => call<Job>("POST", `/cases/${enc(caseId)}/jobs/${enc(id)}/cancel`, {}, signal),
    /**
     * PATCH /cases/{id}/title `{ title }`: the applicant's own name for the application, returning the
     * full Case. The server trims it to one line; empty or over 500 characters is 422; a sent,
     * accepted or refused application cannot be renamed.
     */
    renameCase: (caseId: string, title: string, signal?: AbortSignal) =>
      call<Case>("PATCH", `/cases/${enc(caseId)}/title`, { title }, signal, CASE_WAIT_MS),
    addFact: (caseId: string, fact: FactInput, signal?: AbortSignal) =>
      call<Case>("POST", `/cases/${enc(caseId)}/facts`, fact, signal, CASE_WAIT_MS),
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
     * GET /cases/{id}/export/preview: the draft PDF's exact bytes and images of its first pages, as data URLs,
     * for the application screen. `pages` stops early only at the response budget; `page_count` counts all.
     * `too_large`: the PDF alone is over the budget, so nothing of it is sent; the draft download still works.
     */
    exportPreview: (caseId: string, signal?: AbortSignal) =>
      call<ExportPreview | ExportPreviewTooLarge>("GET", `/cases/${enc(caseId)}/export/preview`, undefined, signal, EXPORT_WAIT_MS),
    /** Multipart PDF, JPG, PNG, WebP or UTF-8 text note (4 MiB per file). Upload is not reading. */
    upload: (caseId: string, file: File, signal?: AbortSignal) => uploadPdf(base, caseId, file, signal),
    files: (caseId: string, signal?: AbortSignal) =>
      call<ItemEnvelope<StoredFile>>("GET", `/cases/${enc(caseId)}/files`, undefined, signal).then(unwrapItems),
    removeIntakeFile: (caseId: string, fileId: string, expectedVersion?: number, signal?: AbortSignal) =>
      call<IntakeResult & { removed_facts: number }>("DELETE", `/cases/${enc(caseId)}/intake/files/${enc(fileId)}`, withVersion({}, expectedVersion), signal),
    fileUrl: (caseId: string, fileId: string) => `${base}/cases/${enc(caseId)}/files/${enc(fileId)}`,
    downloadFile: (caseId: string, fileId: string, signal?: AbortSignal) => downloadFile(base, caseId, fileId, signal),
    /**
     * POST /cases/{id}/identify with Accept: text/event-stream, from PR #12.
     * 404 on today's dev. The caller keeps the description cards.
     */
    /**
     * Explicit start only. Missing routes fail without another provider attempt.
     */
    identify: (
      caseId: string,
      prose: string,
      answers: { field?: string | null; question_id?: string | null; answer: string }[] = [],
      signal?: AbortSignal,
      onStage?: StageListener,
      expectedVersion?: number,
    ) => identifyCase(base, caseId, prose, answers, signal, onStage, expectedVersion),
    /**
     * POST /cases/{id}/intake (docs/api/intake.md): read the description and uploaded PDFs into
     * unconfirmed facts that point at the words they came from, plus the plan (scope, fork, questions).
     */
    intake: (caseId: string, body: IntakeRequest, signal?: AbortSignal) =>
      call<IntakeResult>("POST", `/cases/${enc(caseId)}/intake`, body, signal, INTAKE_WAIT_MS),
    /** GET /cases/{id}/intake: the stored run. 404 `intake not run` before the first run. */
    storedIntake: (caseId: string, signal?: AbortSignal) =>
      call<IntakeResult>("GET", `/cases/${enc(caseId)}/intake`, undefined, signal),
    /** POST /cases/{id}/intake/answers. "Not sure" writes no fact and is never asked again. */
    intakeAnswers: (caseId: string, answers: { question_id: string; answer: string }[], expectedVersion?: number, signal?: AbortSignal) =>
      call<IntakeResult>("POST", `/cases/${enc(caseId)}/intake/answers`, withVersion({ answers }, expectedVersion), signal),
    /** POST /cases/{id}/intake/scope: `true` is the applicant's "this is a building-code question". */
    intakeScope: (caseId: string, buildingCode: boolean, expectedVersion?: number, signal?: AbortSignal) =>
      call<IntakeResult>("POST", `/cases/${enc(caseId)}/intake/scope`, withVersion({ building_code: buildingCode }, expectedVersion), signal),
    /** POST /cases/{id}/intake/plan: re-rank the questions, for example after code identification. */
    intakePlan: (caseId: string, expectedVersion?: number, signal?: AbortSignal) =>
      call<IntakeResult>("POST", `/cases/${enc(caseId)}/intake/plan`, withVersion({}, expectedVersion), signal),
    /** GET /cases/{id}/identify. 404 detail `identify result not found` when nothing is stored. */
    storedIdentify: (caseId: string, signal?: AbortSignal) =>
      call<IdentifyResult>("GET", `/cases/${enc(caseId)}/identify`, undefined, signal, CASE_WAIT_MS),

    /**
     * POST /cases/{id}/identify/{provision}/decision.
     * Body is yes, no, or not_sure, plus the optional `expected_version`. The reply is the identify
     * result with `section_c` (the rows a yes wrote) and `case_version`.
     */
    decide: (caseId: string, provisionId: string, decision: "yes" | "no" | "not_sure", signal?: AbortSignal, expectedVersion?: number) =>
      call<IdentifyDecisionResponse>(
        "POST",
        `/cases/${enc(caseId)}/identify/${enc(provisionId)}/decision`,
        withVersion({ decision }, expectedVersion),
        signal,
        CASE_WAIT_MS,
      ),
    /** GET /cases/{id}/identify/information-request. Read-only questions and legacy not_sure items. */
    informationRequest: (caseId: string, signal?: AbortSignal) =>
      call<InformationRequest>("GET", `/cases/${enc(caseId)}/identify/information-request`, undefined, signal),
    /**
     * POST /cases/{id}/identify/requirements/{requirement_id}/decision. Applicability only
     * (`include` / `exclude` / `review`); `expected_version` is required. The reply is the identify
     * result with the updated ledger and `case_version`.
     */
    decideRequirement: (caseId: string, requirementId: string, body: RequirementDecisionRequest, signal?: AbortSignal) =>
      call<IdentifyResult>(
        "POST",
        `/cases/${enc(caseId)}/identify/requirements/${enc(requirementId)}/decision`,
        body,
        signal,
        CASE_WAIT_MS,
      ),
    /** POST /cases/{id}/evidence. 409 = stale version or existing ID; 404 = case gone or slot absent. */
    saveEvidence: (caseId: string, body: EvidenceWrite, signal?: AbortSignal) =>
      call<EvidenceSaved>("POST", `/cases/${enc(caseId)}/evidence`, body, signal),
    /** DELETE /cases/{id}/evidence/{evidence_id} with `{ expected_version }`. Removes exactly one
     * slot and returns the full saved Case; other slots and uploaded bytes stay. */
    deleteEvidence: (caseId: string, evidenceId: string, expectedVersion: number, signal?: AbortSignal) =>
      call<Case>("DELETE", `/cases/${enc(caseId)}/evidence/${enc(evidenceId)}`, { expected_version: expectedVersion }, signal, CASE_WAIT_MS),
    /** GET /rules: the rule definitions the browser evaluator runs (docs/api/rules.md). No case, no provider. */
    rules: (signal?: AbortSignal) =>
      call<{ version: number; edition: string; index: RuleIndex; rules: RuleDef[] }>("GET", "/rules", undefined, signal),
    /** GET /cases/{id}/rules: the stored state of record for every coded rule. Read-only. */
    caseRules: (caseId: string, signal?: AbortSignal) => call<CaseRules>("GET", `/cases/${enc(caseId)}/rules`, undefined, signal, CASE_WAIT_MS),
    /** GET /jurisdictions: every pack, the coverage labels and their meanings (docs/api/jurisdictions.md). */
    jurisdictions: (signal?: AbortSignal) => call<JurisdictionsResult>("GET", "/jurisdictions", undefined, signal),
    /** GET /jurisdictions/{id}: one pack with the province's items merged in. */
    jurisdiction: (id: string, signal?: AbortSignal) => call<JurisdictionDetail>("GET", `/jurisdictions/${enc(id)}`, undefined, signal),
    /** GET /cases/{id}/jurisdiction/pack: the pack the case resolves to, or null. */
    casePack: (caseId: string, signal?: AbortSignal) => call<CaseJurisdictionPack>("GET", `/cases/${enc(caseId)}/jurisdiction/pack`, undefined, signal, CASE_WAIT_MS),
    /** GET /cases/{id}/checklists: standing-package checklists with the applicant's answers (docs/api/checklists.md). */
    caseChecklists: (caseId: string, signal?: AbortSignal) => call<CaseChecklists>("GET", `/cases/${enc(caseId)}/checklists`, undefined, signal, CASE_WAIT_MS),
    /** POST one checklist answer with `expected_version`. 409 = stale version: reload and let the person answer again. */
    answerChecklist: (caseId: string, checklistId: string, body: ChecklistAnswerRequest, signal?: AbortSignal) =>
      call<ChecklistAnswerResult>("POST", `/cases/${enc(caseId)}/checklists/${enc(checklistId)}/answers`, body, signal),
    /** POST /cases/{id}/identify/confirm. Writes provisions after a code-database check. */
    confirmIdentify: (caseId: string, provisions: string[], signal?: AbortSignal, expectedVersion?: number) =>
      call<Case>("POST", `/cases/${enc(caseId)}/identify/confirm`, withVersion({ provisions }, expectedVersion), signal, CASE_WAIT_MS),
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
  routed_to?: "officer" | "professional" | "applicant" | null;
  submission_blocking?: boolean;
}

export interface EngineProcessField {
  id: string;
  label: string;
  prompt: string;
  reviewer_looks_for: string[];
  citation: string;
  required: true;
  answer: { value: string } | null;
  /** Precedents to read for structure; never text to paste and never an answer. */
  example?: EngineProcessExample | null;
}

export interface EngineProcessExample {
  kind: "structure_only";
  label: string;
  must_address: string[];
  precedents: {
    title: string;
    issuer: string;
    number?: string | null;
    date?: string | null;
    pdf_page: number;
    url?: string | null;
    structure: string;
    edition: string;
  }[];
}

export interface ProfessionalResult {
  required: "yes" | "no" | "depends";
  general_required: "yes" | "no" | "depends";
  reasons: { code: string; required: "yes" | "no" | "depends"; message: string; citation: string }[];
  questions: string[];
  /** Facts the screen still needs to decide, e.g. "storeys" or "professional.role". */
  missing_facts?: string[];
  scope_note: string;
  resolution?: import("./types.gen").ProfessionalRequirementResolution | null;
  mandatory_required?: boolean;
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

export interface InformationRequest {
  case_id: string;
  items: { id: string; provision_id: string; text: string }[];
  case_version?: number;
  /** Context for the officer, separate from the administrative completeness gaps. */
  questions?: ReviewQuestion[];
}

export interface ReviewQuestion {
  id: string;
  field: string;
  text: string;
  provision_id: string | null;
  answer: string | null;
  state: "not_sure" | "unanswered" | "answered" | "unconfirmed" | "withdrawn";
  source: string;
  source_detail: string | null;
  origin: "code_check" | "code_matching" | "intake" | "officer_request";
  /** A response to an officer request, separate from the original manual code decision. */
  clarification?: Pick<ReviewQuestion, "answer" | "state" | "source" | "source_detail">;
}

export interface UploadedFile extends StoredFile {
  pages?: number;
  sha256?: string;
  read?: boolean;
}

/** Metadata from the case-owned upload inventory. Presence is verified by the store. */
export interface StoredFile {
  id: string;
  name: string;
  size: number;
  content_type: string;
  read_report?: FileReport | null;
}

async function downloadFile(base: string, caseId: string, fileId: string, signal?: AbortSignal): Promise<Blob> {
  const timed = withTimeout(signal, ENGINE_WAIT_MS);
  try {
    const response = await fetch(`${base}/cases/${enc(caseId)}/files/${enc(fileId)}`, {
      credentials: credentialsMode(), signal: timed.signal,
    });
    if (!response.ok) throw new EngineError(response.status, await readError(response));
    return await response.blob();
  } catch (error) {
    if (error instanceof EngineError || timed.canceled()) throw error;
    throw new EngineError(0, timed.timedOut() ? "The engine did not answer in time." : "The file could not be downloaded. Try again.");
  } finally { timed.clear(); }
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
/**
 * A saved case carries its identification result, and the production requirement profile stores a
 * ledger of about 2,000 Division B rows: the case payload is ~15 MB and a local read measured ~9 s.
 * Answers, applicability writes and the ledger's own decisions all return that payload, so they get a
 * budget that fits the bytes rather than the 8 s command bound. Still bounded, and still cancelled
 * with the caller or the account.
 */
export const CASE_WAIT_MS = 60_000;

/** Generation and grounding audit each have 180 seconds, followed by registry and save overhead. */
export const APPLICANT_DRAFT_WAIT_MS = 420_000;

/**
 * An export, or its preview, fills the whole form and appendix. The review's 500-reference draft took 49.8 s
 * locally before the appendix cleanup and 22.3 s (preview) to 22.9 s (download) after it; a hosted function
 * can be slower. Shared by both so the preview's "too large" answer and the draft download it offers can
 * finish. Still bounded, and still cancelled with the caller or the account.
 */
export const EXPORT_WAIT_MS = 90_000;
/**
 * Intake reads the description, then runs the document review inside the same request under the engine's
 * 240 s review deadline (engine/intake/review.py), after the description is read. A local AI connection
 * can take most of both.
 */
const INTAKE_WAIT_MS = 420_000;

function withTimeout(parent: AbortSignal | undefined, ms: number) {
  const scope = accountRequestSignal(parent);
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), ms);
  const abort = () => ctl.abort();
  if (scope.aborted) ctl.abort();
  else scope.addEventListener("abort", abort, { once: true });
  return {
    signal: ctl.signal,
    clear: () => { clearTimeout(timer); scope.removeEventListener("abort", abort); },
    canceled: () => scope.aborted,
    timedOut: () => ctl.signal.aborted && !scope.aborted,
  };
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
  // The privacy notice is shown elsewhere; never repeat it as an export notice.
  if (!text || text.startsWith(PRIVACY_NOTICE.split(".")[0])) return "";
  return text;
}

async function exportPdf(base: string, caseId: string, draft: boolean, signal?: AbortSignal) {
  const timed = withTimeout(signal, EXPORT_WAIT_MS);
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
    if (timed.canceled()) throw e;
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
  return { blob, filename: match?.[1] ?? `${caseId}-scc-variance.pdf`, notice: exportNotice(res.headers.get("X-Batatis-Jurisdiction-Notice")) };
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
    if (timed.canceled()) throw e;
    if (timed.timedOut()) throw new EngineError(0, "The engine did not answer in time.");
    throw new EngineError(0, e instanceof Error ? e.message : String(e));
  } finally {
    timed.clear();
  }
  if (!res.ok) throw new EngineError(res.status, await readError(res));
  return (await res.json()) as UploadedFile;
}

/** Identify writes are one compare-and-swap: send the case version last read (409 when it is stale). */
function withVersion<T extends object>(body: T, expectedVersion?: number): T & { expected_version?: number } {
  return expectedVersion == null ? body : { ...body, expected_version: expectedVersion };
}

/** One identify stream event: the stage name and its counts (never prose or code text). */
export type StageListener = (stage: string, data: Record<string, unknown>) => void;

async function readIdentifyResponse(res: Response, onStage?: StageListener): Promise<IdentifyResult> {
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
      if (ev.event !== "done" && ev.event !== "error") {
        let data: Record<string, unknown> = {};
        try {
          const parsedData = JSON.parse(ev.data) as unknown;
          if (parsedData && typeof parsedData === "object") data = parsedData as Record<string, unknown>;
        } catch {
          /* counts are optional */
        }
        onStage?.(ev.event, data);
      }
      if (ev.event === "error") {
        // Keep the engine's status (409 conflict, 503 unavailable) and its public message.
        let payload: { status?: unknown; message?: unknown } = {};
        try {
          payload = JSON.parse(ev.data) as typeof payload;
        } catch {
          /* fall back below */
        }
        const status = typeof payload.status === "number" ? payload.status : 503;
        throw new EngineError(status, typeof payload.message === "string" ? payload.message : "Article ranking failed.");
      }
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
  onStage?: StageListener,
  expectedVersion?: number,
): Promise<IdentifyResult> {
  const timed = withTimeout(signal, 60000);
  let res: Response;
  try {
    res = await fetch(`${base}/cases/${enc(caseId)}/identify`, {
      credentials: credentialsMode(),
      method: "POST",
      signal: timed.signal,
      headers: { Accept: "text/event-stream", "Content-Type": "application/json" },
      body: JSON.stringify(withVersion({ prose, answers }, expectedVersion)),
    });
    return await readIdentifyResponse(res, onStage);
  } catch (e) {
    if (timed.canceled() || e instanceof EngineError) throw e;
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

// VITE_ENGINE_URL (local direct calls) wins; VITE_API_BASE is the deploy setting (docs/deploy.md).
export const engine: Engine = createEngine(import.meta.env?.VITE_ENGINE_URL ?? import.meta.env?.VITE_API_BASE ?? "/api");
