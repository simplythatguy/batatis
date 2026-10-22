import { useEffect, useRef, useState } from "react";
import { accounts, submitBlockers, type ApplicationSummary } from "../api/accounts";
import { EngineError } from "../api/client";
import { Notices } from "../components";
import { UNSIGNED_LINE, isProfessionalHold, professionalRouteNote } from "../humanReview";
import { useApplicationExport } from "../screens/Application";
import { useCase } from "../store";
import { patchApplication, refreshApplications, useAccount } from "./account";
import { authorityName, readOnlyStatus } from "./applications";
import { useCurrentApplication } from "./begin";
import { gapKey } from "./deck";
import { calmHref } from "./routes";
import { EngineerCallout } from "./Review";
import { FormPlaceholder, FormViewer } from "./FormViewer";
import { CIcon, Dot, Eyebrow } from "./ui";
import { retryExtras, useCaseExtras } from "./caseExtras";

const when = (iso: string | null) => {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
};

const STATUS_TEXT: Record<string, string> = {
  submitted: "Waiting for an officer to pick it up.",
  in_review: "An officer is reviewing it.",
};

/**
 * Submit to the reviewing authority (signed in only). Gated on the shared blocking gaps; a 409
 * shows the engine's own list. After submitting the application is read-only with its status.
 */
function SubmitPanel() {
  const { c, gaps, engineId, saveStatus } = useCase();
  const account = useAccount();
  const { app } = useCurrentApplication();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [blockers, setBlockers] = useState<{ id: string; field: string | null; label: string }[]>([]);
  if (account.phase !== "signed-in") {
    return account.phase === "signed-out"
      ? <p className="cf-faint cf-small cf-submit-note">Submitting to the authority needs an account. <a className="cf-inline-link" href="#/signin">Sign in</a>, or download the PDF.</p>
      : <p className="cf-faint cf-small cf-submit-note">Submitting isn’t available on this server. You can still download the PDF.</p>;
  }
  if (!engineId || !app) {
    return <p className="cf-faint cf-small cf-submit-note" role="status">{saveStatus === "failed" || saveStatus === "gone" ? "Submit becomes available once this application is saved." : "Saving your application…"}</p>;
  }
  const where = authorityName(app.authority || c.authority) || "";
  if (app.status !== "draft" && app.status !== "returned") {
    return <SubmittedStatus app={app} where={where} />;
  }
  // Items routed to the officer (whether a registered professional is required) travel with the
  // application: they close the official PDF, not submission. The engine's submit check agrees.
  const blocking = gaps.filter((g) => g.severity === "blocking" && !isProfessionalHold(g));
  const routed = gaps.some((g) => g.severity === "blocking" && isProfessionalHold(g));
  const reason = !c.authority ? "Choose Calgary or Edmonton as the reviewing authority before submitting. Not sure yet keeps it open." : blocking.length ? `${blocking.length} required ${blocking.length === 1 ? "item is" : "items are"} missing.` : "";

  async function submit() {
    if (reason || busy || !app) return;
    setBusy(true);
    setError("");
    setBlockers([]);
    try {
      await accounts.submit(app.id);
      patchApplication(app.id, { status: "submitted", submitted_at: new Date().toISOString(), unread_messages: 0 });
      void refreshApplications();
    } catch (e) {
      const list = submitBlockers(e);
      if (list.length) setBlockers(list);
      else setError(e instanceof EngineError ? e.detail : "The application was not submitted.");
    } finally {
      setBusy(false);
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
          {reason} <a className="cf-inline-link" href={!c.authority ? "#/questions?focus=authority" : "#/review"}>{!c.authority ? "Pick one" : "See them"}</a>
        </p>
      )}
      {!reason && routed && <p className="cf-faint cf-small">The professional question goes to the officer with your application.</p>}
      {blockers.length > 0 && (
        <div role="status">
          <p className="cf-small">The authority’s check found {blockers.length} required {blockers.length === 1 ? "item" : "items"} still missing:</p>
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
  return (
    <div className="cf-submitted" role="status">
      <p className="cf-submitted-h">
        <Dot tone={s.tone} />
        {s.heading}
      </p>
      <p className="cf-faint cf-small">
        {app.submitted_at ? `Submitted ${when(app.submitted_at)}. ` : ""}
        {app.reviewer?.name && app.status === "in_review" ? `${app.reviewer.name} is reviewing it. ` : STATUS_TEXT[app.status] ? `${STATUS_TEXT[app.status]} ` : ""}
        {s.note}
      </p>
    </div>
  );
}

/** Before an application exists: the empty form, so it is clear what will be filled in. */
function ApplicationEmpty() {
  return (
    <div className="cf-doc">
      <FormPlaceholder />
      <aside className="cf-glass cf-side" aria-label="Download">
        <Eyebrow plain>Status</Eyebrow>
        <div className="cf-side-big">Nothing filled in yet.<br /><span className="cf-muted">Every section is still missing.</span></div>
        <p className="cf-faint cf-small">Describe what you’re building. Batatis fills in what it can and asks you for the rest.</p>
        <a className="cf-btn is-primary is-center" href="#/">Describe your project</a>
        <p className="cf-faint cf-small cf-disclaimer">This checks administrative completeness. It does not say the design complies or is safe.</p>
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
  const { locked } = useCurrentApplication();
  const signedIn = account.phase === "signed-in";
  const { c, gaps, checkStatus, checkNote, completenessRecord, engineId, factsEpoch } = useCase();
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
  const reasons: { tone: "blocking" | "warning" | "pending"; text: string; action?: { label: string; run: () => void } | { label: string; href: string } }[] = [];
  if (!ex.officialReady) {
    if (checkStatus === "running") reasons.push({ tone: "pending", text: checkNote || "Checking your draft…" });
    else if (!checked) reasons.push({ tone: "warning", text: checkStatus === "unavailable" ? "The last check couldn’t finish." : checkStatus === "stale" ? "Your draft changed since the last check." : "Your application hasn’t been checked yet.", action: { label: checkStatus === "unavailable" ? "Try again" : "Check now", run: ex.runCheck } });
    if (route) reasons.push({ tone: "warning", text: "Waiting on a registered professional’s confirmation." });
  }

  // Each blocker links to the card that fixes it (the same shared gap list as Review and the deck).
  const blockers = ex.officialReady ? [] : ex.blocking.filter((g) => !isProfessionalHold(g));
  /** Link an export blocker to its deck card, falling back to the gap’s existing destination. */
  const fixHref = (g: (typeof gaps)[number]) => {
    const key = gapKey(c, g);
    return key ? `#/questions?focus=${encodeURIComponent(key)}` : calmHref(g.href);
  };
  const pack = extras.pack?.pack ?? null;
  const exportNotices = pack?.notices.filter((n) => n.surfaces.includes("export_header") || n.surfaces.includes("export_appendix")) ?? [];
  const filled = pack?.forms.find((f) => f.export === "supported");

  const headline = ex.officialReady ? "Ready for the official PDF." : "You can download a draft.";
  const sub = ex.officialReady ? "Nothing required is missing." : "Official PDF on hold.";
  const showStatus = ex.exportAttempted || ex.stage !== "idle";

  return (
    <div className="cf-doc">
      {/* The actual PDF the engine fills, not a drawing of it. */}
      <FormViewer locked={locked} />
      <aside className="cf-glass cf-side" aria-label="Download">
        <Eyebrow plain>Status</Eyebrow>
        {!locked && <div className="cf-side-big">{headline}<br /><span className="cf-muted">{sub}</span></div>}
        <SubmitPanel />
        {reasons.length > 0 && !locked && (
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
        <button type="button" className="cf-btn is-center" disabled={ex.busy || !ex.officialReady} data-requires-no-blocking-gaps={ex.blocking.length ? "true" : undefined} onClick={() => void ex.prepare(false)}>
          {ex.stage === "preparing" && !ex.draftIntent ? "Preparing PDF…" : "Official PDF"}
        </button>
        {!ex.officialReady && <p className="cf-faint cf-small">The Official PDF unlocks after a current check finds no required items. Drafts can be incomplete.</p>}
        {blockers.length > 0 && !locked && (
          <div className="cf-side-blockers">
            <p className="cf-small">Still needed for the Official PDF:</p>
            <ul className="cf-rows is-compact">
              {blockers.slice(0, 5).map((g) => (
                <li key={g.id} className="cf-row">
                  <Dot tone="blocking" />
                  <span className="cf-row-text">{g.label}</span>
                  <a className="cf-row-go" href={fixHref(g)}>Fix <CIcon name="arrow" size={13} /></a>
                </li>
              ))}
            </ul>
            {blockers.length > 5 && <p className="cf-faint cf-small">And {blockers.length - 5} more. <a className="cf-inline-link" href="#/review">See all on Review</a></p>}
          </div>
        )}
        {filled && <p className="cf-faint cf-small">Batatis fills {filled.title}{filled.version ? ` (${filled.version})` : ""}.</p>}
        {!pack && c.authority && engineId && (
          extras.failed.case
            ? <p className="cf-note cf-small" role="status"><Dot tone="warning" />The office’s notes for the download didn’t load. <button type="button" className="cf-link-btn" onClick={retryExtras}>Try again</button></p>
            : extras.pack
              // Loaded, and Batatis has no notes for this office: say so, and what still applies.
              ? <p className="cf-faint cf-small" role="status">Batatis has no local notes for this office yet. The download uses the standard variance form; ask the office how they want it submitted.</p>
              : <p className="cf-faint cf-small" role="status">Loading the office’s notes for the download…</p>
        )}
        {exportNotices.map((n) => (
          <div key={n.id} className="cf-side-notice" role="note">
            <p className="cf-side-notice-h">{n.heading}</p>
            <p>{n.message}</p>
            {n.sources[0] && <p><a className="cf-inline-link" href={n.sources[0].url} target="_blank" rel="noreferrer">{n.sources[0].title}</a></p>}
          </div>
        ))}
        <button type="button" className="cf-btn is-ghost is-sm is-center" onClick={ex.downloadRecord}>Download a text record</button>

        {showStatus && (
          <div className="cf-side-status" role="status">
            {ex.busy && <span className="cf-dot is-pending cf-pulse" aria-hidden="true" />}
            <p>{ex.statusText}</p>
            {ex.stage === "ready" && ex.file && (
              <>
                <p className="cf-faint">Download started: {ex.file.name}. {ex.file.draft ? "This draft may have missing or unconfirmed information." : UNSIGNED_LINE}</p>
                <button type="button" className="cf-btn is-sm" onClick={ex.downloadAgain}>Download again</button>
              </>
            )}
            {ex.stage === "ready" && ex.file?.notice && <Notices notices={[ex.file.notice]} />}
          </div>
        )}
        {route && ex.stage === "blocked" && <p className="cf-faint cf-small">{route}</p>}
        {(ex.tech || ex.reasons.length > 0) && (
          <details className="cf-tech">
            <summary>Technical detail</summary>
            {ex.reasons.length > 0 ? <ul>{ex.reasons.map((r) => <li key={r}>{r}</li>)}</ul> : <p>{ex.tech}</p>}
          </details>
        )}
        {completenessRecord && <p className="cf-faint cf-small">Record: {completenessRecord.label}. {completenessRecord.note}</p>}
        <EngineerCallout c={c} gaps={gaps} />
        <p className="cf-faint cf-small cf-disclaimer">This checks administrative completeness. It does not say the design complies or is safe.</p>
      </aside>
    </div>
  );
}
