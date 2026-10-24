/**
 * #/review/<caseId>: one path, one thing on screen at a time. Opening an application nobody has
 * picked up picks it up (as "Pick up" in the queue does), so there is no second button to start the
 * review; the review then runs by itself. Its steps (Request, Missing, Checks, Decide) sit in the
 * header as the shell's stage tabs. The "Pick up" bar is only the fallback when that claim failed.
 * A resubmitted application whose reservation you kept waits for an explicit "Resume review".
 * The application and the messages open in drawers from the header; running the review again and
 * releasing the claim ("Stop reviewing", back to the queue) live in ⋯.
 *
 * The case, its gaps, the saved officer questions and the thread are read as one snapshot for the
 * current application and sign-in; a late read for another one is dropped and aborted. Every
 * decision pins the version on screen (`expected_version`), so a newer save is a conflict to refresh.
 */
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { AccountsError, claimConflict, review, type Claim, type DecisionItemInput, type Message } from "../../api/accounts";
import { EngineError, type EngineGap, type InformationRequest } from "../../api/client";
import { packageReview, type ReviewTarget } from "../../api/packageReview";
import type { Case as EngineCase, PackageReviewIndex, ProfessionalRequirementRequest, ReviewSession } from "../../api/types.gen";
import { CODE_EDITION } from "../../config";
import { EvidenceFileLink } from "../../EvidenceFileLink";
import { RetainedSourceFiles } from "../../RetainedSourceFiles";
import { accountSession, useAccount } from "../account";
import { AcIcon, Avatar, PageHead } from "../auth/bits";
import { ExpiryNotice } from "../ExpiryNotice";
import { getNotificationsState, subscribeNotifications } from "../notifications/notifications";
import { CIcon, ConfirmDialog, Modal } from "../ui";
import { MoreMenu } from "../shell/MoreMenu";
import { Messages } from "./Messages";
import { CloseOutDue, CloseOutPanel } from "./CloseOutPanel";
import { InfoRequest } from "./InfoRequest";
import { OpenQuestions } from "./OpenQuestions";
import { PackageReview, StepTitle, type FinalStep } from "./PackageReview";
import { blockingGaps, refusalDecision } from "./packageView";
import { ProfessionalRequirement } from "./ProfessionalRequirement";
import { applicantLine, decisionGate, sentLabel, sentPhrase, sinceLabel, withPackage, type PackageState } from "./queue";
import { RefuseDialog } from "./RefuseDialog";
import { ReturnDialog } from "./ReturnDialog";
import { StatusPill } from "./ReviewQueue";
import { loadQueue, patchRow, setBlocking, useQueue } from "./reviewData";
import { readReviewSnapshot } from "./reviewSnapshot";
import { sheetFromEngine, type SheetRow } from "./sheet";
import { SubmissionHistory } from "./SubmissionHistory";
import { mergeThreadMessages } from "./threadMessages";

function Value({ r }: { r: SheetRow }) {
  if (!r.value) {
    return r.required
      ? <span className="cf-sheet-missing"><span className="cf-sheet-dot" aria-hidden="true" />— <em>missing</em></span>
      : <span className="cf-sheet-none">—</span>;
  }
  return <span>{r.value}{r.unconfirmed && <span className="cf-sheet-flag"> · not confirmed by the applicant</span>}</span>;
}

function Kv({ rows, wide }: { rows: SheetRow[]; wide?: boolean }) {
  return (
    <div className={`cf-sheet-kv${wide ? " is-wide" : ""}`}>
      {rows.map((r) => [<span key={`${r.label}-k`}>{r.label}</span>, <Value key={`${r.label}-v`} r={r} />])}
    </div>
  );
}

function Sheet({ c, information, questionError }: { c: EngineCase; information: InformationRequest | null; questionError: string }) {
  const s = useMemo(() => sheetFromEngine(c, information), [c, information]);
  return (
    <article className="cf-sheet ac-sheet" aria-label="Submitted application">
      <h2>Safety Codes Variance — Part 1</h2>
      <div className="cf-sheet-sub">{CODE_EDITION}{c.submitted_at ? ` · Sent ${sentPhrase(c.submitted_at)}` : ""}</div>
      <h4>A · Applicant</h4>
      <Kv rows={s.applicant} />
      <h4>B · Project</h4>
      <Kv rows={s.project} />
      <p className="cf-sheet-label">Proposed alternative</p>
      <p className="cf-sheet-p"><Value r={s.alternative} /></p>
      <h4>C · Code references</h4>
      {s.references.length ? (
        s.references.map((r) => (
          <p key={r.provision} className="cf-sheet-p"><span className="cf-sheet-ref">{r.provision}</span> {r.codes}</p>
        ))
      ) : (
        <p className="cf-sheet-p"><Value r={{ label: "", value: null, required: true }} /> No code reference confirmed.</p>
      )}
      <h4>Alternative path · written by the applicant</h4>
      <Kv rows={s.process} wide />
      <h4>D · Supporting information</h4>
      <Kv rows={s.supporting} />
      {s.documents.map((doc) => <p className="cf-sheet-p" key={doc.id}>
        {doc.title}<br />
        {[doc.type, doc.author, doc.date].filter(Boolean).join(" · ")}
        <br />{doc.fileId
          ? <><EvidenceFileLink caseId={c.id} fileId={doc.fileId} name={doc.fileName || doc.title} /> · Source: {doc.fileName}</>
          : <span className="cf-sheet-flag">Listed only · no file attached</span>}
      </p>)}
      <RetainedSourceFiles caseId={c.id} />
      <p className="cf-sheet-note">Professional evidence is provided by the applicant’s registered professional. Batatis does not write it.</p>
      <OpenQuestions questions={s.questions} loading={information === null && !questionError} error={questionError} />
    </article>
  );
}

function Completeness({ gaps, error }: { gaps: EngineGap[] | null; error: string }) {
  const shown = (gaps ?? []).filter((g) => g.severity !== "info");
  const required = gaps ? gaps.filter((g) => g.severity === "blocking").length : 0;
  return (
    <details className="ac-side-sec pr-checklist">
      <summary>Applicant’s own checklist{gaps ? ` · ${required ? `${required} required missing` : "nothing required missing"}` : ""}</summary>
      {error ? (
        <p className="ac-faint ac-small">{error}</p>
      ) : gaps == null ? (
        <p className="ac-faint ac-small">Checking…</p>
      ) : (
        <ul className="ac-lrows">
          {!shown.some((g) => g.severity === "blocking") && (
            <li className="ac-lrow"><span className="cf-dot is-done" aria-hidden="true" />No required items missing</li>
          )}
          {shown.map((g) => (
            <li key={g.id} className="ac-lrow">
              <span className={`cf-dot is-${g.severity === "blocking" ? "blocking" : "warning"}`} aria-hidden="true" />
              <span>{g.message}<span className="cf-sr">{g.severity === "blocking" ? " (required)" : " (check)"}</span></span>
            </li>
          ))}
        </ul>
      )}
      <p className="ac-faint ac-small">What Batatis checked before the applicant sent it. Your review is the package review.</p>
    </details>
  );
}

/** A right-side drawer (bottom sheet on phones) with a title and a close button. */
function Drawer({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  const id = `rv-drawer-${title.toLowerCase().replace(/\W+/g, "-")}`;
  // Mount on first open, then stay mounted: closing slides out with its content. Messages are only
  // marked read while their drawer is open (see `reading`).
  const [seen, setSeen] = useState(open);
  if (open && !seen) setSeen(true);
  return (
    <Modal open={open} onClose={onClose} labelledBy={id} className="cf-drawer rv-drawer">
      <div className="cf-drawer-scroll">
        <div className="cf-drawer-head">
          <h2 id={id} className="rv-drawer-title">{title}</h2>
          <button type="button" className="cf-icon-btn is-plain" aria-label="Close" onClick={onClose}><CIcon name="close" /></button>
        </div>
        {seen && children}
      </div>
    </Modal>
  );
}

/** The path, or the information request opened from the decision. */
type View = "flow" | "request";

export function ReviewDetail({ caseId, phoneTools }: { caseId: string; phoneTools?: ReactNode }) {
  const { user } = useAccount();
  const me = user?.id ?? null;
  const q = useQueue();
  const target: ReviewTarget = useMemo(() => ({ kind: "case", id: caseId }), [caseId]);
  const [c, setCase] = useState<EngineCase | null>(null);
  const [loadError, setLoadError] = useState("");
  const [gaps, setGaps] = useState<EngineGap[] | null>(null);
  const [gapError, setGapError] = useState("");
  const [messages, setMessages] = useState<Message[] | null>(null);
  const [information, setInformation] = useState<InformationRequest | null>(null);
  const [questionError, setQuestionError] = useState("");
  const [busy, setBusy] = useState<"" | "claim" | "release" | "accept" | "professional">("");
  const [note, setNote] = useState("");
  const [actionError, setActionError] = useState("");
  const [conflict, setConflict] = useState<Claim | null>(null);
  const [confirm, setConfirm] = useState<"" | "accept" | "takeover">("");
  const [returning, setReturning] = useState(false);
  const [refusing, setRefusing] = useState(false);
  const [professionalEditing, setProfessionalEditing] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState("");
  // Package review: the index (versions, latest, close-out) and the version on screen.
  const [index, setIndex] = useState<PackageReviewIndex | null>(null);
  const [indexState, setIndexState] = useState<"loading" | "ready" | "unavailable" | "failed">("loading");
  const [shown, setShown] = useState<ReviewSession | null>(null);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState("");
  const [view, setView] = useState<View>("flow");
  const [drawer, setDrawer] = useState<"" | "application" | "messages">("");
  const [msgDraft, setMsgDraft] = useState("");
  const work = useRef<HTMLDivElement>(null);
  const upload = useRef<HTMLInputElement>(null);
  // The header slot the step tabs render into (state, so the review re-renders once it exists).
  const [stepSlot, setStepSlot] = useState<HTMLDivElement | null>(null);
  const autoRan = useRef("");
  // One automatic pick-up per application opened; a failure shows the bar with its error instead.
  const autoClaimed = useRef("");

  // A background refresh never swaps the record under an open decision, dialog or determination;
  // it waits and runs once they close.
  const pendingRefresh = useRef(false);
  const protectedInteraction = useRef(false);
  useLayoutEffect(() => { protectedInteraction.current = Boolean(busy || returning || refusing || confirm || professionalEditing); });
  // Reads belong to this application and this sign-in: a replaced one aborts and ignores them.
  const request = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const scope = useRef({ caseId, session: accountSession() });
  useLayoutEffect(() => {
    scope.current = { caseId, session: accountSession() };
    return () => { request.current++; controller.current?.abort(); pendingRefresh.current = false; };
  }, [caseId, user]);

  const row = q.rows.find((r) => r.id === caseId) ?? null;

  const reload = useCallback(async (mode: "replace" | "background" | "action" = "action"): Promise<EngineCase | null> => {
    const session = accountSession();
    if (scope.current.caseId !== caseId || scope.current.session !== session) return null;
    const read = ++request.current;
    controller.current?.abort();
    const ctl = new AbortController();
    controller.current = ctl;
    const current = () => request.current === read && session === accountSession()
      && scope.current.caseId === caseId && scope.current.session === session;
    setRefreshing(true);
    setRefreshError("");
    if (mode === "replace") {
      setCase(null);
      setGaps(null);
      setMessages(null);
      setInformation(null);
      setConflict(null);
      setConfirm("");
      setReturning(false);
      setRefusing(false);
    }
    setLoadError("");
    setGapError("");
    setQuestionError("");
    try {
      const snapshot = await readReviewSnapshot(caseId, ctl.signal);
      if (!current()) return null;
      if (mode === "background" && protectedInteraction.current) { pendingRefresh.current = true; return null; }
      setCase(snapshot.c);
      setGaps(snapshot.gaps);
      setInformation(snapshot.information);
      setMessages((previous) => (current() ? mergeThreadMessages(previous, snapshot.messages) : previous));
      setGapError(snapshot.gapError);
      setQuestionError(snapshot.questionError);
      if (snapshot.gaps) setBlocking(caseId, snapshot.gaps.filter((g) => g.severity === "blocking").length);
      return snapshot.c;
    } catch (e) {
      if (!current()) return null;
      // Missing and unauthorized cases intentionally share a privacy-friendly 404.
      if (mode === "replace" || (e instanceof EngineError && e.status === 404)) {
        setCase(null);
        setNote("");
        setLoadError(e instanceof EngineError && e.status === 404 ? "This application isn’t available to you. It may have been withdrawn or sent to another authority." : "The application didn’t load.");
      } else {
        setRefreshError(e instanceof EngineError ? e.detail : "The updated application didn’t load. Refresh to try again.");
      }
      return null;
    } finally {
      if (controller.current === ctl) controller.current = null;
      if (current()) setRefreshing(false);
    }
  }, [caseId, user]);

  const loadIndex = useCallback(async (keepShown = false) => {
    const session = accountSession();
    const live = () => scope.current.caseId === target.id && scope.current.session === session && session === accountSession();
    try {
      const ix = await packageReview.index(target);
      if (!live()) return null;
      setIndex(ix);
      setIndexState("ready");
      if (!keepShown) setShown(ix.latest);
      return ix;
    } catch (e) {
      if (!live()) return null;
      // Only a missing route means "not on this server"; anything else (network, 5xx) is a failure
      // with a retry, and acceptance waits for it.
      setIndexState(e instanceof EngineError && (e.status === 404 || e.status === 405) ? "unavailable" : "failed");
      return null;
    }
  }, [target]);

  useEffect(() => {
    setNote("");
    setConflict(null);
    setBusy("");
    setActionError("");
    setProfessionalEditing(false);
    setIndex(null);
    setShown(null);
    setIndexState("loading");
    setRunError("");
    setView("flow");
    setDrawer("");
    setMsgDraft("");
    void reload("replace");
    void loadIndex();
    if (!q.rows.length) void loadQueue();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, reload]);

  const refreshDetail = useCallback(() => {
    if (protectedInteraction.current || controller.current) { pendingRefresh.current = true; return; }
    pendingRefresh.current = false;
    void reload("background");
  }, [reload]);

  // A refresh that waited for a dialog or action runs once nothing is open.
  useEffect(() => {
    if (refreshing || busy || returning || refusing || confirm || professionalEditing || !pendingRefresh.current) return;
    refreshDetail();
  }, [refreshing, busy, returning, refusing, confirm, professionalEditing, refreshDetail]);

  // A notification about this application (a resend, a notice) refreshes the open review in place.
  useEffect(() => {
    if (user?.role !== "reviewer" || !user.authority) return;
    const session = accountSession();
    const key = (n: ReturnType<typeof getNotificationsState>["items"][number]) => JSON.stringify([n.id, n.created_at, n.status]);
    let seen = new Set(getNotificationsState().items.map(key));
    const stop = subscribeNotifications(() => {
      const notifications = getNotificationsState();
      if (session !== accountSession() || notifications.phase !== "ready") return;
      const changed = notifications.items.some((n) => n.case_id === caseId && !seen.has(key(n)));
      seen = new Set(notifications.items.map(key));
      if (changed) refreshDetail();
    });
    // The same hash does not fire hashchange. An already-seen bell row still asks for a fresh read.
    const onPick = (event: MouseEvent) => {
      if (session !== accountSession() || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const link = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>("a.ac-note") : null;
      if (link?.getAttribute("href") === `#/review/${encodeURIComponent(caseId)}`) refreshDetail();
    };
    document.addEventListener("click", onPick);
    return () => { stop(); document.removeEventListener("click", onPick); };
  }, [caseId, user, refreshDetail]);

  // Unknown (loading, refreshing or failed) is not "no gaps": acceptance waits for a real completeness result.
  const blocking = refreshing || refreshError || gaps === null ? null : gaps.filter((g) => g.severity === "blocking").length;
  const status = c?.status ?? row?.status ?? "submitted";
  // The saved case is the authority on the claim once it is read; the queue row only fills the wait.
  const claim = c ? c.claim ?? null : row?.claim ?? null;
  const latest = index?.latest ?? null;
  const professionalPending = Boolean(gaps?.some((g) => g.severity === "blocking" && g.field === "professional_requirement"));
  const available = c?.id === caseId && !loadError;

  // The screen changes under the keyboard (Pick up, Take over, the request and back):
  // move focus to the top of the work area so nobody is left on the page body.
  const screenKey = `${view}:${status}:${claim?.reviewer_id ?? ""}`;
  const lastScreen = useRef(screenKey);
  useEffect(() => {
    if (lastScreen.current === screenKey) return;
    lastScreen.current = screenKey;
    if (!work.current?.contains(document.activeElement) || document.activeElement === document.body) work.current?.focus({ preventScroll: true });
  }, [screenKey]);

  const pkg: PackageState = indexState === "loading" ? { state: "loading" }
    : indexState === "unavailable" ? { state: "unavailable" }
    : indexState === "failed" ? { state: "failed" }
    : !latest ? { state: "none" }
    : c && latest.case_version != null && latest.case_version !== c.version ? { state: "stale", version: latest.version }
    : { state: "current", blocking: blockingGaps(latest) };
  const gate = withPackage(decisionGate({ status, claim }, me, blocking, professionalPending), pkg);
  const questions = useMemo(() => (c ? sheetFromEngine(c, information).questions : []), [c, information]);
  const openQuestions = questions.filter((q) => q.state !== "answered").length;
  const mine = Boolean(claim && me && claim.reviewer_id === me);
  const canRun = mine && status === "in_review";
  const applicant = row ? row.applicant.name : "the applicant";
  const Applicant = applicant === "the applicant" ? "The applicant" : applicant;
  const title = c?.title?.trim() || row?.title?.trim() || "Application";
  const closeOut = index?.close_out ?? null;
  // A reservation kept across a resubmission still names its officer; only they resume it.
  const otherClaim = conflict ?? (claim && !mine && (status === "in_review" || status === "submitted") ? claim : null);
  const unclaimed = status === "submitted" && !claim && !otherClaim;
  const resumable = mine && status === "submitted";

  // Opening a file nobody has picked up picks it up: you are already in the review.
  useEffect(() => {
    if (!unclaimed || !available || !me || busy || autoClaimed.current === caseId) return;
    autoClaimed.current = caseId;
    void doClaim();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [unclaimed, available, me, caseId]);

  // Yours and not reviewed yet (or changed since): run the review now instead of asking for a
  // click. Once per saved version, so a failure shows its retry rather than looping.
  const needsRun = canRun && available && indexState === "ready" && (!latest || pkg.state === "stale");
  useEffect(() => {
    const key = `${caseId}:${c?.version ?? ""}`;
    if (!needsRun || running || autoRan.current === key) return;
    autoRan.current = key;
    void run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [needsRun, caseId, c?.version]);

  async function run(files?: File[]) {
    if (running) return;
    setRunning(true);
    setRunError("");
    try {
      const s = await packageReview.run(target, files);
      setShown(s);
      setView("flow");
      await loadIndex(true);
      await reload();
    } catch (e) {
      setRunError(e instanceof AccountsError
        ? e.status === 503 ? "The package review isn’t available on this server (the code database is missing)." : e.status === 413 ? "Those files are too large: at most 12 PDFs and 4 MB in total." : e.detail
        : "The review didn’t run. Try again.");
    } finally {
      setRunning(false);
    }
  }

  async function pickVersion(v: number) {
    if (shown?.version === v) return;
    setRunError("");
    try {
      setShown(await packageReview.version(target, v));
    } catch (e) {
      setRunError(e instanceof AccountsError ? e.detail : "That version didn’t load.");
    }
  }

  async function doClaim(takeOver = false) {
    const session = accountSession();
    const current = () => session === accountSession() && scope.current.session === session && scope.current.caseId === caseId;
    setBusy("claim");
    setActionError("");
    try {
      const cl = await review.claim(caseId, takeOver);
      if (!current()) return;
      setConflict(null);
      patchRow(caseId, { claim: cl, status: "in_review" }, session);
      // Deciding needs the case's new version, so read it again. The review then runs by itself (see
      // needsRun) unless one exists for this version; after a resend it runs again, so the diff shows
      // what changed.
      await reload();
      await loadIndex();
    } catch (e) {
      if (!current()) return;
      const other = claimConflict(e);
      if (other) setConflict(other);
      else setActionError(e instanceof AccountsError ? e.detail : "That didn’t work. Try again.");
      await reload();
    } finally {
      if (current()) setBusy("");
    }
  }

  async function release() {
    setBusy("release");
    setActionError("");
    try {
      await review.release(caseId);
      patchRow(caseId, { claim: null, status: "submitted" });
      // Back to the queue: staying here would pick it straight up again.
      window.location.hash = "#/review";
    } catch (e) {
      setActionError(e instanceof AccountsError ? e.detail : "That didn’t work. Try again.");
      if (e instanceof EngineError && e.status === 404) await reload();
    } finally {
      setBusy("");
    }
  }

  async function decided() {
    await reload();
    void loadQueue();
    await loadIndex(true);
  }

  async function accept() {
    if (!c) return;
    setConfirm("");
    setBusy("accept");
    setActionError("");
    try {
      await review.decide(caseId, { outcome: "accept", expected_version: c.version });
      patchRow(caseId, { status: "accepted" });
      setNote(`Accepted as administratively complete. ${Applicant} has been told.`);
      await decided();
    } catch (e) {
      setActionError(e instanceof AccountsError ? e.detail : "That didn’t work. Try again.");
      if (e instanceof EngineError && e.status === 404) await reload();
    } finally {
      setBusy("");
    }
  }

  async function sendReturn(message: string, items: DecisionItemInput[]) {
    if (!c) throw new Error("Refresh the application before recording a decision.");
    try {
      await review.decide(caseId, { outcome: "return", message, items, expected_version: c.version });
    } catch (e) {
      if (e instanceof EngineError && e.status === 404) await reload();
      throw e;
    }
    setReturning(false);
    setView("flow");
    patchRow(caseId, { status: "returned" });
    setNote(`Returned to ${applicant} with your message.`);
    await decided();
  }

  /** The officer's written reasons with the appeal notice, pinned to the version on screen. No correction list. */
  async function sendRefusal(reasons: string) {
    if (!c) throw new Error("Refresh the application before recording a decision.");
    try {
      await review.decide(caseId, refusalDecision(reasons, c.version));
    } catch (e) {
      if (e instanceof EngineError && e.status === 404) await reload();
      throw e;
    }
    setRefusing(false);
    setView("flow");
    patchRow(caseId, { status: "refused" });
    setCase((saved) => (saved ? { ...saved, status: "refused" } : saved));
    setNote(`Refusal sent to ${applicant} with the appeal notice. This application is closed.`);
    await decided();
  }

  /** The officer's own determination for this scope; acceptance waits for the refreshed result. */
  async function resolveProfessional(body: ProfessionalRequirementRequest) {
    setBusy("professional");
    setGaps(null);
    setGapError("");
    try {
      await review.resolveProfessional(caseId, body);
      await reload();
    } catch (e) {
      await reload();
      setGapError("Reload the completeness check before accepting this application.");
      throw e;
    } finally {
      setBusy("");
    }
  }

  function requestMore() {
    // Without a package review (or on a server without it), fall back to the plain return note.
    if (shown || latest) {
      // A failed refresh leaves an older index: never swap the version that just ran for it.
      if (latest && indexState === "ready" && shown?.version !== latest.version) setShown(latest);
      setView("request");
    } else setReturning(true);
  }

  /** Retry the index from the request view; once it is known, edit its newest version. */
  async function retryIndexForRequest() {
    setIndexState("loading");
    const ix = await loadIndex(true);
    if (ix?.latest && (!shown || ix.latest.version > shown.version)) setShown(ix.latest);
  }

  async function requestSentAndReturned() {
    patchRow(caseId, { status: "returned" });
    await decided();
  }

  const meta = [row ? applicantLine(row) : null, c?.submitted_at ? `sent ${sentPhrase(c.submitted_at)}` : null].filter(Boolean).join(" · ");
  const decidedRow = c?.decision ? `${c.decision.by_name} · ${sentLabel(c.decision.at)}` : "";
  const unread = (messages ?? []).filter((m) => m.kind !== "status" && !m.read_by_me && m.author.id !== me).length;
  const requestSent = Boolean(latest?.information_request.sent_at);
  const suggestAsk = gate.canReturn && !gate.canAccept;

  // The queue's badge follows what was actually read here (receipts name the displayed messages only).
  useEffect(() => {
    if (messages && available) patchRow(caseId, { unread_messages: unread });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [unread, messages === null, available]);

  const menu = [
    ...(canRun ? [
      { label: running ? "Reviewing…" : "Run the review again", onClick: () => void run(), disabled: running },
      { label: "Review uploaded PDFs", onClick: () => upload.current?.click(), disabled: running },
    ] : []),
    ...(mine && status === "in_review" ? [{ label: busy === "release" ? "Releasing…" : "Stop reviewing", onClick: () => void release(), separator: canRun, disabled: Boolean(busy) }] : []),
  ];

  /** Not yours to decide: the information request stays readable as a record. */
  const record = shown && view !== "request" ? <button type="button" className="cf-btn is-xs is-ghost rv-record" onClick={() => setView("request")}>Information request</button> : null;

  /** Who has the file: one quiet line above the path. */
  function claimLine() {
    // Yours: the steps in the header already say so; nothing to read here.
    if (unclaimed || resumable || (mine && status === "in_review")) return null;
    if (otherClaim) {
      return (
        <div className="rv-who">
          <Avatar name={otherClaim.reviewer_name} size="sm" />
          <span>{status === "submitted" ? `Reserved for ${otherClaim.reviewer_name}` : `${otherClaim.reviewer_name} is reviewing this`} <span className="ac-faint">· {sinceLabel(otherClaim.claimed_at)}</span></span>
          <button type="button" className="cf-btn is-xs" disabled={Boolean(busy)} onClick={() => setConfirm("takeover")}>Take over</button>
          {record}
        </div>
      );
    }
    return (
      <div className="rv-who">
        <StatusPill a={{ status, claim, submission_number: c?.submission_number }} />
        {decidedRow && <span className="ac-faint">{decidedRow}</span>}
        {record}
      </div>
    );
  }

  /** Nobody has picked it up: it is being picked up now, or that failed and one bar offers it again. */
  function pickUp() {
    if (busy === "claim" || (autoClaimed.current !== caseId && !actionError)) {
      return <p className="ac-empty rv-reading" role="status"><span className="rv-spin" aria-hidden="true" />Opening the review…</p>;
    }
    return (
      <>
        <div className="rv-pick" role="region" aria-label="Not picked up">
          <span className="rv-chip is-accent"><span className="cf-dot" aria-hidden="true" />New</span>
          <span className="rv-pick-t">Not picked up yet</span>
          <button type="button" className="cf-btn is-sm is-primary" disabled={Boolean(busy)} onClick={() => void doClaim()}>
            <AcIcon name="hand" size={15} />Pick up
          </button>
        </div>
        {c ? <Sheet c={c} information={information} questionError={questionError} /> : <p className="ac-empty">Loading the application…</p>}
      </>
    );
  }

  /** Resent with your reservation kept: nothing changes until you resume, so you see what changed first. */
  function resume() {
    return (
      <>
        <div className="rv-pick" role="region" aria-label="Resubmitted">
          <span className="rv-chip is-accent"><span className="cf-dot" aria-hidden="true" />Resubmitted</span>
          <span className="rv-pick-t">Waiting for you to resume</span>
          <button type="button" className="cf-btn is-sm is-primary" disabled={Boolean(busy)} onClick={() => void doClaim()}>
            {busy === "claim" ? "Resuming…" : "Resume review"}
          </button>
        </div>
        {c && <SubmissionHistory c={c} />}
        {c ? <Sheet c={c} information={information} questionError={questionError} /> : <p className="ac-empty">Loading the application…</p>}
      </>
    );
  }

  /** Why Accept is off, in a few words (the full sentence stays in the title and for screen readers). */
  function acceptHint(): string {
    const n = (k: number) => `${k} required ${k === 1 ? "item" : "items"}`;
    if (blocking === null || pkg.state === "loading") return "Checking…";
    if (professionalPending) return "Determination needed";
    if (blocking > 0) return `${n(blocking)} missing`;
    if (pkg.state === "current" && pkg.blocking > 0) return `${n(pkg.blocking)} open`;
    if (pkg.state === "stale") return "Changed · review again";
    if (pkg.state === "failed") return "Review didn’t load";
    if (pkg.state === "none") return "Not reviewed yet";
    return "Not yet";
  }

  /** The decision: three choices, each saying what it does. Accept waits for a clean review. */
  function decide() {
    return (
      <section className="rv-decide" aria-labelledby="rv-decide-h">
        <div id="rv-decide-h"><StepTitle step="final">Decide</StepTitle></div>
        <p className="rv-scope"><AcIcon name="clipboard" size={14} />Completeness only · not a design approval</p>
        <div className="rv-choices">
          <button type="button" className="rv-choice is-green" aria-label="Accept" aria-describedby="rv-choice-accept" disabled={!gate.canAccept || Boolean(busy) || refreshing} onClick={() => setConfirm("accept")} data-requires-no-blocking-gaps={gate.canAccept ? undefined : "true"}>
            <span className="pr-ico" aria-hidden="true"><AcIcon name="check" size={22} /></span>
            <span className="rv-choice-t">{busy === "accept" ? "Accepting…" : "Accept"}</span>
            <span id="rv-choice-accept" className="rv-choice-d" title={gate.canAccept ? undefined : gate.reason}>{gate.canAccept ? "Complete" : acceptHint()}</span>
          </button>
          <button type="button" className="rv-choice is-amber" aria-label="Ask for more" aria-describedby="rv-choice-ask" disabled={!gate.canReturn || Boolean(busy) || refreshing} onClick={requestMore}>
            <span className="pr-ico" aria-hidden="true"><AcIcon name="send" size={20} /></span>
            <span className="rv-choice-t">Ask for more</span>
            <span id="rv-choice-ask" className="rv-choice-d">{suggestAsk ? <span className="rv-tag">Suggested</span> : "Send a list"}</span>
          </button>
          <button type="button" className="rv-choice is-rose" aria-label="Refuse" aria-describedby="rv-choice-refuse" disabled={!gate.canRefuse || Boolean(busy) || refreshing} onClick={() => setRefusing(true)}>
            <span className="pr-ico" aria-hidden="true"><AcIcon name="ban" size={20} /></span>
            <span className="rv-choice-t">Refuse</span>
            <span id="rv-choice-refuse" className="rv-choice-d">With appeal notice</span>
          </button>
        </div>
        {!gate.canAccept && gate.reason && <p className="cf-sr" role="note">{gate.reason}</p>}
        {/* With a package review, Ask for more sends its request; the plain return (open applicant
            questions included, as clarification requests) stays one click away. */}
        {(shown || latest) && gate.canReturn && (
          <p className="rv-scope">
            {openQuestions > 0 && <>{openQuestions} open applicant {openQuestions === 1 ? "question" : "questions"} · </>}
            <button type="button" className="cf-link-btn" disabled={Boolean(busy) || refreshing} onClick={() => setReturning(true)}>Return with a message</button>
          </p>
        )}
        {c && (
          <ProfessionalRequirement
            c={c}
            editable={canRun}
            busy={Boolean(busy) || refreshing}
            unresolved={professionalPending}
            onEditingChange={setProfessionalEditing}
            onResolve={resolveProfessional}
          />
        )}
      </section>
    );
  }

  /** The path's last step: the decision while it's yours, otherwise the close-out or the outcome. */
  function finalStep(): FinalStep {
    if (gate.canReturn) return { label: "Decide", content: decide() };
    if (closeOut) {
      return {
        label: "Close-out",
        content: (
          <CloseOutPanel c={closeOut} bare>
            <CloseOutDue c={closeOut} inline canMark={Boolean(me && (c?.decision?.by_id === me || claim?.reviewer_id === me))} onChange={(co) => setIndex((ix) => (ix ? { ...ix, close_out: co } : ix))} />
          </CloseOutPanel>
        ),
      };
    }
    return {
      label: "Outcome",
      content: (
        <section className="rv-decide" aria-labelledby="rv-outcome-h">
          <h2 id="rv-outcome-h" className="pr-title">{status === "returned" ? "Back with the applicant" : status === "in_review" ? "Someone else is deciding" : "Where this stands"}</h2>
          {gate.reason && <p className="pr-lede">{gate.reason}</p>}
          {/* Take over sits once, on the "… is reviewing this" line above. */}
          {requestSent && (
            <div className="rv-start-acts">
              <button type="button" className="cf-btn is-sm is-ghost" onClick={() => setView("request")}>See the request that was sent</button>
            </div>
          )}
        </section>
      ),
    };
  }

  function main() {
    if (unclaimed) return pickUp();
    if (resumable) return resume();
    if (view === "request" && shown) {
      return (
        <>
          <button type="button" className="rv-back" onClick={() => setView("flow")}><AcIcon name="back" size={15} />{gate.canReturn ? "Back to your decision" : "Back"}</button>
          {/* The run on screen can be newer than a stale index; editing and sending wait until the index is known. */}
          {canRun && indexState !== "ready" && indexState !== "unavailable" && (
            <p className="pr-note rv-note" role={indexState === "failed" ? "alert" : "status"}>
              <span className="cf-dot is-warning" aria-hidden="true" />
              {indexState === "failed" ? "The review list didn’t refresh · editing waits" : "Checking the review list…"}
              {indexState === "failed" && <button type="button" className="cf-btn is-xs" onClick={() => void retryIndexForRequest()}>Try again</button>}
            </p>
          )}
          <InfoRequest
            target={target}
            session={shown}
            latest={!latest || shown.version >= latest.version}
            canEdit={canRun && (indexState === "ready" || indexState === "unavailable")}
            held={canRun && indexState !== "ready" && indexState !== "unavailable"}
            terminalStatus={status === "accepted" || status === "refused" ? status : undefined}
            applicant={applicant === "the applicant" ? "the applicant" : applicant}
            onChange={(s) => { setShown(s); void loadIndex(true); void reload(); }}
            onReturned={requestSentAndReturned}
          />
        </>
      );
    }
    if (indexState === "loading" && !shown) return <p className="ac-empty">Loading the review…</p>;
    if (indexState === "failed" && !shown) {
      return (
        <div className="rv-empty">
          <h2 className="pr-title">The review didn’t load</h2>
          <p className="pr-lede">Accept waits for it.</p>
          <button type="button" className="cf-btn is-sm" onClick={() => { setIndexState("loading"); void loadIndex(); }}>Try again</button>
          {gate.canReturn && <div className="rv-final">{decide()}</div>}
        </div>
      );
    }
    // Another officer has it and this page has no review of theirs to show: the line above says who
    // and offers Take over; nothing below repeats it.
    if (otherClaim && !shown) return null;
    if (indexState === "unavailable" || !shown) {
      const f = finalStep();
      return (
        <>
          <div className="rv-empty">
            {indexState === "unavailable" ? (
              <>
                <h2 className="pr-title">Read it, then decide</h2>
                <p className="pr-lede">No automatic review on this server.</p>
                <button type="button" className="cf-btn is-sm" onClick={() => setDrawer("application")}>Read the application</button>
              </>
            ) : canRun ? (
              runError ? (
                <>
                  <h2 className="pr-title">The review didn’t run</h2>
                  <p className="ac-error" role="alert">{runError}</p>
                  <div className="rv-start-acts">
                    <button type="button" className="cf-btn is-sm is-primary" disabled={running} onClick={() => void run()}>{running ? "Reviewing…" : "Try again"}</button>
                  </div>
                </>
              ) : (
                <p className="ac-empty rv-reading" role="status"><span className="rv-spin" aria-hidden="true" />Reading the application…</p>
              )
            ) : (
              <h2 className="pr-title">No review was run</h2>
            )}
          </div>
          {/* While the review reads the file, only that shows; a failed run still lets you decide. */}
          {(indexState === "unavailable" || !canRun || (gate.canReturn && runError)) && <div className="rv-final">{f.content}</div>}
        </>
      );
    }
    return (
      <>
        {runError && <p className="ac-error" role="alert">{runError}</p>}
        {/* The review on screen loaded; only the version list behind it did not. Accept waits for it. */}
        {indexState === "failed" && (
          <p className="pr-note rv-note" role="alert">
            <span className="cf-dot is-warning" aria-hidden="true" />The review list didn’t refresh · Accept waits
            <button type="button" className="cf-btn is-xs" onClick={() => { setIndexState("loading"); void loadIndex(true); }}>Try again</button>
          </p>
        )}
        {pkg.state === "stale" && canRun && (
          <p className="pr-note rv-note" role="note">
            <span className="cf-dot is-warning" aria-hidden="true" />Changed since review v{pkg.version}
            <button type="button" className="cf-btn is-xs" disabled={running} onClick={() => void run()}>{running ? "Reviewing…" : "Run it again"}</button>
          </p>
        )}
        <PackageReview
          session={shown}
          versions={index?.sessions ?? []}
          onPickVersion={(v) => void pickVersion(v)}
          final={finalStep()}
          initialStep={closeOut ? "final" : undefined}
          navTarget={stepSlot}
        />
      </>
    );
  }

  return (
    <div className="ac-page">
      <PageHead
        title={<><a className="ac-crumb" href="#/review">Queue</a><span className="ac-crumb-sep" aria-hidden="true">/</span><span className="ac-crumb-leaf" title={title}>{title}</span></>}
        phoneTools={phoneTools}
        center={<div ref={setStepSlot} className="rv-head-steps" />}
        right={!loadError && (
          <>
            {!unclaimed && (
              <button type="button" className="cf-btn is-sm is-ghost rv-head-btn" onClick={() => setDrawer("application")} aria-label="Application">
                <AcIcon name="doc" size={16} /><span className="rv-head-label">Application</span>
              </button>
            )}
            <button type="button" className="cf-btn is-sm is-ghost rv-head-btn" onClick={() => setDrawer("messages")} aria-label={unread ? `Messages, ${unread} unread` : "Messages"}>
              <AcIcon name="chat" size={16} /><span className="rv-head-label">Messages</span>
              {unread > 0 && <span className="rv-badge" aria-hidden="true">{unread}</span>}
            </button>
            {menu.length > 0 && <MoreMenu items={menu} />}
          </>
        )}
      />
      {loadError ? (
        <div className="ac-page-body is-narrow">
          <p className="ac-empty" role="status">{loadError}</p>
          <div className="cf-row-actions">
            <a className="cf-btn is-sm is-primary" href="#/review" onClick={() => void loadQueue()}>Back to the queue</a>
            <button type="button" className="cf-btn is-sm" onClick={() => { void reload("replace"); void loadQueue(); }}>Refresh</button>
          </div>
        </div>
      ) : (
        <div ref={work} className="ac-page-body rv" tabIndex={-1} aria-label="Review">
          {claimLine()}
          {note && <p className="ac-done rv-note" role="status"><span className="cf-dot is-done" aria-hidden="true" />{note}</p>}
          {actionError && <p className="ac-error rv-note" role="alert">{actionError}</p>}
          {refreshError && <p className="ac-error rv-note" role="status">{refreshError} <button type="button" className="cf-btn is-xs" onClick={refreshDetail}>Refresh application</button></p>}
          {main()}
        </div>
      )}

      <input ref={upload} className="pr-file-input" type="file" accept="application/pdf,.pdf" multiple tabIndex={-1} aria-hidden="true"
        onChange={(e) => { const f = [...(e.target.files ?? [])]; e.target.value = ""; if (f.length) void run(f); }} />
      <Drawer open={drawer === "application"} onClose={() => setDrawer("")} title="Application">
        {meta && <p className="ac-faint ac-small rv-drawer-meta">{meta}</p>}
        {available && <ExpiryNotice expiresAt={c.expires_at} officer />}
        {available && <SubmissionHistory c={c} />}
        <Completeness gaps={gaps} error={gapError} />
        {available && !canRun && <ProfessionalRequirement c={c} editable={false} busy={false} unresolved={professionalPending} onResolve={resolveProfessional} />}
        {available ? <Sheet c={c} information={information} questionError={questionError} /> : <p className="ac-empty">Loading the application…</p>}
      </Drawer>
      <Drawer open={drawer === "messages"} onClose={() => setDrawer("")} title="Messages">
        <Messages caseId={caseId} me={me} messages={messages} onChange={setMessages} canWrite={Boolean(user)} hideTitle draft={msgDraft} onDraft={setMsgDraft} reading={drawer === "messages"} />
      </Drawer>
      <ReturnDialog open={available && returning} caseId={caseId} applicant={Applicant} gaps={gaps ?? []} questions={questions} questionError={questionError} onClose={() => setReturning(false)} onSend={sendReturn} />
      <RefuseDialog key={`${me}:${caseId}`} open={available && refusing} applicant={Applicant} onClose={() => setRefusing(false)} onSend={sendRefusal} onRefresh={() => void reload()} />
      <ConfirmDialog
        open={available && confirm === "accept"}
        title="Accept as administratively complete?"
        body={<p>{Applicant} is told the application is administratively complete. It isn’t an approval of the design; technical review stays with the authority. The copy to the Safety Codes Council is then due within 10 days.</p>}
        cancel="Not yet"
        confirm="Accept as complete"
        onClose={() => setConfirm("")}
        onConfirm={() => void accept()}
      />
      <ConfirmDialog
        open={available && confirm === "takeover"}
        title="Take over this review?"
        body={<p>{otherClaim?.reviewer_name} started reviewing this application. If you take over, you become the reviewer and the history records both names.</p>}
        cancel="Keep theirs"
        confirm="Take over"
        onClose={() => setConfirm("")}
        onConfirm={() => { setConfirm(""); void doClaim(true); }}
      />
    </div>
  );
}
