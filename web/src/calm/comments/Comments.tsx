/**
 * `#/comments`: everything the Safety Codes Officer wrote about the open application, on its own
 * page. The newest decision leads with its items, each a link to the question that fixes it; then
 * what was said after it, any sent information request, and the earlier history. Messages are one
 * way: the applicant answers a return by fixing and resending, never by replying here.
 *
 * The thread is marked read only once this page, for this application, is visible with every
 * unread message on it. Late answers for another application or account are dropped.
 */
import { useEffect, useMemo, useState } from "react";
import { accounts, type ApplicationSummary, type Message, type MessageItem } from "../../api/accounts";
import { EngineError } from "../../api/client";
import { packageReview } from "../../api/packageReview";
import type { SentInformationRequest } from "../../api/types.gen";
import { factLabel } from "../../model";
import { hrefFor, useCase } from "../../store";
import type { Case, Gap } from "../../types";
import { initials, patchApplication, useAccount } from "../account";

import { openAssistant } from "../assistant/assistant";
import { gapKey } from "../deck";
import { Icon24 } from "../icons";
import { calmHref, lastStageHash } from "../routes";
import { CIcon, Dot } from "../ui";
import { useOpenProblem } from "./opening";
import { arrange, counted, displayedIds, earlierStartsOpen, itemsRepeatBody, shouldMarkRead, unshownRequests } from "./thread";
import "./comments.css";

const when = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
};

/**
 * A ticked item from the officer, as a row that opens the question that fixes it. An item with
 * nowhere in Batatis to fix it (a signature, a free-text request) has no link: the unknown-field
 * fallback is Start, which fixes nothing.
 */
export function itemLink(c: Case, gaps: Gap[], item: MessageItem): { label: string; href: string | null } {
  const gap = item.gap_id ? gaps.find((g) => g.id === item.gap_id) : item.field ? gaps.find((g) => g.field === item.field) : undefined;
  const label = item.note?.trim() || gap?.label || (item.field ? factLabel(item.field) : "Item to fix");
  if (gap) {
    const key = gapKey(c, gap);
    return { label, href: key ? `#/questions?focus=${encodeURIComponent(key)}` : calmHref(gap.href) };
  }
  const href = item.field ? calmHref(hrefFor(item.field)) : null;
  return { label, href: href && href !== "#/" ? href : null };
}

function useVisible(): boolean {
  const [visible, setVisible] = useState(() => typeof document === "undefined" || document.visibilityState !== "hidden");
  useEffect(() => {
    const on = () => setVisible(document.visibilityState !== "hidden");
    document.addEventListener("visibilitychange", on);
    return () => document.removeEventListener("visibilitychange", on);
  }, []);
  return visible;
}

/** A closed file's state, in a few words; acceptance keeps its boundary (not a design approval). */
const SETTLED_LINE: Partial<Record<ApplicationSummary["status"], { label: string; note?: string; tone: "done" | "blocking" | "pending" }>> = {
  refused: { label: "Refused · read-only", tone: "blocking" },
  accepted: { label: "Accepted · administratively complete", note: "not a design approval", tone: "done" },
  withdrawn: { label: "Withdrawn · read-only", tone: "pending" },
};

const author = (m: Message) => (m.author.role === "reviewer" ? m.author.name || "The officer" : "You");

/** One comment in the thread (a status line stays a quiet line of history). */
function note(m: Message, fresh: boolean) {
  if (m.kind === "status") return <li key={m.id} className="cf-comment-status"><span>{m.body}</span> · {when(m.created_at)}</li>;
  return (
    <li key={m.id} className="cf-comment">
      <p className="cf-comment-meta">
        {fresh && <span className="cf-comment-new" aria-label="New" />}
        {author(m)} · {when(m.created_at)}
      </p>
      <p className="cf-comment-body">{m.body}</p>
      {m.items.length > 0 && !itemsRepeatBody(m) && (
        <ul className="cf-comment-plain">{m.items.map((it, i) => <li key={i}>{it.note || (it.field ? factLabel(it.field) : "")}</li>)}</ul>
      )}
    </li>
  );
}

export function Comments({ caseParam }: { caseParam: string | null }) {
  const { c, gaps, engineId } = useCase();
  const account = useAccount();
  const problem = useOpenProblem();
  const visible = useVisible();
  const accountId = account.user?.id ?? null;
  // A link for another application waits for the shell's guarded switch; it never shows this one's thread.
  const waiting = Boolean(caseParam && caseParam !== engineId);
  const app: ApplicationSummary | null = (!waiting && engineId && account.applications?.find((a) => a.id === engineId)) || null;
  const key = app ? `${accountId}:${app.id}` : null;

  const [loaded, setLoaded] = useState<{ key: string; messages: Message[]; fresh: ReadonlySet<string> } | null>(null);
  const [requests, setRequests] = useState<{ key: string; list: SentInformationRequest[] } | null>(null);
  const [error, setError] = useState<{ key: string; text: string } | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!app || !key) return;
    let live = true;
    setError(null);
    accounts.messages(app.id).then(
      (m) => { if (live) setLoaded({ key, messages: m, fresh: new Set(m.filter(counted).map((x) => x.id)) }); },
      (e: unknown) => { if (live) setError({ key, text: e instanceof EngineError ? e.detail : "The officer’s comments did not load." }); },
    );
    // A sent information request reaches the applicant while the officer still has the file.
    if (app.status === "in_review") {
      packageReview.sent(app.id).then((r) => { if (live) setRequests({ key, list: r.requests }); }, () => undefined);
    }
    return () => { live = false; };
  }, [key, app?.status, app?.updated_at, attempt]); // eslint-disable-line react-hooks/exhaustive-deps

  const messages = loaded && loaded.key === key ? loaded.messages : null;
  const fresh = loaded && loaded.key === key ? loaded.fresh : new Set<string>();
  const failed = error && error.key === key ? error.text : "";
  const thread = useMemo(() => arrange(messages ?? []), [messages]);
  const sent = unshownRequests(requests && requests.key === key ? requests.list : [], messages ?? []);

  // Read receipts: only for what this visible page shows, for this application.
  useEffect(() => {
    if (!app || !key || !shouldMarkRead({ messages, displayed: displayedIds(thread), visible, sameApplication: true })) return;
    let live = true;
    accounts.markRead(app.id).then(() => {
      if (!live) return;
      setLoaded((l) => (l && l.key === key ? { ...l, messages: l.messages.map((m) => ({ ...m, read_by_me: true })) } : l));
      patchApplication(app.id, { unread_messages: 0 });
    }, () => undefined);
    return () => { live = false; };
  }, [key, messages, thread, visible]); // eslint-disable-line react-hooks/exhaustive-deps

  const back = lastStageHash();
  const head = (
    <div className="cf-comments-head">
      <a className="cf-comments-back" href={back} aria-label="Back to the application"><CIcon name="back" size={15} /><span>Back</span></a>
      <h1 className="cf-comments-title"><Icon24 name="msg" size={18} />Comments</h1>
    </div>
  );

  if (waiting) {
    return (
      <div className="cf-comments">
        {head}
        {problem && problem.id === caseParam
          ? <p className="cf-comments-note" role="alert"><Dot tone="blocking" />{problem.text}</p>
          : <p className="cf-comments-note" role="status">Opening…</p>}
      </div>
    );
  }
  if (!app) {
    return (
      <div className="cf-comments">
        {head}
        <p className="cf-comments-empty">No comments yet</p>
      </div>
    );
  }

  const refused = app.status === "refused";
  const status = SETTLED_LINE[app.status] ?? null;
  const lead = thread.latest;
  // Fix links only while the file is back with the applicant; a refusal is final, never "fix and resend".
  const rows = app.status === "returned" && lead ? lead.items.map((it) => itemLink(c, gaps, it)) : [];
  const fixable = rows.filter((r): r is { label: string; href: string } => Boolean(r.href));
  const who = lead?.author.name || app.reviewer?.name || "The officer";

  return (
    <div className="cf-comments" data-application-id={app.id}>
      {head}
      {status && <p className="cf-comments-state"><Dot tone={status.tone} /><span>{status.label}</span>{status.note && <span className="cf-faint"> · {status.note}</span>}</p>}
      {messages === null && !failed && <p className="cf-comments-note" role="status">Loading…</p>}
      {failed && (
        <p className="cf-comments-note" role="alert">
          {failed} <button type="button" className="cf-btn is-xs" onClick={() => setAttempt((n) => n + 1)}><CIcon name="retry" size={13} />Try again</button>
        </p>
      )}
      {messages && !lead && !sent.length && !thread.earlier.length && <p className="cf-comments-empty">No comments yet</p>}

      {lead && (
        <article className="cf-comment-lead" aria-labelledby="cf-comment-lead-who">
          <span className="cf-returned-av" aria-hidden="true">{initials(who) || "?"}</span>
          <div className="cf-comment-lead-body">
            <h2 className="cf-comment-lead-who" id="cf-comment-lead-who">
              {fresh.has(lead.id) && <span className="cf-comment-new" aria-label="New" />}
              {who}
              <span> · {when(lead.created_at)}</span>
            </h2>
            <p className="cf-comment-body">{lead.body}</p>
            {rows.length > 0 && (
              <ul className="cf-comment-items" aria-label="To fix">
                {rows.map((r, i) => (
                  <li key={i}>
                    {r.href
                      ? <a href={r.href}><span className="cf-dot is-blocking" aria-hidden="true" />{r.label}<Icon24 name="right" size={14} /></a>
                      : <span className="cf-comment-item-plain"><span className="cf-dot is-blocking" aria-hidden="true" />{r.label}</span>}
                  </li>
                ))}
              </ul>
            )}
            {!rows.length && lead.items.length > 0 && !itemsRepeatBody(lead) && <ul className="cf-comment-plain">{lead.items.map((it, i) => <li key={i}>{it.note || (it.field ? factLabel(it.field) : "")}</li>)}</ul>}
            <div className="cf-comment-acts">
              {fixable.length > 0 && <a className="cf-btn is-primary is-sm" href={fixable[0].href}>Fix {fixable.length} {fixable.length === 1 ? "item" : "items"}</a>}
              {app.status === "returned" && !fixable.length && <a className="cf-btn is-primary is-sm" href="#/review">See what’s missing</a>}
              <button
                type="button"
                className="cf-btn is-ghost is-sm"
                onClick={() => openAssistant({ screen: "message", focus: { kind: "message", id: lead.id }, label: "the officer’s comment", suggestions: refused ? ["Explain this refusal", "Explain the appeal notice"] : ["What do I need to change?", "Explain this comment"] }, refused ? "Explain the officer’s refusal and appeal notice in plain words." : "Explain this comment in plain words. What do I need to change?")}
              >
                <Icon24 name="spark" size={15} />Explain
              </button>
            </div>
          </div>
        </article>
      )}

      {sent.length > 0 && (
        <section className="cf-comment-group" aria-label="Information requested">
          {[...sent].reverse().map((r) => (
            <div key={r.sent_at} className="cf-comment">
              <p className="cf-comment-meta">{r.sent_by_name || app.reviewer?.name || "The officer"} · {when(r.sent_at)}</p>
              <p className="cf-comment-body">{r.intro}</p>
              <ol className="cf-comment-plain">{r.items.map((t, i) => <li key={i}>{t}</li>)}</ol>
              <p className="cf-faint cf-small">Comes back to you to update</p>
            </div>
          ))}
        </section>
      )}

      {thread.since.length > 0 && (
        <ol className="cf-comment-group" aria-label="Since then">
          {thread.since.map((m) => note(m, fresh.has(m.id)))}
        </ol>
      )}

      {/* History is one click away; it starts open only when it holds something unread, so the
          thread is never marked read with a message folded out of sight. */}
      {thread.earlier.length > 0 && (
        <details key={key} className="cf-comment-earlier" open={earlierStartsOpen(thread, fresh)}>
          <summary className="cf-comment-earlier-h">Earlier<span className="cf-faint"> · {thread.earlier.length}</span></summary>
          <ol className="cf-comment-group">
            {thread.earlier.map((m) => note(m, fresh.has(m.id)))}
          </ol>
        </details>
      )}
    </div>
  );
}
