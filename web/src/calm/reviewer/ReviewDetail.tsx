/**
 * #/review/<caseId>: the package review (one step at a time), the information request, the
 * application as a paper sheet and the close-out in the main pane; the claim, the decision
 * (accept, refuse, request more information), the close-out due date and messages beside it.
 */
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { accounts, AccountsError, claimConflict, review, type Claim, type DecisionItemInput, type Message } from "../../api/accounts";
import { engine, EngineError, type EngineGap } from "../../api/client";
import { packageReview, type ReviewTarget } from "../../api/packageReview";
import type { Case as EngineCase, PackageReviewIndex, ReviewSession } from "../../api/types.gen";
import { CODE_EDITION } from "../../config";
import { useAccount } from "../account";
import { AcIcon, Avatar, PageHead } from "../auth/bits";
import { CIcon, ConfirmDialog } from "../ui";
import { Messages } from "./Messages";
import { CloseOutDue, CloseOutPanel } from "./CloseOutPanel";
import { InfoRequest } from "./InfoRequest";
import { PackageReview } from "./PackageReview";
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
  return (
    <details className="ac-side-sec pr-checklist">
      <summary id="ac-comp-h">Applicant’s checklist{gaps ? ` · ${gaps.filter((g) => g.severity === "blocking").length} required missing` : ""}</summary>
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
    </details>
  );
}

type View = "review" | "request" | "application" | "closeout";

function UploadButton({ disabled, onFiles, label = "Upload PDFs" }: { disabled?: boolean; onFiles: (files: File[]) => void; label?: string }) {
  const input = useRef<HTMLInputElement>(null);
  return (
    <>
      <input ref={input} className="pr-file-input" type="file" accept="application/pdf,.pdf" multiple tabIndex={-1} aria-hidden="true"
        onChange={(e) => { const f = [...(e.target.files ?? [])]; e.target.value = ""; if (f.length) onFiles(f); }} />
      <button type="button" className="cf-btn is-xs" disabled={disabled} onClick={() => input.current?.click()}><CIcon name="upload" size={13} />{label}</button>
    </>
  );
}

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
  const [view, setView] = useState<View>("review");

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
    void loadIndex().then((ix) => { if (ix?.close_out) setView("closeout"); });
    if (!q.rows.length) void loadQueue();
    engine.gaps(caseId).then(
      (g) => { setGaps(g); setBlocking(caseId, g.filter((x) => x.severity === "blocking").length); },
      () => setGapError("The completeness check didn’t run. Reload to try again."),
    );
    accounts.messages(caseId).then(setMessages, () => setMessages([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId]);

  // Unknown (loading or failed) is not "no gaps": acceptance waits for a real completeness result.
  const blocking = gaps === null ? null : gaps.filter((g) => g.severity === "blocking").length;
  const status = c?.status ?? row?.status ?? "submitted";
  const claim = c?.claim ?? row?.claim ?? null;
  const latest = index?.latest ?? null;
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

  async function run(files?: File[]) {
    if (running) return;
    setRunning(true);
    setRunError("");
    try {
      const s = await packageReview.run(target, files);
      setShown(s);
      setView("review");
      await loadIndex(true);
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
      const saved = await reload();
      // Starting a review runs the package review, unless one exists for this version of the
      // application (after a resend it runs again, so the diff shows what was resolved).
      const ix = await loadIndex();
      const stale = ix?.latest && saved && ix.latest.case_version != null && ix.latest.case_version !== saved.version;
      if (ix && (!ix.latest || stale)) void run();
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
    const ix = await loadIndex(true);
    if (ix?.close_out) setView("closeout");
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
    setView("review");
    patchRow(caseId, { status: "returned" });
    setNote(`Returned to ${applicant} with your message.`);
    await decided();
  }

  async function sendRefusal(reasons: string) {
    await review.decide(caseId, refusalDecision(reasons));
    setRefusing(false);
    setView("review");
    patchRow(caseId, { status: "refused" });
    setCase((saved) => saved ? { ...saved, status: "refused" } : saved);
    setNote(`Refusal sent to ${applicant} with the appeal notice. This application is closed.`);
    await decided();
  }

  function requestMore() {
    // Without a package review (or on a server without it), fall back to the plain return note.
    if (shown || latest) {
      if (latest && shown?.version !== latest.version) setShown(latest);
      setView("request");
    } else setReturning(true);
  }

  async function requestSentAndReturned() {
    patchRow(caseId, { status: "returned" });
    await decided();
  }

  const meta = [row ? applicantLine(row) : null, c?.submitted_at ? `sent ${sentPhrase(c.submitted_at)}` : null].filter(Boolean).join(" · ");
  const otherClaim = conflict ?? (claim && !mine && status === "in_review" ? claim : null);
  const decidedRow = c?.decision ? `${c.decision.by_name} · ${sentLabel(c.decision.at)}` : "";

  const views: { id: View; label: string }[] = [
    { id: "review", label: "Package review" },
    { id: "request", label: "Information request" },
    { id: "application", label: "Application" },
    ...(closeOut ? [{ id: "closeout" as View, label: "Close-out" }] : []),
  ];

  const runActions = canRun ? (
    <>
      <button type="button" className="cf-btn is-xs" disabled={running} onClick={() => void run()}><CIcon name="retry" size={13} />{running ? "Reviewing…" : "Run again"}</button>
      <UploadButton disabled={running} onFiles={(f) => void run(f)} />
    </>
  ) : undefined;

  function main() {
    if (view === "application") return c ? <Sheet c={c} /> : <p className="ac-empty">Loading the application…</p>;
    if (view === "closeout" && closeOut) return <CloseOutPanel c={closeOut} />;
    if (indexState === "loading") return <p className="ac-empty pr-empty">Loading the package review…</p>;
    if (indexState === "failed") {
      return (
        <div className="pr-empty">
          <h2 className="pr-title">The package review didn’t load</h2>
          <p className="pr-lede">Acceptance waits until it does.</p>
          <button type="button" className="cf-btn is-sm" onClick={() => { setIndexState("loading"); void loadIndex(); }}>Try again</button>
        </div>
      );
    }
    if (indexState === "unavailable") {
      return (
        <div className="pr-empty">
          <h2 className="pr-title">Package review isn’t available here</h2>
          <p className="pr-lede">This server doesn’t run the package review. Read the application and use the checklist beside it.</p>
          <button type="button" className="cf-btn is-sm" onClick={() => setView("application")}>Read the application</button>
        </div>
      );
    }
    if (!shown) {
      return (
        <div className="pr-empty">
          <h2 className="pr-title">{running ? "Reviewing the package…" : "No package review yet"}</h2>
          <p className="pr-lede">
            {canRun
              ? "The review reads the saved application, or PDFs you upload (the SCC form, fillable or flattened, and its attachments), and lists what is present, blank or not found."
              : status === "submitted" ? "Start reviewing to run the package review." : "No package review was run for this application."}
          </p>
          {runError && <p className="ac-error" role="alert">{runError}</p>}
          {canRun && (
            <div className="pr-head-acts">
              <button type="button" className="cf-btn is-sm is-primary" disabled={running} onClick={() => void run()}>{running ? "Reviewing…" : "Review the saved application"}</button>
              <UploadButton disabled={running} onFiles={(f) => void run(f)} label="Review uploaded PDFs" />
            </div>
          )}
        </div>
      );
    }
    if (view === "request") {
      return (
        <InfoRequest
          target={target}
          session={shown}
          latest={!latest || shown.version === latest.version}
          canEdit={canRun}
          applicant={applicant === "the applicant" ? "the applicant" : applicant}
          onChange={(s) => { setShown(s); void loadIndex(true); accounts.messages(caseId).then(setMessages, () => undefined); }}
          onReturned={requestSentAndReturned}
        />
      );
    }
    return (
      <>
        {runError && <p className="ac-error pr-empty" role="alert">{runError}</p>}
        {pkg.state === "stale" && canRun && (
          <p className="pr-note pr-empty" role="note"><span className="cf-dot is-warning" aria-hidden="true" />The application changed after version {pkg.version}. Run the review again to see what was resolved.</p>
        )}
        <PackageReview
          session={shown}
          versions={index?.sessions ?? []}
          onPickVersion={(v) => void pickVersion(v)}
          actions={runActions}
          finish={{ label: "Information request", onClick: () => setView("request") }}
        />
      </>
    );
  }

  return (
    <div className="ac-page">
      <PageHead
        title={<><a className="ac-crumb" href="#/review">Queue</a><span className="ac-crumb-sep" aria-hidden="true">/</span>{title}</>}
        meta={meta ? `· ${meta}` : undefined}
        phoneTools={phoneTools}
      />
      {loadError ? (
        <div className="ac-page-body is-narrow"><p className="ac-empty">{loadError} <a className="ac-link" href="#/review">Back to the queue</a></p></div>
      ) : (
        <div className="ac-rv">
          <div className="ac-rv-sheet pr-main">
            <div className="pr-view" role="group" aria-label="Show">
              {views.map((v) => (
                <button key={v.id} type="button" className="ac-tab" aria-pressed={view === v.id} onClick={() => setView(v.id)}>{v.label}</button>
              ))}
            </div>
            {main()}
          </div>
          <aside className="ac-rv-side" aria-label="Review">
            {note && <p className="ac-done" role="status"><span className="cf-dot is-done" aria-hidden="true" />{note}</p>}
            {actionError && <p className="ac-error" role="alert">{actionError}</p>}

            {mine && status === "in_review" ? (
              <div className="ac-claimed">
                <Avatar name={user?.name ?? user?.email} />
                <div className="ac-claimed-txt">You’re reviewing this<small>{sinceLabel(claim!.claimed_at)} · other officers see your name</small></div>
                <button type="button" className="cf-btn is-xs is-ghost" disabled={Boolean(busy)} onClick={() => void release()}>{busy === "release" ? "Releasing…" : "Release"}</button>
              </div>
            ) : otherClaim ? (
              <div className="ac-claimed">
                <Avatar name={otherClaim.reviewer_name} />
                <div className="ac-claimed-txt">{otherClaim.reviewer_name} is reviewing this<small>{sinceLabel(otherClaim.claimed_at)}</small></div>
                <button type="button" className="cf-btn is-xs" disabled={Boolean(busy)} onClick={() => setConfirm("takeover")}>Take over</button>
              </div>
            ) : status === "submitted" ? (
              <div className="ac-claimed">
                <span className="ac-av is-md is-empty" aria-hidden="true" />
                <div className="ac-claimed-txt">No one is reviewing this yet<small>Start reviewing so other officers know you’ve got it. The package review runs straight away.</small></div>
                <button type="button" className="cf-btn is-xs" disabled={Boolean(busy)} onClick={() => void doClaim()}>
                  <AcIcon name="hand" size={14} />{busy === "claim" ? "Starting…" : "Start reviewing"}
                </button>
              </div>
            ) : (
              <div className="ac-claimed">
                <StatusPill a={{ status, claim }} />
                <div className="ac-claimed-txt">{decidedRow}</div>
              </div>
            )}

            {gate.canReturn ? (
              <section className="ac-side-sec pr-decide" aria-labelledby="pr-decide-h">
                <h3 id="pr-decide-h" className="ac-side-h">Decide</h3>
                <button type="button" className="cf-btn is-sm" disabled={Boolean(busy)} onClick={requestMore}>Request more information</button>
                <div className="pr-decide-row">
                  <button type="button" className="cf-btn is-sm" disabled={Boolean(busy)} onClick={() => setRefusing(true)}>Refuse</button>
                  <button type="button" className="cf-btn is-sm is-primary" disabled={!gate.canAccept || Boolean(busy)} onClick={() => setConfirm("accept")} data-requires-no-blocking-gaps={gate.canAccept ? undefined : "true"}>
                    {busy === "accept" ? "Accepting…" : "Accept as complete"}
                  </button>
                </div>
                {gate.reason && <p className="ac-faint ac-small" role="note">{gate.reason}</p>}
              </section>
            ) : (
              gate.reason && !closeOut && <p className="ac-faint ac-small" role="note">{gate.reason}</p>
            )}

            {closeOut && <CloseOutDue c={closeOut} canMark={Boolean(me && (c?.decision?.by_id === me || claim?.reviewer_id === me))} onChange={(co) => setIndex((ix) => (ix ? { ...ix, close_out: co } : ix))} />}

            <Completeness gaps={gaps} error={gapError} />
            <Messages caseId={caseId} me={me} messages={messages} onChange={setMessages} canWrite={Boolean(user)} />
            <p className="ac-faint ac-small ac-rv-fine">Accepting means administratively complete. It isn’t an approval of the design.</p>
          </aside>
        </div>
      )}

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
