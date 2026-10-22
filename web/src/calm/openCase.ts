/**
 * Rebuild the browser case from a saved engine case (opening an application from the list). Pure.
 *
 * What the engine stores: facts (answers, the description, process fields, professional and
 * evidence facts), the jurisdiction, the title and the confirmed provisions. What it does not
 * store: unanswered or "No" code-check cards and attached file names. Those are re-derived from
 * the description (cards) or are simply absent (files), never invented.
 */
import type { Case as EngineCase } from "../api/types.gen";
import { emptyCase, applyDescription } from "../intake";
import { localField } from "../intakeFields";
import { CODECHECK_PREFIX, PROCESS_FACT, reducer } from "../model";
import { isProvision } from "../provisions";
import type { ApplicantType, AuthorityId, Candidate, Case, Fact, ProcessFieldId } from "../types";

const WITHDRAWN = "Answer withdrawn by applicant";

/** The latest saved fact per field, without withdrawn answers. Order is preserved. */
export function latestFacts(facts: EngineCase["facts"]): Fact[] {
  // Intake's Section A/B export keys (owner_name, ...) are the browser's field ids (owner, ...).
  const latest = new Map<string, EngineCase["facts"][number]>();
  for (const f of facts) latest.set(localField(f.field), f);
  return [...latest.entries()]
    .filter(([, f]) => f.source?.ref !== WITHDRAWN && !(f.value === "" && f.status === "unconfirmed"))
    .map(([field, f]) => ({ ...f, field, id: f.id, status: f.status }) as Fact);
}

export function caseFromEngine(saved: EngineCase, type: ApplicantType): Case {
  const base = emptyCase(type);
  const facts = latestFacts(saved.facts);
  const by = new Map(facts.map((f) => [f.field, f]));
  const description = by.get("project.description");
  const authority = (saved.jurisdiction?.id === "calgary" || saved.jurisdiction?.id === "edmonton" ? saved.jurisdiction.id : "") as AuthorityId;
  const process = { ...base.process };
  // As engine/process_fields.py: the newest answer across the field's names counts only when the
  // applicant confirmed it as their own words. Anything else stays a gap; its saved fact is kept.
  for (const [id, field] of Object.entries(PROCESS_FACT) as [ProcessFieldId, string][]) {
    const f = by.get(field);
    if (f && f.status === "confirmed" && f.kind === "pointed" && typeof f.value === "string" && f.value.trim() && f.value === f.source?.quote) process[id] = f.value;
  }
  // Starter and intake questions read as answered when their field has a saved answer.
  const questions = base.questions.map((q) => {
    const v = by.get(q.field)?.value;
    return v != null && v !== "" ? { ...q, answer: String(v) } : q;
  });
  const confirmed: Candidate[] = saved.provisions.filter(isProvision).map((id) => ({
    id: `search-${id}`,
    topic: id,
    provision: id,
    part: Number(id.split(".")[0]) || 0,
    benchmark: true,
    identified: true,
    quote: { text: "", citation: "", source: "code" },
    departure: "do something other than what this sentence requires",
    clarifyingQuestion: "Which part of this sentence does the design not follow?",
    answer: "yes",
  }));
  let c: Case = {
    ...base,
    id: `case-${saved.id}`,
    title: saved.title || base.title,
    authority,
    facts: facts.filter((f) => f.field !== "project.description"),
    questions,
    process,
    candidates: confirmed,
  };
  // The description re-derives its own facts and code-check cards, exactly as when typed.
  if (description && typeof description.value === "string") c = applyDescription(c, description.value);
  // Keep the saved description fact itself (same id and value), so nothing is re-sent.
  if (description) c = { ...c, facts: [...c.facts.filter((f) => f.field !== "project.description"), description] };
  if (saved.title) c = { ...c, title: saved.title };
  return restoreCardAnswers(c);
}

/**
 * Answers to cards read from the description come back from their saved facts: a stored
 * `codecheck.<card>` answer, and the storey count for the storeys card. The saved facts are kept
 * as they are (same ids), so reopening sends nothing.
 */
function restoreCardAnswers(c: Case): Case {
  const savedFacts = c.facts;
  let next = c;
  for (const f of savedFacts) {
    if (!f.field.startsWith(CODECHECK_PREFIX)) continue;
    const id = f.field.slice(CODECHECK_PREFIX.length);
    const answer = f.value;
    if ((answer === "yes" || answer === "no" || answer === "not-sure") && next.candidates.some((a) => a.id === id && a.answer === null)) {
      next = reducer(next, { type: "answerCandidate", id, answer });
    }
  }
  const storeys = savedFacts.find((f) => f.field === "building.storeys" && f.status === "confirmed" && Number.isInteger(Number(f.value)) && Number(f.value) > 0);
  if (storeys && next.candidates.some((a) => a.id === "desc-storeys" && a.answer === null)) {
    next = reducer(next, { type: "setStoreyCount", value: String(storeys.value) });
  }
  return next === c ? c : { ...next, facts: savedFacts };
}
