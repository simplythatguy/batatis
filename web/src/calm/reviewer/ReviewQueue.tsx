/** #/review for reviewers: everything sent to their authority, one quiet row each. A row opens the file. */
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { review, type QueueApplication } from "../../api/accounts";
import { useAccount } from "../account";
import { authorityName } from "../applications";
import { AcIcon, Avatar, PageHead, type AcIconName } from "../auth/bits";
import { MOD_KEY } from "../ui";
import { completenessView, filterQueue, reviewerCell, sentLabel, statusPill, tabCounts, TABS, type QueueTab } from "./queue";
import { loadQueue, patchRow, useQueue } from "./reviewData";

export function StatusPill({ a }: { a: Pick<QueueApplication, "status" | "claim"> }) {
  const s = statusPill(a.status, Boolean(a.claim));
  const hue = { accent: "accent", warning: "amber", blocking: "rose", done: "green", pending: "slate" }[s.tone];
  return <span className={`ac-pill is-${hue}`}><span className={`ac-pill-dot is-${s.tone}`} aria-hidden="true" />{s.label}</span>;
}

/** Each filter's icon. */
const TAB_ICON: Record<QueueTab, AcIconName> = {
  all: "inbox",
  new: "inbox",
  mine: "hand",
  returned: "send",
  accepted: "check",
  refused: "ban",
};

/** The applicant's own checklist as an icon: green when nothing required is missing. */
function Checklist({ pct, label }: { pct: number | null; label: string }) {
  if (pct == null) return null;
  const ok = label === "Complete" || pct >= 100;
  const text = ok ? "Applicant’s checklist complete" : label.endsWith("missing") ? `${label.replace(" missing", "")} required missing` : `${label} answered`;
  return (
    <span className={`rq-check ${ok ? "is-green" : "is-rose"}`} title={text}>
      <AcIcon name={ok ? "check" : "alert"} size={13} />
      <span className={ok ? "cf-sr" : undefined}>{ok ? text : label.replace(" missing", "")}</span>
    </span>
  );
}

/** What the officer does next with this row, in plain words. */
function nextStep(a: QueueApplication, me: string | null): string {
  if (a.status === "submitted" && !a.claim) return "Pick up";
  if (a.status === "in_review" && me && a.claim?.reviewer_id === me) return "Continue";
  return "View";
}

export function ReviewQueue({ phoneTools }: { phoneTools?: ReactNode }) {
  const { user } = useAccount();
  const q = useQueue();
  const me = user?.id ?? null;
  const [tab, setTab] = useState<QueueTab>("all");
  const [query, setQuery] = useState("");
  const search = useRef<HTMLInputElement>(null);
  const [now] = useState(() => Date.now());
  const [picking, setPicking] = useState("");

  /** "Pick up" means it: claim, then open the review (no second "start" screen). If someone got
   *  there first, the review page says who and offers to take over. */
  async function pickUp(a: QueueApplication, href: string) {
    if (picking) return;
    setPicking(a.id);
    try {
      const claim = await review.claim(a.id, false);
      patchRow(a.id, { claim, status: "in_review" });
    } catch {
      // Fall through: the review page shows the conflict or the error.
    } finally {
      setPicking("");
      window.location.hash = href;
    }
  }

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
  // Only filters with something in them (plus All and the one you're on): fewer things to read.
  const tabs = TABS.filter((t) => t.id === "all" || t.id === tab || counts[t.id] > 0);

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
      <div className="ac-page-body rq">
        <h2 className="cf-sr">Applications</h2>
        {tabs.length > 1 && (
          <div className="ac-tabs rq-tabs" role="group" aria-label="Filter applications">
            {tabs.map((t) => (
              <button key={t.id} type="button" aria-pressed={tab === t.id} className="ac-tab" onClick={() => setTab(t.id)}>
                <AcIcon name={TAB_ICON[t.id]} size={14} />{t.label}<span className="ac-tab-n">{counts[t.id]}</span>
              </button>
            ))}
          </div>
        )}

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
          <ul className="rq-list">
            {rows.map((a) => {
              const who = reviewerCell(a, me);
              const comp = completenessView(a.completeness, q.blocking[a.id] ?? null);
              const title = a.title?.trim() || "Untitled application";
              const step = nextStep(a, me);
              return (
                <li key={a.id}>
                  <a
                    className="rq-row"
                    href={`#/review/${encodeURIComponent(a.id)}`}
                    aria-busy={picking === a.id || undefined}
                    onClick={step === "Pick up" ? (e) => {
                      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
                      e.preventDefault();
                      void pickUp(a, e.currentTarget.getAttribute("href") ?? "");
                    } : undefined}
                  >
                    <span className="rq-main">
                      <span className="rq-title">
                        {title}
                        {a.unread_messages > 0 && <span className="rq-unread"><span className="ac-note-dot" aria-hidden="true" />{a.unread_messages} unread</span>}
                      </span>
                      <span className="rq-meta">
                        {[a.applicant.name, a.submitted_at ? sentLabel(a.submitted_at, now) : ""].filter(Boolean).join(" · ")}
                        <Checklist pct={comp.pct} label={comp.label} />
                      </span>
                    </span>
                    <span className="rq-side">
                      {who.name && <span className="rq-who" title={who.mine ? "You’re reviewing this" : `${who.name} is reviewing this`}><Avatar name={who.name} size="sm" /><span className="rq-who-name">{who.label}</span></span>}
                      {step !== "Pick up" && <StatusPill a={a} />}
                      <span className={`rq-go${step === "Pick up" ? " is-new" : ""}`}>{picking === a.id ? "Picking up…" : step}<AcIcon name="chev" size={14} /></span>
                    </span>
                  </a>
                </li>
              );
            })}
          </ul>
        )}
        <a className="cf-btn is-sm is-ghost rq-foot" href="#/review/package"><AcIcon name="upload" size={15} />Review outside PDFs</a>
      </div>
    </div>
  );
}
