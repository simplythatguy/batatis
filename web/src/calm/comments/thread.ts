/**
 * The officer's comments on one application, arranged for the comments page: the newest decision
 * first, everything said after it, then the earlier history. Nothing is dropped, so every unread
 * message is on screen before the thread is marked read (the read route clears the whole thread).
 */
import type { ApplicationStatus, Message } from "../../api/accounts";

export interface Thread {
  /** The newest decision (a return or refusal carries its reasons there); else the newest officer note. */
  latest: Message | null;
  /** Everything after `latest`, oldest first: officer follow-ups and any earlier applicant messages. */
  since: Message[];
  /** Everything before `latest`, newest first, status lines included as history. */
  earlier: Message[];
}

const byTime = (a: Message, b: Message) => Date.parse(a.created_at) - Date.parse(b.created_at);

export function arrange(messages: readonly Message[]): Thread {
  const ordered = [...messages].sort(byTime);
  const officer = ordered.filter((m) => m.author.role === "reviewer" && m.kind !== "status");
  const decisions = officer.filter((m) => m.kind === "decision");
  const latest = decisions.at(-1) ?? officer.at(-1) ?? null;
  const at = latest ? ordered.indexOf(latest) : ordered.length;
  return {
    latest,
    since: latest ? ordered.slice(at + 1) : [],
    earlier: ordered.slice(0, at).reverse(),
  };
}

/** Messages that count toward the unread badge (status lines never do). */
export const counted = (m: Message) => !m.read_by_me && m.kind !== "status";

/**
 * Mark the thread read only when this page shows the right application, is actually visible, and
 * every counted unread message is among those displayed.
 */
export function shouldMarkRead(input: { messages: readonly Message[] | null; displayed: ReadonlySet<string>; visible: boolean; sameApplication: boolean }): boolean {
  const { messages, displayed, visible, sameApplication } = input;
  if (!messages || !visible || !sameApplication) return false;
  const unread = messages.filter(counted);
  return unread.length > 0 && unread.every((m) => displayed.has(m.id));
}

export function displayedIds(t: Thread): Set<string> {
  return new Set([...(t.latest ? [t.latest.id] : []), ...t.since.map((m) => m.id), ...t.earlier.map((m) => m.id)]);
}

/** One short line for the top of the workflow: what happened, in a few words. */
export function noticeLine(status: ApplicationStatus): string | null {
  switch (status) {
    case "returned": return "Returned for changes";
    case "refused": return "Refused · read-only";
    case "in_review": return "Information requested";
    default: return null;
  }
}

/** The message body already spells out every item (a sent request's numbered list): don't list them again. */
export function itemsRepeatBody(m: Pick<Message, "body" | "items">): boolean {
  return m.items.length > 0 && m.items.every((it) => Boolean(it.note?.trim()) && m.body.includes(it.note!.trim()));
}

/**
 * Sent information requests the thread does not already show. Sending one also posts it as the
 * officer's message; showing both put the same list on the page twice.
 */
export function unshownRequests<R extends { intro: string }>(requests: readonly R[], messages: readonly Pick<Message, "body">[]): R[] {
  return requests.filter((r) => {
    const intro = r.intro.trim();
    return !intro || !messages.some((m) => m.body.includes(intro));
  });
}

/** Earlier history waits behind one click, except when it holds a message the applicant hasn't read. */
export function earlierStartsOpen(t: Thread, fresh: ReadonlySet<string>): boolean {
  return t.earlier.some((m) => fresh.has(m.id));
}
