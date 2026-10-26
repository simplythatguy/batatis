import { CIcon, Modal } from "../ui";
import type { DocBlock } from "./document";
import type { HistoryEntry } from "./history";
import type { WorkspaceController } from "./useWorkspace";

export function HistoryDrawer({ open, onClose, workspace, blocks, locked, onRestore }: {
  open: boolean; onClose: () => void; workspace: WorkspaceController; blocks: DocBlock[]; locked: boolean; onRestore: (entry: HistoryEntry) => void;
}) {
  return <Modal open={open} onClose={onClose} labelledBy="aw-history-title" className="cf-drawer aw-history"><div className="cf-drawer-scroll">
    <div className="aw-dialog-head"><h2 id="aw-history-title" className="cf-modal-title">History</h2><button type="button" className="cf-icon-btn" aria-label="Close history" title="Close history" onClick={onClose}><CIcon name="close" /></button></div>
    {workspace.historyNote && <p className="cf-hint" role="status">{workspace.historyNote} <button type="button" className="cf-link-btn" onClick={() => void workspace.flushHistory()}>Try again</button></p>}
    {workspace.historyPending > 0 && <p className="cf-faint cf-small" role="status">{workspace.historyPending} changes waiting to sync</p>}
    {!workspace.history.length && <p className="cf-faint">Your edits will appear here.</p>}
    <ol className="aw-history-list">{[...workspace.history].reverse().map(entry => {
      const block = blocks.find(b => b.id === entry.block);
      return <li key={entry.id}><span className="cf-faint cf-small">{entry.by === "ai" ? "AI · accepted" : entry.by === "restore" ? "Restored" : "You"} · <time dateTime={entry.at}>{new Date(entry.at).toLocaleString()}</time></span>
        <h3>{entry.label}</h3><details><summary>Change</summary><p><span className="cf-faint cf-small">Before</span><br />{entry.before || "—"}</p><p><span className="cf-faint cf-small">After</span><br />{entry.after || "—"}</p></details>
        {!locked && block?.target.kind !== "card" && <button type="button" className="cf-btn is-xs" disabled={!block || block.text === entry.after} onClick={() => onRestore(entry)}>Restore</button>}
      </li>;
    })}</ol>
  </div></Modal>;
}
