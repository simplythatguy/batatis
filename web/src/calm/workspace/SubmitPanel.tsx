import { useRef, useState } from "react";
import { submitBlockers, type ApplicationSummary } from "../../api/accounts";
import { EngineError } from "../../api/client";
import { useCase } from "../../store";
import { useAccount } from "../account";
import { authorityName, readOnlyStatus } from "../applications";
import { useCurrentApplication } from "../begin";
import { preparationGaps } from "../preparation";
import { CIcon, Dot } from "../ui";
import type { DocSection } from "./document";
import { workspaceFixHref } from "./readiness";
import { submissionOfficeReason } from "../../config";

const when = (iso: string | null) => {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
};

/**
 * Submit to the reviewing authority (signed in only). Gated on the shared submission-blocking gaps; a
 * 409 shows the engine's own list. Submit saves the open draft first and sends exactly the version that
 * save acknowledged; a newer edit or a failed save stops it. After submitting the application is
 * read-only with its status.
 */
export function SubmitPanel({ signingReason, beforeSubmit, sections }: { signingReason: string; beforeSubmit: () => Promise<void>; sections: DocSection[] }) {
  const { c, gaps, engineId, saveStatus, submitDraft, submitting: busy, checkStatus, requestCheck } = useCase();
  const account = useAccount();
  const { app } = useCurrentApplication();
  const [error, setError] = useState("");
  const [preparing, setPreparing] = useState(false);
  const pending = useRef(false);
  const reasonNow = useRef("");
  const appNow = useRef(app); appNow.current = app;
  const [blockers, setBlockers] = useState<{ id: string; field: string | null; label: string }[]>([]);
  if (account.phase !== "signed-in") {
    return account.phase === "signed-out"
      ? <p className="cf-faint cf-small cf-submit-note"><a className="cf-inline-link" href="#/signin">Sign in</a> to submit.</p>
      : <p className="cf-faint cf-small cf-submit-note">Submitting isn’t available here.</p>;
  }
  if (!engineId || !app) {
    return <p className="cf-faint cf-small cf-submit-note" role="status">{saveStatus === "failed" || saveStatus === "gone" ? "Save to enable Submit." : "Saving your application…"}</p>;
  }
  const where = authorityName(app.authority || c.authority) || "";
  if (app.status !== "draft" && app.status !== "returned") {
    return <SubmittedStatus app={app} where={where} />;
  }
  // Items routed to the officer (whether a registered professional is required) travel with the
  // application: they close the official PDF and acceptance, not submission. The engine's submit check agrees.
  const blocking = gaps.filter((g) => g.severity === "blocking" && g.submissionBlocking !== false);
  const work = preparationGaps(c, blocking);
  const needsCheck = work.checkNeeded.length > 0;
  const routed = gaps.some((g) => g.severity === "blocking" && g.submissionBlocking === false);
  const n = work.applicant.length;
  // An office without reviewers in Batatis (anywhere but Calgary and Edmonton) receives the exported PDF instead.
  const office = c.authority ? submissionOfficeReason(c) : "";
  const reason = !c.authority ? "Choose a reviewing office." : office || (n ? "Edit the flagged items first." : needsCheck ? "Check your changed application first." : signingReason);

  reasonNow.current = reason;
  async function submit() {
    if (reason || busy || pending.current || !app) return;
    pending.current = true; setPreparing(true);
    setError("");
    setBlockers([]);
    try {
      await beforeSubmit();
      if (reasonNow.current || appNow.current?.id !== app.id || !["draft", "returned"].includes(appNow.current.status)) { setError("The application changed. Review it before submitting."); return; }
      await submitDraft(app.id);
    } catch (e) {
      const list = submitBlockers(e);
      if (list.length) setBlockers(list);
      else setError(e instanceof EngineError ? e.detail : e instanceof Error ? e.message : "The application was not submitted.");
    } finally {
      pending.current = false; setPreparing(false);
    }
  }

  const linkFor = (b: { id: string; field: string | null }) => {
    const gap = gaps.find((g) => g.id === b.id || (b.field && g.field === b.field));
    return gap ? workspaceFixHref(c, sections, gap) : b.field ? workspaceFixHref(c, sections, { id: b.id, field: b.field, href: "#/review" }) : "#/review";
  };

  return (
    <div className="cf-submit">
      <button type="button" className="cf-btn is-primary is-center" disabled={Boolean(reason) || busy || preparing} onClick={() => void submit()}>
        {busy || preparing ? "Submitting…" : `${app.status === "returned" ? "Resubmit" : "Submit"} to ${where || "the authority"}`}
      </button>
      {reason && (
        <p className="cf-faint cf-small">
          {reason} {office ? null : signingReason && !n && !needsCheck && c.authority ? <a className="cf-inline-link" href="#/application?step=sign">Sign</a> : c.authority && needsCheck && !n
            ? <button type="button" className="cf-link-btn" disabled={checkStatus === "running"} onClick={() => void requestCheck(checkStatus === "unavailable")}>{checkStatus === "running" ? "Checking…" : "Check application"}</button>
            : !c.authority ? <a className="cf-inline-link" href="#/questions?focus=authority">Pick one</a> : null}
        </p>
      )}
      {!reason && routed && <p className="cf-faint cf-small">The professional question goes to the officer with your application.</p>}
      {blockers.length > 0 && (
        <div role="status">
          <p className="cf-small">{blockers.length} required {blockers.length === 1 ? "item" : "items"} still missing:</p>
          <ul className="cf-rows is-compact">
            {blockers.map((b) => (
              <li key={b.id} className="cf-row">
                <Dot tone="blocking" />
                <span className="cf-row-text">{b.label}</span>
                <a className="cf-row-go" href={linkFor(b)}>Edit <CIcon name="arrow" size={13} /></a>
              </li>
            ))}
          </ul>
        </div>
      )}
      {error && <p className="cf-hint" role="status">{error}</p>}
    </div>
  );
}

function SubmittedStatus({ app, where }: { app: ApplicationSummary; where: string }) {
  const s = readOnlyStatus(app.status, where);
  const sent = app.submitted_at ? `${(app.submission_number ?? 1) > 1 ? `Resubmitted · submission ${app.submission_number}` : "Submitted"} ${when(app.submitted_at)}. ` : "";
  // A final status keeps its own truth (and never promises a return); a sent one says who has it.
  const line = app.status === "in_review" && app.reviewer?.name ? `${app.reviewer.name} is reviewing it. You can make corrections if the officer returns it.`
    : app.status === "submitted" && app.reviewer?.name ? `Waiting for ${app.reviewer.name} to resume review.`
    : app.status === "submitted" || app.status === "in_review" ? s.next
    : `${s.note} ${s.next}`;
  return (
    <div className="cf-submitted" role="status">
      <p className="cf-submitted-h">
        <Dot tone={s.tone} />
        {s.heading}
      </p>
      <p className="cf-faint cf-small">{sent}{line}</p>
    </div>
  );
}

