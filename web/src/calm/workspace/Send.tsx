import { useEffect, useRef } from "react";
import { Notices } from "../../components";
import { evidenceBinding } from "../../evidence";
import { EvidenceFileLink } from "../../EvidenceFileLink";
import { professionalHoldReason, professionalRouteNote } from "../../humanReview";
import { factFor, valueText } from "../../model";
import { RetainedSourceFiles } from "../../RetainedSourceFiles";
import { useApplicationExport } from "../../screens/Application";
import { useCase } from "../../store";
import type { Case } from "../../types";
import { useCurrentApplication } from "../begin";
import { ExpiryNotice } from "../ExpiryNotice";
import { EngineerCallout } from "../Review";
import { PackagePreview } from "./PackagePreview";
import { SubmitPanel } from "./SubmitPanel";
import { listedDocuments, type DocSection } from "./document";
import { officerFlags, signingFlags } from "./readiness";
import type { WorkspaceController } from "./useWorkspace";
import { preparationGaps } from "../preparation";
import { CIcon, CompletenessNote, Dot } from "../ui";
import { retryExtras, useCaseExtras } from "../caseExtras";

/**
 * The listed documents, one step away: each with its attached PDF (the actual saved bytes, through
 * the authorized download) or "Listed only". Batatis never says a file is attached when it is not.
 */
function DocumentList({ c, caseId }: { c: Case; caseId: string | null }) {
  const docs = listedDocuments(c);
  return (
    <details className="cf-side-notice cf-side-docs" open>
      <summary className="cf-side-notice-h">In the package</summary>
      <p className="cf-sheet-document">Form · Part 1</p><p className="cf-sheet-document">Appendix · Your case</p>
      {docs.map((doc) => {
        const binding = evidenceBinding(c.facts, doc.id);
        const metadata = ["evidence_type", "responsible_party", "date"].map((field) => valueText(factFor(c, `evidence.${doc.id}.${field}`)).trim()).filter(Boolean).join(" · ");
        return (
          <p className="cf-sheet-document" key={doc.id}>
            {doc.title}
            {metadata && <span className="cf-sheet-document-meta">{metadata}</span>}
            <span className="cf-sheet-document-meta">{binding && caseId
              ? <><EvidenceFileLink caseId={caseId} fileId={binding.fileId} name={binding.name} />{c.files.find(f => f.engineId === binding.fileId || f.id === binding.fileId)?.pages != null && <span> · {c.files.find(f => f.engineId === binding.fileId || f.id === binding.fileId)?.pages} pages</span>}</>
              : "Not attached"}</span>
          </p>
        );
      })}
    </details>
  );
}

/** Officer package and the existing submission/export capabilities. */
export function Send({ download, workspace, sections, zoom }: { download: "" | "options" | "draft"; workspace: WorkspaceController; sections: DocSection[]; zoom: number }) {
  const { app, readOnly } = useCurrentApplication();
  const { c, gaps, applicationIdentity, checkStatus, checkNote, engineId, factsEpoch } = useCase();
  const extras = useCaseExtras(engineId, factsEpoch, c.authority);
  const signatureFlags = signingFlags(workspace.state, workspace.signaturesCurrent);
  const ex = useApplicationExport(() => true, "Applicant signatures are recorded in the package. Officer Part 2 is blank.");
  const officialReady = ex.officialReady && workspace.state.phase === "ready" && signatureFlags.length === 0;
  const flags = officerFlags(c, gaps, sections, signatureFlags);
  const versionKey = JSON.stringify([c.facts, c.process, c.authority, c.sectionC, workspace.state.record?.signatures, workspace.state.record?.consent]);
  const draftBtn = useRef<HTMLButtonElement>(null);
  const checked = checkStatus === "ready" || checkStatus === "needs_answers";

  useEffect(() => {
    if (!download) return;
    // "Download draft" from the menu is the explicit request; "options" only opens this panel.
    if (download === "draft") void ex.prepare(true);
    else draftBtn.current?.focus();
    location.replace("#/application?step=send");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [download]);

  const route = professionalRouteNote(ex.blocking);
  // The applicant's own items, the officer's determination and a needed fresh check are different next steps.
  const work = preparationGaps(c, ex.blocking);
  const officerPending = work.officer.length;
  const reasons: { tone: "blocking" | "warning" | "pending"; text: string; action?: { label: string; run: () => void } | { label: string; href: string } }[] = [];
  if (!officialReady) {
    if (checkStatus === "running") reasons.push({ tone: "pending", text: checkNote || "Checking your draft…" });
    else if (!checked) reasons.push({ tone: "warning", text: checkStatus === "unavailable" ? "The last check couldn’t finish." : checkStatus === "stale" ? "Your application changed since the last check." : readOnly ? "Check the saved application to see the current official PDF requirements." : "Your application hasn’t been checked yet.", action: { label: readOnly ? "Check saved application" : checkStatus === "unavailable" ? "Try again" : "Check now", run: ex.runCheck } });
    // A saved (read-only) application is judged only by a current check of what was saved.
    if (officerPending && (!readOnly || checked)) reasons.push({ tone: "warning", text: "Officer determination pending. Official PDF and administrative acceptance remain on hold.", action: { label: "Review", href: "#/review" } });
    const professionalReason = professionalHoldReason(ex.blocking);
    if (professionalReason && !officerPending && !work.checkNeeded.length && (!readOnly || checked)) reasons.push({ tone: "warning", text: professionalReason });
  }

  const pack = extras.pack?.pack ?? null;
  const exportNotices = pack?.notices.filter((n) => n.surfaces.includes("export_header") || n.surfaces.includes("export_appendix")) ?? [];

  const showStatus = ex.exportAttempted || ex.stage !== "idle";
  const showRoute = route && ex.stage === "blocked" && route !== ex.statusText;

  return (
    <div className="aw-send">
      <PackagePreview official={officialReady} versionKey={versionKey} zoom={zoom} />
      <aside className="cf-glass cf-side aw-send-side" aria-label="Send application">
        <h1 className="aw-flags-heading">Officer would flag {flags.length}</h1>
        {flags.length > 0 && <ul className="cf-rows is-compact">{flags.map(flag => <li key={flag.id} className="cf-row"><Dot tone="warning" /><span className="cf-row-text">{flag.label}</span>{!readOnly && <a className="cf-row-go" href={flag.href}>Fix <CIcon name="arrow" size={13} /></a>}</li>)}</ul>}
        {/* A new selection or sign-in owns its own errors; late callbacks target the unmounted panel. */}
        <SubmitPanel key={applicationIdentity} sections={sections} signingReason={workspace.state.phase !== "ready" ? workspace.state.note : signatureFlags.length ? "Review consent and signatures." : ""} beforeSubmit={workspace.flushHistory} />
        {workspace.state.phase === "failed" && <p className="cf-faint cf-small" role="status">{workspace.state.note} <button type="button" className="cf-link-btn" onClick={workspace.retry}>Try again</button></p>}
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
        <button ref={draftBtn} type="button" className="cf-btn is-center" disabled={ex.busy || Boolean(c.exampleId)} onClick={() => void ex.prepare(!officialReady)}><CIcon name="doc" size={15} />{ex.busy ? "Preparing PDF…" : "Download PDF"}</button>
        <p className="cf-faint cf-small">{officialReady ? "Official package" : "Draft · not for submission"}</p>
        <details className="cf-side-notice"><summary>Download options</summary><div className="aw-download-options">
          <button type="button" className="cf-btn is-sm" disabled={ex.busy || Boolean(c.exampleId)} onClick={() => void ex.prepare(true)}>Draft PDF</button>
          <button type="button" className="cf-btn is-sm" disabled={ex.busy || !officialReady} data-requires-no-blocking-gaps={!officialReady ? "true" : undefined} onClick={() => void ex.prepare(false)}>Official PDF</button>
          {!officialReady && <p className="cf-faint cf-small">Official PDF needs a current check, no required items, consent and current signatures.</p>}
        </div></details>
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
                <p className="cf-faint">{ex.file.draft ? "Draft: may be incomplete." : "Officer Part 2 is blank."}</p>
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
