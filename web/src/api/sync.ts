/**
 * Push the browser case to the engine.
 * Facts go to POST /cases/{id}/facts. Jurisdiction goes to PUT /cases/{id}/jurisdiction
 * once the applicant picks an authority (backend/case-api). Never recreate a case
 * when that route is unavailable; keep the draft and report the unacknowledged update.
 */
import { engine, EngineError } from "./client";
import type { EngineGap } from "./client";
import { factSignature, jurisdictionBody, jurisdictionForCreate } from "../rules";
import type { AuthorityId, Fact, ListedEvidence } from "../types";

const ID_KEY = "batatis-engine-case-id";
const POSTED_KEY = "batatis-engine-posted";
const EVIDENCE_KEY = "batatis-engine-evidence";

let inflight: Promise<string> | null = null;
let generation = 0;
const factQueues = new Map<string, Promise<unknown>>();

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
  sessionStorage.removeItem(ID_KEY);
  sessionStorage.removeItem(POSTED_KEY);
  sessionStorage.removeItem(EVIDENCE_KEY);
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
      return created.id;
    })
    .finally(() => {
      if (inflight === request) inflight = null;
    });
  inflight = request;
  return request;
}

/** PUT is the update contract. Older engines may only acknowledge the jurisdiction
 * supplied at creation. A mismatched value must fail without making an orphan copy. */
export async function syncJurisdiction(caseId: string, authority: AuthorityId, _title: string): Promise<string> {
  const token = generation;
  if (!authority) {
    const current = await engine.getCase(caseId);
    assertGeneration(token);
    if (!current.jurisdiction) return caseId;
    throw new EngineError(409, "The cleared reviewing authority could not be saved. Your draft is still open.", "This engine cannot clear a saved jurisdiction yet.");
  }
  const body = jurisdictionBody(authority);
  try {
    await engine.setJurisdiction(caseId, body);
    assertGeneration(token);
    return caseId;
  } catch (e) {
    assertGeneration(token);
    if (!(e instanceof EngineError) || ![404, 405].includes(e.status)) throw e;
    const current = await engine.getCase(caseId);
    assertGeneration(token);
    if (current.jurisdiction?.id === body.id) return caseId;
    throw new EngineError(e.status, "The reviewing authority could not be saved. Your draft is still open.", e.technical);
  }
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
      await engine.addFact(caseId, fact);
      assertGeneration(token);
      if (latest.has(fact.field)) done[fact.field] = { id: fact.id, signature };
      else delete done[fact.field];
      remember(caseId, done);
    } catch (e) {
      assertGeneration(token);
      error = e instanceof EngineError ? e.detail : String(e);
    }
  }
  return error;
}

function evidencePosted(caseId: string): Set<string> {
  try {
    const raw = JSON.parse(sessionStorage.getItem(EVIDENCE_KEY) || "{}") as Record<string, string[]>;
    const list = raw[caseId];
    return new Set(Array.isArray(list) ? list.map(String) : []);
  } catch {
    return new Set();
  }
}

function forgetEvidence(caseId: string, id: string) {
  const facts = postedFor(caseId);
  for (const field of Object.keys(facts)) if (field.startsWith(`evidence.${id}.`)) delete facts[field];
  remember(caseId, facts);
  const done = evidencePosted(caseId);
  for (const signature of [...done]) {
    if (signature.startsWith(`${id}:`)) done.delete(signature);
  }
  rememberEvidence(caseId, done);
}

function rememberEvidence(caseId: string, ids: Set<string>) {
  let map: Record<string, string[]> = {};
  try {
    const raw = JSON.parse(sessionStorage.getItem(EVIDENCE_KEY) || "{}");
    if (raw && typeof raw === "object" && !Array.isArray(raw)) map = raw as Record<string, string[]>;
  } catch {
    map = {};
  }
  map[caseId] = [...ids];
  sessionStorage.setItem(EVIDENCE_KEY, JSON.stringify(map));
}

/**
 * POST typed evidence as text. A 404 means this engine does not serve the route yet.
 * The local record stays text either way. Nothing here is stored as a file reference.
 */
export async function pushListedEvidence(caseId: string, items: ListedEvidence[]): Promise<string | null> {
  const token = generation;
  const done = evidencePosted(caseId);
  let error: string | null = null;
  for (const item of items) {
    assertGeneration(token);
    if (!item.provisionId || !item.evidenceType || !item.description.trim()) continue;
    const signature = `${item.id}:${item.description}`;
    if (done.has(signature)) continue;
    const description = item.date
      ? `${item.description}. Person responsible: ${item.responsible}. Date: ${item.date}.`
      : `${item.description}. Person responsible: ${item.responsible}.`;
    try {
      await engine.addEvidence(caseId, {
        provision_id: item.provisionId,
        evidence_type: item.evidenceType,
        description,
      });
      assertGeneration(token);
      done.add(signature);
      rememberEvidence(caseId, done);
    } catch (e) {
      assertGeneration(token);
      if (e instanceof EngineError && e.status === 404) {
        done.add(signature);
        rememberEvidence(caseId, done);
        continue;
      }
      error = e instanceof EngineError ? e.detail : String(e);
    }
  }
  return error;
}

/**
 * DELETE one evidence slot on the engine. A missing route is acknowledged so the
 * browser copy stays removed. Any other failure stays queued for the next save.
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
    try {
      await engine.deleteEvidence(caseId, id);
      assertGeneration(token);
      forgetEvidence(caseId, id);
      acked.push(id);
    } catch (e) {
      assertGeneration(token);
      if (e instanceof EngineError && e.status === 404 && !/case not found/i.test(e.detail)) {
        forgetEvidence(caseId, id);
        acked.push(id);
        continue;
      }
      error = e instanceof EngineError ? e.detail : String(e);
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
