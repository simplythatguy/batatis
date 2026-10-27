/**
 * One finding at a time, in the applicant's question-deck layout: the field, a short title, the
 * applicant's own words with every source one click away, and one call (Ask for it or Dismiss).
 * The check's own explanation sits behind "Why". Keys: 1 and 2 choose, Enter goes on.
 */
import { useEffect, useId, useState } from "react";
import type { DispositionEdit, Finding, FindingState, InputFile, RequestLimits } from "../../api/types.gen";
import { Icon24 } from "../icons";
import { CodeRef } from "./CodeRef";
import { OpenFileLink } from "./OpenFileLink";
import { officerVoice } from "./packageView";
import type { DraftRequestItem } from "./requestDraft";
import { findingSources, findingTitle } from "./workspaceView";

type Reason = NonNullable<FindingState["reason"]>;

export const DISMISS_REASONS: { id: Reason; label: string }[] = [
  { id: "checked", label: "I checked it" },
  { id: "not_needed", label: "Not needed" },
  { id: "does_not_fit", label: "Check doesn’t fit" },
];

export interface FindingStepData {
  finding: Finding;
  state: FindingState;
  /** Its drafted request item, if the review drafted one. */
  item: DraftRequestItem | undefined;
  /** The officer added an item of their own for this field. */
  own: boolean;
  /** Where on the form, in words: "B · Legal description". */
  where: string;
  /** The value on the form now, and before the last return when it changed. */
  value: string | null;
  before: string | null | undefined;
  /** A gap from the completeness rules has its own wording. */
  title?: string;
}

export function FindingStep({ step, caseId, files, limits, editable, last, canBack, onCall, onText, onAddOwn, onNext, onBack }: {
  step: FindingStepData;
  caseId: string;
  files: InputFile[];
  limits: RequestLimits;
  editable: boolean;
  last: boolean;
  canBack: boolean;
  onCall: (edit: DispositionEdit) => void;
  onText: (key: string, text: string) => void;
  onAddOwn: (finding: Finding) => void;
  onNext: () => void;
  onBack: () => void;
}) {
  const id = useId();
  const { finding: f, state, item } = step;
  const [why, setWhy] = useState(false);
  const [wording, setWording] = useState(false);
  useEffect(() => { setWhy(false); setWording(false); }, [f.key]);

  const askable = Boolean(item);
  const asked = askable ? state.state === "ask" : step.own;
  const dismissed = state.state === "dismissed";
  const call = (patch: Partial<DispositionEdit>) =>
    onCall({ key: f.key, state: state.state, reason: state.reason, note: state.note, ...patch });
  const ask = () => (askable ? call({ state: "ask", reason: null, note: "" }) : !step.own && onAddOwn(f));
  const dismiss = () => { if (!state.locked) call({ state: "dismissed", reason: state.reason ?? null }); };

  // 1 asks, 2 dismisses, Enter goes on; never while typing.
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey || !(e.target instanceof Element)) return;
      if (e.target.closest("input, textarea, button, a, [role=listbox], dialog[open]")) {
        if (e.key !== "Enter" || !e.target.closest("button.rw-next")) return;
      }
      if (e.key === "1" && editable) { e.preventDefault(); ask(); }
      else if (e.key === "2" && editable) { e.preventDefault(); dismiss(); }
      else if (e.key === "Enter") { e.preventDefault(); onNext(); }
    };
    document.addEventListener("keydown", key);
    return () => document.removeEventListener("keydown", key);
  });

  const sources = findingSources(f.pointers, files, caseId);
  const quotes = sources.filter((s) => s.quote);
  const blocking = f.severity === "blocking";

  return (
    <div className="cf-q-wrap rw-step" data-finding={f.key}>
      <p className="cf-eyebrow">
        <span className={`cf-dot is-${dismissed ? "pending" : f.severity}${state.state === "verify" ? " is-ring" : ""}`} aria-hidden="true" />
        {step.where}
        <span className="cf-sr"> · {dismissed ? "dismissed" : blocking ? "required" : "to check"}</span>
      </p>
      <h2 id={`${id}-t`} className="cf-q-text rw-step-t" tabIndex={-1}>{step.title ?? findingTitle(f)}</h2>

      {quotes.length > 0 ? (
        <>
          <p className="cf-q-help"><q>{quotes[0].quote}</q></p>
          {quotes.slice(1).map((s, i) => <p key={i} className="rw-more-q"><q>{s.quote}</q></p>)}
        </>
      ) : step.value ? (
        <p className="cf-q-help"><q>{step.value}</q></p>
      ) : null}
      {step.before !== undefined && <p className="rw-before">Before: {step.before || "—"}</p>}

      {(sources.some((s) => s.chip) || f.citations.length > 0) && (
        <div className="rw-srcs">
          {sources.map((s, i) => !s.chip ? null : s.fileId
            ? <OpenFileLink key={i} caseId={caseId} fileId={s.fileId} page={s.page} name={f.pointers[i]?.file ?? ""} label={s.chip} />
            : <span key={i} className="cf-cite is-static" title={s.where}><Icon24 name="file" size={14} />{s.chip}</span>)}
          {f.citations.map((c) => <CodeRef key={c} citation={c} />)}
        </div>
      )}

      {why && <p className="rw-why-text">{officerVoice(f.message)}</p>}

      <div className="cf-choices-q" role="group" aria-labelledby={`${id}-t`}>
        <button type="button" className="cf-choice" aria-pressed={asked} disabled={!editable || (!askable && step.own)} onClick={ask}>
          <span className="cf-choice-key" aria-hidden="true">1</span>
          <span className="cf-choice-label">{askable ? "Ask for it" : "Add to request"}</span>
          <span className="cf-choice-check" aria-hidden="true"><Icon24 name="check" size={16} /></span>
        </button>
        <button type="button" className="cf-choice" aria-pressed={dismissed} disabled={!editable || state.locked} onClick={dismiss}
          aria-describedby={state.locked ? `${id}-lock` : undefined}>
          <span className="cf-choice-key" aria-hidden="true">2</span>
          <span className="cf-choice-label">Dismiss</span>
          <span className="cf-choice-check" aria-hidden="true"><Icon24 name="check" size={16} /></span>
        </button>
      </div>
      {state.locked && <p id={`${id}-lock`} className="rw-hint">Required by the completeness rules</p>}

      {dismissed && (
        <div className="rw-dismiss">
          <div className="rw-reasons" role="group" aria-label="Why">
            {DISMISS_REASONS.map((r) => (
              <button key={r.id} type="button" className="cf-chip" aria-pressed={state.reason === r.id} disabled={!editable}
                onClick={() => call({ reason: r.id })}>{r.label}</button>
            ))}
          </div>
          <label htmlFor={`${id}-note`} className="cf-sr">Note</label>
          <input id={`${id}-note`} className="cf-uline rw-note" maxLength={500} value={state.note} readOnly={!editable}
            placeholder={blocking ? "Note · required" : "Note"} onChange={(e) => call({ note: e.target.value })} />
        </div>
      )}

      {asked && item && wording && (
        <div className="rw-wording">
          <label htmlFor={`${id}-w`} className="cf-sr">What they read</label>
          <textarea id={`${id}-w`} className="cf-uline is-area" rows={2} maxLength={limits.item_text} value={item.text}
            readOnly={!editable} onChange={(e) => onText(item.key, e.target.value)} />
          {item.target && <p className="rw-hint">{item.target.label}</p>}
        </div>
      )}

      <div className="rw-acts">
        <button type="button" className="cf-btn is-primary is-lg rw-next" onClick={onNext}>
          {last ? "Decide" : "Next"}<kbd>↵</kbd>
        </button>
        <button type="button" className="cf-link-btn" disabled={!canBack} onClick={onBack}>Back</button>
        <button type="button" className="cf-link-btn" aria-expanded={why} onClick={() => setWhy(!why)}>Why</button>
        {asked && item && editable && (
          <button type="button" className="cf-link-btn" aria-expanded={wording} onClick={() => setWording(!wording)}>Wording</button>
        )}
      </div>
    </div>
  );
}

/** Progress per form section: one tick per finding, filled once it has a call, dark where you are. */
export function FindingFooter({ sections, at, onJump }: {
  sections: { id: string; name: string; steps: { index: number; decided: boolean; title: string }[] }[];
  at: number;
  onJump: (index: number) => void;
}) {
  return (
    <footer className="cf-qfoot rw-foot" aria-label="Findings by section">
      <div className="cf-secs">
        {sections.map((s) => {
          const on = s.steps.some((x) => x.index === at);
          const done = s.steps.filter((x) => x.decided).length;
          const first = s.steps.find((x) => !x.decided) ?? s.steps[0];
          return (
            <div key={s.id} className={`cf-qsec is-slate${on ? " is-on" : ""}`} style={{ ["--n" as string]: s.steps.length }}>
              <button type="button" className="cf-qsec-btn" onClick={() => onJump(first.index)}
                aria-label={`${s.name}: ${done} of ${s.steps.length} with a call. Go to ${first.title}.`}>
                <span className="cf-qsec-bar" aria-hidden="true">
                  {s.steps.map((x) => <i key={x.index} className={x.index === at ? "is-cur" : x.decided ? "is-done" : ""} />)}
                </span>
                <span className="cf-qsec-lab" aria-hidden="true">
                  <span className={`cf-qsec-name${s.id.length === 1 ? "" : " is-alone"}`}>{s.name}</span>
                  {s.id.length === 1 && <span className="cf-qsec-l">{s.id}</span>}
                  <span className="cf-qsec-count">{done}<span className="cf-qsec-of"> of </span><span className="cf-qsec-slash">/</span>{s.steps.length}</span>
                </span>
              </button>
            </div>
          );
        })}
      </div>
    </footer>
  );
}
