/**
 * Relevance scores for the current engine case, shared by every ring.
 * GET when the library or palette opens; POST only on the explicit "Score relevance" button
 * (it costs money). Never rescored automatically.
 */
import { useCallback, useMemo, useSyncExternalStore } from "react";
import { CodeLibraryError, codeLibrary, type RelevanceResult } from "../api/codeLibrary";
import { useCase } from "../store";
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
  inflight?.abort();
  inflight = null;
  state = EMPTY;
  for (const l of listeners) l();
}

export async function loadRelevance(caseId: string) {
  if (state.phase === "running" && state.caseId === caseId) return;
  if (state.caseId !== caseId) state = { ...EMPTY, caseId };
  set({ phase: state.result ? state.phase : "loading", error: null });
  try {
    const result = await codeLibrary.relevance(caseId);
    if (state.caseId !== caseId || state.phase === "running") return;
    set({ phase: result ? "ready" : "none", result });
  } catch (e) {
    if (state.caseId !== caseId || state.phase === "running") return;
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
  const s = useRelevanceState();
  const mine = s.caseId === engineId ? s : { ...EMPTY, caseId: engineId };
  const display = mine.result?.display;
  const blocked =
    phase !== "case" ? "Start your application first." : !c.description.trim() ? "Describe your project first. Scores are estimated from your description." : "";
  const refresh = useCallback(() => {
    if (engineId) void loadRelevance(engineId);
  }, [engineId]);
  const score = useCallback(async () => {
    if (blocked) return;
    // The engine scores the saved description, so the current text is saved first.
    const id = (await saveDraft()) ?? engineId;
    if (!id) {
      set({ caseId: engineId, phase: state.result ? "ready" : "error", error: new CodeLibraryError(0, "Your draft could not be saved, so it cannot be scored yet.", "save not acknowledged") });
      return;
    }
    await scoreRelevance(id);
  }, [blocked, saveDraft, engineId]);
  // Stable per result, so memoized trees and filters do not rebuild on every render.
  const cutoffs = useMemo(() => cutoffsOf(mine.result), [mine.result]);
  const rerank = mine.result?.rerank;
  const shown = useCallback((id: string) => {
    const key = display?.[id] != null ? id : articleOf(id) ?? id;
    return shownFor(key, display, rerank, cutoffs);
  }, [display, rerank, cutoffs]);
  return { ...mine, display, rerank, shown, cutoffs, stale: Boolean(mine.result?.stale), blocked, refresh, score };
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
