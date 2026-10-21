import { engine, EngineError, isCaseConflict, isCaseGone, type SectionDBody, type SectionDPlan, type SectionDIssue, type ProfessionalResult, type EngineProcessField } from "./client";
import { acknowledgedVersion, acknowledgeWrite, CONFLICT_TEXT, engineGeneration, isEngineGeneration, needsReconcile, noteConflict } from "./sync";
import { confirmedProvisions } from "../provisions";
import type { Case } from "../types";

export interface SectionDRead {
  plan: SectionDPlan;
  issues: SectionDIssue[] | null;
  issuesNote: string | null;
  professional: ProfessionalResult;
  fields: EngineProcessField[];
}

export class SectionDRecoveryError extends Error {
  readonly kind: "conflict" | "missing";
  readonly detail: string;
  constructor(kind: "conflict" | "missing", detail: string) {
    super(kind === "missing"
      ? "This saved case is no longer available. It was deleted or passed its 7-day limit."
      : "The saved case changed somewhere else. Your answers are still here. Refresh the case before trying again.");
    this.kind = kind;
    this.detail = detail;
  }
}

/** Called inside the case save queue after its facts/evidence acknowledgement.
 * Await writes even when invalidated: an aborted HTTP request can still mutate the
 * server. The next revision must write after this one, not race it.
 *
 * A confirmed selection is sent as an explicit list with the acknowledged version.
 * An empty selection sends `[]` only when the saved case still holds references
 * (withdrawal); otherwise it rebuilds. A 409 marks the case for explicit reconcile. */
export async function readSectionD(id: string, snapshot: Case, current: () => boolean): Promise<SectionDRead | null> {
  const token = engineGeneration();
  const provisions = confirmedProvisions(snapshot);
  const expected = acknowledgedVersion(id);
  if (expected === null || needsReconcile(id)) throw new EngineError(409, CONFLICT_TEXT, "No current acknowledged case version.");
  let body: SectionDBody = { provisions, expected_version: expected };
  if (!provisions.length) {
    const saved = await engine.getCase(id);
    if (!current()) return null;
    if (!saved.provisions?.length && !saved.section_c?.length) body = { expected_version: expected };
  }
  let plan: SectionDPlan;
  try { plan = await engine.sectionD(id, body); }
  catch (e) {
    if (isCaseConflict(e) && isEngineGeneration(token)) noteConflict(id);
    throw e;
  }
  if (isEngineGeneration(token)) acknowledgeWrite(id, plan.case_version);
  if (!current()) return null;
  let issues: SectionDIssue[] | null = null;
  try { issues = await engine.sectionDIssues(id); }
  catch (e) {
    if (!(e instanceof EngineError && [404, 405].includes(e.status) && !isCaseGone(e))) throw e;
  }
  if (!current()) return null;
  const [professional, fields] = await Promise.all([engine.professional(id), engine.processFields(id)]);
  return current() ? { plan, issues, issuesNote: null, professional, fields } : null;
}
