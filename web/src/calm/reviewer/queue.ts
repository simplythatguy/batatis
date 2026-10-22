/** Reviewer queue as pure functions: tabs and counts, search, the claim cell and the row action. */
import type { ApplicationStatus, QueueApplication } from "../../api/accounts";
import { APPLICANT_LABEL } from "../auth/onboardingSteps";

export type QueueTab = "all" | "new" | "mine" | "returned" | "accepted";

export const TABS: { id: QueueTab; label: string }[] = [
  { id: "all", label: "All" },
  { id: "new", label: "New" },
  { id: "mine", label: "Mine" },
  { id: "returned", label: "Returned" },
  { id: "accepted", label: "Accepted" },
];

export function inTab(a: QueueApplication, tab: QueueTab, me: string | null): boolean {
  switch (tab) {
    case "all":
      return true;
    case "new":
      return a.status === "submitted" && !a.claim;
    case "mine":
      return Boolean(me && a.claim?.reviewer_id === me) && a.status !== "accepted";
    case "returned":
      return a.status === "returned";
    case "accepted":
      return a.status === "accepted";
  }
}

export function tabCounts(rows: QueueApplication[], me: string | null): Record<QueueTab, number> {
  const out = { all: 0, new: 0, mine: 0, returned: 0, accepted: 0 } as Record<QueueTab, number>;
  for (const r of rows) for (const t of TABS) if (inTab(r, t.id, me)) out[t.id]++;
  return out;
}

export function applicantLine(a: QueueApplication): string {
  const type = a.applicant.applicant_type ? APPLICANT_LABEL[a.applicant.applicant_type] ?? a.applicant.applicant_type : "";
  return [a.applicant.name, type.toLowerCase()].filter(Boolean).join(" · ");
}

/** Rows in a tab that match the search (title, applicant, type), newest sent first. */
export function filterQueue(rows: QueueApplication[], tab: QueueTab, query: string, me: string | null): QueueApplication[] {
  const q = query.trim().toLowerCase();
  return rows
    .filter((r) => inTab(r, tab, me))
    .filter((r) => !q || `${r.title ?? ""} ${applicantLine(r)}`.toLowerCase().includes(q))
    .sort((a, b) => Date.parse(b.submitted_at ?? b.updated_at) - Date.parse(a.submitted_at ?? a.updated_at));
}

export type PillTone = "accent" | "warning" | "blocking" | "done" | "pending";

/** Status pill: label and dot tone (New uses the accent dot, as in the v2 contract). */
export function statusPill(status: ApplicationStatus, claimed: boolean): { label: string; tone: PillTone } {
  switch (status) {
    case "submitted":
      return claimed ? { label: "In review", tone: "warning" } : { label: "New", tone: "accent" };
    case "in_review":
      return { label: "In review", tone: "warning" };
    case "returned":
      return { label: "Returned", tone: "blocking" };
    case "accepted":
      return { label: "Accepted", tone: "done" };
    case "withdrawn":
      return { label: "Withdrawn", tone: "pending" };
    default:
      return { label: "Draft", tone: "pending" };
  }
}

/** The Reviewer cell: "You", the other reviewer's name, or nobody. */
export function reviewerCell(a: QueueApplication, me: string | null): { name: string | null; label: string; mine: boolean } {
  if (!a.claim) return { name: null, label: "—", mine: false };
  const mine = Boolean(me && a.claim.reviewer_id === me);
  return { name: a.claim.reviewer_name, label: mine ? "You" : a.claim.reviewer_name, mine };
}

export type RowAction = "claim" | "open" | "view";

/** Unclaimed submitted → Start reviewing; your own in-review → Open; everything else → View. */
export function rowAction(a: QueueApplication, me: string | null): RowAction {
  if (a.status === "submitted" && !a.claim) return "claim";
  if (a.status === "in_review" && me && a.claim?.reviewer_id === me) return "open";
  return "view";
}

/** Whether this person may return or accept right now, and the reason shown when not. */
export function decisionGate(
  a: { status: ApplicationStatus; claim: { reviewer_id: string; reviewer_name: string } | null },
  me: string | null,
  /** null while the completeness check is loading or has failed: acceptance waits for a real result. */
  blocking: number | null,
): { canReturn: boolean; canAccept: boolean; reason: string } {
  const no = (reason: string) => ({ canReturn: false, canAccept: false, reason });
  if (a.status === "accepted") return no("Accepted as administratively complete.");
  if (a.status === "returned") return no("Returned to the applicant. It comes back here when they resend it.");
  if (a.status !== "in_review" || !a.claim) return no("Start reviewing to return or accept this application.");
  if (!me || a.claim.reviewer_id !== me) return no(`${a.claim.reviewer_name} is reviewing this. Only they can return or accept it.`);
  if (blocking === null) {
    return { canReturn: true, canAccept: false, reason: "Waiting for the completeness check before this can be accepted." };
  }
  if (blocking > 0) {
    return { canReturn: true, canAccept: false, reason: `${blocking} required ${blocking === 1 ? "item is" : "items are"} missing, so it can only be returned.` };
  }
  return { canReturn: true, canAccept: true, reason: "" };
}

export type PackageState =
  | { state: "loading" }
  | { state: "unavailable" }
  | { state: "none" }
  | { state: "stale"; version: number }
  | { state: "current"; blocking: number };

/**
 * The accept gate with the package review: acceptance also waits for a package review of the
 * current application and never passes with its blocking gaps open. When the package review
 * can't run on this server, the completeness check alone decides (as before).
 */
export function withPackage(gate: ReturnType<typeof decisionGate>, pkg: PackageState): ReturnType<typeof decisionGate> {
  if (!gate.canAccept || pkg.state === "unavailable") return gate;
  const no = (reason: string) => ({ ...gate, canAccept: false, reason });
  if (pkg.state === "loading") return no("Waiting for the package review before this can be accepted.");
  if (pkg.state === "none") return no("Run the package review before accepting.");
  if (pkg.state === "stale") return no(`The application changed after review version ${pkg.version}. Run the review again before accepting.`);
  if (pkg.blocking > 0) return no(`The package review has ${pkg.blocking} required ${pkg.blocking === 1 ? "item" : "items"} open, so it can't be accepted yet.`);
  return gate;
}

/* —— Times —— */

const DAY = 86_400_000;

function startOfDay(t: number): number {
  const d = new Date(t);
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

export function clock(iso: string): string {
  const t = Date.parse(iso);
  return Number.isFinite(t) ? new Date(t).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }) : "";
}

/** "Today, 9:12 AM", "Yesterday", "Oct 19" (local time). */
export function sentLabel(iso: string | null, now = Date.now()): string {
  if (!iso) return "—";
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return "—";
  const today = startOfDay(now);
  if (t >= today) return `Today, ${clock(iso)}`;
  if (t >= today - DAY) return "Yesterday";
  return new Date(t).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/** Mid-sentence form: "today, 9:12 AM", "yesterday", "Oct 19". */
export function sentPhrase(iso: string | null, now = Date.now()): string {
  return sentLabel(iso, now).replace(/^Today/, "today").replace(/^Yesterday/, "yesterday");
}

/** "since 2:14 PM" today, otherwise "since Oct 19". */
export function sinceLabel(iso: string, now = Date.now()): string {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return "";
  return t >= startOfDay(now) ? `since ${clock(iso)}` : `since ${new Date(t).toLocaleDateString("en-US", { month: "short", day: "numeric" })}`;
}

/* —— Completeness —— */

export interface CompletenessView {
  /** 0–100 for the ring, or null when nothing is known yet. */
  pct: number | null;
  label: string;
}

/**
 * The list does not run the full checker (completeness is null), so the ring comes from the
 * row's own numbers when present, else from the case's gaps: no required item missing = 100%.
 */
export function completenessView(c: QueueApplication["completeness"], blocking: number | null): CompletenessView {
  if (c && c.total > 0) {
    const pct = Math.round((100 * Math.min(c.answered, c.total)) / c.total);
    return { pct, label: `${pct}%` };
  }
  if (blocking == null) return { pct: null, label: "—" };
  if (blocking === 0) return { pct: 100, label: "Complete" };
  return { pct: 0, label: `${blocking} missing` };
}
