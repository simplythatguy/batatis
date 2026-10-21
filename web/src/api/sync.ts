/**
 * Push the browser case to the engine.
 * Facts go to POST /cases/{id}/facts. Jurisdiction goes to PUT /cases/{id}/jurisdiction
 * with the acknowledged version. Never recreate a case when a route is unavailable or the
 * case is gone; keep the draft and report the unacknowledged update.
 *
 * Versions: every committed write increments the stored Case version by one. `known` is the
 * last version reached through this visit's own consecutive writes. A response that skips a
 * number means another writer changed the case, so `known` stays put and the next versioned
 * write (plan or jurisdiction) is rejected by the engine with 409. Only an explicit reconcile
 * adopts a version the visit did not write itself.
 */
import { engine, EngineError, isCaseConflict, isCaseGone } from "./client";
import type { EngineGap, EvidenceWrite } from "./client";
import type { Case as EngineCase } from "./types.gen";
import { factSignature, jurisdictionBody, jurisdictionForCreate } from "../rules";
import type { AuthorityId, Fact, ListedEvidence } from "../types";
import { evidenceSlot } from "../model";

const ID_KEY = "batatis-engine-case-id";
const POSTED_KEY = "batatis-engine-posted";
/** Older builds recorded unacknowledged evidence POSTs here. Cleared, never read. */
const LEGACY_EVIDENCE_KEY = "batatis-engine-evidence";

let inflight: Promise<string> | null = null;
let generation = 0;
const factQueues = new Map<string, Promise<unknown>>();
const known = new Map<string, number>();
const conflicts = new Set<string>();
const jurisdictions = new Map<string, string | null>();
/** Evidence slots the engine has shown for each case, from acknowledged writes and explicit reads. */
const ledgerSlots = new Map<string, Set<string>>();
/** Listing revisions the engine acknowledged, so a repeated push never writes them twice. */
const ackedRevs = new Map<string, Map<string, number>>();
/** Slots this visit tried to create; a removal of one never tried needs no request. */
const attempted = new Map<string, Set<string>>();
const latestLedger = new Map<string, Fact[]>();

/** The version to send as `expected_version`, or null before the case is acknowledged. */
export function acknowledgedVersion(caseId: string): number | null {
  return known.get(caseId) ?? null;
}

/** True after the engine rejected a versioned write; only an explicit reconcile clears it. */
export function needsReconcile(caseId: string): boolean {
  return conflicts.has(caseId);
}

/** Record the engine's answer to one of this visit's writes. */
export function acknowledgeWrite(caseId: string, version: unknown) {
  if (typeof version !== "number" || !Number.isInteger(version) || version < 1) return;
  const previous = known.get(caseId);
  if (previous === undefined || version === previous + 1) known.set(caseId, version);
}

export function noteConflict(caseId: string) {
  conflicts.add(caseId);
}

export const CONFLICT_TEXT = "The saved case changed somewhere else. Your answers are still here.";

/** Captured by callers before starting work; a reset invalidates every continuation. */
export const engineGeneration = () => generation;
export const isEngineGeneration = (value: number) => value === generation;

export class StaleEngineSession extends Error {
  constructor() {
    super("The application changed while saving.");
    this.name = "StaleEngineSession";
  }
}

function assertGeneration(value: number) {
  if (!isEngineGeneration(value)) throw new StaleEngineSession();
}

export function engineCaseId(): string | null {
  return sessionStorage.getItem(ID_KEY);
}

export function clearEngineSession() {
  generation += 1;
  factQueues.clear();
  known.clear();
  conflicts.clear();
  jurisdictions.clear();
  ledgerSlots.clear();
  ackedRevs.clear();
  attempted.clear();
  latestLedger.clear();
  sessionStorage.removeItem(ID_KEY);
  sessionStorage.removeItem(POSTED_KEY);
  sessionStorage.removeItem(LEGACY_EVIDENCE_KEY);
  inflight = null;
}

type PostedFact = { id: string; signature: string };

function postedFor(caseId: string): Record<string, PostedFact> {
  try {
    const map = JSON.parse(sessionStorage.getItem(POSTED_KEY) || "{}");
    const fields = map?.[caseId];
    return fields && typeof fields === "object" && !Array.isArray(fields) ? fields : {};
  } catch {
    return {};
  }
}

function remember(caseId: string, fields: Record<string, PostedFact>) {
  let map: Record<string, unknown> = {};
  try { map = JSON.parse(sessionStorage.getItem(POSTED_KEY) || "{}"); } catch { /* empty */ }
  sessionStorage.setItem(POSTED_KEY, JSON.stringify({ ...map, [caseId]: fields }));
}

/**
 * One create at a time. A second caller waits on the same promise, so two
 * keystrokes cannot open two cases and strand facts on the first.
 */
export function ensureEngineCase(title: string, authority: AuthorityId): Promise<string> {
  const existing = engineCaseId();
  if (existing) return Promise.resolve(existing);
  if (inflight) return inflight;
  const token = generation;
  const request = engine
    .createCase({ title, jurisdiction: jurisdictionForCreate(authority) })
    .then((created) => {
      assertGeneration(token);
      sessionStorage.setItem(ID_KEY, created.id);
      acknowledgeWrite(created.id, created.version);
      jurisdictions.set(created.id, created.jurisdiction?.id ?? null);
      return created.id;
    })
    .finally(() => {
      if (inflight === request) inflight = null;
    });
  inflight = request;
  return request;
}

/**
 * PUT `{ jurisdiction, expected_version }` only when the authority differs from the last
 * acknowledged value. An engine without the route (404/405) counts as saved only when its
 * stored value already matches. A missing case or a conflict is never retried here.
 */
export async function syncJurisdiction(caseId: string, authority: AuthorityId, _title: string): Promise<string> {
  const token = generation;
  const jurisdiction = authority ? jurisdictionBody(authority) : null;
  const wanted = jurisdiction?.id ?? null;
  if (jurisdictions.has(caseId) && jurisdictions.get(caseId) === wanted) return caseId;
  const unsaved = wanted
    ? "The reviewing authority could not be saved. Your draft is still open."
    : "The cleared reviewing authority could not be saved. Your draft is still open.";
  const expected = known.get(caseId);
  if (conflicts.has(caseId) || expected === undefined) throw new EngineError(409, CONFLICT_TEXT, "No acknowledged case version to send.");
  try {
    const saved = await engine.setJurisdiction(caseId, { jurisdiction, expected_version: expected });
    assertGeneration(token);
    acknowledgeWrite(caseId, saved.version);
    jurisdictions.set(caseId, saved.jurisdiction?.id ?? null);
    return caseId;
  } catch (e) {
    assertGeneration(token);
    if (isCaseConflict(e)) {
      noteConflict(caseId);
      throw new EngineError(409, CONFLICT_TEXT, (e as EngineError).technical);
    }
    if (isCaseGone(e) || !(e instanceof EngineError) || ![404, 405].includes(e.status)) throw e;
    const current = await engine.getCase(caseId);
    assertGeneration(token);
    const stored = current.jurisdiction?.id ?? null;
    if (stored === wanted) {
      jurisdictions.set(caseId, stored);
      return caseId;
    }
    throw new EngineError(e.status, unsaved, e.technical);
  }
}

/**
 * Explicit reconcile after a conflict: read the saved case, adopt its version, and re-base
 * this visit's posted-answer record on the saved values so the next save re-sends any local
 * answer that differs. Answers this visit never wrote are left alone. A missing case throws.
 */
export async function reconcileEngineCase(caseId: string): Promise<EngineCase> {
  const token = generation;
  const saved = await engine.getCase(caseId);
  assertGeneration(token);
  known.set(caseId, saved.version);
  jurisdictions.set(caseId, saved.jurisdiction?.id ?? null);
  const latest = new Map(saved.facts.map((fact) => [fact.field, fact]));
  const posted = postedFor(caseId);
  for (const field of Object.keys(posted)) {
    const stored = latest.get(field);
    if (stored) posted[field] = { id: stored.id, signature: factSignature(stored) };
    else delete posted[field];
  }
  remember(caseId, posted);
  conflicts.delete(caseId);
  noteLedger(caseId, saved);
  return saved;
}

/** Reconcile a complete browser fact snapshot, including withdrawals. Serialize writes
 * so a slower older save cannot become the engine's latest revision. */
export function pushFacts(caseId: string, facts: Fact[]): Promise<string | null> {
  const token = generation;
  const previous = factQueues.get(caseId) ?? Promise.resolve();
  const request = previous.catch(() => {}).then(() => reconcileFacts(caseId, facts, token));
  factQueues.set(caseId, request);
  return request;
}

async function reconcileFacts(caseId: string, facts: Fact[], token: number): Promise<string | null> {
  assertGeneration(token);
  const done = postedFor(caseId);
  const latest = new Map(facts.map((fact) => [fact.field, fact]));
  const revisions = [...latest.values()];
  for (const [field, posted] of Object.entries(done)) {
    // Evidence is written only through its own atomic route; see pushListedEvidence.
    if (latest.has(field) || field.startsWith("evidence.")) continue;
    revisions.push({
      id: `${posted.id}-withdrawn`, field, value: "", kind: "pointed", status: "unconfirmed",
      source: { type: "user_click", ref: "Answer withdrawn by applicant", quote: "" },
    });
  }
  let error: string | null = null;
  for (const fact of revisions) {
    assertGeneration(token);
    // Browser evidence facts mirror what the evidence route already saved. Never re-post them.
    if (fact.field.startsWith("evidence.")) continue;
    const signature = factSignature(fact);
    if (done[fact.field]?.signature === signature) continue;
    try {
      const saved = await engine.addFact(caseId, fact);
      assertGeneration(token);
      acknowledgeWrite(caseId, saved.version);
      if (latest.has(fact.field)) done[fact.field] = { id: fact.id, signature };
      else delete done[fact.field];
      remember(caseId, done);
    } catch (e) {
      assertGeneration(token);
      error = e instanceof EngineError ? e.detail : String(e);
      // A deleted or expired case stays gone; do not keep posting into it.
      if (isCaseGone(e)) break;
    }
  }
  return error;
}

/** The engine's evidence ledger facts from a saved Case. The browser mirrors exactly these. */
export function evidenceFacts(saved: EngineCase): Fact[] {
  return saved.facts.filter((fact) => fact.field.startsWith("evidence.")) as Fact[];
}

function noteLedger(caseId: string, saved: EngineCase) {
  const facts = evidenceFacts(saved);
  latestLedger.set(caseId, facts);
  const slots = new Set(saved.evidence.map((item) => item.id));
  for (const fact of facts) {
    const slot = evidenceSlot(fact.field);
    if (slot) slots.add(slot);
  }
  ledgerSlots.set(caseId, slots);
}

const setFor = <T,>(map: Map<string, T>, caseId: string, make: () => T) => {
  if (!map.has(caseId)) map.set(caseId, make());
  return map.get(caseId)!;
};

export type EvidenceRejection = { id: string; rev?: number; reason: string };

/** What the engine acknowledged. `facts` is its evidence ledger after the latest acknowledged write. */
export interface EvidenceOutcome {
  acked: { id: string; rev: number }[];
  deleted: string[];
  rejected: EvidenceRejection[];
  facts: Fact[] | null;
  error: string | null;
}

const REJECTED: [RegExp, string][] = [
  [/scope must resolve/i, "This task changed, so the document could not be added to it. Your text is still here."],
  [/attachment workflow/i, "This slot holds an attached file. Your text is still here."],
  [/ambiguous/i, "Couldn’t remove this document. It shares its name with another saved entry."],
  [/evidence not found/i, "This document was removed somewhere else. Your text is still here."],
];

function rejection(e: unknown): string {
  const text = e instanceof EngineError ? `${e.detail} ${e.technical}` : String(e);
  return REJECTED.find(([pattern]) => pattern.test(text))?.[1] ?? "This document could not be saved. Your text is still here.";
}

function listingBody(item: ListedEvidence, expected: number): EvidenceWrite {
  const body: EvidenceWrite = {
    operation: item.operation,
    evidence_id: item.id,
    expected_version: expected,
    title: item.description,
    description: item.description,
    evidence_type: item.evidenceType,
  };
  // A string is saved; null withdraws a saved value (update only); undefined retains or omits.
  if (typeof item.responsible === "string" || (item.responsible === null && item.operation === "update")) body.responsible_party = item.responsible;
  if (typeof item.date === "string" || (item.date === null && item.operation === "update")) body.date = item.date;
  // Only a new listing names its task. An edit omits scope, so withdrawn links are never restored.
  if (item.operation === "create" && item.taskId) body.scope = { item_id: item.taskId };
  return body;
}

/**
 * Save each staged listing with POST /cases/{id}/evidence and the acknowledged version. A listing
 * counts as saved only for the exact revision the engine acknowledged. A conflict waits for an
 * explicit refresh, a deleted or expired case stops the queue, and a refused listing is returned
 * so its text can go back to the form. No automatic retry, upsert or replacement case.
 */
export async function pushListedEvidence(caseId: string, items: ListedEvidence[]): Promise<EvidenceOutcome> {
  const token = generation;
  const outcome: EvidenceOutcome = { acked: [], deleted: [], rejected: [], facts: latestLedger.get(caseId) ?? null, error: null };
  const revs = setFor(ackedRevs, caseId, () => new Map<string, number>());
  for (const item of items) {
    assertGeneration(token);
    if (revs.get(item.id) === item.rev) {
      outcome.acked.push({ id: item.id, rev: item.rev });
      continue;
    }
    const expected = known.get(caseId);
    if (conflicts.has(caseId) || expected === undefined) {
      outcome.error = CONFLICT_TEXT;
      break;
    }
    if (item.operation === "create") setFor(attempted, caseId, () => new Set<string>()).add(item.id);
    try {
      const saved = await engine.saveEvidence(caseId, listingBody(item, expected));
      assertGeneration(token);
      acknowledgeWrite(caseId, saved.case_version);
      noteLedger(caseId, saved.case);
      revs.set(item.id, item.rev);
      outcome.acked.push({ id: item.id, rev: item.rev });
      outcome.facts = latestLedger.get(caseId) ?? null;
    } catch (e) {
      assertGeneration(token);
      if (isCaseConflict(e)) {
        noteConflict(caseId);
        outcome.error = CONFLICT_TEXT;
        break;
      }
      if (e instanceof EngineError && (e.status === 422 || (e.status === 404 && !isCaseGone(e)))) {
        outcome.rejected.push({ id: item.id, rev: item.rev, reason: rejection(e) });
        continue;
      }
      // Gone, unreachable or an unanswered request: unknown or failed, never saved.
      outcome.error = e instanceof EngineError ? e.detail : String(e);
      break;
    }
  }
  return outcome;
}

/**
 * DELETE one evidence slot with `{ expected_version }`. Only the engine's answer acknowledges a
 * removal. A slot this visit never sent and the engine never showed needs no request. A 404 for
 * the slot is checked with a read, never taken as success. Ambiguous older slots are refused
 * once and not retried.
 */
export async function pushDeletedEvidence(caseId: string, ids: string[]): Promise<EvidenceOutcome> {
  const token = generation;
  const outcome: EvidenceOutcome = { acked: [], deleted: [], rejected: [], facts: latestLedger.get(caseId) ?? null, error: null };
  for (const id of ids) {
    assertGeneration(token);
    if (!id.trim()) continue;
    if (!attempted.get(caseId)?.has(id) && !ledgerSlots.get(caseId)?.has(id)) {
      outcome.deleted.push(id);
      continue;
    }
    const expected = known.get(caseId);
    if (conflicts.has(caseId) || expected === undefined) {
      outcome.error = CONFLICT_TEXT;
      break;
    }
    try {
      const saved = await engine.deleteEvidence(caseId, id, expected);
      assertGeneration(token);
      acknowledgeWrite(caseId, saved.version);
      noteLedger(caseId, saved);
      outcome.deleted.push(id);
      outcome.facts = latestLedger.get(caseId) ?? null;
    } catch (e) {
      assertGeneration(token);
      if (isCaseConflict(e)) {
        noteConflict(caseId);
        outcome.error = CONFLICT_TEXT;
        break;
      }
      if (e instanceof EngineError && e.status === 422) {
        outcome.rejected.push({ id, reason: rejection(e) });
        continue;
      }
      if (e instanceof EngineError && e.status === 404 && !isCaseGone(e)) {
        // Confirm absence with a read. The version is not adopted from it.
        try {
          const current = await engine.getCase(caseId);
          assertGeneration(token);
          const present = current.evidence.some((item) => item.id === id)
            || current.facts.some((fact) => evidenceSlot(fact.field) === id);
          if (!present) {
            ledgerSlots.get(caseId)?.delete(id);
            attempted.get(caseId)?.delete(id);
            outcome.deleted.push(id);
            continue;
          }
        } catch (read) {
          assertGeneration(token);
          outcome.error = read instanceof EngineError ? read.detail : String(read);
          break;
        }
      }
      outcome.error = e instanceof EngineError ? e.detail : String(e);
      if (isCaseGone(e) || !(e instanceof EngineError) || e.status === 0) break;
    }
  }
  return outcome;
}

export async function refreshGaps(caseId: string): Promise<{ gaps: EngineGap[]; error: string | null }> {
  try {
    return { gaps: await engine.gaps(caseId), error: null };
  } catch (e) {
    return { gaps: [], error: e instanceof EngineError ? e.detail : String(e) };
  }
}
