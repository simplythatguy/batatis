import { useRef, useState } from "react";
import type { WordingDraft } from "../api/types.gen";
import { statementDrafts } from "../applicantDrafts";
import { PROCESS_FIELDS } from "../model";
import { useCase } from "../store";
import type { ProcessFieldId } from "../types";
import { DraftContent } from "./ApplicantDrafts";
import { useCurrentApplication } from "./begin";
import { Icon24 } from "./icons";
import { CIcon } from "./ui";
import "./ApplicantDrafts.css";

type Run = { done: number; total: number; stopped: boolean };

const HELD = "Accept or reject the drafts first.";
const ADDED = new Map<string, ReadonlySet<string>>();

/** A draft that still waits on the applicant: wording to accept, for a statement not yet written. */
const waiting = (draft: WordingDraft | undefined, written: string): WordingDraft | null =>
  draft?.status === "draft" && draft.text.trim() && !written.trim() ? draft : null;

/**
 * The six variance statements on one screen. Batatis drafts them in one request; each is accepted,
 * rejected or written here, and Accept all decides them one at a time. Writes belong to the store.
 */
export function StatementReview() {
  const { c, dispatch, engineId, drafting, draftingStale, draftActivity, draftingError, generateApplicantDrafts, decideApplicantDraft } = useCase();
  const { locked } = useCurrentApplication();
  const [run, setRun] = useState<Run | null>(null);
  const [writing, setWriting] = useState<ProcessFieldId | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  // Gap answers already added, kept per application so leaving the card and coming back can't add one twice.
  const [added, setAdded] = useState<ReadonlySet<string>>(() => ADDED.get(engineId ?? "") ?? new Set());
  // Accept all awaits each decision; the latest store function holds the latest draft record.
  const decide = useRef(decideApplicantDraft);
  decide.current = decideApplicantDraft;
  const drafts = statementDrafts(drafting);
  const generating = draftActivity.kind === "generating";
  const running = run !== null && !run.stopped;
  const busy = draftActivity.kind !== "idle" || running;
  const pending = PROCESS_FIELDS.flatMap((p) => { const d = waiting(drafts.get(p.id), c.process[p.id]); return d ? [d] : []; });
  const open = PROCESS_FIELDS.filter((p) => !c.process[p.id].trim()).length;
  const canDecide = !locked && !busy && !draftingStale;
  // Typing any statement changes what the drafts were written from, so every pending draft would go stale.
  const held = (pending.length > 0 && !draftingStale) || busy;

  async function acceptAll() {
    const ids = pending.map((d) => d.id);
    setRun({ done: 0, total: ids.length, stopped: false });
    for (const id of ids) {
      // A refusal (already answered, nothing to accept, changed input) stops here; the rest stay waiting.
      if (!(await decide.current(id, "accept"))) { setRun((r) => r && { ...r, stopped: true }); return; }
      setRun((r) => r && { ...r, done: r.done + 1 });
    }
    setRun(null);
  }
  const setText = (id: ProcessFieldId, value: string) => dispatch({ type: "setProcess", field: id, value });
  /** A gap answer joins the statement it belongs to, after the wording already there. */
  function append(id: ProcessFieldId, key: string) {
    const answer = answers[key]?.trim();
    if (!answer) return;
    const current = c.process[id].trimEnd();
    // After a reload the added list is gone; an answer the statement already holds is not added again.
    if (!current.includes(answer)) setText(id, current ? `${current}\n\n${answer}` : answer);
    setAdded((s) => { const next = new Set(s).add(key); ADDED.set(engineId ?? "", next); return next; });
  }

  const primary = drafts.size === 0 && !generating && open > 0 ? { label: "Draft my case", icon: true, act: () => void generateApplicantDrafts(), off: locked || busy || !c.description.trim() }
    : draftingStale && open > 0 && !generating ? { label: "Draft again", icon: true, act: () => void generateApplicantDrafts(), off: locked || busy }
      : pending.length > 0 ? { label: "Accept all", icon: false, act: () => void acceptAll(), off: !canDecide }
        : null;

  return <div className="cf-statements" aria-busy={busy}>
    <ul className="cf-statement-list">{PROCESS_FIELDS.map((p) => {
      const draft = drafts.get(p.id);
      const text = c.process[p.id];
      const written = Boolean(text.trim());
      const asks = waiting(draft, text);
      const editing = writing === p.id && !held;
      const unchanged = written && draft?.status === "accepted" && draft.text === text;
      const state = written ? "Written" : asks ? "Draft to review" : generating ? "Drafting" : draft?.status === "rejected" ? "Rejected" : "Not written";
      const preview = written ? text : asks?.text ?? "";
      const gaps = draft?.questions ?? [];
      return <li key={p.id}>
        <details>
          <summary>
            <span className="cf-statement-mark" aria-hidden="true">
              {written ? <CIcon name="check" size={14} /> : <span className={`cf-dot${asks ? " is-warning" : ""}${generating && !draft ? " cf-pulse" : ""}`} />}
            </span>
            <span className="cf-statement-label">{p.label}</span>
            <span className="cf-statement-preview">{preview}</span>
            <span className="cf-sr">{state}</span>
            <CIcon name="chev" size={14} />
          </summary>
          <div className="cf-statement-body">
            {asks ? <DraftContent draft={asks} sources={drafting?.sources ?? []} caseId={engineId} c={c} />
              : unchanged && draft ? <DraftContent draft={{ ...draft, questions: [] }} sources={drafting?.sources ?? []} caseId={engineId} c={c} />
                : written && !editing ? <p className="cf-statement-text">{text}</p> : null}
            {editing && <textarea className="cf-uline is-area" rows={3} aria-label={p.label} value={text} onChange={(e) => setText(p.id, e.target.value)} placeholder="In your own words…" />}
            {!asks && gaps.length > 0 && <ul className="cf-statement-gaps">{gaps.map((q, i) => {
              const key = `${draft!.id}:${i}`;
              return <li key={key}>
                {q.routed_to === "professional"
                  ? <p><span className="cf-draft-kind"><Icon24 name="compose" size={13} />For your professional</span>{q.text}</p>
                  : added.has(key) ? <p><span className="cf-draft-kind"><CIcon name="check" size={12} />Added</span>{q.text}</p>
                    : <label>
                      <span className="cf-draft-kind">{q.text}</span>
                      <span className="cf-statement-answer">
                        <input className="cf-uline" value={answers[key] ?? ""} disabled={locked || held} title={held ? HELD : undefined} onChange={(e) => setAnswers((a) => ({ ...a, [key]: e.target.value }))} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); if (!held) append(p.id, key); } }} placeholder="Your answer, in a sentence" />
                        <button type="button" className="cf-btn is-sm" disabled={locked || held || !answers[key]?.trim()} onClick={() => append(p.id, key)}>Add</button>
                      </span>
                    </label>}
              </li>;
            })}</ul>}
            <div className="cf-row-actions">
              {asks ? <>
                <button type="button" className="cf-btn is-sm" disabled={!canDecide} onClick={() => { setRun(null); void decide.current(asks.id, "accept"); }}><CIcon name="check" size={14} />Accept</button>
                <button type="button" className="cf-btn is-ghost is-sm" disabled={!canDecide} onClick={() => { setRun(null); void decide.current(asks.id, "reject"); }}>Reject</button>
              </> : <button type="button" className="cf-link-btn" disabled={locked || held} title={held ? HELD : undefined} aria-expanded={editing} onClick={() => setWriting((w) => w === p.id ? null : p.id)}>
                {editing ? "Done" : written ? "Edit" : "Write it"}
              </button>}
            </div>
          </div>
        </details>
      </li>;
    })}</ul>
    {generating && <p className="cf-note" role="status"><span className="cf-dot is-pending cf-pulse" aria-hidden="true" />Drafting your case. This can take a few minutes.</p>}
    {running && <p className="cf-note" role="status"><span className="cf-dot is-pending cf-pulse" aria-hidden="true" />Accepting {run.done + 1} of {run.total}…</p>}
    {held && !busy && <p className="cf-note">{HELD}</p>}
    {draftingStale && !generating && <p className="cf-note" role="status"><span className="cf-dot is-warning" aria-hidden="true" />Your answers changed since these drafts.</p>}
    {(run?.stopped || draftingError) && <p className="cf-note" role="alert"><span className="cf-dot is-blocking" aria-hidden="true" />
      {run?.stopped && `Accepted ${run.done} of ${run.total}. The rest are still waiting. `}{draftingError}
    </p>}
    {primary && <div className="cf-row-actions">
      <button type="button" className="cf-btn is-primary" disabled={primary.off} onClick={() => { if (!primary.off) primary.act(); }}>
        {primary.icon && <Icon24 name="spark" size={15} />}{primary.label}
      </button>
    </div>}
  </div>;
}
