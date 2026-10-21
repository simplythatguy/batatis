import { forwardRef, useImperativeHandle, useRef, useState, type ReactNode } from "react";
import type { ApplicationSummary } from "../../api/accounts";
import { groupApplications, statusLine } from "../applications";
import { Icon24 } from "../icons";
import { MOD_KEY } from "../ui";

export interface ApplicationListHandle {
  focusSearch: () => void;
}

/** One row: title, one context line, accent bar when selected, optional hover actions. */
function Row({ a, selected, onSelect, actions, line }: { a: ApplicationSummary; selected: boolean; onSelect: (id: string) => void; actions?: ReactNode; line?: { text: string; tone: string; attention: boolean } }) {
  const l = line ?? statusLine(a);
  return (
    <li className={`cf-list-row${selected ? " is-selected" : ""}`}>
      <button type="button" className="cf-list-hit" aria-current={selected ? "page" : undefined} onClick={() => onSelect(a.id)}>
        <span className="cf-list-title">{a.title || "Untitled application"}</span>
        <span className={`cf-list-line is-${l.tone}${l.attention ? " is-attention" : ""}`}>
          <span className={`cf-dot is-${l.tone === "accent" ? "accent" : l.tone === "amber" ? "warning" : l.tone === "green" ? "done" : "pending"}`} aria-hidden="true" />
          {l.text}
        </span>
      </button>
      {actions && <div className="cf-list-actions">{actions}</div>}
    </li>
  );
}

/**
 * Email-client style list of applications: search, New application, active rows,
 * then a quiet Settled group. Reused by the reviewer queue with its own rows and line function.
 */
export const ApplicationList = forwardRef<ApplicationListHandle, {
  title?: string;
  items: ApplicationSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onNew?: () => void;
  loading?: boolean;
  error?: string;
  /** Shown above the rows (for example "Not saved to an account. This visit only."). */
  note?: ReactNode;
  empty?: ReactNode;
  rowActions?: (a: ApplicationSummary) => ReactNode;
  lineFor?: (a: ApplicationSummary) => { text: string; tone: string; attention: boolean };
}>(function ApplicationList({ title = "Applications", items, selectedId, onSelect, onNew, loading, error, note, empty, rowActions, lineFor }, ref) {
  const [query, setQuery] = useState("");
  const search = useRef<HTMLInputElement>(null);
  useImperativeHandle(ref, () => ({ focusSearch: () => search.current?.focus() }), []);
  const { active, settled } = groupApplications(items, query);
  return (
    <aside className="cf-list" aria-label={title}>
      <div className="cf-list-head">
        <h2>{title}</h2>
        <div className="cf-list-tools">
          {onNew && (
            <button type="button" className="cf-icon-btn is-plain cf-list-new" aria-label="New application" title="New application" onClick={onNew}>
              <Icon24 name="compose" size={17} />
            </button>
          )}
        </div>
      </div>
      <label className="cf-list-search">
        <Icon24 name="search" size={15} />
        <span className="cf-sr">Search applications</span>
        <input ref={search} type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search applications" onKeyDown={(e) => { if (e.key === "Escape") { setQuery(""); e.currentTarget.blur(); } }} />
        <span className="cf-kbd is-dark" aria-hidden="true">{MOD_KEY} K</span>
      </label>
      <div className="cf-list-scroll">
        {note && <div className="cf-applist-note">{note}</div>}
        {error && <p className="cf-applist-note is-error" role="status">{error}</p>}
        {loading && !items.length && <p className="cf-applist-note" role="status">Loading applications…</p>}
        {!loading && !items.length && !error && (empty ?? <p className="cf-applist-note">No applications yet.</p>)}
        {query && !active.length && !settled.length && items.length > 0 && <p className="cf-applist-note">Nothing matches “{query}”.</p>}
        <ul className="cf-list-rows">
          {active.map((a) => <Row key={a.id} a={a} selected={a.id === selectedId} onSelect={onSelect} actions={rowActions?.(a)} line={lineFor?.(a)} />)}
        </ul>
        {settled.length > 0 && (
          <>
            <div className="cf-list-group">Settled</div>
            <ul className="cf-list-rows is-settled">
              {settled.map((a) => <Row key={a.id} a={a} selected={a.id === selectedId} onSelect={onSelect} actions={rowActions?.(a)} line={lineFor?.(a)} />)}
            </ul>
          </>
        )}
      </div>
    </aside>
  );
});
