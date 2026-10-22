import { useEffect, useMemo, useState } from "react";
import { accounts, type ApplicationSummary, type Message, type MessageItem } from "../../api/accounts";
import { EngineError } from "../../api/client";
import { factLabel } from "../../model";
import { hrefFor, useCase } from "../../store";
import type { Case, Gap } from "../../types";
import { initials, patchApplication } from "../account";
import { authorityName } from "../applications";
import { openAssistant } from "../assistant/assistant";
import { gapKey } from "../deck";
import { Icon24 } from "../icons";
import { calmHref } from "../routes";

const when = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
};

/** A ticked item from the officer, as a row that opens the question that fixes it. */
export function itemLink(c: Case, gaps: Gap[], item: MessageItem): { label: string; href: string } {
  const gap = item.gap_id ? gaps.find((g) => g.id === item.gap_id) : item.field ? gaps.find((g) => g.field === item.field) : undefined;
  const label = item.note?.trim() || gap?.label || (item.field ? factLabel(item.field) : "Item to fix");
  if (gap) {
    const key = gapKey(c, gap);
    return { label, href: key ? `#/questions?focus=${encodeURIComponent(key)}` : calmHref(gap.href) };
  }
  return { label, href: item.field ? calmHref(hrefFor(item.field)) : "#/review" };
}

/**
 * The officer's return or final refusal. Messages are one way (officer to applicant): the applicant
 * answers a return by fixing the items and sending the application again, never by replying.
 */
export function ReturnedBanner({ app }: { app: ApplicationSummary }) {
  const { c, gaps } = useCase();
  const refused = app.status === "refused";
  const [messages, setMessages] = useState<Message[] | null>(null);
  /** Unread when this load arrived: they stay on screen after being marked read. */
  const [unreadAtLoad, setUnreadAtLoad] = useState<ReadonlySet<string>>(() => new Set());
  const [error, setError] = useState("");
  // Bumped by "Try again"; the effect below owns the request, so a late answer for another file is dropped.
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    setMessages(null);
    setError("");
    accounts
      .messages(app.id)
      .then((m) => {
        if (!live) return;
        setMessages(m);
        setUnreadAtLoad(new Set(m.filter((x) => !x.read_by_me).map((x) => x.id)));
      })
      .catch((e: unknown) => { if (live) setError(e instanceof EngineError ? e.detail : "The officer’s message did not load."); });
    return () => { live = false; };
  }, [app.id, app.status, app.updated_at, attempt]);

  const { latest, correspondence } = useMemo(() => {
    const ordered = [...(messages ?? [])].sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at));
    const fromOfficer = ordered.filter((m) => m.author.role === "reviewer" && m.kind !== "status");
    // The latest decision leads (a return carries its items there); without one, the latest officer message.
    const decisions = fromOfficer.filter((m) => m.kind === "decision");
    const latest = refused ? decisions[decisions.length - 1] : decisions[decisions.length - 1] ?? fromOfficer[fromOfficer.length - 1];
    const after = ordered.slice(latest ? ordered.indexOf(latest) + 1 : 0);
    // Refused: both sides' correspondence since. Returned: the officer's notes sent with or after the
    // return, and any earlier officer message still unread (an applicant can resend without opening it).
    const notes = latest ? fromOfficer.filter((m) => m !== latest && (after.includes(m) || unreadAtLoad.has(m.id))) : [];
    return { latest, correspondence: refused ? after : notes };
  }, [messages, refused, unreadAtLoad]);

  // The read endpoint clears the whole thread. Only call it after rendering every unread message;
  // earlier correspondence is not displayed. Status lines are not messages and are never counted.
  useEffect(() => {
    const counted = (m: Message) => !m.read_by_me && m.kind !== "status";
    if (!messages?.some(counted)) return;
    const visible = new Set([...(latest ? [latest.id] : []), ...correspondence.map((m) => m.id)]);
    if (messages.some((m) => counted(m) && !visible.has(m.id))) return;
    let live = true;
    accounts.markRead(app.id).then(() => {
      if (!live) return;
      setMessages((list) => list?.map((m) => visible.has(m.id) ? { ...m, read_by_me: true } : m) ?? null);
      patchApplication(app.id, { unread_messages: 0 });
    }).catch(() => {});
    return () => { live = false; };
  }, [app.id, messages, latest, correspondence]);

  const rows = refused ? [] : (latest?.items ?? []).map((it) => itemLink(c, gaps, it));
  const who = latest?.author.name || app.reviewer?.name || "The officer";
  const where = authorityName(app.authority);

  return (
    <section className="cf-returned" aria-labelledby="cf-returned-who">
      <span className="cf-returned-av" aria-hidden="true">{initials(who) || "?"}</span>
      <div className="cf-returned-body">
        <h2 className="cf-returned-who" id="cf-returned-who">
          {who} <span>· {where ? `Safety Codes Officer, ${where} · ` : ""}{refused ? "refused" : "returned"} this{latest ? ` ${when(latest.created_at)}` : ""}</span>
        </h2>
        {messages === null && !error && <p className="cf-faint" role="status">Loading the officer’s message…</p>}
        {error && (
          <p className="cf-faint cf-returned-retry" role="status">
            {error} <button type="button" className="cf-btn is-xs" onClick={() => setAttempt((n) => n + 1)}>Try again</button>
          </p>
        )}
        {latest && <p className="cf-returned-msg">{latest.body}</p>}
        {messages && !latest && <p className="cf-returned-msg cf-muted">{refused ? "A refusal was recorded. Contact the officer for the written notice and appeal information." : "Returned for administrative information. Open the review to see what is missing."}</p>}
        {refused && <p className="cf-faint cf-small">Closed · read-only</p>}
        {rows.length > 0 && (
          <ul className="cf-returned-items">
            {rows.map((r) => (
              <li key={r.label + r.href}>
                <a href={r.href}><span className="cf-dot is-blocking" aria-hidden="true" />{r.label}<Icon24 name="right" size={14} /></a>
              </li>
            ))}
          </ul>
        )}
        {correspondence.length > 0 && (
          <ol className="cf-returned-items" aria-label={refused ? "Correspondence after refusal" : "The officer’s notes"}>
            {correspondence.map((m) => (
              <li key={m.id}>
                <p className="cf-faint cf-small">{m.author.role === "reviewer" ? m.author.name || "The officer" : "You"} · {when(m.created_at)}</p>
                <p className="cf-returned-msg">{m.body}</p>
                {m.items.length > 0 && !m.items.every((it) => it.note && m.body.includes(it.note.trim())) && (
                  <ul className="cf-returned-items">{m.items.map((it, i) => <li key={i}>{it.note || it.field}</li>)}</ul>
                )}
              </li>
            ))}
          </ol>
        )}
        <div className="cf-returned-acts">
          {rows.length > 0 && <a className="cf-btn is-primary is-sm" href={rows[0].href}>Fix {rows.length} {rows.length === 1 ? "item" : "items"}</a>}
          {!refused && !rows.length && <a className="cf-btn is-primary is-sm" href="#/review">See what’s missing</a>}
          {latest && (
            <button
              type="button"
              className="cf-btn is-ghost is-sm"
              onClick={() => openAssistant({ screen: "message", focus: { kind: "message", id: latest.id }, label: "the officer’s message", suggestions: refused ? ["Explain this refusal", "Explain the appeal notice"] : ["What do I need to change?", "Explain this message"] }, refused ? "Explain the officer’s refusal and appeal notice in plain words." : "Explain this message in plain words. What do I need to change?")}
            >
              <Icon24 name="spark" size={15} />Explain this message
            </button>
          )}
        </div>
      </div>
    </section>
  );
}
