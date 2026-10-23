/**
 * Rebuild the browser case from a saved engine case (opening an application from the list). Pure.
 *
 * What the engine stores: facts (answers, the description, process fields, professional and
 * evidence facts), the jurisdiction, the title, the confirmed provisions and the code-check
 * selection (`selected_articles`, docs/api/selected-articles.md): every code card with its answer,
 * unanswered and pending ones included. What it does not store: attached file names, which are
 * simply absent, never invented.
 */
import type { Case as EngineCase, IdentifyResult, IntakeResult, SelectedArticleInput } from "../api/types.gen";
import { emptyCase, applyDescription } from "../intake";
import { localField } from "../intakeFields";
import { CODECHECK_PREFIX, PROCESS_FACT, reducer } from "../model";
import { canonicalProvision, isProvision } from "../provisions";
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
  // A saved selection is the card list; `null` (never saved) falls back to the confirmed references.
  const confirmed: Candidate[] = saved.selected_articles ? [] : saved.provisions.filter(isProvision).map((id) => ({
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
  if (saved.title) c = { ...c, title: saved.title, titleKept: true };
  if (saved.selected_articles) c = restoreSelection(c, saved.selected_articles, saved.provisions);
  return restoreCardAnswers(c);
}

/**
 * The code-check selection to save: every card on a real provision, in order, with its answer and
 * whether that answer still waits for the engine. Cards read from the description are not code
 * references; their answers travel as facts. One card per provision and per id.
 */
export function selectedArticles(c: Case): SelectedArticleInput[] {
  const ids = new Set<string>();
  const provisions = new Set<string>();
  const out: SelectedArticleInput[] = [];
  for (const a of c.candidates) {
    const key = canonicalProvision(a.provision);
    if (!isProvision(a.provision) || ids.has(a.id) || provisions.has(key)) continue;
    ids.add(a.id);
    provisions.add(key);
    out.push({ id: a.id, provision: a.provision, answer: a.answer, pending: Boolean(a.pending) });
  }
  return out;
}

/** A saved card, rebuilt with its stable id. Code wording and attributions are read separately. */
function selectedCard(s: SelectedArticleInput, confirmed: Set<string>): Candidate {
  const suggestion = s.id.startsWith("id-") ? "identify" : s.id.startsWith("search-") && !confirmed.has(canonicalProvision(s.provision)) ? "search" : undefined;
  return {
    id: s.id,
    topic: s.provision,
    provision: s.provision,
    part: Number(s.provision.split(".")[0]) || 0,
    benchmark: false,
    identified: true,
    ...(suggestion ? { suggestion } : {}),
    quote: { text: "", citation: "", source: "code" },
    departure: "do something other than what this sentence requires",
    clarifyingQuestion: "Which part of this sentence does the design not follow?",
    answer: null,
  };
}

/**
 * Put each saved card's answer and pending state back through the reducer (a Not sure keeps its
 * open question). Only an answer the engine acknowledged reads as the benchmark: a pending Yes
 * stays open and resendable, and nothing here confirms a reference.
 */
function answerSelection(c: Case, list: SelectedArticleInput[], skip: (s: SelectedArticleInput) => boolean = () => false): Case {
  let next = c;
  for (const s of list) {
    if (skip(s)) continue;
    const card = next.candidates.find((a) => a.id === s.id);
    if (!card) continue;
    const answer = s.answer ?? null;
    if (card.answer !== answer) next = reducer(next, { type: "answerCandidate", id: s.id, answer });
    if (Boolean(card.pending) !== Boolean(s.pending)) next = reducer(next, { type: "markDecisionPending", id: s.id, pending: Boolean(s.pending) });
  }
  const pending = new Set(list.filter((s) => s.pending).map((s) => s.id));
  return { ...next, candidates: next.candidates.map((a) => (pending.has(a.id) && a.benchmark ? { ...a, benchmark: false } : a)) };
}

function restoreSelection(c: Case, list: SelectedArticleInput[], provisions: string[]): Case {
  const confirmed = new Set(provisions.map(canonicalProvision));
  const cards = list.map((s) => selectedCard(s, confirmed));
  const keep = c.candidates.filter((a) => !isProvision(a.provision) && !cards.some((x) => x.id === a.id));
  return answerSelection({ ...c, candidates: [...keep, ...cards] }, list);
}

/**
 * Open a saved application in one step: the saved case, then what intake read and the last code
 * identification as they were stored (no provider call). With a saved selection, it decides which
 * code cards exist: identification never refills a removed card, and a card it replaced keeps its
 * saved id. A stored identification decision stays the answer of its card unless the saved card
 * was still waiting for the engine (pending), whose answer and state come back as they were.
 */
export function openedCase(saved: EngineCase, type: ApplicantType, stored: { intake: IntakeResult | null; identify: IdentifyResult | null }): Case {
  const restored = caseFromEngine(saved, type);
  let c = restored;
  if (stored.intake) c = reducer(c, { type: "restoreIntake", result: stored.intake, text: c.description.trim() });
  if (stored.identify) c = reducer(c, { type: "noteIdentify", result: stored.identify });
  const list = saved.selected_articles;
  if (!list) return c;
  const cards = list.map((s) => c.candidates.find((a) => a.id === s.id) ?? restored.candidates.find((a) => a.id === s.id)).filter((a): a is Candidate => Boolean(a));
  const ids = new Set(cards.map((a) => a.id));
  const keep = c.candidates.filter((a) => !isProvision(a.provision) && !ids.has(a.id));
  const next = { ...c, candidates: [...keep, ...cards] };
  const decided = new Set(stored.identify ? cards.filter((a) => a.suggestion === "identify").map((a) => a.id) : []);
  const questions = next.questions.filter((q) => !q.cardId || next.candidates.some((a) => a.id === q.cardId));
  return answerSelection({ ...next, questions }, list, (s) => decided.has(s.id) && !s.pending);
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
