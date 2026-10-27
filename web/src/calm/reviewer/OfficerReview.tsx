/**
 * The officer's review, on the applicant's Review layout: a headline that counts, the list of what to
 * ask for, and one card with the sections and the one main action. A row opens in place to show the
 * applicant's own words and the source files. ✕ means "don't ask for this"; a required item asks why
 * (one tap). Everything else is one step away: the full application, the messages.
 */
import { useId, useState, type ReactNode } from "react";
import type { DispositionEdit, Finding, FindingState, InputFile, RequestTarget, RulebookGap } from "../../api/types.gen";
import { CIcon, CompletenessNote, Dot, Eyebrow } from "../ui";
import { Icon24, type IconName } from "../icons";
import { CodeRef } from "./CodeRef";
import { OpenFileLink } from "./OpenFileLink";
import { officerVoice, sentence } from "./packageView";
import type { DraftRequestItem } from "./requestDraft";
import { TargetSelect } from "./TargetSelect";
import { findingSources } from "./workspaceView";

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

export const DISMISS_REASONS: { id: NonNullable<FindingState["reason"]>; label: string }[] = [
  { id: "checked", label: "I checked it" },
  { id: "not_needed", label: "Not needed" },
  { id: "does_not_fit", label: "Check doesn’t fit" },
];

export interface Row {
  finding: Finding;
  state: FindingState;
  /** The review drafted a request item for it. */
  askable: boolean;
}

function Evidence({ f, caseId, files }: { f: Finding; caseId: string; files: InputFile[] }) {
  const sources = findingSources(f.pointers, files, caseId);
  return (
    <div className="ow-ev">
      {sources.filter((s) => s.quote).map((s, i) => <q key={i}>{s.quote}</q>)}
      <div className="ow-ev-chips">
        {sources.map((s, i) => !s.chip ? null : s.fileId
          ? <OpenFileLink key={i} caseId={caseId} fileId={s.fileId} page={s.page} name={f.pointers[i]?.file ?? ""} label={s.chip} />
          : <span key={i} className="cf-cite is-static"><Icon24 name="file" size={14} />{s.chip}</span>)}
        {f.citations.map((c) => <CodeRef key={c} citation={c} />)}
      </div>
      <p className="cf-faint cf-small">{officerVoice(f.message)}</p>
    </div>
  );
}

export function FindingRow({ row, caseId, files, editable, onCall, onAddOwn }: {
  row: Row; caseId: string; files: InputFile[]; editable: boolean;
  onCall: (edit: DispositionEdit) => void; onAddOwn: (f: Finding) => void;
}) {
  const { finding: f, state } = row;
  const [open, setOpen] = useState(false);
  const [why, setWhy] = useState(false);
  const verify = state.state === "verify";
  const tone = f.severity === "blocking" ? "blocking" : "warning";
  const dismiss = (reason: DismissReason) => { setWhy(false); onCall({ key: f.key, state: "dismissed", reason, note: "" }); };
  const drop = () => (f.severity === "blocking" ? setWhy(true) : dismiss("not_needed"));
  return (
    <li className={`cf-row ow-row${open ? " is-open" : ""}`}>
      <span className={`cf-dot is-${tone}${verify ? " is-ring" : ""}`} aria-hidden="true" />
      <button type="button" className="cf-row-text ow-row-t" aria-expanded={open} onClick={() => setOpen(!open)}
        title={verify ? "Couldn’t be read · look first" : undefined}>
        {sentence(f.label)}
        <span className="cf-sr">{f.severity === "blocking" ? ", required" : ", to check"}{verify ? ", look first" : ""}</span>
      </button>
      {editable && verify && (
        <button type="button" className="cf-row-go" onClick={() => (row.askable ? onCall({ key: f.key, state: "ask", reason: null, note: "" }) : onAddOwn(f))}>
          Ask <CIcon name="plus" size={13} />
        </button>
      )}
      {editable && (state.locked ? (
        <span className="cf-faint cf-small" title="The completeness rules require it">Required</span>
      ) : (
        <button type="button" className="cf-icon-btn is-plain ow-x" aria-label={`Don’t ask for ${f.label}`} title="Don’t ask" onClick={drop}>
          <CIcon name="close" size={14} />
        </button>
      ))}
      {why && (
        <div className="ow-why" role="group" aria-label="Why not ask">
          {DISMISS_REASONS.map((r) => <button key={r.id} type="button" className="cf-chip" onClick={() => dismiss(r.id)}>{r.label}</button>)}
          <button type="button" className="cf-link-btn" onClick={() => setWhy(false)}>Cancel</button>
        </div>
      )}
      {open && <Evidence f={f} caseId={caseId} files={files} />}
    </li>
  );
}

type DismissReason = NonNullable<FindingState["reason"]>;

function OwnItem({ item, targets, limits, onText, onTarget, onRemove }: {
  item: DraftRequestItem; targets: RequestTarget[]; limits: number;
  onText: (t: string) => void; onTarget: (t: RequestTarget) => void; onRemove: () => void;
}) {
  return (
    <li className="cf-row ow-row ow-own">
      <span className="cf-dot is-pending" aria-hidden="true" />
      <div className="ow-own-body">
        <input className="ow-own-input" aria-label="Your item" maxLength={limits} value={item.text} placeholder="What should they provide?"
          onChange={(e) => onText(e.target.value)} />
        <TargetSelect options={targets} value={item.target} onChange={onTarget} />
      </div>
      <button type="button" className="cf-icon-btn is-plain ow-x" aria-label="Remove your item" title="Remove" onClick={onRemove}><CIcon name="close" size={14} /></button>
    </li>
  );
}

export interface SectionRow { id: string; title: string; icon: IconName; summary: string; tone: "blocking" | "warning" | "pending" | "done" | null }

export function OfficerReview({ headline, lede, rows, rulebook, dismissed, own, caseId, files, editable, targets, itemLimit, sections, actions,
  extra, onCall, onAddOwn, onAdd, onOwnText, onOwnTarget, onOwnRemove, onSection }: {
  headline: string;
  lede: ReactNode;
  rows: Row[];
  rulebook: RulebookGap[];
  dismissed: Row[];
  own: DraftRequestItem[];
  caseId: string;
  files: InputFile[];
  editable: boolean;
  targets: RequestTarget[];
  itemLimit: number;
  sections: SectionRow[];
  /** The main action and its neighbour, or the outcome once decided. */
  actions: ReactNode;
  /** Under the list: the close-out, the sent request, a determination. */
  extra?: ReactNode;
  onCall: (edit: DispositionEdit) => void;
  onAddOwn: (f: Finding) => void;
  onAdd: () => void;
  onOwnText: (key: string, text: string) => void;
  onOwnTarget: (key: string, target: RequestTarget) => void;
  onOwnRemove: (key: string) => void;
  onSection: (id: string) => void;
}) {
  const id = useId();
  const listed = rows.length + rulebook.length + own.length;
  return (
    <div className="cf-review ow">
      <div className="cf-review-main">
        <h1 className="cf-h1" id={`${id}-h`} tabIndex={-1}>{headline}</h1>
        {lede && <p className="cf-lede is-sm">{lede}</p>}

        {listed > 0 && <div className="cf-list-label">To ask</div>}
        {listed > 0 && (
          <ul className="cf-rows" aria-label="To ask">
            {rows.map((r) => <FindingRow key={r.finding.key} row={r} caseId={caseId} files={files} editable={editable} onCall={onCall} onAddOwn={onAddOwn} />)}
            {rulebook.map((g) => (
              <li key={g.id} className="cf-row ow-row">
                <Dot tone="blocking" />
                <span className="cf-row-text">{g.message}</span>
                <span className="cf-faint cf-small">Required</span>
              </li>
            ))}
            {own.map((item) => (
              <OwnItem key={item.key} item={item} targets={targets} limits={itemLimit}
                onText={(t) => onOwnText(item.key, t)} onTarget={(t) => onOwnTarget(item.key, t)} onRemove={() => onOwnRemove(item.key)} />
            ))}
          </ul>
        )}
        {editable && (
          <button type="button" className="cf-link-btn ow-add" onClick={onAdd}><CIcon name="plus" size={13} />Add your own</button>
        )}

        {dismissed.length > 0 && (
          <details className="ow-fold">
            <summary className="cf-list-label">Not asking · {dismissed.length}</summary>
            <ul className="cf-rows">
              {dismissed.map((r) => (
                <li key={r.finding.key} className="cf-row ow-row is-quiet">
                  <Dot tone="pending" />
                  <span className="cf-row-text">{sentence(r.finding.label)}
                    <span className="cf-faint cf-small"> · {DISMISS_REASONS.find((x) => x.id === r.state.reason)?.label ?? "Not asking"}</span>
                  </span>
                  {editable && !r.state.locked && (
                    <button type="button" className="cf-row-go" onClick={() => onCall({ key: r.finding.key, state: r.askable ? "ask" : "verify", reason: null, note: "" })}>Ask again</button>
                  )}
                </li>
              ))}
            </ul>
          </details>
        )}
        {extra}
      </div>

      <aside className="cf-glass cf-sections" aria-label="Application">
        <Eyebrow plain>Application</Eyebrow>
        <ul className="cf-sec-list">
          {sections.map((s) => (
            <li key={s.id} className="cf-sec ow-sec">
              <button type="button" className="ow-sec-btn" onClick={() => onSection(s.id)} aria-label={`${s.title}${s.summary ? `: ${s.summary}` : ""}. Open the application here.`}>
                <span className="cf-sec-icon" aria-hidden="true"><Icon24 name={s.icon} size={18} /></span>
                <span className="cf-sec-t">
                  <span>{s.title} <span className="cf-faint">· {s.id === "process" ? "Your case" : `Section ${s.id}`}</span></span>
                  {s.summary && <span className="cf-faint">{s.summary}</span>}
                </span>
                {s.tone && <Dot tone={s.tone} />}
              </button>
            </li>
          ))}
        </ul>
        <div className="cf-sec-actions">{actions}</div>
        <CompletenessNote />
      </aside>
    </div>
  );
}

export { plural };
