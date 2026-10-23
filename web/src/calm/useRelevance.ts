/**
 * Relevance scores for the current engine case, shared by every ring.
 * GET when the library or palette opens; POST only on the explicit "Score relevance" button
 * (it costs money). Never rescored automatically. With the library's context set to None
 * (codeScope.ts) there are no scores at all: nothing is read, requested or shown.
 */
import { useCallback, useMemo, useSyncExternalStore } from "react";
import { CodeLibraryError, codeLibrary, type RelevanceResult } from "../api/codeLibrary";
import { useCase } from "../store";
import { useCodeScope, type CodeScope } from "./codeScope";
import { libraryEpoch } from "./libraryContext";
import { cutoffsOf, shownFor, type Cutoffs, type Shown } from "./relevance";

export type RelevancePhase = "idle" | "loading" | "none" | "ready" | "running" | "error";

export interface RelevanceState {
  caseId: string | null;
  phase: RelevancePhase;
  result: RelevanceResult | null;
  /** The last failure; kept beside an older result when a rescore fails. */
  error: CodeLibraryError | null;
  /** Date.now() when a POST started, for the elapsed-time label. */
  startedAt: number | null;
  /** Date.now() before which a 429 asks us to wait. */
  retryAt: number | null;
}

const EMPTY: RelevanceState = { caseId: null, phase: "idle", result: null, error: null, startedAt: null, retryAt: null };
let state: RelevanceState = EMPTY;
const listeners = new Set<() => void>();
let inflight: AbortController | null = null;
/** Bumps on every reset (another case opened, Start over), so a Score that was saving its draft stops. */
let resets = 0;

function set(next: Partial<RelevanceState>) {
  state = { ...state, ...next };
  for (const l of listeners) l();
}

function asError(e: unknown): CodeLibraryError {
  if (e instanceof CodeLibraryError) return e;
  const msg = e instanceof Error ? e.message : String(e);
  return new CodeLibraryError(0, "The code service did not respond.", msg);
}

/** Reset when the case changes (Start over). */
export function resetRelevance() {
  resets += 1;
  inflight?.abort();
  inflight = null;
  state = EMPTY;
  for (const l of listeners) l();
}

export async function loadRelevance(caseId: string) {
  if (state.phase === "running" && state.caseId === caseId) return;
  if (state.caseId !== caseId) state = { ...EMPTY, caseId };
  set({ phase: state.result ? state.phase : "loading", error: null });
  // A reset while this GET was out (the shell settling the switch that opened this very case)
  // leaves no case in the state: the answer is still this case's. Another case's state drops it;
  // every reader also compares caseId with the open case before showing anything.
  const mine = () => (state.caseId === null ? ((state = { ...EMPTY, caseId }), true) : state.caseId === caseId) && state.phase !== "running";
  try {
    const result = await codeLibrary.relevance(caseId);
    if (!mine()) return;
    set({ phase: result ? "ready" : "none", result });
  } catch (e) {
    if (!mine()) return;
    set({ phase: state.result ? "ready" : "error", error: asError(e) });
  }
}

export async function scoreRelevance(caseId: string) {
  if (state.phase === "running") return;
  inflight?.abort();
  const ctl = new AbortController();
  inflight = ctl;
  if (state.caseId !== caseId) state = { ...EMPTY, caseId };
  set({ phase: "running", error: null, startedAt: Date.now(), retryAt: null });
  try {
    const result = await codeLibrary.score(caseId, ctl.signal);
    if (ctl.signal.aborted || state.caseId !== caseId) return;
    set({ phase: "ready", result, startedAt: null });
  } catch (e) {
    if (ctl.signal.aborted || state.caseId !== caseId) return;
    const err = asError(e);
    set({
      phase: state.result ? "ready" : "error",
      error: err,
      startedAt: null,
      // Retry-After is only readable cross-origin when the engine exposes it; wait 15 s otherwise.
      retryAt: err.status === 429 ? Date.now() + (err.retryAfter ?? 15) * 1000 : null,
    });
  } finally {
    if (inflight === ctl) inflight = null;
  }
}

function subscribe(l: () => void) {
  listeners.add(l);
  return () => listeners.delete(l);
}

export function useRelevanceState(): RelevanceState {
  return useSyncExternalStore(subscribe, () => state, () => state);
}

export interface Relevance extends RelevanceState {
  /** "none": the library is browsing without an application; every field below is empty. */
  scope: CodeScope;
  display: Record<string, number> | undefined;
  /** Articles the rerank judged; others are never yellow or red (the guard). */
  rerank: Record<string, number> | undefined;
  /** Score and band for an article or a sentence inside it, after the guard. */
  shown: (id: string) => Shown;
  cutoffs: Cutoffs;
  stale: boolean;
  /** Why scoring cannot start, or "" when it can. */
  blocked: string;
  /** GET the saved scores for this case (free). */
  refresh: () => void;
  /** POST: saves the draft first so the engine scores the current description. */
  score: () => Promise<void>;
}

export function useRelevance(): Relevance {
  const { engineId, c, phase, saveDraft } = useCase();
  const scope = useCodeScope();
  const none = scope === "none";
  const s = useRelevanceState();
  const mine = none ? EMPTY : s.caseId === engineId ? s : { ...EMPTY, caseId: engineId };
  const display = mine.result?.display;
  const blocked =
    none ? "" : phase !== "case" ? "Start your application first." : !c.description.trim() ? "Describe your project to score it." : "";
  const refresh = useCallback(() => {
    if (!none && engineId) void loadRelevance(engineId);
  }, [none, engineId]);
  const score = useCallback(async () => {
    if (none || blocked) return;
    // The engine scores the saved description, so the current text is saved first. If the library
    // changed context or another case opened meanwhile, the request is no longer the one asked for.
    const asked = `${resets}:${libraryEpoch()}`;
    const id = (await saveDraft()) ?? engineId;
    if (asked !== `${resets}:${libraryEpoch()}`) return;
    if (!id) {
      set({ caseId: engineId, phase: state.result ? "ready" : "error", error: new CodeLibraryError(0, "Your draft could not be saved, so it cannot be scored yet.", "save not acknowledged") });
      return;
    }
    await scoreRelevance(id);
  }, [none, blocked, saveDraft, engineId]);
  // Stable per result, so memoized trees and filters do not rebuild on every render.
  const cutoffs = useMemo(() => cutoffsOf(mine.result), [mine.result]);
  const rerank = mine.result?.rerank;
  const shown = useCallback((id: string) => {
    const key = display?.[id] != null ? id : articleOf(id) ?? id;
    return shownFor(key, display, rerank, cutoffs);
  }, [display, rerank, cutoffs]);
  return { ...mine, scope, display, rerank, shown, cutoffs, stale: Boolean(mine.result?.stale), blocked, refresh, score };
}

/** Score for an article or a sentence inside it ("9.27.3.4.(1)" reads "9.27.3.4."). */
export function scoreFor(display: Record<string, number> | undefined, id: string): number | undefined {
  if (!display) return undefined;
  if (display[id] != null) return display[id];
  const article = articleOf(id);
  return article ? display[article] : undefined;
}

/** The article a provision id belongs to: four numeric levels and a trailing dot. */
export function articleOf(id: string): string | null {
  const m = /^(\d+\.\d+\.\d+\.\d+)\.?/.exec(id.trim());
  return m ? `${m[1]}.` : null;
}
