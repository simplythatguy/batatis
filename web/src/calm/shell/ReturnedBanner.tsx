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
 * The officer's return or final refusal. A refusal keeps the message thread available without
 * offering application edits or resubmission.
 */
export function ReturnedBanner({ app }: { app: ApplicationSummary }) {
  const { c, gaps } = useCase();
  const refused = app.status === "refused";
  const [messages, setMessages] = useState<Message[] | null>(null);
  const [error, setError] = useState("");
  const [replying, setReplying] = useState(false);
  const [reply, setReply] = useState("");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState("");

  useEffect(() => {
    let live = true;
    setMessages(null);
    setError("");
    accounts
      .messages(app.id)
      .then((m) => {
        if (!live) return;
        setMessages(m);
      })
      .catch((e: unknown) => { if (live) setError(e instanceof EngineError ? e.detail : "The officer’s message did not load."); });
    return () => { live = false; };
  }, [app.id, app.status, app.updated_at]);

  const { latest, correspondence } = useMemo(() => {
    const ordered = [...(messages ?? [])].sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at));
    const fromOfficer = ordered.filter((m) => m.author.role === "reviewer" && (refused ? m.kind === "decision" : m.kind !== "status"));
    const latest = fromOfficer[fromOfficer.length - 1];
    return { latest, correspondence: refused ? ordered.slice(latest ? ordered.indexOf(latest) + 1 : 0) : [] };
  }, [messages, refused]);

  // The read endpoint clears the whole thread. Only call it after rendering every unread message;
  // earlier correspondence and the return banner's reply count are not displayed message bodies.
  useEffect(() => {
    if (!messages?.some((m) => !m.read_by_me)) return;
    const visible = new Set([...(latest ? [latest.id] : []), ...correspondence.map((m) => m.id)]);
    if (messages.some((m) => !m.read_by_me && !visible.has(m.id))) return;
    let live = true;
    accounts.markRead(app.id).then(() => {
      if (!live) return;
      setMessages((list) => list?.map((m) => visible.has(m.id) ? { ...m, read_by_me: true } : m) ?? null);
      patchApplication(app.id, { unread_messages: 0 });
    }).catch(() => {});
    return () => { live = false; };
  }, [app.id, messages, latest, correspondence]);

  const rows = refused ? [] : (latest?.items ?? []).map((it) => itemLink(c, gaps, it));
  const mine = (messages ?? []).filter((m) => latest && m.author.role !== "reviewer" && m.kind === "message" && m.created_at > latest.created_at);
  const who = latest?.author.name || app.reviewer?.name || "The officer";
  const where = authorityName(app.authority);

  async function send() {
    const body = reply.trim();
    if (!body || sending) return;
    setSending(true);
    setSent("");
    try {
      const m = await accounts.postMessage(app.id, body);
      setMessages((list) => [...(list ?? []), m]);
      setReply("");
      setReplying(false);
      setSent("Reply sent to the officer.");
    } catch (e) {
      setSent(e instanceof EngineError ? e.detail : "The reply was not sent. Your text is still here.");
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="cf-returned" aria-labelledby="cf-returned-who">
      <span className="cf-returned-av" aria-hidden="true">{initials(who) || "?"}</span>
      <div className="cf-returned-body">
        <h2 className="cf-returned-who" id="cf-returned-who">
          {who} <span>· {where ? `Safety Codes Officer, ${where} · ` : ""}{refused ? "refused" : "returned"} this{latest ? ` ${when(latest.created_at)}` : ""}</span>
        </h2>
        {messages === null && !error && <p className="cf-faint" role="status">Loading the officer’s message…</p>}
        {error && <p className="cf-faint" role="status">{error}</p>}
        {latest && <p className="cf-returned-msg">{latest.body}</p>}
        {messages && !latest && <p className="cf-returned-msg cf-muted">{refused ? "A refusal was recorded. Contact the officer for the written notice and appeal information." : "Returned for administrative information. Open the review to see what is missing."}</p>}
        {refused && <p className="cf-faint cf-small">This application is closed and read-only. You can still reply to the officer.</p>}
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
          <ol className="cf-returned-items" aria-label="Correspondence after refusal">
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
        {!refused && mine.length > 0 && <p className="cf-faint cf-small">You replied {mine.length === 1 ? "once" : `${mine.length} times`}. The officer sees it with the application.</p>}
        <div className="cf-returned-acts">
          {rows.length > 0 && <a className="cf-btn is-primary is-sm" href={rows[0].href}>Fix {rows.length} {rows.length === 1 ? "item" : "items"}</a>}
          {!refused && !rows.length && <a className="cf-btn is-primary is-sm" href="#/review">See what’s missing</a>}
          <button type="button" className="cf-btn is-sm" aria-expanded={replying} onClick={() => setReplying((v) => !v)}><Icon24 name="msg" size={15} />Reply</button>
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
        {replying && (
          <form className="cf-composer-box cf-returned-reply" onSubmit={(e) => { e.preventDefault(); void send(); }}>
            <label className="cf-sr" htmlFor="cf-reply">Reply to {who}</label>
            <textarea id="cf-reply" rows={3} maxLength={4000} value={reply} autoFocus onChange={(e) => setReply(e.target.value)} placeholder={`Reply to ${who}…`}
              onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); void send(); } if (e.key === "Escape") setReplying(false); }} />
            <div className="cf-composer-box-foot">
              <span className="cf-faint cf-small">Plain text. The officer sees it with your application.</span>
              <button type="submit" className="cf-btn is-sm" disabled={!reply.trim() || sending}>{sending ? "Sending…" : "Send"}</button>
            </div>
          </form>
        )}
        {sent && <p className="cf-faint cf-small" role="status">{sent}</p>}
      </div>
    </section>
  );
}
