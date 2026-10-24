/**
 * Standing-package checklists in the deck (docs/api/checklists.md). Pure.
 *
 * A checklist is the applicant's declaration that the project follows a published package; it is
 * never a determination, and the officer decides. Counts are a tally of the applicant's own answers,
 * never a score or a pass mark.
 */
import type { CaseChecklist, CaseCondition, CaseChecklists } from "../api/types.gen";
import type { Case } from "../types";
import { articleOf, type ShownRule } from "./rulesView";

export type ConditionState = "confirmed" | "not_yet" | "does_not_apply";

export const NOT_REVIEWED_PERSON = "Not yet reviewed by a person.";

/** Normalize text with word boundaries for matching published package titles. */
const words = (t: string) => ` ${t.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim()} `;

/** A sentence matches its own id; an article matches every sentence the package lists in it. */
const within = (provision: string, listed: string) => (provision.includes("(") ? provision === listed : articleOf(provision) === articleOf(listed));

/**
 * Packages that fit this case: the engine's own provision match, a code-check card or a departing
 * rule on a provision the package varies, or the package's name in the applicant's description.
 */
export function matchingChecklists(c: Case, data: CaseChecklists | null, rules: ShownRule[] = []): CaseChecklist[] {
  if (!data) return [];
  const text = words(`${c.description} ${c.intake?.text ?? ""}`);
  return data.checklists.filter((cl) => {
    if (cl.matches_case_provisions) return true;
    if (text.includes(words(cl.title))) return true;
    const cards = c.candidates.filter((a) => a.answer !== "no").map((a) => a.provision);
    const departs = rules.filter((r) => r.state === "departs").map((r) => r.provision.id);
    return cl.provisions.some((p) => [...cards, ...departs].some((x) => within(x, p)));
  });
}

/** The option rows of a one-of choice that another option already confirmed: nothing to ask. */
export function coveredByOption(cl: CaseChecklist, row: CaseCondition): boolean {
  if (!row.one_of) return false;
  return cl.conditions.some((x) => x !== row && x.one_of === row.one_of && x.answer?.state === "confirmed");
}

/** Sibling options to record as "does not apply" once one option is confirmed. */
export function otherOptions(cl: CaseChecklist, row: CaseCondition): CaseCondition[] {
  if (!row.one_of) return [];
  return cl.conditions.filter((x) => x !== row && x.one_of === row.one_of && x.may_not_apply && !x.answer);
}

/** "Not yet", or an always-applies row left unanswered, means the package is not yet followed in full. */
export function followedInFull(cl: CaseChecklist): boolean {
  return cl.conditions.every((x) => x.answer && x.answer.state !== "not_yet");
}

/** Find the published group containing a checklist condition. */
export function groupOf(cl: CaseChecklist, row: CaseCondition) {
  return cl.groups.find((g) => g.id === row.group);
}

/** "Calgary SPV-001 Zero Lot Line": the code and title, without inventing an office name. */
export const packageName = (cl: { code: string; title: string }) => `${cl.code} ${cl.title}`;

/** What the applicant should ask the office: conflicts and text only in a figure (never rows). */
export function askTheOffice(cl: CaseChecklist) {
  return cl.source_notes.filter((n) => n.kind === "conflict" || n.kind === "figure_only");
}

export const STATE_LABEL: Record<ConditionState, string> = {
  confirmed: "Yes, my project does this",
  not_yet: "Not yet",
  does_not_apply: "Does not apply",
};

/** Answer choices for one row; "does not apply" only where the row may not apply. */
export function conditionChoices(row: CaseCondition): { value: ConditionState; label: string }[] {
  const out: { value: ConditionState; label: string }[] = [{ value: "confirmed", label: STATE_LABEL.confirmed }, { value: "not_yet", label: STATE_LABEL.not_yet }];
  if (row.may_not_apply) out.push({ value: "does_not_apply", label: STATE_LABEL.does_not_apply });
  return out;
}

/** The tally in words, never "complete" or "passed". */
export function tallyLine(cl: CaseChecklist): string {
  const n = cl.counts;
  const parts = [`${n.confirmed} confirmed`];
  if (n.not_yet) parts.push(`${n.not_yet} not yet`);
  if (n.does_not_apply) parts.push(`${n.does_not_apply} do not apply`);
  if (n.unanswered) parts.push(`${n.unanswered} to answer`);
  return parts.join(" · ");
}
