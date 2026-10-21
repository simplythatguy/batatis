/** #/review/<caseId>: the application as a paper sheet, completeness, messages, and the decision. */
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { accounts, AccountsError, claimConflict, review, type Claim, type DecisionItemInput, type Message } from "../../api/accounts";
import { engine, EngineError, type EngineGap } from "../../api/client";
import type { Case as EngineCase } from "../../api/types.gen";
import { CODE_EDITION } from "../../config";
import { useAccount } from "../account";
import { AcIcon, Avatar, PageHead } from "../auth/bits";
import { ConfirmDialog } from "../ui";
import { Messages } from "./Messages";
import { applicantLine, decisionGate, sentLabel, sentPhrase, sinceLabel } from "./queue";
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
    <section className="ac-side-sec" aria-labelledby="ac-comp-h">
      <h3 id="ac-comp-h" className="ac-side-h">Completeness</h3>
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
    </section>
  );
}

export function ReviewDetail({ caseId, phoneTools }: { caseId: string; phoneTools?: ReactNode }) {
  const { user } = useAccount();
  const me = user?.id ?? null;
  const q = useQueue();
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

  const row = q.rows.find((r) => r.id === caseId) ?? null;

  const reload = useCallback(async () => {
    try {
      const saved = (await engine.getCase(caseId)) as unknown as EngineCase;
      setCase(saved);
      setLoadError("");
    } catch (e) {
      setLoadError(e instanceof EngineError && e.status === 404 ? "This application isn’t available to you. It may have been withdrawn or sent to another authority." : "The application didn’t load.");
    }
  }, [caseId]);

  useEffect(() => {
    setCase(null);
    setGaps(null);
    setMessages(null);
    setNote("");
    setConflict(null);
    void reload();
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
  const gate = decisionGate({ status, claim }, me, blocking);
  const mine = Boolean(claim && me && claim.reviewer_id === me);
  const applicant = row ? row.applicant.name : "the applicant";
  const title = c?.title?.trim() || row?.title?.trim() || "Application";

  async function doClaim(takeOver = false) {
    setBusy("claim");
    setActionError("");
    try {
      const cl = await review.claim(caseId, takeOver);
      setConflict(null);
      patchRow(caseId, { claim: cl, status: "in_review" });
      await reload();
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
  }

  async function accept() {
    setConfirm("");
    setBusy("accept");
    setActionError("");
    try {
      await review.decide(caseId, { outcome: "accept" });
      patchRow(caseId, { status: "accepted" });
      setNote(`Accepted as administratively complete. ${applicant === "the applicant" ? "The applicant" : applicant} has been told.`);
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
    patchRow(caseId, { status: "returned" });
    setNote(`Returned to ${applicant} with your message.`);
    await decided();
  }

  const meta = [row ? applicantLine(row) : null, c?.submitted_at ? `sent ${sentPhrase(c.submitted_at)}` : null].filter(Boolean).join(" · ");

  const otherClaim = conflict ?? (claim && !mine && status === "in_review" ? claim : null);

  return (
    <div className="ac-page">
      <PageHead
        title={<><a className="ac-crumb" href="#/review">Queue</a><span className="ac-crumb-sep" aria-hidden="true">/</span>{title}</>}
        meta={meta ? `· ${meta}` : undefined}
        phoneTools={phoneTools}
        right={
          <>
            <button type="button" className="cf-btn is-sm" disabled={!gate.canReturn || Boolean(busy)} onClick={() => setReturning(true)}>Return with message</button>
            <button type="button" className="cf-btn is-sm is-primary" disabled={!gate.canAccept || Boolean(busy)} onClick={() => setConfirm("accept")} data-requires-no-blocking-gaps={blocking ? "true" : undefined}>
              {busy === "accept" ? "Accepting…" : "Accept as complete"}
            </button>
          </>
        }
      />
      {gate.reason && <p className="ac-gate-reason" role="note">{gate.reason}</p>}
      {loadError ? (
        <div className="ac-page-body is-narrow"><p className="ac-empty">{loadError} <a className="ac-link" href="#/review">Back to the queue</a></p></div>
      ) : (
        <div className="ac-rv">
          <div className="ac-rv-sheet">
            {c ? <Sheet c={c} /> : <p className="ac-empty">Loading the application…</p>}
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
                <div className="ac-claimed-txt">No one is reviewing this yet<small>Start reviewing so other officers know you’ve got it.</small></div>
                <button type="button" className="cf-btn is-xs" disabled={Boolean(busy)} onClick={() => void doClaim()}>
                  <AcIcon name="hand" size={14} />{busy === "claim" ? "Starting…" : "Start reviewing"}
                </button>
              </div>
            ) : (
              <div className="ac-claimed">
                <StatusPill a={{ status, claim }} />
                <div className="ac-claimed-txt">{c?.decision ? `${c.decision.by_name} · ${sentLabel(c.decision.at)}` : ""}</div>
              </div>
            )}

            <Completeness gaps={gaps} error={gapError} />
            <Messages caseId={caseId} me={me} messages={messages} onChange={setMessages} canWrite={Boolean(user)} />
            <p className="ac-faint ac-small ac-rv-fine">Accepting means administratively complete. It isn’t an approval of the design.</p>
          </aside>
        </div>
      )}

      <ReturnDialog open={returning} caseId={caseId} applicant={applicant === "the applicant" ? "The applicant" : applicant} gaps={gaps ?? []} onClose={() => setReturning(false)} onSend={sendReturn} />
      <ConfirmDialog
        open={confirm === "accept"}
        title="Accept as administratively complete?"
        body={<p>{applicant === "the applicant" ? "The applicant" : applicant} is told the application is administratively complete. It isn’t an approval of the design; technical review stays with the authority.</p>}
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
