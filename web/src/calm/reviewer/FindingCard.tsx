import { useId, useState } from "react";
import type { DispositionEdit, Finding, FindingState, InputFile, RequestLimits } from "../../api/types.gen";
import { AcIcon } from "../auth/bits";
import { CodeRef } from "./CodeRef";
import { OpenFileLink } from "./OpenFileLink";
import { officerVoice, sentence } from "./packageView";
import type { DraftRequestItem } from "./requestDraft";
import { findingSources } from "./workspaceView";

export const DISMISS_REASONS = [
  { id: "checked", label: "I checked it" }, { id: "not_needed", label: "Not needed here" }, { id: "does_not_fit", label: "The check doesn’t fit" },
] satisfies { id: NonNullable<FindingState["reason"]>; label: string }[];

export function FindingCard({ finding, state, item, caseId, files, limits, editable, onDisposition, onText }: {
  finding: Finding; state: FindingState; item: DraftRequestItem | undefined; caseId: string; files: InputFile[]; limits: RequestLimits;
  editable: boolean; onDisposition: (edit: DispositionEdit) => void; onText: (key: string, text: string) => void;
}) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const dismissed = state.state === "dismissed";
  const reason = DISMISS_REASONS.find(r => r.id === state.reason)?.label;
  const sub = dismissed ? `Dismissed${reason ? ` · ${reason}` : " · choose a reason"}`
    : state.state === "verify" ? finding.severity === "blocking" ? "Look first · still required" : "Look first · to check"
    : finding.severity === "blocking" ? "Required" : "To check";
  const edit = (patch: Partial<DispositionEdit>) => onDisposition({ key: finding.key, state: state.state, reason: state.reason, note: state.note, ...patch });
  const sources = findingSources(finding.pointers, files, caseId);
  return (
    <section className={`rw-finding${dismissed ? " is-dismissed" : ""}`} tabIndex={0} data-finding={finding.key} aria-labelledby={`${id}-title`}>
      <div className="rw-finding-head">
        <span className={`cf-dot is-${dismissed ? "pending" : finding.severity}${state.state === "verify" ? " is-ring" : ""}`} aria-hidden="true" />
        <div className="rw-finding-title"><h3 id={`${id}-title`}>{sentence(finding.label)}</h3><p>{sub}</p></div>
        {editable && <div className="rw-seg" role="group" aria-label={`Your call: ${finding.label}`}>
          <button type="button" data-action="ask" aria-pressed={state.state === "ask"} onClick={() => edit({ state: "ask", reason: null, note: "" })}>Ask</button>
          <button type="button" data-action="dismiss" aria-pressed={dismissed} disabled={state.locked} aria-describedby={state.locked ? `${id}-locked` : undefined}
            onClick={() => { edit({ state: "dismissed" }); setOpen(true); }}>Dismiss</button>
        </div>}
        <button type="button" className="cf-icon-btn is-plain rw-details" aria-label={`Details: ${finding.label}`} title="Details" aria-expanded={open} aria-controls={`${id}-body`} onClick={() => setOpen(!open)}>
          <AcIcon name="chev" size={16} />
        </button>
      </div>
      {state.locked && <p id={`${id}-locked`} className="rw-locked">Completeness rules still require this.</p>}
      {open && <div id={`${id}-body`} className="rw-finding-body">
        <p className="rw-ai">{officerVoice(finding.message)}</p>
        {sources.length > 0 && <ul className="rw-sources" aria-label="Sources">{sources.map((source, index) => <li key={index}>
          {source.quote !== null && source.quote !== "" && <q>{source.quote}</q>}
          <div className="rw-where"><AcIcon name="doc" size={13} /><span>{source.where || "Source location not recorded"}</span>
            {source.fileId && <OpenFileLink caseId={caseId} fileId={source.fileId} page={source.page} name={finding.pointers[index].file} />}
          </div>
        </li>)}</ul>}
        {finding.citations.length > 0 && <div className="pr-cites">{finding.citations.map(citation => <CodeRef key={citation} citation={citation} />)}</div>}
        {state.state === "ask" && item && <div className="rw-field">
          <label htmlFor={`${id}-text`}>They read</label>
          <textarea id={`${id}-text`} className="ac-ta" rows={3} maxLength={limits.item_text} value={item.text} readOnly={!editable} onChange={e => onText(item.key, e.target.value)} />
          <p className="rw-meta">They answer at · {item.target?.label || "Target not recorded"}</p>
        </div>}
        {dismissed && <div className="rw-field">
          <span className="rw-label">Why you dismissed it</span>
          <div className="rw-reasons" role="group" aria-label="Dismissal reason">{DISMISS_REASONS.map(reason => <button type="button" className="cf-chip" key={reason.id} disabled={!editable} aria-pressed={state.reason === reason.id} onClick={() => edit({ reason: reason.id })}>{reason.label}</button>)}</div>
          <label htmlFor={`${id}-note`}>{finding.severity === "blocking" ? "Note (required)" : "Note (optional)"}</label>
          <textarea id={`${id}-note`} className="ac-ta" rows={2} value={state.note} readOnly={!editable} onChange={e => edit({ note: e.target.value })} />
          <p className="rw-meta">Kept in the record · the applicant doesn’t see it</p>
          {state.by_name && <p className="rw-meta">{state.by_name}{state.at ? ` · ${new Date(state.at).toLocaleString()}` : ""}</p>}
        </div>}
      </div>}
    </section>
  );
}
