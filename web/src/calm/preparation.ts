/** Applicant actions, explicit abstentions and a local professional question have different next steps. */
import type { Case, Gap } from "../types";

export function preparationGaps(c: Case, gaps: Gap[]): { applicant: Gap[]; officer: Gap[]; checkNeeded: Gap[] } {
  const out = { applicant: [] as Gap[], officer: [] as Gap[], checkNeeded: [] as Gap[] };
  for (const g of gaps) {
    const q = c.questions.find((q) => g.id === `question-${q.id}` || g.id === q.id);
    const card = q?.cardId ?? (q?.id.startsWith("q-from-") ? q.id.slice("q-from-".length) : undefined);
    const abstained = g.severity === "warning" && card && c.candidates.some((a) => a.id === card && a.answer === "not-sure");
    if (g.submissionBlocking === false || abstained) out.officer.push(g);
    // A local heuristic cannot establish submission handoff. Keep the gate, but request a check
    // instead of telling the applicant their own professional answer is missing.
    else if (g.id === "practice-unknown" || (g.id === "professional-not-engaged" && c.practiceOfEngineering !== true)) out.checkNeeded.push(g);
    else out.applicant.push(g);
  }
  return out;
}
