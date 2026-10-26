/** One application, its inline findings, and one saved request-and-decision rail. */
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type Dispatch, type ReactNode, type SetStateAction } from "react";
import { AccountsError, claimConflict, review, type Claim, type Message } from "../../api/accounts";
import { EngineError } from "../../api/client";
import { packageReview, type ReviewTarget } from "../../api/packageReview";
import type { Case, PackageReviewIndex, ProfessionalRequirementRequest, ReviewSession, Workspace } from "../../api/types.gen";
import { accountSession, useAccount } from "../account";
import { AcIcon, Avatar, PageHead } from "../auth/bits";
import { ExpiryNotice } from "../ExpiryNotice";
import { getNotificationsState, subscribeNotifications } from "../notifications/notifications";
import { MoreMenu } from "../shell/MoreMenu";
import { ConfirmDialog, Modal } from "../ui";
import { CloseOutDue, CloseOutPanel } from "./CloseOutPanel";
import { refusalDecision } from "./packageView";
import { ProfessionalRequirement } from "./ProfessionalRequirement";
import { sentLabel, sinceLabel } from "./queue";
import { RefuseDialog } from "./RefuseDialog";
import { RequestRail } from "./RequestRail";
import { loadQueue, patchRow, setBlocking, useQueue } from "./reviewData";
import { readReviewSnapshot } from "./reviewSnapshot";
import { sheetFromEngine } from "./sheet";
import { SubmissionHistory } from "./SubmissionHistory";
import { mergeThreadMessages } from "./threadMessages";
import { useRequestDraft } from "./useRequestDraft";
import { allAnchors, findingState, sheetRows, targetOptions, type FindingFilter } from "./workspaceView";
import { WorkspaceSheet } from "./WorkspaceSheet";
import "./review.css";

type Snapshot = Awaited<ReturnType<typeof readReviewSnapshot>>;
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
  const [tab, setTab] = useState<"request" | "messages">("request");
  const [filter, setFilter] = useState<FindingFilter>("all");
  const page = useRef<HTMLDivElement>(null);
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
      setShown(current => !keepShown || !current || (current.version === previous?.latest?.version && next.latest && next.latest.version > current.version) ? next.latest : current);
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
    setMessageDraft(""); setTab("request"); setFilter("all"); setDraftPending(false); draftDirty.current = false; actionPending.current = false;
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
  const editable = canReview && onLatest && currentReview && !shown?.information_request.sent_at && indexState === "ready" && !running && !busy && !refreshing && !refreshError;
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
      if (live(session) && sequence === indexReads.current) { setShown(next); setFilter("all"); }
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
      if (e instanceof EngineError && (e.status === 409 || e.status === 404)) { await reload(); await loadIndex(true); }
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

  const pendingChanged = useCallback((pending: boolean) => { draftDirty.current = pending; setDraftPending(pending); }, []);
  const adoptIndex = (next: PackageReviewIndex) => { setBlocking(caseId, next.workspace?.current ? next.workspace.tally.required : null); setIndex(next); if (next.latest) setShown(next.latest); setIndexState("ready"); };
  const readOnlyReason = indexState === "loading" || indexState === "failed" ? "The review list is not current · decisions wait" : !onLatest ? latest && shown && shown.version < latest.version ? "Earlier review · read-only" : "The review list is not current · decisions wait" : status === "returned" ? "Sent request · read-only until the applicant fixes and resends"
    : status === "accepted" ? "Administratively complete · technical review next" : status === "refused" ? "Refused · the record is closed"
    : otherClaim ? `${otherClaim.reviewer_name} is reviewing this` : !currentReview ? "The application changed · review again" : !canReview ? "Resume this review to edit" : "";
  const professional = c && <ProfessionalRequirement c={c} editable={canReview && !draftPending && (!shown || onLatest)} busy={Boolean(busy) || running || refreshing} unresolved={professionalPending} onResolve={resolveProfessional} onEditingChange={setProfessionalEditing} />;
  const outcome = closeOut && <div className="rw-rail-section"><CloseOutPanel c={closeOut} bare><CloseOutDue c={closeOut} inline canMark={Boolean(me && (c?.decision?.by_id === me || claim?.reviewer_id === me))} onChange={co => setIndex(previous => previous ? { ...previous, close_out: co } : previous)} /></CloseOutPanel></div>;
  const menu = [
    ...(canReview ? [
      { label: running ? "Reviewing…" : "Run the review again", onClick: () => void run(), disabled: Boolean(busy) || running || draftPending },
      { label: "Review uploaded PDFs", onClick: () => upload.current?.click(), disabled: Boolean(busy) || running || draftPending },
      { label: busy === "release" ? "Releasing…" : "Stop reviewing", onClick: () => void release(), disabled: Boolean(busy) || running || draftPending, separator: true },
    ] : []),
  ];
  const versions = index?.sessions ?? [];
  const sheet = c ? sheetFromEngine(c, snapshot?.information) : null;
  const fallbackRows = sheet ? sheetRows(sheet, null) : [];
  const fallbackAnchors = sheet ? allAnchors(fallbackRows, sheet, null) : [];

  return <div className="ac-page rw-page" ref={page}>
    <PageHead title={<><a className="ac-crumb" href="#/review">Queue</a><span className="ac-crumb-sep" aria-hidden="true">/</span><span className="ac-crumb-leaf" title={title}>{title}</span></>} phoneTools={phoneTools}
      right={<>
        {shown && <details className="rw-version-menu"><summary>v{shown.version}<span className="cf-sr"> · review version on screen</span><AcIcon name="chev" size={12} /></summary>
          <div>{versions.map(version => <button type="button" key={version.version} disabled={draftPending || running || Boolean(busy)} aria-pressed={version.version === shown.version} onClick={event => { void pickVersion(version.version); const details = event.currentTarget.closest("details"); if (details) details.open = false; }}>Version {version.version} · {version.required} required</button>)}</div>
        </details>}
        <button type="button" className="cf-btn is-xs is-ghost" title="Refresh application" aria-label="Refresh application" disabled={Boolean(busy) || running || draftPending} onClick={() => refresh()}><AcIcon name="history" size={15} /></button>
        <button type="button" className="cf-btn is-xs is-ghost" title="Messages" aria-label={unread ? `Messages, ${unread} unread` : "Messages"} onClick={() => { setTab("messages"); page.current?.querySelector<HTMLElement>("[data-tab=messages]")?.focus({ preventScroll: true }); page.current?.querySelector(".rw-correspondence")?.scrollIntoView({ block: "start" }); }}><AcIcon name="chat" size={15} />{unread > 0 && <span className="rw-badge">{unread}</span>}</button>
        {menu.length > 0 && <MoreMenu items={menu} />}
      </>} />
    {loadError ? <div className="ac-page-body is-narrow"><p role="alert">{loadError}</p><a className="cf-btn is-sm" href="#/review">Back to the queue</a><button type="button" className="cf-btn is-sm" onClick={() => refresh(true)}>Try again</button></div>
      : !c || !snapshot || !sheet ? <p className="ac-empty" role="status">Loading the application…</p> : <div className="rw-workspace">
        <div className="rw-banners">
          {otherClaim && <div className="rw-banner"><Avatar name={otherClaim.reviewer_name} size="sm" /><span>{otherClaim.reviewer_name} is reviewing this · {sinceLabel(otherClaim.claimed_at)}</span><button type="button" className="cf-btn is-xs" disabled={Boolean(busy)} onClick={() => setTakeover(true)}>Take over</button></div>}
          {unclaimed && <div className="rw-banner" role="status">{busy === "claim" || !actionError ? "Opening the review…" : <>Not picked up yet<button type="button" className="cf-btn is-sm" onClick={() => void doClaim()}>Pick up</button></>}</div>}
          {resumable && <div className="rw-banner"><span>Resubmitted · waiting for you to resume</span><button type="button" className="cf-btn is-sm" disabled={Boolean(busy)} onClick={() => void doClaim()}>Resume review</button></div>}
          {status === "returned" && <div className="rw-banner"><span className="cf-dot is-warning" aria-hidden="true" /><span>Returned{c.decision ? ` ${sentLabel(c.decision.at)}` : ""} · read-only until the applicant fixes and resends</span></div>}
          {status === "accepted" && <div className="rw-banner"><span className="cf-dot is-done" aria-hidden="true" />Administratively complete · technical review next</div>}
          {status === "refused" && <div className="rw-banner"><span className="cf-dot is-blocking" aria-hidden="true" />Refused · record to keep on file</div>}
          {actionError && <p className="rw-banner" role="alert">{actionError}</p>}
          {refreshError && <p className="rw-banner" role="alert">{refreshError}<button type="button" className="cf-btn is-xs" onClick={() => refresh(true)}>Try again</button></p>}
          {running && <p className="rw-banner" role="status">Reviewing the saved application…</p>}
          {runError && <p className="rw-banner" role="alert">{runError}<button type="button" className="cf-btn is-xs" disabled={running || Boolean(busy) || draftPending} onClick={() => void run()}>Try again</button></p>}
          {indexState === "failed" && <p className="rw-banner" role="alert">The review didn’t load · decisions wait<button type="button" className="cf-btn is-xs" onClick={() => { setIndexState("loading"); void loadIndex(true); }}>Try again</button></p>}
          {indexState === "unavailable" && <p className="rw-banner">Package review unavailable on this server · completeness checklist only</p>}
        </div>
        {shown && indexState !== "unavailable" ? <SessionWorkspace key={`${shown.package_id}:${shown.version}:${me}`} c={c} snapshot={snapshot} session={shown} workspace={workspace} target={target} editable={editable} busy={Boolean(busy) || running || refreshing}
          showDecision={canReview && !(shown && latest && shown.version < latest.version)} historical={Boolean(shown && latest && shown.version < latest.version)} required={versions.find(v => v.version === shown.version)?.required} filter={filter} onFilter={setFilter} tab={tab} onTab={setTab} messages={messages} onMessages={setMessages} me={me} messageDraft={messageDraft} onMessageDraft={setMessageDraft}
          onPending={pendingChanged} onSaved={adoptIndex} onConflict={() => refresh(true)} onReturn={() => openPreview("return")} onAccept={() => openPreview("accept")} onRefuse={() => setRefusing(true)} professional={professional} outcome={outcome} readOnlyReason={readOnlyReason} refreshMessages={() => refresh(true)} />
          : <div className="rw">
            <div className="rw-document"><ExpiryNotice expiresAt={c.expires_at} officer /><WorkspaceSheet c={c} sheet={sheet} rows={fallbackRows} anchors={fallbackAnchors} information={snapshot.information} questionError={snapshot.questionError}
              session={null} workspace={null} states={new Map()} items={[]} limits={READ_ONLY_LIMITS} filter="all" editable={false} historical={false} professional={professional} onDisposition={() => {}} onText={() => {}} />
              {indexState === "unavailable" && <section className="rw-canonical-gaps" aria-label="Completeness checklist"><h3>Completeness checklist</h3>{snapshot.gapError ? <p>{snapshot.gapError}</p> : snapshot.gaps === null ? <p>Checklist unavailable</p> : snapshot.gaps.filter(g => g.severity !== "info").map(g => <p key={g.id}><span className={`cf-dot is-${g.severity}`} aria-hidden="true" />{g.message}</p>)}</section>}
            </div>
            <RequestRail caseId={caseId} session={null} workspace={null} filter="all" onFilter={setFilter} tab={tab} onTab={setTab} draft={null} editable={false} busy={Boolean(busy)} targets={[]} questions={sheet.questions} messages={messages} onMessages={setMessages} me={me} messageDraft={messageDraft} onMessageDraft={setMessageDraft}
              onReturn={() => {}} onAccept={() => {}} onRefuse={() => {}} readOnlyReason={indexState === "loading" ? "Loading the review…" : runError ? "Review failed · try again" : "Review not available"} refreshMessages={() => refresh(true)}
              outcome={outcome || (canReview ? <div className="rw-decision"><p className="rw-pin">Application version {c.version}</p><p className="rw-scope">Completeness only · not a design approval</p><div className="rw-decision-actions">
                <button type="button" className="cf-btn is-sm is-primary" disabled={indexState !== "unavailable" || Boolean(busy) || refreshing} onClick={() => { setDecisionError(""); setLegacyReturn(true); }}>{indexState === "unavailable" ? "Return with a message" : "Return with 0 items"}</button>
                <button type="button" className="cf-btn is-sm" disabled={indexState !== "unavailable" || Boolean(busy) || refreshing || snapshot.gaps === null || Boolean(snapshot.gapError) || snapshot.gaps.some(g => g.severity === "blocking")} onClick={() => openPreview("accept")}>Accept</button>
                <button type="button" className="cf-btn is-sm" disabled={Boolean(busy) || refreshing} onClick={() => setRefusing(true)}>Refuse</button>
              </div>{indexState !== "unavailable" ? <p className="rw-hint">Acceptance and requests wait for the saved review.</p> : snapshot.gaps?.some(g => g.severity === "blocking") ? <p className="rw-hint">Required checklist items remain.</p> : snapshot.gapError ? <p className="rw-hint">{snapshot.gapError}</p> : null}</div> : null)} />
          </div>}
      </div>}
    <input ref={upload} className="pr-file-input" type="file" accept="application/pdf,.pdf" multiple tabIndex={-1} aria-hidden="true" onChange={event => { const files = [...(event.target.files ?? [])]; event.target.value = ""; if (files.length) void run(files); }} />
    <Modal open={Boolean(preview)} onClose={() => { if (!busy) setPreview(null); }} labelledBy="rw-decision-title" className="ac-return">
      <div className="cf-modal-body"><h2 id="rw-decision-title" className="cf-modal-title">{preview?.kind === "return" ? `Return to ${applicant}?` : "Accept as administratively complete?"}</h2>
        {preview?.kind === "return" ? <><p className="rw-meta">They fix the application and send it again. They can’t reply.</p><pre className="rw-letter" aria-label="Request to send">{preview.text}</pre><p className="rw-meta">Version {preview.reviewVersion} · {preview.count} {preview.count === 1 ? "item" : "items"}</p></>
          : <p>{applicant} is told the file is complete. This is not a variance and not a design approval; technical review comes next.</p>}
        {decisionError && <p className="rw-hint" role="alert">{decisionError} Close this dialog and review the refreshed file.</p>}
      </div>
      <div className="cf-modal-foot"><button type="button" className="cf-btn" disabled={Boolean(busy)} onClick={() => setPreview(null)}>Not yet</button><button type="button" className="cf-btn is-primary" disabled={Boolean(busy) || Boolean(decisionError)} onClick={() => void decide()}>{busy ? "Saving…" : preview?.kind === "return" ? "Return" : "Accept as complete"}</button></div>
    </Modal>
    <Modal open={legacyReturn} onClose={() => { if (!busy) setLegacyReturn(false); }} labelledBy="rw-legacy-title" className="ac-return">
      <div className="cf-modal-body"><h2 id="rw-legacy-title" className="cf-modal-title">Return with a message</h2><p className="rw-meta">They fix the application and send it again. They can’t reply.</p><label className="rw-label" htmlFor="rw-legacy-text">Your message</label><textarea className="ac-ta" id="rw-legacy-text" rows={6} maxLength={4000} value={legacyText} onChange={event => setLegacyText(event.target.value)} />
        {legacyText.trim().length < 10 && <p className="rw-hint">Write at least 10 characters.</p>}{decisionError && <p className="rw-hint" role="alert">{decisionError}</p>}
      </div><div className="cf-modal-foot"><button type="button" className="cf-btn" disabled={Boolean(busy)} onClick={() => setLegacyReturn(false)}>Cancel</button><button type="button" className="cf-btn is-primary" disabled={Boolean(busy) || legacyText.trim().length < 10} onClick={() => void sendLegacyReturn()}>Return</button></div>
    </Modal>
    <RefuseDialog open={refusing && Boolean(c)} applicant={applicant} onClose={() => setRefusing(false)} onSend={sendRefusal} onRefresh={() => refresh(true)} />
    <ConfirmDialog open={takeover} title="Take over this review?" body={<p>{otherClaim?.reviewer_name} started this review. Taking over records both names in the history.</p>} cancel="Keep theirs" confirm="Take over" onClose={() => setTakeover(false)} onConfirm={() => void doClaim(true)} />
  </div>;
}

function SessionWorkspace({ c, snapshot, session, workspace, target, editable, busy, showDecision, historical, required, filter, onFilter, tab, onTab, messages, onMessages, me, messageDraft, onMessageDraft, onPending, onSaved, onConflict, onReturn, onAccept, onRefuse, professional, outcome, readOnlyReason, refreshMessages }: {
  c: Case; snapshot: Snapshot; session: ReviewSession; workspace: Workspace | null; target: ReviewTarget; editable: boolean; busy: boolean; showDecision: boolean; historical: boolean; required?: number;
  filter: FindingFilter; onFilter: (filter: FindingFilter) => void; tab: "request" | "messages"; onTab: (tab: "request" | "messages") => void;
  messages: Message[] | null; onMessages: Dispatch<SetStateAction<Message[] | null>>; me: string | null; messageDraft: string; onMessageDraft: (value: string) => void;
  onPending: (pending: boolean) => void; onSaved: (index: PackageReviewIndex) => void; onConflict: () => void; onReturn: () => void; onAccept: () => void; onRefuse: () => void;
  professional: ReactNode; outcome: ReactNode; readOnlyReason: string; refreshMessages: () => void;
}) {
  const draft = useRequestDraft({ target, session, limits: workspace?.limits ?? READ_ONLY_LIMITS, enabled: editable, onSaved, onConflict });
  const [composing, setComposing] = useState(false);
  useEffect(() => { onPending(draft.pending || composing); }, [draft.pending, composing, onPending]);
  useEffect(() => () => onPending(false), [onPending]);
  const root = useRef<HTMLDivElement>(null);
  const sheet = useMemo(() => {
    const current = sheetFromEngine(c, snapshot.information);
    return historical ? { ...current, references: [], documents: [], questions: [] } : current;
  }, [c, snapshot.information, historical]);
  const rows = useMemo(() => sheetRows(sheet, session, historical), [sheet, session, historical]);
  const anchors = useMemo(() => allAnchors(rows, sheet, session), [rows, sheet, session]);
  const states = new Map(session.findings.map(finding => {
    const state = findingState(finding, session, workspace);
    return [finding.key, { ...state, ...draft.state.content.findings.find(edit => edit.key === finding.key) }];
  }));
  useEffect(() => {
    const keydown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey || !(event.target instanceof Element)) return;
      if (event.target.closest("input, textarea, select, [contenteditable=true], dialog[open], .rw-target-picker, .rw-version-menu")) return;
      const key = event.key.toLowerCase();
      if (!["j", "k", "a", "d"].includes(key)) return;
      const cards = [...(root.current?.querySelectorAll<HTMLElement>("[data-finding]") ?? [])];
      const selected = event.target.closest<HTMLElement>("[data-finding]");
      const index = cards.findIndex(card => card === selected);
      if (key === "j" || key === "k") {
        const next = cards[Math.max(0, Math.min(cards.length - 1, index + (key === "j" ? 1 : -1)))];
        if (next) { event.preventDefault(); next.focus({ preventScroll: true }); next.scrollIntoView({ block: "center" }); }
      } else if (editable && selected) {
        const button = selected.querySelector<HTMLButtonElement>(`[data-action=${key === "a" ? "ask" : "dismiss"}]`);
        if (button && !button.disabled) { event.preventDefault(); button.click(); }
      }
    };
    document.addEventListener("keydown", keydown);
    return () => document.removeEventListener("keydown", keydown);
  }, [editable]);
  return <div className="rw" ref={root}>
    <div className="rw-document"><ExpiryNotice expiresAt={c.expires_at} officer />
      <WorkspaceSheet c={c} sheet={sheet} rows={rows} anchors={anchors} information={snapshot.information} questionError={snapshot.questionError} session={session} workspace={workspace} states={states} items={draft.state.content.items} limits={workspace?.limits ?? READ_ONLY_LIMITS}
        filter={filter} editable={editable} historical={historical} professional={historical ? null : professional} onDisposition={edit => draft.dispatch({ type: "finding", edit })} onText={(key, text) => draft.dispatch({ type: "item", key, patch: { text } })} />
      {!historical && <SubmissionHistory c={c} />}
    </div>
    <RequestRail caseId={c.id} session={session} workspace={workspace} required={required} showDecision={showDecision} filter={filter} onFilter={onFilter} tab={tab} onTab={onTab} draft={draft} editable={editable} busy={busy} targets={targetOptions(session, anchors)} questions={sheet.questions}
      messages={messages} onMessages={onMessages} me={me} messageDraft={messageDraft} onMessageDraft={onMessageDraft} onReturn={onReturn} onAccept={onAccept} onRefuse={onRefuse} outcome={outcome} readOnlyReason={readOnlyReason} refreshMessages={refreshMessages} composing={composing} onComposing={setComposing} />
  </div>;
}
