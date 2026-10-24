/** Return-with-message helpers. Pure. */
import type { DecisionItemInput } from "../../api/accounts";
import type { EngineGap, ReviewQuestion } from "../../api/client";

export const RETURN_MIN = 10;

/** Gaps the officer can tick: blocking first, then warnings. Advice (info) is not an item. */
export function returnableGaps(gaps: EngineGap[]): EngineGap[] {
  const rank = { blocking: 0, warning: 1, info: 2 } as const;
  return gaps.filter((g) => g.severity !== "info").sort((a, b) => rank[a.severity] - rank[b.severity]);
}

/** Ticked gaps as decision items the applicant sees beside the message. */
export function decisionItems(gaps: ReturnChoice[], ticked: ReadonlySet<string>): DecisionItemInput[] {
  return gaps
    .filter((g) => ticked.has(g.id))
    .map((g) => ({ gap_id: g.id.slice(0, 200), field: g.field ? g.field.slice(0, 200) : undefined, note: (g.message || g.fix_hint || "Please address this item.").slice(0, 2000) }));
}

export type ReturnChoice = Pick<EngineGap, "id" | "field" | "message" | "fix_hint"> & {
  severity?: EngineGap["severity"];
};

/** Clarification is an explicit officer choice, never an invented completeness gap. */
export function returnChoices(gaps: EngineGap[], questions: ReviewQuestion[]): ReturnChoice[] {
  const choices: ReturnChoice[] = returnableGaps(gaps);
  const ids = new Set(choices.map(item => item.id));
  for (const q of questions) {
    if (q.state === "answered" || ids.has(q.id)
      || /^(professional[._]|responsible_professional)/.test(q.field)) continue;
    ids.add(q.id);
    choices.push({ id: q.id, field: `clarification.${q.id}`, message: `Please clarify: ${q.text}${q.answer ? ` Applicant answer: ${q.answer}.` : ""}${q.clarification?.answer ? ` Latest clarification: ${q.clarification.answer}` : ""}` });
  }
  return choices;
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
    "The requested items are listed below this note.",
    "",
    "Review your corrections, then Resubmit on Application. The officer will confirm them during review.",
  ].join("\n");
}

/** The question sent to /assist for a draft. The officer edits whatever comes back. */
export function draftQuestion(labels: string[]): string {
  return [
    "Draft a short, polite note from the Safety Codes Officer to the applicant, returning the application for administrative information only.",
    "Write only a brief introduction and next step. The checked items will be displayed separately below your note: do not repeat or list them in the note.",
    "Ask the applicant to review their corrections, then Resubmit on Application. Do not judge the design or say whether it complies.",
    "Checked items (context only):",
    ...labels.map((l) => `- ${l}`),
  ].join("\n").slice(0, 1500);
}

export function messageProblem(message: string): string {
  const n = message.trim().length;
  if (n >= RETURN_MIN) return "";
  return n === 0 ? `Write a message of at least ${RETURN_MIN} characters.` : `At least ${RETURN_MIN} characters · ${n} so far.`;
}
