/** Application list rows: one context line per application, and the quiet Settled group. Pure. */
import type { ApplicationStatus, ApplicationSummary } from "../api/accounts";
import { AUTHORITIES } from "../config";
import { ago } from "./relevance";

export type LineTone = "grey" | "amber" | "accent" | "green";

export interface StatusLine {
  text: string;
  tone: LineTone;
  /** Draws the accent colour on the line (returned with news). */
  attention: boolean;
}

export const SETTLED: ReadonlySet<ApplicationStatus> = new Set(["accepted", "withdrawn"]);

export function authorityName(id: string | null | undefined): string {
  if (!id) return "";
  return AUTHORITIES.find((a) => a.id === id)?.name ?? id.charAt(0).toUpperCase() + id.slice(1);
}

export function percent(c: ApplicationSummary["completeness"]): number | null {
  if (!c || !c.total) return null;
  return Math.round((100 * Math.min(c.answered, c.total)) / c.total);
}

export function statusLine(a: ApplicationSummary, now = Date.now()): StatusLine {
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
      return { text: join("Returned", n > 0 ? `${n} new ${n === 1 ? "message" : "messages"}` : "fix and resubmit"), tone: "accent", attention: true };
    }
    case "accepted":
      return { text: join("Accepted", where), tone: "green", attention: false };
    case "withdrawn":
      return { text: "Withdrawn", tone: "grey", attention: false };
    default:
      // A status this client does not know yet must not break the whole list.
      return { text: join(String(a.status ?? "") || "Status unknown", where), tone: "grey", attention: false };
  }
}

/** Active first (newest first), settled in their own group; the search matches the title. */
export function groupApplications(apps: ApplicationSummary[], query = ""): { active: ApplicationSummary[]; settled: ApplicationSummary[] } {
  const q = query.trim().toLowerCase();
  const shown = apps
    .filter((a) => !q || a.title.toLowerCase().includes(q) || authorityName(a.authority).toLowerCase().includes(q))
    .sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at));
  return { active: shown.filter((a) => !SETTLED.has(a.status)), settled: shown.filter((a) => SETTLED.has(a.status)) };
}

/** Submitted and in-review applications are read-only until they come back. */
export const readOnly = (s: ApplicationStatus | null | undefined) => s === "submitted" || s === "in_review" || s === "accepted" || s === "withdrawn";
