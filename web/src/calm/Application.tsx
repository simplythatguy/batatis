import { useEffect, useRef, useState } from "react";
import { accounts, submitBlockers, type ApplicationSummary } from "../api/accounts";
import { EngineError } from "../api/client";
import { Notices } from "../components";
import { AUTHORITIES, CODE_EDITION } from "../config";
import { UNSIGNED_LINE, professionalRouteNote } from "../humanReview";
import { DETAIL_FIELDS, PROCESS_FIELDS, displayValue, factFor, valueText } from "../model";
import { useApplicationExport } from "../screens/Application";
import { useCase } from "../store";
import type { Case, SectionCRow } from "../types";
import { patchApplication, refreshApplications, useAccount } from "./account";
import { authorityName } from "./applications";
import { useCurrentApplication } from "./begin";
import { gapKey } from "./deck";
import { calmHref } from "./routes";
import { EngineerCallout } from "./Review";
import { CIcon, Dot, Eyebrow } from "./ui";

function Missing() {
  return <span className="cf-sheet-missing"><span className="cf-sheet-dot" aria-hidden="true" />— <em>missing</em></span>;
}

function Value({ c, id }: { c: Case; id: string }) {
  const def = DETAIL_FIELDS.find((d) => d.id === id)!;
  const fact = factFor(c, id);
  if (!valueText(fact).trim()) return def.required ? <Missing /> : <span className="cf-sheet-none">—</span>;
  return (
    <span>
      {displayValue(fact!)}
      {fact!.status === "unconfirmed" && <span className="cf-sheet-flag"> · needs your check</span>}
    </span>
  );
}

function codes(row: SectionCRow) {
  const objectives = [...new Set(row.pairs.flatMap((p) => p.objectives))];
  const functions = [...new Set(row.pairs.flatMap((p) => p.functions))];
  if (!objectives.length && !functions.length) return "No row in the attribution table";
  return `Objectives ${objectives.join(", ") || "—"} · Functions ${functions.join(", ") || "—"}`;
}

function documents(c: Case): string[] {
  const titles = new Map<string, string>();
  for (const f of c.facts) {
    const m = /^evidence\.([^.]+)\.title$/.exec(f.field);
    if (m && typeof f.value === "string" && f.value.trim() && !c.unscopedEvidence?.includes(m[1])) titles.set(m[1], f.value.trim());
  }
  return [...titles.values()];
}

/** Part 1, Sections A–D, from the same case values the PDF is generated from. */
function Sheet({ c }: { c: Case }) {
  const kv = (ids: string[]) => ids.map((id) => {
    const def = DETAIL_FIELDS.find((d) => d.id === id)!;
    return [<span key={`${id}-k`}>{def.label}</span>, <Value key={`${id}-v`} c={c} id={id} />];
  });
  const departures = c.sectionC.filter((r) => c.candidates.find((a) => a.id === r.candidateId)?.answer === "yes");
  const otherRefs = c.sectionC.length - departures.length;
  const role = factFor(c, "professional.role");
  const registration = factFor(c, "professional.registration_number");
  const docs = documents(c);
  const authority = AUTHORITIES.find((a) => a.id === c.authority)?.name;
  return (
    <article className="cf-sheet" aria-label="Application preview">
      <h2>Safety Codes Variance — Part 1</h2>
      <div className="cf-sheet-sub">{CODE_EDITION} · Draft preview</div>

      <h4>A · Applicant</h4>
      <div className="cf-sheet-kv">{kv(["owner", "representative", "mailingAddress", "date"])}</div>

      <h4>B · Project</h4>
      <div className="cf-sheet-kv">
        <span>Reviewing authority</span>
        {authority ? <span>{authority}</span> : <Missing />}
        {kv(["scope", "permit", "municipalAddress", "legalDescription"])}
      </div>
      <p className="cf-sheet-label">Proposed alternative</p>
      <p className="cf-sheet-p">{valueText(factFor(c, "alternative")).trim() || <Missing />}</p>

      <h4>C · Code references</h4>
      {departures.length ? (
        departures.map((r) => (
          <p key={r.provision} className="cf-sheet-p">
            <span className="cf-sheet-ref">{r.provision}</span> {codes(r)}
          </p>
        ))
      ) : (
        <p className="cf-sheet-p"><Missing /> No departure from a looked-up sentence confirmed yet.</p>
      )}
      {otherRefs > 0 && <p className="cf-sheet-note">{otherRefs} other looked-up {otherRefs === 1 ? "sentence is" : "sentences are"} not marked as a departure.</p>}

      <h4>Alternative path · written by the applicant</h4>
      <div className="cf-sheet-kv is-wide">
        {PROCESS_FIELDS.map((p) => [
          <span key={`${p.id}-k`}>{p.label}</span>,
          <span key={`${p.id}-v`}>{c.process[p.id].trim() || <Missing />}</span>,
        ])}
      </div>

      <h4>D · Supporting information</h4>
      <div className="cf-sheet-kv">
        <span>Registered professional</span>
        {role && valueText(role) ? <span>{displayValue(role)}{role.status === "unconfirmed" ? " · routed to the officer" : ""}</span> : <Missing />}
        <span>Registration or seal</span>
        {registration && valueText(registration) ? <span>{displayValue(registration)}</span> : <span className="cf-sheet-none">—</span>}
        <span>Documents listed</span>
        {docs.length ? <span>{docs.join("; ")}</span> : <Missing />}
      </div>
      <p className="cf-sheet-note">Professional evidence is provided by the applicant’s registered professional. Batatis does not write it.</p>
    </article>
  );
}

const when = (iso: string | null) => {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
};

const STATUS_TEXT: Record<string, string> = {
  submitted: "Waiting for an officer to pick it up.",
  in_review: "An officer is reviewing it.",
  accepted: "Accepted as administratively complete. This is not a finding that the design complies or is safe.",
  withdrawn: "Withdrawn.",
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
    return <p className="cf-faint cf-small cf-submit-note">Submitting to the authority needs an account. You can still download the PDF.</p>;
  }
  if (!engineId || !app) {
    return <p className="cf-faint cf-small cf-submit-note" role="status">{saveStatus === "failed" || saveStatus === "gone" ? "Submit becomes available once this application is saved." : "Saving your application…"}</p>;
  }
  const where = authorityName(app.authority || c.authority) || "";
  if (app.status !== "draft" && app.status !== "returned") {
    return <SubmittedStatus app={app} where={where} />;
  }
  const blocking = gaps.filter((g) => g.severity === "blocking");
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
  return (
    <div className="cf-submitted" role="status">
      <p className="cf-submitted-h">
        <Dot tone={app.status === "accepted" ? "done" : "warning"} />
        {app.status === "accepted" ? `Accepted by ${where || "the authority"}` : `Sent to ${where || "the authority"}`}
      </p>
      <p className="cf-faint cf-small">
        {app.submitted_at ? `Submitted ${when(app.submitted_at)}. ` : ""}
        {app.reviewer?.name && app.status === "in_review" ? `${app.reviewer.name} is reviewing it. ` : STATUS_TEXT[app.status] ? `${STATUS_TEXT[app.status]} ` : ""}
        {app.status !== "accepted" && "Read-only until the officer returns it."}
      </p>
    </div>
  );
}

/** Before an application exists: the empty form, so it is clear what will be filled in. */
function ApplicationEmpty() {
  const { c } = useCase();
  return (
    <div className="cf-doc">
      <div className="cf-sheet-pane">
        <Sheet c={c} />
      </div>
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

export function Application({ download }: { download: "" | "options" | "draft" }) {
  const { phase } = useCase();
  return phase === "case" ? <CaseApplication download={download} /> : <ApplicationEmpty />;
}

function CaseApplication({ download }: { download: "" | "options" | "draft" }) {
  const account = useAccount();
  const { locked } = useCurrentApplication();
  const signedIn = account.phase === "signed-in";
  const { c, gaps, checkStatus, checkNote, completenessRecord } = useCase();
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
    if (ex.blocking.length) reasons.push({ tone: "blocking", text: `${ex.blocking.length} required ${ex.blocking.length === 1 ? "item is" : "items are"} missing.`, action: { label: "See them", href: "#/review" } });
    if (route) reasons.push({ tone: "warning", text: "Waiting on a registered professional’s confirmation." });
  }

  const headline = ex.officialReady ? "Ready for the official PDF." : "You can download a draft.";
  const sub = ex.officialReady ? "Nothing required is missing." : "Official PDF on hold.";
  const showStatus = ex.exportAttempted || ex.stage !== "idle";

  return (
    <div className="cf-doc">
      <div className="cf-sheet-pane">
        <Sheet c={c} />
      </div>
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
        {!ex.officialReady && <p className="cf-faint cf-small">The official PDF unlocks after a current check finds no required items. Drafts can be incomplete.</p>}
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
