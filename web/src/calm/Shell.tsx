import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { ApplicationSummary } from "../api/accounts";
import { engineCaseId, engineGeneration, isEngineGeneration } from "../api/sync";
import { groupGaps } from "../humanReview";
import { useCase } from "../store";
import { accountSession, bootAccount, deleteApplication, refreshApplications, setApplicationPreferences, useAccount, type AccountPhase } from "./account";
import { groupApplications, readOnly, readOnlyStatus } from "./applications";
import { saveTitle, titleError } from "./rename";
import { RenameDialog } from "./shell/RenameDialog";
import { DeleteDialog } from "./shell/DeleteDialog";
import type { RowAction } from "./shell/RowMenu";
import { AssistantPanel } from "./assistant/AssistantPanel";
import { NativePanels } from "./assistant/NativePanels";
import { AskButton, AskHost } from "./assistant/AskButton";
import { invalidateAssistantNavigation, setAssistantCase, setAssistantContext, toggleAssistant, useAssistant, type AssistBinding } from "./assistant/assistant";
import { OPEN_APPLICATIONS } from "./assistant/destinations";
import { useCurrentApplication } from "./begin";
import { CodePalette, OPEN_PALETTE, openPalette } from "./CodePalette";
import { ApplicationSwitchContext, useCodeScope, type ApplicationSwitch } from "./codeScope";
import { KEEP_OPEN_NOTE, switchApplication } from "./libraryContext";
import { buildDeck, deckProgress } from "./deck";
import { useDeckExtras } from "./useDeckExtras";
import { rememberStage, STAGES, type Screen } from "./routes";
import { setOpenProblem } from "./comments/opening";
import { getSession, resetSession, useSession } from "./session";
import { AppHeader, type StageRingItem } from "./shell/AppHeader";
import { AppLayout } from "./shell/AppLayout";
import { ApplicationList, type ApplicationListHandle } from "./shell/ApplicationList";
import { MoreMenu } from "./shell/MoreMenu";
import { Rail, type RailDestination } from "./shell/Rail";
import { RequestBanner } from "./shell/RequestBanner";
import { ReturnedBanner } from "./shell/ReturnedBanner";
import { AccountButton, NotificationsBell } from "./routes.extra";
import { useNotifications } from "./notifications/notifications";
import { useRoute } from "../router";
import { resetRelevance } from "./useRelevance";
import { Tip } from "./RelevanceRing";
import { CIcon, ConfirmDialog, Dot, MOD_KEY, type DotTone } from "./ui";
import { activeJob, jobLabel } from "../api/jobs";
import { SaveConflictDialog } from "./SaveConflictDialog";

/** The check's state, quietly beside the save status (Review holds the detail and the big retry). */
function CheckStatus() {
  const { phase, checkStatus, reading } = useCase();
  const { app } = useCurrentApplication();
  if (phase !== "case" || app?.status === "refused") return null;
  const job = [reading?.intakeJob, reading?.identifyJob].find(job => job && activeJob(job));
  if (job) return <span className="cf-save-check" role="status"><span className="cf-dot is-pending cf-pulse" aria-hidden="true" />{jobLabel(job)}</span>;
  if (checkStatus === "running") return <span className="cf-save-check" role="status"><span className="cf-dot is-pending cf-pulse" aria-hidden="true" />Checking…</span>;
  if (checkStatus === "unavailable") return <a className="cf-save-check" href="#/review" role="status" title="The last check couldn’t finish. Retry from the ⋯ menu or open Review.">Check unavailable</a>;
  return null;
}

/** True once `on` has held for `ms`; a conflict the store resolves on its own never flashes. */
function useLasting(on: boolean, ms: number): boolean {
  const [lasting, setLasting] = useState(false);
  useEffect(() => {
    if (!on) { setLasting(false); return; }
    const timer = window.setTimeout(() => setLasting(true), ms);
    return () => window.clearTimeout(timer);
  }, [on, ms]);
  return on && lasting;
}

/** The red status words, as an icon, once the header has no room for them. Hover, focus or tap shows the message. */
function SaveWarn({ message, detail }: { message: string; detail?: string }) {
  const ref = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const text = [message, detail].filter(Boolean).join(" ");
  return (
    <>
      <button
        ref={ref}
        type="button"
        className="cf-icon-btn is-xs is-plain cf-save-warn"
        aria-label={text}
        onPointerEnter={() => setOpen(true)}
        onPointerLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen((v) => !v)}
      >
        <CIcon name="warn" size={15} />
      </button>
      <Tip anchor={ref.current} open={open} id="cf-save-warn-tip" side="bottom">
        <span>{message}</span>
        {detail ? <p>{detail}</p> : null}
      </Tip>
    </>
  );
}

export function SaveStatus() {
  const { phase, saveStatus, savedNote, saveDetail, saveDraft, saveConflict: conflicted, saveConflictReview, reviewSaveConflict } = useCase();
  const saveConflict = useLasting(conflicted, 1500) || (saveConflictReview?.kind ?? "closed") !== "closed";
  // A submission on its way keeps the saved state; the page says editing is paused.
  const current = useCurrentApplication();
  if (phase !== "case") return null;
  if (current.readOnly) {
    const s = readOnlyStatus(current.app?.status);
    return <div className="cf-save" role="status"><Dot tone={s.tone} /><span className="cf-save-label">{s.label}</span></div>;
  }
  const map: Record<string, { tone: DotTone; label: string }> = {
    idle: { tone: "pending", label: "Not saved yet" },
    unsaved: { tone: "pending", label: "Unsaved" },
    saving: { tone: "pending", label: "Saving…" },
    saved: { tone: "done", label: "Saved" },
    failed: { tone: "blocking", label: savedNote || "Not saved" },
    gone: { tone: "blocking", label: savedNote },
  };
  const s = map[saveStatus] ?? map.idle;
  const problem = saveStatus === "failed" || saveStatus === "gone";
  const label = saveConflict ? "Saved changes need review" : s.label;
  const detail = saveDetail && saveDetail !== label ? saveDetail : "";
  return (
    <><div className={`cf-save${problem || saveConflict ? " is-problem" : ""}`} role="status" title={[savedNote, saveDetail].filter(Boolean).join(" · ") || undefined}>
      <Dot tone={s.tone} />
      <span className="cf-save-label">{label}</span>
      {(problem || saveConflict) && <SaveWarn message={label} detail={detail} />}
      {saveConflict && <button type="button" className="cf-btn is-xs" disabled={saveConflictReview?.kind === "loading"} onClick={() => void reviewSaveConflict()}>{saveConflictReview?.kind === "loading" ? "Loading…" : "Review changes"}</button>}
      {!saveConflict && saveStatus === "unsaved" && <button type="button" className="cf-btn is-xs is-ghost" onClick={() => void saveDraft()}>Save now</button>}
      {!saveConflict && saveStatus === "failed" && <button type="button" className="cf-btn is-xs" onClick={() => void saveDraft()}><CIcon name="retry" size={13} />Retry</button>}
      {saveStatus === "gone" && <a className="cf-btn is-xs" href="#/application?download=options">Keep a draft</a>}
    </div><SaveConflictDialog /></>
  );
}


/** Ring percentages for the four stages, from the same case, gaps and deck as the screens. */
function useStageProgress() {
  const { c, gaps, phase, checkedAt, engineGaps } = useCase();
  const session = useSession();
  const { options } = useDeckExtras();
  return useMemo(() => {
    if (phase !== "case") return { start: 0, questions: 0, review: 0, application: 0 };
    const deck = buildDeck(c, gaps, { ...options, seen: new Set(session.seen), includeDone: true });
    const { done, total } = deckProgress(deck);
    const groups = groupGaps(gaps, new Map(engineGaps.map((g) => [g.id, g.section])));
    const sectionsClear = [["A"], ["B", "facts"], ["C"], ["D", "process"]].filter((keys) => !keys.some((k) => (groups.get(k) ?? []).length)).length;
    return {
      start: c.description.trim() ? 100 : 0,
      questions: total ? (100 * done) / total : 0,
      review: checkedAt ? (100 * sectionsClear) / 4 : 0,
      application: 0,
    };
  }, [c, gaps, phase, checkedAt, engineGaps, session.seen, options]);
}

const PHONE = "(max-width: 760px)";
const signedInParam = (id: string | null, phase: AccountPhase) => (id && phase === "signed-in" ? id : null);
/** Tab-scoped application and owner ids, so another account never restores this selection. */
const OPEN_KEY = "batatis-open-application";
const OPEN_OWNER_KEY = "batatis-open-application-owner";
const remembered = (owner: string | null) => { try { return owner && sessionStorage.getItem(OPEN_OWNER_KEY) === owner ? sessionStorage.getItem(OPEN_KEY) : null; } catch { return null; } };
const remember = (id: string | null, owner?: string) => {
  try {
    if (id && owner) { sessionStorage.setItem(OPEN_KEY, id); sessionStorage.setItem(OPEN_OWNER_KEY, owner); }
    else { sessionStorage.removeItem(OPEN_KEY); sessionStorage.removeItem(OPEN_OWNER_KEY); }
  } catch { /* storage unavailable */ }
};
const isPhone = () => window.matchMedia(PHONE).matches;
/** `#/review/<case id>` (not the PDF-package pages): the file a reviewer has open. */
function reviewCaseOf(path: string): string | null {
  const m = /^\/review\/(.+)$/.exec(path);
  if (!m || /^package(\/|$)/.test(m[1])) return null;
  try { return decodeURIComponent(m[1]) || null; } catch { return null; }
}

/** What an account page is, for the assistant's context line. */
function accountPage(path: string): { screen: string; label: string } {
  if (path === "/settings") return { screen: "settings", label: "settings" };
  if (path === "/notifications") return { screen: "notifications", label: "notifications" };
  if (path === "/review") return { screen: "queue", label: "the review queue" };
  if (/^\/review\/package(\/|$)/.test(path)) return { screen: "package", label: "a PDF package" };
  if (path.startsWith("/review/")) return { screen: "review", label: "this file" };
  return { screen: "account", label: "your account" };
}

/**
 * `plain`: an account page (settings, notifications, the reviewer's queue and review) that draws its
 * own header; the shell gives it the rail and the assistant only. Reviewers never get the
 * application list or the stage header.
 */
export function Shell({ active, children, plain = false }: { active: Screen; children: ReactNode; plain?: boolean }) {
  const { c, phase, engineId, resetToWho, openCase, refreshCurrentCase, readSync, saveStatus, saveDraft, checkStatus, requestCheck, renameCase } = useCase();
  const [renaming, setRenaming] = useState<{ id: string; title: string } | null>(null);
  const [deleting, setDeleting] = useState<{ id: string; title: string } | null>(null);
  /** Applications with a pin or archive change on its way to the server. */
  const [pending, setPending] = useState<ReadonlySet<string>>(() => new Set());
  const account = useAccount();
  const notifications = useNotifications();
  const assistant = useAssistant();
  const [confirm, setConfirm] = useState(false);
  const [palette, setPalette] = useState(false);
  const [listNote, setListNote] = useState("");
  const [opening, setOpening] = useState<string | null>(null);
  /** Bumped by Start over / New application: a switch still saving or opening then leaves the new draft alone. */
  const freshDraft = useRef(0);
  const [listCollapsed, setListCollapsed] = useState(false);
  const [sheet, setSheet] = useState(false);
  const listRef = useRef<ApplicationListHandle>(null);
  const openRequest = useRef(0);
  const inCase = phase === "case";
  const progress = useStageProgress();
  const signedIn = account.phase === "signed-in";
  const signedOut = account.phase === "signed-out";
  const startingDraft = getSession().startRequested;
  const reviewer = account.user?.role === "reviewer";
  const bare = plain || reviewer;
  const onStage = !bare && STAGES.some((s) => s.screen === active);
  const route = useRoute();
  /** "none": the code library is browsing without an application (no title, stages or status). */
  const scope = useCodeScope();
  /** `#/application?case=<id>` (a notification): open that application, then drop the parameter. */
  const caseParam = signedInParam(route.params.get("case"), account.phase);
  /** The last stage page, so Applications in the rail returns to it from the code library. */
  const lastStage = useRef("#/");
  if (onStage) lastStage.current = location.hash || "#/";
  useEffect(() => { if (onStage) rememberStage(location.hash || "#/"); });

  useEffect(() => { bootAccount(); }, []);
  // The assistant's binding: who asks, about which application (none under the library's None;
  // a reviewer's is the file open in the review). Each binding keeps its own conversation.
  const reviewerContext = useRef<{ principal: string; caseId: string | null }>({ principal: "", caseId: null });
  const assistPrincipal = JSON.stringify([signedIn, account.user?.id, account.user?.role, account.user?.authority]);
  if (reviewerContext.current.principal !== assistPrincipal) reviewerContext.current = { principal: assistPrincipal, caseId: null };
  const routeReviewCase = reviewer ? reviewCaseOf(route.path) : null;
  if (routeReviewCase) reviewerContext.current.caseId = routeReviewCase;
  // Global reviewer pages keep the file selected in the assistant until another file is opened.
  const assistCase = reviewer ? reviewerContext.current.caseId : scope === "none" ? null : engineId;
  const assistMode: AssistBinding["mode"] = assistCase ? "case" : reviewer || scope === "none" ? "none" : "draft";
  const assistRow = assistCase ? account.applications?.find((a) => a.id === assistCase) : undefined;
  const assistName = reviewer || assistMode === "none" || !inCase ? "" : assistRow?.title || c.title || "";
  const assistFiles = assistMode === "case" && !reviewer ? (c.files ?? []).filter((f) => f.engineId).map((f) => ({ id: f.engineId!, name: f.name })) : [];
  const assistFilesKey = assistFiles.map((f) => f.id).join("|");
  const assistUpload = !reviewer && assistMode === "case" && !readOnly(assistRow?.status ?? "draft");
  const unsavedLifetime = `${engineGeneration()}:${c.id}`;
  useEffect(() => {
    setAssistantCase({
      accountId: signedIn ? account.user?.id ?? null : null,
      role: signedIn ? account.user?.role ?? null : null,
      authority: signedIn ? account.user?.authority ?? null : null,
      mode: signedIn ? assistMode : "none",
      caseId: signedIn ? assistCase : null,
      draftId: unsavedLifetime,
      caseName: assistName,
      canUpload: signedIn && assistUpload,
      files: signedIn ? assistFiles : [],
    });
  }, [signedIn, account.user?.id, account.user?.role, account.user?.authority, assistMode, assistCase, unsavedLifetime, assistName, assistUpload, assistFilesKey]); // eslint-disable-line react-hooks/exhaustive-deps
  // A new owned case appears in the list once the engine has created it.
  useEffect(() => { if (signedIn && engineId) void refreshApplications(); }, [signedIn, engineId]);
  useEffect(() => { if (signedIn && engineId && !reviewer) remember(engineId, account.user!.id); }, [signedIn, engineId, reviewer, account.user?.id]);

  // The existing notification poll is the only timer. Read/unread changes and repeated polls
  // do not re-fetch cases; a new status or message refreshes the list and its selected case.
  const seenNotifications = useRef({ session: -1, keys: new Set<string>() });
  useEffect(() => {
    if (!signedIn || reviewer || notifications.phase !== "ready") return;
    const session = accountSession();
    const previous = seenNotifications.current.session === session ? seenNotifications.current.keys : new Set<string>();
    const key = (n: (typeof notifications.items)[number]) => JSON.stringify([n.id, n.created_at, n.status]);
    const fresh = notifications.items.filter(n => !previous.has(key(n)));
    seenNotifications.current = { session, keys: new Set(notifications.items.map(key)) };
    if (!fresh.length) return;
    void refreshApplications();
    if (engineId && fresh.some(n => n.case_id === engineId)) void refreshCurrentCase();
  }, [signedIn, reviewer, notifications.phase, notifications.items, engineId, account.user]); // eslint-disable-line react-hooks/exhaustive-deps

  // After a reload, reopen the application this tab had open (signed in only).
  const restored = useRef(false);
  useEffect(() => {
    if (restored.current || account.phase === "probing") return;
    restored.current = true;
    if (reviewer || startingDraft) return;
    const id = remembered(account.user?.id ?? null);
    if (!id) return;
    if (!signedIn || inCase || caseParam) { if (!signedIn) remember(null); return; }
    const session = accountSession(), request = ++openRequest.current, token = engineGeneration();
    setOpening(id);
    void openCase(id, null).then((error) => {
      if (session !== accountSession() || request !== openRequest.current) return;
      setOpening(null);
      if (!error) return;
      if (!isEngineGeneration(token)) return;
      remember(null);
      resetToWho("That application is no longer available.");
    });
  }, [account.phase]); // eslint-disable-line react-hooks/exhaustive-deps
  // Screens without their own context: the assistant looks at the page (account pages by path).
  useEffect(() => {
    if (active === "questions" && !plain) return;
    const page = plain ? accountPage(route.path) : null;
    const label = page?.label ?? (active === "start" ? "your description" : active === "review" ? "your review" : active === "application" ? "your application" : active === "code" ? "the code library" : active === "comments" ? "the officer’s comments" : "your application");
    setAssistantContext({ screen: page?.screen ?? (active === "start" ? "describe" : active), label });
  }, [active, plain, route.path]);

  // The code library needs the room: the list folds away while it is open (⌘B or the header
  // button brings it back) and returns to how it was when the library closes.
  const listBeforeCode = useRef<boolean | null>(null);
  useEffect(() => {
    if (active === "code" && !bare) {
      if (listBeforeCode.current === null) {
        listBeforeCode.current = listCollapsed;
        setListCollapsed(true);
      }
    } else if (listBeforeCode.current !== null) {
      setListCollapsed(listBeforeCode.current);
      listBeforeCode.current = null;
    }
  }, [active, bare]); // eslint-disable-line react-hooks/exhaustive-deps

  /** An explicit open or close inside the library is what leaving it restores. */
  const keepList = (collapsed: boolean) => { if (listBeforeCode.current !== null) listBeforeCode.current = collapsed; };
  // The shortcut handler is registered once; it reads the current state from this ref.
  // Synced after commit, not during render: a render React discards must not leave its value in the ref.
  const listCollapsedNow = useRef(listCollapsed);
  useLayoutEffect(() => { listCollapsedNow.current = listCollapsed; });
  const toggleList = () => {
    if (isPhone()) return setSheet(true);
    const next = !listCollapsedNow.current;
    keepList(next);
    setListCollapsed(next);
  };

  // Cmd/Ctrl+B sidebar, +J assistant, +K search applications, +Shift+K search the code.
  useEffect(() => {
    if (signedOut) return;
    const on = (e: KeyboardEvent) => {
      // A page's own shortcut (the queue's ⌘K search) runs first and claims the key.
      if (!(e.metaKey || e.ctrlKey) || e.altKey || e.defaultPrevented) return;
      const k = e.key.toLowerCase();
      if (k === "b") { e.preventDefault(); toggleList(); }
      else if (k === "j") { e.preventDefault(); toggleAssistant(); }
      else if (k === "k" && e.shiftKey) { e.preventDefault(); setPalette((v) => !v); }
      else if (k === "k") {
        e.preventDefault();
        if (isPhone()) setSheet(true);
        else { keepList(false); setListCollapsed(false); }
        window.setTimeout(() => listRef.current?.focusSearch(), 0);
      }
    };
    const open = () => setPalette(true);
    // The assistant opens the application list the same way the rail does.
    const list = () => showApplicationsNow.current();
    document.addEventListener("keydown", on);
    window.addEventListener(OPEN_PALETTE, open);
    window.addEventListener(OPEN_APPLICATIONS, list);
    return () => { document.removeEventListener("keydown", on); window.removeEventListener(OPEN_PALETTE, open); window.removeEventListener(OPEN_APPLICATIONS, list); };
  }, [signedOut]);

  const deckDone = Math.round(progress.questions);
  const localRow: ApplicationSummary | null = inCase
    ? { id: engineId ?? "this-visit", title: c.title || "New application", status: "draft", authority: c.authority || null, updated_at: new Date().toISOString(), submitted_at: null, completeness: { answered: deckDone, total: 100 }, unread_messages: 0, reviewer: null, archived: false, pinned: false }
    : null;
  const saved = account.applications ?? [];
  // Signed in, a new draft shows at once, before the engine has listed it.
  // The open case's row shows this draft's name until the server has one, so header and list agree.
  const named = saved.map((a) => (a.id === engineId && !a.title?.trim() && inCase ? { ...a, title: c.title } : a));
  const items = signedIn ? (localRow && !named.some((a) => a.id === localRow.id) ? [localRow, ...named] : named) : localRow ? [localRow] : [];
  const selectedId = engineId ?? (localRow ? "this-visit" : null);
  const current = (engineId && saved.find((a) => a.id === engineId)) || null;

  const empty = !inCase && !getSession().draft.trim();
  const stages: StageRingItem[] = [
    { id: "start", label: "Describe", icon: "describe", href: "#/", pct: progress.start, current: active === "start" },
    { id: "questions", label: "Questions", icon: "questions", href: "#/questions", pct: progress.questions, current: active === "questions", hint: inCase ? undefined : "Starts with your description" },
    { id: "review", label: "Review", icon: "review", href: "#/review", pct: progress.review, current: active === "review", hint: inCase ? undefined : "Nothing to review yet" },
    { id: "application", label: "Application", icon: "file", href: "#/application", pct: current && ["submitted", "in_review", "accepted", "refused"].includes(current.status) ? 100 : progress.application, current: active === "application", hint: inCase ? undefined : "Nothing filled in yet" },
  ];

  const showApplications = () => {
    if (isPhone()) setSheet(true);
    else { keepList(false); setListCollapsed(false); }
    if (!onStage) location.hash = lastStage.current;
  };
  const showApplicationsNow = useRef(showApplications);
  useLayoutEffect(() => { showApplicationsNow.current = showApplications; });

  const destinations: RailDestination[] = reviewer ? [
    { id: "queue", label: "Review queue", icon: "table", href: "#/review", current: route.path === "/review" || route.path.startsWith("/review/") },
    { id: "code", label: "Code library", icon: "book", href: "#/code", current: active === "code" && !plain },
  ] : [
    {
      id: "applications",
      label: "Applications",
      icon: "inbox",
      onClick: showApplications,
      current: onStage,
      badge: items.some((a) => (a.status === "returned" || a.status === "refused") && a.unread_messages > 0),
    },
    { id: "code", label: "Code library", icon: "book", href: "#/code", current: active === "code", shortcut: `${MOD_KEY} ⇧ K` },
  ];

  async function startNew() {
    freshDraft.current += 1;
    openRequest.current++;
    const request = openRequest.current, session = accountSession();
    setOpening(null);
    setListNote("");
    if (inCase && !readSync().saved && !(await saveDraft())) {
      if (request === openRequest.current && session === accountSession()) setListNote(KEEP_OPEN_NOTE);
      return;
    }
    if (request !== openRequest.current || session !== accountSession()) return;
    remember(null);
    resetSession();
    resetRelevance();
    resetToWho(signedIn ? "" : undefined);
  }

  /** Open another saved application here (the list, notification links and the code library's picker share it). */
  async function switchTo(id: string): Promise<string | null> {
    if (!signedIn) return "Sign in to open a saved application.";
    if (opening) return "Another application is still opening.";
    // Choosing another application retires what the assistant was about to open, even if the switch fails.
    invalidateAssistantNavigation();
    const session = accountSession(), request = ++openRequest.current;
    // A newer open or another sign-in owns the list and the open application from then on.
    const stale = () => session !== accountSession() || request !== openRequest.current;
    setOpening(id);
    const mark = freshDraft.current;
    const superseded = () => freshDraft.current !== mark || stale();
    // Keep the open draft before switching; a failed save keeps it open and says so. A new draft started
    // meanwhile wins: nothing is opened over it and its description, files and role stay. The save state is
    // read when the switch starts (an answer derived since the last render is unsaved too).
    const error = await switchApplication(id, {
      inCase, saveStatus: readSync().saved ? saveStatus : "unsaved", saveDraft,
      openCase: (next) => (superseded() ? Promise.resolve(null) : openCase(next, null)),
      settle: () => { if (!superseded()) resetRelevance(); },
    });
    if (stale()) return null;
    setOpening(null);
    // A deleted or expired application leaves the list; a refused save changed nothing on the server.
    if (error && error !== KEEP_OPEN_NOTE) void refreshApplications();
    return error;
  }

  async function open(id: string, to?: string) {
    const refused = items.find((a) => a.id === id)?.status === "refused";
    const destination = to ?? (refused ? "#/application" : "#/questions");
    if (id === selectedId || id === engineId) {
      setListNote("");
      setOpenProblem(null);
      // Go there now: the refresh below finishes later, when the visitor may have moved on.
      if (to) location.replace(to);
      else if (refused) location.hash = destination;
      else if (!onStage) location.hash = lastStage.current;
      if (signedIn && engineId === id) {
        // The application already open here (a notification, or its own row): refresh its status, officer
        // updates and messages in place. It is never reopened over unsaved answers.
        const session = accountSession(), request = ++openRequest.current;
        const [, error] = await Promise.all([refreshApplications(), refreshCurrentCase()]);
        if (session !== accountSession() || request !== openRequest.current || engineCaseId() !== id) return;
        setListNote(error ?? "");
      }
      return;
    }
    if (!signedIn || opening) return;
    setListNote("");
    setOpenProblem(null);
    const mark = freshDraft.current, request = openRequest.current + 1, session = accountSession();
    const error = await switchTo(id);
    // Start over, a newer open or another sign-in meanwhile: stay where they left things.
    if (freshDraft.current !== mark || openRequest.current !== request || session !== accountSession()) return;
    if (error) {
      setListNote(error);
      // A link (a notification's comments) says why on its page; the open application stays as it was.
      if (to) setOpenProblem({ id, text: error });
      return;
    }
    location.hash = destination;
  }

  useEffect(() => {
    if (!caseParam) return;
    // A notification can target the application already open here: open() refreshes it in place.
    void open(caseParam, `#${route.path || "/"}`);
  }, [caseParam]); // eslint-disable-line react-hooks/exhaustive-deps

  /** Pin, unpin, archive or restore: the row moves once the server has saved it; the open application stays open. */
  async function setPreference(a: ApplicationSummary, patch: { pinned?: boolean; archived?: boolean }, verb: string) {
    setListNote("");
    setPending((p) => new Set(p).add(a.id));
    const error = await setApplicationPreferences(a.id, patch);
    setPending((p) => { const next = new Set(p); next.delete(a.id); return next; });
    if (error) setListNote(`Couldn’t ${verb} “${a.title || "this application"}”. ${error}`);
  }

  /** After the server's 204: if it was the open application, open the newest one left, else start fresh. */
  async function removeApplication(id: string): Promise<string | null> {
    const error = await deleteApplication(id);
    if (error) return error;
    if (id !== engineId) return null;
    remember(null);
    resetSession();
    resetRelevance();
    const left = groupApplications(saved.filter((a) => a.id !== id));
    const next = [...left.pinned, ...left.active][0];
    if (next && !(await openCase(next.id, null))) {
      location.hash = "#/questions";
      return null;
    }
    resetToWho("");
    return null;
  }

  function actionsFor(a: ApplicationSummary): RowAction[] {
    const editable = !readOnly(a.status);
    const rename: RowAction = { id: "rename", label: "Rename", icon: "pencil", disabled: !editable, hint: editable ? undefined : "Read-only", onSelect: () => setRenaming({ id: a.id, title: a.title }) };
    // Pin, archive and delete belong to applications saved to the account.
    if (!signedIn || !saved.some((s) => s.id === a.id)) return [rename];
    const waiting = pending.has(a.id);
    return [
      rename,
      ...(a.archived ? [] : [a.pinned
        ? { id: "unpin", label: "Unpin", icon: "pinOff", disabled: waiting, onSelect: () => void setPreference(a, { pinned: false }, "unpin") } as RowAction
        : { id: "pin", label: "Pin", icon: "pin", disabled: waiting, onSelect: () => void setPreference(a, { pinned: true }, "pin") } as RowAction]),
      a.archived
        ? { id: "restore", label: "Restore", icon: "restore", disabled: waiting, onSelect: () => void setPreference(a, { archived: false }, "restore") }
        : { id: "archive", label: "Archive", icon: "archive", disabled: waiting, onSelect: () => void setPreference(a, { archived: true }, "archive") },
      // Any owned application: the server's DELETE policy decides, and its refusal is shown in the dialog.
      { id: "delete", label: "Delete…", icon: "trash", destructive: true, separatorBefore: true, disabled: waiting, onSelect: () => setDeleting({ id: a.id, title: a.title }) },
    ];
  }

  const list = (
    <ApplicationList
      ref={listRef}
      items={items}
      selectedId={opening ?? selectedId}
      onSelect={(id) => void open(id)}
      actionsFor={actionsFor}
      onNew={() => {
        if (!inCase) {
          setListNote("");
          location.hash = "#/";
          window.setTimeout(() => document.getElementById("cf-describe")?.focus(), 0);
        } else if (signedIn) startNew();
        else setConfirm(true);
      }}
      loading={account.loadingList}
      error={account.listError}
      note={opening ? "Opening…" : listNote || (!signedIn && inCase ? "Saved for this visit only." : undefined)}
      empty={<p className="cf-applist-note">{empty ? "Describe what you’re building to start your first application." : "Your new application appears here once it starts."}</p>}
    />
  );

  // The saved name when the list has it (so header and list always agree), else this draft's.
  const title = inCase ? current?.title || c.title || "New application" : "New application";
  // In the code library the picker names the application; under None nothing of the application shows.
  const library = active === "code";
  const withCase = inCase && scope === "application";
  const header = signedOut ? <AppHeader title="Batatis" right={<a className="cf-btn is-ghost is-sm" href="#/signin">Sign in</a>} /> : (
    <AppHeader
      title={library ? undefined : title}
      onRename={inCase ? renameCase : undefined}
      renameDisabled={readOnly(current?.status)}
      stages={scope === "none" ? undefined : stages}
      onToggleList={toggleList}
      listOpen={!listCollapsed}
      toggleHint={`${MOD_KEY} B`}
      right={
        <>
          {scope === "application" && <CheckStatus />}
          {scope === "application" && <SaveStatus />}
          <AskButton />
          <MoreMenu
            items={[
              { label: "Look up code", hint: `${MOD_KEY} ⇧ K`, onClick: openPalette },
              { label: "Code library", href: "#/code" },
              ...(withCase && current && current.status !== "draft" ? [{ label: current.unread_messages > 0 ? `Comments (${current.unread_messages} new)` : "Comments", href: "#/comments" }] : []),
              ...(withCase && current?.status !== "refused" && checkStatus === "unavailable" ? [{ label: "Try the check again", onClick: () => void requestCheck(true), separator: true }] : []),
              ...(withCase
                ? [
                    { label: "Download draft", href: "#/application?download=draft", separator: true },
                    { label: signedIn ? "New application" : "Start over", onClick: () => (signedIn ? startNew() : setConfirm(true)) },
                  ]
                : []),
            ]}
          />
        </>
      }
    />
  );


  const appSwitch: ApplicationSwitch = { items, openId: selectedId, opening, switchTo };
  // Reviewers' code library has no application header; it keeps a slim one so Ask stays one tap away.
  const bareHeader = bare && library && !plain ? <AppHeader right={<AskButton />} /> : null;

  return (
    <AskHost.Provider value={true}>
      {/* Nothing native is offered while another application is opening. */}
      <NativePanels ownedCaseId={!reviewer && !opening && assistRow?.id === engineId ? engineId : null} />
    <ApplicationSwitchContext.Provider value={appSwitch}>
      <AppLayout
        rail={signedOut ? null : <Rail destinations={destinations} notificationsSlot={<NotificationsBell />} accountSlot={<AccountButton />} />}
        list={bare || signedOut ? undefined : list}
        header={bare ? bareHeader : header}
        banner={onStage && (current?.status === "returned" || current?.status === "refused") ? <ReturnedBanner key={`${current.id}:${current.status}`} app={current} /> : onStage && current?.status === "in_review" ? <RequestBanner app={current} /> : null}
        assistant={!signedOut && assistant.open ? <AssistantPanel /> : null}
        listCollapsed={listCollapsed}
        sheetOpen={sheet}
        onSheetClose={() => setSheet(false)}
      >
        {children}
      </AppLayout>
      <CodePalette open={palette} onClose={() => setPalette(false)} />
      <RenameDialog
        target={renaming}
        onClose={() => setRenaming(null)}
        onSave={(id, next) => (id === selectedId ? renameCase(next) : saveTitle(id, next).then(() => null, titleError))}
      />
      <DeleteDialog target={deleting} onClose={() => setDeleting(null)} onDelete={removeApplication} />
      <ConfirmDialog
        open={confirm}
        title="Start a new application?"
        body={<p>Without an account this clears your answers in this browser. Files already uploaded are not deleted now; they expire with the case. Download a draft first if you need a copy.</p>}
        cancel="Keep working"
        confirm="Start new"
        onClose={() => setConfirm(false)}
        onConfirm={() => {
          setConfirm(false);
          startNew();
        }}
      />
    </ApplicationSwitchContext.Provider>
    </AskHost.Provider>
  );
}
