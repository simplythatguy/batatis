import { useEffect, useRef, useState } from "react";
import { Notices } from "../../components";
import { evidenceBinding } from "../../evidence";
import { EvidenceFileLink } from "../../EvidenceFileLink";
import { professionalHoldReason, professionalRouteNote } from "../../humanReview";
import { factFor, valueText } from "../../model";
import { RetainedSourceFiles } from "../../RetainedSourceFiles";
import { useApplicationExport } from "../../screens/Application";
import { useCase } from "../../store";
import { useCurrentApplication } from "../begin";
import { retryExtras, useCaseExtras } from "../caseExtras";
import { ExpiryNotice } from "../ExpiryNotice";
import { Icon24 } from "../icons";
import { preparationGaps } from "../preparation";
import { EngineerCallout } from "../Review";
import { CompletenessNote, Dot } from "../ui";
import { listedDocuments, type DocSection } from "./document";
import { PackagePreview } from "./PackagePreview";
import { GROUP_LABEL, groupFlags, officerFlags, signingFlags } from "./readiness";
import { SubmitPanel } from "./SubmitPanel";
import type { WorkspaceController } from "./useWorkspace";

const SHOWN = 6;

/** What the officer receives, what they would flag, and the one action that sends it. */
export function Send({ download, workspace, sections, zoom }: { download: "" | "options" | "draft"; workspace: WorkspaceController; sections: DocSection[]; zoom: number }) {
  const { app, readOnly } = useCurrentApplication();
  const { c, gaps, applicationIdentity, checkStatus, checkNote, engineId, factsEpoch } = useCase();
  const extras = useCaseExtras(engineId, factsEpoch, c.authority);
  const signing = signingFlags(workspace.state, workspace.signaturesCurrent);
  const ex = useApplicationExport(() => true, "Applicant signatures are in the package. Officer Part 2 is blank.");
  const officialReady = ex.officialReady && workspace.state.phase === "ready" && signing.length === 0;
  const flags = officerFlags(c, gaps, sections, signing);
  const groups = groupFlags(flags);
  const total = groups.reduce((n, g) => n + g.rows.length, 0);
  const [all, setAll] = useState(false);
  // What the package shows, not how the store happens to hold it: a save that only renumbers facts is no change.
  const record = workspace.state.record;
  const versionKey = JSON.stringify([
    Object.entries(Object.fromEntries(c.facts.filter(f => f.status === "confirmed" && f.kind !== "proposed").map(f => [f.field, f.value]))).sort(([a], [b]) => a.localeCompare(b)),
    c.process, c.authority, c.sectionC.map(r => r.provision),
    record?.signatures.map(sig => [sig.role, sig.signed_on, sig.current]), record?.consent?.agreed,
  ]);
  const downloadButton = useRef<HTMLButtonElement>(null);
  const checked = checkStatus === "ready" || checkStatus === "needs_answers";
  const docs = listedDocuments(c);

  useEffect(() => {
    if (!download) return;
    // "Download draft" from the menu is the explicit request; "options" only brings this step forward.
    if (download === "draft") void ex.prepare(true);
    else downloadButton.current?.focus();
    location.replace("#/application?step=send");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [download]);

  // A stale or missing check, an officer determination and a professional hold are different next steps.
  const work = preparationGaps(c, ex.blocking);
  const holds: { tone: "warning" | "pending"; text: string; action?: { label: string; run: () => void } }[] = [];
  if (!officialReady) {
    if (checkStatus === "running") holds.push({ tone: "pending", text: checkNote || "Checking…" });
    else if (!checked) holds.push({
      tone: "warning",
      text: checkStatus === "unavailable" ? "The last check couldn’t finish." : checkStatus === "stale" ? "Changed since the last check." : "Not checked yet.",
      action: { label: checkStatus === "unavailable" ? "Try again" : "Check now", run: ex.runCheck },
    });
    const professional = professionalHoldReason(ex.blocking);
    if (professional && !work.officer.length && !work.checkNeeded.length && (!readOnly || checked)) holds.push({ tone: "warning", text: professional });
  }
  const route = professionalRouteNote(ex.blocking);
  const pack = extras.pack?.pack ?? null;
  const notices = pack?.notices.filter(n => n.surfaces.includes("export_header") || n.surfaces.includes("export_appendix")) ?? [];
  let shown = 0;

  return (
    <div className="aw-send">
      {/* The package includes the signatures, so it is drawn once they have loaded. */}
      {workspace.state.phase === "loading"
        ? <section className="aw-package-preview"><div className="aw-preview-empty" role="status">Preparing the package…</div></section>
        : <PackagePreview official={officialReady} versionKey={versionKey} zoom={zoom} />}

      <aside className="aw-send-panel" aria-label="Send">
        <section className="aw-card aw-flags" aria-labelledby="aw-flags-h">
          <h2 id="aw-flags-h">
            {total ? <>Officer would flag <span className="aw-count">{total}</span></> : <><Icon24 name="check" size={16} />Nothing to flag</>}
          </h2>
          {holds.map(h => (
            <p key={h.text} className="aw-hold">
              <Dot tone={h.tone} /><span>{h.text}</span>
              {h.action && <button type="button" className="cf-link-btn" disabled={ex.busy || checkStatus === "running"} onClick={h.action.run}>{h.action.label}</button>}
            </p>
          ))}
          {groups.map(g => {
            const rows = g.rows.filter(() => all || shown++ < SHOWN);
            if (!rows.length) return null;
            return (
              <div key={g.group} className="aw-flag-group">
                <h3>{GROUP_LABEL[g.group]}</h3>
                <ul>
                  {rows.map(r => (
                    <li key={r.key}>
                      <Dot tone={g.group === "officer" ? "pending" : "blocking"} />
                      <span className="aw-flag-text" title={r.all.join("\n")}>{r.label}</span>
                      {r.count > 1 && <span className="aw-times" aria-label={`${r.count} times`}>×{r.count}</span>}
                      {!readOnly && g.group !== "officer" && <a className="aw-fix" href={r.href} aria-label={`Fix: ${r.label}`}>Fix</a>}
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
          {!all && total > SHOWN && <button type="button" className="cf-link-btn" onClick={() => setAll(true)}>Show all {total}</button>}
          {!total && <p className="aw-fine">Administrative completeness only. Not a review of the design.</p>}
        </section>

        <section className="aw-card aw-package" aria-labelledby="aw-pack-h">
          <h2 id="aw-pack-h">In the package</h2>
          <ul>
            <li><Icon24 name="file" size={15} /><span>Variance form, Part 1</span></li>
            <li><Icon24 name="file" size={15} /><span>Appendix · your case</span></li>
            {docs.map(doc => {
              const binding = evidenceBinding(c.facts, doc.id);
              const who = valueText(factFor(c, `evidence.${doc.id}.responsible_party`)).trim();
              return (
                <li key={doc.id} className={binding ? "" : "is-missing"}>
                  <Icon24 name="clip" size={15} />
                  <span>{doc.title}{who && <span className="aw-meta"> · {who}</span>}</span>
                  {binding && engineId
                    ? <span className="aw-meta"><EvidenceFileLink caseId={engineId} fileId={binding.fileId} name="PDF" /></span>
                    : <span className="aw-missing-word">Not attached</span>}
                </li>
              );
            })}
          </ul>
        </section>

        <SubmitPanel key={applicationIdentity} sections={sections} beforeSubmit={workspace.flushHistory}
          signingReason={workspace.state.phase !== "ready" ? workspace.state.note : signing.length ? "Consent and signatures first." : ""} />

        <div className="aw-send-row">
          <button ref={downloadButton} type="button" className="cf-btn is-sm" disabled={ex.busy || Boolean(c.exampleId)} onClick={() => void ex.prepare(!officialReady)}>
            <Icon24 name="download" size={15} />{ex.busy ? "Preparing…" : officialReady ? "Download PDF" : "Download draft"}
          </button>
          <button type="button" className="cf-btn is-sm is-ghost" title="The answers and review record as text. Not the official form." disabled={ex.recordBusy} onClick={() => void ex.downloadRecord()}>
            {ex.recordBusy ? "Reading…" : "Text record"}
          </button>
        </div>
        {!officialReady && <p className="aw-fine">A draft is marked “not for submission” on every page.</p>}

        {(ex.exportAttempted || ex.stage !== "idle") && (
          <div className="aw-export-status" role="status">
            {ex.busy && <span className="cf-dot is-pending cf-pulse" aria-hidden="true" />}
            <p>{ex.statusText}</p>
            {ex.stage === "ready" && ex.file && <button type="button" className="cf-link-btn" onClick={ex.downloadAgain}>Download again</button>}
            {ex.stage === "ready" && ex.file?.notice && <Notices notices={[ex.file.notice]} />}
            {route && ex.stage === "blocked" && route !== ex.statusText && <p className="aw-fine">{route}</p>}
          </div>
        )}
        {ex.recordNote && <p className="aw-fine" role="status">{ex.recordNote}</p>}

        <EngineerCallout c={c} gaps={readOnly && !checked ? [] : gaps} readOnly={readOnly} />
        <ExpiryNotice expiresAt={app?.expires_at} />

        {(notices.length > 0 || (!pack && c.authority && engineId) || ex.tech || ex.reasons.length > 0) && (
          <details className="aw-more-details">
            <summary>Office notes and details</summary>
            {!pack && c.authority && engineId && (extras.failed.case
              ? <p className="aw-fine" role="status">Office notes didn’t load. <button type="button" className="cf-link-btn" onClick={retryExtras}>Try again</button></p>
              : !extras.pack && <p className="aw-fine" role="status">Loading office notes…</p>)}
            {notices.map(n => (
              <div key={n.id} className="aw-office-note">
                <h3>{n.heading}</h3>
                <p>{n.message}</p>
                {n.sources[0] && <a className="cf-inline-link" href={n.sources[0].url} target="_blank" rel="noreferrer">{n.sources[0].title}</a>}
              </div>
            ))}
            {(ex.tech || ex.reasons.length > 0) && (ex.reasons.length ? <ul>{ex.reasons.map(r => <li key={r}>{r}</li>)}</ul> : <p className="aw-fine">{ex.tech}</p>)}
          </details>
        )}
        <RetainedSourceFiles caseId={engineId} />
        <CompletenessNote />
      </aside>
    </div>
  );
}
