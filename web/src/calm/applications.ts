/** Application list rows: one context line per application, and the quiet Settled group. Pure. */
import type { ApplicationStatus, ApplicationSummary } from "../api/accounts";
import { AUTHORITIES } from "../config";
import { ago } from "./relevance";

export type LineTone = "grey" | "amber" | "accent" | "green";

export interface StatusLine {
  /** The full line. With unread messages it is the accessible name and hover label, not visible text. */
  text: string;
  tone: LineTone;
  /** Draws the accent colour on the line (returned with news). */
  attention: boolean;
  /** Unread officer messages on a returned or refused application: shown as a message icon and the count. */
  unread: number;
}

export const SETTLED: ReadonlySet<ApplicationStatus> = new Set(["accepted", "refused", "withdrawn"]);

export function authorityName(id: string | null | undefined): string {
  if (!id) return "";
  return AUTHORITIES.find((a) => a.id === id)?.name ?? id.charAt(0).toUpperCase() + id.slice(1);
}

export function percent(c: ApplicationSummary["completeness"]): number | null {
  if (!c || !c.total) return null;
  return Math.round((100 * Math.min(c.answered, c.total)) / c.total);
}

export function statusLine(a: ApplicationSummary, now = Date.now()): StatusLine {
  return { unread: 0, ...line(a, now) };
}

function line(a: ApplicationSummary, now: number): Omit<StatusLine, "unread"> & { unread?: number } {
  const where = authorityName(a.authority);
  const join = (...parts: (string | null | undefined | false)[]) => parts.filter(Boolean).join(" · ");
  switch (a.status) {
    case "draft": {
      const p = percent(a.completeness);
      return { text: join("Draft", p != null && `${p}%`, ago(a.updated_at, now)), tone: "grey", attention: false };
    }
    case "submitted":
      return { text: join("Submitted", where), tone: "amber", attention: false };
    case "in_review":
      return { text: join("In review", where), tone: "amber", attention: false };
    case "returned": {
      const n = a.unread_messages;
      return { text: join("Returned", n > 0 ? `${n} new ${n === 1 ? "message" : "messages"}` : "fix and resubmit"), tone: "accent", attention: true, unread: Math.max(0, n) };
    }
    case "accepted":
      return { text: join("Accepted", where), tone: "green", attention: false };
    case "refused": {
      const n = a.unread_messages;
      return { text: join("Refused", n > 0 ? `${n} new ${n === 1 ? "message" : "messages"}` : where), tone: n > 0 ? "accent" : "grey", attention: n > 0, unread: Math.max(0, n) };
    }
    case "withdrawn":
      return { text: "Withdrawn", tone: "grey", attention: false };
    default:
      // A status this client does not know yet must not break the whole list.
      return { text: join(String(a.status ?? "") || "Status unknown", where), tone: "grey", attention: false };
  }
}

export interface ApplicationGroups {
  /** Pinned by the owner, above everything else (any status). */
  pinned: ApplicationSummary[];
  active: ApplicationSummary[];
  settled: ApplicationSummary[];
  /** The owner's archive shelf: out of the main list until restored (a pin waits for the restore). */
  archived: ApplicationSummary[];
}

/** Pinned, then active (newest first), then settled; archived on their own shelf. The search matches the title and authority. */
export function groupApplications(apps: ApplicationSummary[], query = ""): ApplicationGroups {
  const q = query.trim().toLowerCase();
  const shown = apps
    .filter((a) => !q || a.title.toLowerCase().includes(q) || authorityName(a.authority).toLowerCase().includes(q))
    .sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at));
  const live = shown.filter((a) => !a.archived);
  return {
    pinned: live.filter((a) => a.pinned),
    active: live.filter((a) => !a.pinned && !SETTLED.has(a.status)),
    settled: live.filter((a) => !a.pinned && SETTLED.has(a.status)),
    archived: shown.filter((a) => a.archived),
  };
}

const STATUS_WORD: Record<ApplicationStatus, string> = {
  draft: "Draft",
  submitted: "Submitted",
  in_review: "In review",
  returned: "Returned · fix and resubmit",
  // The officer's decision is about administrative completeness only.
  accepted: "Accepted · completeness only",
  refused: "Refused",
  withdrawn: "Withdrawn",
};

export interface PreviewFact {
  icon: "review" | "landmark" | "user" | "questions" | "msg" | "clock" | "archive";
  text: string;
}

/**
 * The row's hover and focus preview: the real summary fields only, one short line each, nothing
 * the server did not send (no score, no verdict).
 */
export function previewFacts(a: ApplicationSummary, now = Date.now()): PreviewFact[] {
  const facts: PreviewFact[] = [{ icon: "review", text: STATUS_WORD[a.status] ?? (String(a.status ?? "") || "Status unknown") }];
  const where = authorityName(a.authority);
  if (where) facts.push({ icon: "landmark", text: where });
  if (a.reviewer?.name) facts.push({ icon: "user", text: a.reviewer.name });
  const c = a.completeness;
  if (c && c.total > 0) facts.push({ icon: "questions", text: `${Math.min(c.answered, c.total)} of ${c.total} answered` });
  const n = statusLine(a, now).unread;
  if (n > 0) facts.push({ icon: "msg", text: `${n} new ${n === 1 ? "message" : "messages"}` });
  const when = ago(a.updated_at, now);
  if (when) facts.push({ icon: "clock", text: `Updated ${when}` });
  if (a.archived) facts.push({ icon: "archive", text: "Archived" });
  return facts;
}

/** Only draft and returned records are editable, including when a newer server adds a final status. */
export const readOnly = (s: string | null | undefined) => s != null && s !== "draft" && s !== "returned";

/**
 * Shared wording for a read-only application: the header label, the heading and note on Review, the
 * questions and the saved form, and what the applicant can do next. A final status never promises a return.
 */
export function readOnlyStatus(status: string | null | undefined, authority?: string | null): {
  label: string;
  heading: string;
  note: string;
  next: string;
  tone: "done" | "blocking" | "pending" | "warning";
} {
  const where = authorityName(authority) || "the authority";
  const records = "You can review the saved application and download the available records.";
  if (status === "refused") return { label: "Refused · read-only", heading: `Refused by ${where}`, note: "The officer recorded an administrative refusal. This application is closed.", next: "Read the officer’s reasons and the appeal notice in the application’s messages.", tone: "blocking" };
  if (status === "accepted") return { label: "Accepted", heading: `Accepted by ${where}`, note: "Accepted as administratively complete. This does not decide whether the design complies or is safe.", next: `This is the final saved application. ${records}`, tone: "done" };
  if (status === "withdrawn") return { label: "Withdrawn · read-only", heading: "Withdrawn", note: "This application is closed.", next: records, tone: "pending" };
  if (status === "submitted" || status === "in_review") return {
    label: "Sent · read-only",
    heading: `Sent to ${where}`,
    note: "Read-only while it is with the authority.",
    next: `${status === "in_review" ? "An officer is reviewing it." : "Waiting for an officer to pick it up."} You can make corrections if the officer returns it.`,
    tone: "warning",
  };
  // A status this client does not know yet is final until the server says otherwise.
  return { label: "Read-only", heading: "Saved application", note: "This saved application is read-only.", next: records, tone: "pending" };
}
