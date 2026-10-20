import { engine, EngineError, type SectionDPlan, type SectionDIssue, type ProfessionalResult, type EngineProcessField } from "./client";
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
      ? "This saved case is no longer available. Your answers are still on this page. Keep a draft before choosing Reset case."
      : "The saved case changed. Your answers are still here. Refresh the case before trying again.");
    this.kind = kind;
    this.detail = detail;
  }
}

/** Called inside the case save queue after its facts/evidence acknowledgement.
 * Await writes even when invalidated: an aborted HTTP request can still mutate the
 * server. The next revision must write after this one, not race it. */
export async function readSectionD(id: string, snapshot: Case, current: () => boolean): Promise<SectionDRead | null> {
  const provisions = confirmedProvisions(snapshot);
  if (!provisions.length) {
    const saved = await engine.getCase(id);
    if (!current()) return null;
    if (saved.provisions?.length) {
      // This backend cannot accept an empty provisions list. Do not show old results
      // or silently restore withdrawn choices; integration must provide that contract.
      throw new Error("No confirmed references remain. The server could not clear its earlier references. Your current draft is kept here.");
    }
  }
  const plan = await engine.sectionD(id, provisions.length ? provisions : undefined);
  if (!current()) return null;
  let issues: SectionDIssue[] | null = null;
  try { issues = await engine.sectionDIssues(id); }
  catch (e) {
    if (!(e instanceof EngineError && [404, 405].includes(e.status) && !/case not found/i.test(e.detail))) throw e;
  }
  if (!current()) return null;
  const [professional, fields] = await Promise.all([engine.professional(id), engine.processFields(id)]);
  return current() ? { plan, issues, issuesNote: null, professional, fields } : null;
}
