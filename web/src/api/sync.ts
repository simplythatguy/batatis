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
import type { EngineGap } from "./client";
import type { Case as EngineCase } from "./types.gen";
import { factSignature, jurisdictionBody, jurisdictionForCreate } from "../rules";
import type { AuthorityId, Fact, ListedEvidence } from "../types";

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
    // Evidence removal is handled by its explicit DELETE and acknowledgement queue.
    if (latest.has(field) || field.startsWith("evidence.")) continue;
    revisions.push({
      id: `${posted.id}-withdrawn`, field, value: "", kind: "pointed", status: "unconfirmed",
      source: { type: "user_click", ref: "Answer withdrawn by applicant", quote: "" },
    });
  }
  let error: string | null = null;
  for (const fact of revisions) {
    assertGeneration(token);
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

function forgetEvidence(caseId: string, id: string) {
  const facts = postedFor(caseId);
  for (const field of Object.keys(facts)) if (field.startsWith(`evidence.${id}.`)) delete facts[field];
  remember(caseId, facts);
}

const LISTED_FIELDS = ["title", "responsible_party", "evidence_type"] as const;

/**
 * Typed evidence is saved only as its `evidence.<id>.*` facts; this engine has no separate
 * evidence route. A listing counts as saved only after those fact writes were acknowledged.
 * Nothing here is a file reference, and no request is sent.
 */
export async function pushListedEvidence(caseId: string, items: ListedEvidence[]): Promise<string | null> {
  const posted = postedFor(caseId);
  const unsaved = items.filter((item) => item.description.trim()
    && !LISTED_FIELDS.every((field) => posted[`evidence.${item.id}.${field}`]));
  return unsaved.length ? "Listed evidence is not saved yet. Your entries are still here." : null;
}

/**
 * DELETE one evidence slot with `{ expected_version }`. Only the engine's answer acknowledges a
 * removal; any failure keeps it queued. A conflict waits for an explicit reconcile, and a
 * deleted or expired case stops the queue.
 */
export async function pushDeletedEvidence(
  caseId: string,
  ids: string[],
): Promise<{ acked: string[]; error: string | null }> {
  const token = generation;
  const acked: string[] = [];
  let error: string | null = null;
  for (const id of ids) {
    assertGeneration(token);
    if (!id.trim()) continue;
    const expected = known.get(caseId);
    if (conflicts.has(caseId) || expected === undefined) {
      error = CONFLICT_TEXT;
      break;
    }
    try {
      const saved = await engine.deleteEvidence(caseId, id, expected);
      assertGeneration(token);
      acknowledgeWrite(caseId, saved.version);
      forgetEvidence(caseId, id);
      acked.push(id);
    } catch (e) {
      assertGeneration(token);
      if (isCaseConflict(e)) {
        noteConflict(caseId);
        error = CONFLICT_TEXT;
        break;
      }
      error = e instanceof EngineError ? e.detail : String(e);
      if (isCaseGone(e)) break;
    }
  }
  return { acked, error };
}

export async function refreshGaps(caseId: string): Promise<{ gaps: EngineGap[]; error: string | null }> {
  try {
    return { gaps: await engine.gaps(caseId), error: null };
  } catch (e) {
    return { gaps: [], error: e instanceof EngineError ? e.detail : String(e) };
  }
}
