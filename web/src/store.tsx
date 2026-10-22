import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, useState, type Dispatch, type ReactNode } from "react";
import { engine, EngineError, failureText, isCaseConflict, isCaseGone, type EngineGap } from "./api/client";
import type { IdentifyResult, IntakeResult, Question as PlanQuestion } from "./api/types.gen";
import { type CompletenessRecord, isProfessionalHold, officerRoutedLabel } from "./humanReview";
import { acknowledgedVersion, acknowledgeWrite, adoptEngineCase, clearEngineSession, CONFLICT_TEXT, engineCaseId, engineGeneration, evidenceFacts, isEngineGeneration, ensureEngineCase, needsReconcile, noteConflict, notePosted, pushDeletedEvidence, pushFacts, pushListedEvidence, reconcileEngineCase, refreshGaps, syncJurisdiction, type EvidenceOutcome } from "./api/sync";
import { engineNotices, groupEvidenceGaps, missingFromEngine, uploadMessage } from "./rules";
import { readDecisionBody, wireDecision } from "./identify";
import { asLocal } from "./intakeFields";
import { toViewRow } from "./api/sectionC";
import { getSession, updateSession } from "./calm/session";
import { checkCurrent, newCheckState, type CheckState, type SaveStatus } from "./checkState";
import { emptyCase } from "./intake";
import { gapLabel, getGaps, lookupBasis, reducer, type Action } from "./model";
import { caseForRole, initialVisit } from "./visit";
import type { ApplicantType, Candidate, CandidateAnswer, Case, Fact, Gap } from "./types";
import { useSectionC } from "./api/sectionC";
import { readSectionD, SectionDRecoveryError, type SectionDRead } from "./api/sectionD";
import { isProvision, reconcileSectionC, sameCards } from "./provisions";
import { caseFromEngine } from "./calm/openCase";
import { refreshCase, setChecklist } from "./calm/caseExtras";

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

/**
 * The reading after Start: intake (what we read and the plan), then code identification over the
 * stream. Visit-local progress only; the results live on the case (`Case.intake`, `Case.identify`).
 */
export interface Reading {
  intake: "idle" | "running" | "done" | "error";
  intakeNote: string;
  identify: "idle" | "running" | "done" | "error" | "skipped";
  identifyNote: string;
  /** Stream stages seen in the current identification, with their counts. */
  stages: Record<string, Record<string, unknown>>;
  /** A planner question, the scope click or a code card being written (its id). */
  busy: string | null;
}

const NO_READING: Reading = { intake: "idle", intakeNote: "", identify: "idle", identifyNote: "", stages: {}, busy: null };

/** The engine's role name for the applicant type (docs/api/intake.md `applicant_role`). */
function roleFor(type: ApplicantType): string {
  return type === "builder" ? "homebuilder" : type;
}

interface Store {
  reading: Reading;
  /** Read the description and attached PDFs (intake), then check the code (identify). Explicit: Start and Continue. */
  readDescription: () => Promise<void>;
  /** Upload PDFs held for this case (in the save queue, so intake can read them by id). */
  uploadFiles: () => Promise<void>;
  /** Run code identification again (the code-check card's Try again). */
  runIdentify: () => Promise<void>;
  /** Answer one planner question; "Not sure" is allowed. Resolves to an error text, or null when saved. */
  answerPlan: (q: PlanQuestion, answer: string) => Promise<string | null>;
  /** The redirect page: `true` is "This is a building-code question". */
  overrideScope: (buildingCode: boolean) => Promise<string | null>;
  /** Yes, No or Not sure on a code card; identified cards also go to the decision route. */
  decide: (candidate: Candidate, answer: CandidateAnswer) => Promise<string | null>;
  /**
   * One standing-package answer through the checklist answers route, with `expected_version`, in the
   * save queue. Resolves to an error text (a 409 says so and waits for `reloadChecklists`), or null.
   */
  answerChecklist: (checklistId: string, conditionId: string, state: "confirmed" | "not_yet" | "does_not_apply", reason?: string) => Promise<string | null>;
  /** The explicit reload after a conflict: adopt the saved version, then read the checklists again. */
  reloadChecklists: () => Promise<string | null>;
  sectionCLookup: ReturnType<typeof useSectionC>;
  retrySectionC: () => void;
  snapshotKey: string;
  loadSectionD: (retry?: boolean) => Promise<SectionDRead | null>;
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
  /** Back to an empty Start. `note` replaces "Cleared for this visit." (signed in, the old one stays in the list). */
  resetToWho: (note?: string) => void;
  /** Open a saved application (list row) as this visit's case. Resolves to an error text, or null when open. */
  openCase: (id: string, type: ApplicantType) => Promise<string | null>;
  completenessRecord: CompletenessRecord | null;
  setCompletenessRecord: (record: CompletenessRecord | null) => void;
  /** Gap list from the latest review, including one that has not re-rendered yet. */
  readGaps: () => Gap[];
}

const Ctx = createContext<Store | null>(null);

export const GONE_NOTE = "Case deleted or expired. Your answers stay here.";
const CONFLICT_NOTE = "Not saved. The saved case changed somewhere else.";

const FIELD_HREF: Record<string, string> = {
  owner_name: "#/application?tab=A&focus=field-owner",
  representative: "#/application?tab=A&focus=field-representative",
  mailing_address: "#/application?tab=A&focus=field-mailingAddress",
  application_date: "#/application?tab=A&focus=field-date",
  civic_address: "#/application?tab=B&focus=field-municipalAddress",
  legal_description: "#/application?tab=B&focus=field-legalDescription",
  alternative_description: "#/application?tab=B&focus=field-alternative",
  scope: "#/application?tab=B&focus=field-scope",
  jurisdiction: "#/describe?focus=authority",
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

/** The app link that fixes a field (engine gap field or a reviewer's ticked item). */
export function hrefFor(field: string): string {
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
  /** Like `revision`, but document saves and removals do not change it: they never alter the
   * Section D plan, so they must not rebuild (and re-save) it or replace the screen. */
  const planRevision = useRef(0);
  const syncQueue = useRef<Promise<unknown>>(Promise.resolve());
  const sectionDHold = useRef<{ generation: number; id: string; error: SectionDRecoveryError } | null>(null);
  /** The saved case was deleted or expired. Nothing is written again until Reset starts a new case. */
  const goneCase = useRef<string | null>(null);
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
  const [reading, setReadingState] = useState<Reading>(NO_READING);
  const setReading = (patch: Partial<Reading> | ((r: Reading) => Partial<Reading>)) =>
    setReadingState((r) => ({ ...r, ...(typeof patch === "function" ? patch(r) : patch) }));
  const latestGaps = useRef<Gap[]>([]);
  const latestCase = useRef(c);
  latestCase.current = c;
  const renderGeneration = engineGeneration();
  const renderRevision = revision.current;
  const renderPlanRevision = planRevision.current;
  const [lookupAttempt, setLookupAttempt] = useState(0);
  const sectionCLookup = useSectionC(c.candidates.filter(a => isProvision(a.provision)).map(a => ({ candidateId: a.id, provision: a.provision })), [], lookupAttempt);

  const publishCheck = useCallback((next: CheckState) => {
    checkRef.current = next;
    setCheck(next);
  }, []);

  // Stable dispatch prevents deterministic lookup effects from refiring on status updates.
  // File list changes and upload acknowledgements are not draft edits: files never travel in a save
  // (they upload on their own route) and do not change the gaps, so they must not mark the draft
  // unsaved or abort a running check.
  const dispatch = useCallback((action: Action) => {
    // A lookup that only attaches Section C rows (or re-orders the same cards, as it does right
    // after a saved case is opened) is derived data, not an edit: the draft stays saved.
    const derived = (action.type === "reconcileSectionC" && sameCards(reducer(latestCase.current, action).candidates, latestCase.current.candidates)) || [ "editEvidenceDraft", "addFiles", "removeFile", "setFileResult", "ackEvidence", "noteUnscopedEvidence", "notePractice", "noteSectionC", "bindOpenQuestion", "noteIdentifyQuestions", "noteIntake", "restoreIntake", "noteIntakeRecord", "adoptFacts", "noteIdentify"].includes(action.type);
    if (!derived) {
      revision.current += 1;
      if (action.type !== "saveEvidence" && action.type !== "removeEvidence") planRevision.current += 1;
      activeCheck.current?.ctl.abort();
      syncState.current = { saved: false, reviewed: false, detail: "" };
      setSyncOk(false);
      // A deleted or expired case stays reported as gone while the applicant keeps editing.
      if (!goneCase.current || goneCase.current !== engineCaseId()) {
        setSaveStatus("unsaved");
        setSaveDetail("");
        setSavedNote("");
      }
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

  useEffect(() => {
    if (sectionCLookup.source !== "live") return;
    if (reconcileSectionC(c, sectionCLookup.rows) !== c) dispatch({ type: "reconcileSectionC", rows: sectionCLookup.rows, basis: lookupBasis(c) });
  }, [sectionCLookup, c.candidates, dispatch]);

  /** Adopt an explicit fresh read's evidence ledger before writing again (derived, not new input). */
  function refreshed(saved: Parameters<typeof evidenceFacts>[0], snapshot: Case): Case {
    const action: Action = { type: "ackEvidence", facts: evidenceFacts(saved), refreshed: true };
    dispatch(action);
    return reducer(snapshot, action);
  }

  function applyEvidence(outcome: EvidenceOutcome, snapshot: Case): Case {
    const action: Action = { type: "ackEvidence", ...outcome };
    dispatch(action);
    return reducer(snapshot, action);
  }

  function loadSectionD(retry = false): Promise<SectionDRead | null> {
    const token = renderGeneration, version = renderPlanRevision;
    let snapshot = c;
    const candidateKey = JSON.stringify(c.candidates);
    const rowKey = JSON.stringify(c.sectionC);
    if (sectionCLookup.source === "loading") return Promise.resolve(null);
    if (sectionCLookup.source !== "live") return Promise.reject(new Error("Code references could not be loaded. Try the lookup again in Section C."));
    const current = () => isEngineGeneration(token) && planRevision.current === version && JSON.stringify(latestCase.current.candidates) === candidateKey && JSON.stringify(latestCase.current.sectionC) === rowKey;
    const pending = syncQueue.current.catch(() => {}).then(async () => {
      if (!current()) return null;
      const engineId = engineCaseId();
      if (engineId && goneCase.current === engineId) {
        throw new SectionDRecoveryError("missing", "case not found");
      }
      const hold = sectionDHold.current;
      if (hold?.generation === token && (hold.error.kind === "missing" || !retry)) throw hold.error;
      if (engineId && (hold?.generation === token || needsReconcile(engineId))) {
        if (!retry) throw new SectionDRecoveryError("conflict", "A versioned save is waiting for an explicit reconcile.");
        // Only the labelled retry may recover a conflict. Read the live case and adopt
        // its version before writing again; never replace a missing case with a new one.
        try { snapshot = refreshed(await reconcileEngineCase(engineId), snapshot); }
        catch (error) {
          if (isCaseGone(error)) {
            goneCase.current = engineId;
            const missing = new SectionDRecoveryError("missing", (error as EngineError).detail);
            sectionDHold.current = { generation: token, id: engineId, error: missing };
            throw missing;
          }
          throw error;
        }
        if (!current()) return null;
        sectionDHold.current = null;
      }
      const id = await performSync(snapshot, current);
      if (!id || !current()) {
        if (current()) {
          if (goneCase.current && goneCase.current === engineCaseId()) throw new SectionDRecoveryError("missing", "case not found");
          throw new Error(syncState.current.detail || "Save was not acknowledged.");
        }
        return null;
      }
      try { return await readSectionD(id, snapshot, current); }
      catch (error) {
        if (!current()) return null;
        if (isCaseConflict(error) || isCaseGone(error)) {
          const gone = isCaseGone(error);
          if (gone) goneCase.current = id;
          const recovery = new SectionDRecoveryError(gone ? "missing" : "conflict", (error as EngineError).detail);
          sectionDHold.current = { generation: token, id, error: recovery };
          throw recovery;
        }
        throw error;
      }
    });
    syncQueue.current = pending;
    return pending;
  }

  function sync(explicit: boolean): Promise<string | null> {
    const token = renderGeneration;
    const version = renderRevision;
    let snapshot = c;
    const current = () => isEngineGeneration(token) && revision.current === version;
    const pending = syncQueue.current.catch(() => {}).then(async () => {
      const id = engineCaseId();
      // "Try saving again" is the explicit reconcile for a conflicted save.
      if (explicit && id && needsReconcile(id) && goneCase.current !== id) {
        try { snapshot = refreshed(await reconcileEngineCase(id), snapshot); }
        catch (error) { if (isCaseGone(error)) goneCase.current = id; }
      }
      return performSync(snapshot, current);
    });
    syncQueue.current = pending;
    return pending;
  }

  async function performSync(snapshot: Case, current: () => boolean): Promise<string | null> {
    if (!current()) return null;
    const existing = engineCaseId();
    if (existing && goneCase.current === existing) {
      markGone("case not found");
      return null;
    }
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
      // One atomic write per listing, then removals. Only acknowledged revisions count as saved.
      const listed = await pushListedEvidence(id, snapshot.listedEvidence ?? []);
      if (!current()) return null;
      snapshot = applyEvidence(listed, snapshot);
      const deleted = listed.error ? null : await pushDeletedEvidence(id, snapshot.deletedEvidence ?? []);
      if (!current()) return null;
      if (deleted) snapshot = applyEvidence(deleted, snapshot);
      if (!factError) setFactsEpoch((n) => n + 1);
      // A refused listing is back in its form with a note; it is not a failed save of the case.
      const failure = factError ?? listed.error ?? deleted?.error;
      if (failure) throw new Error(failure);
      // A document staged after this snapshot is not saved yet; the next save sends it.
      const staged = latestCase.current.listedEvidence?.length || latestCase.current.deletedEvidence?.length;
      if (staged && !goneCase.current) {
        setSaveStatus("unsaved");
        setSavedNote("");
        return id;
      }
      setSaveStatus("saved");
      setSavedNote("Saved for this visit");
      syncState.current = { ...syncState.current, saved: true, detail: "" };
      latestGaps.current = composeGaps(latestCase.current, gapsSource, engineGaps);
      return id;
    } catch (e) {
      if (!current()) return null;
      const message = e instanceof EngineError ? e.detail : e instanceof Error ? e.message : String(e);
      setEngineId(engineCaseId());
      if (/case not found/i.test(message)) {
        goneCase.current = engineCaseId();
        markGone(message);
        return null;
      }
      setSaveStatus("failed");
      setSaveDetail(message);
      setSavedNote(isCaseConflict(e) ? CONFLICT_NOTE : "Not saved. Keep this page open.");
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

  /** Terminal for this case: keep every local answer, offer a draft download, never recreate. */
  function markGone(detail: string) {
    setSaveStatus("gone");
    setSaveDetail(detail);
    setSavedNote(GONE_NOTE);
    setSyncOk(false);
    syncState.current = { saved: false, reviewed: false, detail };
    setGapsSource("idle");
    latestGaps.current = getGaps(latestCase.current);
  }

  /** Every engine write runs on the save queue, so versions advance one at a time (docs/api-contract.md). */
  function enqueue<T>(work: () => Promise<T>): Promise<T> {
    const pending = syncQueue.current.catch(() => {}).then(work);
    syncQueue.current = pending;
    return pending;
  }

  /** Apply derived engine output without marking the draft unsaved. */
  function derive(action: Action) {
    dispatch(action);
  }

  /** PDFs held until the case exists: uploaded once, in this queue, so intake can read them. */
  async function uploadHeld(id: string, live: () => boolean): Promise<void> {
    const held = getSession().held;
    if (!held.length) return;
    updateSession((s) => ({ held: [], uploading: [...s.uploading, ...held.map((h) => h.id)] }));
    for (const { id: local, file } of held) {
      if (!live()) break;
      if (!latestCase.current.files.some((f) => f.id === local)) continue;
      try {
        const saved = await engine.upload(id, file);
        if (!live()) break;
        dispatch({ type: "setFileResult", id: local, error: null, read: true, pages: saved.pages, sha256: saved.sha256, engineId: saved.id });
      } catch (e) {
        const status = e instanceof EngineError ? e.status : 0;
        const detail = e instanceof EngineError ? e.detail : String(e);
        dispatch({ type: "setFileResult", id: local, error: uploadMessage(status, detail), unreachable: status === 0 });
      } finally {
        updateSession((s) => ({ uploading: s.uploading.filter((x) => x !== local) }));
      }
    }
  }

  /** Take an intake run's facts into the case, recorded as saved (the engine wrote them). */
  function adoptIntake(id: string, result: IntakeResult, text: string) {
    const before = latestCase.current;
    const previous = new Set(before.intake?.factIds ?? []);
    const removed = before.facts.filter((f) => previous.has(f.id) && f.status === "unconfirmed").map((f) => f.field);
    derive({ type: "noteIntake", result, text });
    const ids = new Set(result.facts.map((f) => f.id));
    const adopted = latestCase.current.facts.filter((f) => ids.has(f.id));
    notePosted(id, adopted, removed.filter((field) => !adopted.some((f) => f.field === field)));
  }

  /** Read facts an intake route wrote (answers, the scope click) back from the case, once. */
  async function adoptWritten(id: string, fields: string[], refs: string[], drop: (f: Fact) => boolean = () => false) {
    const saved = await engine.getCase(id);
    const known = new Set(latestCase.current.facts.map((f) => f.id));
    const facts: Fact[] = [];
    for (const field of fields) {
      const latest = [...saved.facts].reverse().find((f) => f.field === field);
      if (latest && refs.includes(latest.source.ref) && !known.has(latest.id)) facts.push(asLocal(latest) as Fact);
    }
    const dropIds = latestCase.current.facts.filter(drop).map((f) => f.id);
    if (facts.length || dropIds.length) derive({ type: "adoptFacts", facts, drop: dropIds });
    if (facts.length) notePosted(id, facts);
  }

  function intakeError(e: unknown, id: string): string {
    if (isCaseConflict(e)) {
      noteConflict(id);
      return CONFLICT_TEXT;
    }
    if (e instanceof EngineError && e.status === 0) return "Batatis could not be reached. Your description is still here.";
    return failureText(e);
  }

  /** Code identification over the stream, then the planner re-ranked against its candidates. Inside the queue. */
  async function identifyNow(id: string, live: () => boolean): Promise<void> {
    setReading({ identify: "running", identifyNote: "", stages: {} });
    let result: IdentifyResult;
    try {
      result = await engine.identify(
        id,
        latestCase.current.description.trim(),
        [],
        undefined,
        (stage, data) => { if (live()) setReading((r) => ({ stages: { ...r.stages, [stage]: data } })); },
        acknowledgedVersion(id) ?? undefined,
      );
    } catch (e) {
      if (!live()) return;
      setReading({ identify: "error", identifyNote: intakeError(e, id) });
      return;
    }
    if (!live()) return;
    acknowledgeWrite(id, result.case_version);
    derive({ type: "noteIdentify", result });
    setReading({ identify: "done" });
    try {
      const planned = await engine.intakePlan(id, acknowledgedVersion(id) ?? undefined);
      if (!live()) return;
      acknowledgeWrite(id, planned.case_version);
      derive({ type: "noteIntakeRecord", record: planned.record });
    } catch {
      /* the earlier plan stays; its questions are still valid */
    }
  }

  function readDescription(): Promise<void> {
    const token = engineGeneration();
    const live = () => isEngineGeneration(token);
    setReading({ ...NO_READING, intake: "running" });
    return enqueue(async () => {
      if (!live()) return;
      const snapshot = latestCase.current;
      const text = snapshot.description.trim();
      const id = await performSync(snapshot, live);
      if (!live()) return;
      if (!id) {
        setReading({ intake: "error", intakeNote: "Your description wasn’t saved, so it wasn’t read yet. Try again." });
        return;
      }
      await uploadHeld(id, live);
      if (!live()) return;
      const fileIds = latestCase.current.files.map((f) => f.engineId).filter((x): x is string => Boolean(x));
      let result: IntakeResult;
      try {
        result = await engine.intake(id, { text: text || undefined, file_ids: fileIds, role: roleFor(snapshot.applicantType), model: true, expected_version: acknowledgedVersion(id) ?? undefined });
      } catch (e) {
        if (!live()) return;
        setReading({ intake: "error", intakeNote: intakeError(e, id) });
        return;
      }
      if (!live()) return;
      acknowledgeWrite(id, result.case_version);
      adoptIntake(id, result, text);
      setReading({ intake: "done" });
      if (result.record.plan?.scope.status === "redirect") {
        setReading({ identify: "skipped" });
        return;
      }
      if (text) await identifyNow(id, live);
    });
  }

  function runIdentify(): Promise<void> {
    const token = engineGeneration();
    const live = () => isEngineGeneration(token);
    setReading({ identify: "running", identifyNote: "", stages: {} });
    return enqueue(async () => {
      const id = await performSync(latestCase.current, live);
      if (!id || !live()) {
        if (live()) setReading({ identify: "error", identifyNote: "Your draft wasn’t saved, so the code check didn’t run. Try again." });
        return;
      }
      await identifyNow(id, live);
    });
  }

  function answerPlan(q: PlanQuestion, answer: string): Promise<string | null> {
    const token = engineGeneration();
    const live = () => isEngineGeneration(token);
    setReading({ busy: q.id });
    return enqueue(async () => {
      try {
        const id = await performSync(latestCase.current, live);
        if (!live()) return null;
        if (!id) return "Your draft wasn’t saved, so the answer wasn’t either. Try again.";
        let result: IntakeResult;
        try {
          result = await engine.intakeAnswers(id, [{ question_id: q.id, answer }], acknowledgedVersion(id) ?? undefined);
        } catch (e) {
          if (e instanceof EngineError && e.status === 422) return `That answer couldn’t be read. ${e.detail.replace(/^./, (x) => x.toUpperCase())}.`.replace(/\.\.$/, ".");
          return intakeError(e, id);
        }
        if (!live()) return null;
        acknowledgeWrite(id, result.case_version);
        await adoptWritten(id, [q.field], ["intake answer"]);
        if (!live()) return null;
        derive({ type: "noteIntakeRecord", record: result.record });
        return null;
      } catch (e) {
        return failureText(e);
      } finally {
        if (live()) setReading({ busy: null });
      }
    });
  }

  function overrideScope(buildingCode: boolean): Promise<string | null> {
    const token = engineGeneration();
    const live = () => isEngineGeneration(token);
    setReading({ busy: "scope" });
    return enqueue(async () => {
      try {
        const id = await performSync(latestCase.current, live);
        if (!live()) return null;
        if (!id) return "Your draft wasn’t saved. Try again.";
        let result: IntakeResult;
        try {
          result = await engine.intakeScope(id, buildingCode, acknowledgedVersion(id) ?? undefined);
        } catch (e) {
          return intakeError(e, id);
        }
        if (!live()) return null;
        acknowledgeWrite(id, result.case_version);
        await adoptWritten(id, ["scope.redirect"], ["intake:scope", "intake:description"], (f) => f.field === "scope.redirect" && f.kind === "computed");
        if (!live()) return null;
        derive({ type: "noteIntakeRecord", record: result.record });
        // An override is an explicit "this is building code": identify the current description again, so a
        // result kept from an earlier description can never be decided on.
        if (result.record.plan?.scope.status !== "redirect" && (buildingCode || !latestCase.current.identify)) await identifyNow(id, live);
        return null;
      } catch (e) {
        return failureText(e);
      } finally {
        if (live()) setReading({ busy: null });
      }
    });
  }

  function decide(candidate: Candidate, answer: CandidateAnswer): Promise<string | null> {
    dispatch({ type: "answerCandidate", id: candidate.id, answer });
    if (candidate.suggestion !== "identify" || !/^\d/.test(candidate.provision)) return Promise.resolve(null);
    const token = engineGeneration();
    const live = () => isEngineGeneration(token);
    const provision = candidate.provision;
    return enqueue(async () => {
      const id = engineCaseId();
      if (!id || !live()) return null;
      try {
        const body = await engine.decide(id, provision, wireDecision(answer), undefined, acknowledgedVersion(id) ?? undefined);
        if (!live()) return null;
        acknowledgeWrite(id, body.case_version);
        derive({ type: "markDecisionPending", id: candidate.id, pending: false });
        const read = readDecisionBody(body, provision);
        if (read.row) derive({ type: "noteSectionC", rows: [toViewRow(read.row, candidate.id)] });
        if (answer === "not-sure" && read.openQuestionId) derive({ type: "bindOpenQuestion", candidateId: candidate.id, questionId: read.openQuestionId });
        derive({ type: "noteIdentify", result: body });
        // A decision moves the fork (any yes reads as the alternative-solution path); re-plan quietly.
        try {
          const planned = await engine.intakePlan(id, acknowledgedVersion(id) ?? undefined);
          if (live()) {
            acknowledgeWrite(id, planned.case_version);
            derive({ type: "noteIntakeRecord", record: planned.record });
          }
        } catch {
          /* no intake run on this case, or the plan is unchanged */
        }
        return null;
      } catch (e) {
        if (isCaseConflict(e)) noteConflict(id);
        // Keep the answer on screen but not as done: until the engine stores it, a No or Not sure would be lost
        // (Section D saves persist only Yes) and a Not sure would miss the officer's information request.
        if (live()) derive({ type: "markDecisionPending", id: candidate.id, pending: true });
        return e instanceof EngineError && e.status === 0 ? "Not saved yet: Batatis could not be reached. Your answer is kept here; answer again to resend it." : failureText(e);
      }
    });
  }

  function answerChecklist(checklistId: string, conditionId: string, state: "confirmed" | "not_yet" | "does_not_apply", reason?: string): Promise<string | null> {
    const token = engineGeneration();
    const live = () => isEngineGeneration(token);
    return enqueue(async () => {
      const id = await performSync(latestCase.current, live);
      if (!live()) return null;
      if (!id) return "Your draft wasn’t saved, so the answer wasn’t either. Try again.";
      const expected = acknowledgedVersion(id);
      if (needsReconcile(id) || expected === null) {
        noteConflict(id);
        return CONFLICT_TEXT;
      }
      try {
        const result = await engine.answerChecklist(id, checklistId, { condition_id: conditionId, state, reason: reason?.trim() || null, expected_version: expected });
        if (!live()) return null;
        acknowledgeWrite(id, result.case_version);
        setChecklist(id, result.checklist, result.case_version);
        return null;
      } catch (e) {
        if (isCaseConflict(e)) {
          noteConflict(id);
          return CONFLICT_TEXT;
        }
        if (e instanceof EngineError && e.status === 0) return "Not saved: Batatis could not be reached. Answer again to resend it.";
        return failureText(e);
      }
    });
  }

  function reloadChecklists(): Promise<string | null> {
    const token = engineGeneration();
    return enqueue(async () => {
      const id = engineCaseId();
      if (!id || !isEngineGeneration(token)) return null;
      try {
        if (needsReconcile(id) || acknowledgedVersion(id) === null) refreshed(await reconcileEngineCase(id), latestCase.current);
        return (await refreshCase(id)) ? null : "The checklist didn’t load. Try again.";
      } catch (e) {
        if (isCaseGone(e)) {
          goneCase.current = id;
          markGone((e as EngineError).detail);
        }
        return failureText(e);
      }
    });
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
        // A check never doubles as a conflict reconcile; that stays its own labelled action.
        const id = await sync(false);
        if (!current()) return null;
        if (!id || !syncState.current.saved) throw new Error(syncState.current.detail || "Save was not acknowledged.");
        publishCheck({ ...run, note: "Checking your draft…" });
        // Code identification runs once after Start (readDescription), not on every check: the
        // check is the save plus the administrative gap list.
        const got = await refreshGaps(id);
        if (!current()) return null;
        if (got.error) throw new Error(got.error);
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
        const stale = isCaseConflict(e) && /updated concurrently/i.test(detail);
        if (stale) {
          const id = engineCaseId();
          if (id) noteConflict(id);
        }
        publishCheck({ ...run, status: "unavailable", note: stale ? CONFLICT_NOTE : "Check unavailable. Your work is still here.", detail });
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
    goneCase.current = null;
    sectionDHold.current = null;
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
    setReadingState(NO_READING);
    publishCheck(newCheckState());
  }

  const gaps = useMemo(() => composeGaps(c, gapsSource, engineGaps), [c, engineGaps, gapsSource]);
  const notices = useMemo(() => (gapsSource === "engine" ? engineNotices(engineGaps) : []), [engineGaps, gapsSource]);
  useEffect(() => { latestGaps.current = gaps; }, [gaps]);

  const value: Store = {
    reading, readDescription, runIdentify,
    uploadFiles: () => {
      const token = engineGeneration();
      return enqueue(async () => {
        const id = engineCaseId();
        if (id) await uploadHeld(id, () => isEngineGeneration(token));
      });
    }, answerPlan, overrideScope, decide, answerChecklist, reloadChecklists,
    sectionCLookup, retrySectionC: () => setLookupAttempt(n => n + 1),
    snapshotKey: `${renderGeneration}:${renderPlanRevision}:${JSON.stringify(c.candidates)}:${JSON.stringify(c.sectionC)}:${sectionCLookup.source}`,
    loadSectionD,
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
    resetToWho: (note = "Cleared for this visit.") => {
      clearVisit(emptyCase("homebuilder"));
      setPhase("who");
      setResetNote(note);
      location.hash = "#/";
    },
    openCase: async (id, type) => {
      let saved;
      try {
        saved = await engine.getCase(id);
      } catch (e) {
        return e instanceof EngineError ? (isCaseGone(e) ? "That application was deleted or has expired." : e.detail) : "The application did not open.";
      }
      // Same reset as Start over, then adopt the saved version and answers so the next save
      // sends only what the applicant changes.
      clearVisit(caseFromEngine(saved, type));
      adoptEngineCase(saved);
      setEngineId(saved.id);
      // What intake read and the last code identification come back as they were stored (no provider call).
      const [intake, identify] = await Promise.all([
        engine.storedIntake(saved.id).catch(() => null),
        engine.storedIdentify(saved.id).catch(() => null),
      ]);
      if (intake) derive({ type: "restoreIntake", result: intake, text: latestCase.current.description.trim() });
      if (identify) derive({ type: "noteIdentify", result: identify });
      setReadingState({ ...NO_READING, intake: intake ? "done" : "idle", identify: identify ? "done" : "idle" });
      setSaveStatus("saved");
      setSavedNote("Saved");
      syncState.current = { saved: true, reviewed: false, detail: "" };
      setResetNote("");
      setPhase("case");
      return null;
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
