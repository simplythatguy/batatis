import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, useState, type Dispatch, type ReactNode } from "react";
import { engine, EngineError, failureText, isCaseConflict, isCaseGone, type EngineGap, type UploadedFile } from "./api/client";
import type { Case as EngineCase, IdentifyResult, IntakeResult, Question as PlanQuestion } from "./api/types.gen";
import { type CompletenessRecord } from "./humanReview";
import { acknowledgedVersion, acknowledgeWrite, adoptEngineCase, clearEngineSession, CONFLICT_TEXT, engineCaseId, engineGeneration, evidenceFacts, isEngineGeneration, ensureEngineCase, isReadOnlyCase, needsReconcile, noteConflict, notePosted, noteShownSelection, pushDeletedEvidence, pushFacts, pushListedEvidence, pushSelectedArticles, reconcileEngineCase, refreshGaps, selectionKey, syncJurisdiction, type EvidenceOutcome } from "./api/sync";
import { engineNotices, factSignature, groupEvidenceGaps, missingFromEngine, uploadMessage } from "./rules";
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
import { caseFromEngine, latestFacts, openedCase, reviewedDescription, selectedArticles } from "./calm/openCase";
import { normalizeTitle, saveTitle, TITLE_EMPTY, titleError } from "./calm/rename";
import { refreshCase, resetExtras, setChecklist } from "./calm/caseExtras";
import { accounts } from "./api/accounts";
import { accountSession, getAccountState, patchApplication, refreshApplications, subscribeAccount, useAccount } from "./calm/account";
import { readOnly } from "./calm/applications";

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
  /** Upload supporting bytes inside the save queue; binding is a separate atomic evidence save. */
  uploadEvidenceFile: (file: File) => Promise<UploadedFile>;
  /** Run code identification again (the code-check card's Try again). */
  runIdentify: () => Promise<void>;
  /** Answer one planner question; "Not sure" is allowed. Resolves to an error text, or null when saved. */
  answerPlan: (q: PlanQuestion, answer: string) => Promise<string | null>;
  /** Rename the open application (saved, then shown in the header and the list). Resolves to an error text, or null. */
  renameCase: (title: string) => Promise<string | null>;
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
  /** Selection and sign-in identity, including reopening the same saved case; draft edits keep it. */
  applicationIdentity: string;
  /** Status of the saved record; available even before the account list finishes loading. */
  applicationStatus: string | null;
  /** Increments after facts are pushed, so Section D can reload on the new facts. */
  factsEpoch: number;
  savedNote: string;
  phase: "who" | "case";
  /** Shown after Reset so the clear is visible. */
  resetNote: string;
  dispatch: Dispatch<Action>;
  saveDraft: () => Promise<string | null>;
  /** Save this displayed revision and submit it in the same queue. Rejects unacknowledged or stale work. */
  submitDraft: (caseId: string) => Promise<void>;
  submitting: boolean;
  /** The saved revision is on its way to the authority; local edits pause until the response. */
  submissionDispatched: boolean;
  beginEmpty: (type: ApplicantType) => void;
  /** Back to an empty Start. `note` replaces "Cleared for this visit." (signed in, the old one stays in the list). */
  resetToWho: (note?: string) => void;
  /**
   * Open a saved application (list row) as this visit's case. Resolves to an error text, or null when open.
   * An open overtaken by a newer open, Start over, an edit of the open draft or another sign-in changes
   * nothing and resolves to a note that the current answers stay open (the shell's own guard decides
   * whether to show it).
   */
  openCase: (id: string, type: ApplicantType) => Promise<string | null>;
  /** Refresh the selected case only while its acknowledged draft and account are still current. */
  refreshCurrentCase: () => Promise<string | null>;
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

function composeGaps(localCase: Case, source: Store["gapsSource"], engine: EngineGap[], savedOnly = false): Gap[] {
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
      label,
      href: hrefFor(g.field),
      field: g.field,
      submissionBlocking: g.submission_blocking,
    });
  }
  // A locked record is checked as stored. Reconstructed browser questions cannot add export
  // requirements to a server record the applicant cannot edit.
  if (savedOnly) return admin;
  const workflow = local.filter((g) => {
    // The current engine screen owns professional duties, including a recorded
    // officer resolution. Local heuristics cannot restore a requirement it resolved.
    if (["needs-professional", "practice-unknown", "professional-not-engaged"].includes(g.id)) return false;
    // Local missing answers remain blocking while an older online review is displayed.
    if (!g.field) return true;
    return !aliasKeys(g.field).some((key) => seen.has(key));
  });
  return [...admin, ...workflow];
}

/** The code cards on a case, ignoring order. */
const selectionSet = (c: Case) => selectionKey([...selectedArticles(c)].sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0)));

/** The app link that fixes a field (engine gap field or a reviewer's ticked item). */
export function hrefFor(field: string): string {
  if (FIELD_HREF[field]) return FIELD_HREF[field];
  if (field.startsWith("section_c") || field.startsWith("provisions")) return "#/section-c";
  if (field.startsWith("evidence") || field.startsWith("professional")) return "#/application?tab=D";
  return "#/describe";
}

export function CaseProvider({ children }: { children: ReactNode }) {
  const account = useAccount();
  const loaded = useMemo(load, []);
  const [phase, setPhase] = useState<"who" | "case">(loaded.phase);
  const [resetNote, setResetNote] = useState(loaded.note);
  const [c, reduce] = useReducer(reducer, loaded.case);
  const revision = useRef(0);
  /** Like `revision`, but document saves and removals do not change it: they never alter the
   * Section D plan, so they must not rebuild (and re-save) it or replace the screen. */
  const planRevision = useRef(0);
  const syncQueue = useRef<Promise<unknown>>(Promise.resolve());
  const activeSubmit = useRef<{ generation: number; session: number; revision: number; caseId: string; dispatched: boolean; ctl: AbortController; promise: Promise<void> } | null>(null);
  const caseRead = useRef(0);
  const caseOpening = useRef(false);
  const caseReads = useRef(new Set<{ session: number; ctl: AbortController }>());
  const activeRefresh = useRef<{ token: number; session: number; id: string; promise: Promise<string | null> } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submissionDispatched, setSubmissionDispatched] = useState(false);
  useEffect(() => {
    const stop = subscribeAccount(() => {
      for (const read of caseReads.current) if (read.session !== accountSession()) read.ctl.abort();
      if (activeSubmit.current && activeSubmit.current.session !== accountSession()) {
        activeSubmit.current.ctl.abort();
        activeSubmit.current = null;
        setSubmitting(false);
        setSubmissionDispatched(false);
      }
    });
    return () => { stop(); for (const read of caseReads.current) read.ctl.abort(); activeSubmit.current?.ctl.abort(); };
  }, []);
  const sectionDHold = useRef<{ generation: number; id: string; error: SectionDRecoveryError } | null>(null);
  /** The saved case was deleted or expired. Nothing is written again until Reset starts a new case. */
  const goneCase = useRef<string | null>(null);
  const [engineId, setEngineId] = useState<string | null>(null);
  const openedStatus = useRef<string | null>(null);
  const [savedStatus, setSavedStatus] = useState<string | null>(null);
  const applicationStatus = account.applications?.find((app) => app.id === engineId)?.status ?? savedStatus;
  const [savedOnlyGaps, setSavedOnlyGaps] = useState(false);
  const [factsEpoch, setFactsEpoch] = useState(0);
  const [remoteEpoch, setRemoteEpoch] = useState(0);
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
  const savedSelection = useRef<string | null>(null);
  const refreshedSelection = useRef(new Map<string, string>());
  latestCase.current = c;
  const renderGeneration = engineGeneration();
  const renderSession = accountSession();
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
    // On a read-only case the lookup's expansion of an article is display only: never an unsaved edit.
    const readOnlyCase = isReadOnlyCase(engineCaseId());
    const derived = (action.type === "reconcileSectionC" && (readOnlyCase || sameCards(reducer(latestCase.current, action).candidates, latestCase.current.candidates))) || [ "editEvidenceDraft", "addFiles", "removeFile", "setFileResult", "ackEvidence", "noteUnscopedEvidence", "notePractice", "noteProfessionalWork", "noteSectionC", "bindOpenQuestion", "noteIdentifyQuestions", "noteIntake", "restoreIntake", "restoreReviewQuestions", "noteIntakeRecord", "adoptFacts", "noteIdentify", "renameCase"].includes(action.type);
    // A read-only application's code cards are not the applicant's to change (the deck and library are locked;
    // the references screen's Remove is not): refused, so the screen keeps showing what is saved.
    if (!derived && readOnlyCase && action.type !== "reset" && selectionKey(selectedArticles(reducer(latestCase.current, action))) !== selectionKey(selectedArticles(latestCase.current))) return;
    // Disabled controls cover mounted callers; this also covers document shortcuts and late
    // input callbacks. Keep derived acknowledgements and explicit case/session resets working.
    const transition = activeSubmit.current;
    const editing = !derived || ["editEvidenceDraft", "addFiles", "removeFile"].includes(action.type);
    if (action.type !== "reset" && editing && transition?.dispatched
      && isEngineGeneration(transition.generation) && transition.caseId === engineCaseId()) return;
    if (action.type === "answerCandidate" || action.type === "removeCandidate") refreshedSelection.current.delete(action.id);
    if (action.type === "addCandidate") refreshedSelection.current.delete(action.candidate.id);
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
    const before = latestCase.current;
    latestCase.current = reducer(before, action);
    // Derived output that adds or removes a code card (an identification) is saved like an edit, so a
    // switch saves it first. A re-order alone is saved quietly by the next save.
    if (derived && readOnlyCase) noteShownSelection(engineCaseId(), selectedArticles(before), selectedArticles(latestCase.current));
    else if (derived && selectionSet(latestCase.current) !== selectionSet(before) && (!goneCase.current || goneCase.current !== engineCaseId())) {
      // Unsaved for the autosave, a switch and Submit alike (autosave runs only while something is unsaved).
      syncState.current = { ...syncState.current, saved: false };
      setSaveStatus("unsaved");
    }
    reduce(action);
  }, [publishCheck]);

  useEffect(() => {
    if (sectionCLookup.source !== "live") return;
    // A refresh adopts the saved cards as-is. Looking up their wording must not rewrite that
    // selection; an explicit answer releases its card for the normal sentence expansion.
    const preserve = selectedArticles(c).filter(a => refreshedSelection.current.get(a.id) === selectionKey([a])).map(a => a.id);
    if (reconcileSectionC(c, sectionCLookup.rows, preserve) !== c) dispatch({ type: "reconcileSectionC", rows: sectionCLookup.rows, basis: lookupBasis(c), preserve });
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
    const current = () => isEngineGeneration(token) && revision.current === version && accountSession() === renderSession;
    const pending = syncQueue.current.catch(() => {}).then(async () => {
      if (!current()) return null;
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

  function lockedCase(id: string) {
    return readOnly(getAccountState().applications?.find((app) => app.id === id)?.status ?? openedStatus.current);
  }

  async function performSync(snapshot: Case, live: () => boolean, signal?: AbortSignal): Promise<string | null> {
    const current = () => live() && !signal?.aborted && accountSession() === renderSession && isEngineGeneration(renderGeneration);
    if (!current()) return null;
    const existing = engineCaseId();
    // Autosave and downloads must never write a submitted/final record. The read-only
    // check below reads the server directly and does not use this save acknowledgement.
    if (existing && lockedCase(existing)) return existing;
    if (existing && goneCase.current === existing) {
      markGone("case not found");
      return null;
    }
    syncState.current = { ...syncState.current, saved: false, detail: "" };
    setSaveStatus("saving");
    setSavedNote("Saving…");
    setSaveDetail("");
    try {
      // Only a name the applicant chose is sent; a placeholder leaves the case for the engine to name.
      let id = await ensureEngineCase(snapshot.titleKept ? snapshot.title : null, snapshot.authority, signal);
      if (!current()) return null;
      setEngineId(id);
      id = await syncJurisdiction(id, snapshot.authority, snapshot.title, signal);
      if (!current()) return null;
      const factError = await pushFacts(id, snapshot.facts, signal);
      if (!current()) return null;
      // The code-check cards, answers and pending state: a snapshot that never confirms a reference.
      const selectionError = await pushSelectedArticles(id, selectedArticles(snapshot), signal);
      if (!current()) return null;
      if (!selectionError) savedSelection.current = selectionKey(selectedArticles(snapshot));
      // One atomic write per listing, then removals. Only acknowledged revisions count as saved.
      const listed = await pushListedEvidence(id, snapshot.listedEvidence ?? [], signal);
      if (!current()) return null;
      snapshot = applyEvidence(listed, snapshot);
      const deleted = listed.error ? null : await pushDeletedEvidence(id, snapshot.deletedEvidence ?? [], signal);
      if (!current()) return null;
      if (deleted) snapshot = applyEvidence(deleted, snapshot);
      if (!factError) setFactsEpoch((n) => n + 1);
      // A refused listing is back in its form with a note; it is not a failed save of the case.
      const failure = factError ?? selectionError ?? listed.error ?? deleted?.error;
      if (failure) throw new Error(failure);
      // A document staged after this snapshot is not saved yet; the next save sends it.
      const staged = latestCase.current.listedEvidence?.length || latestCase.current.deletedEvidence?.length
        || (!isReadOnlyCase(id) && selectionKey(selectedArticles(latestCase.current)) !== selectionKey(selectedArticles(snapshot)));
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

  /**
   * Rename the open application. Saved through PATCH /cases/{id}/title in the save queue (it moves
   * the case version), then shown in the header and the list. Before the case exists the name is kept
   * and sent when it is created. Resolves to an error text, or null when saved.
   */
  function renameCase(raw: string): Promise<string | null> {
    const title = normalizeTitle(raw);
    if (!title) return Promise.resolve(TITLE_EMPTY);
    const token = engineGeneration();
    return enqueue(async () => {
      const id = engineCaseId();
      if (!isEngineGeneration(token)) return null;
      if (!id) {
        derive({ type: "renameCase", title });
        return null;
      }
      try {
        const saved = await saveTitle(id, title);
        // Another application was opened meanwhile: the list row is updated, this case is not.
        if (!isEngineGeneration(token) || engineCaseId() !== id) return null;
        acknowledgeWrite(id, saved.version);
        derive({ type: "renameCase", title: saved.title ?? title });
        return null;
      } catch (e) {
        return isEngineGeneration(token) ? titleError(e) : null;
      }
    });
  }

  /** The save and server transition share a queue: no pending or later save can race submission. */
  function submitDraft(caseId: string): Promise<void> {
    const token = renderGeneration, version = renderRevision, session = renderSession;
    const user = account.user;
    const ctl = new AbortController();
    const current = () => !ctl.signal.aborted && isEngineGeneration(token) && revision.current === version && engineCaseId() === caseId
      && accountSession() === session && getAccountState().phase === "signed-in" && Boolean(user) && getAccountState().user === user;
    const changed = () => new Error("The application or sign-in changed while submitting. Review your latest answers and submit again.");
    const pending = activeSubmit.current;
    if (pending) {
      return pending.generation === token && pending.session === session && pending.revision === version && pending.caseId === caseId
        ? pending.promise : Promise.reject(changed());
    }
    if (!current()) return Promise.reject(changed());
    setSubmitting(true);
    const promise = enqueue(async () => {
      if (!current()) throw changed();
      // A submit click never silently reconciles a conflict or retries a failed in-flight save.
      const unsaved = () => new Error(goneCase.current === caseId ? GONE_NOTE
        : `Your latest answers were not saved, so the application was not submitted. ${needsReconcile(caseId) ? CONFLICT_TEXT : syncState.current.detail || "Try saving again first."}`);
      if (goneCase.current === caseId || needsReconcile(caseId) || (!syncState.current.saved && syncState.current.detail)) throw unsaved();
      // Earlier queued intake/decision writes may have adopted acknowledged facts without an edit.
      // Read their result here, while the same user revision is still current.
      const id = await performSync(latestCase.current, current, ctl.signal);
      if (!current()) throw changed();
      if (id !== caseId || !syncState.current.saved || needsReconcile(caseId)) throw unsaved();
      const expected = acknowledgedVersion(caseId);
      if (expected === null) throw unsaved();
      const transition = activeSubmit.current;
      if (!transition) throw changed();
      // Saving can still be cancelled by a new edit. Once dispatched, freezing the displayed
      // revision is necessary: ignoring a response cannot undo a committed server transition.
      transition.dispatched = true;
      setSubmissionDispatched(true);
      let submitted;
      try {
        submitted = await accounts.submit(caseId, expected, ctl.signal);
      } catch (error) {
        if (!current()) throw changed();
        if (error instanceof EngineError && isCaseConflict(error) && /saved application changed|updated concurrently/i.test(error.technical)) {
          // The pinned transition lost to another writer. Recovery uses the existing explicit Save retry.
          noteConflict(caseId);
          setSaveStatus("failed");
          setSavedNote(CONFLICT_NOTE);
          setSaveDetail(CONFLICT_TEXT);
          setSyncOk(false);
          syncState.current = { saved: false, reviewed: false, detail: CONFLICT_TEXT };
          if (checkRef.current.status !== "not_requested") {
            publishCheck({ ...checkRef.current, status: "stale", note: "The saved case changed. Check again after saving.", detail: "" });
          }
        }
        throw error;
      }
      if (!current()) throw changed();
      acknowledgeWrite(caseId, submitted.version);
      patchApplication(caseId, { status: "submitted", submitted_at: submitted.submitted_at, submission_number: submitted.submission_number,
        expires_at: submitted.expires_at, reviewer: submitted.claim ? { name: submitted.claim.reviewer_name } : null, unread_messages: 0 });
      void refreshApplications();
    });
    const active = { generation: token, session, revision: version, caseId, dispatched: false, ctl, promise };
    activeSubmit.current = active;
    const settled = () => {
      if (activeSubmit.current !== active) return;
      activeSubmit.current = null;
      setSubmitting(false);
      setSubmissionDispatched(false);
    };
    void promise.then(settled, settled);
    return promise;
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
        // Keep the answer on screen but not as done (pending, saved with the selection): until the engine stores the
        // decision, it is not a confirmed reference (Section D sends only an acknowledged Yes) and a Not sure would
        // miss the officer's information request. Answering again resends it.
        if (live()) derive({ type: "markDecisionPending", id: candidate.id, pending: true });
        return e instanceof EngineError && e.status === 0 ? "Not saved yet: Batatis could not be reached. Your answer is kept here; answer again to resend it." : failureText(e);
      }
    });
  }

  /** Queue a versioned checklist answer and update shared extras, preserving conflict and missing-case feedback. */
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
        if (!live()) return null;                     // the applicant moved on: a late reply never touches the new case
        if (isCaseConflict(e)) {
          noteConflict(id);
          return CONFLICT_TEXT;
        }
        if (isCaseGone(e)) {
          goneCase.current = id;
          markGone((e as EngineError).detail);
        }
        if (e instanceof EngineError && e.status === 0) return "Not saved: Batatis could not be reached. Answer again to resend it.";
        return failureText(e);
      }
    });
  }

  /** Reconcile a stale case and reload its extras, marking a deleted or expired case as gone. */
  function reloadChecklists(): Promise<string | null> {
    const token = engineGeneration();
    return enqueue(async () => {
      const id = engineCaseId();
      if (!id || !isEngineGeneration(token)) return null;
      try {
        if (needsReconcile(id) || acknowledgedVersion(id) === null) {
          const saved = await reconcileEngineCase(id);
          if (!isEngineGeneration(token)) return null;  // the applicant moved on during the reconcile
          refreshed(saved, latestCase.current);
        }
        let gone: unknown = null;
        const ok = await refreshCase(id, (e) => { if (isCaseGone(e)) gone = e; });
        if (!isEngineGeneration(token)) return null;
        if (gone) throw gone;                         // a deleted or expired case is marked gone, not retried
        return ok ? null : "The checklist didn’t load. Try again.";
      } catch (e) {
        if (!isEngineGeneration(token)) return null;  // a reply for the case the applicant left
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
    const savedId = engineCaseId();
    const savedOnly = Boolean(savedId && lockedCase(savedId));
    if (!savedOnly && checkCurrent(previous, token, version)) return Promise.resolve(savedId);
    if (previous.status === "unavailable" && !retry) return Promise.resolve(null);
    const ctl = new AbortController();
    const run: CheckState = { status: "running", generation: token, revision: version, attempt: previous.attempt + 1, note: savedOnly ? "Checking the saved application…" : "Saving before checking…", detail: "" };
    const current = () => isEngineGeneration(token) && revision.current === version && !ctl.signal.aborted;
    publishCheck(run);
    setSyncOk(false);
    syncState.current = { ...syncState.current, reviewed: false };
    setEngineGaps([]);
    setGapsSource("loading");
    setGapsNote("");
    setReviewDetail("");
    setSavedOnlyGaps(savedOnly);
    // One explicit run: acknowledged draft save or locked-record read → deterministic gaps.
    // No fallback start, provider switch, automatic retry or download.
    const promise = (async () => {
      try {
        // A check never doubles as a conflict reconcile; that stays its own labelled action.
        const before = savedOnly && savedId ? await engine.getCase(savedId, ctl.signal) : null;
        if (!current()) return null;
        if (before && !readOnly(before.status)) throw new Error("The application was returned. Reopen it to make corrections before checking again.");
        const id = before?.id ?? await sync(false);
        if (!current()) return null;
        if (!id || (!savedOnly && !syncState.current.saved)) throw new Error(syncState.current.detail || "Save was not acknowledged.");
        publishCheck({ ...run, note: savedOnly ? "Reading the server’s administrative items…" : "Checking your draft…" });
        // Code identification runs once after Start (readDescription), not on every check: the
        // check is the save plus the administrative gap list.
        const got = await refreshGaps(id);
        if (!current()) return null;
        if (got.error) throw new Error(got.error);
        if (before) {
          const after = await engine.getCase(id, ctl.signal);
          if (!current()) return null;
          if (after.version !== before.version || after.status !== before.status) throw new Error("The saved application changed during the check. Check it again.");
        }
        const combined = composeGaps(latestCase.current, "engine", got.gaps, savedOnly);
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

  const selection = useMemo(() => selectionKey(selectedArticles(c)), [c.candidates]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (phase !== "case") return;
    if (syncState.current.saved) return;
    if (!c.facts.length && !c.authority && !engineCaseId()) return;
    const handle = window.setTimeout(() => { if (!syncState.current.saved) void sync(false); }, 500);
    return () => window.clearTimeout(handle);
    // Saving facts does not request identification or a full administrative check.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, c.facts, c.authority, c.title, c.listedEvidence, c.deletedEvidence, selection]);

  /** Reset the save session, case extras and visible request state before adopting another case. */
  function clearVisit(next: Case) {
    savedSelection.current = null;
    refreshedSelection.current.clear();
    for (const read of caseReads.current) read.ctl.abort();
    caseReads.current.clear();
    caseRead.current++;
    caseOpening.current = false;
    activeRefresh.current = null;
    activeCheck.current?.ctl.abort();
    activeCheck.current = null;
    activeSubmit.current?.ctl.abort();
    activeSubmit.current = null;
    setSubmitting(false);
    setSubmissionDispatched(false);
    clearEngineSession();
    resetExtras();                                   // the next case never renders with the last case's rules, checklists or pack
    goneCase.current = null;
    sectionDHold.current = null;
    syncQueue.current = Promise.resolve();
    dispatch({ type: "reset", to: next });
    syncState.current = { saved: false, reviewed: false, detail: "" };
    latestGaps.current = getGaps(next);
    setEngineId(null);
    setFactsEpoch(0);
    setRemoteEpoch(0);
    setEngineGaps([]);
    openedStatus.current = null;
    setSavedStatus(null);
    setSavedOnlyGaps(false);
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

  async function readSavedCase(id: string, signal?: AbortSignal) {
    const saved = await engine.getCase(id, signal);
    // Both records are embedded in this exact case revision. Later route reads can observe
    // another writer's newer run and combine its questions with this snapshot's older facts.
    const record = saved.intake;
    const pointers = new Set(record?.pointers.map(p => p.fact_id));
    const intake: IntakeResult | null = record ? {
      case_id: saved.id, case_version: saved.version, record,
      facts: saved.facts.filter(f => pointers.has(f.id)),
    } : null;
    const reviewedText = await reviewedDescription(saved, record ?? null);
    return { saved, intake, identify: saved.identify, reviewedText };
  }

  /** `next` is the opened case built in one step (openedCase): intake, code cards and their saved selection included. */
  function showSavedCase(read: Awaited<ReturnType<typeof readSavedCase>>, next: Case) {
    clearVisit(next);
    // Adopt the saved version, answers and shown code cards so the next save sends only what the applicant changes.
    adoptEngineCase(read.saved, selectedArticles(next));
    savedSelection.current = selectionKey(read.saved.selected_articles ?? selectedArticles(next));
    openedStatus.current = read.saved.status;
    setSavedStatus(read.saved.status);
    patchApplication(read.saved.id, { status: read.saved.status, authority: read.saved.authority });
    setEngineId(read.saved.id);
    setReadingState({ ...NO_READING, intake: read.intake ? "done" : "idle", identify: read.identify ? "done" : "idle" });
    setSaveStatus("saved");
    setSavedNote("Saved");
    syncState.current = { saved: true, reviewed: false, detail: "" };
    setResetNote("");
    setPhase("case");
  }

  const keptDraft = "Your local answers stay open. Save them before refreshing this application.";
  function cleanForRefresh() {
    const draft = latestCase.current;
    return syncState.current.saved && !activeSubmit.current && !caseOpening.current
      && !draft.listedEvidence?.length && !draft.deletedEvidence?.length
      && !Object.keys(draft.evidenceDrafts ?? {}).length
      && !getSession().held.length && !getSession().uploading.length;
  }

  /** A background read never acts as Save/reconcile and never blocks subsequent local saves. */
  function refreshCurrentCase(): Promise<string | null> {
    const id = engineCaseId(), token = engineGeneration(), session = accountSession();
    if (!id || getAccountState().phase !== "signed-in") return Promise.resolve(null);
    const pending = activeRefresh.current;
    if (pending?.token === token && pending.session === session && pending.id === id) return pending.promise;
    if (!cleanForRefresh() || needsReconcile(id)) return Promise.resolve(keptDraft);
    const version = revision.current, request = caseRead.current, queue = syncQueue.current;
    const readScope = { session, ctl: new AbortController() };
    caseReads.current.add(readScope);
    const current = () => isEngineGeneration(token) && engineCaseId() === id && accountSession() === session
      && revision.current === version && caseRead.current === request && syncQueue.current === queue
      && cleanForRefresh() && !needsReconcile(id);
    const promise = (async () => {
      try {
        const read = await readSavedCase(id, readScope.ctl.signal);
        if (!current()) return keptDraft;
        // Even without an applicant edit, another acknowledged operation may have advanced it.
        const known = acknowledgedVersion(id);
        if (known !== null && read.saved.version < known) return keptDraft;
        const changed = known !== read.saved.version;
        const derived = changed ? await Promise.all([
          engine.gaps(id, readScope.ctl.signal).catch(() => null),
          engine.professional(id, readScope.ctl.signal).catch(() => null),
          engine.sectionDIssues(id, readScope.ctl.signal).catch(() => null),
        ]) : null;
        if (!current()) return keptDraft;
        if (derived) {
          // These read-only routes lack a revision envelope. One bounded confirming read
          // prevents publishing them with a different content revision; there is no retry loop.
          const verified = await engine.getCase(id, readScope.ctl.signal);
          if (!current()) return keptDraft;
          if (verified.version !== read.saved.version) return "The saved application changed during refresh. Select it again to refresh.";
        }
        const next = caseFromEngine(read.saved, latestCase.current.applicantType);
        const signatures = (facts: Fact[]) => JSON.stringify(facts.map(f => [f.field, factSignature(f)]).sort());
        const local = latestCase.current;
        const restored = openedCase(read.saved, local.applicantType, read);
        const sameContent = local.title === next.title && local.authority === next.authority
          && signatures(latestFacts(local.facts as EngineCase["facts"])) === signatures(next.facts)
          && JSON.stringify(local.intake?.record ?? null) === JSON.stringify(read.saved.intake)
          && JSON.stringify(local.identify ?? null) === JSON.stringify(read.saved.identify)
          && JSON.stringify(local.candidates.filter(a => a.answer === "yes" && isProvision(a.provision)).map(a => a.provision).sort())
            === JSON.stringify([...read.saved.provisions].sort())
          // Compare the acknowledged wire snapshot: read-only lookup expansion is display only.
          && savedSelection.current === selectionKey(read.saved.selected_articles ?? selectedArticles(restored));
        // Officer status/thread updates preserve the active card, files and unfinished controls.
        if (sameContent) {
          // The shown cards are the acknowledged selection (nothing unsaved here): never re-sent over another tab's.
          adoptEngineCase(read.saved, selectedArticles(local));
          // The return decision can introduce answer cards without changing any facts.
          // Reconcile only these cards so the active applicant controls stay mounted.
          derive({ type: "restoreReviewQuestions", questions: next.questions });
        }
        else {
          showSavedCase(read, { ...restored, files: local.files });
          refreshedSelection.current = new Map(selectedArticles(restored).map(a => [a.id, selectionKey([a])]));
        }
        openedStatus.current = read.saved.status;
        setSavedStatus(read.saved.status);
        patchApplication(read.saved.id, { status: read.saved.status, authority: read.saved.authority });
        const savedOnly = readOnly(read.saved.status);
        setSavedOnlyGaps(savedOnly);
        if (derived) {
          const [gaps, professional, issues] = derived;
          activeCheck.current?.ctl.abort();
          activeCheck.current = null;
          setCompletenessRecord(null);
          setSyncOk(false);
          syncState.current = { ...syncState.current, reviewed: false };
          setEngineGaps(gaps ?? []);
          setGapsSource(gaps ? "engine" : "idle");
          setGapsNote("");
          setReviewDetail("");
          const practice = professional?.required === "yes" || issues?.some(issue => issue.practice_of_engineering.value === true)
            ? true : professional?.required === "no" && issues !== null && issues.every(issue => issue.practice_of_engineering.value === false) ? false : "unknown";
          derive({ type: "notePractice", value: practice });
          latestGaps.current = composeGaps(latestCase.current, gaps ? "engine" : "idle", gaps ?? [], savedOnly);
          if (checkRef.current.status !== "not_requested") {
            publishCheck({ ...checkRef.current, status: "stale", note: "The saved application changed. Check again when you’re ready.", detail: "" });
          }
          // A server determination can change without a fact/provision edit. Section D must
          // discard its old guidance while the active question/editor and file labels stay put.
          setRemoteEpoch(n => n + 1);
          setFactsEpoch(n => n + 1);
        }
        return null;
      } catch (e) {
        if (!current()) return keptDraft;
        if (isCaseGone(e)) {
          goneCase.current = id;
          markGone("case not found");
          return "That application is no longer available. Your local answers stay open.";
        }
        return e instanceof EngineError ? e.detail : "The application could not be refreshed.";
      } finally {
        caseReads.current.delete(readScope);
      }
    })();
    const active = { token, session, id, promise };
    activeRefresh.current = active;
    void promise.finally(() => { if (activeRefresh.current === active) activeRefresh.current = null; });
    return promise;
  }

  const gaps = useMemo(() => composeGaps(c, gapsSource, engineGaps, savedOnlyGaps), [c, engineGaps, gapsSource, savedOnlyGaps]);
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
    },
    uploadEvidenceFile: (file) => {
      const token = engineGeneration();
      const live = () => isEngineGeneration(token);
      return enqueue(async () => {
        if (!live()) throw new Error("The application changed while uploading.");
        const id = await performSync(latestCase.current, live);
        if (!id || !live()) throw new Error(syncState.current.detail || "Save the application before uploading.");
        const saved = await engine.upload(id, file);
        if (!live()) throw new Error("The application changed while uploading.");
        return saved;
      });
    }, answerPlan, overrideScope, decide, answerChecklist, reloadChecklists, renameCase,
    sectionCLookup, retrySectionC: () => setLookupAttempt(n => n + 1),
    snapshotKey: `${renderGeneration}:${renderPlanRevision}:${remoteEpoch}:${JSON.stringify(c.candidates)}:${JSON.stringify(c.sectionC)}:${sectionCLookup.source}`,
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
    engineId, applicationIdentity: JSON.stringify([renderGeneration, renderSession, engineId]), applicationStatus, factsEpoch, phase, resetNote, dispatch,
    saveDraft: () => sync(true),
    refreshCurrentCase,
    submitDraft, submitting, submissionDispatched,
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
      // A newer open, a reset (Start over, New application), an edit of the open draft or another sign-in
      // while this one is still reading wins: the late read is dropped and the draft open now stays as it is.
      const token = engineGeneration(), version = revision.current, session = accountSession();
      const request = ++caseRead.current;
      const readScope = { session, ctl: new AbortController() };
      caseReads.current.add(readScope);
      caseOpening.current = true;
      const current = () => isEngineGeneration(token) && revision.current === version
        && accountSession() === session && caseRead.current === request;
      try {
        const read = await readSavedCase(id, readScope.ctl.signal);
        if (!current()) return "The application or sign-in changed while opening. Your current answers stay open.";
        showSavedCase(read, openedCase(read.saved, type, read));
        return null;
      } catch (e) {
        if (!current()) return "The application or sign-in changed while opening. Your current answers stay open.";
        return e instanceof EngineError ? (isCaseGone(e) ? "That application was deleted or has expired." : e.detail) : "The application did not open.";
      } finally {
        caseReads.current.delete(readScope);
        if (caseRead.current === request) caseOpening.current = false;
      }
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
