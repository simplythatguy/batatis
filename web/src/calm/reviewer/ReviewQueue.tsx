/** #/review for reviewers: everything sent to their authority, with who is reviewing what. */
import { Fragment, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { AccountsError, claimConflict, review, type Claim, type QueueApplication } from "../../api/accounts";
import { useAccount } from "../account";
import { authorityName } from "../applications";
import { AcIcon, Avatar, PageHead } from "../auth/bits";
import { ConfirmDialog, MOD_KEY } from "../ui";
import { applicantLine, completenessView, filterQueue, reviewerCell, rowAction, sentLabel, statusPill, tabCounts, TABS, type QueueTab } from "./queue";
import { loadQueue, patchRow, useQueue } from "./reviewData";

export function ProgressRing({ pct, size = 18 }: { pct: number | null; size?: number }) {
  const r = size / 2 - 1.5;
  const c = 2 * Math.PI * r;
  const p = pct == null ? 0 : Math.max(0, Math.min(100, pct));
  return (
    <svg className={`ac-ring${p >= 100 ? " is-full" : ""}${pct == null ? " is-unknown" : ""}`} width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
      <circle className="ac-ring-trk" cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth="1.75" />
      {p > 0 && <circle className="ac-ring-arc" cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth="1.75" strokeDasharray={`${(p / 100) * c} ${c}`} transform={`rotate(-90 ${size / 2} ${size / 2})`} />}
    </svg>
  );
}

export function StatusPill({ a }: { a: Pick<QueueApplication, "status" | "claim"> }) {
  const s = statusPill(a.status, Boolean(a.claim));
  return <span className="ac-pill"><span className={`ac-pill-dot is-${s.tone}`} aria-hidden="true" />{s.label}</span>;
}

interface RowState {
  busy?: boolean;
  conflict?: Claim;
  error?: string;
}

export function ReviewQueue({ phoneTools }: { phoneTools?: ReactNode }) {
  const { user } = useAccount();
  const q = useQueue();
  const me = user?.id ?? null;
  const [tab, setTab] = useState<QueueTab>("all");
  const [query, setQuery] = useState("");
  const [rowState, setRowState] = useState<Record<string, RowState>>({});
  const [takeOver, setTakeOver] = useState<{ id: string; claim: Claim } | null>(null);
  const search = useRef<HTMLInputElement>(null);
  const [now] = useState(() => Date.now());

  useEffect(() => { void loadQueue(); }, []);

  // ⌘K / Ctrl+K searches the queue here (captured before the shell's own shortcut).
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey) || e.altKey || e.shiftKey || e.key.toLowerCase() !== "k") return;
      e.preventDefault();
      e.stopPropagation();
      search.current?.focus();
      search.current?.select();
    };
    window.addEventListener("keydown", on, true);
    return () => window.removeEventListener("keydown", on, true);
  }, []);

  const counts = useMemo(() => tabCounts(q.rows, me), [q.rows, me]);
  const rows = useMemo(() => filterQueue(q.rows, tab, query, me), [q.rows, tab, query, me]);
  const authority = authorityName(user?.authority);
  const setRow = (id: string, s: RowState) => setRowState((m) => ({ ...m, [id]: s }));

  async function claim(id: string, over = false) {
    setRow(id, { busy: true });
    try {
      const c = await review.claim(id, over);
      patchRow(id, { status: "in_review", claim: c });
      setRow(id, {});
      location.hash = `#/review/${encodeURIComponent(id)}`;
    } catch (e) {
      const conflict = claimConflict(e);
      if (conflict) {
        patchRow(id, { claim: conflict, status: "in_review" });
        setRow(id, { conflict });
      } else {
        setRow(id, { error: e instanceof AccountsError ? e.detail : "That didn’t work. Try again." });
        void loadQueue();
      }
    }
  }

  const open = (id: string) => `#/review/${encodeURIComponent(id)}`;

  return (
    <div className="ac-page">
      <PageHead
        title="Review queue"
        meta={authority ? `· ${authority}` : undefined}
        phoneTools={phoneTools}
        right={
          <label className="ac-search">
            <AcIcon name="search" size={15} />
            <span className="cf-sr">Search applications</span>
            <input ref={search} type="search" placeholder="Search" value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => { if (e.key === "Escape" && query) { e.preventDefault(); setQuery(""); } }} />
            {!query && <kbd className="ac-search-kbd" aria-hidden="true">{MOD_KEY} K</kbd>}
          </label>
        }
      />
      <div className="ac-page-body">
        <div className="ac-queue-head">
          <div>
            <h2 className="ac-h1">{q.phase === "ready" || q.rows.length ? `${counts.all} ${counts.all === 1 ? "application" : "applications"}` : "Applications"}</h2>
            <p className="ac-lead">{authority ? `Sent to ${authority}. ` : ""}Pick one up to let other officers know you’ve got it. A package from outside Batatis? <a className="ac-link" href="#/review/package">Review its PDFs</a>.</p>
          </div>
          <div className="ac-tabs" role="group" aria-label="Filter applications">
            {TABS.map((t) => (
              <button key={t.id} type="button" aria-pressed={tab === t.id} className="ac-tab" onClick={() => setTab(t.id)}>
                {t.label} <span className="ac-tab-n">{counts[t.id]}</span>
              </button>
            ))}
          </div>
        </div>

        {q.error && q.rows.length > 0 && (
          <p className="ac-empty" role="status">{q.error} These rows may be out of date. <button type="button" className="ac-link" onClick={() => void loadQueue()}>Try again</button></p>
        )}
        {q.phase === "error" && !q.rows.length ? (
          <p className="ac-empty">{q.error || "The queue didn’t load."} <button type="button" className="ac-link" onClick={() => void loadQueue()}>Try again</button></p>
        ) : q.phase !== "ready" && !q.rows.length ? (
          <p className="ac-empty">Loading the queue…</p>
        ) : !q.rows.length ? (
          <p className="ac-empty">No applications have been sent to {authority || "your authority"} yet.</p>
        ) : !rows.length ? (
          <p className="ac-empty">{query ? `No applications match “${query.trim()}”.` : "Nothing here right now."}</p>
        ) : (
          <table className="ac-table">
            <thead>
              <tr>
                <th scope="col">Application</th>
                <th scope="col">Applicant</th>
                <th scope="col">Sent</th>
                <th scope="col">Completeness</th>
                <th scope="col">Status</th>
                <th scope="col">Reviewer</th>
                <th scope="col"><span className="cf-sr">Action</span></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((a) => {
                const rs = rowState[a.id] ?? {};
                const who = reviewerCell(a, me);
                const action = rowAction(a, me);
                const comp = completenessView(a.completeness, q.blocking[a.id] ?? null);
                const title = a.title?.trim() || "Untitled application";
                return (
                  <Fragment key={a.id}>
                  <tr className={rs.conflict ? "has-note" : undefined}>
                    <td className="ac-td-title" data-label="Application">
                      <a href={open(a.id)} className="ac-row-link">{title}</a>
                      {a.unread_messages > 0 && <span className="ac-unread"><span className="ac-note-dot" aria-hidden="true" />{a.unread_messages} unread</span>}
                    </td>
                    <td className="ac-muted-cell" data-label="Applicant">{applicantLine(a)}</td>
                    <td className="ac-muted-cell" data-label="Sent">{sentLabel(a.submitted_at, now)}</td>
                    <td data-label="Completeness">
                      <span className="ac-comp" title={comp.pct == null ? "Checking…" : undefined}><ProgressRing pct={comp.pct} />{comp.label}</span>
                    </td>
                    <td data-label="Status"><StatusPill a={a} /></td>
                    <td data-label="Reviewer">
                      {who.name ? <span className="ac-claim"><Avatar name={who.name} size="sm" />{who.label}</span> : <span className="ac-faint">—</span>}
                    </td>
                    <td className="ac-td-action">
                      {action === "claim" && !rs.conflict ? (
                        <button type="button" className="cf-btn is-sm" disabled={rs.busy} onClick={() => void claim(a.id)}>
                          <AcIcon name="hand" size={15} />{rs.busy ? "Starting…" : "Start reviewing"}
                        </button>
                      ) : (
                        <a className="cf-btn is-sm is-ghost" href={open(a.id)}>{action === "open" ? "Open" : "View"}</a>
                      )}
                      {rs.error && <p className="ac-error is-row" role="alert">{rs.error}</p>}
                    </td>
                  </tr>
                  {rs.conflict && (
                    <tr className="ac-conflict-row">
                      <td colSpan={7}>
                        <div className="ac-conflict" role="status">
                          <span>{rs.conflict.reviewer_name} is already reviewing this</span>
                          <a className="cf-btn is-xs is-ghost" href={open(a.id)}>View</a>
                          <button type="button" className="cf-btn is-xs" onClick={() => setTakeOver({ id: a.id, claim: rs.conflict! })}>Take over</button>
                          <button type="button" className="cf-btn is-xs is-ghost" onClick={() => setRow(a.id, {})}>Dismiss</button>
                        </div>
                      </td>
                    </tr>
                  )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
      <ConfirmDialog
        open={Boolean(takeOver)}
        title="Take over this review?"
        body={<p>{takeOver?.claim.reviewer_name} started reviewing this application. If you take over, you become the reviewer and the history records both names.</p>}
        cancel="Keep theirs"
        confirm="Take over"
        onClose={() => setTakeOver(null)}
        onConfirm={() => {
          const t = takeOver;
          setTakeOver(null);
          if (t) void claim(t.id, true);
        }}
      />
    </div>
  );
}
