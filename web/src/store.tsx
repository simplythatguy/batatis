import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, useState, type Dispatch, type ReactNode } from "react";
import { engine, EngineError, type EngineGap } from "./api/client";
import { type CompletenessRecord, isProfessionalHold, officerRoutedLabel } from "./humanReview";
import { clearEngineSession, engineCaseId, engineGeneration, isEngineGeneration, ensureEngineCase, pushDeletedEvidence, pushFacts, pushListedEvidence, refreshGaps, syncJurisdiction } from "./api/sync";
import { engineNotices, groupEvidenceGaps, missingFromEngine } from "./rules";
import { applyIdentifyPlan, planIdentify } from "./identify";
import { checkCurrent, newCheckState, type CheckState, type SaveStatus } from "./checkState";
import { emptyCase } from "./intake";
import { gapLabel, getGaps, reducer, type Action } from "./model";
import { caseForRole, initialVisit } from "./visit";
import type { ApplicantType, Case, Gap } from "./types";

/** Older builds kept the whole case here. It is removed on load and never written again. */
const LEGACY_KEYS = ["batatis-web-case-v4", "batatis-web-case-v3"];

/** A cold visit starts empty. Nothing about a previous visitor's case is read or kept in this browser. */
function load() {
  try {
    for (const key of LEGACY_KEYS) sessionStorage.removeItem(key);
    clearEngineSession();
  } catch {
    /* storage unavailable: nothing to clear */
  }
  return initialVisit();
}

interface Store {
  c: Case;
  /** Workflow gaps (unconfirmed facts, unanswered cards) plus engine gaps when the route returns. */
  gaps: Gap[];
  /** Engine `info` items. Shown as notices, never counted as missing. */
  notices: string[];
  engineGaps: EngineGap[];
  /** idle = no review requested. engine = online result. browser = limited local check. */
  gapsSource: "idle" | "loading" | "engine" | "browser";
  gapsNote: string;
  /** Raw failure text for a collapsed technical detail. Not shown as the status line. */
  reviewDetail: string;
  /** True only after the latest save and online review both succeeded. */
  syncOk: boolean;
  saveStatus: SaveStatus;
  saveDetail: string;
  checkStatus: CheckState["status"];
  checkNote: string;
  checkDetail: string;
  checkedAt?: string;
  /** Explicit user action only; failed attempts require the labelled retry action. */
  requestCheck: (retry?: boolean) => Promise<string | null>;
  /** A failed lookup makes an earlier full-check receipt stale, never successful. */
  noteLookupFailure: (detail: string) => void;
  readSync: () => { saved: boolean; reviewed: boolean; detail: string };
  engineId: string | null;
  /** Increments after facts are pushed, so Section D can reload on the new facts. */
  factsEpoch: number;
  savedNote: string;
  phase: "who" | "case";
  /** Shown after Reset so the clear is visible. */
  resetNote: string;
  dispatch: Dispatch<Action>;
  saveDraft: () => Promise<string | null>;
  beginEmpty: (type: ApplicantType) => void;
  resetToWho: () => void;
  completenessRecord: CompletenessRecord | null;
  setCompletenessRecord: (record: CompletenessRecord | null) => void;
  /** Gap list from the latest review, including one that has not re-rendered yet. */
  readGaps: () => Gap[];
}

const Ctx = createContext<Store | null>(null);

const FIELD_HREF: Record<string, string> = {
  owner_name: "#/application?tab=A&focus=field-owner",
  representative: "#/application?tab=A&focus=field-representative",
  mailing_address: "#/application?tab=A&focus=field-mailingAddress",
  application_date: "#/application?tab=A&focus=field-date",
  civic_address: "#/application?tab=B&focus=field-municipalAddress",
  legal_description: "#/application?tab=B&focus=field-legalDescription",
  alternative_description: "#/application?tab=B&focus=field-alternative",
  scope: "#/application?tab=B&focus=field-scope",
  jurisdiction: "#/describe",
  rationale: "#/application?tab=alt&focus=field-rationale",
  risk_assessment: "#/application?tab=alt&focus=field-risk",
  mitigating_measures: "#/application?tab=alt&focus=field-mitigation",
  assumptions_and_limits: "#/application?tab=alt&focus=field-assumptions",
  maintenance_operation: "#/application?tab=alt&focus=field-maintenance",
  qualifications: "#/application?tab=alt&focus=field-qualifications",
  provisions: "#/code-check",
  professional_qualifications: "#/application?tab=alt&focus=field-qualifications",
  professional_requirement: "#/application?tab=D&focus=prof-role",
  responsible_professional: "#/application?tab=D&focus=prof-role",
};

const FIELD_ALIASES: Record<string, string[]> = {
  owner_name: ["owner_name", "owner", "section_a.owner_name"],
  owner: ["owner_name", "owner", "section_a.owner_name"],
  representative: ["representative", "section_a.representative"],
  mailing_address: ["mailing_address", "mailingAddress", "section_a.mailing_address"],
  mailingAddress: ["mailing_address", "mailingAddress"],
  application_date: ["application_date", "date"],
  date: ["application_date", "date"],
  civic_address: ["civic_address", "municipalAddress"],
  municipalAddress: ["civic_address", "municipalAddress"],
  legal_description: ["legal_description", "legalDescription"],
  legalDescription: ["legal_description", "legalDescription"],
  alternative_description: ["alternative_description", "alternative"],
  alternative: ["alternative_description", "alternative"],
  scope: ["scope"],
  "assembly.cavityRsi": ["assembly.cavityRsi"],
  "professional.role": ["professional.role", "professional_requirement", "responsible_professional"],
  professional_requirement: ["professional.role", "professional_requirement", "responsible_professional"],
  responsible_professional: ["professional.role", "professional_requirement", "responsible_professional"],
};

function aliasKeys(field: string): string[] {
  // Process gaps use the engine name; local facts use the process. prefix.
  const processField = field.replace(/^process\./, "");
  return FIELD_ALIASES[field] ?? [processField, `process.${processField}`];
}

function composeGaps(localCase: Case, source: Store["gapsSource"], engine: EngineGap[]): Gap[] {
  const local = getGaps(localCase);
  if (source !== "engine") return local;
  const seen = new Set<string>();
  const admin: Gap[] = [];
  for (const g of missingFromEngine(groupEvidenceGaps(engine))) {
    const keys = aliasKeys(g.field);
    if (keys.some((key) => seen.has(key))) continue;
    for (const key of keys) seen.add(key);
    const label = gapLabel(g.message, g.fix_hint);
    admin.push({
      id: g.id,
      severity: g.severity,
      label: isProfessionalHold(g) ? officerRoutedLabel(label) : label,
      href: hrefFor(g.field),
      field: g.field,
    });
  }
  const workflow = local.filter((g) => {
    // Local missing answers remain blocking while an older online review is displayed.
    if (!g.field) return true;
    return !aliasKeys(g.field).some((key) => seen.has(key));
  });
  return [...admin, ...workflow];
}

function hrefFor(field: string): string {
  if (FIELD_HREF[field]) return FIELD_HREF[field];
  if (field.startsWith("section_c") || field.startsWith("provisions")) return "#/section-c";
  if (field.startsWith("evidence") || field.startsWith("professional")) return "#/application?tab=D";
  return "#/describe";
}

export function CaseProvider({ children }: { children: ReactNode }) {
  const loaded = useMemo(load, []);
  const [phase, setPhase] = useState<"who" | "case">(loaded.phase);
  const [resetNote, setResetNote] = useState(loaded.note);
  const [c, reduce] = useReducer(reducer, loaded.case);
  const revision = useRef(0);
  const syncQueue = useRef<Promise<unknown>>(Promise.resolve());
  const [engineId, setEngineId] = useState<string | null>(null);
  const [factsEpoch, setFactsEpoch] = useState(0);
  const [engineGaps, setEngineGaps] = useState<EngineGap[]>([]);
  const [gapsSource, setGapsSource] = useState<Store["gapsSource"]>("idle");
  const [gapsNote, setGapsNote] = useState("");
  const [reviewDetail, setReviewDetail] = useState("");
  const [syncOk, setSyncOk] = useState(false);
  const syncState = useRef({ saved: false, reviewed: false, detail: "" });
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const [saveDetail, setSaveDetail] = useState("");
  const [savedNote, setSavedNote] = useState("");
  const [check, setCheck] = useState<CheckState>(newCheckState);
  const checkRef = useRef(check);
  const activeCheck = useRef<{ promise: Promise<string | null>; ctl: AbortController } | null>(null);
  const [completenessRecord, setCompletenessRecord] = useState<CompletenessRecord | null>(null);
  const latestGaps = useRef<Gap[]>([]);
  const latestCase = useRef(c);
  latestCase.current = c;
  const renderGeneration = engineGeneration();
  const renderRevision = revision.current;

  const publishCheck = useCallback((next: CheckState) => {
    checkRef.current = next;
    setCheck(next);
  }, []);

  // Stable dispatch prevents deterministic lookup effects from refiring on status updates.
  const dispatch = useCallback((action: Action) => {
    const derived = ["ackEvidenceDeletion", "notePractice", "noteSectionC", "bindOpenQuestion", "noteIdentifyQuestions"].includes(action.type);
    if (!derived) {
      revision.current += 1;
      activeCheck.current?.ctl.abort();
      syncState.current = { saved: false, reviewed: false, detail: "" };
      setSyncOk(false);
      setSaveStatus("unsaved");
      setSaveDetail("");
      setSavedNote("");
      setCompletenessRecord(null);
      setGapsSource("idle");
      setEngineGaps([]);
      setGapsNote("");
      setReviewDetail("");
      if (checkRef.current.status !== "not_requested") {
        publishCheck({ ...checkRef.current, status: "stale", note: "Draft changed. Check your updates when you’re ready.", detail: "" });
      }
    }
    latestCase.current = reducer(latestCase.current, action);
    reduce(action);
  }, [publishCheck]);

  function sync(_announce: boolean): Promise<string | null> {
    const token = renderGeneration;
    const version = renderRevision;
    const snapshot = c;
    const current = () => isEngineGeneration(token) && revision.current === version;
    const pending = syncQueue.current.catch(() => {}).then(() => performSync(snapshot, current));
    syncQueue.current = pending;
    return pending;
  }

  async function performSync(snapshot: Case, current: () => boolean): Promise<string | null> {
    if (!current()) return null;
    syncState.current = { ...syncState.current, saved: false, detail: "" };
    setSaveStatus("saving");
    setSavedNote("Saving…");
    setSaveDetail("");
    try {
      let id = await ensureEngineCase(snapshot.title, snapshot.authority);
      if (!current()) return null;
      setEngineId(id);
      id = await syncJurisdiction(id, snapshot.authority, snapshot.title);
      if (!current()) return null;
      const factError = await pushFacts(id, snapshot.facts);
      if (!current()) return null;
      const evidenceError = await pushListedEvidence(id, snapshot.listedEvidence ?? []);
      if (!current()) return null;
      const deleted = await pushDeletedEvidence(id, snapshot.deletedEvidence ?? []);
      if (!current()) return null;
      if (deleted.acked.length) dispatch({ type: "ackEvidenceDeletion", ids: deleted.acked });
      if (!factError) setFactsEpoch((n) => n + 1);
      const failure = factError ?? evidenceError ?? deleted.error;
      if (failure) throw new Error(failure);
      setSaveStatus("saved");
      setSavedNote("Saved for this visit");
      syncState.current = { ...syncState.current, saved: true, detail: "" };
      latestGaps.current = composeGaps(latestCase.current, gapsSource, engineGaps);
      return id;
    } catch (e) {
      if (!current()) return null;
      const message = e instanceof EngineError ? e.detail : e instanceof Error ? e.message : String(e);
      setEngineId(engineCaseId());
      setSaveStatus("failed");
      setSaveDetail(message);
      setSavedNote("Not saved. Keep this page open.");
      setSyncOk(false);
      syncState.current = { saved: false, reviewed: false, detail: message };
      setGapsSource("idle");
      setGapsNote("");
      setReviewDetail("");
      latestGaps.current = getGaps(latestCase.current);
      if (checkCurrent(checkRef.current, engineGeneration(), revision.current)) {
        publishCheck({ ...checkRef.current, status: "stale", note: "Save failed. Your earlier check is out of date.", detail: "" });
      }
      return null;
    }
  }

  function requestCheck(retry = false): Promise<string | null> {
    const token = renderGeneration;
    const version = renderRevision;
    if (!isEngineGeneration(token) || revision.current !== version) return Promise.resolve(null);
    if (activeCheck.current) return activeCheck.current.promise;
    const previous = checkRef.current;
    if (checkCurrent(previous, token, version)) return Promise.resolve(engineCaseId());
    if (previous.status === "unavailable" && !retry) return Promise.resolve(null);
    const ctl = new AbortController();
    const run: CheckState = { status: "running", generation: token, revision: version, attempt: previous.attempt + 1, note: "Saving before checking…", detail: "" };
    const current = () => isEngineGeneration(token) && revision.current === version && !ctl.signal.aborted;
    publishCheck(run);
    setSyncOk(false);
    syncState.current = { ...syncState.current, reviewed: false };
    setEngineGaps([]);
    setGapsSource("loading");
    setGapsNote("");
    setReviewDetail("");
    // One explicit run: acknowledged save → optional article ranking → deterministic gaps.
    // No fallback start, provider switch, automatic retry or download.
    const promise = (async () => {
      try {
        const id = await sync(true);
        if (!current()) return null;
        if (!id || !syncState.current.saved) throw new Error(syncState.current.detail || "Save was not acknowledged.");
        publishCheck({ ...run, note: "Checking your draft…" });
        const prose = c.description.trim();
        const result = prose ? await engine.identify(id, prose, [], ctl.signal) : null;
        if (!current()) return null;
        const got = await refreshGaps(id);
        if (!current()) return null;
        if (got.error) throw new Error(got.error);
        if (result?.mode === "cached_demo" || result?.cached === true) throw new Error("Only a cached demonstration is available. Use manual code search.");
        if (result) {
          const plan = planIdentify(result);
          // Publishing derived output is part of this run, not new user intent.
          applyIdentifyPlan((action) => {
            latestCase.current = reducer(latestCase.current, action);
            reduce(action);
          }, plan);
        }
        const combined = composeGaps(latestCase.current, "engine", got.gaps);
        latestGaps.current = combined;
        setEngineGaps(got.gaps);
        setGapsSource("engine");
        const note = combined.length ? "Check finished. Review the open items." : "Check finished. No missing items found.";
        publishCheck({ ...run, status: combined.length ? "needs_answers" : "ready", note, detail: "", completedAt: new Date().toLocaleString() });
        setSyncOk(true);
        syncState.current = { saved: true, reviewed: true, detail: "" };
        return id;
      } catch (e) {
        if (!current()) return null;
        const detail = e instanceof EngineError ? e.technical : e instanceof Error ? e.message : String(e);
        publishCheck({ ...run, status: "unavailable", note: "Check unavailable. Your work is still here.", detail });
        setGapsSource("browser");
        setReviewDetail(detail);
        setSyncOk(false);
        syncState.current = { ...syncState.current, reviewed: false, detail };
        latestGaps.current = getGaps(latestCase.current);
        return null;
      }
    })();
    const active = { promise, ctl };
    activeCheck.current = active;
    void promise.finally(() => { if (activeCheck.current === active) activeCheck.current = null; });
    return promise;
  }

  useEffect(() => {
    if (phase !== "case") return;
    if (!c.facts.length && !c.authority && !engineCaseId()) return;
    const handle = window.setTimeout(() => void sync(false), 500);
    return () => window.clearTimeout(handle);
    // Saving facts does not request identification or a full administrative check.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, c.facts, c.authority, c.title, c.listedEvidence, c.deletedEvidence]);

  function clearVisit(next: Case) {
    activeCheck.current?.ctl.abort();
    activeCheck.current = null;
    clearEngineSession();
    syncQueue.current = Promise.resolve();
    dispatch({ type: "reset", to: next });
    syncState.current = { saved: false, reviewed: false, detail: "" };
    latestGaps.current = getGaps(next);
    setEngineId(null);
    setFactsEpoch(0);
    setEngineGaps([]);
    setGapsSource("idle");
    setGapsNote("");
    setSyncOk(false);
    setSaveStatus("idle");
    setSaveDetail("");
    setSavedNote("");
    setReviewDetail("");
    setCompletenessRecord(null);
    publishCheck(newCheckState());
  }

  const gaps = useMemo(() => composeGaps(c, gapsSource, engineGaps), [c, engineGaps, gapsSource]);
  const notices = useMemo(() => (gapsSource === "engine" ? engineNotices(engineGaps) : []), [engineGaps, gapsSource]);
  useEffect(() => { latestGaps.current = gaps; }, [gaps]);

  const value: Store = {
    c, gaps, notices, engineGaps, gapsSource, gapsNote, reviewDetail, syncOk,
    saveStatus, saveDetail, savedNote,
    checkStatus: check.status, checkNote: check.note, checkDetail: check.detail,
    checkedAt: checkCurrent(check, engineGeneration(), revision.current) ? check.completedAt : undefined,
    requestCheck,
    noteLookupFailure: (detail) => {
      if (checkRef.current.status === "not_requested") return;
      activeCheck.current?.ctl.abort();
      publishCheck({ ...checkRef.current, status: "stale", note: "Latest lookup failed. Earlier results may be out of date.", detail });
      setSyncOk(false);
      syncState.current = { ...syncState.current, reviewed: false, detail };
    },
    readSync: () => syncState.current,
    engineId, factsEpoch, phase, resetNote, dispatch,
    saveDraft: () => sync(true),
    beginEmpty: (type) => {
      clearVisit(caseForRole(type, latestCase.current));
      setResetNote("");
      setPhase("case");
      location.hash = "#/describe";
    },
    completenessRecord, setCompletenessRecord,
    readGaps: () => latestGaps.current,
    resetToWho: () => {
      clearVisit(emptyCase("homebuilder"));
      setPhase("who");
      setResetNote("Cleared for this visit.");
      location.hash = "#/";
    },
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useCase(): Store {
  const s = useContext(Ctx);
  if (!s) throw new Error("useCase outside CaseProvider");
  return s;
}

export function resetCase(dispatch: Dispatch<Action>) {
  clearEngineSession();
  dispatch({ type: "reset", to: emptyCase("homebuilder") });
}
