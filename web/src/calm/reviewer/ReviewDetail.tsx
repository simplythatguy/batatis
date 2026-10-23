/**
 * #/review/<caseId>: one path, one thing on screen at a time. "Pick up" in the queue claims the
 * application and lands here on the review; the review runs by itself. Its four steps (Overview,
 * Missing, Checks, Decide) sit in the header as the shell's stage tabs. An application nobody has
 * picked up shows the application itself with one "Pick up" bar. The application and the messages
 * open in drawers from the header; running the review again and releasing the claim live in ⋯.
 */
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { accounts, AccountsError, claimConflict, review, type Claim, type DecisionItemInput, type Message } from "../../api/accounts";
import { engine, EngineError, type EngineGap } from "../../api/client";
import { packageReview, type ReviewTarget } from "../../api/packageReview";
import type { Case as EngineCase, PackageReviewIndex, ReviewSession } from "../../api/types.gen";
import { CODE_EDITION } from "../../config";
import { useAccount } from "../account";
import { AcIcon, Avatar, PageHead } from "../auth/bits";
import { CIcon, ConfirmDialog, Modal } from "../ui";
import { MoreMenu } from "../shell/MoreMenu";
import { Messages } from "./Messages";
import { CloseOutDue, CloseOutPanel } from "./CloseOutPanel";
import { InfoRequest } from "./InfoRequest";
import { PackageReview, StepTitle, type FinalStep } from "./PackageReview";
import { blockingGaps, refusalDecision } from "./packageView";
import { applicantLine, decisionGate, sentLabel, sentPhrase, sinceLabel, withPackage, type PackageState } from "./queue";
import { RefuseDialog } from "./RefuseDialog";
import { ReturnDialog } from "./ReturnDialog";
import { StatusPill } from "./ReviewQueue";
import { loadQueue, patchRow, setBlocking, useQueue } from "./reviewData";
import { sheetFromEngine, type SheetRow } from "./sheet";

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

function Sheet({ c }: { c: EngineCase }) {
  const s = useMemo(() => sheetFromEngine(c), [c]);
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
      <p className="cf-sheet-note">Professional evidence is provided by the applicant’s registered professional. Batatis does not write it.</p>
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
  // Mount on first open, then stay mounted: closing slides out with its content, and a half-written
  // message survives. Messages are only marked read once the drawer has been opened.
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
  const [busy, setBusy] = useState<"" | "claim" | "release" | "accept">("");
  const [note, setNote] = useState("");
  const [actionError, setActionError] = useState("");
  const [conflict, setConflict] = useState<Claim | null>(null);
  const [confirm, setConfirm] = useState<"" | "accept" | "takeover">("");
  const [returning, setReturning] = useState(false);
  const [refusing, setRefusing] = useState(false);
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

  const row = q.rows.find((r) => r.id === caseId) ?? null;

  const reload = useCallback(async (): Promise<EngineCase | null> => {
    try {
      const saved = (await engine.getCase(caseId)) as unknown as EngineCase;
      setCase(saved);
      setLoadError("");
      return saved;
    } catch (e) {
      setLoadError(e instanceof EngineError && e.status === 404 ? "This application isn’t available to you. It may have been withdrawn or sent to another authority." : "The application didn’t load.");
      return null;
    }
  }, [caseId]);

  const loadIndex = useCallback(async (keepShown = false) => {
    try {
      const ix = await packageReview.index(target);
      setIndex(ix);
      setIndexState("ready");
      if (!keepShown) setShown(ix.latest);
      return ix;
    } catch (e) {
      // Only a missing route means "not on this server"; anything else (network, 5xx) is a failure
      // with a retry, and acceptance waits for it.
      setIndexState(e instanceof EngineError && (e.status === 404 || e.status === 405) ? "unavailable" : "failed");
      return null;
    }
  }, [target]);

  useEffect(() => {
    setCase(null);
    setGaps(null);
    setMessages(null);
    setNote("");
    setConflict(null);
    setIndex(null);
    setShown(null);
    setIndexState("loading");
    void reload();
    setView("flow");
    setDrawer("");
    void loadIndex();
    if (!q.rows.length) void loadQueue();
    engine.gaps(caseId).then(
      (g) => { setGaps(g); setBlocking(caseId, g.filter((x) => x.severity === "blocking").length); },
      () => setGapError("The completeness check didn’t run. Reload to try again."),
    );
    accounts.messages(caseId).then(setMessages, () => setMessages([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId]);

  // Opening the messages reads them: the badge clears here and in the queue.
  useEffect(() => {
    if (drawer !== "messages") return;
    setMessages((ms) => (ms?.some((m) => !m.read_by_me) ? ms.map((m) => ({ ...m, read_by_me: true })) : ms));
    patchRow(caseId, { unread_messages: 0 });
  }, [drawer, messages, caseId]);

  // Unknown (loading or failed) is not "no gaps": acceptance waits for a real completeness result.
  const blocking = gaps === null ? null : gaps.filter((g) => g.severity === "blocking").length;
  const status = c?.status ?? row?.status ?? "submitted";
  const claim = c?.claim ?? row?.claim ?? null;
  const latest = index?.latest ?? null;

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
  const gate = withPackage(decisionGate({ status, claim }, me, blocking), pkg);
  const mine = Boolean(claim && me && claim.reviewer_id === me);
  const canRun = mine && status === "in_review";
  const applicant = row ? row.applicant.name : "the applicant";
  const Applicant = applicant === "the applicant" ? "The applicant" : applicant;
  const title = c?.title?.trim() || row?.title?.trim() || "Application";
  const closeOut = index?.close_out ?? null;

  // Yours and not reviewed yet (or changed since): run the review now instead of asking for a
  // click. Once per saved version, so a failure shows its retry rather than looping.
  const needsRun = canRun && indexState === "ready" && Boolean(c) && (!latest || pkg.state === "stale");
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
      // Reading messages can advance the saved version after the initial case load.
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
    setBusy("claim");
    setActionError("");
    try {
      const cl = await review.claim(caseId, takeOver);
      setConflict(null);
      patchRow(caseId, { claim: cl, status: "in_review" });
      // The review then runs by itself (see needsRun) unless one exists for this version of the
      // application; after a resend it runs again, so the diff shows what was resolved.
      await reload();
      await loadIndex();
    } catch (e) {
      const other = claimConflict(e);
      if (other) setConflict(other);
      else setActionError(e instanceof AccountsError ? e.detail : "That didn’t work. Try again.");
      await reload();
    } finally {
      setBusy("");
    }
  }

  async function release() {
    setBusy("release");
    setActionError("");
    try {
      await review.release(caseId);
      patchRow(caseId, { claim: null, status: "submitted" });
      await reload();
    } catch (e) {
      setActionError(e instanceof AccountsError ? e.detail : "That didn’t work. Try again.");
    } finally {
      setBusy("");
    }
  }

  async function decided() {
    await reload();
    accounts.messages(caseId).then(setMessages, () => undefined);
    void loadQueue();
    await loadIndex(true);
  }

  async function accept() {
    setConfirm("");
    setBusy("accept");
    setActionError("");
    try {
      await review.decide(caseId, { outcome: "accept" });
      patchRow(caseId, { status: "accepted" });
      setNote(`Accepted as administratively complete. ${Applicant} has been told.`);
      await decided();
    } catch (e) {
      setActionError(e instanceof AccountsError ? e.detail : "That didn’t work. Try again.");
    } finally {
      setBusy("");
    }
  }

  async function sendReturn(message: string, items: DecisionItemInput[]) {
    await review.decide(caseId, { outcome: "return", message, items });
    setReturning(false);
    setView("flow");
    patchRow(caseId, { status: "returned" });
    setNote(`Returned to ${applicant} with your message.`);
    await decided();
  }

  async function sendRefusal(reasons: string) {
    await review.decide(caseId, refusalDecision(reasons));
    setRefusing(false);
    setView("flow");
    patchRow(caseId, { status: "refused" });
    setCase((saved) => saved ? { ...saved, status: "refused" } : saved);
    setNote(`Refusal sent to ${applicant} with the appeal notice. This application is closed.`);
    await decided();
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
  const otherClaim = conflict ?? (claim && !mine && status === "in_review" ? claim : null);
  const decidedRow = c?.decision ? `${c.decision.by_name} · ${sentLabel(c.decision.at)}` : "";
  const unclaimed = status === "submitted" && !claim && !otherClaim;
  const unread = (messages ?? []).filter((m) => m.kind !== "status" && !m.read_by_me && m.author.id !== me).length;
  const requestSent = Boolean(latest?.information_request.sent_at);
  const suggestAsk = gate.canReturn && !gate.canAccept;

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
    if (unclaimed || (mine && status === "in_review")) return null;
    if (otherClaim) {
      return (
        <div className="rv-who">
          <Avatar name={otherClaim.reviewer_name} size="sm" />
          <span>{otherClaim.reviewer_name} is reviewing this <span className="ac-faint">· {sinceLabel(otherClaim.claimed_at)}</span></span>
          <button type="button" className="cf-btn is-xs" disabled={Boolean(busy)} onClick={() => setConfirm("takeover")}>Take over</button>
          {record}
        </div>
      );
    }
    return (
      <div className="rv-who">
        <StatusPill a={{ status, claim }} />
        {decidedRow && <span className="ac-faint">{decidedRow}</span>}
        {record}
      </div>
    );
  }

  /** Nobody has picked it up: the application itself, with one bar to pick it up. */
  function pickUp() {
    return (
      <>
        <div className="rv-pick" role="region" aria-label="Not picked up">
          <span className="rv-chip is-accent"><span className="cf-dot" aria-hidden="true" />New</span>
          <span className="rv-pick-t">Not picked up yet</span>
          <button type="button" className="cf-btn is-sm is-primary" disabled={Boolean(busy)} onClick={() => void doClaim()}>
            <AcIcon name="hand" size={15} />{busy === "claim" ? "Picking up…" : "Pick up"}
          </button>
        </div>
        {c ? <Sheet c={c} /> : <p className="ac-empty">Loading the application…</p>}
      </>
    );
  }

  /** Why Accept is off, in a few words (the full sentence stays in the title and for screen readers). */
  function acceptHint(): string {
    const n = (k: number) => `${k} required ${k === 1 ? "item" : "items"}`;
    if (blocking === null || pkg.state === "loading") return "Checking…";
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
        <div id="rv-decide-h"><StepTitle step="final">Your decision</StepTitle></div>
        <p className="rv-scope"><AcIcon name="clipboard" size={14} />Completeness only · not a design approval</p>
        <div className="rv-choices">
          <button type="button" className="rv-choice is-green" disabled={!gate.canAccept || Boolean(busy)} onClick={() => setConfirm("accept")} data-requires-no-blocking-gaps={gate.canAccept ? undefined : "true"}>
            <span className="pr-ico" aria-hidden="true"><AcIcon name="check" size={22} /></span>
            <span className="rv-choice-t">{busy === "accept" ? "Accepting…" : "Accept"}</span>
            <span className="rv-choice-d" title={gate.canAccept ? undefined : gate.reason}>{gate.canAccept ? "Complete" : acceptHint()}</span>
          </button>
          <button type="button" className="rv-choice is-amber" disabled={Boolean(busy)} onClick={requestMore}>
            <span className="pr-ico" aria-hidden="true"><AcIcon name="send" size={20} /></span>
            <span className="rv-choice-t">Ask for more</span>
            <span className="rv-choice-d">{suggestAsk ? <span className="rv-tag">Suggested</span> : "Send a list"}</span>
          </button>
          <button type="button" className="rv-choice is-rose" disabled={Boolean(busy)} onClick={() => setRefusing(true)}>
            <span className="pr-ico" aria-hidden="true"><AcIcon name="ban" size={20} /></span>
            <span className="rv-choice-t">Refuse</span>
            <span className="rv-choice-d">With appeal notice</span>
          </button>
        </div>
        {!gate.canAccept && gate.reason && <p className="cf-sr" role="note">{gate.reason}</p>}
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
          <div className="rv-start-acts">
            {otherClaim && <button type="button" className="cf-btn is-sm" disabled={Boolean(busy)} onClick={() => setConfirm("takeover")}>Take over</button>}
            {requestSent && <button type="button" className="cf-btn is-sm is-ghost" onClick={() => setView("request")}>See the request that was sent</button>}
          </div>
        </section>
      ),
    };
  }

  function main() {
    if (unclaimed) return pickUp();
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
            onChange={(s) => { setShown(s); void loadIndex(true); accounts.messages(caseId).then(setMessages, () => undefined); }}
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
              <>
                <h2 className="pr-title">No review was run</h2>
                
              </>
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
        <div className="ac-page-body is-narrow"><p className="ac-empty">{loadError} <a className="ac-link" href="#/review">Back to the queue</a></p></div>
      ) : (
        <div ref={work} className="ac-page-body rv" tabIndex={-1} aria-label="Review">
          {claimLine()}
          {note && <p className="ac-done rv-note" role="status"><span className="cf-dot is-done" aria-hidden="true" />{note}</p>}
          {actionError && <p className="ac-error rv-note" role="alert">{actionError}</p>}
          {main()}
        </div>
      )}

      <input ref={upload} className="pr-file-input" type="file" accept="application/pdf,.pdf" multiple tabIndex={-1} aria-hidden="true"
        onChange={(e) => { const f = [...(e.target.files ?? [])]; e.target.value = ""; if (f.length) void run(f); }} />
      <Drawer open={drawer === "application"} onClose={() => setDrawer("")} title="Application">
        {meta && <p className="ac-faint ac-small rv-drawer-meta">{meta}</p>}
        <Completeness gaps={gaps} error={gapError} />
        {c ? <Sheet c={c} /> : <p className="ac-empty">Loading the application…</p>}
      </Drawer>
      <Drawer open={drawer === "messages"} onClose={() => setDrawer("")} title="Messages">
        <Messages caseId={caseId} me={me} messages={messages} onChange={setMessages} canWrite={Boolean(user)} hideTitle draft={msgDraft} onDraft={setMsgDraft} />
      </Drawer>
      <ReturnDialog open={returning} caseId={caseId} applicant={Applicant} gaps={gaps ?? []} onClose={() => setReturning(false)} onSend={sendReturn} />
      <RefuseDialog open={refusing} applicant={Applicant} onClose={() => setRefusing(false)} onSend={sendRefusal} />
      <ConfirmDialog
        open={confirm === "accept"}
        title="Accept as administratively complete?"
        body={<p>{Applicant} is told the application is administratively complete. It isn’t an approval of the design; technical review stays with the authority. The copy to the Safety Codes Council is then due within 10 days.</p>}
        cancel="Not yet"
        confirm="Accept as complete"
        onClose={() => setConfirm("")}
        onConfirm={() => void accept()}
      />
      <ConfirmDialog
        open={confirm === "takeover"}
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
