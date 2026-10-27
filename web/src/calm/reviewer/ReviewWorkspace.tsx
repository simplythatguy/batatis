/**
 * #/review/<caseId>: the officer's workspace. The application is the screen, with each finding under
 * the row it is about; the rail holds the counts, the request exactly as it will be sent, the
 * messages, and the decision for the version on screen. One status line says what needs attention.
 * Data and actions live here; the pieces below only draw what they are given.
 */
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type Dispatch, type ReactNode, type SetStateAction } from "react";
import { AccountsError, claimConflict, review, type Claim, type Message } from "../../api/accounts";
import { EngineError } from "../../api/client";
import { packageReview, type ReviewTarget } from "../../api/packageReview";
import type { Case, Finding, PackageReviewIndex, ProfessionalRequirementRequest, ReviewSession, Workspace } from "../../api/types.gen";
import { accountSession, useAccount } from "../account";
import { AcIcon, Avatar, PageHead } from "../auth/bits";
import { ExpiryNotice } from "../ExpiryNotice";
import { getNotificationsState, subscribeNotifications } from "../notifications/notifications";
import { MoreMenu } from "../shell/MoreMenu";
import { ConfirmDialog, Modal } from "../ui";
import { CloseOutPanel } from "./CloseOutPanel";
import { refusalDecision, sentence } from "./packageView";
import { officerItem } from "./requestDraft";
import { ProfessionalRequirement } from "./ProfessionalRequirement";
import { sinceLabel } from "./queue";
import { RefuseDialog } from "./RefuseDialog";
import { loadQueue, patchRow, setBlocking, useQueue } from "./reviewData";
import { readReviewSnapshot } from "./reviewSnapshot";
import { sheetFromEngine } from "./sheet";
import { SubmissionHistory } from "./SubmissionHistory";
import { mergeThreadMessages } from "./threadMessages";
import { useRequestDraft } from "./useRequestDraft";
import { Messages } from "./Messages";
import { OpenQuestions } from "./OpenQuestions";
import { DecideStage } from "./DecideStage";
import { FindingFooter, FindingStep } from "./FindingStep";
import { ReadSheet } from "./ReadSheet";
import { StageButton } from "../shell/AppHeader";
import { Icon24 } from "../icons";
import { localField } from "../../intakeFields";
import { StatusPill } from "./ReviewQueue";
import { allAnchors, anchorFor, changedFields, findingState, SECTIONS, sheetRows, targetOptions, workspaceDecision } from "./workspaceView";
import "./review.css";

type Snapshot = Awaited<ReturnType<typeof readReviewSnapshot>>;
type Stage = "read" | "findings" | "decide";
type DraftReport = { pending: boolean; trouble: string; discard: () => void };
type IndexState = "loading" | "ready" | "failed" | "unavailable";
type DecisionPreview = { kind: "return"; caseVersion: number; reviewVersion: number; text: string; count: number }
  | { kind: "accept"; caseVersion: number; reviewVersion?: number };
const READ_ONLY_LIMITS = { intro: 0, item_text: 0, items: 0, text: 0 };
const errorText = (e: unknown, fallback: string) => e instanceof EngineError ? e.detail : fallback;

export function ReviewWorkspace({ caseId, phoneTools }: { caseId: string; phoneTools?: ReactNode }) {
  const { user } = useAccount();
  const me = user?.id ?? null;
  const q = useQueue();
  const target: ReviewTarget = useMemo(() => ({ kind: "case", id: caseId }), [caseId]);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [messages, setMessages] = useState<Message[] | null>(null);
  const [messageDraft, setMessageDraft] = useState("");
  const [loadError, setLoadError] = useState("");
  const [refreshError, setRefreshError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [index, setIndex] = useState<PackageReviewIndex | null>(null);
  const [indexState, setIndexState] = useState<IndexState>("loading");
  const [shown, setShown] = useState<ReviewSession | null>(null);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState("");
  const [busy, setBusy] = useState<"" | "claim" | "release" | "decision" | "professional">("");
  const [actionError, setActionError] = useState("");
  const [conflict, setConflict] = useState<Claim | null>(null);
  const [takeover, setTakeover] = useState(false);
  const [preview, setPreview] = useState<DecisionPreview | null>(null);
  const [decisionError, setDecisionError] = useState("");
  const [refusing, setRefusing] = useState(false);
  const [legacyReturn, setLegacyReturn] = useState(false);
  const [legacyText, setLegacyText] = useState("");
  const [professionalEditing, setProfessionalEditing] = useState(false);
  const [draftPending, setDraftPending] = useState(false);
  // A save that failed or a draft the server would refuse: shown in the status line with a way out.
  const [draftTrouble, setDraftTrouble] = useState<{ text: string; discard: () => void } | null>(null);
  // Where the officer is: the application, the findings one at a time, or the decision. null = not chosen yet.
  const [stage, setStage] = useState<Stage | null>(null);
  // Bumped by the header's message button: the decision page opens with the messages unfolded.
  const [messagesAsk, setMessagesAsk] = useState(0);
  const upload = useRef<HTMLInputElement>(null);
  const scope = useRef({ caseId, session: accountSession() });
  const reads = useRef(0), indexReads = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const autoClaimed = useRef("");
  const autoRan = useRef("");
  const actionPending = useRef(false);
  const draftDirty = useRef(false);
  const protectedInteraction = useRef(false);
  const deferredRefresh = useRef(false);
  const indexRef = useRef(index);
  indexRef.current = index;
  protectedInteraction.current = Boolean(busy || draftPending || preview || refusing || takeover || professionalEditing || legacyReturn || running);
  useLayoutEffect(() => {
    scope.current = { caseId, session: accountSession() };
    return () => { reads.current++; indexReads.current++; controller.current?.abort(); };
  }, [caseId, user]);
  const live = useCallback((session: ReturnType<typeof accountSession>) => scope.current.caseId === caseId && scope.current.session === session && accountSession() === session, [caseId]);

  const reload = useCallback(async (mode: "replace" | "background" | "action" = "action") => {
    const session = accountSession(), sequence = ++reads.current;
    controller.current?.abort();
    const ctl = new AbortController(); controller.current = ctl;
    const current = () => live(session) && sequence === reads.current;
    setRefreshing(true); setRefreshError("");
    if (mode === "replace") { setSnapshot(null); setMessages(null); setLoadError(""); }
    try {
      const next = await readReviewSnapshot(caseId, ctl.signal);
      if (!current()) return null;
      if (mode === "background" && protectedInteraction.current) { deferredRefresh.current = true; return null; }
      setSnapshot(next); setMessages(previous => mergeThreadMessages(previous, next.messages)); setLoadError("");
      return next.c;
    } catch (e) {
      if (!current()) return null;
      if (mode === "replace" || (e instanceof EngineError && e.status === 404)) {
        setSnapshot(null); setLoadError(e instanceof EngineError && e.status === 404 ? "This application isn’t available to you. It may have been withdrawn or sent to another authority." : errorText(e, "The application didn’t load."));
      } else setRefreshError(errorText(e, "The updated application didn’t load. Try again."));
      return null;
    } finally { if (current()) setRefreshing(false); }
  }, [caseId, live]);

  const loadIndex = useCallback(async (keepShown = false) => {
    const session = accountSession(), sequence = ++indexReads.current;
    try {
      const next = await packageReview.index(target);
      if (!live(session) || sequence !== indexReads.current) return null;
      const previous = indexRef.current;
      setIndex(next); setIndexState("ready");
      setBlocking(target.id, next.workspace?.current ? next.workspace.tally.required : null);
      setShown(current => {
        if (!keepShown || !current || !next.latest) return next.latest;
        // The same version, refreshed (sent, saved elsewhere), or a newer one while the latest was on screen.
        if (current.version === next.latest.version) return next.latest;
        if (current.version === previous?.latest?.version && next.latest.version > current.version) return next.latest;
        return current;
      });
      return next;
    } catch (e) {
      if (!live(session) || sequence !== indexReads.current) return null;
      setIndexState(e instanceof EngineError && (e.status === 404 || e.status === 405) ? "unavailable" : "failed");
      return null;
    }
  }, [target, live]);

  const refresh = useCallback((force = false) => {
    if (!force && protectedInteraction.current) { deferredRefresh.current = true; return; }
    deferredRefresh.current = false;
    void reload(force ? "action" : "background");
    void loadIndex(true);
  }, [reload, loadIndex]);

  useEffect(() => {
    setIndex(null); setShown(null); setIndexState("loading"); setRunError(""); setActionError(""); setConflict(null);
    setBusy(""); setRunning(false); setPreview(null); setRefusing(false); setTakeover(false); setLegacyReturn(false); setLegacyText("");
    setMessageDraft(""); setStage(null); setDraftPending(false); setDraftTrouble(null); draftDirty.current = false; actionPending.current = false;
    autoClaimed.current = ""; autoRan.current = "";
    void reload("replace"); void loadIndex(); if (!q.rows.length) void loadQueue();
  }, [caseId, user, reload, loadIndex]); // The queue itself never resets an open document.

  useEffect(() => {
    if (!protectedInteraction.current && deferredRefresh.current && !refreshing) refresh();
  }, [busy, draftPending, preview, refusing, takeover, professionalEditing, legacyReturn, running, refreshing, refresh]);
  useEffect(() => {
    if (user?.role !== "reviewer" || !user.authority) return;
    const session = accountSession();
    const key = (n: ReturnType<typeof getNotificationsState>["items"][number]) => JSON.stringify([n.id, n.created_at, n.status]);
    let seen = new Set(getNotificationsState().items.map(key));
    const stop = subscribeNotifications(() => {
      const notes = getNotificationsState();
      if (!live(session) || notes.phase !== "ready") return;
      const changed = notes.items.some(n => n.case_id === caseId && !seen.has(key(n)));
      seen = new Set(notes.items.map(key));
      if (changed) refresh();
    });
    const onPick = (event: MouseEvent) => {
      if (!live(session) || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.altKey || event.shiftKey) return;
      const link = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>("a.ac-note") : null;
      if (link?.getAttribute("href") === `#/review/${encodeURIComponent(caseId)}`) refresh();
    };
    document.addEventListener("click", onPick);
    return () => { stop(); document.removeEventListener("click", onPick); };
  }, [caseId, user, live, refresh]);

  const c = snapshot?.c ?? null;
  const row = q.rows.find(row => row.id === caseId);
  const status = c?.status ?? row?.status ?? "submitted";
  const claim = c ? c.claim : row?.claim ?? null;
  const mine = Boolean(me && claim?.reviewer_id === me);
  const canReview = mine && status === "in_review";
  const otherClaim = conflict ?? (!mine && claim && (status === "in_review" || status === "submitted") ? claim : null);
  const unclaimed = status === "submitted" && !claim && !otherClaim;
  const resumable = status === "submitted" && mine;
  const latest = index?.latest ?? null;
  const workspace = shown && index?.workspace?.version === shown.version && latest?.version === shown.version ? index.workspace : null;
  const onLatest = Boolean(shown && latest?.version === shown.version);
  const currentReview = Boolean(workspace?.current && workspace.case_version === c?.version);
  const editable = canReview && onLatest && currentReview && !shown?.information_request.sent_at && indexState === "ready" && !running && !refreshError;
  const applicant = row?.applicant.name || "The applicant";
  const title = c?.title?.trim() || row?.title?.trim() || "Application";
  const closeOut = index?.close_out;
  const professionalPending = Boolean(snapshot?.gaps?.some(g => g.field === "professional_requirement" && g.severity === "blocking"));
  const unread = (messages ?? []).filter(m => !m.read_by_me && m.kind !== "status" && m.author.id !== me).length;
  useEffect(() => { if (c && messages) patchRow(caseId, { unread_messages: unread }); }, [caseId, c, unread, messages === null]);

  async function doClaim(takeOver = false) {
    if (actionPending.current) return;
    const session = accountSession(); actionPending.current = true; setBusy("claim"); setActionError("");
    try {
      const next = await review.claim(caseId, takeOver);
      if (!live(session)) return;
      setConflict(null); setTakeover(false); patchRow(caseId, { claim: next, status: "in_review" }, session);
      await reload(); await loadIndex();
    } catch (e) {
      if (!live(session)) return;
      const other = claimConflict(e);
      if (other) setConflict(other); else setActionError(errorText(e, "The claim didn’t save. Try again."));
      await reload();
    } finally { if (live(session)) { actionPending.current = false; setBusy(""); } }
  }
  useEffect(() => {
    if (!c || !me || !unclaimed || autoClaimed.current === caseId) return;
    autoClaimed.current = caseId; void doClaim();
  }, [c, me, unclaimed, caseId]); // One attempt per opened application; errors offer a retry.

  async function run(files?: File[]) {
    if (!canReview || actionPending.current || draftDirty.current) return;
    const session = accountSession(); actionPending.current = true; setRunning(true); setRunError("");
    try {
      const next = await packageReview.run(target, files);
      if (!live(session)) return;
      setShown(next); await loadIndex(true); await reload();
    } catch (e) {
      if (!live(session)) return;
      if (e instanceof AccountsError && e.status === 503 && /code database/i.test(e.detail)) setIndexState("unavailable");
      else setRunError(errorText(e, "The review didn’t run. Try again."));
    } finally { if (live(session)) { actionPending.current = false; setRunning(false); } }
  }
  useEffect(() => {
    const key = `${caseId}:${c?.version ?? ""}`;
    const needsRun = canReview && c && indexState === "ready" && (!latest || (index?.workspace && !index.workspace.current) || latest.case_version !== c.version);
    if (!needsRun || running || busy || draftPending || preview || refusing || legacyReturn || professionalEditing || autoRan.current === key) return;
    autoRan.current = key; void run();
  }, [canReview, c, index, indexState, latest, caseId, running, busy, draftPending, preview, refusing, legacyReturn, professionalEditing]);

  async function release() {
    if (actionPending.current || draftDirty.current) return;
    const session = accountSession(); actionPending.current = true; setBusy("release"); setActionError("");
    try { await review.release(caseId); if (live(session)) { patchRow(caseId, { claim: null, status: "submitted" }); window.location.hash = "#/review"; } }
    catch (e) { if (live(session)) setActionError(errorText(e, "The claim wasn’t released. Try again.")); }
    finally { if (live(session)) { actionPending.current = false; setBusy(""); } }
  }
  async function pickVersion(version: number) {
    if (draftDirty.current || actionPending.current || preview || refusing || version === shown?.version) return;
    const session = accountSession(), sequence = ++indexReads.current; setRunError("");
    try {
      const next = latest?.version === version ? latest : await packageReview.version(target, version);
      if (live(session) && sequence === indexReads.current) { setShown(next); setStage("read"); }
    } catch (e) { if (live(session)) setRunError(errorText(e, "That review version didn’t load. Try again.")); }
  }
  async function afterDecision(next: Case) {
    setSnapshot(previous => previous ? { ...previous, c: next } : previous);
    patchRow(caseId, { status: next.status, claim: next.claim });
    await reload(); await loadIndex(true); void loadQueue();
  }
  function openPreview(kind: "return" | "accept") {
    if (!c || actionPending.current || draftDirty.current) return;
    if (kind === "return") {
      if (!editable || !workspace?.tally.asked || !shown) return;
      setPreview({ kind, caseVersion: c.version, reviewVersion: shown.version, text: shown.information_request.text, count: workspace.tally.asked });
    } else {
      if (indexState === "unavailable") {
        if (!canReview || snapshot?.gaps === null || snapshot?.gapError || snapshot?.gaps.some(g => g.severity === "blocking")) return;
        setPreview({ kind, caseVersion: c.version });
      } else {
        if (!editable || !workspace?.gate.can_accept || !shown) return;
        setPreview({ kind, caseVersion: c.version, reviewVersion: shown.version });
      }
    }
    setDecisionError("");
  }
  async function decide() {
    if (!preview || !c || actionPending.current || draftDirty.current || decisionError) return;
    const session = accountSession(); actionPending.current = true; setBusy("decision"); setDecisionError("");
    try {
      const next = preview.kind === "return"
        ? await packageReview.returnWithRequest(caseId, preview.reviewVersion, { expected_version: preview.caseVersion, text: preview.text })
        : await review.decide(caseId, { outcome: "accept", expected_version: preview.caseVersion, ...(preview.reviewVersion === undefined ? {} : { review_version: preview.reviewVersion }) });
      if (!live(session)) return;
      setPreview(null); await afterDecision(next);
    } catch (e) {
      if (!live(session)) return;
      setDecisionError(errorText(e, "The decision didn’t save. Try again."));
      if (e instanceof EngineError && [0, 404, 409].includes(e.status)) { await reload(); await loadIndex(true); }
    } finally { if (live(session)) { actionPending.current = false; setBusy(""); } }
  }
  async function sendRefusal(reasons: string) {
    if (!c || !canReview || draftDirty.current || actionPending.current) throw new Error("Save the request and refresh the application before deciding.");
    const session = accountSession(); actionPending.current = true; setBusy("decision");
    try {
      const next = await review.decide(caseId, refusalDecision(reasons, c.version));
      if (!live(session)) return;
      setRefusing(false); await afterDecision(next);
    } catch (e) { if (live(session) && e instanceof EngineError && [404, 409].includes(e.status)) { await reload(); await loadIndex(true); } throw e; }
    finally { if (live(session)) { actionPending.current = false; setBusy(""); } }
  }
  async function sendLegacyReturn() {
    if (!c || !canReview || indexState !== "unavailable" || legacyText.trim().length < 10 || actionPending.current) return;
    const session = accountSession(); actionPending.current = true; setBusy("decision"); setDecisionError("");
    try {
      const next = await review.decide(caseId, { outcome: "return", expected_version: c.version, message: legacyText.trim(), items: [] });
      if (!live(session)) return;
      setLegacyReturn(false); setLegacyText(""); await afterDecision(next);
    } catch (e) { if (live(session)) { setDecisionError(errorText(e, "The return didn’t save. Try again.")); await reload(); } }
    finally { if (live(session)) { actionPending.current = false; setBusy(""); } }
  }
  async function resolveProfessional(body: ProfessionalRequirementRequest) {
    const session = accountSession(); if (actionPending.current || draftDirty.current) throw new Error("Save the request changes first.");
    actionPending.current = true; setBusy("professional");
    try { await review.resolveProfessional(caseId, body); if (live(session)) { await reload(); await loadIndex(true); } }
    catch (e) { if (live(session)) { await reload(); await loadIndex(true); } throw e; }
    finally { if (live(session)) { actionPending.current = false; setBusy(""); } }
  }

  const draftChanged = useCallback((state: DraftReport) => {
    draftDirty.current = state.pending;
    setDraftPending(state.pending);
    setDraftTrouble(state.trouble ? { text: state.trouble, discard: state.discard } : null);
  }, []);
  const adoptIndex = (next: PackageReviewIndex) => { setBlocking(caseId, next.workspace?.current ? next.workspace.tally.required : null); setIndex(next); if (next.latest) setShown(next.latest); setIndexState("ready"); };
  const versions = index?.sessions ?? [];
  const historical = Boolean(shown && latest && shown.version < latest.version);
  const sheet = c ? sheetFromEngine(c, snapshot?.information) : null;
  const canRecord = Boolean(me && (c?.decision?.by_id === me || claim?.reviewer_id === me));
  const outcome = closeOut
    ? <CloseOutPanel c={closeOut} canRecord={canRecord} onChange={(next) => setIndex((previous) => (previous ? { ...previous, close_out: next } : previous))} />
    : null;
  const professional = c && (
    <ProfessionalRequirement c={c} editable={canReview && !draftPending && !historical} busy={Boolean(busy) || running || refreshing}
      unresolved={professionalPending} onResolve={resolveProfessional} onEditingChange={setProfessionalEditing} />
  );
  const idle = !busy && !running && !draftPending;
  const menu = [
    ...(canReview ? [
      { label: running ? "Reading…" : "Run the review again", onClick: () => void run(), disabled: !idle },
      { label: "Review uploaded PDFs", onClick: () => upload.current?.click(), disabled: !idle },
    ] : []),
    ...versions.filter((v) => v.version !== shown?.version).map((v, i) => ({
      label: `Open v${v.version}${v.version === latest?.version ? " · latest" : ""}`,
      onClick: () => void pickVersion(v.version), disabled: !idle, separator: i === 0 && canReview,
    })),
    { label: "Refresh", onClick: () => refresh(true), disabled: !idle, separator: true },
    ...(canReview ? [{ label: busy === "release" ? "Releasing…" : "Stop reviewing", onClick: () => void release(), disabled: !idle }] : []),
  ];

  /** The one line under the header: what needs the officer's attention, with its action. */
  function statusLine(): { tone: string; text: ReactNode; action?: ReactNode; role?: "alert" | "status" } | null {
    const retry = (label: string, onClick: () => void, disabled = false) =>
      <button type="button" className="cf-btn is-xs" disabled={disabled} onClick={onClick}>{label}</button>;
    if (unclaimed) {
      return busy === "claim" || !actionError
        ? { tone: "pending", text: "Opening the review…", role: "status" }
        : { tone: "blocking", text: `Not picked up · ${actionError}`, role: "alert", action: retry("Pick up", () => void doClaim()) };
    }
    if (draftTrouble) {
      return { tone: "blocking", text: draftTrouble.text, role: "alert",
        action: <button type="button" className="cf-btn is-xs" onClick={draftTrouble.discard}>Discard my changes</button> };
    }
    if (actionError) return { tone: "blocking", text: actionError, role: "alert" };
    if (refreshError) return { tone: "blocking", text: refreshError, role: "alert", action: retry("Try again", () => refresh(true)) };
    if (otherClaim) {
      return { tone: "pending", text: <><Avatar name={otherClaim.reviewer_name} size="sm" />{otherClaim.reviewer_name} is reviewing this · {sinceLabel(otherClaim.claimed_at)}</>,
        action: retry("Take over", () => setTakeover(true), Boolean(busy)) };
    }
    if (resumable) return { tone: "warning", text: "Resubmitted · reserved for you", action: retry("Resume review", () => void doClaim(), Boolean(busy)) };
    if (running) return { tone: "pending", text: "Reading the application…", role: "status" };
    if (runError) return { tone: "blocking", text: runError, role: "alert", action: retry("Try again", () => void run(), !idle) };
    if (indexState === "failed") return { tone: "blocking", text: "The review didn’t load · decisions wait", role: "alert", action: retry("Try again", () => { setIndexState("loading"); void loadIndex(true); }) };
    if (indexState === "unavailable") return { tone: "pending", text: "No automatic review on this server · the completeness checklist decides" };
    if (historical && latest) return { tone: "pending", text: `v${shown?.version} · an earlier review, read-only`, action: retry(`Back to v${latest.version}`, () => void pickVersion(latest.version)) };
    if (canReview && shown && !currentReview) return { tone: "warning", text: "The application changed after this review", action: retry("Review again", () => void run(), !idle) };
    return null;
  }
  const line = c ? statusLine() : null;

  const findingsCount = (shown?.findings ?? []).filter((f) => f.key !== "peer_review:signal").length + (workspace?.rulebook.length ?? 0);
  const decided = status === "returned" || status === "accepted" || status === "refused";
  // The first place to land: the decision once there is one, else the findings, else the decision.
  const at: Stage = stage ?? (decided || !findingsCount ? "decide" : "findings");
  const toLook = workspace?.tally.verify ?? 0;
  const go = (next: Stage) => setStage(next);

  const stages = shown && indexState !== "unavailable" && (
    <nav className="cf-stages rw-stages" aria-label="Review">
      <StageButton id="rw-read" label="Application" ariaLabel="Application" icon={<AcIcon name="doc" size={16} />} pct={100} current={at === "read"} onClick={() => go("read")} />
      <StageButton id="rw-findings" label="Findings" icon={<AcIcon name="alert" size={16} />} current={at === "findings"}
        ariaLabel={`Findings, ${findingsCount}${toLook ? `, ${toLook} to look at` : ""}`}
        pct={findingsCount ? Math.round(100 * (findingsCount - toLook) / findingsCount) : 100}
        count={at === "findings" ? undefined : toLook || undefined} disabled={findingsCount ? undefined : "No findings"} onClick={() => go("findings")} />
      <StageButton id="rw-decide" label="Decide" ariaLabel="Decide" icon={<AcIcon name="scale" size={16} />} pct={decided ? 100 : 0} done={decided} current={at === "decide"} onClick={() => go("decide")} />
    </nav>
  );

  return (
    <div className="ac-page rw-page">
      <PageHead
        title={<><a className="ac-crumb" href="#/review">Queue</a><span className="ac-crumb-sep" aria-hidden="true">/</span><span className="ac-crumb-leaf" title={title}>{title}</span></>}
        meta={c && <StatusPill a={{ status, claim, submission_number: c.submission_number }} />}
        center={stages ? <div className="rv-head-steps">{stages}</div> : undefined}
        phoneTools={phoneTools}
        right={
          <>
            <button type="button" className="cf-icon-btn rw-head-msg" aria-label={unread ? `Messages, ${unread} new` : "Messages"} title="Messages"
              onClick={() => { go("decide"); setMessagesAsk((n) => n + 1); }}>
              <Icon24 name="msg" size={17} />{unread > 0 && <span className="rw-n is-new">{unread}</span>}
            </button>
            {c && <MoreMenu items={menu} />}
          </>
        }
      />
      {loadError ? (
        <div className="ac-page-body is-narrow">
          <p className="ac-empty" role="alert">{loadError}</p>
          <div className="cf-row-actions">
            <a className="cf-btn is-primary" href="#/review">Back to the queue</a>
            <button type="button" className="cf-btn" onClick={() => refresh(true)}>Try again</button>
          </div>
        </div>
      ) : !c || !snapshot || !sheet ? (
        <p className="ac-empty" role="status">Loading the application…</p>
      ) : (
        <div className="rw-body">
          {line && (
            <div className={`rw-line is-${line.tone}`} role={line.role}>
              <span className="cf-dot" aria-hidden="true" />
              <span className="rw-line-t">{line.text}</span>
              {line.action}
            </div>
          )}
          {shown && indexState !== "unavailable" ? (
            <SessionWorkspace key={`${shown.package_id}:${shown.version}:${me}`} stage={at} onStage={go} messagesAsk={messagesAsk}
              c={c} snapshot={snapshot} session={shown} workspace={workspace} target={target} applicant={applicant}
              editable={editable} busy={Boolean(busy) || running || refreshing} showDecision={canReview && !historical && !closeOut}
              historical={historical} status={status} messages={messages} onMessages={setMessages} me={me}
              messageDraft={messageDraft} onMessageDraft={setMessageDraft} unread={unread} onDraft={draftChanged} onSaved={adoptIndex}
              onConflict={() => refresh(true)} onReturn={() => openPreview("return")} onAccept={() => openPreview("accept")}
              onRefuse={() => setRefusing(true)} professional={professional} outcome={outcome} />
          ) : (
            <div className="rw-read">
              <ExpiryNotice expiresAt={c.expires_at} officer />
              <ReadSheet c={c} sheet={sheet} rows={sheetRows(sheet, null)} anchors={allAnchors(sheetRows(sheet, null), sheet, null)}
                session={null} rulebook={[]} states={new Map()} historical={false} professional={professional}
                questions={<OpenQuestions questions={sheet.questions} loading={false} error={snapshot.questionError} />} onOpen={() => {}} />
              {indexState === "unavailable" && canReview && !outcome && (() => {
                const blocking = (snapshot.gaps ?? []).filter((g) => g.severity === "blocking");
                const blocked = snapshot.gaps === null || Boolean(snapshot.gapError) || blocking.length > 0;
                return (
                  <section className="rw-legacy" aria-label="Decide">
                    {blocking.length > 0 && <p className="rw-hint"><span className="cf-dot is-blocking" aria-hidden="true" />{plural(blocking.length, "required item")} missing</p>}
                    <div className="rw-acts">
                      <button type="button" className="cf-btn is-primary is-lg" disabled={Boolean(busy) || refreshing} onClick={() => { setDecisionError(""); setLegacyReturn(true); }}>
                        <AcIcon name="send" size={16} />Return
                      </button>
                      <button type="button" className="cf-btn is-lg" disabled={blocked || Boolean(busy) || refreshing} onClick={() => openPreview("accept")}>Accept</button>
                      <button type="button" className="cf-btn is-lg is-ghost" disabled={Boolean(busy) || refreshing} onClick={() => setRefusing(true)}>Refuse</button>
                    </div>
                    <p className="rw-scope">Completeness only · not a design approval</p>
                  </section>
                );
              })()}
              {outcome}
              <SubmissionHistory c={c} />
            </div>
          )}
        </div>
      )}

      <input ref={upload} className="pr-file-input" type="file" accept="application/pdf,.pdf" multiple tabIndex={-1} aria-hidden="true"
        onChange={(e) => { const files = [...(e.target.files ?? [])]; e.target.value = ""; if (files.length) void run(files); }} />

      <Modal open={Boolean(preview)} onClose={() => { if (!busy) setPreview(null); }} labelledBy="rw-decision-title" className="ac-return rw-dialog">
        <div className="cf-modal-body">
          <h2 id="rw-decision-title" className="cf-modal-title">{preview?.kind === "return" ? `Return to ${applicant}?` : "Accept as administratively complete?"}</h2>
          <p className="cf-muted">{preview?.kind === "return"
            ? `${plural(preview.count, "item")}. They fix the application and send it again; they can’t reply.`
            : `${applicant} is told the file is complete. Not a variance, not a design approval.`}</p>
          {decisionError && <p className="rw-hint is-error" role="alert"><span className="cf-dot is-blocking" aria-hidden="true" />{decisionError}</p>}
        </div>
        <div className="cf-modal-foot">
          <button type="button" className="cf-btn" disabled={Boolean(busy)} onClick={() => setPreview(null)}>{decisionError ? "Close" : "Not yet"}</button>
          {!decisionError && (
            <button type="button" className="cf-btn is-primary" disabled={Boolean(busy)} onClick={() => void decide()}>
              {busy ? "Saving…" : preview?.kind === "return" ? "Return" : "Accept"}
            </button>
          )}
        </div>
      </Modal>

      <Modal open={legacyReturn} onClose={() => { if (!busy) setLegacyReturn(false); }} labelledBy="rw-legacy-title" className="ac-return rw-dialog">
        <div className="cf-modal-body">
          <h2 id="rw-legacy-title" className="cf-modal-title">Return to {applicant}?</h2>
          <label className="cf-sr" htmlFor="rw-legacy-text">What they need to fix</label>
          <textarea className="cf-uline is-area" id="rw-legacy-text" rows={4} maxLength={4000} value={legacyText} placeholder="What they need to fix"
            onChange={(e) => setLegacyText(e.target.value)} />
          {decisionError && <p className="rw-hint is-error" role="alert"><span className="cf-dot is-blocking" aria-hidden="true" />{decisionError}</p>}
        </div>
        <div className="cf-modal-foot">
          <button type="button" className="cf-btn" disabled={Boolean(busy)} onClick={() => setLegacyReturn(false)}>Not yet</button>
          <button type="button" className="cf-btn is-primary" disabled={Boolean(busy) || legacyText.trim().length < 10}
            title={legacyText.trim().length < 10 ? "At least 10 characters" : undefined} onClick={() => void sendLegacyReturn()}>Return</button>
        </div>
      </Modal>

      <RefuseDialog open={refusing && Boolean(c)} applicant={applicant} onClose={() => setRefusing(false)} onSend={sendRefusal} onRefresh={() => refresh(true)} />
      <ConfirmDialog open={takeover} title="Take over this review?"
        body={<p>{otherClaim?.reviewer_name} started this review. The history keeps both names.</p>}
        cancel="Keep theirs" confirm="Take over" onClose={() => setTakeover(false)} onConfirm={() => void doClaim(true)} />
    </div>
  );
}

const plural = (n: number, one: string) => `${n} ${n === 1 ? one : `${one}s`}`;
const SECTION_NAME: Record<string, string> = { A: "Applicant", B: "Project", C: "Code", process: "Your case", D: "Documents" };

/** The review of one version, in three places: the application, the findings one at a time, the decision. */
function SessionWorkspace({ stage, onStage, messagesAsk, c, snapshot, session, workspace, target, applicant, editable, busy, showDecision, historical, status, messages, onMessages, me, messageDraft, onMessageDraft, unread, onDraft, onSaved, onConflict, onReturn, onAccept, onRefuse, professional, outcome }: {
  stage: Stage; onStage: (s: Stage) => void; messagesAsk: number;
  c: Case; snapshot: Snapshot; session: ReviewSession; workspace: Workspace | null; target: ReviewTarget; applicant: string;
  editable: boolean; busy: boolean; showDecision: boolean; historical: boolean; status: string;
  messages: Message[] | null; onMessages: Dispatch<SetStateAction<Message[] | null>>; me: string | null; messageDraft: string; onMessageDraft: (v: string) => void; unread: number;
  onDraft: (state: DraftReport) => void; onSaved: (index: PackageReviewIndex) => void; onConflict: () => void;
  onReturn: () => void; onAccept: () => void; onRefuse: () => void; professional: ReactNode; outcome: ReactNode;
}) {
  const limits = workspace?.limits ?? READ_ONLY_LIMITS;
  const draft = useRequestDraft({ target, session, limits, enabled: editable, onSaved, onConflict });
  const save = draft.state.save;
  const trouble = save.kind === "error" ? save.message : save.kind !== "saved" ? draft.problem : "";
  const { dispatch } = draft;
  const discard = useCallback(() => dispatch({ type: "reset", session }), [dispatch, session]);
  useEffect(() => { onDraft({ pending: draft.pending, trouble, discard }); }, [draft.pending, trouble, discard, onDraft]);
  useEffect(() => () => onDraft({ pending: false, trouble: "", discard: () => {} }), [onDraft]);

  const sheet = useMemo(() => {
    const current = sheetFromEngine(c, snapshot.information);
    return historical ? { ...current, references: [], documents: [], questions: [] } : current;
  }, [c, snapshot.information, historical]);
  const rows = useMemo(() => sheetRows(sheet, session, historical), [sheet, session, historical]);
  const anchors = useMemo(() => allAnchors(rows, sheet, session), [rows, sheet, session]);
  const changes = useMemo(() => (historical ? new Map() : changedFields(c)), [c, historical]);
  const targets = targetOptions(session, anchors);
  // The server's state, with this browser's unsaved calls on top until the save comes back.
  const states = new Map(session.findings.map((f) => {
    const state = findingState(f, session, workspace);
    return [f.key, { ...state, ...draft.state.content.findings.find((e) => e.key === f.key) }];
  }));

  // One step per finding, in form order, then the completeness rules' gaps no finding covers.
  const steps = useMemo(() => {
    const at = new Map(anchors.map((a, i) => [a.id, i]));
    const own = draft.state.content.items.filter((i) => !i.finding_key).map((i) => i.target?.field);
    const asStep = (f: Finding, title?: string) => {
      const anchor = anchorFor(f, anchors);
      const row = anchors.find((a) => a.id === anchor);
      const reading = rows.find((r) => r.id === anchor)?.reading;
      const change = changes.get(localField(f.field));
      return {
        order: SECTIONS.indexOf(f.section) * 10_000 + (at.get(anchor) ?? 9_999),
        data: {
          finding: f, state: states.get(f.key) ?? { key: f.key, state: "verify" as const, locked: true, reason: null, note: "", by_name: null, at: null },
          item: draft.state.content.items.find((i) => i.finding_key === f.key), own: own.includes(f.field),
          where: `${f.section === "process" ? "Your case" : f.section} · ${row?.label ?? sentence(f.label)}`,
          value: reading?.value ?? null, before: change ? change.before : undefined, title,
        },
      };
    };
    const findings = session.findings.filter((f) => f.key !== "peer_review:signal").map((f) => asStep(f));
    const rules = (workspace?.rulebook ?? []).map((g) => asStep({ key: g.id, section: g.section ?? "A", field: g.field ?? "", label: g.message,
      status: "missing", problem: null, defect_class: null, message: g.message, severity: "blocking", routed_to: "applicant", pointers: [], citations: [] }, g.message));
    return [...findings, ...rules].sort((a, b) => a.order - b.order).map((x) => x.data);
  }, [session, workspace, anchors, rows, changes, draft.state.content, states]); // eslint-disable-line react-hooks/exhaustive-deps

  const [index, setIndex] = useState(() => Math.max(0, steps.findIndex((s) => s.state.state === "verify")));
  const current = steps[Math.min(index, steps.length - 1)];
  const page = useRef<HTMLDivElement>(null);
  useEffect(() => { page.current?.querySelector<HTMLElement>(".rw-step-t")?.focus({ preventScroll: true }); }, [index, stage]);
  const open = (key: string) => { const i = steps.findIndex((s) => s.finding.key === key); if (i >= 0) { setIndex(i); onStage("findings"); } };
  const addOwn = (f: Finding) => {
    const t = targets.find((x) => x.field === f.field) ?? targets.find((x) => x.section === f.section && !x.field)
      ?? { section: f.section, field: f.field, label: sentence(f.label) };
    dispatch({ type: "add", item: officerItem(`Please provide or confirm the ${f.label}.`, t) });
  };

  const sections = SECTIONS.map((id) => ({
    id, name: SECTION_NAME[id],
    steps: steps.map((s, i) => ({ s, i })).filter(({ s }) => s.finding.section === id)
      .map(({ s, i }) => ({ index: i, decided: s.state.state !== "verify", title: s.title ?? s.finding.label })),
  })).filter((s) => s.steps.length);

  const gate = workspaceDecision({ workspace, editable, pending: draft.pending, busy });
  const why = trouble || (!gate.canReturn ? gate.returnReason : gate.acceptReason);

  return (
    <div className="rw-stage" ref={page}>
      {stage === "read" && (
        <div className="rw-read">
          <ExpiryNotice expiresAt={c.expires_at} officer />
          <ReadSheet c={c} sheet={sheet} rows={rows} anchors={anchors} session={session} rulebook={workspace?.rulebook ?? []} states={states}
            historical={historical} professional={historical ? null : professional} onOpen={open}
            questions={historical ? null : <OpenQuestions questions={sheet.questions} loading={snapshot.information === null && !snapshot.questionError} error={snapshot.questionError} />} />
          {!historical && <SubmissionHistory c={c} />}
        </div>
      )}
      {stage === "findings" && current && (
        <div className="cf-deck-page">
          <div className="cf-q-stage">
            <FindingStep step={current} caseId={c.id} files={session.files} limits={limits} editable={editable}
              last={index >= steps.length - 1} canBack={index > 0}
              onCall={(edit) => dispatch({ type: "finding", edit })} onText={(key, text) => dispatch({ type: "item", key, patch: { text } })}
              onAddOwn={addOwn} onNext={() => (index >= steps.length - 1 ? onStage("decide") : setIndex(index + 1))} onBack={() => setIndex(Math.max(0, index - 1))} />
          </div>
          <FindingFooter sections={sections} at={index} onJump={setIndex} />
        </div>
      )}
      {(stage === "decide" || (stage === "findings" && !current)) && (
        <div className="cf-deck-page">
          <div className="cf-q-stage">
            <DecideStage session={session} workspace={workspace} applicant={applicant} status={status} decidedAt={c.decision?.at ?? null}
              draft={editable ? draft : null} editable={editable} targets={targets} questions={sheet.questions}
              choices={showDecision ? { canReturn: gate.canReturn, canAccept: gate.canAccept, canRefuse: gate.canRefuse, why, busy, onReturn, onAccept, onRefuse } : null}
              outcome={outcome} unread={unread} messagesAsk={messagesAsk}
              messages={<Messages caseId={c.id} me={me} messages={messages} onChange={onMessages} canWrite={showDecision} hideTitle draft={messageDraft} onDraft={onMessageDraft} reading />} />
          </div>
        </div>
      )}
    </div>
  );
}
