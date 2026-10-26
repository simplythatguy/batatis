/**
 * The side rail: the counts (one definition, from the server), what changed since the last version,
 * the request or the messages, and the decision for the version on screen. Decisions wait for saved
 * edits; Accept follows the server's gate and shows its reason when it is off.
 */
import { useId, type ReactNode } from "react";
import type { ReviewDiff, ReviewTally } from "../../api/types.gen";
import { AcIcon } from "../auth/bits";
import type { FindingFilter } from "./workspaceView";

type Tab = "request" | "messages";

export function Tally({ tally, filter, onFilter }: { tally: ReviewTally; filter: FindingFilter; onFilter: (f: FindingFilter) => void }) {
  const tiles: [FindingFilter, number, string, string][] = [
    ["required", tally.required, "Required", "blocking"],
    ["to_check", tally.to_check, "To check", "warning"],
    ["dismissed", tally.dismissed, "Dismissed", "pending"],
  ];
  return (
    <div className="rw-tally-wrap">
      <div className="rw-tally" role="group" aria-label="Counts · choose one to show only those findings">
        {tiles.map(([key, n, label, tone]) => (
          <button key={key} type="button" aria-pressed={filter === key} onClick={() => onFilter(filter === key ? "all" : key)}>
            <b>{n}</b>
            <span><span className={`cf-dot is-${tone}`} aria-hidden="true" />{label}</span>
          </button>
        ))}
      </div>
      {tally.verify > 0 && <p className="rw-verify"><span className="cf-dot is-ring" aria-hidden="true" />{tally.verify} the review couldn’t establish · look first</p>}
    </div>
  );
}

export function Since({ diff }: { diff: ReviewDiff }) {
  const parts: [number, string, string][] = [
    [diff.resolved.length, "fixed", "done"],
    [diff.still_open.length, "still open", "warning"],
    [diff.new.length, "new", "blocking"],
    [diff.unverified?.length ?? 0, "can’t tell", "pending"],
  ];
  return (
    <details className="rw-since">
      <summary>
        <span className="rw-since-h">Since v{diff.previous_version}</span>
        {parts.filter(([n]) => n > 0).map(([n, label, tone]) => (
          <span key={label}><span className={`cf-dot is-${tone}`} aria-hidden="true" />{n} {label}</span>
        ))}
        <AcIcon name="chev" size={14} />
      </summary>
      {([["Fixed", diff.resolved], ["Still open", diff.still_open], ["New", diff.new], ["Can’t tell", diff.unverified ?? []]] as const)
        .filter(([, list]) => list.length)
        .map(([label, list]) => (
          <div key={label} className="rw-since-list">
            <h4>{label}</h4>
            <ul>{list.map((e) => <li key={e.key}>{e.label}</li>)}</ul>
          </div>
        ))}
    </details>
  );
}

export interface Decision {
  version: number;
  savedAt: string;
  asked: number;
  /** Without a review there is no item list: "Return with a message". */
  returnLabel?: string;
  canReturn: boolean;
  returnWhy: string;
  canAccept: boolean;
  acceptWhy: string;
  canRefuse: boolean;
  busy: boolean;
  onReturn: () => void;
  onAccept: () => void;
  onRefuse: () => void;
}

export function DecisionBar({ d }: { d: Decision }) {
  const id = useId();
  const returnWhy = !d.canReturn ? d.returnWhy : "";
  const acceptWhy = !d.canAccept && d.acceptWhy !== returnWhy ? d.acceptWhy : "";
  const refuseWhy = !d.canRefuse ? "Wait for the current action to finish" : "";
  return (
    <footer className="rw-decide">
      <p className="rw-pin"><AcIcon name="clipboard" size={13} />Deciding on v{d.version} · {d.savedAt}</p>
      <div className="rw-decide-acts">
        <button type="button" className="cf-btn is-sm is-primary is-wide" disabled={!d.canReturn || d.busy}
          aria-describedby={returnWhy ? `${id}-r` : undefined} onClick={d.onReturn}>
          <AcIcon name="send" size={14} />{d.returnLabel ?? `Return with ${d.asked} ${d.asked === 1 ? "item" : "items"}`}
        </button>
        <button type="button" className="cf-btn is-sm" disabled={!d.canAccept || d.busy}
          data-requires-no-blocking-gaps={d.canAccept ? undefined : "true"}
          aria-describedby={!d.canAccept ? `${id}-${acceptWhy ? "a" : "r"}` : undefined} onClick={d.onAccept}>
          <AcIcon name="check" size={14} />Accept
        </button>
        <button type="button" className="cf-btn is-sm" disabled={!d.canRefuse || d.busy} title={refuseWhy || undefined} onClick={d.onRefuse}>Refuse</button>
      </div>
      {returnWhy && <p id={`${id}-r`} className="rw-why"><span className="cf-dot is-blocking" aria-hidden="true" />{returnWhy}</p>}
      {acceptWhy && <p id={`${id}-a`} className="rw-why"><span className="cf-dot is-blocking" aria-hidden="true" />{acceptWhy}</p>}
      <p className="rw-scope">Completeness only · not a design approval</p>
    </footer>
  );
}

export function ReviewRail({ top, tab, onTab, asked, unread, request, messages, foot }: {
  /** Counts and "since", when there is a review. */
  top: ReactNode;
  tab: Tab;
  onTab: (t: Tab) => void;
  asked: number | null;
  unread: number;
  request: ReactNode;
  messages: ReactNode;
  /** The decision bar, or the outcome once decided. */
  foot: ReactNode;
}) {
  const id = useId();
  const tabs: [Tab, string, ReactNode][] = [
    ["request", "Request", asked !== null && <span className="rw-n">{asked}</span>],
    ["messages", "Messages", unread > 0 && <span className="rw-n is-new">{unread}</span>],
  ];
  return (
    <aside className="rw-rail" aria-label="Request and decision">
      {top}
      <div className="rw-tabs" role="tablist" aria-label="Request or messages"
        onKeyDown={(e) => {
          if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
          e.preventDefault();
          const next = tab === "request" ? "messages" : "request";
          onTab(next);
          e.currentTarget.querySelector<HTMLElement>(`[data-tab="${next}"]`)?.focus();
        }}>
        {tabs.map(([key, label, badge]) => (
          <button key={key} type="button" role="tab" id={`${id}-${key}`} data-tab={key} aria-selected={tab === key}
            aria-controls={`${id}-p`} tabIndex={tab === key ? 0 : -1} onClick={() => onTab(key)}>
            {label}{badge}
          </button>
        ))}
      </div>
      <div className="rw-panel" id={`${id}-p`} role="tabpanel" aria-labelledby={`${id}-${tab}`}>
        {tab === "request" ? request : messages}
      </div>
      {foot}
    </aside>
  );
}
