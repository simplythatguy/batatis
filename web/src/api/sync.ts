/**
 * Push the browser case to the engine. Facts go to POST /cases/{id}/facts.
 * Gaps, Section D, professional screening and export are separate calls.
 */
import { engine, EngineError, type EngineGap } from "./client";
import type { AuthorityId, Fact } from "../types";

const ID_KEY = "batatis-engine-case-id";
const POSTED_KEY = "batatis-engine-posted";

const AUTHORITY: Record<Exclude<AuthorityId, "">, { id: string; name: string; authority: null }> = {
  calgary: { id: "calgary", name: "Calgary", authority: null },
  edmonton: { id: "edmonton", name: "Edmonton", authority: null },
};

export function engineCaseId(): string | null {
  return sessionStorage.getItem(ID_KEY);
}

export function clearEngineSession() {
  sessionStorage.removeItem(ID_KEY);
  sessionStorage.removeItem(POSTED_KEY);
}

function posted(): Set<string> {
  try {
    const raw = JSON.parse(sessionStorage.getItem(POSTED_KEY) || "[]");
    return new Set(Array.isArray(raw) ? raw.map(String) : []);
  } catch {
    return new Set();
  }
}

function remember(ids: Set<string>) {
  sessionStorage.setItem(POSTED_KEY, JSON.stringify([...ids]));
}

export async function ensureEngineCase(title: string, authority: AuthorityId): Promise<string> {
  const existing = engineCaseId();
  if (existing) return existing;
  const created = await engine.createCase({
    title,
    jurisdiction: authority ? AUTHORITY[authority] : null,
  });
  sessionStorage.setItem(ID_KEY, created.id);
  return created.id;
}

/** Post facts the engine has not seen. One rejected fact does not stop the rest. */
export async function pushFacts(caseId: string, facts: Fact[]): Promise<string | null> {
  const done = posted();
  let error: string | null = null;
  for (const fact of facts) {
    if (done.has(fact.id)) continue;
    try {
      await engine.addFact(caseId, fact);
      done.add(fact.id);
      remember(done);
    } catch (e) {
      error = e instanceof EngineError ? e.message : String(e);
    }
  }
  return error;
}

export async function refreshGaps(caseId: string): Promise<{ gaps: EngineGap[]; error: string | null }> {
  try {
    return { gaps: await engine.gaps(caseId), error: null };
  } catch (e) {
    return { gaps: [], error: e instanceof EngineError ? e.message : String(e) };
  }
}
