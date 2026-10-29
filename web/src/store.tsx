import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, useState, type Dispatch, type ReactNode } from "react";
import { engine, EngineError, failureText, isCaseConflict, isCaseGone, type EngineGap, type UploadedFile } from "./api/client";
import type { Case as EngineCase, DraftingRecord, IntakeResult, Question as PlanQuestion, RequirementRecord } from "./api/types.gen";
import { acceptedApplicantFact, applicantDraftInputKey, unchangedDraftField, type ApplicantDraftActivity, type ApplicantDraftCommand } from "./applicantDrafts";
import { forApplicant, type CompletenessRecord } from "./humanReview";
import { hrefFor } from "./gapHref";
import { acknowledgedVersion, acknowledgeWrite, adoptEngineCase, clearEngineSession, CONFLICT_TEXT, engineCaseId, engineGeneration, isEngineGeneration, ensureEngineCase, isReadOnlyCase, needsReconcile, noteConflict, notePosted, noteShownSelection, pushDeletedEvidence, pushDraft, pushListedEvidence, refreshGaps, selectionKey, type EvidenceOutcome } from "./api/sync";
import { engineNotices, factSignature, groupEvidenceGaps, missingFromEngine, uploadMessage } from "./rules";
import { readDecisionBody, wireDecision } from "./identify";
import { asLocal } from "./intakeFields";
import { picturesAllowed } from "./intakeView";
import { toViewRow } from "./api/sectionC";
import { getSession, resetSavedSession, subscribeSession, updateSavedSession, type Session } from "./calm/session";
import { applicantDraft, draftAccount, restoreApplicantDraft, sessionDraft } from "./calm/applicantDraft";
import { questionDrafts } from "./calm/questionDrafts";
import { checkCurrent, newCheckState, type CheckState, type SaveStatus } from "./checkState";
import { emptyCase } from "./intake";
import { gapLabel, getGaps, lookupBasis, reducer, type Action } from "./model";
import { caseForRole, initialVisit } from "./visit";
import type { ApplicantType, Candidate, CandidateAnswer, Case, Fact, Gap } from "./types";
import { useSectionC } from "./api/sectionC";
import { readSectionD, SectionDRecoveryError, type SectionDRead } from "./api/sectionD";
import { isProvision, reconcileSectionC, sameCards } from "./provisions";
import { caseFromEngine, latestFacts, openedCase, reviewedDescription, selectedArticles } from "./calm/openCase";
import { requirementDecision, type RequirementAnswer, type RequirementDecision } from "./calm/requirements";
import { normalizeTitle, saveTitle, TITLE_EMPTY, titleError } from "./calm/rename";
import { refreshCase, resetExtras, setChecklist, setIdentify } from "./calm/caseExtras";
import { accounts } from "./api/accounts";
import { accountSession, getAccountState, patchApplication, refreshApplications, subscribeAccount, useAccount } from "./calm/account";
import { readOnly } from "./calm/applications";
import { activeJob, isApplicantJob, latestJob, observeJob, type CaseJob } from "./api/jobs";
import { PROCESS_FACT, PROCESS_FIELDS } from "./model";
import { acknowledgeJobCase, acknowledgedAuthority, acknowledgedDraft, acknowledgedDraftKey, acknowledgedEvidenceFacts, acknowledgedSelectionKey, draftKey, pendingFactChanges, pushReconciledDraft } from "./api/sync";
import { registerSignOutGuard, resetSignOutStatus } from "./calm/auth/signOutGuard";
import { applicationEditsPaused, pauseApplicationEdits, useApplicationEditsPaused, whenEditsResume } from "./calm/applicationEditing";
import { reconcileDraft, type ReconciliationChoices, type ReconciliationInput, type SaveConflictReview } from "./calm/reconcileDraft";

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
 * The reading after Start: intake (what we read and the plan), then code identification.
 * Progress rejoins durable jobs; results live on the case (`Case.intake`, `Case.identify`).
 */
export interface Reading {
  intake: "idle" | "running" | "done" | "error";
  intakeNote: string;
  identify: "idle" | "running" | "done" | "error" | "skipped";
  identifyNote: string;
  /** Legacy synchronous identification stage details, when supplied. */
  stages: Record<string, Record<string, unknown>>;
  /** A planner question, the scope click or a code card being written (its id). */
  busy: string | null;
  intakeJob?: CaseJob;
  identifyJob?: CaseJob;
}

const NO_READING: Reading = { intake: "idle", intakeNote: "", identify: "idle", identifyNote: "", stages: {}, busy: null };

/** The engine's role name for the applicant type (docs/api/intake.md `applicant_role`). */
function roleFor(type: ApplicantType | null): string | null {
  return type === "builder" ? "homebuilder" : type;
}

interface Store {
  drafting: DraftingRecord | null;
  draftingStale: boolean;
  draftActivity: ApplicantDraftActivity;
  draftingError: string;
  /** Each resolves true once the server committed this command; false when it failed or did not run. */
  generateApplicantDrafts: () => Promise<boolean>;
  decideApplicantDraft: (draftId: string, decision: "accept" | "reject") => Promise<boolean>;
  retryApplicantDrafts: () => Promise<void>;
  reading: Reading;
  /** Read the description and attached PDFs (intake), then check the code (identify). Explicit: Start and Continue. */
  readDescription: () => Promise<void>;
  /** Upload PDFs held for this case (in the save queue, so intake can read them by id). */
  uploadFiles: () => Promise<void>;
  /** Upload a file whose upload failed again; a later file is read as soon as it is uploaded. */
  retryUpload: (fileId: string) => Promise<void>;
  /** Remove a file and the unconfirmed answers that came only from it; returns how many were removed. */
  removeFile: (fileId: string) => number;
  /** Upload supporting bytes inside the save queue; binding is a separate atomic evidence save. */
  uploadEvidenceFile: (file: File, itemId?: string) => Promise<UploadedFile>;
  /** Run code identification again (the code-check card's Try again). */
  runIdentify: () => Promise<void>;
  cancelReadingJob: (kind: CaseJob["kind"]) => Promise<string | null>;
  /** Answer one planner question; "Not sure" is allowed. Resolves to an error text, or null when saved. */
  answerPlan: (q: PlanQuestion, answer: string) => Promise<string | null>;
  /** Rename the open application (saved, then shown in the header and the list). Resolves to an error text, or null. */
  renameCase: (title: string) => Promise<string | null>;
  /** The redirect page: `true` is "This is a building-code question". */
  overrideScope: (buildingCode: boolean) => Promise<string | null>;
  /** Yes, No or Not sure on a code card; identified cards also go to the decision route. */
  decide: (candidate: Candidate, answer: CandidateAnswer) => Promise<string | null>;
  /**
   * The applicant's one-line departure from a card they answered Yes: records the benchmark, the
   * Section C row and the varied requirement in one call. Resolves to an error text, or null.
   */
  confirmDeparture: (candidate: Candidate, departure: string) => Promise<string | null>;
  /**
   * One requirement-ledger answer (`include` / `exclude` / `review`): applicability only, decided
   * independently of any departure. Resolves to an error text, or null when the engine stored it.
   */
  decideRequirement: (requirement: RequirementRecord, answer: RequirementAnswer, reason?: string) => Promise<string | null>;
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
  saveConflict: boolean;
  saveConflictReview: SaveConflictReview;
  reviewSaveConflict: () => Promise<string | null>;
  saveReviewedChanges: (choices: ReconciliationChoices) => Promise<string | null>;
  closeSaveConflictReview: () => void;
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
  /** Run another versioned write (history, signatures, consent) in the save queue, so versions advance one at a time. */
  queueWrite: <T>(work: () => Promise<T>) => Promise<T>;
  /** Save this displayed revision and submit it in the same queue. Rejects unacknowledged or stale work. */
  submitDraft: (caseId: string) => Promise<void>;
  submitting: boolean;
  /** The saved revision is on its way to the authority; local edits pause until the response. */
  submissionDispatched: boolean;
  beginEmpty: (type: ApplicantType | null) => void;
  /** Back to an empty Start. `note` replaces "Cleared for this visit." (signed in, the old one stays in the list). */
  resetToWho: (note?: string) => void;
  /**
   * Open a saved application (list row) as this visit's case. Resolves to an error text, or null when open.
   * An open overtaken by a newer open, Start over, an edit of the open draft or another sign-in changes
   * nothing and resolves to a note that the current answers stay open (the shell's own guard decides
   * whether to show it).
   */
  openCase: (id: string, type: ApplicantType | null) => Promise<string | null>;
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
    const label = forApplicant(gapLabel(g.message, g.fix_hint));
    admin.push({
      id: g.id,
      severity: g.severity,
      label,
      href: hrefFor(g.field, g.section),
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



/** How many times a superseded code check starts again by itself before the applicant is asked. */
const IDENTIFY_RERUNS = 3;
export function CaseProvider({ children }: { children: ReactNode }) {
  const editsPaused = useApplicationEditsPaused();
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
  const activeSave = useRef<{ token: number; session: number; promise: Promise<string | null> } | null>(null);
  const restoring = useRef(false);
  const phaseRef = useRef(phase);
  phaseRef.current = phase;
  const evidenceUploads = useRef(new Map<string, { file: File; itemId?: string; saved?: UploadedFile }>());
  const mounted = useRef(true);
  const jobObservers = useRef(new Map<string, { ctl: AbortController; stop: () => void }>());
  const currentJobs = useRef(new Map<CaseJob["kind"], string>());
  const completedJobs = useRef(new Set<string>());
  /** Code checks started again because the answers changed mid-check, per case; reset when one finishes. */
  const identifyReruns = useRef(new Map<string, number>());
  const jobRequestKeys = useRef(new Map<string, { key: string; replaces?: string }>());
  const jobActionNotes = useRef(new Map<string, string>());
  const activeSubmit = useRef<{ generation: number; session: number; revision: number; caseId: string; dispatched: boolean; ctl: AbortController; promise: Promise<void> } | null>(null);
  const activeDraftWrite = useRef<{ session: number; ctl: AbortController; promise: Promise<boolean> } | null>(null);
  const draftAccountSession = useRef(accountSession());
  const draftRetry = useRef<ApplicantDraftCommand | null>(null);
  const [draftRecord, setDraftRecord] = useState<{ record: DraftingRecord; basis: string } | null>(null);
  const [draftActivity, setDraftActivity] = useState<ApplicantDraftActivity>({ kind: "idle" });
  const [draftingError, setDraftingError] = useState("");
  const caseRead = useRef(0);
  const caseOpening = useRef(false);
  const caseReads = useRef(new Set<{ session: number; ctl: AbortController }>());
  const activeRefresh = useRef<{ token: number; session: number; id: string; promise: Promise<string | null> } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submissionDispatched, setSubmissionDispatched] = useState(false);
  useEffect(() => {
    mounted.current = true;
    let principal = draftAccount(getAccountState().user);
    let session = accountSession();
    const stop = subscribeAccount(() => {
      for (const read of caseReads.current) if (read.session !== accountSession()) read.ctl.abort();
      if (activeSubmit.current && activeSubmit.current.session !== accountSession()) {
        activeSubmit.current.ctl.abort();
        activeSubmit.current = null;
        setSubmitting(false);
        setSubmissionDispatched(false);
      }
      if (draftAccountSession.current !== accountSession()) {
        draftAccountSession.current = accountSession();
        activeDraftWrite.current?.ctl.abort();
        activeDraftWrite.current = null;
        draftRetry.current = null;
        setDraftRecord(null);
        setDraftActivity({ kind: "idle" });
        setDraftingError("");
      }
      const next = draftAccount(getAccountState().user);
      if (session !== accountSession()) {
        session = accountSession();
        for (const observer of jobObservers.current.values()) { observer.ctl.abort(); observer.stop(); }
        jobObservers.current.clear();
        const id = engineCaseId();
        if (next === principal && id) {
          if (!syncState.current.saved) dirty();
          void rejoinJobs(id);
        }
      }
      if (next !== principal) {
        // Signing in or finishing onboarding keeps what the visitor typed on Start; any other account change clears it.
        const { draft, draftFiles, draftFilesLost, startRequested } = getSession();
        const [before, beforeRole] = principal ? JSON.parse(principal) as [string, string | null] : [null, null];
        const [after] = next ? JSON.parse(next) as [string] : [null];
        const frontDoor = after !== null && (before === null || (before === after && beforeRole === null));
        const keep = frontDoor ? { draft, draftFiles, draftFilesLost, startRequested } : {};
        principal = next;
        resetSignOutStatus();
        questionDrafts.selectAccount(next);
        clearVisit(emptyCase("homebuilder"), keep);
        setPhase("who");
        if (!next) {
          sessionStorage.removeItem("batatis-open-application");
          sessionStorage.removeItem("batatis-open-application-owner");
        }
      }
    });
    return () => {
      mounted.current = false;
      stop(); for (const read of caseReads.current) read.ctl.abort(); activeSubmit.current?.ctl.abort(); activeDraftWrite.current?.ctl.abort();
      for (const observer of jobObservers.current.values()) { observer.ctl.abort(); observer.stop(); }
      jobObservers.current.clear();
    };
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
  const [editEpoch, setEditEpoch] = useState(0);
  const [saveDetail, setSaveDetail] = useState("");
  const [savedNote, setSavedNote] = useState("");
  const [saveConflictReview, setSaveConflictReview] = useState<SaveConflictReview>({ kind: "closed" });
  const conflictRead = useRef<Promise<string | null> | null>(null);
  const recovery = useRef<{
    token: number; session: number; id: string; revision: number; input: ReconciliationInput;
    read: Awaited<ReturnType<typeof readSavedCase>>;
  } | null>(null);
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

  const dirty = useCallback(() => {
    revision.current += 1;
    setEditEpoch(n => n + 1);
    activeCheck.current?.ctl.abort();
    syncState.current = { saved: false, reviewed: false, detail: "" };
    setSyncOk(false);
    setSaveStatus("unsaved");
    setSaveDetail("");
    setSavedNote("");
    if (checkRef.current.status !== "not_requested") publishCheck({ ...checkRef.current, status: "stale", note: "Draft changed. Check your updates when you’re ready.", detail: "" });
  }, [publishCheck]);

  useEffect(() => {
    let before = JSON.stringify(sessionDraft(getSession()));
    const stopSession = subscribeSession(() => {
      const next = JSON.stringify(sessionDraft(getSession()));
      if (!restoring.current && phaseRef.current === "case" && next !== before) dirty();
      before = next;
    });
    const stopText = questionDrafts.subscribe(scope => {
      if (restoring.current || phaseRef.current !== "case") return;
      const current = questionDrafts.scope(draftAccount(getAccountState().user), engineGeneration(), engineCaseId());
      if (scope === current) dirty();
    });
    const unload = (event: BeforeUnloadEvent) => {
      const s = getSession();
      if (!syncState.current.saved && phaseRef.current === "case" || s.held.length || s.uploading.length
        || s.draft.trim() || s.draftFiles.length || evidenceUploads.current.size) {
        event.preventDefault(); event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", unload);
    return () => { stopSession(); stopText(); window.removeEventListener("beforeunload", unload); };
  }, [dirty]);

  useEffect(() => registerSignOutGuard(async () => {
    const session = accountSession(), token = engineGeneration();
    const current = () => mounted.current && accountSession() === session && isEngineGeneration(token);
    const prepared = getSession();
    if (phaseRef.current !== "case") return prepared.draft.trim() || prepared.draftFiles.length
      ? "Your unfinished application isn’t saved. Start it before signing out; your text and files stay here." : null;
    const id = await enqueue(() => {
      if (!current()) return Promise.resolve(null);
      const files = getSession();
      if (syncState.current.saved && !files.held.length && !files.uploading.length && !evidenceUploads.current.size) return Promise.resolve(engineCaseId());
      return flushCurrent(current);
    });
    return id && current() && syncState.current.saved ? null
      : `Your latest changes aren’t saved, so you’re still signed in. ${syncState.current.detail || "Keep this page open and try saving again."}`;
  }), []);

  // Stable dispatch keeps deterministic lookups separate from applicant edits and upload acknowledgements.
  const dispatch = useCallback((action: Action, origin: "applicant" | "save" = "applicant") => {
    // A lookup that only attaches Section C rows (or re-orders the same cards, as it does right
    // after a saved case is opened) is derived data, not an edit: the draft stays saved.
    // On a read-only case the lookup's expansion of an article is display only: never an unsaved edit.
    const readOnlyCase = isReadOnlyCase(engineCaseId());
    const derived = (action.type === "reconcileSectionC" && (readOnlyCase || sameCards(reducer(latestCase.current, action).candidates, latestCase.current.candidates))) || [ "adoptCase", "setFileResult", "ackEvidence", "noteUnscopedEvidence", "notePractice", "noteProfessionalWork", "noteSectionC", "bindOpenQuestion", "noteIdentifyQuestions", "noteIntake", "restoreIntake", "restoreReviewQuestions", "noteIntakeRecord", "adoptFacts", "adoptApplicantDraft", "noteIdentify", "renameCase"].includes(action.type);
    // A read-only application's code cards are not the applicant's to change (the deck and library are locked;
    // the references screen's Remove is not): refused, so the screen keeps showing what is saved.
    if (!derived && readOnlyCase && action.type !== "reset" && selectionKey(selectedArticles(reducer(latestCase.current, action))) !== selectionKey(selectedArticles(latestCase.current))) return;
    // Disabled controls cover mounted callers; this also covers document shortcuts and late
    // input callbacks. Keep derived acknowledgements and explicit case/session resets working.
    const transition = activeSubmit.current;
    const editing = !derived || ["editEvidenceDraft", "addFiles", "removeFile"].includes(action.type);
    if (editing && origin === "applicant" && applicationEditsPaused()) return;
    if (action.type !== "reset" && editing && transition?.dispatched
      && isEngineGeneration(transition.generation) && transition.caseId === engineCaseId()) return;
    if (action.type === "answerCandidate" || action.type === "removeCandidate") refreshedSelection.current.delete(action.id);
    if (action.type === "addCandidate") refreshedSelection.current.delete(action.candidate.id);
    if (action.type === "editEvidenceDraft" && action.patch.fileRef === null) {
      for (const [id, pending] of evidenceUploads.current) if (pending.itemId === action.itemId) evidenceUploads.current.delete(id);
    }
    if (!derived || action.type === "adoptApplicantDraft") {
      // An accepted draft is already saved on the server: it changes the answers without making them unsaved.
      if (derived) revision.current += 1;
      else dirty();
      if (!derived && !["editEvidenceDraft", "reset"].includes(action.type)) {
        setReading(r => ({
          ...(r.intakeJob && ["failed", "cancelled", "superseded"].includes(r.intakeJob.state) ? { intake: "idle", intakeJob: undefined, intakeNote: "" } : {}),
          ...(r.identifyJob && ["failed", "cancelled", "superseded"].includes(r.identifyJob.state) ? { identify: "idle", identifyJob: undefined, identifyNote: "" } : {}),
        }));
      }
      if (!["saveEvidence", "removeEvidence", "editEvidenceDraft", "addFiles", "removeFile"].includes(action.type)) planRevision.current += 1;
      activeCheck.current?.ctl.abort();
      syncState.current = { saved: derived ? syncState.current.saved : false, reviewed: false, detail: "" };
      setSyncOk(false);
      // A deleted or expired case stays reported as gone while the applicant keeps editing.
      if (!derived && (!goneCase.current || goneCase.current !== engineCaseId())) {
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
  }, [publishCheck, dirty]);

  useEffect(() => {
    if (sectionCLookup.source !== "live") return;
    // A refresh adopts the saved cards as-is. Looking up their wording must not rewrite that
    // selection; an explicit answer releases its card for the normal sentence expansion.
    const preserve = selectedArticles(c).filter(a => refreshedSelection.current.get(a.id) === selectionKey([a])).map(a => a.id);
    if (reconcileSectionC(c, sectionCLookup.rows, preserve) !== c) dispatch({ type: "reconcileSectionC", rows: sectionCLookup.rows, basis: lookupBasis(c), preserve });
  }, [sectionCLookup, c.candidates, dispatch]);

  function applyEvidence(outcome: EvidenceOutcome, snapshot: Case): Case {
    const action: Action = { type: "ackEvidence", ...outcome };
    dispatch(action);
    return reducer(snapshot, action);
  }

  function loadSectionD(retry = false): Promise<SectionDRead | null> {
    const token = renderGeneration, version = renderPlanRevision;
    const snapshot = c;
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
        throw new SectionDRecoveryError("conflict", CONFLICT_TEXT);
      }
      const id = await performSync(current);
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

  function sync(): Promise<string | null> {
    const token = renderGeneration;
    const session = renderSession;
    const current = () => isEngineGeneration(token) && accountSession() === session;
    if (!current()) return Promise.resolve(null);
    const active = activeSave.current;
    if (active?.token === token && active.session === session) return active.promise;
    const pending = syncQueue.current.catch(() => {}).then(async () => {
      if (!current()) return null;
      return flushCurrent(current);
    });
    syncQueue.current = pending;
    const entry = { token, session, promise: pending };
    activeSave.current = entry;
    void pending.finally(() => { if (activeSave.current === entry) activeSave.current = null; });
    return pending;
  }

  /** Coalesce edits made during a request into the next snapshot before a switch/download proceeds. */
  async function flushCurrent(current: () => boolean, signal?: AbortSignal): Promise<string | null> {
    while (current() && !signal?.aborted) {
      const id = await performSync(current, signal);
      if (!id || !current()) return null;
      if (syncState.current.saved || lockedCase(id)) return id;
    }
    return null;
  }

  function lockedCase(id: string) {
    return readOnly(getAccountState().applications?.find((app) => app.id === id)?.status ?? openedStatus.current);
  }

  async function performSync(live: () => boolean, signal?: AbortSignal): Promise<string | null> {
    const token = engineGeneration(), session = accountSession();
    const current = () => mounted.current && live() && !signal?.aborted && accountSession() === session && isEngineGeneration(token);
    if (!current()) return null;
    const existing = engineCaseId();
    // Autosave and downloads must never write a submitted/final record. The read-only
    // check below reads the server directly and does not use this save acknowledgement.
    if (existing && lockedCase(existing)) return existing;
    if (existing && goneCase.current === existing) {
      markGone("case not found");
      return null;
    }
    const version = revision.current;
    let snapshot = latestCase.current;
    const draft = applicantDraft(snapshot, draftAccount(getAccountState().user), token, existing);
    syncState.current = { ...syncState.current, saved: false, detail: "" };
    setSaveStatus("saving");
    setSavedNote("Saving…");
    setSaveDetail("");
    try {
      // Only a name the applicant chose is sent; a placeholder leaves the case for the engine to name.
      const id = await ensureEngineCase(snapshot.titleKept ? snapshot.title : null, snapshot.authority, signal);
      if (!current()) return null;
      setEngineId(id);
      const saved = await pushDraft(id, { facts: snapshot.facts, authority: snapshot.authority, selected: selectedArticles(snapshot), draft }, signal);
      if (!current()) return null;
      savedSelection.current = selectionKey(selectedArticles(snapshot));
      if (saved) {
        // The response is the acknowledgement. Saving never fans out into derived route reloads.
        openedStatus.current = saved.status;
        setSavedStatus(saved.status);
      }
      // One atomic write per listing, then removals. Only acknowledged revisions count as saved.
      const listed = await pushListedEvidence(id, snapshot.listedEvidence ?? [], signal);
      if (!current()) return null;
      snapshot = applyEvidence(listed, snapshot);
      const deleted = listed.error ? null : await pushDeletedEvidence(id, snapshot.deletedEvidence ?? [], signal);
      if (!current()) return null;
      if (deleted) snapshot = applyEvidence(deleted, snapshot);
      // A refused listing is back in its form with a note; it is not a failed save of the case.
      const failure = listed.error ?? deleted?.error;
      if (failure) throw new Error(failure);
      await uploadHeld(id, current, signal);
      if (!current()) return null;
      await uploadPendingEvidence(id, current, signal);
      if (!current()) return null;
      const unuploaded = latestCase.current.files.some(file => !file.engineId);
      if (unuploaded || getSession().held.length || evidenceUploads.current.size) throw new Error("Some files aren’t saved yet. Keep this page open and try again.");
      // A document staged after this snapshot is not saved yet; the next save sends it.
      const staged = revision.current !== version
        || draftKey(applicantDraft(latestCase.current, draftAccount(getAccountState().user), token, id)) !== draftKey(draft)
        || latestCase.current.listedEvidence?.length || latestCase.current.deletedEvidence?.length
        || (!isReadOnlyCase(id) && selectionKey(selectedArticles(latestCase.current)) !== selectionKey(selectedArticles(snapshot)));
      if (staged && !goneCase.current) {
        setSaveStatus("unsaved");
        setSavedNote("");
        return id;
      }
      setSaveStatus("saved");
      setSavedNote("Saved");
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

  /** Draft metadata is server state. Only an accepted canonical fact enters the local answer model. */
  function writeApplicantDraft(command: ApplicantDraftCommand): Promise<boolean> {
    // Another write is in flight: this command is not sent.
    if (activeDraftWrite.current) return activeDraftWrite.current.promise.then(() => false);
    const token = renderGeneration, session = renderSession, version = revision.current, user = account.user;
    let selectedId = engineCaseId();
    const ctl = new AbortController();
    const live = () => !ctl.signal.aborted && isEngineGeneration(token) && accountSession() === session
      && getAccountState().phase === "signed-in" && Boolean(user) && getAccountState().user === user
      && (!selectedId || engineCaseId() === selectedId);
    const current = () => live() && revision.current === version;
    if (!live()) return Promise.resolve(false);
    if (activeSubmit.current || (selectedId && (lockedCase(selectedId) || isReadOnlyCase(selectedId)))) {
      setDraftingError(activeSubmit.current ? "Wait for submission to finish." : "Drafting is available only for your editable application.");
      return Promise.resolve(false);
    }
    draftRetry.current = command;
    setDraftingError("");
    setDraftActivity(command.kind === "generate" ? { kind: "generating" } : { kind: "deciding", draftId: command.draftId });
    const promise = enqueue(async (): Promise<boolean> => {
      try {
        if (!current()) throw new Error("Your answers changed. Review them, then try drafting again.");
        if (selectedId && goneCase.current === selectedId) throw new Error(GONE_NOTE);
        // A version conflict is resolved through the save-conflict review, never silently here.
        if (selectedId && needsReconcile(selectedId)) throw new EngineError(409, CONFLICT_TEXT);
        if (selectedId && (lockedCase(selectedId) || isReadOnlyCase(selectedId))) throw new Error("This saved application is read-only.");
        const id = await performSync(current, ctl.signal);
        if (!live()) return false;
        if (!current()) throw new Error("Your answers changed while saving. Try again with your latest answers.");
        if (!id || !syncState.current.saved) throw new Error(syncState.current.detail || "Save your answers before drafting.");
        selectedId = id;
        if (lockedCase(id) || isReadOnlyCase(id)) throw new Error("This saved application is read-only.");
        if (command.kind === "generate") await uploadHeld(id, current);
        if (!current()) throw new Error("Your input changed while preparing the drafts. Try again with your latest answers.");
        if (command.kind === "generate" && (getSession().held.length || getSession().uploading.length)) throw new Error("A document is still waiting to upload. Finish uploading, then try drafting again.");
        const expected = acknowledgedVersion(id);
        if (expected === null || needsReconcile(id)) throw new EngineError(409, CONFLICT_TEXT);
        const before = latestCase.current;
        const basis = applicantDraftInputKey(before);
        if (command.kind === "decide" && (!draftRecord || draftRecord.record.stale || draftRecord.basis !== basis)) {
          throw new Error("These drafts use earlier input. Draft your application again before accepting or rejecting.");
        }
        if (command.kind === "decide" && command.decision === "accept"
          && !draftRecord?.record.drafts.find(d => d.id === command.draftId)?.text.trim()) {
          throw new Error("No wording to accept. Answer the questions, then draft again.");
        }
        const saved = command.kind === "generate"
          ? await engine.generateApplicantDrafts(id, expected, ctl.signal)
          : await engine.decideApplicantDraft(id, command.draftId, expected, command.decision, ctl.signal);
        if (!live()) return false;
        // The server committed even if the applicant edited while waiting. Advance CAS before the
        // next queued autosave; replace only the accepted field if that field still matches.
        acknowledgeWrite(id, saved.version);
        const editedWhileWaiting = revision.current !== version || applicantDraftInputKey(latestCase.current) !== basis;
        if (command.kind === "decide" && command.decision === "accept") {
          const fact = acceptedApplicantFact(saved, command.draftId);
          if (!fact) throw new Error("The decision was saved, but its confirmed answer could not be restored. Save your local answers and refresh before continuing.");
          notePosted(id, [fact]);
          if (unchangedDraftField(before, latestCase.current, fact.field)) derive({ type: "adoptApplicantDraft", fact });
          setFactsEpoch(n => n + 1);
        }
        const record = saved.drafting;
        setDraftRecord(record ? { record, basis: editedWhileWaiting ? basis : applicantDraftInputKey(latestCase.current) } : null);
        if (command.kind === "generate" && !record) throw new Error("No drafts were returned. Try drafting again.");
        if (editedWhileWaiting) {
          setDraftingError("Your input changed while drafting. Your edits are kept; generate fresh drafts before deciding.");
        }
        return true;
      } catch (error) {
        if (!live()) return false;
        if (isCaseGone(error) && selectedId) {
          goneCase.current = selectedId;
          markGone("case not found");
        }
        if (isCaseConflict(error) && selectedId) {
          noteConflict(selectedId);
          setSaveStatus("failed");
          setSavedNote(CONFLICT_NOTE);
          setSaveDetail(CONFLICT_TEXT);
          syncState.current = { ...syncState.current, saved: false, reviewed: false, detail: CONFLICT_TEXT };
          setSyncOk(false);
          activeCheck.current?.ctl.abort();
          setEngineGaps([]);
          setGapsSource("idle");
          setCompletenessRecord(null);
          if (checkRef.current.status !== "not_requested") {
            publishCheck({ ...checkRef.current, status: "stale", note: "The saved application changed. Check again after saving.", detail: "" });
          }
        }
        setDraftingError(isCaseGone(error) ? GONE_NOTE : isCaseConflict(error)
          ? "The saved application changed. Review the save conflict, then draft again."
          : error instanceof Error ? error.message : failureText(error));
        return false;
      }
    });
    const active = { session, ctl, promise };
    activeDraftWrite.current = active;
    void promise.finally(() => {
      if (activeDraftWrite.current !== active) return;
      activeDraftWrite.current = null;
      setDraftActivity({ kind: "idle" });
    });
    return promise;
  }

  /**
   * Rename the open application. Saved through PATCH /cases/{id}/title in the save queue (it moves
   * the case version), then shown in the header and the list. Before the case exists the name is kept
   * and sent when it is created. Resolves to an error text, or null when saved.
   */
  function renameCase(raw: string): Promise<string | null> {
    if (applicationEditsPaused()) return Promise.resolve("Editing is paused while your application is saved or you sign out.");
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
      const id = await flushCurrent(current, ctl.signal);
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
  async function uploadHeld(id: string, live: () => boolean, signal?: AbortSignal): Promise<void> {
    const held = getSession().held;
    if (!held.length) return;
    for (const { id: local, file } of held) {
      if (!live()) break;
      if (!latestCase.current.files.some((f) => f.id === local)) continue;
      updateSavedSession(s => ({ uploading: [...s.uploading, local] }));
      try {
        const saved = await engine.upload(id, file, signal);
        if (!live()) break;
        dispatch({ type: "setFileResult", id: local, error: null, read: true, pages: saved.pages, sha256: saved.sha256, engineId: saved.id });
        updateSavedSession(s => ({ held: s.held.filter(f => f.id !== local) }));
      } catch (e) {
        if (!live()) break;
        const status = e instanceof EngineError ? e.status : 0;
        const detail = e instanceof EngineError ? e.detail : String(e);
        dispatch({ type: "setFileResult", id: local, error: uploadMessage(status, detail), unreachable: status === 0 });
      } finally {
        if (live()) updateSavedSession((s) => ({ uploading: s.uploading.filter((x) => x !== local) }));
      }
    }
  }

  async function uploadPendingEvidence(id: string, live: () => boolean, signal?: AbortSignal) {
    for (const [key, entry] of evidenceUploads.current) {
      if (!live()) return;
      const saved = await engine.upload(id, entry.file, signal);
      if (!live()) return;
      entry.saved = saved;
      if (evidenceUploads.current.get(key) !== entry) continue;
      evidenceUploads.current.delete(key);
      if (entry.itemId) dispatch({ type: "editEvidenceDraft", itemId: entry.itemId,
        patch: { fileRef: saved.id, note: "PDF uploaded. Save the document to attach it." } }, "save");
    }
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

  function jobProgress(job: CaseJob) {
    // A finished job is still reading until its result is applied, so no card is asked from the unread case.
    const state = activeJob(job) || (job.state === "succeeded" && !completedJobs.current.has(job.id)) ? "running" : job.state === "succeeded" ? "done" : "error";
    if (!activeJob(job)) jobActionNotes.current.delete(job.id);
    const note = jobActionNotes.current.get(job.id) ?? (job.state === "superseded" ? "Your answers changed. Read the updated description again."
      : job.state === "cancelled" ? "This work was cancelled. You can start it again."
      : job.state === "failed" ? job.error?.message || "This work did not finish. Try again." : "");
    setReading(job.kind === "intake"
      ? { intake: state, intakeNote: note, intakeJob: job }
      : { identify: state, identifyNote: note, identifyJob: job, stages: {} });
  }

  /** Apply only the output of this owned job, retaining edits newer than its acknowledged input. */
  async function finishJob(job: CaseJob, live: () => boolean) {
    await whenEditsResume();
    if (!live() || completedJobs.current.has(job.id)) return;
    if (job.state !== "succeeded") {
      // Answering a question while the code is checked supersedes the check. Check again on the
      // latest answers instead of reporting a failure, a few times per case.
      const reruns = identifyReruns.current.get(job.case_id) ?? 0;
      if (job.kind === "identify" && job.state === "superseded" && job.error?.code === "input_changed" && reruns < IDENTIFY_RERUNS) {
        completedJobs.current.add(job.id);
        identifyReruns.current.set(job.case_id, reruns + 1);
        void startJob("identify").catch(() => jobProgress(job));
        return;
      }
      jobProgress(job);
      return;
    }
    if (job.kind === "identify") identifyReruns.current.delete(job.case_id);
    let continueIdentify = false;
    await enqueue(async () => {
      if (!live()) return;
      const read = await readSavedCase(job.case_id);
      if (!live()) return;
      const local = latestCase.current;
      const beforeVersion = acknowledgedVersion(job.case_id);
      const changes = pendingFactChanges(job.case_id, local.facts);
      const cardsChanged = selectionKey(selectedArticles(local)) !== savedSelection.current;
      const localDraft = applicantDraft(local, draftAccount(getAccountState().user), engineGeneration(), job.case_id);
      const baselineDraft = acknowledgedDraftKey(job.case_id);
      const localDraftChanged = draftKey(localDraft) !== baselineDraft;
      const remoteDraftChanged = draftKey(read.saved.applicant_draft) !== baselineDraft;
      const authorityChanged = (local.authority || null) !== acknowledgedAuthority(job.case_id);
      if (localDraftChanged && remoteDraftChanged && draftKey(localDraft) !== draftKey(read.saved.applicant_draft)) {
        noteConflict(job.case_id);
        setSaveStatus("failed"); setSavedNote(CONFLICT_NOTE); setSaveDetail(CONFLICT_TEXT);
        syncState.current = { saved: false, reviewed: false, detail: CONFLICT_TEXT };
        jobProgress(job);
        return;
      }
      const outputVersion = job.result_version;
      if (!acknowledgeJobCase(read.saved, outputVersion)) {
        setReading(job.kind === "intake" ? { intake: "error", intakeNote: "The saved application changed. Reopen it to read its latest progress." }
          : { identify: "error", identifyNote: "The saved application changed. Reopen it to read its latest progress." });
        return;
      }
      let next = openedCase(read.saved, local.applicantType, read);
      if (remoteDraftChanged && !localDraftChanged) {
        restoring.current = true;
        restoreApplicantDraft(read.saved.applicant_draft, draftAccount(getAccountState().user), engineGeneration(), job.case_id, true);
        restoring.current = false;
      }
      // A fresh identification supplies new cards; a rejoined, already applied result retains the saved selection.
      if (job.kind === "identify" && read.identify && JSON.stringify(read.identify) !== JSON.stringify(local.identify)) {
        next = reducer(next, { type: "noteIdentify", result: read.identify });
      }
      const facts = [...next.facts.filter(f => !changes.has(f.field)), ...[...changes.values()].filter((f): f is Fact => f !== null)];
      const process = { ...next.process };
      for (const { id } of PROCESS_FIELDS) if (changes.has(PROCESS_FACT[id])) process[id] = local.process[id];
      next = { ...next, facts, process, files: remoteDraftChanged && !localDraftChanged ? next.files : local.files,
        evidenceDrafts: remoteDraftChanged && !localDraftChanged ? next.evidenceDrafts : local.evidenceDrafts,
        listedEvidence: local.listedEvidence, deletedEvidence: local.deletedEvidence,
        evidenceIssues: local.evidenceIssues, evidenceRev: local.evidenceRev,
        ...(authorityChanged ? { authority: local.authority } : {}),
        ...(local.intake?.filesChanged && next.intake ? { intake: { ...next.intake, filesChanged: true } } : {}),
        ...(changes.has("project.description") ? { description: local.description, title: local.title, titleKept: local.titleKept } : {}),
        ...(cardsChanged ? { candidates: local.candidates, sectionC: local.sectionC } : {}),
      };
      if (read.saved.version !== beforeVersion || remoteDraftChanged || JSON.stringify(local.identify ?? null) !== JSON.stringify(read.identify)
        || JSON.stringify(local.intake?.record ?? null) !== JSON.stringify(read.saved.intake)) {
        revision.current++;
        planRevision.current++;
        activeCheck.current?.ctl.abort();
        setSyncOk(false);
        syncState.current = { ...syncState.current, reviewed: false };
        if (checkRef.current.status !== "not_requested") publishCheck({ ...checkRef.current, status: "stale", note: "Your application has new results. Check it again when you’re ready.", detail: "" });
      }
      savedSelection.current = selectionKey(read.saved.selected_articles ?? []);
      derive({ type: "adoptCase", to: next });
      completedJobs.current.add(job.id);
      jobProgress(job);
      setFactsEpoch(n => n + 1);
      continueIdentify = job.kind === "intake" && Boolean(read.reviewedText)
        && read.reviewedText === latestCase.current.description.trim() && read.intake?.record.plan?.scope.status !== "redirect";
      if (job.kind === "intake" && read.intake?.record.plan?.scope.status === "redirect") setReading({ identify: "skipped" });
    });
    if (live() && continueIdentify) void startJob("identify", { jobId: job.id, createdAt: job.created_at }).catch(error => {
      if (live()) setReading({ identify: "error", identifyNote: failureText(error) });
    });
  }

  function watchJob(job: CaseJob) {
    const id = engineCaseId(), token = engineGeneration(), session = accountSession();
    if (!id || job.case_id !== id) return;
    const existing = jobObservers.current.get(job.id);
    if (existing) { existing.ctl.abort(); existing.stop(); jobObservers.current.delete(job.id); }
    const previous = currentJobs.current.get(job.kind);
    if (previous && previous !== job.id) {
      jobObservers.current.get(previous)?.ctl.abort();
      jobObservers.current.get(previous)?.stop();
      jobObservers.current.delete(previous);
    }
    currentJobs.current.set(job.kind, job.id);
    const ctl = new AbortController();
    const live = () => !ctl.signal.aborted && isEngineGeneration(token) && engineCaseId() === id && accountSession() === session
      && currentJobs.current.get(job.kind) === job.id;
    let observed = job, availabilityNote = "", checkedAt = -Infinity, checking = false;
    const activeNote = () => [jobActionNotes.current.get(job.id), availabilityNote].filter(Boolean).join(" ");
    const showAvailability = () => {
      if (live() && activeJob(observed) && activeNote()) setReading(job.kind === "intake"
        ? { intakeNote: activeNote() } : { identifyNote: activeNote() });
    };
    const checkAvailability = () => {
      if (checking || Date.now() - checkedAt < 10000) return;
      checkedAt = Date.now(); checking = true;
      // Availability is advisory and independent of both status polling and the save queue.
      void engine.workerHealth(id, ctl.signal).then(health => {
        if (!live() || !activeJob(observed)) return;
        availabilityNote = health.worker_available ? ""
          : "Background processing is unavailable. Your job is saved and will resume when processing is available.";
        setReading(job.kind === "intake" ? { intakeNote: activeNote() } : { identifyNote: activeNote() });
      }).catch(() => {
        if (!live() || !activeJob(observed)) return;
        availabilityNote = "Background processing availability could not be checked. Your job is saved.";
        showAvailability();
      }).finally(() => { checking = false; });
    };
    const stop = observeJob({ job, signal: ctl.signal,
      read: (jobId, signal) => engine.job(id, jobId, signal),
      change: next => {
        if (!live()) return;
        observed = next; jobProgress(next);
        if (activeJob(next)) { showAvailability(); checkAvailability(); }
      },
      failure: error => {
        if (!live()) return;
        const unavailable = `Progress unavailable. ${failureText(error)}`;
        const terminal = error instanceof EngineError && [401, 403, 404].includes(error.status);
        if (terminal) {
          ctl.abort();
          jobObservers.current.delete(job.id);
          if (isCaseGone(error)) { goneCase.current = id; markGone(failureText(error)); }
        }
        setReading(job.kind === "intake"
          ? { intakeNote: unavailable, ...(terminal ? { intake: "error", intakeJob: undefined } : {}) }
          : { identifyNote: unavailable, ...(terminal ? { identify: "error", identifyJob: undefined } : {}) });
      },
      finished: async next => {
        try { if (live()) await finishJob(next, live); }
        finally { if (jobObservers.current.get(job.id)?.ctl === ctl) jobObservers.current.delete(job.id); }
      },
    });
    jobObservers.current.set(job.id, { ctl, stop });
  }

  async function rejoinJobs(id: string, token = engineGeneration(), session = accountSession()) {
    try {
      const jobs = await engine.jobs(id);
      if (!isEngineGeneration(token) || engineCaseId() !== id || accountSession() !== session) return;
      for (const kind of ["intake", "identify"] as const) {
        const job = latestJob(jobs, kind);
        if (job) watchJob(job);
      }
    } catch (error) {
      if (!isEngineGeneration(token) || engineCaseId() !== id || accountSession() !== session) return;
      setReading({ intakeNote: `Saved progress could not be loaded. ${failureText(error)}` });
    }
  }

  /** Only save, upload and the short acceptance request hold the queue. Polling never does. */
  async function startJob(kind: CaseJob["kind"], chain?: { jobId: string; createdAt: string }): Promise<void> {
    // A click is refused while paused; a chained start from finished work waits for the pause to end.
    if (applicationEditsPaused() && !chain) return;
    const token = engineGeneration(), session = accountSession();
    const live = () => isEngineGeneration(token) && accountSession() === session;
    await whenEditsResume();
    if (!live()) return;
    setReading(kind === "intake" ? { intake: "running", intakeNote: "", intakeJob: undefined }
      : { identify: "running", identifyNote: "", identifyJob: undefined, stages: {} });
    return enqueue(async () => {
      if (!live()) return;
      const id = await flushCurrent(live);
      if (!live()) return;
      if (!id || !syncState.current.saved) {
        setReading(kind === "intake" ? { intake: "error", intakeNote: "Your description wasn’t saved, so it wasn’t read yet. Try again." }
          : { identify: "error", identifyNote: "Your draft wasn’t saved, so the code check didn’t run. Try again." });
        return;
      }
      try {
        const previous = latestJob(await engine.jobs(id), kind);
        if (!live()) return;
        // Chain recovery must join existing downstream work, including completed work after a refresh.
        if (chain && previous) {
          if (previous.created_at >= chain.createdAt) { watchJob(previous); return; }
        }
        // The list read can outlast a new edit. Acknowledge that revision before capturing
        // computation input; later awaits use this immutable saved snapshot.
        if (!(await flushCurrent(live)) || !live() || !syncState.current.saved) throw new Error("Your latest input wasn’t saved. Try again after saving.");
        const snapshot = latestCase.current;
        const expected = acknowledgedVersion(id);
        if (expected === null || needsReconcile(id)) throw new EngineError(409, CONFLICT_TEXT);
        const slot = `${id}:${kind}:${chain?.jobId ?? expected}`;
        let submission = jobRequestKeys.current.get(slot) ?? { key: `batatis-${kind}-${crypto.randomUUID()}` };
        jobRequestKeys.current.set(slot, submission);
        const text = snapshot.description.trim();
        if (!chain && previous?.can_retry && submission.replaces !== previous.id) {
          try {
            const retried = await engine.retryJob(id, previous.id);
            if (live() && isApplicantJob(retried)) watchJob(retried);
            return;
          } catch (error) {
            // A changed input cannot retry the old identity. Submit the current saved input once.
            if (!(error instanceof EngineError) || error.status !== 409) throw error;
            submission = { key: `batatis-${kind}-${crypto.randomUUID()}`, replaces: previous.id };
            jobRequestKeys.current.set(slot, submission);
          }
        }
        const job = kind === "intake"
          ? await engine.startIntakeJob(id, { text: text || undefined, file_ids: snapshot.files.flatMap(f => f.engineId ? [f.engineId] : []), role: roleFor(snapshot.applicantType), model: true, pictures: picturesAllowed(snapshot), expected_version: expected }, submission.key)
          : await engine.startIdentifyJob(id, { prose: text, answers: [], expected_version: expected }, submission.key);
        if (!live()) return;
        if (!isApplicantJob(job) || job.kind !== kind || job.case_id !== id) throw new Error("The progress response belongs to another application.");
        watchJob(job);
      } catch (error) {
        if (!live()) return;
        setReading(kind === "intake" ? { intake: "error", intakeNote: intakeError(error, id) }
          : { identify: "error", identifyNote: intakeError(error, id) });
      }
    });
  }

  function readDescription(): Promise<void> { return startJob("intake"); }
  function runIdentify(): Promise<void> {
    identifyReruns.current.clear();          // a check the applicant starts gets a fresh restart budget
    return startJob("identify");
  }

  /** A version conflict is why the save failed; say so instead of a generic retry. */
  function blockedSave(fallback: string): string {
    const id = engineCaseId();
    return id && needsReconcile(id) ? CONFLICT_TEXT : fallback;
  }

  function answerPlan(q: PlanQuestion, answer: string): Promise<string | null> {
    if (applicationEditsPaused()) return Promise.resolve("Editing is paused. Try again when it resumes.");
    const token = engineGeneration();
    const live = () => isEngineGeneration(token);
    setReading({ busy: q.id });
    return enqueue(async () => {
      try {
        const id = await performSync(live);
        if (!live()) return null;
        if (!id) return blockedSave("Your draft wasn’t saved, so the answer wasn’t either. Try again.");
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
    if (applicationEditsPaused()) return Promise.resolve("Editing is paused. Try again when it resumes.");
    const token = engineGeneration();
    const live = () => isEngineGeneration(token);
    setReading({ busy: "scope" });
    return enqueue(async () => {
      try {
        const id = await performSync(live);
        if (!live()) return null;
        if (!id) return blockedSave("Your draft wasn’t saved. Try again.");
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
        if (result.record.plan?.scope.status !== "redirect" && (buildingCode || !latestCase.current.identify)) void startJob("identify");
        return null;
      } catch (e) {
        return failureText(e);
      } finally {
        if (live()) setReading({ busy: null });
      }
    });
  }

  function decide(candidate: Candidate, answer: CandidateAnswer): Promise<string | null> {
    if (applicationEditsPaused()) return Promise.resolve("Editing is paused. Try again when it resumes.");
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

  /**
   * The applicant's one-line departure from a card they answered Yes. One engine call records the
   * benchmark, the Section C row and the varied requirement, so the appendix prints a departure.
   */
  function confirmDeparture(candidate: Candidate, departure: string): Promise<string | null> {
    if (applicationEditsPaused()) return Promise.resolve("Editing is paused. Try again when it resumes.");
    const text = departure.trim();
    if (!text) return Promise.resolve("Describe what the design does instead.");
    dispatch({ type: "answerCandidate", id: candidate.id, answer: "yes" });
    if (!/^\d/.test(candidate.provision)) return Promise.resolve(null);
    const token = engineGeneration();
    const live = () => isEngineGeneration(token);
    const provision = candidate.provision;
    return enqueue(async () => {
      const id = engineCaseId();
      if (!id || !live()) return null;
      try {
        const body = await engine.confirmBenchmark(id, provision, text, undefined, acknowledgedVersion(id) ?? undefined);
        if (!live()) return null;
        acknowledgeWrite(id, body.case_version);
        derive({ type: "markDecisionPending", id: candidate.id, pending: false });
        setIdentify(id, body);
        const read = readDecisionBody(body, provision);
        if (read.row) derive({ type: "noteSectionC", rows: [toViewRow(read.row, candidate.id)] });
        derive({ type: "noteIdentify", result: body });
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
        if (live()) derive({ type: "markDecisionPending", id: candidate.id, pending: true });
        return e instanceof EngineError && e.status === 0 ? "Not saved yet: Batatis could not be reached. Your answer is kept here; answer again to resend it." : failureText(e);
      }
    });
  }

  /**
   * One requirement-ledger answer: applicability only, through its own route with the version the
   * engine requires. The reply carries the updated ledger, so the next batch appears on its own.
   */
  function decideRequirement(requirement: RequirementRecord, answer: RequirementAnswer, reason = ""): Promise<string | null> {
    if (applicationEditsPaused()) return Promise.resolve("Editing is paused. Try again when it resumes.");
    let decision: RequirementDecision;
    try {
      decision = requirementDecision(requirement, answer, reason);
    } catch (e) {
      return Promise.resolve(e instanceof Error ? e.message : "A reason is required for this answer.");
    }
    const token = engineGeneration();
    const live = () => isEngineGeneration(token);
    return enqueue(async () => {
      const id = engineCaseId();
      if (!id || !live()) return null;
      const expected = acknowledgedVersion(id) ?? latestCase.current.identify?.case_version;
      if (!expected) return "The code check isn’t saved yet. Try again in a moment.";
      try {
        const body = await engine.decideRequirement(id, requirement.id, {
          disposition: decision.disposition,
          role: decision.role,
          reason: decision.reason,
          expected_version: expected,
        });
        if (!live()) return null;
        acknowledgeWrite(id, body.case_version);
        derive({ type: "noteIdentify", result: body });
        return null;
      } catch (e) {
        if (!live()) return null;
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

  /** Queue a versioned checklist answer and update shared extras, preserving conflict and missing-case feedback. */
  function answerChecklist(checklistId: string, conditionId: string, state: "confirmed" | "not_yet" | "does_not_apply", reason?: string): Promise<string | null> {
    if (applicationEditsPaused()) return Promise.resolve("Editing is paused. Try again when it resumes.");
    const token = engineGeneration();
    const live = () => isEngineGeneration(token);
    return enqueue(async () => {
      const id = await performSync(live);
      if (!live()) return null;
      if (!id) return blockedSave("Your draft wasn’t saved, so the answer wasn’t either. Try again.");
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
    const id = engineCaseId();
    if (id && needsReconcile(id)) return reviewSaveConflict();
    const token = engineGeneration();
    return enqueue(async () => {
      const id = engineCaseId();
      if (!id || !isEngineGeneration(token)) return null;
      try {
        if (needsReconcile(id) || acknowledgedVersion(id) === null) return CONFLICT_TEXT;
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

  /** Read-only preparation. Keep the conflict fence and local editors until a reviewed CAS succeeds. */
  function reviewSaveConflict(): Promise<string | null> {
    if (applicationEditsPaused()) return Promise.resolve("Editing is paused. Try again when it resumes.");
    if (conflictRead.current) return conflictRead.current;
    const id = engineCaseId(), token = engineGeneration(), session = accountSession();
    if (!id) return Promise.resolve(null);
    const current = () => mounted.current && isEngineGeneration(token) && engineCaseId() === id && accountSession() === session;
    setSaveConflictReview({ kind: "loading" });
    const pending = enqueue(async () => {
      try {
        const read = await readSavedCase(id);
        if (!current()) return null;
        if (readOnly(read.saved.status)) throw new Error("This application has been sent or closed. Your local draft stays here; the saved application cannot be overwritten.");
        const local = latestCase.current, remote = openedCase(read.saved, local.applicantType, read);
        const baselineSelection = acknowledgedSelectionKey(id);
        const input: ReconciliationInput = {
          local, remote,
          draft: applicantDraft(local, draftAccount(getAccountState().user), token, id),
          savedDraft: read.saved.applicant_draft, baselineDraft: acknowledgedDraft(id),
          localFacts: pendingFactChanges(id, local.facts), remoteFacts: pendingFactChanges(id, remote.facts),
          baselineAuthority: acknowledgedAuthority(id), baselineEvidence: acknowledgedEvidenceFacts(id),
          localSelectionChanged: selectionKey(selectedArticles(local)) !== baselineSelection,
          remoteSelectionChanged: selectionKey(selectedArticles(remote)) !== baselineSelection,
        };
        recovery.current = { token, session, id, revision: revision.current, input, read };
        setSaveConflictReview({ kind: "review", conflicts: reconcileDraft(input).conflicts, saving: false, note: "" });
        return null;
      } catch (error) {
        if (!current()) return null;
        const note = failureText(error);
        if (isCaseGone(error)) { goneCase.current = id; markGone(note); }
        setSaveDetail(note);
        setSaveConflictReview({ kind: "closed" });
        return note;
      }
    });
    conflictRead.current = pending;
    void pending.finally(() => { if (conflictRead.current === pending) conflictRead.current = null; });
    return pending;
  }

  function saveReviewedChanges(choices: ReconciliationChoices): Promise<string | null> {
    const entry = recovery.current;
    if (!entry || applicationEditsPaused()) return Promise.resolve("Review the saved changes first.");
    const merged = reconcileDraft(entry.input, choices);
    if (merged.conflicts.some(item => choices[item.id] !== "mine" && choices[item.id] !== "saved")) return Promise.resolve("Choose which value to keep for each change.");
    const current = () => mounted.current && isEngineGeneration(entry.token) && engineCaseId() === entry.id && accountSession() === entry.session;
    if (!current() || revision.current !== entry.revision) {
      const note = "Your draft changed during review. Review the latest changes before saving.";
      setSaveConflictReview({ kind: "review", conflicts: merged.conflicts, saving: false, note });
      return Promise.resolve(note);
    }
    const resume = pauseApplicationEdits();
    setSaveConflictReview({ kind: "review", conflicts: merged.conflicts, saving: true, note: "" });
    return enqueue(async () => {
      try {
        if (!current()) return null;
        const saved = await pushReconciledDraft(entry.read.saved, merged.snapshot);
        if (!current() || !saved) return null;
        const reviewedText = await reviewedDescription(saved, saved.intake);
        if (!current()) return null;
        const next = openedCase(saved, merged.snapshot.draft.role, { ...entry.read, reviewedText, files: merged.files });
        restoring.current = true;
        restoreApplicantDraft(saved.applicant_draft, draftAccount(getAccountState().user), entry.token, entry.id, true);
        restoring.current = false;
        derive({ type: "adoptCase", to: { ...next, listedEvidence: merged.listedEvidence, deletedEvidence: merged.deletedEvidence,
          evidenceIssues: entry.input.local.evidenceIssues, evidenceRev: entry.input.local.evidenceRev } });
        savedSelection.current = selectionKey(saved.selected_articles ?? []);
        sectionDHold.current = null;
        openedStatus.current = saved.status;
        setSavedStatus(saved.status);
        dirty();
        planRevision.current++;
        setFactsEpoch(n => n + 1);
        setEngineGaps([]); setGapsSource("idle"); setCompletenessRecord(null);
        const id = await flushCurrent(current);
        if (!current()) return null;
        recovery.current = null;
        setSaveConflictReview({ kind: "closed" });
        void rejoinJobs(entry.id);
        return id && syncState.current.saved ? null : syncState.current.detail || "Some changes still need saving. Your draft stays open.";
      } catch (error) {
        if (!current()) return null;
        const note = isCaseConflict(error) ? "The saved application changed again. Review its latest changes before saving." : failureText(error);
        setSaveStatus("failed"); setSavedNote(CONFLICT_NOTE); setSaveDetail(note);
        syncState.current = { saved: false, reviewed: false, detail: note };
        if (isCaseConflict(error)) {
          noteConflict(entry.id); recovery.current = null;
          setSaveConflictReview({ kind: "closed" });
        } else setSaveConflictReview({ kind: "review", conflicts: merged.conflicts, saving: false, note });
        return note;
      } finally { resume(); }
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
        const id = before?.id ?? await sync();
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
    if (!c.facts.length && !c.authority && !c.files.length && !Object.keys(c.evidenceDrafts ?? {}).length && !engineCaseId()) return;
    const handle = window.setTimeout(() => { if (!syncState.current.saved) void sync(); }, 500);
    return () => window.clearTimeout(handle);
    // Saving facts does not request identification or a full administrative check.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, editEpoch, c.facts, c.authority, c.title, c.listedEvidence, c.deletedEvidence, c.evidenceDrafts, selection]);

  /** Reset the save session, case extras and visible request state before adopting another case. */
  function clearVisit(next: Case, keep: Partial<Session> = {}) {
    for (const observer of jobObservers.current.values()) { observer.ctl.abort(); observer.stop(); }
    jobObservers.current.clear();
    currentJobs.current.clear();
    completedJobs.current.clear();
    jobRequestKeys.current.clear();
    jobActionNotes.current.clear();
    recovery.current = null;
    conflictRead.current = null;
    setSaveConflictReview({ kind: "closed" });
    evidenceUploads.current.clear();
    restoring.current = true;
    resetSavedSession(keep);
    restoring.current = false;
    activeSave.current = null;
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
    activeDraftWrite.current?.ctl.abort();
    activeDraftWrite.current = null;
    draftRetry.current = null;
    setDraftRecord(null);
    setDraftActivity({ kind: "idle" });
    setDraftingError("");
    setSubmitting(false);
    setSubmissionDispatched(false);
    clearEngineSession();
    resetExtras();                                   // the next case never renders with the last case's rules, checklists or pack
    goneCase.current = null;
    sectionDHold.current = null;
    syncQueue.current = Promise.resolve();
    dispatch({ type: "reset", to: next }, "save");
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
    let drafting = saved.drafting ?? null;
    if (drafting) {
      try {
        const current = await engine.applicantDrafts(id, signal);
        // Keep wording and decisions bound to this Case snapshot. A newer record or an unreadable
        // staleness check stays inspectable, but cannot be accepted against this older snapshot.
        const sameDecisions = current && JSON.stringify(current.drafts.map(d => [d.id, d.status])) === JSON.stringify(drafting.drafts.map(d => [d.id, d.status]));
        drafting = { ...drafting, stale: drafting.stale || !current || current.stale
          || current.input_fingerprint !== drafting.input_fingerprint || !sameDecisions };
      } catch (error) {
        if (isCaseGone(error) || signal?.aborted) throw error;
        drafting = { ...drafting, stale: true };
      }
    }
    // Both records are embedded in this exact case revision. Later route reads can observe
    // another writer's newer run and combine its questions with this snapshot's older facts.
    const record = saved.intake;
    const pointers = new Set(record?.pointers.map(p => p.fact_id));
    const intake: IntakeResult | null = record ? {
      case_id: saved.id, case_version: saved.version, record,
      facts: saved.facts.filter(f => pointers.has(f.id)),
    } : null;
    const reviewedText = await reviewedDescription(saved, record ?? null);
    const fileIds = saved.applicant_draft?.intake_file_ids ?? record?.files.map(file => file.file_id) ?? [];
    const inventory = fileIds.length ? await engine.files(id, signal) : [];
    const files = fileIds.map(fileId => {
      const stored = inventory.find(file => file.id === fileId);
      if (!stored) throw new Error("A saved reading attachment could not be loaded. Your current application stays open.");
      return { id: `saved-${fileId}`, engineId: fileId, name: stored.name, read: true };
    });
    return { saved, intake, identify: saved.identify, reviewedText, files, drafting };
  }

  /** `next` is the opened case built in one step (openedCase): intake, code cards and their saved selection included. */
  function showSavedCase(read: Awaited<ReturnType<typeof readSavedCase>>, next: Case) {
    clearVisit(next);
    // Adopt the saved version, answers and shown code cards so the next save sends only what the applicant changes.
    adoptEngineCase(read.saved, selectedArticles(next));
    restoring.current = true;
    restoreApplicantDraft(read.saved.applicant_draft, draftAccount(getAccountState().user), engineGeneration(), read.saved.id);
    restoring.current = false;
    savedSelection.current = selectionKey(read.saved.selected_articles ?? selectedArticles(next));
    openedStatus.current = read.saved.status;
    setSavedStatus(read.saved.status);
    patchApplication(read.saved.id, { status: read.saved.status, authority: read.saved.authority });
    setEngineId(read.saved.id);
    setDraftRecord(read.drafting ? { record: read.drafting, basis: applicantDraftInputKey(next) } : null);
    setReadingState({ ...NO_READING, intake: read.intake ? "done" : "idle", identify: read.identify ? "done" : "idle" });
    setSaveStatus("saved");
    setSavedNote("Saved");
    syncState.current = { saved: true, reviewed: false, detail: "" };
    setResetNote("");
    setPhase("case");
    void rejoinJobs(read.saved.id);
  }

  const keptDraft = "Your local answers stay open. Save them before refreshing this application.";
  function cleanForRefresh() {
    const draft = latestCase.current;
    return syncState.current.saved && !applicationEditsPaused() && !activeSubmit.current && !activeDraftWrite.current && !caseOpening.current
      && !draft.listedEvidence?.length && !draft.deletedEvidence?.length
      && !getSession().held.length && !getSession().uploading.length && !evidenceUploads.current.size;
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
          && ((!read.saved.applicant_draft && acknowledgedDraftKey(id) === "null")
            || draftKey(applicantDraft(local, draftAccount(getAccountState().user), engineGeneration(), id)) === draftKey(read.saved.applicant_draft))
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
          setDraftRecord(read.drafting ? { record: read.drafting, basis: applicantDraftInputKey(latestCase.current) } : null);
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
        if (sameContent) await rejoinJobs(id, token, session);
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

  /** Remove a file and its source-only unconfirmed answers now; the engine records it in the save queue. */
  function removeFileNow(fileId: string): number {
    const before = latestCase.current;
    const file = before.files.find(f => f.id === fileId);
    const engineFileId = file?.engineId;
    const id = engineCaseId(), token = engineGeneration();
    if (!file || isReadOnlyCase(id)) return 0;
    dispatch({ type: "removeFile", id: fileId });
    if (latestCase.current.files.some(f => f.id === fileId)) return 0;
    updateSavedSession(s => ({ held: s.held.filter(h => h.id !== fileId) }));
    const gone = before.facts.filter(f => !latestCase.current.facts.some(after => after.id === f.id));
    if (id && engineFileId) {
      const live = () => isEngineGeneration(token) && engineCaseId() === id;
      void enqueue(async () => {
        if (!live()) return;
        try {
          const result = await engine.removeIntakeFile(id, engineFileId, acknowledgedVersion(id) ?? undefined);
          if (!live()) return;
          acknowledgeWrite(id, result.case_version);
          derive({ type: "noteIntakeRecord", record: result.record });
          const present = new Set(latestCase.current.facts.map(f => f.id));
          const facts = result.facts.filter(f => present.has(f.id)).map(f => asLocal(f) as Fact);
          derive({ type: "adoptFacts", facts });
          notePosted(id, facts, gone.map(f => f.field));
        } catch (error) {
          if (!live()) return;
          derive({ type: "restoreFiles", files: [...latestCase.current.files, { ...file, error: "Removal not saved. Remove it again." }] });
          setReading({ intake: "error", intakeNote: failureText(error) });
        }
      });
    }
    return gone.length;
  }

  const value: Store = {
    drafting: draftRecord?.record ?? null,
    draftingStale: Boolean(draftRecord && (draftRecord.record.stale || draftRecord.basis !== applicantDraftInputKey(c) || (engineId && needsReconcile(engineId)))),
    draftActivity, draftingError,
    generateApplicantDrafts: () => writeApplicantDraft({ kind: "generate" }),
    decideApplicantDraft: (draftId, decision) => writeApplicantDraft({ kind: "decide", draftId, decision }),
    retryApplicantDrafts: () => draftRetry.current ? writeApplicantDraft(draftRetry.current).then(() => {}) : Promise.resolve(),
    reading, readDescription, runIdentify,
    cancelReadingJob: kind => {
      const token = engineGeneration(), session = accountSession(), id = engineCaseId();
      const job = kind === "intake" ? reading.intakeJob : reading.identifyJob;
      if (!id || !job || !activeJob(job)) return Promise.resolve(null);
      const live = () => isEngineGeneration(token) && accountSession() === session && engineCaseId() === id;
      return enqueue(async () => {
        try {
          const saved = await engine.cancelJob(id, job.id);
          if (!live()) return null;
          if (!isApplicantJob(saved) || saved.id !== job.id || saved.case_id !== id) throw new Error("The progress response belongs to another application.");
          jobObservers.current.get(job.id)?.ctl.abort();
          jobObservers.current.get(job.id)?.stop();
          jobObservers.current.delete(job.id);
          watchJob(saved);
          return null;
        } catch (error) {
          if (!live() || currentJobs.current.get(kind) !== job.id) return null;
          const note = `Could not cancel this work. ${failureText(error)}`;
          jobActionNotes.current.set(job.id, note);
          setReading(kind === "intake" ? { intakeNote: note } : { identifyNote: note });
          return note;
        }
      });
    },
    uploadFiles: () => {
      const token = engineGeneration();
      return enqueue(async () => {
        const id = engineCaseId();
        if (id) await flushCurrent(() => isEngineGeneration(token));
      }).then(() => {
        // A file added after the first reading is read as soon as it is uploaded; no Continue needed.
        const c = latestCase.current;
        const unread = c.files.some(f => f.engineId && !f.error && !c.intake?.record.files.some(r => r.file_id === f.engineId));
        if (isEngineGeneration(token) && c.intake && unread && !getSession().held.length) void startJob("intake").catch(() => {});
      });
    },
    retryUpload: (fileId) => {
      dispatch({ type: "setFileResult", id: fileId, error: null, read: false });
      return value.uploadFiles();
    },
    removeFile: removeFileNow,
    uploadEvidenceFile: (file, itemId) => {
      if (applicationEditsPaused()) return Promise.reject(new Error("Editing is paused. Try again when it resumes."));
      const token = engineGeneration();
      const live = () => isEngineGeneration(token);
      const entry: { file: File; itemId?: string; saved?: UploadedFile } = { file, itemId };
      if (itemId) for (const [key, previous] of evidenceUploads.current) if (previous.itemId === itemId) evidenceUploads.current.delete(key);
      evidenceUploads.current.set(crypto.randomUUID(), entry);
      dirty();
      return enqueue(async () => {
        if (!live()) throw new Error("The application changed while uploading.");
        const id = await flushCurrent(live);
        if (!id || !live()) throw new Error(syncState.current.detail || "Save the application before uploading.");
        if (!entry.saved) throw new Error("The file was replaced before uploading.");
        return entry.saved;
      });
    }, answerPlan, overrideScope, decide, confirmDeparture, decideRequirement, answerChecklist, reloadChecklists, renameCase,
    sectionCLookup, retrySectionC: () => setLookupAttempt(n => n + 1),
    snapshotKey: `${renderGeneration}:${renderPlanRevision}:${remoteEpoch}:${JSON.stringify(c.candidates)}:${JSON.stringify(c.sectionC)}:${sectionCLookup.source}`,
    loadSectionD,
    c, gaps, notices, engineGaps, gapsSource, gapsNote, reviewDetail, syncOk,
    saveStatus, saveDetail, savedNote, saveConflict: Boolean(engineId && needsReconcile(engineId)), saveConflictReview,
    reviewSaveConflict, saveReviewedChanges,
    closeSaveConflictReview: () => { if (!applicationEditsPaused()) { recovery.current = null; setSaveConflictReview({ kind: "closed" }); } },
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
    saveDraft: () => sync(),
    queueWrite: enqueue,
    refreshCurrentCase,
    submitDraft, submitting, submissionDispatched,
    beginEmpty: (type) => {
      if (applicationEditsPaused()) return;
      clearVisit(caseForRole(type, latestCase.current));
      setResetNote("");
      setPhase("case");
      location.hash = "#/describe";
    },
    completenessRecord, setCompletenessRecord,
    readGaps: () => latestGaps.current,
    resetToWho: (note = "Cleared for this visit.") => {
      if (applicationEditsPaused()) return;
      clearVisit(emptyCase("homebuilder"));
      setPhase("who");
      setResetNote(note);
      location.hash = "#/";
    },
    openCase: async (id, type) => {
      if (applicationEditsPaused()) return "Editing is paused. Your current application stays open.";
      if (phaseRef.current === "case" && !syncState.current.saved && !(await sync())) return "Your latest answers aren’t saved, so this application stays open.";
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
  return <Ctx.Provider value={value}><fieldset className="cf-edit-lock" disabled={editsPaused} aria-label="Application session">{children}</fieldset></Ctx.Provider>;
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
