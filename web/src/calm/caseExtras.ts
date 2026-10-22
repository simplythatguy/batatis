/**
 * Read-only engine data the deck, Review and Application show beside the case: the coded rules
 * (definitions for the live evaluator and the case's state of record), the standing-package
 * checklists with the applicant's answers, and the jurisdiction pack. One module store, so every
 * screen derives from the same copy. Reads only; the one write (a checklist answer) goes through
 * the save queue in store.tsx and lands here with `setChecklists`.
 */
import { useEffect, useSyncExternalStore } from "react";
import { engine } from "../api/client";
import type { CaseChecklists, CaseJurisdictionPack, CaseRules, JurisdictionDetail, JurisdictionsResult } from "../api/types.gen";
import type { RuleData } from "./rulesView";

export interface CaseExtras {
  caseId: string | null;
  /** GET /rules, once per visit. Null until it loads, or when the engine is unreachable. */
  rules: RuleData | null;
  /** GET /cases/{id}/rules: the stored state of record. */
  caseRules: CaseRules | null;
  checklists: CaseChecklists | null;
  pack: CaseJurisdictionPack | null;
  /** GET /jurisdictions: coverage labels and the fallback pack for places Batatis has no local pack for. */
  directory: JurisdictionsResult | null;
  /** GET /jurisdictions/{id}, by pack id. */
  details: Record<string, JurisdictionDetail>;
  /** Reads that failed, so screens can say so and offer Try again (`retryExtras`). */
  failed: { rules?: boolean; case?: boolean; directory?: boolean; details: Record<string, boolean> };
}

const EMPTY: CaseExtras = { caseId: null, rules: null, caseRules: null, checklists: null, pack: null, directory: null, details: {}, failed: { details: {} } };
let state: CaseExtras = EMPTY;
const listeners = new Set<() => void>();
let loadedKey = "";
/** The latest case refresh; an older one finishing late never overwrites the pack. */
let refreshSeq = 0;
const fail = (patch: Partial<CaseExtras["failed"]>) => set({ failed: { ...state.failed, ...patch } });
let rulesLoad: Promise<void> | null = null;
let directoryLoad: Promise<void> | null = null;
const detailLoads = new Map<string, Promise<void>>();

function set(next: Partial<CaseExtras>) {
  state = { ...state, ...next };
  for (const l of listeners) l();
}

export const getExtras = () => state;

function subscribe(l: () => void) {
  listeners.add(l);
  return () => listeners.delete(l);
}

/** The engine's rule data, keyed by id the way the evaluator wants it. */
function loadRules(): Promise<void> {
  if (state.rules) return Promise.resolve();
  rulesLoad ??= engine.rules().then(
    (r) => { set({ rules: { index: r.index, rules: Object.fromEntries(r.rules.map((d) => [d.id, d])) } }); fail({ rules: false }); },
    () => { rulesLoad = null; fail({ rules: true }); },
  );
  return rulesLoad;
}

export function loadDirectory(): Promise<void> {
  if (state.directory) return Promise.resolve();
  directoryLoad ??= engine.jurisdictions().then((d) => { set({ directory: d }); fail({ directory: false }); }, () => { directoryLoad = null; fail({ directory: true }); });
  return directoryLoad;
}

export function loadJurisdiction(id: string): Promise<void> {
  if (state.details[id]) return Promise.resolve();
  let p = detailLoads.get(id);
  if (!p) {
    p = engine.jurisdiction(id).then(
      (d) => { set({ details: { ...state.details, [id]: d } }); fail({ details: { ...state.failed.details, [id]: false } }); },
      () => { detailLoads.delete(id); fail({ details: { ...state.failed.details, [id]: true } }); },
    );
    detailLoads.set(id, p);
  }
  return p;
}

/**
 * Re-read everything case-scoped. Older data stays on screen until the new read lands, and a read
 * that saw an older case version than the one held (a GET racing a checklist answer) is dropped.
 * Resolves false when a read failed; `onError` sees each rejection (so a caller can tell a deleted case apart).
 */
export async function refreshCase(caseId: string, onError?: (e: unknown) => void): Promise<boolean> {
  if (state.caseId !== caseId) state = { ...EMPTY, rules: state.rules, directory: state.directory, details: state.details, failed: state.failed, caseId };
  const seq = ++refreshSeq;
  const live = () => state.caseId === caseId;
  let ok = true;
  const miss = (e: unknown) => { ok = false; onError?.(e); };
  await Promise.all([
    engine.caseRules(caseId).then((r) => { if (live() && r.case_version >= (state.caseRules?.case_version ?? 0)) set({ caseRules: r }); }, miss),
    engine.caseChecklists(caseId).then((r) => { if (live() && r.case_version >= (state.checklists?.case_version ?? 0)) set({ checklists: r }); }, miss),
    engine.casePack(caseId).then((r) => { if (live() && seq === refreshSeq) set({ pack: r }); }, miss),
  ]);
  if (live() && seq === refreshSeq) fail({ case: !ok });
  return ok;
}

/** A checklist answer's response: the whole checklist with answers at the committed version. */
export function setChecklist(caseId: string, checklist: CaseChecklists["checklists"][number], caseVersion: number) {
  const cur = state.checklists;
  if (state.caseId !== caseId || !cur) return;
  set({ checklists: { ...cur, case_version: caseVersion, checklists: cur.checklists.map((x) => (x.id === checklist.id ? checklist : x)) } });
}

/** Try again after a failed read: the rule data, the case's reads, the directory and any failed pack. */
export function retryExtras() {
  void loadRules();
  if (state.caseId) void refreshCase(state.caseId);
  if (state.failed.directory) void loadDirectory();
  for (const [id, bad] of Object.entries(state.failed.details)) if (bad) void loadJurisdiction(id);
}

export function resetExtras() {
  loadedKey = "";
  state = { ...EMPTY, rules: state.rules, directory: state.directory, details: state.details, failed: { ...state.failed, case: false } };
  for (const l of listeners) l();
}

/**
 * Subscribe, and keep the case-scoped reads current: once per saved revision (`epoch`) and
 * authority. Every caller passes the same key, so several screens trigger one read.
 */
export function useCaseExtras(engineId: string | null, epoch: number, authority: string): CaseExtras {
  const extras = useSyncExternalStore(subscribe, getExtras, getExtras);
  useEffect(() => { void loadRules(); }, []);
  useEffect(() => {
    if (!engineId) {
      if (state.caseId) resetExtras();
      return;
    }
    const key = `${engineId}:${epoch}:${authority}`;
    if (key === loadedKey) return;
    loadedKey = key;
    void refreshCase(engineId);
  }, [engineId, epoch, authority]);
  return extras;
}
