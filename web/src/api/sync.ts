/**
 * Push the browser case to the engine.
 * Facts go to POST /cases/{id}/facts. Jurisdiction goes to PUT /cases/{id}/jurisdiction
 * once the applicant picks an authority (backend/case-api). Today's dev has no PUT,
 * so a case that was opened with no jurisdiction is recreated with one.
 */
import { engine, EngineError } from "./client";
import type { EngineGap } from "./client";
import { factSignature, jurisdictionBody, jurisdictionForCreate } from "../rules";
import type { AuthorityId, Fact } from "../types";

const ID_KEY = "batatis-engine-case-id";
const POSTED_KEY = "batatis-engine-posted";

let inflight: Promise<string> | null = null;

export function engineCaseId(): string | null {
  return sessionStorage.getItem(ID_KEY);
}

export function clearEngineSession() {
  sessionStorage.removeItem(ID_KEY);
  sessionStorage.removeItem(POSTED_KEY);
  inflight = null;
}

function postedMap(): Record<string, string[]> {
  try {
    const raw = JSON.parse(sessionStorage.getItem(POSTED_KEY) || "{}");
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) return {};
    return raw as Record<string, string[]>;
  } catch {
    return {};
  }
}

function postedFor(caseId: string): Set<string> {
  const list = postedMap()[caseId];
  return new Set(Array.isArray(list) ? list.map(String) : []);
}

function remember(caseId: string, ids: Set<string>) {
  const map = postedMap();
  map[caseId] = [...ids];
  sessionStorage.setItem(POSTED_KEY, JSON.stringify(map));
}

/**
 * One create at a time. A second caller waits on the same promise, so two
 * keystrokes cannot open two cases and strand facts on the first.
 */
export function ensureEngineCase(title: string, authority: AuthorityId): Promise<string> {
  const existing = engineCaseId();
  if (existing) return Promise.resolve(existing);
  if (inflight) return inflight;
  inflight = engine
    .createCase({ title, jurisdiction: jurisdictionForCreate(authority) })
    .then((created) => {
      sessionStorage.setItem(ID_KEY, created.id);
      return created.id;
    })
    .finally(() => {
      inflight = null;
    });
  return inflight;
}

/**
 * Tell the engine which authority was picked. PUT is the contract.
 * On today's dev that route 404s. If the case was already created with this
 * jurisdiction, leave it. Otherwise open a new case that carries it, because
 * POST /cases is the only way this engine stores a jurisdiction.
 */
export async function syncJurisdiction(caseId: string, authority: Exclude<AuthorityId, "">, title: string): Promise<string> {
  const body = jurisdictionBody(authority);
  try {
    await engine.setJurisdiction(caseId, body);
    return caseId;
  } catch (e) {
    if (!(e instanceof EngineError) || e.status !== 404) throw e;
  }
  try {
    const current = await engine.getCase(caseId);
    if (current.jurisdiction?.id === body.id) return caseId;
  } catch (e) {
    if (!(e instanceof EngineError) || e.status === 0) throw e;
  }
  const created = await engine.createCase({ title, jurisdiction: body });
  sessionStorage.setItem(ID_KEY, created.id);
  return created.id;
}

/** Post facts the engine has not seen at this value. An edit of the same id is sent again. */
export async function pushFacts(caseId: string, facts: Fact[]): Promise<string | null> {
  const done = postedFor(caseId);
  let error: string | null = null;
  for (const fact of facts) {
    const signature = factSignature(fact);
    if (done.has(signature)) continue;
    try {
      await engine.addFact(caseId, fact);
      done.add(signature);
      remember(caseId, done);
    } catch (e) {
      error = e instanceof EngineError ? e.detail : String(e);
    }
  }
  return error;
}

export async function refreshGaps(caseId: string): Promise<{ gaps: EngineGap[]; error: string | null }> {
  try {
    return { gaps: await engine.gaps(caseId), error: null };
  } catch (e) {
    return { gaps: [], error: e instanceof EngineError ? e.detail : String(e) };
  }
}
