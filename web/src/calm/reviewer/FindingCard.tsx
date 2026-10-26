/**
 * One automated finding, shown under the field it is about. The officer makes one call (Ask or
 * Dismiss) and can open the evidence: the check's message, every source quote in full with its file
 * and page, and the code it cites. Nothing here recounts or judges; the state comes from the server.
 */
import { useId, useState } from "react";
import type { DispositionEdit, Finding, FindingState, InputFile, RequestLimits } from "../../api/types.gen";
import { AcIcon } from "../auth/bits";
import { CodeRef } from "./CodeRef";
import { OpenFileLink } from "./OpenFileLink";
import { officerVoice, sentence } from "./packageView";
import type { DraftRequestItem } from "./requestDraft";
import { findingSources } from "./workspaceView";

type Reason = NonNullable<FindingState["reason"]>;

export const DISMISS_REASONS: { id: Reason; label: string }[] = [
  { id: "checked", label: "I checked it" },
  { id: "not_needed", label: "Not needed here" },
  { id: "does_not_fit", label: "Check doesn’t fit" },
];

/** The one line under the title: what this finding means for the decision right now. */
export function findingStatus(finding: Finding, state: FindingState): string {
  if (state.state === "dismissed") {
    const reason = DISMISS_REASONS.find((r) => r.id === state.reason)?.label;
    return reason ? `Dismissed · ${reason}` : "Dismissed · choose why";
  }
  const required = finding.severity === "blocking";
  if (state.locked) return "Required by the completeness rules";
  if (state.state === "verify") return required ? "Look first · still required" : "Look first";
  return required ? "Required" : "To check";
}

export function FindingCard({ finding, state, item, askable, caseId, files, limits, editable, focused, onDisposition, onText, onAddItem }: {
  finding: Finding;
  state: FindingState;
  /** Its request item, while it is asked. */
  item: DraftRequestItem | undefined;
  /** The review drafted a request item for it. Without one (an officer check), the officer writes their own. */
  askable: boolean;
  caseId: string;
  files: InputFile[];
  limits: RequestLimits;
  editable: boolean;
  focused?: boolean;
  onDisposition: (edit: DispositionEdit) => void;
  onText: (key: string, text: string) => void;
  onAddItem: (finding: Finding) => void;
}) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const dismissed = state.state === "dismissed";
  const tone = dismissed ? "pending" : finding.severity;
  const sources = findingSources(finding.pointers, files, caseId);
  const call = (patch: Partial<DispositionEdit>) =>
    onDisposition({ key: finding.key, state: state.state, reason: state.reason, note: state.note, ...patch });

  return (
    <article
      className={`rw-f${dismissed ? " is-dismissed" : ""}${focused ? " is-focus" : ""}`}
      tabIndex={-1}
      data-finding={finding.key}
      aria-labelledby={`${id}-t`}
    >
      <div className="rw-f-head">
        <span className={`cf-dot is-${tone}${state.state === "verify" ? " is-ring" : ""}`} aria-hidden="true" />
        <div className="rw-f-title">
          <h4 id={`${id}-t`}>{sentence(finding.label)}</h4>
          <p>{findingStatus(finding, state)}</p>
        </div>
        {editable && !askable && !dismissed && (
          <button type="button" className="cf-btn is-xs is-ghost rw-f-own" title="Write your own request item for this"
            onClick={() => onAddItem(finding)}>Add to request</button>
        )}
        {editable && (
          <div className="rw-seg" role="group" aria-label={`Your call on ${finding.label}`}>
            {askable && <button type="button" data-action="ask" aria-pressed={state.state === "ask"}
              onClick={() => call({ state: "ask", reason: null, note: "" })}>Ask</button>}
            <button type="button" data-action="dismiss" aria-pressed={dismissed} disabled={state.locked}
              title={state.locked ? "The completeness rules still require this. Ask for it." : undefined}
              onClick={() => { call({ state: "dismissed", reason: state.reason ?? null }); setOpen(true); }}>Dismiss</button>
          </div>
        )}
        <button type="button" className="rw-f-more" aria-expanded={open} aria-controls={`${id}-b`}
          aria-label={open ? "Hide the evidence" : "Show the evidence"} onClick={() => setOpen(!open)}>
          <AcIcon name="chev" size={16} />
        </button>
      </div>

      {open && (
        <div id={`${id}-b`} className="rw-f-body">
          <p className="rw-f-msg">{officerVoice(finding.message)}</p>
          {sources.length > 0 && (
            <ul className="rw-srcs" aria-label="Where it was read">
              {sources.map((s, i) => (
                <li key={i}>
                  {s.quote && <q>{s.quote}</q>}
                  {(s.where || s.fileId) && (
                    <span className="rw-where">
                      <AcIcon name="doc" size={13} />
                      {s.where}
                      {s.fileId && <OpenFileLink caseId={caseId} fileId={s.fileId} page={s.page} name={finding.pointers[i].file} />}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
          {finding.citations.length > 0 && (
            <div className="pr-cites">{finding.citations.map((c) => <CodeRef key={c} citation={c} />)}</div>
          )}

          {state.state === "ask" && item && (
            <div className="rw-ask">
              <label htmlFor={`${id}-ask`}>They read</label>
              <textarea id={`${id}-ask`} className="ac-ta" rows={2} maxLength={limits.item_text} value={item.text}
                readOnly={!editable} onChange={(e) => onText(item.key, e.target.value)} />
              {item.target && <p className="rw-target"><AcIcon name="right" size={12} />They answer at {item.target.label}</p>}
            </div>
          )}

          {dismissed && (
            <div className="rw-ask">
              <span className="rw-ask-h">Why</span>
              <div className="rw-reasons" role="group" aria-label="Why you dismissed it">
                {DISMISS_REASONS.map((r) => (
                  <button key={r.id} type="button" className="cf-chip" aria-pressed={state.reason === r.id}
                    disabled={!editable} onClick={() => call({ reason: r.id })}>{r.label}</button>
                ))}
              </div>
              <label htmlFor={`${id}-note`} className="cf-sr">Note</label>
              <textarea id={`${id}-note`} className="ac-ta" rows={2} maxLength={500} value={state.note} readOnly={!editable}
                placeholder={finding.severity === "blocking" ? "Note · needed for a required item" : "Note · optional"}
                onChange={(e) => call({ note: e.target.value })} />
              <p className="rw-target">For the record only · the applicant doesn’t see it{state.by_name ? ` · ${state.by_name}` : ""}</p>
            </div>
          )}
        </div>
      )}
    </article>
  );
}

/** A blocking gap from the shared completeness rules that no finding covers: shown, never dismissed. */
export function RulebookRow({ message }: { message: string }) {
  return (
    <section className="rw-f is-rule">
      <div className="rw-f-head">
        <span className="cf-dot is-blocking" aria-hidden="true" />
        <div className="rw-f-title">
          <h4>{message}</h4>
          <p>Required by the completeness rules</p>
        </div>
      </div>
    </section>
  );
}
