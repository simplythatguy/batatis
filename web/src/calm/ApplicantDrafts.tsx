import { Fragment, useEffect, useRef, useState } from "react";
import { engine, failureText, type EngineProcessField } from "../api/client";
import type { ApplicantDraft, DraftingRecord } from "../api/types.gen";
import { applicantDraftHref, draftPassages } from "../applicantDrafts";
import { EvidenceFileLink } from "../EvidenceFileLink";
import { localField } from "../intakeFields";
import { PROCESS_FACT } from "../model";
import { useRoute } from "../router";
import { useCase } from "../store";
import type { Case } from "../types";
import { useAccount } from "./account";
import { useCurrentApplication } from "./begin";
import { CIcon } from "./ui";
import "./ApplicantDrafts.css";

const STATUS = { draft: "Draft", accepted: "Accepted", rejected: "Rejected" } satisfies Record<ApplicantDraft["status"], string>;
const CLAIM_KIND = { fact: "", assumption: "Assumption", plan: "Planned work" } satisfies Record<ApplicantDraft["claims"][number]["kind"], string>;

function publicUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try { const url = new URL(value); return ["https:", "http:"].includes(url.protocol) ? url.href : null; }
  catch { return null; }
}

type SourceContext = { sources: DraftingRecord["sources"]; caseId: string | null; c: Pick<Case, "files" | "intake"> };

export function DraftSources({ claim, sources, caseId, c }: SourceContext & { claim: ApplicantDraft["claims"][number] }) {
  if (!claim.sources.length) return <p className="cf-draft-meta">No source excerpt supplied.</p>;
  return <details className="cf-draft-sources">
    <summary><CIcon name="doc" size={14} />Sources <span>{claim.sources.length}</span></summary>
    {claim.sources.map((reference, i) => {
      const source = sources.find(s => s.id === reference.source_id);
      const url = publicUrl(source?.url);
      const file = source && (c.intake?.record.files.find(f => f.file_id === source.ref)
        ?? c.files.find(f => f.engineId === source.ref));
      return <figure key={i}>
        <figcaption>
          {url ? <a href={url} target="_blank" rel="noreferrer">{source?.label || source?.ref}<CIcon name="external" size={12} /></a>
            : source?.label || source?.ref || `Unavailable source (${reference.source_id})`}
          {source?.page != null && ` · p. ${source.page}`}
          {file && source && caseId && <> · <EvidenceFileLink caseId={caseId} fileId={source.ref} name={file.name} /></>}
        </figcaption>
        <blockquote>{reference.quote}</blockquote>
      </figure>;
    })}
  </details>;
}

export function DraftClaim({ claim, prefix = "", ...context }: SourceContext & { claim: ApplicantDraft["claims"][number]; prefix?: string }) {
  const marker = claim.kind === "assumption" ? "Assumption:" : claim.kind === "plan" ? "Plan:" : "";
  const label = marker && claim.text.trimStart().startsWith(marker) ? "" : prefix.trim() || CLAIM_KIND[claim.kind];
  return <div className="cf-draft-claim">
    {label && <span className="cf-draft-kind">{label}</span>}
    <p>{claim.text}</p>
    <DraftSources claim={claim} {...context} />
  </div>;
}

export function DraftContent({ draft, ...context }: SourceContext & { draft: ApplicantDraft }) {
  const wording = draftPassages(draft);
  return <>
    <div className="cf-draft-wording">
      {wording ? <>
        {wording.passages.map(({ before, prefix, claim }, i) => <Fragment key={i}>
          {before.trim() && <p>{before}</p>}
          <DraftClaim claim={claim} prefix={prefix} {...context} />
        </Fragment>)}
        {wording.after.trim() && <p>{wording.after}</p>}
      </> : <>
        {draft.text && <p>{draft.text}</p>}
        {draft.claims.map((claim, i) => <DraftClaim key={i} claim={claim} {...context} />)}
      </>}
    </div>
    {draft.questions.length > 0 && <div className="cf-draft-questions">
      <h4>Still to answer</h4>
      <ul>{draft.questions.map((question, i) => <li key={i}>
        <span className="cf-draft-kind">{question.routed_to === "professional" ? "For your professional" : "For you"}</span>
        <p>{question.text}</p>
      </li>)}</ul>
    </div>}
  </>;
}

type Guidance = { kind: "idle" } | { kind: "loading" } | { kind: "ready"; fields: EngineProcessField[] } | { kind: "error"; message: string };

/** One disclosure retains reviewer guidance and the source-linked precedent structures. */
export function DraftGuidance({ field }: { field: string | null }) {
  const { engineId, applicationIdentity } = useCase();
  const [open, setOpen] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<Guidance>({ kind: "idle" });
  useEffect(() => {
    if (!open || !engineId) return;
    const ctl = new AbortController();
    setState({ kind: "loading" });
    void engine.processFields(engineId, ctl.signal).then(fields => {
      if (!ctl.signal.aborted) setState({ kind: "ready", fields });
    }, error => { if (!ctl.signal.aborted) setState({ kind: "error", message: failureText(error) }); });
    return () => ctl.abort();
  }, [open, engineId, applicationIdentity, attempt]);
  const fields = state.kind === "ready" ? state.fields.filter(f => !field?.startsWith("process.") || localField(`process.${f.id}`) === localField(field)) : [];
  return <details className="cf-draft-guidance" onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>Guidance and precedents</summary>
    {!engineId ? <p>Save your application to load the guidance.</p>
      : state.kind === "loading" ? <p role="status">Loading guidance…</p>
        : state.kind === "error" ? <p role="alert">{state.message} <button type="button" className="cf-link-btn" onClick={() => setAttempt(n => n + 1)}>Try again</button></p>
          : state.kind === "ready" && !fields.length ? <p>No guidance was returned for this field.</p>
            : fields.map(f => <div key={f.id}>
              <h4>{f.label}</h4><p>{f.prompt}</p>
              <ul>{f.reviewer_looks_for.map(line => <li key={line}>{line}</li>)}</ul>
              {f.citation && <p className="cf-draft-meta">{f.citation}</p>}
              {f.example && <>
                <p>{f.example.label}</p>
                <ul>{f.example.must_address.map(line => <li key={line}>{line}</li>)}</ul>
                {f.example.precedents.map((precedent, i) => {
                  const url = publicUrl(precedent.url);
                  return <div key={i}>
                    <p>{url ? <a href={url} target="_blank" rel="noreferrer">{precedent.title}</a> : precedent.title}</p>
                    <p className="cf-draft-meta">{[precedent.issuer, precedent.number, precedent.date, precedent.edition, `p. ${precedent.pdf_page}`].filter(Boolean).join(" · ")}</p>
                    <p>{precedent.structure}</p>
                  </div>;
                })}
                <p className="cf-draft-meta">Use the structure only. Check scope, status and edition; a precedent is not acceptance of this project.</p>
              </>}
            </div>)}
  </details>;
}

/** The deck offers this same writing panel without moving or replacing a manual answer card. */
export function ApplicantDraftLink({ field }: { field: string | null }) {
  if (!field) return null;
  return <a className="cf-link-btn cf-draft-entry" href={applicantDraftHref(field)}><CIcon name="doc" size={14} />Review a sourced draft</a>;
}

export function processDraftField(id: string): string | null {
  return Object.entries(PROCESS_FACT).find(([key]) => key === id)?.[1] ?? null;
}

/** One piece of writing at a time, in the existing Review stage. All writes belong to the store. */
export function ApplicantDrafts() {
  const { c, engineId, applicationIdentity, drafting, draftingStale, draftActivity, draftingError,
    generateApplicantDrafts, decideApplicantDraft, retryApplicantDrafts, submitting, saveStatus } = useCase();
  const { locked } = useCurrentApplication();
  const { phase: accountPhase } = useAccount();
  const route = useRoute();
  const focus = route.params.get("focus");
  const field = focus?.startsWith("draft:") ? focus.slice(6) : null;
  const [selected, setSelected] = useState("");
  const selectionHistory = useRef<{ scope: string; ids: Set<string> }>({ scope: "", ids: new Set() });
  const panel = useRef<HTMLElement>(null);
  const picker = useRef<HTMLDetailsElement>(null);
  const drafts = drafting?.drafts ?? [];
  const scope = JSON.stringify([applicationIdentity, field]);
  const preferred = drafts.find(d => field && d.field === field && d.status === "draft")
    ?? drafts.find(d => field && d.field === field)
    ?? drafts.find(d => d.status === "draft") ?? drafts[0];
  const choice = (selectionHistory.current.scope === scope && drafts.find(d => d.id === selected)) || preferred;
  useEffect(() => {
    const previous = selectionHistory.current;
    const added = drafts.find(d => d.status === "draft" && !previous.ids.has(d.id) && (!field || d.field === field))
      ?? drafts.find(d => d.status === "draft" && !previous.ids.has(d.id));
    setSelected(id => previous.scope !== scope ? preferred?.id ?? "" : added?.id ?? (drafts.some(d => d.id === id) ? id : preferred?.id ?? ""));
    selectionHistory.current = { scope, ids: new Set(drafts.map(d => d.id)) };
  }, [scope, drafting]);
  useEffect(() => {
    if (field) { panel.current?.scrollIntoView({ block: "start" }); panel.current?.focus({ preventScroll: true }); }
  }, [applicationIdentity, field]);
  const busy = draftActivity.kind !== "idle";
  const disabled = locked || submitting || busy || saveStatus === "gone" || accountPhase !== "signed-in";
  const reason = locked || submitting ? "This application is read-only while sent or submitting."
    : saveStatus === "gone" ? "This application was deleted or expired."
      : !busy && accountPhase === "probing" ? "Checking sign-in…"
        : !busy && accountPhase !== "signed-in" ? <><a className="cf-inline-link" href="#/signin">Sign in</a> to draft or decide application wording.</>
          : !c.description.trim() ? "Describe your project before drafting." : "";
  return <section ref={panel} tabIndex={-1} className="cf-applicant-drafts" aria-labelledby="cf-drafts-heading" aria-busy={busy}>
    <h2 id="cf-drafts-heading">Your application wording</h2>
    <p className="cf-draft-meta">Review and own the wording you accept. Professional analysis, calculations and seals come from your engineer or architect.</p>
    <div className="cf-row-actions">
      <button type="button" className="cf-btn is-sm" disabled={disabled || !c.description.trim()} onClick={() => { if (!disabled && c.description.trim()) void generateApplicantDrafts(); }}>
        {draftActivity.kind === "generating" ? "Drafting…" : "Draft my application"}
      </button>
      {busy && <span className="cf-draft-meta" role="status">{draftActivity.kind === "generating" ? "Preparing source-linked writing. This can take a few minutes." : "Saving your decision…"}</span>}
    </div>
    {reason && <p className="cf-draft-meta">{reason}</p>}
    {draftingError && <p className="cf-draft-error" role="alert">{draftingError}{!reason && <button type="button" className="cf-link-btn" disabled={disabled} onClick={() => { if (!disabled) void retryApplicantDrafts(); }}>Try again</button>}</p>}
    {draftingStale && <p className="cf-draft-warning" role="status">Previous or unverified input · Generate fresh drafts before accepting or rejecting.</p>}
    {drafting?.notices.map((notice, i) => <p className="cf-draft-meta" key={i}>{notice}</p>)}
    {!drafting && !busy && <p className="cf-draft-meta">Drafts stay separate from your answers until you accept them.</p>}
    {drafting && !drafts.length && <p role="status">No writing was returned. Review the generation notes, then try again.</p>}
    {choice && drafting && <>
      <details className="cf-draft-picker" ref={picker}>
        <summary>{choice.title}<span className="cf-draft-status">{STATUS[choice.status]}</span><CIcon name="chev" size={14} /></summary>
        <div role="group" aria-label="Choose application wording">
          {drafts.map(draft => <button type="button" key={draft.id} aria-pressed={draft.id === choice.id} onClick={() => { setSelected(draft.id); if (picker.current) picker.current.open = false; }}>
            <span>{draft.title}</span><span className="cf-draft-status">{STATUS[draft.status]}</span>
          </button>)}
        </div>
      </details>
      <article key={choice.id} aria-label={choice.title}>
        <DraftContent draft={choice} sources={drafting.sources} caseId={engineId} c={c} />
        {choice.status === "draft" ? <>
          <p className="cf-draft-meta">{choice.text.trim() ? "Accepting saves this wording as your answer. Open questions and professional work stay open." : "No wording to accept. Answer the questions, then draft again."}</p>
          <div className="cf-row-actions">
            <button type="button" className="cf-btn is-primary is-sm" disabled={disabled || draftingStale || !choice.text.trim()} onClick={() => { if (!disabled && !draftingStale && choice.text.trim()) void decideApplicantDraft(choice.id, "accept"); }}>Accept draft</button>
            <button type="button" className="cf-btn is-ghost is-sm" disabled={disabled || draftingStale} onClick={() => { if (!disabled && !draftingStale) void decideApplicantDraft(choice.id, "reject"); }}>Reject</button>
          </div>
        </> : <p className="cf-draft-meta" role="status">{choice.status === "accepted" ? "Accepted by you. Original wording and sources are retained." : "Rejected. No answer was added."}</p>}
      </article>
    </>}
    <DraftGuidance key={applicationIdentity} field={choice?.field ?? field} />
  </section>;
}
