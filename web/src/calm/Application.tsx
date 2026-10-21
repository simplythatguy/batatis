import { useEffect, useRef } from "react";
import { Notices } from "../components";
import { AUTHORITIES, CODE_EDITION } from "../config";
import { UNSIGNED_LINE, professionalRouteNote } from "../humanReview";
import { DETAIL_FIELDS, PROCESS_FIELDS, displayValue, factFor, valueText } from "../model";
import { useApplicationExport } from "../screens/Application";
import { useCase } from "../store";
import type { Case, SectionCRow } from "../types";
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

export function Application({ download }: { download: "" | "options" | "draft" }) {
  const { c, gaps, checkStatus, checkNote, checkDetail, completenessRecord } = useCase();
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
        <div className="cf-side-big">{headline}<br /><span className="cf-muted">{sub}</span></div>
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
        <button ref={draftBtn} type="button" className="cf-btn is-primary is-center" disabled={ex.busy || Boolean(c.exampleId)} onClick={() => void ex.prepare(true)}>
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
        {(ex.tech || ex.reasons.length > 0 || (checkStatus === "unavailable" && checkDetail)) && (
          <details className="cf-tech">
            <summary>Technical detail</summary>
            {ex.reasons.length > 0 ? <ul>{ex.reasons.map((r) => <li key={r}>{r}</li>)}</ul> : <p>{ex.tech || checkDetail}</p>}
          </details>
        )}
        {completenessRecord && <p className="cf-faint cf-small">Record: {completenessRecord.label}. {completenessRecord.note}</p>}
        <EngineerCallout c={c} gaps={gaps} />
        <p className="cf-faint cf-small cf-disclaimer">This checks administrative completeness. It does not say the design complies or is safe.</p>
      </aside>
    </div>
  );
}
