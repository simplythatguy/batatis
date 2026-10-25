/**
 * The question deck: one card per thing the applicant still has to answer.
 * Pure and derived. Every card comes from the case and the shared gap list; nothing is typed by hand.
 * Card keys reuse the legacy focus ids (field-*, cand-*, fact-*, q-*), so gap hrefs land on cards.
 *
 * Order: Section A → B → C → D. Reading and planner cards stay in the section they fill.
 */
import type { Question as PlanQuestion } from "../api/types.gen";
import { AUTHORITIES } from "../config";
import { confirmedAnswer, localField } from "../intakeFields";
import { codeQuestion, fileNotes, type ReadCopy, planInput, planQuestions, plannedFields, readCopy, readGroups, scopeRedirect } from "../intakeView";
import { DETAIL_FIELDS, DETAIL_IDS, PROCESS_FIELDS, answeredByDescription, factFor, questionAnsweredByFact, valueText } from "../model";
import { isProvision, keywordCandidate, keywordGroups } from "../provisions";
import { quoteKind } from "../rules";
import type { ApplicantType, Candidate, Case, Gap } from "../types";
import type { CaseChecklists, CaseRules } from "../api/types.gen";
import type { InputSpec } from "../rules/evaluate";
import { conditionChoices, coveredByOption, followedInFull, groupOf, matchingChecklists, tallyLine } from "./checklistView";
import { calmHref } from "./routes";
import { caseRuleResults, inputChoices, linkedCandidate, plainResult, RULE_REF, ruleFacts, ruleInPlay, ruleTopic, type RuleData, type ShownRule } from "./rulesView";
import { preparationGaps } from "./preparation";

/** Choice values on rule and package cards. */
export const RULE_ADD = "add";
export const RULE_LEAVE = "leave";
export const PACKAGE_YES = "yes";
export const PACKAGE_NO = "no";

export type DeckKind =
  | "fact" | "file" | "plan" | "candidate" | "storeys" | "question" | "authority" | "detail" | "process" | "section-d"
  /** Intake reading the description and files, or failed (with Try again). */
  | "reading"
  /** Code identification running, not run yet, or failed (with Try again). */
  | "code-run"
  /** "I could not narrow this down", or the labelled keyword fallback. */
  | "code-note"
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
  eyebrow: string;
  title: string;
  /** One muted line under the question. */
  context: string;
  /** The applicant's own words, shown quoted after `context`. */
  quote?: string;
  why: string;
  /** What the card edits: fact id, candidate id, question id or field id. */
  ref: string;
  done: boolean;
  /** Offered once; Skip does not bring it back and it is not counted. */
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
}

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
  /** Rule inputs answered Not sure in this visit: not asked again. */
  ruleUnsure?: ReadonlySet<string>;
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

export const WRITTEN_BY_YOU = "You write this in your own words. Batatis never writes it for you.";

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

/** Build a code-check card, keeping answers open until the engine stores them. */
function candidateItem(c: Case, a: Candidate): DeckItem {
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
      why: "The count decides which part of the code is the benchmark. Buildings up to 3 storeys usually follow Part 9; larger ones follow Part 3. Skip leaves the question open for review.",
      ref: a.id,
      done: done || Boolean(confirmedAnswer(c.facts, "storeys")),
      optional: false,
    };
  }
  const kind = quoteKind(a);
  const real = isProvision(a.provision);
  const topic = a.topic.trim();
  if (!real || kind === "applicant") {
    return {
      key: `cand-${a.id}`,
      kind: "candidate",
      section: "C",
      eyebrow: sectionEyebrow("C"),
      title: `Does your design ${a.departure}?`,
      context: "You wrote",
      quote: a.quote.text.trim() || firstSentence(c.description),
      why: "Your answer decides whether this becomes a departure in your application. Skip leaves the question open for review.",
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
      title: codeQuestion(topic),
      context: keywordCandidate(c, a)
        ? "A keyword match only. Its relevance has not been assessed."
        : a.rank === "committed" ? "Likely match for your project." : "Close match for your project.",
      why: "Yes adds this rule to the list of rules your design differs from (Section C of the form). No leaves it out. Skip leaves the question open for review. Batatis never decides whether the design meets the code.",
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
    title: "Is your design different from what this rule asks for?",
    context: origin,
    why: "Yes adds this rule to the list of rules your design differs from (Section C of the form). No leaves it out. Skip leaves the question open for review.",
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

/** The deck key a gap's fix link opens, or null when the fix is not a card (Start, references). */
export function gapKey(c: Case, gap: Gap): string | null {
  const href = calmHref(gap.href);
  if (!href.startsWith("#/questions")) return null;
  const focus = new URLSearchParams(href.split("?")[1] ?? "").get("focus");
  return focus ? aliasKey(c, focus) : null;
}

export function sectionDGaps(gaps: Gap[]): Gap[] {
  return gaps.filter((g) => g.href.includes("tab=D"));
}

/** Section D is part of the deck once a real code reference, a professional screen or a Section D gap exists. */
export function sectionDRelevant(c: Case, gaps: Gap[]): boolean {
  return c.candidates.some((a) => isProvision(a.provision)) || sectionDGaps(gaps).length > 0 || c.practiceOfEngineering !== undefined;
}

const SCOPE_ITEM_KEY = "scope";

/** Derive ordered form cards from case facts, shared gaps, coded rules and package choices. */
export function buildDeck(c: Case, gaps: Gap[], opts: DeckOptions = {}): DeckItem[] {
  const seen = opts.seen ?? new Set<string>();
  // A card a current *blocking* gap points at is open, whatever the local value says.
  // Warnings (Not sure, open questions for the officer) never lock an answered card.
  const gapKeys = new Set(gaps.filter((g) => g.severity === "blocking").map((g) => gapKey(c, g)).filter((k): k is string => !!k));
  const groups = { read: [] as DeckItem[], plan: [] as DeckItem[], A: [] as DeckItem[], B: [] as DeckItem[], questions: [] as DeckItem[], C: [] as DeckItem[], D: [] as DeckItem[] };
  const push = (group: keyof typeof groups, item: DeckItem) => {
    // Legacy uncertainty stays open on Review without asking the same card repeatedly.
    const answeredUnsure = (item.kind === "authority" && seen.has("authority")) || item.settled;
    const open = !item.done || (!item.optional && gapKeys.has(item.key) && item.kind !== "section-d" && !answeredUnsure);
    const next = { ...item, done: !open };
    if (opts.includeDone || !next.done) groups[group].push(next);
  };

  // While intake reads, nothing else is asked: every card after it may already be answered by what it reads.
  if (opts.intake === "running") {
    return [{
      key: "reading",
      kind: "reading",
      section: "B",
      eyebrow: "Reading",
      title: "Reading what you wrote…",
      context: "Batatis reads your description and the text of your PDFs, and marks the words each value came from. Nothing is used until you confirm it.",
      why: "Values read from your words are proposals. You confirm each one, and Batatis never asks again what you confirmed.",
      ref: "reading",
      done: false,
      optional: true,
    }];
  }

  // Another safety-codes regime: one page and nothing else until the applicant says otherwise.
  const redirect = scopeRedirect(c);
  if (redirect && c.facts.some((f) => f.field === "scope.redirect" && f.status === "unconfirmed")) {
    return [{
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
    }];
  }

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

  // 1. What we read from the applicant's words and files, one thing to check per card.
  for (const g of readGroups(c, DETAIL_IDS)) {
    // Once answered, a Section A or B value lives on its form card (same key), editable there.
    if (g.done && DETAIL_IDS.has(g.fact.field)) continue;
    const copy = readCopy(c, g);
    const detail = DETAIL_FIELDS.find((d) => d.id === g.fact.field);
    push("read", {
      key: g.key,
      kind: "fact",
      section: detail?.section === "A" ? "A" : "B",
      eyebrow: "Check what we read",
      title: copy.title,
      context: "",
      why: "We read this from what you gave us. Nothing is used until you confirm it.",
      ref: g.fact.id,
      ids: g.ids,
      read: copy,
      done: g.done,
      optional: false,
      confirmLabels: { confirm: copy.confirm, dismiss: copy.dismiss },
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
      why: "Batatis reads the text layer of PDFs and fillable forms. It does not read images, and it never guesses.",
      ref: f.file_id,
      done: seen.has(key),
      optional: true,
    });
  }

  // 2. Every issued planner question; the final section sort places each in the form.
  const plan = planQuestions(c);
  const planFields = new Set(plan.map(({ q }) => localField(q.field)));
  for (const { q, done, notSure } of plan) {
    const detail = DETAIL_FIELDS.find((d) => d.id === localField(q.field));
    push("plan", {
      key: `plan-${q.id}`,
      kind: "plan",
      section: detail?.section ?? "B",
      eyebrow: q.kind === "conflict" ? "You wrote two things" : q.priority === "administrative" ? sectionEyebrow(detail?.section ?? "B") : "A quick question",
      title: q.text,
      context: "",
      why: q.why,
      ref: q.id,
      done,
      optional: false,
      settled: notSure,
      plan: q,
    });
  }

  // 3. The remaining Section A and B details. Section B opens with the reviewing authority.
  push("B", {
    key: "authority",
    kind: "authority",
    section: "B",
    eyebrow: sectionEyebrow("B"),
    title: "Who will review your application?",
    context: "",
    why: `The authority that issues your permit: ${AUTHORITIES.map((a) => a.name).join(" or ")}. Each has its own submission rules. Batatis never picks one for you.`,
    ref: "authority",
    // Read from the site's municipality, it is a quiet confirmation offered once (with the office's
    // pack); unanswered, it is required.
    done: opts.confirmAuthority ? seen.has("authority") : Boolean(c.authority) || seen.has("authority"),
    optional: Boolean(opts.confirmAuthority && c.authority),
    settled: !c.authority && seen.has("authority"),
  });
  const planned = plannedFields(c);
  for (const d of DETAIL_FIELDS) {
    const fact = factFor(c, d.id);
    if (fact?.status === "unconfirmed") continue; // asked on its "check what we read" card
    // A choice field counts only with one of its choices (a free-text answer elsewhere can land here).
    const filled = d.options ? valueText(fact) in d.options : Boolean(valueText(fact).trim());
    if (!d.required && filled && !opts.includeDone) continue;
    // One editable card per field, including in footer navigation and after a planner answer is saved.
    const cover = planned.get(d.id);
    if (planFields.has(d.id)) continue;
    // The proposed alternative is usually what the applicant already described on Start: offer
    // those words instead of asking again. Nothing is filled until they say yes.
    const offer = d.id === "alternative" && Boolean(c.description.trim());
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
    });
  }

  // Open questions: project questions, and questions from code matching.
  for (const q of c.questions) {
    if (questionOnOtherCard(c, q.id, q.cardId)) continue;
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
  if (id && (!id.narrowed || id.mode === "bm25_fallback")) {
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
    const choice = opts.packages?.[cl.id];
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
      // A real choice: skipped, it comes back once at the end of the pass (even if it joined late).
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
  const unsure = opts.ruleUnsure ?? new Set<string>();
  const missing = new Set(inPlay.flatMap((r) => r.missing.map((m) => m.field)));
  const asked = new Set<string>();
  /** Add each needed rule input once, leaving fields already handled by the planner on its cards. */
  const ruleInputs = (r: ShownRule) => {
    if (!index) return;
    const mine = new Set(r.missing.map((m) => m.field));
    const fields = r.inputs.map((i) => i.field).filter((f) => mine.has(f) || facts.get(f)?.source.ref?.startsWith(RULE_REF) || (unsure.has(f) && !facts.has(f)));
    for (const f of fields) {
      // A planner question asks this field already (or it was answered Not sure there).
      if (asked.has(f) || planned.has(f) || !index.inputs[f]) continue;
      asked.add(f);
      const settled = unsure.has(f) && missing.has(f);
      push("C", {
        key: `rulein-${f}`,
        kind: "rule-input",
        section: "C",
        eyebrow: sectionEyebrow("C"),
        title: index.inputs[f].question,
        context: "",
        why: `${index.inputs[f].why} Batatis compares it with the code’s standard way for ${ruleTopic(r).toLowerCase()}.`,
        ref: f,
        done: !missing.has(f) || settled,
        optional: false,
        settled,
        provision: r.provision.id,
        input: { field: f, spec: index.inputs[f], rule: r.rule_id },
        choices: inputChoices(index.inputs[f]),
      });
    }
  };
  /** Build a follows or departs card; unresolved and inapplicable rules have no result card. */
  const resultItem = (r: ShownRule): DeckItem | null => {
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
      done: seen.has(key),
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
  for (const r of inPlay) {
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
  for (const a of c.candidates) {
    if (behindTriage(a)) continue;
    const r = linked.get(a.id);
    if (r) ruleInputs(r);
    const base = candidateItem(c, a);
    const item = r && (r.state === "departs" || r.state === "follows") ? { ...base, rule: r } : base;
    // An opened keyword lead stays optional: leaving it unanswered does not mean No.
    push("C", keywordCandidate(c, a) && a.answer !== "yes" ? { ...item, optional: true } : item);
  }

  // 5. The alternative-solution case, written by the applicant.
  for (const p of PROCESS_FIELDS) {
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

  // 6. Section D: professional and evidence documents.
  if (sectionDRelevant(c, gaps)) {
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
      context: "Batatis lists what the evidence must address. Your engineer or architect writes it.",
      why: "This part of the form (Section D) names the engineer or architect responsible and lists the proof for each rule your design differs from. Batatis does not write that proof.",
      ref: "section-d",
      done: (seen.has("section-d") && dGaps.length === 0) || pendingForOfficer || needsCheck,
      optional: pendingForOfficer || needsCheck,
      pendingForOfficer,
      needsCheck,
    });
  }
  const items = [...groups.read, ...groups.plan, ...groups.A, ...groups.B, ...groups.questions, ...groups.C, ...groups.D];
  const formPosition = (item: DeckItem) => {
    if (item.kind === "authority") return -1;
    const field = item.plan ? localField(item.plan.field) : item.key.startsWith("field-") ? item.key.slice("field-".length) : "";
    const at = DETAIL_FIELDS.findIndex((d) => d.id === field);
    return at < 0 ? DETAIL_FIELDS.length : at;
  };
  return SECTIONS.flatMap((s) => items.filter((item) => item.section === s.id).sort((a, b) => formPosition(a) - formPosition(b)));
}

/** Keys after `index` that match `pick` take the form's order among their own positions. */
export function rankAhead(queue: string[], index: number, order: string[], pick: (k: string) => boolean): string[] {
  const at = queue.map((k, i) => (i > index && pick(k) && order.includes(k) ? i : -1)).filter((i) => i >= 0);
  if (at.length < 2) return queue;
  const keys = at.map((i) => queue[i]).sort((a, b) => order.indexOf(a) - order.indexOf(b));
  const out = [...queue];
  at.forEach((i, n) => { out[i] = keys[n]; });
  return out.join("|") === queue.join("|") ? queue : out;
}

/** Insert each new key after the last queued key that comes before it in the form. */
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
  { value: "manufacturer", label: "Manufacturer" },
  { value: "contractor", label: "Contractor" },
  { value: "homebuilder", label: "Homebuilder" },
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
  const tracked = items.filter((i) => !i.optional);
  return { done: tracked.filter((i) => i.done && !i.settled).length, total: tracked.length };
}

/** One current question; saved uncertainty is never labelled answered. Skip does not create a fact. */
export function questionProgress(item: DeckItem, currentKey: string | undefined, skipped: readonly string[]): "current" | "done" | "skipped" | "uncertain" | "open" {
  if (item.key === currentKey) return "current";
  if (skipped.includes(item.key) && (!item.done || item.optional)) return "skipped";
  if (item.settled) return "uncertain";
  return item.done ? "done" : "open";
}

export const QUESTION_PROGRESS_LABEL = { current: "Current question", done: "Answered", skipped: "Skipped", uncertain: "Left open", open: "Unanswered" };

/** Only a real Skip click is called skipped; human-pending work is never an applicant omission. */
export function deckCompletion(items: DeckItem[], skipped: readonly string[]): { open: number; skipped: number; message: string } {
  const left = items.filter((i) => !i.done && !i.optional);
  const count = left.filter((i) => skipped.includes(i.key)).length;
  const message = count ? `You skipped ${count} ${count === 1 ? "question" : "questions"}. They stay on your list and on the review.`
    : left.length ? `${left.length} ${left.length === 1 ? "question still needs" : "questions still need"} your answer. Review shows what is missing.`
      : items.some((i) => i.needsCheck) ? "Your answers are in. Check your changed application to see the current requirements."
        : items.some((i) => i.pendingForOfficer) ? "Your answers are in. The officer’s determination is still pending; Review keeps it visible."
          : "Batatis checks what you have and shows anything still missing.";
  return { open: left.length, skipped: count, message };
}

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
export function choicesFor(item: DeckItem): { value: string; label: string }[] {
  if (item.choices) return item.choices;
  if (item.kind === "plan" && item.plan) {
    const input = planInput(item.plan.field);
    return input.kind === "choices" ? input.choices ?? [] : [];
  }
  if (item.kind === "fact") return [{ value: "confirm", label: item.confirmLabels?.confirm ?? "Yes, that’s right" }, { value: "dismiss", label: item.confirmLabels?.dismiss ?? "No, something else" }];
  if (item.kind === "authority") return AUTHORITIES.map((a) => ({ value: a.id, label: a.name }));
  if (item.kind === "candidate") {
    return item.provision
      ? [{ value: "yes", label: "Yes, it differs" }, { value: "no", label: "No, it follows" }]
      : [{ value: "yes", label: "Yes" }, { value: "no", label: "No" }];
  }
  if (item.kind === "detail") {
    if (item.confirmLabels) return [{ value: "confirm", label: item.confirmLabels.confirm }, { value: "dismiss", label: item.confirmLabels.dismiss }];
    const def = DETAIL_FIELDS.find((d) => d.id === item.ref);
    if (def?.options) return Object.entries(def.options).map(([value, label]) => ({ value, label }));
  }
  return [];
}
