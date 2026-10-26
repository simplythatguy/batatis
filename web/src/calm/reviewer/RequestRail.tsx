import { useId, type Dispatch, type ReactNode, type SetStateAction } from "react";
import type { Message } from "../../api/accounts";
import type { RequestTarget, ReviewSession, Workspace } from "../../api/types.gen";
import type { ReviewQuestion } from "../../api/client";
import { AcIcon } from "../auth/bits";
import { Messages } from "./Messages";
import { sentLabel, clock } from "./queue";
import { RequestEditor } from "./RequestEditor";
import type { useRequestDraft } from "./useRequestDraft";
import { workspaceDecision, type FindingFilter } from "./workspaceView";

export function RequestRail({ caseId, session, workspace, required, filter, onFilter, tab, onTab, draft, editable, busy, targets, questions, messages, onMessages, me, messageDraft, onMessageDraft, onReturn, onAccept, onRefuse, outcome, readOnlyReason, refreshMessages, composing = false, onComposing, showDecision = editable }: {
  caseId: string; session: ReviewSession | null; workspace: Workspace | null; required?: number; filter: FindingFilter; onFilter: (filter: FindingFilter) => void;
  tab: "request" | "messages"; onTab: (tab: "request" | "messages") => void; draft: ReturnType<typeof useRequestDraft> | null;
  editable: boolean; busy: boolean; targets: RequestTarget[]; questions: ReviewQuestion[]; messages: Message[] | null; onMessages: Dispatch<SetStateAction<Message[] | null>>;
  me: string | null; messageDraft: string; onMessageDraft: (value: string) => void; onReturn: () => void; onAccept: () => void; onRefuse: () => void;
  showDecision?: boolean; composing?: boolean; onComposing?: (open: boolean) => void; outcome?: ReactNode; readOnlyReason: string; refreshMessages: () => void;
}) {
  const id = useId();
  const tally = workspace?.tally;
  const pending = Boolean(draft?.pending || composing);
  const availability = workspaceDecision({ workspace, editable, pending, busy });
  const gate = !editable && readOnlyReason ? { ...availability, acceptReason: workspace?.gate.reason || readOnlyReason, returnReason: readOnlyReason } : availability;
  const text = session?.information_request.text ?? "";
  const diff = session?.diff;
  return <aside className="rw-rail" aria-label="Request and decision">
    {tally ? <div className="rw-rail-section"><div className="rw-tally" role="group" aria-label="Review counts">
      {([
        ["required", tally.required, "Required", "blocking"],
        ["to_check", tally.to_check, "To check", "warning"], ["dismissed", tally.dismissed, "Dismissed", "pending"],
      ] satisfies [FindingFilter, number, string, string][]).map(([key, count, label, tone]) => <button type="button" key={key} aria-pressed={filter === key} onClick={() => onFilter(filter === key ? "all" : key)}>
        <b>{count}</b><span><span className={`cf-dot is-${tone}`} aria-hidden="true" />{label}</span>{key === "required" && tally.verify > 0 && <small>{tally.verify} look first</small>}
      </button>)}
    </div></div> : required !== undefined && <p className="rw-rail-section rw-meta">Version {session?.version} · {required} required</p>}
    {filter !== "all" && <p className="rw-filter-note">Filtering findings · <button type="button" className="cf-link-btn" onClick={() => onFilter("all")}>Show all</button></p>}
    {diff && <section className="rw-rail-section" aria-label={`Since version ${diff.previous_version}`}>
      <h3>Since version {diff.previous_version}</h3><div className="rw-since">
        <span><span className="cf-dot is-done" aria-hidden="true" />{diff.resolved.length} fixed</span>
        <span><span className="cf-dot is-warning" aria-hidden="true" />{diff.still_open.length} still open</span>
        <span><span className="cf-dot is-blocking" aria-hidden="true" />{diff.new.length} new</span>
        <span><span className="cf-dot is-pending" aria-hidden="true" />{diff.unverified?.length ?? 0} can’t tell</span>
      </div>
      <details className="rw-diff"><summary>Details</summary><p>{diff.statement}</p>{[
        ["Fixed", diff.resolved], ["Still open", diff.still_open], ["New", diff.new], ["Can’t tell", diff.unverified ?? []],
      ].map(([label, entries]) => <div key={String(label)}>{typeof entries !== "string" && entries.length > 0 && <><h4>{String(label)}</h4><ul>{entries.map(entry => <li key={entry.key}>{entry.label} · {entry.message}</li>)}</ul></>}</div>)}</details>
    </section>}
    <div className="rw-tabs" role="tablist" aria-label="Correspondence">
      <button type="button" id={`${id}-request-tab`} role="tab" aria-selected={tab === "request"} aria-controls={`${id}-request`} onClick={() => onTab("request")}><AcIcon name="doc" size={14} />Request{tally && <span className="rw-badge">{tally.asked}</span>}</button>
      <button type="button" id={`${id}-messages-tab`} role="tab" aria-selected={tab === "messages"} aria-controls={`${id}-messages`} onClick={() => onTab("messages")}><AcIcon name="chat" size={14} />Messages{messages && <span className="rw-badge">{messages.length}</span>}</button>
    </div>
    <section className="rw-rail-section rw-correspondence" id={`${id}-${tab}`} role="tabpanel" aria-labelledby={`${id}-${tab}-tab`}>
      {tab === "request" ? <>
        <h3>{session?.information_request.sent_at ? `Sent ${sentLabel(session.information_request.sent_at)}` : "What the applicant receives"}</h3>
        <pre className="rw-letter" aria-label="Saved request text">{text || "No saved request text yet."}</pre>
        {workspace && <p className="rw-limit"><span>{workspace.tally.asked} items</span><span>{text.length} / {workspace.limits.text}</span></p>}
        {draft && <div className="rw-save" role="status" aria-live="polite">
          {draft.state.save.kind === "saved" ? draft.state.savedAt ? `Saved ${clock(draft.state.savedAt)}` : "Saved draft"
            : draft.state.save.kind === "saving" ? "Saving… · preview is the last save"
            : draft.state.save.kind === "error" ? draft.state.save.message : "Unsaved changes · preview is the last save"}
          {draft.problem && <p>{draft.problem}</p>}
          {draft.state.save.kind === "error" && editable && <button type="button" className="cf-btn is-xs" onClick={() => draft.dispatch({ type: "retry" })}>Retry save</button>}
          {draft.state.save.kind === "dirty" && !draft.problem && editable && <button type="button" className="cf-btn is-xs" onClick={() => void draft.save()}>Save now</button>}
        </div>}
        {editable && draft && workspace && <RequestEditor draft={draft} targets={targets} questions={questions} limits={workspace.limits} onEditing={onComposing} />}
        {!editable && readOnlyReason && <p className="rw-hint">{readOnlyReason}</p>}
      </> : <>
        {messages === null ? <p className="rw-hint">Messages didn’t load. <button type="button" className="cf-btn is-xs" onClick={refreshMessages}>Try again</button></p>
          : <Messages caseId={caseId} me={me} messages={messages} onChange={onMessages} canWrite={editable} hideTitle draft={messageDraft} onDraft={onMessageDraft} />}
        <p className="rw-meta">One way · they answer by fixing and resending</p>
      </>}
    </section>
    {outcome || (showDecision && session && <footer className="rw-decision">
      <p className="rw-pin"><AcIcon name="clipboard" size={13} />Deciding on version {session.version} · {draft?.state.savedAt ? `saved ${clock(draft.state.savedAt)}` : `saved ${sentLabel(session.created_at)}`}</p>
      <p className="rw-scope">Completeness only · not a design approval</p>
      <div className="rw-decision-actions">
        <button type="button" className="cf-btn is-sm is-primary" disabled={!gate.canReturn} aria-describedby={`${id}-return-why`} onClick={onReturn}><AcIcon name="send" size={14} />Return with {tally?.asked ?? 0} {tally?.asked === 1 ? "item" : "items"}</button>
        <button type="button" className="cf-btn is-sm" disabled={!gate.canAccept} aria-describedby={`${id}-accept-why`} data-requires-no-blocking-gaps={gate.canAccept ? undefined : "true"} onClick={onAccept}><AcIcon name="check" size={14} />Accept</button>
        <button type="button" className="cf-btn is-sm" disabled={!gate.canRefuse} onClick={onRefuse}>Refuse</button>
      </div>
      {gate.returnReason && <p className="rw-hint" id={`${id}-return-why`}>{gate.returnReason}</p>}
      {!gate.canAccept && gate.acceptReason && <p className="rw-hint" id={`${id}-accept-why`} title={gate.acceptReason}><span className="rw-short-reason" aria-hidden="true">{gate.acceptReason}</span><span className="cf-sr">{gate.acceptReason}</span></p>}
    </footer>)}
  </aside>;
}
