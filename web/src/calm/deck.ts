/**
 * The question deck: one card per thing the applicant still has to answer.
 * Pure and derived. Every card comes from the case and the shared gap list; nothing is typed by hand.
 * Card keys reuse the legacy focus ids (field-*, cand-*, fact-*, q-*), so gap hrefs land on cards.
 *
 * Journey order decides what is asked; section letters retain the form mapping.
 */
import type { Question as PlanQuestion } from "../api/types.gen";
import { confirmedAnswer, localField } from "../intakeFields";
import { codeQuestion, fileNotes, type ReadCopy, planInput, planQuestions, plannedFields, readGroups, scopeRedirect, legalFromFacts } from "../intakeView";
import { DETAIL_FIELDS, DETAIL_IDS, PROCESS_FIELDS, answeredByDescription, factFor, questionAnsweredByFact, valueText } from "../model";
import { articleOf, isProvision, keywordCandidate, keywordGroups } from "../provisions";
import { requirementAnswer, requirementQueue, requirementTopic } from "./requirements";
import { quoteKind } from "../rules";
import type { ApplicantType, Candidate, Case, Gap } from "../types";
import type { BenchmarkRecord, CaseChecklists, CaseRules, RequirementRecord } from "../api/types.gen";
import type { InputSpec } from "../rules/evaluate";
import { conditionChoices, coveredByOption, followedInFull, groupOf, matchingChecklists, tallyLine } from "./checklistView";
import { calmHref } from "./routes";
import { caseRuleResults, inputChoices, linkedCandidate, plainResult, RULE_REF, ruleFacts, ruleInPlay, ruleTopic, type RuleData, type ShownRule } from "./rulesView";
import { preparationGaps } from "./preparation";
import { professionalCounts } from "../professional";
import { decidePath, namedRuleInputs, pathStopCopy } from "../pathDecision";
import { answererOf, itemOpen, journeyAnswers, journeyProgress, orderJourney, PAPERWORK_FIELDS, productScope, routeChoice, stageOf, understandingAnswerKey, understandingRows, type UnderstandingRow, type Answerer, type JourneyAnswerValue, type Stage } from "./journey";

/** Choice values on rule and package cards. */
export const RULE_ADD = "add";
export const RULE_LEAVE = "leave";
export const PACKAGE_YES = "yes";
export const PACKAGE_NO = "no";

export type DeckKind =
  | "understood" | "route" | "route-detail" | "product-scope" | "product-notice" | "role" | "paperwork"
  | "fact" | "file" | "plan" | "candidate" | "storeys" | "question" | "authority" | "detail" | "process" | "section-d"
  /** Intake reading the description and files, or failed (with Try again). */
  | "reading"
  /** Code identification running, not run yet, or failed (with Try again). */
  | "code-run"
  /** "I could not narrow this down", or the labelled keyword fallback. */
  | "code-note"
  /** The requirement-ledger counts and the way into the code library. */
  | "code-ledger"
  /** One ledger rule: does it apply to this project? Departure is asked on its own card. */
  | "requirement"
  /** The applicant's own words for the departure from the named benchmark sentence. */
  | "departure"
  /** Keyword-only leads grouped by topic; each lead opens on request (never a relevance score). */
  | "code-triage"
  /** A number or answer a coded rule needs (docs/api/rules.md). */
  | "rule-input"
  /** A coded rule's result: follows or departs from the acceptable solution. */
  | "rule"
  /** A standing package offered for this project (docs/api/checklists.md). */
  | "package"
  /** One condition of an accepted standing package. */
  | "condition"
  /** The tally after the last condition, and what to ask the office. */
  | "package-end"
  /** Another safety-codes regime: the redirect page. */
  | "scope";

/** Variance form sections, in the order the deck asks them and the footer shows them. */
export type SectionId = "A" | "B" | "C" | "D";

/**
 * Plain words first; the form's letter stays visible as quiet secondary text, so applicants learn
 * how their answers map to the official form without needing to know it.
 */
export const SECTIONS: { id: SectionId; label: string; short: string; about: string }[] = [
  { id: "A", label: "About you", short: "About you", about: "Section A of the variance form: who is applying, and who owns the site." },
  { id: "B", label: "Your project", short: "Project", about: "Section B: the site, and what you want to do differently." },
  { id: "C", label: "Which rules apply", short: "Rules", about: "Section C: the building-code rules your design differs from, and why each rule exists." },
  { id: "D", label: "Your case and proof", short: "Your case", about: "Section D: why your design works as well, and the documents that back it up." },
];

/** "Your project · Section B": the plain name, then the form's letter. */
export const sectionEyebrow = (id: SectionId) => `${SECTIONS.find((s) => s.id === id)?.label} · Section ${id}`;

export interface DeckItem {
  key: string;
  kind: DeckKind;
  /** Form section this card fills (footer progress, popover). */
  section: SectionId;
  stage: Stage;
  answerer: Answerer;
  eyebrow: string;
  title: string;
  /** One muted line under the question. */
  context: string;
  /** The applicant's own words, shown quoted after `context`. */
  quote?: string;
  why: string;
  /** What the card edits: fact id, candidate id, question id or field id. */
  ref: string;
  field?: string;
  done: boolean;
  /** Offered once and excluded from required-answer totals. */
  optional: boolean;
  /** A real code provision for the citation chip. Absent for cards built from the applicant's words. */
  provision?: string;
  /**
   * Two answers in plain words: proposed facts ("Yes, 2 storeys" / "No, something else") and the
   * proposed alternative, which offers the description instead of asking for it again.
   */
  confirmLabels?: { confirm: string; dismiss: string };
  /** A "what we read" card: every fact one click confirms or rejects, and how it reads. */
  ids?: string[];
  read?: ReadCopy;
  /** A planner card: the question as the API ranked it. */
  plan?: PlanQuestion;
  /** Legacy uncertainty: left open on Review, without repeatedly asking the card. */
  settled?: boolean;
  /** A coded rule's result: on its own card, or on the code-check card for the same article. */
  rule?: ShownRule;
  /** A rule input card: the field and how it is asked. */
  input?: { field: string; spec: InputSpec; rule: string };
  /** Standing-package cards: the checklist id, and the condition id on a condition card. */
  checklist?: string;
  condition?: string;
  /** Answer choices carried by the card itself (rules and packages), in keyboard order. */
  choices?: { value: string; label: string }[];
  /** Section D: the applicant's part is done and the officer's professional determination is pending. */
  pendingForOfficer?: boolean;
  /** Section D: answers changed after the last check; the current requirements need a fresh check. */
  needsCheck?: boolean;
  rows?: UnderstandingRow[];
  acknowledgementKey?: string;
  /** The paperwork sheet retains each field's identity, deferral and required status. */
  paperworkRows?: DeckItem[];
  assumed?: boolean;
  deferred?: JourneyAnswerValue;
  suggestedValue?: string;
  /** Inner professional/evidence questions may supply their real counts here. */
  counts?: Partial<Record<Answerer, { open: number; done: number }>>;
  /** A ledger rule card: the requirement row this answer decides (applicability only). */
  requirement?: RequirementRecord;
}
type UnpositionedItem = Omit<DeckItem, "stage" | "answerer">;
const positioned = (item: UnpositionedItem): DeckItem => ({ ...item, stage: stageOf(item), answerer: answererOf(item) });

export interface DeckOptions {
  /** Keys the applicant has continued past in this visit (Section D, optional cards). */
  seen?: ReadonlySet<string>;
  /** Include answered cards too (progress, focus links to an answered card). */
  includeDone?: boolean;
  /** Code identification for this visit: running, failed, or finished. */
  identify?: "idle" | "running" | "done" | "error" | "skipped";
  /** Intake for this visit: while it reads, the deck holds one waiting card so nothing is asked twice. */
  intake?: "idle" | "running" | "done" | "error";
  intakeNote?: string;
  /** Rule definitions (GET /rules) and the case's stored results (GET /cases/{id}/rules). */
  rules?: RuleData | null;
  storedRules?: CaseRules | null;
  /** GET /cases/{id}/checklists, and the applicant's choice on each offered package. */
  checklists?: CaseChecklists | null;
  packages?: Readonly<Record<string, "yes" | "no">>;
  /**
   * The reviewing authority card shows the office's pack. An authority read from the site's
   * municipality is then confirmed once on that card (optional) instead of being skipped.
   */
  confirmAuthority?: boolean;
  /** An optional keyword lead the applicant explicitly opened from grouped triage or a saved link. */
  focusedCandidate?: string;
  /** The stored benchmark: once its departure is confirmed the deck stops asking for it. */
  benchmark?: BenchmarkRecord | null;
  /** A visible default supplied by the caller, never a silently saved date. */
  today?: string;
}

const RULE_WHY = "Batatis compares the numbers you give with one acceptable solution in the code. It flags where your design departs from it; it never decides whether the design is acceptable. The officer decides.";

/** Coded rules and standing packages that apply to this case, ready to place in the Rules step. */
export function caseRules(c: Case, opts: DeckOptions): ShownRule[] {
  if (!opts.rules) return [];
  return caseRuleResults(c, opts.rules, opts.storedRules).filter((r) => ruleInPlay(c, opts.rules!, r));
}

/** A short label is enough for an obvious field; the control and its placeholder say the rest. */
const DETAIL_QUESTION: Record<string, string> = {
  owner: "Owner",
  representative: "Representative",
  mailingAddress: "Mailing address",
  date: "Request date",
  scope: "One site or every site?",
  permit: "Permit number",
  municipalAddress: "Site address",
  legalDescription: "Legal description",
  alternative: "What will you do differently?",
};

const PROCESS_QUESTION: Record<string, string> = {
  rationale: "Why do you need to build it differently, and why will it work as well?",
  risk: "What could go wrong if it doesn’t work as well?",
  mitigation: "What reduces those risks?",
  assumptions: "Under what conditions does your case hold?",
  maintenance: "What has to be looked after once it’s built?",
  qualifications: "Who takes responsibility for this, and for which parts?",
};

export const WRITTEN_BY_YOU = "Write your answer or review a sourced draft. You own the wording you accept.";

/** Whitespace folded, cut at `n` characters with an ellipsis. */
const clip = (t: string, n: number) => {
  const s = t.replace(/\s+/g, " ").trim();
  return s.length > n ? `${s.slice(0, n - 1).trimEnd()}…` : s;
};

/** "Your description" → "your description"; other sources keep their case ("NBC table"). */
export function sourcePhrase(ref: string): string {
  return /^(Your|The|This)\b/.test(ref) ? ref.charAt(0).toLowerCase() + ref.slice(1) : ref;
}

/** The applicant's first sentence, for quoting back. */
function firstSentence(text: string): string {
  const t = text.trim();
  const s = t.split(/(?<=[.!?])\s+/)[0] ?? t;
  return s.length > 160 ? `${s.slice(0, 157)}…` : s;
}

/** "(2)" when another card is on the same rule, so cards on its different sentences read apart. */
export function sentenceLabel(c: Case, a: Candidate): string {
  const sentence = a.provision.match(/^\d+\.\d+\.\d+\.\d+\.?((?:\([0-9a-z.]+\))+)$/)?.[1] ?? "";
  const shared = c.candidates.some((x) => x.id !== a.id && articleOf(x.provision) === articleOf(a.provision));
  return sentence && shared ? sentence : "";
}

/** Build a code-check card, keeping answers open until the engine stores them. */
function candidateItem(c: Case, a: Candidate): UnpositionedItem {
  // An answer the engine has not stored yet keeps the card open, so answering again resends it.
  const done = a.answer !== null && !a.pending;
  if (a.id === "desc-storeys") {
    return {
      key: `cand-${a.id}`,
      kind: "storeys",
      section: "C",
      eyebrow: sectionEyebrow("C"),
      title: "How many storeys is the building?",
      context: "",
      why: "The count decides which part of the code is the benchmark. Buildings up to 3 storeys usually follow Part 9; larger ones follow Part 3. Not sure leaves the question open for review.",
      ref: a.id,
      done: done || Boolean(confirmedAnswer(c.facts, "storeys")),
      optional: false,
    };
  }
  const kind = quoteKind(a);
  const real = isProvision(a.provision);
  const topic = a.topic.trim();
  const sentence = sentenceLabel(c, a);
  if (!real || kind === "applicant") {
    return {
      key: `cand-${a.id}`,
      kind: "candidate",
      section: "C",
      eyebrow: sectionEyebrow("C"),
      title: `Does your design ${a.departure}?`,
      context: "You wrote",
      quote: a.quote.text.trim() || firstSentence(c.description),
      why: "Your answer decides whether this becomes a departure in your application. Not sure leaves the question open for review.",
      ref: a.id,
      done,
      optional: false,
    };
  }
  if (a.suggestion === "identify") {
    return {
      key: `cand-${a.id}`,
      kind: "candidate",
      section: "C",
      eyebrow: sectionEyebrow("C"),
      title: codeQuestion(topic, sentence),
      context: keywordCandidate(c, a)
        ? "A keyword match only. Its relevance has not been assessed."
        : a.rank === "committed" ? "Likely match for your project." : "Close match for your project.",
      why: "Yes adds this rule to the list of rules your design differs from (Section C of the form). No leaves it out. Not sure leaves the question open for review. Batatis never decides whether the design meets the code.",
      ref: a.id,
      done,
      optional: false,
      provision: a.provision,
    };
  }
  const origin =
    a.suggestion === "search"
      ? "You added this rule from the code library."
      : kind === "ranking"
        ? "Suggested by article ranking."
        : `About ${topic.charAt(0).toLowerCase()}${topic.slice(1)}.`;
  return {
    key: `cand-${a.id}`,
    kind: "candidate",
    section: "C",
    eyebrow: sectionEyebrow("C"),
    title: `Is your design different from what ${sentence ? `sentence ${sentence} of ` : ""}this rule asks for?`,
    context: origin,
    why: "Yes adds this rule to the list of rules your design differs from (Section C of the form). No leaves it out. Not sure leaves the question open for review.",
    ref: a.id,
    done,
    optional: false,
    provision: a.provision,
  };
}

/** Questions answered on another card, or by the description on Start, are not asked twice. */
function questionOnOtherCard(c: Case, id: string, cardId?: string): boolean {
  if (id.startsWith("q-prof-") || id.startsWith("q-scope-") || id.startsWith("q-from-") || cardId || answeredByDescription(c, id)) return true;
  return id === "q-desc-storeys" && c.candidates.some((a) => a.id === "desc-storeys");
}

/** Map a gap or link key to the card that answers it. */
export function aliasKey(c: Case, key: string): string {
  if (paperworkRowKey(c, key)) return "paperwork";
  const row = understandingRows(c, DETAIL_IDS).find((r) => r.key === key || (key.startsWith("fact-") && r.ids.includes(key.slice(5))));
  if (row && !row.separate) return "understood";
  if (key.startsWith("field-")) {
    const q = planQuestions(c).find(({ q }) => localField(q.field) === key.slice("field-".length))?.q;
    if (q) return `plan-${q.id}`;
  }
  if (key.startsWith("fact-")) {
    const id = key.slice("fact-".length);
    const group = readGroups(c, DETAIL_IDS).find((g) => g.ids.includes(id));
    if (group) return group.key;
  }
  if (key.startsWith("q-q-from-")) return `cand-${key.slice("q-q-from-".length)}`;
  if (key === "q-q-desc-storeys" && c.candidates.some((a) => a.id === "desc-storeys")) return "cand-desc-storeys";
  if (key.startsWith("q-")) {
    const q = c.questions.find((x) => `q-${x.id}` === key);
    if (q?.cardId) return `cand-${q.cardId}`;
  }
  return key;
}

/** Resolve old field/planner/fact links to the row inside the paperwork sheet. */
export function paperworkRowKey(c: Case, key: string): string | null {
  if (key === "authority" || key === "field-authority") return "authority";
  if (key === "role" || key === "field-applicant_role") return "role";
  const plan = planQuestions(c).find(({ q }) => `plan-${q.id}` === key)?.q;
  const fact = key.startsWith("fact-") ? c.facts.find((f) => f.id === key.slice(5)) ?? c.intake?.facts.find((f) => f.id === key.slice(5)) : undefined;
  const field = localField(plan?.field ?? fact?.field ?? (key.startsWith("field-") ? key.slice(6) : ""));
  return PAPERWORK_FIELDS.has(field) ? field === "applicant_role" ? "role" : `field-${field}` : null;
}

/** Keep a paperwork row's focus in fix links; the deck resolves its containing sheet on entry. */
export function gapKey(c: Case, gap: Gap): string | null {
  const href = calmHref(gap.href);
  if (!href.startsWith("#/questions")) return null;
  const focus = new URLSearchParams(href.split("?")[1] ?? "").get("focus");
  return focus ? paperworkRowKey(c, focus) ?? aliasKey(c, focus) : null;
}

export function sectionDGaps(gaps: Gap[]): Gap[] {
  return gaps.filter((g) => g.href.includes("tab=D"));
}

/** Section D is part of the deck once a real code reference, a professional screen or a Section D gap exists. */
export function sectionDRelevant(c: Case, gaps: Gap[]): boolean {
  return c.candidates.some((a) => isProvision(a.provision)) || sectionDGaps(gaps).length > 0 || c.practiceOfEngineering !== undefined;
}

const SCOPE_ITEM_KEY = "scope";

/**
 * The first card answered Yes whose departure the engine has not confirmed. One benchmark is
 * recorded per application, so only this card asks for the applicant's words; the other Yes answers
 * stay Section C rows.
 */
function departureCandidate(c: Case, opts: DeckOptions): Candidate | undefined {
  if (opts.benchmark?.departure_status === "confirmed") return undefined;
  return c.candidates.find((a) => a.answer === "yes" && !a.pending && isProvision(a.provision));
}

function departureItem(a: Candidate): UnpositionedItem {
  return {
    key: `dep-${a.id}`,
    kind: "departure",
    section: "C",
    eyebrow: sectionEyebrow("C"),
    title: "What does your design do instead?",
    context: "",
    why: "Batatis names this sentence as the benchmark in Section C of the application and records your words as the departure. The officer decides whether the departure is acceptable; Batatis never does.",
    ref: a.id,
    provision: a.provision,
    done: false,
    optional: false,
  };
}

/** Derive ordered form cards from case facts, shared gaps, coded rules and package choices. */
export function buildDeck(c: Case, gaps: Gap[], opts: DeckOptions = {}): DeckItem[] {
  const seen = opts.seen ?? new Set<string>();
  // A card a current *blocking* gap points at is open, whatever the local value says.
  // Warnings (Not sure, open questions for the officer) never lock an answered card.
  const gapKeys = new Set(gaps.filter((g) => g.severity === "blocking").map((g) => gapKey(c, g)).filter((k): k is string => !!k));
  const groups = { read: [] as DeckItem[], plan: [] as DeckItem[], A: [] as DeckItem[], B: [] as DeckItem[], questions: [] as DeckItem[], C: [] as DeckItem[], D: [] as DeckItem[] };
  const deferred = journeyAnswers(c);
  const push = (group: keyof typeof groups, source: UnpositionedItem) => {
    const item = positioned(source);
    const pending = item.kind === "candidate" && c.candidates.some((a) => a.id === item.ref && a.pending);
    const answer = pending ? undefined : deferred.get(item.key) ?? (item.stage === "paperwork" ? [...deferred.values()].find((a) => a.stage === "paperwork" && a.field === localField(item.field ?? item.ref)) : undefined);
    // Legacy uncertainty stays open on Review without asking the same card repeatedly.
    const answeredUnsure = (item.kind === "authority" && seen.has("authority")) || item.settled;
    const open = !item.done || (!item.optional && gapKeys.has(item.key) && item.kind !== "section-d" && item.kind !== "understood" && !answeredUnsure);
    const next: DeckItem = { ...item, done: answer ? true : !open, settled: answer ? true : item.settled, deferred: answer?.value, answerer: answer?.value === "designer" ? "designer" : item.answerer };
    if (item.stage === "paperwork" || opts.includeDone || (!next.done && next.answerer !== "office")) groups[group].push(next);
  };

  // While intake reads, nothing else is asked: every card after it may already be answered by what it reads.
  if (opts.intake === "running") {
    return [positioned({
      key: "reading",
      kind: "reading",
      section: "B",
      eyebrow: "Reading",
      title: "Reading what you wrote…",
      context: "Batatis reads your description and the text of your PDFs, fills in what it finds and notes where each value came from. It asks only what is missing or unclear.",
      why: "What you already wrote is used as written. You can change any value later on the review page.",
      ref: "reading",
      done: false,
      optional: true,
    })];
  }

  // Another safety-codes regime: one page and nothing else until the applicant says otherwise.
  const redirect = scopeRedirect(c);
  if (redirect && c.facts.some((f) => f.field === "scope.redirect" && f.status === "unconfirmed")) {
    return [positioned({
      key: SCOPE_ITEM_KEY,
      kind: "scope",
      section: "B",
      eyebrow: "Before we go on",
      title: `This reads as a ${redirect.regime?.name ?? "different"} question.`,
      context: redirect.message ?? "",
      why: "Batatis prepares building-code variance applications only (the National Building Code, Alberta Edition).",
      ref: SCOPE_ITEM_KEY,
      done: false,
      optional: false,
    })];
  }

  const decision = decidePath(c);
  const acceptance = productScope(c) === "product_acceptance";
  const packaged = decision.path === "acceptable" || decision.path === "alternative";

  const unread = !c.intake && Boolean(c.description.trim()) && opts.intake !== undefined;
  if (opts.intake === "error" || (unread && opts.intake === "idle")) {
    const failed = opts.intake === "error";
    push("read", {
      key: "reading",
      kind: "reading",
      section: "B",
      eyebrow: "Reading",
      title: failed ? "We couldn’t read your description just now." : "Let Batatis read your description.",
      context: failed
        ? opts.intakeNote || "Your words are saved. Try again, or answer the questions below yourself."
        : "It proposes the values it finds, with the words each came from, and asks only what is still missing.",
      why: "Without the reading, every detail about you and your project is asked as a question instead.",
      ref: "reading",
      done: false,
      optional: true,
    });
  }

  const rows = understandingRows(c, DETAIL_IDS);
  const readFields = new Set(rows.filter((r) => r.value != null && r.value !== "").map((r) => r.field));
  const shared = rows.filter((r) => !r.separate && answererOf({ kind: "question", ref: r.field, section: "B" }) !== "office");
  const acknowledgementKey = understandingAnswerKey(c, shared);
  const acknowledged = deferred.get(acknowledgementKey)?.value === "acknowledged";
  if (shared.length) push("read", {
    key: "understood", kind: "understood", section: "B", eyebrow: "Understand · Section B",
    title: "Here’s what I understood", context: "", why: "Check the values and their sources. Looks right confirms every row together; Fix opens an individual fact.",
    ref: "understood", rows: shared, ids: [...new Set(shared.filter((r) => !r.done).flatMap((r) => r.ids))],
    done: acknowledged, optional: false, acknowledgementKey,
    counts: { batatis: { open: acknowledged ? 0 : 1, done: acknowledged ? 1 : 0 } },
  });
  // Conflicts and proposals read from pictures require their own confirmation.
  for (const row of rows.filter((r) => !shared.includes(r))) {
    const copy = row.copy;
    const detail = DETAIL_FIELDS.find((d) => d.id === row.field);
    push("read", {
      key: row.key,
      kind: "fact",
      section: detail?.section === "A" ? "A" : "B",
      eyebrow: row.separate ? "Check this reading" : "To confirm with the office",
      title: copy.title,
      context: "",
      why: "We read this from what you gave us, but it isn’t clear enough to use without you.",
      ref: row.ref,
      field: row.field,
      ids: row.ids,
      read: copy,
      done: row.done,
      optional: false,
      confirmLabels: { confirm: copy.confirm, dismiss: copy.dismiss },
    });
  }
  const route = routeChoice(c);
  const fork = c.intake?.record.plan?.fork;
  if (fork && fork.variance_needed !== "unknown" && !decision.firm) push("B", {
    key: "route", kind: "route", section: "B", eyebrow: "Route · Section B",
    title: fork.variance_needed === "likely" ? "You likely need a variance" : "You may not need a variance",
    // The applicant's own sentence explains the route; the bare cue ("instead of") does not.
    context: "", quote: clip(valueText(factFor(c, "alternative")), 200) || fork.cues.join(" · ") || firstSentence(c.description) || undefined,
    why: fork.explanation, ref: "journey.route", done: route !== null, optional: false,
    // A likely variance has nothing to choose: the card's own Continue records the route.
    choices: fork.variance_needed === "likely" ? undefined : [{ value: "standard", label: "Use the standard way" }, { value: "different", label: "Something is different" }],
  });
  if (route === "different") push("B", {
    key: "route-detail", kind: "route-detail", section: "B", eyebrow: "Route · Section B",
    title: "What will be different?", context: "", why: "Describe what you want to do differently from the code’s standard way. This records your words, not a technical conclusion.",
    ref: "journey.departure", done: false, optional: false,
  });
  if (productScope(c) === "product_acceptance") push("B", {
    key: "product-notice", kind: "product-notice", section: "B", eyebrow: "Product acceptance",
    title: "A product acceptance route", context: "Across Alberta means product acceptance, for example a CCMC evaluation. A site variance is a separate request for one building or site.",
    why: "The engine’s sourced product-route notice explains the available routes.", ref: "product_scope", done: seen.has("product-notice"), optional: true,
  });
  if ((decision.path === "not_applicable" || (decision.path === "unresolved" && !decision.asksRuleInputs)) && (c.description.trim() || c.facts.length > 0) && !acceptance) {
    const copy = pathStopCopy(decision);
    push("B", {
      key: "path-stop", kind: "code-note", section: "B", eyebrow: "Route",
      title: copy.title, context: copy.context,
      why: "The package stays closed. Batatis does not decide that the design complies or is safe.",
      ref: "path-stop", done: seen.has("path-stop"), optional: true,
    });
  }
  // Files intake could not read in full say so, with the reason, once.
  for (const f of fileNotes(c)) {
    const key = `file-${f.file_id}`;
    push("read", {
      key,
      kind: "file",
      section: "B",
      eyebrow: "Your files",
      title: f.status === "not_read" ? `We couldn’t read ${f.name}.` : `We read part of ${f.name}.`,
      context: f.reason ?? "",
      why: "Each file report says what was read and what remains unread. Batatis never guesses what an unread page contains.",
      ref: f.file_id,
      done: seen.has(key),
      optional: true,
    });
  }

  // Every issued planner question takes its journey position, retaining the form mapping.
  const plan = planQuestions(c);
  const planFields = new Set(plan.map(({ q }) => localField(q.field)));
  // A description that names one coded solution asks only that solution's inputs.
  const namedInputs = decision.ruleId ? new Set(namedRuleInputs(decision.ruleId) ?? []) : null;
  for (const { q, done, notSure } of plan) {
    if (q.field === "product_scope" && decision.path !== "alternative") continue;
    if ((q.field === "alternative_description" || localField(q.field) === "alternative") && decision.path !== "alternative") continue;
    // A firm check has the inputs it needs. A named rule asks only its own remaining inputs.
    if (decision.firm && q.priority !== "administrative" && q.field !== "product_scope") continue;
    if (namedInputs && q.priority !== "administrative" && q.field !== "product_scope"
        && !namedInputs.has(q.field) && !namedInputs.has(localField(q.field))) continue;
    if (PAPERWORK_FIELDS.has(localField(q.field)) && q.kind !== "conflict") continue;
    if (readFields.has(localField(q.field)) && q.kind !== "conflict") continue;
    const detail = DETAIL_FIELDS.find((d) => d.id === localField(q.field));
    push("plan", {
      key: `plan-${q.id}`,
      kind: q.field === "product_scope" ? "product-scope" : "plan",
      section: detail?.section ?? "B",
      eyebrow: q.kind === "conflict" ? "You wrote two things" : q.priority === "administrative" ? sectionEyebrow(detail?.section ?? "B") : "A quick question",
      title: q.field === "product_scope" ? "One building, or across Alberta?" : q.text,
      context: "",
      why: q.why,
      ref: q.id,
      done,
      optional: false,
      settled: notSure,
      plan: q,
      choices: q.field === "product_scope" ? [{ value: "site", label: "One building or site" }, { value: "product_acceptance", label: "Across Alberta" }] : undefined,
    });
  }

  push("A", {
    key: "role", kind: "role", section: "A", eyebrow: sectionEyebrow("A"),
    title: "Your part in this project", context: "", why: "Your part helps direct questions to the person who can answer them.", ref: "applicant_role",
    done: [...ROLE_CHOICES.map((r) => r.value), "homebuilder", "builder", "architect-engineer"].includes(String(factFor(c, "applicant_role")?.value ?? "")), optional: true,
    choices: ROLE_CHOICES,
  });

  // Remaining form details and the office are placed in paperwork.
  push("B", {
    key: "authority",
    kind: "authority",
    section: "B",
    eyebrow: sectionEyebrow("B"),
    title: "Who will review your application?",
    context: "",
    why: "The town, city or county that issues your permit. Each has its own submission rules. Batatis never picks one for you.",
    ref: "authority",
    // Read from the site's municipality, it is a quiet confirmation offered once (with the office's
    // pack); unanswered, it is required.
    done: Boolean(c.authority && confirmedAnswer(c.facts, "office.choice")?.value === c.authority) || (opts.confirmAuthority ? seen.has("authority") : Boolean(c.authority) || seen.has("authority")),
    optional: Boolean(opts.confirmAuthority && c.authority),
    settled: !c.authority && seen.has("authority"),
    assumed: Boolean(opts.confirmAuthority && c.authority),
  });
  const planned = plannedFields(c);
  for (const d of DETAIL_FIELDS) {
    if ((d.id === "scope" || d.id === "alternative") && decision.path !== "alternative") continue;
    const paperwork = PAPERWORK_FIELDS.has(d.id);
    if (readFields.has(d.id) && !paperwork) continue;
    const fact = factFor(c, d.id);
    if (fact?.status === "unconfirmed" && !paperwork) continue; // asked on its "check what we read" card
    // A choice field counts only with one of its choices (a free-text answer elsewhere can land here).
    // A legal description read as lot, block and plan is filled, as the sheet shows it.
    const fromParts = d.id === "legalDescription" && Boolean(legalFromFacts(c.facts));
    const filled = d.options ? valueText(fact) in d.options : Boolean(valueText(fact).trim()) || fromParts;
    if (!d.required && filled && !opts.includeDone && !paperwork) continue;
    // One editable card per field, including in footer navigation and after a planner answer is saved.
    const cover = planned.get(d.id);
    if (planFields.has(d.id) && !paperwork) continue;
    // The proposed alternative is usually what the applicant already described on Start: offer
    // those words instead of asking again. Nothing is filled until they say yes.
    const offer = d.id === "alternative" && Boolean(c.description.trim());
    const siteAddress = d.id === "mailingAddress" ? confirmedAnswer(c.facts, "municipalAddress") : undefined;
    const suggestedValue = !filled ? (d.id === "date" ? opts.today : siteAddress ? String(siteAddress.value) : undefined) : undefined;
    push(d.section, {
      key: `field-${d.id}`,
      kind: "detail",
      section: d.section,
      eyebrow: sectionEyebrow(d.section),
      title: offer ? "Is this what you want to do differently?" : DETAIL_QUESTION[d.id] ?? d.label,
      context: offer || (d.options && valueText(fact).trim() && !filled) ? "You wrote" : "",
      quote: offer ? clip(c.description, 240) : d.options && valueText(fact).trim() && !filled ? valueText(fact).trim() : undefined,
      why: offer
        ? "The form asks what you will do instead of the code’s standard way (the acceptable solution)."
        : `The variance form asks for the ${d.label.toLowerCase()} (Section ${d.section}).${d.hint ? ` ${d.hint}.` : ""}`,
      ref: d.id,
      done: d.required ? filled || Boolean(cover?.notSure) : filled || seen.has(`field-${d.id}`),
      optional: !d.required,
      settled: Boolean(cover?.notSure) && !filled,
      confirmLabels: offer ? { confirm: "Yes, use my description", dismiss: "No, I’ll write it" } : undefined,
      suggestedValue,
      assumed: Boolean(suggestedValue),
    });
  }

  // Open questions: project questions, and questions from code matching.
  for (const q of c.questions) {
    if (questionOnOtherCard(c, q.id, q.cardId)) continue;
    if (PAPERWORK_FIELDS.has(localField(q.field))) continue;
    if (readFields.has(localField(q.field)) || planFields.has(localField(q.field))) continue;
    const fromCode = q.kind === "intake" || q.id.startsWith("q-identify-");
    push(fromCode ? "C" : "questions", {
      key: `q-${q.id}`,
      kind: "question",
      section: fromCode ? "C" : "B",
      eyebrow: fromCode ? sectionEyebrow("C") : "A quick question",
      title: q.text,
      context: "",
      why: q.why,
      ref: q.id,
      field: q.field,
      done: Boolean(q.answer?.trim()) || questionAnsweredByFact(c, q),
      optional: false,
    });
  }

  // 4. The code check: committed articles and at most three quoted choices, plus anything the
  // applicant added from the library. The rest of the ranking stays in the library.
  const described = Boolean(c.intake || c.description.trim());
  if (described && !c.identify) {
    push("C", {
      key: "code-run",
      kind: "code-run",
      section: "C",
      eyebrow: sectionEyebrow("C"),
      title: opts.identify === "error" ? "The code check didn’t finish." : opts.identify === "running" ? "Checking the code for your project…" : "Check the code for your project.",
      context: opts.identify === "running"
        ? "Batatis reads every rule in the building code against what you described. Keep answering; your rule questions join the list when it’s done."
        : opts.identify === "error"
          ? "Your answers are kept. Try again, or find the rule in the code yourself."
          : "Batatis reads every rule in the building code against what you described and asks you about the closest few.",
      why: "This finds the rule your design differs from. It is a list of candidates, never a decision that the design meets the code.",
      ref: "code-run",
      done: false,
      optional: true,
    });
  }
  const id = c.identify;
  // `screen: "requirements"` returns a ledger, not a short ranking: `committed` and `choices` are
  // empty and every candidate lives in `requirements`. Review is optional and arrives in batches.
  const ledger = id ? requirementQueue(id) : null;
  if (id && (!id.narrowed || id.mode === "bm25_fallback") && !ledger?.found) {
    push("C", {
      key: "code-note",
      kind: "code-note",
      section: "C",
      eyebrow: sectionEyebrow("C"),
      title: !id.narrowed ? (id.message?.split(/(?<=\.)\s/)[0] ?? "I could not narrow this down.") : "This list comes from a keyword search.",
      context: !id.narrowed ? (id.message?.split(/(?<=\.)\s/).slice(1).join(" ") || "Find the rule in the code yourself, or answer the questions so the next check can narrow it.") : "The full check wasn’t available, so these are keyword matches only. Treat each one as a lead, not a finding.",
      why: id.label,
      ref: "code-note",
      done: seen.has("code-note"),
      optional: true,
    });
  }
  // Standing packages that fit this project: offered once; accepted, one condition at a time.
  const inPlay = caseRules(c, opts);
  for (const cl of matchingChecklists(c, opts.checklists ?? null, inPlay)) {
    const answered = cl.conditions.some((x) => x.answer);
    const savedChoice = factFor(c, `journey.package.${cl.id}`)?.value;
    const choice = savedChoice === "yes" || savedChoice === "no" ? savedChoice : opts.packages?.[cl.id];
    push("C", {
      key: `pkg-${cl.id}`,
      kind: "package",
      section: "C",
      eyebrow: "A pre-reviewed path",
      title: "Your city has a pre-reviewed path for this kind of project.",
      context: `Follow the conditions of its standing package ${cl.code}, ${cl.title}, instead of building a full case?`,
      why: `${cl.summary} ${cl.notice}`,
      ref: cl.id,
      done: Boolean(choice) || answered,
      // A real choice; a deferral is recorded on the case.
      optional: false,
      checklist: cl.id,
      choices: [{ value: PACKAGE_YES, label: "Yes, follow its conditions" }, { value: PACKAGE_NO, label: "No, build my own case" }],
    });
    if (choice === "no" || (choice !== "yes" && !answered)) continue;
    for (const row of cl.conditions) {
      if (!row.answer && coveredByOption(cl, row)) continue;
      const group = groupOf(cl, row);
      push("C", {
        key: `pkgc-${cl.id}-${row.id}`,
        kind: "condition",
        section: "C",
        eyebrow: `${cl.code} · ${group?.title ?? "Condition"}`,
        title: row.plain,
        context: row.when ?? "",
        why: group?.plain ?? cl.notice,
        ref: row.id,
        done: Boolean(row.answer),
        optional: false,
        checklist: cl.id,
        condition: row.id,
        choices: conditionChoices(row),
      });
    }
    const full = followedInFull(cl);
    push("C", {
      key: `pkgend-${cl.id}`,
      kind: "package-end",
      section: "C",
      eyebrow: cl.code,
      title: full ? `You’ve answered every condition of ${cl.code}.` : `${cl.code} is not yet followed in full.`,
      context: `${tallyLine(cl)}. This is your declaration, not a decision: the officer decides whether the package can be used.`,
      why: cl.notice,
      ref: cl.id,
      done: seen.has(`pkgend-${cl.id}`),
      optional: true,
      checklist: cl.id,
    });
  }

  // Coded rules: the inputs each still needs (one per field), then the result. A result for an
  // article that already has a code-check card sits on that card instead of a second one.
  const index = opts.rules?.index;
  const facts = index ? ruleFacts(c, index) : new Map();
  const pool = opts.rules ? caseRuleResults(c, opts.rules, opts.storedRules) : [];
  const namedRule = decision.ruleId ? pool.find((r) => r.rule_id === decision.ruleId) : undefined;
  const rulesToShow = namedRule ? [namedRule] : inPlay;
  const missing = new Set([
    ...rulesToShow.flatMap((r) => r.missing.map((m) => m.field)),
    ...(decision.ruleId ? decision.missing : []),
  ]);
  const asked = new Set<string>();
  /** Add each needed rule input once, leaving fields already handled by the planner on its cards. */
  const ruleInputs = (r: ShownRule) => {
    if (!index) return;
    const mine = new Set([...r.missing.map((m) => m.field), ...(decision.ruleId === r.rule_id ? decision.missing : [])]);
    const fields = r.inputs.map((i) => i.field).filter((f) => mine.has(f) || facts.get(f)?.source.ref?.startsWith(RULE_REF));
    for (const f of fields) {
      // A planner question asks this field already (or it was answered Not sure there).
      if (asked.has(f) || planned.has(f) || readFields.has(f) || !index.inputs[f]) continue;
      asked.add(f);
      push("C", {
        key: `rulein-${f}`,
        kind: "rule-input",
        section: "C",
        eyebrow: sectionEyebrow("C"),
        title: index.inputs[f].question,
        context: "",
        why: `${index.inputs[f].why} Batatis compares it with the code’s standard way for ${ruleTopic(r).toLowerCase()}.`,
        ref: f,
        done: !missing.has(f),
        optional: false,
        provision: r.provision.id,
        input: { field: f, spec: index.inputs[f], rule: r.rule_id },
        choices: inputChoices(index.inputs[f]),
      });
    }
  };
  /** Build a follows or departs card; unresolved and inapplicable rules have no result card. */
  const resultItem = (r: ShownRule): UnpositionedItem | null => {
    if (r.state !== "departs" && r.state !== "follows") return null;
    const plain = plainResult(r);
    const key = `rule-${r.rule_id}`;
    return {
      key,
      kind: "rule",
      section: "C",
      eyebrow: sectionEyebrow("C"),
      title: plain.title,
      context: plain.line,
      why: RULE_WHY,
      ref: r.rule_id,
      done: seen.has(key) || factFor(c, `journey.rule.${r.rule_id}`)?.value === RULE_LEAVE,
      // A departure needs an answer (add the rule, or leave it out); a "follows" result is a note.
      optional: r.state === "follows",
      provision: r.provision.id,
      rule: r,
      choices: r.state === "departs" ? [{ value: RULE_ADD, label: "Add this rule to my application" }, { value: RULE_LEAVE, label: "Leave it out for now" }] : [],
    };
  };
  // A keyword-only lead stays behind the topic triage until the applicant opens it (or answers Yes).
  const behindTriage = (a: Candidate) => keywordCandidate(c, a) && a.answer !== "yes" && opts.focusedCandidate !== `cand-${a.id}`;
  const linked = new Map<string, ShownRule>();
  for (const r of rulesToShow) {
    const card = linkedCandidate(c, r);
    // A rule never hides on a lead that is not shown: it keeps its own card instead.
    if (card && !behindTriage(card)) { linked.set(card.id, r); continue; }
    ruleInputs(r);
    const item = resultItem(r);
    if (item) push("C", item);
  }

  const keyword = keywordGroups(c);
  if (keyword.length) {
    push("C", {
      key: "code-triage", kind: "code-triage", section: "C", eyebrow: sectionEyebrow("C"),
      title: "Review the keyword matches by topic.",
      context: `${keyword.length} articles matched words in your description. This search could not assess which apply. Open a topic to inspect its sentences, or find the rule yourself.`,
      why: "These are unconfirmed leads, not relevance scores or technical decisions. Only an explicit Yes adds a code reference. Leaving a lead unanswered does not mean No.",
      ref: "code-triage", done: seen.has("code-triage"), optional: true,
    });
  }
  const asking = departureCandidate(c, opts);
  for (const a of c.candidates) {
    if (!behindTriage(a)) {
      const r = linked.get(a.id);
      if (r) ruleInputs(r);
      const base = candidateItem(c, a);
      const item = r && (r.state === "departs" || r.state === "follows") ? { ...base, rule: r } : base;
      // An opened keyword lead stays optional: leaving it unanswered does not mean No.
      push("C", keywordCandidate(c, a) && a.answer !== "yes" ? { ...item, optional: true } : item);
    }
    if (asking?.id === a.id) push("C", departureItem(a));
  }

  // 4b. The requirement ledger: its counts stay reachable, and the closest unanswered rules are asked
  // about one at a time. Applicability is answered here; a departure is asked on its own card after.
  if (ledger?.found) {
    push("C", {
      key: "code-ledger",
      kind: "code-ledger",
      section: "C",
      eyebrow: sectionEyebrow("C"),
      title: "Rules that may apply",
      context: ledger.reviewable
        ? `${ledger.found} rules mention what you described. ${ledger.reviewable} ${ledger.reviewable === 1 ? "is" : "are"} still unanswered; the closest ${ledger.batch.length} come next.`
        : `You answered all ${ledger.found} rules that mention what you described.`,
      why: "Batatis finds rules by searching the code’s wording and the sections each one points to. A match means a rule mentions your project, not that your design differs from it. You decide whether each rule applies; the officer reviews that answer.",
      ref: "code-ledger",
      done: seen.has("code-ledger"),
      optional: true,
    });
    // Answered rules keep their card (done) so the answer can be changed; the ledger order stays.
    const shown = new Set([...ledger.answered, ...ledger.batch]);
    for (const record of (id?.requirements ?? []).filter((r) => shown.has(r))) {
      push("C", {
        key: `req-${record.id}`,
        kind: "requirement",
        section: "C",
        eyebrow: sectionEyebrow("C"),
        title: "Does this rule apply to your project?",
        context: requirementTopic(record),
        why: "The rule was found because your description matches its wording or a section it points to. If it applies, the next card asks how your design differs from it. If it does not, say why. Batatis never decides this for you.",
        ref: record.id,
        done: requirementAnswer(record) !== null,
        optional: true,
        provision: record.provision_id ?? undefined,
        requirement: record,
      });
    }
  }

  // 5. The six process fields are the alternative path only. They are not evidence.
  if (decision.path === "alternative" && !acceptance) for (const p of PROCESS_FIELDS) {
    push("D", {
      key: `field-${p.id}`,
      kind: "process",
      section: "D",
      eyebrow: sectionEyebrow("D"),
      title: PROCESS_QUESTION[p.id] ?? p.label,
      context: WRITTEN_BY_YOU,
      why: `Because your design differs from the code’s standard way, the form needs this in your own words (it calls it ${p.label.toLowerCase()}). It can’t be skipped, and it has to come from you or your professional.`,
      ref: p.id,
      done: Boolean(c.process[p.id].trim()),
      optional: false,
    });
  }

  // 6. Shared evidence ladder on the acceptable path, plus the alternative types on that path.
  if (packaged && !acceptance) {
    const dGaps = sectionDGaps(gaps);
    const actions = preparationGaps(c, dGaps);
    const pendingForOfficer = dGaps.length > 0 && actions.applicant.length === 0 && actions.checkNeeded.length === 0;
    const needsCheck = actions.checkNeeded.length > 0 && actions.applicant.length === 0;
    push("D", {
      key: "section-d",
      kind: "section-d",
      section: "D",
      eyebrow: sectionEyebrow("D"),
      title: "Who is responsible, and which documents back this up?",
      context: "Review a draft evidence plan. Your engineer or architect supplies the professional evidence.",
      why: decision.path === "acceptable"
        ? "This lists the shared evidence ladder. It is not a finding that the design complies or is safe."
        : "This part of the form (Section D) names the engineer or architect responsible and lists the proof for each rule your design differs from. Process fields are separate from these documents. Batatis does not write that proof.",
      ref: "section-d",
      done: (seen.has("section-d") && dGaps.length === 0) || pendingForOfficer || needsCheck,
      optional: pendingForOfficer || needsCheck,
      pendingForOfficer,
      needsCheck,
      counts: professionalCounts(c),
    });
  }
  const items = [...groups.read, ...groups.plan, ...groups.A, ...groups.B, ...groups.questions, ...groups.C, ...groups.D];
  const paperworkRows = orderJourney(items.filter((item) => item.stage === "paperwork"));
  const rowsForRoute = paperworkRows.filter((row) => (decision.path === "alternative" && !acceptance) || row.ref !== "scope");
  const counts: DeckItem["counts"] = {};
  for (const row of rowsForRoute.filter((row) => !row.optional)) {
    const count = counts[row.answerer] ??= { open: 0, done: 0 };
    if (itemOpen(row)) count.open++;
    else count.done++;
  }
  const sheet: DeckItem = {
    key: "paperwork", kind: "paperwork", section: "A", stage: "paperwork", answerer: "you",
    eyebrow: "Paperwork", title: "Last details for the form", context: "",
    why: "These details fill the form. Tap a default to accept it, or leave a row for Later. Done saves your answers.",
    ref: "paperwork", optional: false, done: rowsForRoute.every((row) => row.done || row.optional),
    paperworkRows: rowsForRoute, counts,
  };
  const cards = items.filter((item) => item.stage !== "paperwork" && (!acceptance || (item.stage !== "case" && item.stage !== "proof" && item.kind !== "candidate" && item.kind !== "rule" && item.kind !== "package" && item.kind !== "condition" && item.kind !== "package-end")));
  if (opts.includeDone || !sheet.done) cards.push(sheet);
  return orderJourney(cards);
}

/** Keys after `index` that match `pick` take the current journey order. */
export function rankAhead(queue: string[], index: number, order: string[], pick: (k: string) => boolean): string[] {
  const at = queue.map((k, i) => (i > index && pick(k) && order.includes(k) ? i : -1)).filter((i) => i >= 0);
  if (at.length < 2) return queue;
  const keys = at.map((i) => queue[i]).sort((a, b) => order.indexOf(a) - order.indexOf(b));
  const out = [...queue];
  at.forEach((i, n) => { out[i] = keys[n]; });
  return out.join("|") === queue.join("|") ? queue : out;
}

/** Insert each new key after the last queued key that comes before it in the journey. */
export function mergeQueue(queue: string[], fresh: string[], order: string[]): string[] {
  const out = [...queue];
  for (const k of fresh) {
    if (out.includes(k)) continue;
    const pos = order.indexOf(k);
    let at = -1;
    out.forEach((q, i) => {
      const p = order.indexOf(q);
      if (p >= 0 && p < pos) at = i;
    });
    out.splice(at + 1, 0, k);
  }
  return out;
}

export const ROLE_CHOICES: { value: ApplicantType; label: string }[] = [
  { value: "owner", label: "Owner" },
  { value: "designer", label: "Designer or architect" },
  { value: "engineer", label: "Engineer" },
  { value: "contractor", label: "Builder or contractor" },
  { value: "manufacturer", label: "Manufacturer" },
  { value: "other", label: "Someone else" },
];

/** Which of the two alternative answers the saved value means (the description, or the applicant's own words). */
export function alternativeChoice(description: string, value: string): "confirm" | "dismiss" | undefined {
  const v = value.trim();
  if (!v) return undefined;
  return v === description.trim() ? "confirm" : "dismiss";
}

/**
 * Before an application exists the Questions stage asks nothing. Start is the one place to describe
 * the project (and to pick who is applying when onboarding has not), so there is no card to repeat
 * it here: just a quiet line and the way back to Start.
 */
export function preCaseState(draft: string): { items: DeckItem[]; line: string; action: string } {
  const started = Boolean(draft.trim());
  return {
    items: [],
    line: started ? "You’ve started describing your project. Finish it and your questions start here." : "Your questions start once you describe your project.",
    action: started ? "Continue describing" : "Describe your project",
  };
}

/** Answered out of tracked (non-optional) cards. */
export function deckProgress(items: DeckItem[]): { done: number; total: number } {
  const stages = journeyProgress(items).stages;
  return { done: stages.reduce((n, s) => n + s.done, 0), total: stages.reduce((n, s) => n + s.total, 0) };
}

/** One current question; saved uncertainty is never labelled answered. */
export function questionProgress(item: DeckItem, currentKey: string | undefined): "current" | "done" | "uncertain" | "open" {
  if (item.key === currentKey) return "current";
  if (item.settled) return "uncertain";
  return item.done ? "done" : "open";
}

export const QUESTION_PROGRESS_LABEL = { current: "Current question", done: "Answered", uncertain: "Left open", open: "Unanswered" };

/** Letter key for a choice (A, B, C…), Typeform style. */
export const choiceKey = (n: number) => String.fromCharCode(65 + n);

/** Per-section progress for the footer: the queue's cards in that section, in queue order. */
export function sectionProgress(items: DeckItem[]): { id: SectionId; label: string; items: DeckItem[]; done: number }[] {
  return SECTIONS.map((s) => {
    const mine = items.filter((i) => i.section === s.id && !i.optional);
    return { ...s, items: mine, done: mine.filter((i) => i.done && !i.settled).length };
  });
}

/** Choices for a card, in keyboard order (A, B, C). */
function answerChoices(item: DeckItem): { value: string; label: string }[] {
  // Which way the wall faces is asked in place words (neighbour's lot, lane, street), not the rule's Yes/No.
  if (item.kind === "rule-input" && item.input?.field === "faces_public_way") return planInput("faces_public_way").choices ?? [];
  if (item.choices) return item.choices;
  if (item.kind === "plan" && item.plan) {
    const input = planInput(item.plan.field);
    return input.kind === "choices" ? input.choices ?? [] : [];
  }
  if (item.kind === "fact") return [{ value: "confirm", label: item.confirmLabels?.confirm ?? "Yes, that’s right" }, { value: "dismiss", label: item.confirmLabels?.dismiss ?? "No, something else" }];
  // The office is found by typing in its own search box; letter keys would pick an arbitrary place.
  if (item.kind === "authority") return [];
  if (item.kind === "candidate") {
    return item.provision
      ? [{ value: "yes", label: "Yes, it differs" }, { value: "no", label: "No, it follows" }]
      : [{ value: "yes", label: "Yes" }, { value: "no", label: "No" }];
  }
  if (item.kind === "requirement") {
    return [
      { value: "applies", label: "Yes, it applies" },
      { value: "does-not-apply", label: "No, it doesn’t apply" },
      { value: "not-sure", label: "Not sure" },
    ];
  }
  if (item.kind === "detail") {
    if (item.suggestedValue) return [{ value: "use-suggested", label: item.ref === "date" ? "Use today" : "Same as the site address" }, { value: "edit-suggested", label: "Use something else" }];
    if (item.confirmLabels) return [{ value: "confirm", label: item.confirmLabels.confirm }, { value: "dismiss", label: item.confirmLabels.dismiss }];
    const def = DETAIL_FIELDS.find((d) => d.id === item.ref);
    if (def?.options) return Object.entries(def.options).map(([value, label]) => ({ value, label }));
  }
  return [];
}

export function deferralFor(item: DeckItem): { value: Exclude<JourneyAnswerValue, "acknowledged">; label: string } | null {
  // A departure the applicant says exists cannot be deferred: without their words Section C names
  // an acceptable solution the application never says it departs from.
  if (["understood", "paperwork", "reading", "file", "code-run", "code-note", "code-triage", "package-end", "product-notice", "route", "scope", "departure"].includes(item.kind)) return null;
  if (item.stage === "paperwork") return { value: "later", label: "Later" };
  return item.answerer === "designer" ? { value: "designer", label: "Ask my designer" } : { value: "not_sure", label: "Not sure" };
}

/** Picking an offered answer saves it immediately; free text uses the primary action. */
export function choicesFor(item: DeckItem): { value: string; label: string }[] {
  const choices = answerChoices(item);
  const defer = deferralFor(item);
  return choices.length && defer && !choices.some((c) => /not sure|ask my designer|later/i.test(c.label)) ? [...choices, defer] : choices;
}
