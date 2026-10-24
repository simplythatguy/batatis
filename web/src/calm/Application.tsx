import { useEffect, useRef, useState } from "react";
import { submitBlockers, type ApplicationSummary } from "../api/accounts";
import { EngineError } from "../api/client";
import { Notices } from "../components";
import { evidenceBinding } from "../evidence";
import { EvidenceFileLink } from "../EvidenceFileLink";
import { UNSIGNED_LINE, professionalHoldReason, professionalRouteNote } from "../humanReview";
import { factFor, valueText } from "../model";
import { RetainedSourceFiles } from "../RetainedSourceFiles";
import { useApplicationExport } from "../screens/Application";
import { useCase } from "../store";
import type { Case } from "../types";
import { useAccount } from "./account";
import { authorityName, readOnlyStatus } from "./applications";
import { useCurrentApplication } from "./begin";
import { gapKey } from "./deck";
import { ExpiryNotice } from "./ExpiryNotice";
import { calmHref } from "./routes";
import { EngineerCallout } from "./Review";
import { FormPlaceholder, FormViewer } from "./FormViewer";
import { preparationGaps } from "./preparation";
import { CIcon, CompletenessNote, Dot, Eyebrow } from "./ui";
import { retryExtras, useCaseExtras } from "./caseExtras";

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
function SubmitPanel() {
  const { c, gaps, engineId, saveStatus, submitDraft, submitting: busy, checkStatus, requestCheck } = useCase();
  const account = useAccount();
  const { app } = useCurrentApplication();
  const [error, setError] = useState("");
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
  const reason = !c.authority ? "Choose a reviewing office." : n ? `${n} required ${n === 1 ? "item" : "items"} missing.` : needsCheck ? "Check your changed application first." : "";

  async function submit() {
    if (reason || busy || !app) return;
    setError("");
    setBlockers([]);
    try {
      await submitDraft(app.id);
    } catch (e) {
      const list = submitBlockers(e);
      if (list.length) setBlockers(list);
      else setError(e instanceof EngineError ? e.detail : e instanceof Error ? e.message : "The application was not submitted.");
    }
  }

  const linkFor = (b: { id: string; field: string | null }) => {
    const gap = gaps.find((g) => g.id === b.id || (b.field && g.field === b.field));
    const key = gap ? gapKey(c, gap) : null;
    return key ? `#/questions?focus=${encodeURIComponent(key)}` : gap ? calmHref(gap.href) : "#/review";
  };

  return (
    <div className="cf-submit">
      <button type="button" className="cf-btn is-primary is-center" disabled={Boolean(reason) || busy} onClick={() => void submit()}>
        {busy ? "Submitting…" : `${app.status === "returned" ? "Resubmit" : "Submit"} to ${where || "the authority"}`}
      </button>
      {reason && (
        <p className="cf-faint cf-small">
          {reason} {c.authority && needsCheck && !n
            ? <button type="button" className="cf-link-btn" disabled={checkStatus === "running"} onClick={() => void requestCheck(checkStatus === "unavailable")}>{checkStatus === "running" ? "Checking…" : "Check application"}</button>
            : <a className="cf-inline-link" href={!c.authority ? "#/questions?focus=authority" : "#/review"}>{!c.authority ? "Pick one" : "See them"}</a>}
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
                <a className="cf-row-go" href={linkFor(b)}>Fix <CIcon name="arrow" size={13} /></a>
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

/** The Section D documents as listed, each with its title and the id of its saved listing. */
function documents(c: Case): { id: string; title: string }[] {
  const titles = new Map<string, string>();
  for (const f of c.facts) {
    const m = /^evidence\.([^.]+)\.title$/.exec(f.field);
    if (m && typeof f.value === "string" && f.value.trim() && !c.unscopedEvidence?.includes(m[1])) titles.set(m[1], f.value.trim());
  }
  return [...titles].map(([id, title]) => ({ id, title }));
}

/**
 * The listed documents, one step away: each with its attached PDF (the actual saved bytes, through
 * the authorized download) or "Listed only". Batatis never says a file is attached when it is not.
 */
function DocumentList({ c, caseId }: { c: Case; caseId: string | null }) {
  const docs = documents(c);
  if (!docs.length) return null;
  return (
    <details className="cf-side-notice cf-side-docs">
      <summary className="cf-side-notice-h">Documents · {docs.length}</summary>
      {docs.map((doc) => {
        const binding = evidenceBinding(c.facts, doc.id);
        const metadata = ["evidence_type", "responsible_party", "date"].map((field) => valueText(factFor(c, `evidence.${doc.id}.${field}`)).trim()).filter(Boolean).join(" · ");
        return (
          <p className="cf-sheet-document" key={doc.id}>
            {doc.title}
            {metadata && <span className="cf-sheet-document-meta">{metadata}</span>}
            <span className="cf-sheet-document-meta">{binding && caseId
              ? <EvidenceFileLink caseId={caseId} fileId={binding.fileId} name={binding.name} />
              : "Listed only · no file attached"}</span>
          </p>
        );
      })}
    </details>
  );
}

/** Before an application exists: the empty form, so it is clear what will be filled in. */
function ApplicationEmpty() {
  return (
    <div className="cf-doc">
      <FormPlaceholder />
      <aside className="cf-glass cf-side" aria-label="Download">
        <Eyebrow plain>Status</Eyebrow>
        <div className="cf-side-big">Nothing filled in yet.</div>
        <a className="cf-btn is-primary is-center" href="#/">Describe your project</a>
        <CompletenessNote />
      </aside>
    </div>
  );
}

/** Show the current application and download options, or the empty form before a case exists. */
export function Application({ download }: { download: "" | "options" | "draft" }) {
  const { phase } = useCase();
  return phase === "case" ? <CaseApplication download={download} /> : <ApplicationEmpty />;
}

/** Derive the application preview and export panel from shared gaps and jurisdiction data. */
function CaseApplication({ download }: { download: "" | "options" | "draft" }) {
  const account = useAccount();
  const { app, locked, readOnly } = useCurrentApplication();
  const signedIn = account.phase === "signed-in";
  const { c, gaps, applicationIdentity, checkStatus, checkNote, engineId, factsEpoch } = useCase();
  const extras = useCaseExtras(engineId, factsEpoch, c.authority);
  const ex = useApplicationExport();
  const draftBtn = useRef<HTMLButtonElement>(null);
  const checked = checkStatus === "ready" || checkStatus === "needs_answers";

  useEffect(() => {
    if (!download) return;
    // "Download draft" from the menu is the explicit request; "options" only opens this panel.
    if (download === "draft") void ex.prepare(true);
    else draftBtn.current?.focus();
    location.replace("#/application");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [download]);

  const route = professionalRouteNote(ex.blocking);
  // The applicant's own items, the officer's determination and a needed fresh check are different next steps.
  const work = preparationGaps(c, ex.blocking);
  const officerPending = work.officer.length;
  const reasons: { tone: "blocking" | "warning" | "pending"; text: string; action?: { label: string; run: () => void } | { label: string; href: string } }[] = [];
  if (!ex.officialReady) {
    if (checkStatus === "running") reasons.push({ tone: "pending", text: checkNote || "Checking your draft…" });
    else if (!checked) reasons.push({ tone: "warning", text: checkStatus === "unavailable" ? "The last check couldn’t finish." : checkStatus === "stale" ? "Your application changed since the last check." : readOnly ? "Check the saved application to see the current official PDF requirements." : "Your application hasn’t been checked yet.", action: { label: readOnly ? "Check saved application" : checkStatus === "unavailable" ? "Try again" : "Check now", run: ex.runCheck } });
    // A saved (read-only) application is judged only by a current check of what was saved.
    if (officerPending && (!readOnly || checked)) reasons.push({ tone: "warning", text: "Officer determination pending. Official PDF and administrative acceptance remain on hold.", action: { label: "Review", href: "#/review" } });
    const professionalReason = professionalHoldReason(ex.blocking);
    if (professionalReason && !officerPending && !work.checkNeeded.length && (!readOnly || checked)) reasons.push({ tone: "warning", text: professionalReason });
  }

  // Each blocker links to the card that fixes it (the same shared gap list as Review and the deck).
  const blockers = ex.officialReady || (readOnly && !checked) ? [] : work.applicant;
  /** Link an export blocker to its deck card, falling back to the gap’s existing destination. */
  const fixHref = (g: (typeof gaps)[number]) => {
    const key = gapKey(c, g);
    return key ? `#/questions?focus=${encodeURIComponent(key)}` : calmHref(g.href);
  };
  const pack = extras.pack?.pack ?? null;
  const exportNotices = pack?.notices.filter((n) => n.surfaces.includes("export_header") || n.surfaces.includes("export_appendix")) ?? [];

  const applicantComplete = checked && !work.applicant.length && !work.checkNeeded.length && officerPending > 0;
  const headline = ex.officialReady ? "Ready for the official PDF." : applicantComplete ? "Ready to submit for review." : "You can download a draft.";
  const sub = ex.officialReady ? "Nothing required is missing." : applicantComplete ? "The professional question goes to the officer." : "Official PDF on hold.";
  const showStatus = ex.exportAttempted || ex.stage !== "idle";
  const showRoute = route && ex.stage === "blocked" && route !== ex.statusText;

  return (
    <div className="cf-doc">
      {/* The actual PDF the engine fills, not a drawing of it. */}
      <FormViewer locked={locked} status={readOnly && app ? readOnlyStatus(app.status).label.split(" · ")[0] : undefined} />
      <aside className="cf-glass cf-side" aria-label="Download">
        <Eyebrow plain>Status</Eyebrow>
        {!readOnly && <div className="cf-side-big">{headline}<br /><span className="cf-muted">{sub}</span></div>}
        {/* A new selection or sign-in owns its own errors; late callbacks target the unmounted panel. */}
        <SubmitPanel key={applicationIdentity} />
        <ExpiryNotice expiresAt={app?.expires_at} />
        {reasons.length > 0 && (
          <ul className="cf-rows is-compact">
            {reasons.map((r) => (
              <li key={r.text} className="cf-row">
                <Dot tone={r.tone} />
                <span className="cf-row-text">{r.text}</span>
                {r.action && ("href" in r.action
                  ? <a className="cf-row-go" href={r.action.href}>{r.action.label} <CIcon name="arrow" size={13} /></a>
                  : <button type="button" className="cf-row-go" disabled={ex.busy || checkStatus === "running"} onClick={r.action.run}>{r.action.label}</button>)}
              </li>
            ))}
          </ul>
        )}
        <button ref={draftBtn} type="button" className={`cf-btn is-center${signedIn ? "" : " is-primary"}`} disabled={ex.busy || Boolean(c.exampleId)} onClick={() => void ex.prepare(true)}>
          {ex.stage === "preparing" && ex.draftIntent ? "Preparing draft…" : "Download draft PDF"}
        </button>
        <button type="button" className="cf-btn is-center" disabled={ex.busy || !ex.officialReady} data-requires-no-blocking-gaps={ex.blocking.length ? "true" : undefined} title={ex.officialReady ? undefined : readOnly ? "Uses a current read-only check of the saved application." : "Unlocks after a current check finds no administrative holds, including any officer determination."} onClick={() => void ex.prepare(false)}>
          {ex.stage === "preparing" && !ex.draftIntent ? "Preparing PDF…" : "Official PDF"}
        </button>
        {blockers.length > 0 && (
          <div className="cf-side-blockers">
            <p className="cf-small">Still needed for the Official PDF:</p>
            <ul className="cf-rows is-compact">
              {blockers.slice(0, 5).map((g) => (
                <li key={g.id} className="cf-row">
                  <Dot tone="blocking" />
                  <span className="cf-row-text">{g.label}</span>
                  {!readOnly && <a className="cf-row-go" href={fixHref(g)}>Fix <CIcon name="arrow" size={13} /></a>}
                </li>
              ))}
            </ul>
            {blockers.length > 5 && <p className="cf-faint cf-small">And {blockers.length - 5} more. <a className="cf-inline-link" href="#/review">See all on Review</a></p>}
          </div>
        )}
        {!pack && c.authority && engineId && (
          extras.failed.case
            ? <p className="cf-note cf-small" role="status"><Dot tone="warning" />Office notes didn’t load. <button type="button" className="cf-link-btn" onClick={retryExtras}>Try again</button></p>
            : extras.pack
              // Loaded, and no notes for this office: nothing to show.
              ? null
              : <p className="cf-faint cf-small" role="status">Loading office notes…</p>
        )}
        {exportNotices.map((n) => (
          <details key={n.id} className="cf-side-notice">
            <summary className="cf-side-notice-h">{n.heading}</summary>
            <p>{n.message}</p>
            {n.sources[0] && <p><a className="cf-inline-link" href={n.sources[0].url} target="_blank" rel="noreferrer">{n.sources[0].title}</a></p>}
          </details>
        ))}
        <button type="button" className="cf-btn is-ghost is-sm is-center" aria-label="Download a text record" title={readOnly ? "The officer’s decision, reason, date and message history, with the saved answers. Not the official form." : "Not the official form"} disabled={ex.recordBusy} onClick={() => void ex.downloadRecord()}>{ex.recordBusy ? "Reading review record…" : "Text record"}</button>
        {ex.recordNote && <p className="cf-faint cf-small" role="status">{ex.recordNote}</p>}
        <DocumentList c={c} caseId={engineId} />
        <RetainedSourceFiles caseId={engineId} />

        {showStatus && (
          <div className="cf-side-status" role="status">
            {ex.busy && <span className="cf-dot is-pending cf-pulse" aria-hidden="true" />}
            <p>{ex.statusText}</p>
            {ex.stage === "ready" && ex.file && (
              <>
                <p className="cf-faint" title={ex.file.draft ? undefined : UNSIGNED_LINE}>{ex.file.draft ? "Draft: may be incomplete." : "Unsigned. Officer Part 2 is blank."}</p>
                <button type="button" className="cf-btn is-sm" onClick={ex.downloadAgain}>Download again</button>
              </>
            )}
            {ex.stage === "ready" && ex.file?.notice && <Notices notices={[ex.file.notice]} />}
          </div>
        )}
        {showRoute && <p className="cf-faint cf-small">{route}</p>}
        {(ex.tech || ex.reasons.length > 0) && (
          <details className="cf-tech">
            <summary>Technical detail</summary>
            {ex.reasons.length > 0 ? <ul>{ex.reasons.map((r) => <li key={r}>{r}</li>)}</ul> : <p>{ex.tech}</p>}
          </details>
        )}
        <EngineerCallout c={c} gaps={readOnly && !checked ? [] : gaps} readOnly={readOnly} />
        <CompletenessNote />
      </aside>
    </div>
  );
}
