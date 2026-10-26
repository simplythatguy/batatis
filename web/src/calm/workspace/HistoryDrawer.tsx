import { Icon24, type IconName } from "../icons";
import { CIcon, Modal } from "../ui";
import type { HistoryEntry } from "./history";
import { changedWords } from "./suggestions";
import type { Editing } from "./useEditing";

const WHO: Record<HistoryEntry["by"], { word: string; icon: IconName }> = {
  you: { word: "You", icon: "user" },
  ai: { word: "AI, accepted by you", icon: "spark" },
  restore: { word: "Restored", icon: "undo" },
};

function when(iso: string): string {
  const d = new Date(iso);
  const sameDay = d.toDateString() === new Date().toDateString();
  return sameDay ? d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }) : d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

const clip = (s: string, n: number, end: boolean) => s.length <= n ? s : end ? `${s.slice(0, n)}…` : `…${s.slice(-n)}`;

/** Every change to the application, newest first. Any version can come back. */
export function HistoryDrawer({ open, onClose, editing }: { open: boolean; onClose: () => void; editing: Editing }) {
  const { workspace, blocks, locked } = editing;
  const entries = [...workspace.history].reverse();
  return (
    <Modal open={open} onClose={onClose} labelledBy="aw-history-title" className="cf-drawer aw-history">
      <div className="cf-drawer-scroll">
        <div className="aw-dialog-head">
          <h2 id="aw-history-title" className="cf-modal-title">History</h2>
          <button type="button" className="cf-icon-btn" aria-label="Close history" title="Close" onClick={onClose}><CIcon name="close" /></button>
        </div>
        {workspace.historyNote && (
          <p className="aw-note" role="status">{workspace.historyNote}<button type="button" className="cf-link-btn" onClick={() => void workspace.flushHistory()}>Try again</button></p>
        )}
        {workspace.historyPending > 0 && <p className="aw-fine" role="status">Saving {workspace.historyPending} {workspace.historyPending === 1 ? "change" : "changes"}…</p>}
        {!entries.length && <p className="aw-fine">Changes you make appear here.</p>}
        <ol className="aw-timeline">
          {entries.map(entry => {
            const block = blocks.find(b => b.id === entry.block);
            const d = changedWords(entry.before, entry.after);
            const who = WHO[entry.by];
            const canRestore = !locked && block && block.target.kind !== "card" && block.text !== entry.after;
            return (
              <li key={entry.id} className={`is-${entry.by}`}>
                <span className="aw-timeline-icon" title={who.word}><Icon24 name={who.icon} size={13} /></span>
                <div className="aw-timeline-body">
                  <p className="aw-timeline-head">
                    <strong>{entry.label}</strong>
                    <span>{who.word} · <time dateTime={entry.at}>{when(entry.at)}</time></span>
                  </p>
                  <p className="aw-timeline-diff">
                    {clip(d.prefix, 60, false)}
                    {d.removed && <del>{clip(d.removed, 220, true)}</del>}
                    {d.added && <ins>{clip(d.added, 220, true)}</ins>}
                    {clip(d.suffix, 60, true)}
                  </p>
                  {canRestore && <button type="button" className="cf-link-btn" onClick={() => editing.restore(entry)}>Restore this version</button>}
                </div>
              </li>
            );
          })}
        </ol>
      </div>
    </Modal>
  );
}
