/** Return-with-message helpers. Pure. */
import type { DecisionItemInput } from "../../api/accounts";
import type { EngineGap } from "../../api/client";

export const RETURN_MIN = 10;

/** Gaps the officer can tick: blocking first, then warnings. Advice (info) is not an item. */
export function returnableGaps(gaps: EngineGap[]): EngineGap[] {
  const rank = { blocking: 0, warning: 1, info: 2 } as const;
  return gaps.filter((g) => g.severity !== "info").sort((a, b) => rank[a.severity] - rank[b.severity]);
}

/** Ticked gaps as decision items the applicant sees beside the message. */
export function decisionItems(gaps: EngineGap[], ticked: ReadonlySet<string>): DecisionItemInput[] {
  return gaps
    .filter((g) => ticked.has(g.id))
    .map((g) => ({ gap_id: g.id.slice(0, 200), field: g.field ? g.field.slice(0, 200) : undefined, note: (g.message || g.fix_hint || "Please address this item.").slice(0, 2000) }));
}

/**
 * A plain draft from the ticked items, used when the assistant is not available. It is a starting
 * point for the officer to edit, and asks only for administrative information.
 */
export function localDraft(labels: string[]): string {
  const items = labels.map((l) => l.trim()).filter(Boolean);
  if (!items.length) return "";
  return [
    "Thank you for your application. Before it can be accepted as administratively complete, please address the following:",
    "",
    ...items.map((l) => `- ${l}`),
    "",
    "Resend the application once these are in place.",
  ].join("\n");
}

/** The question sent to /assist for a draft. The officer edits whatever comes back. */
export function draftQuestion(labels: string[]): string {
  return [
    "Draft a short, polite note from the Safety Codes Officer to the applicant, returning the application for administrative information only.",
    "Ask them to address these items, one bullet each, without judging the design or saying whether it complies:",
    ...labels.map((l) => `- ${l}`),
  ].join("\n").slice(0, 1500);
}

export function messageProblem(message: string): string {
  const n = message.trim().length;
  if (n >= RETURN_MIN) return "";
  return n === 0 ? `Write a message of at least ${RETURN_MIN} characters.` : `At least ${RETURN_MIN} characters · ${n} so far.`;
}
