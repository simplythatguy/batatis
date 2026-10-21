/**
 * The question deck: one card per thing the applicant still has to answer.
 * Pure and derived. Every card comes from the case and the shared gap list; nothing is typed by hand.
 * Card keys reuse the legacy focus ids (field-*, cand-*, fact-*, q-*), so gap hrefs land on cards.
 */
import { AUTHORITIES } from "../config";
import { DETAIL_FIELDS, DETAIL_IDS, PROCESS_FIELDS, displayValue, factFor, factLabel, valueText } from "../model";
import { isProvision } from "../provisions";
import { quoteKind } from "../rules";
import type { Candidate, Case, Gap } from "../types";
import { calmHref } from "./routes";

export type DeckKind = "fact" | "candidate" | "storeys" | "question" | "authority" | "detail" | "process" | "section-d";

export interface DeckItem {
  key: string;
  kind: DeckKind;
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
}

export interface DeckOptions {
  /** Keys the applicant has continued past in this visit (Section D, optional cards). */
  seen?: ReadonlySet<string>;
  /** Include answered cards too (progress, focus links to an answered card). */
  includeDone?: boolean;
}

const DETAIL_QUESTION: Record<string, string> = {
  owner: "Who is the owner?",
  representative: "Who signs for the applicant?",
  mailingAddress: "What is the mailing address?",
  date: "What date is this request?",
  scope: "Is this for one site, or the whole jurisdiction?",
  permit: "Do you already have a permit number?",
  municipalAddress: "What is the site’s municipal address?",
  legalDescription: "What is the site’s legal description?",
  alternative: "In a sentence or two, what are you proposing instead?",
};

const DETAIL_CONTEXT: Record<string, string> = {
  owner: "The person or company the variance is for.",
  representative: "The person who signs for the applicant.",
  mailingAddress: "Where the authority sends letters about this request.",
  date: "The date you submit this request.",
  scope: "A product used in many places is often jurisdiction-wide. One building is one site.",
  permit: "Only if a permit was already issued. Skip it otherwise.",
  municipalAddress: "The street address of the building.",
  legalDescription: "Lot, block and plan, or ATS.",
  alternative: "Plain words are fine. This goes into Section B as your proposed alternative.",
};

const PROCESS_QUESTION: Record<string, string> = {
  rationale: "Why do you need this alternative, and why should it perform as well?",
  risk: "What could go wrong if it under-performs?",
  mitigation: "What reduces those risks?",
  assumptions: "Under which conditions does your case hold?",
  maintenance: "What has to be maintained or operated after construction?",
  qualifications: "Who takes responsibility, and what is their scope?",
};

export const WRITTEN_BY_YOU = "You write this in your own words. Batatis never writes it for you.";

/** The applicant's first sentence, for quoting back. */
function firstSentence(text: string): string {
  const t = text.trim();
  const s = t.split(/(?<=[.!?])\s+/)[0] ?? t;
  return s.length > 160 ? `${s.slice(0, 157)}…` : s;
}

function candidateItem(c: Case, a: Candidate): DeckItem {
  const done = a.answer !== null;
  if (a.id === "desc-storeys") {
    return {
      key: `cand-${a.id}`,
      kind: "storeys",
      eyebrow: "Code check · Storeys",
      title: "How many storeys is the building?",
      context: "The count decides which part of the code is the benchmark.",
      why: "Buildings up to 3 storeys usually follow Part 9. Larger ones follow Part 3. Not sure keeps it as an open question for the officer.",
      ref: a.id,
      done,
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
      eyebrow: `Code check · ${topic}`,
      title: `Does your design ${a.departure}?`,
      context: "You wrote",
      quote: a.quote.text.trim() || firstSentence(c.description),
      why: "Your answer decides whether this becomes a departure in your application. Not sure keeps it as an open question for the officer.",
      ref: a.id,
      done,
      optional: false,
    };
  }
  const origin =
    a.suggestion === "search"
      ? "You added this rule from the code search."
      : a.suggestion === "identify"
        ? "Suggested from your description. Confirm it before it is used."
        : kind === "ranking"
          ? "Suggested by article ranking."
          : `About ${topic.charAt(0).toLowerCase()}${topic.slice(1)}.`;
  return {
    key: `cand-${a.id}`,
    kind: "candidate",
    eyebrow: `Code check · ${topic}`,
    title: "Is your design different from what this rule asks for?",
    context: origin,
    why: "Yes puts this sentence into Section C as a departure. No removes it from the departures; nothing else changes. Not sure keeps it as an open question for the officer.",
    ref: a.id,
    done,
    optional: false,
    provision: a.provision,
  };
}

/** Questions answered on another card are not asked twice. */
function questionOnOtherCard(c: Case, id: string, cardId?: string): boolean {
  if (id.startsWith("q-prof-") || id.startsWith("q-scope-") || id.startsWith("q-from-") || cardId) return true;
  return id === "q-desc-storeys" && c.candidates.some((a) => a.id === "desc-storeys");
}

/** Map a gap or link key to the card that answers it. */
export function aliasKey(c: Case, key: string): string {
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

export function buildDeck(c: Case, gaps: Gap[], opts: DeckOptions = {}): DeckItem[] {
  const seen = opts.seen ?? new Set<string>();
  // A card a current gap points at is open, whatever the local value says.
  const gapKeys = new Set(gaps.map((g) => gapKey(c, g)).filter((k): k is string => !!k));
  const items: DeckItem[] = [];
  const push = (item: DeckItem) => {
    const open = !item.done || (!item.optional && gapKeys.has(item.key) && item.kind !== "section-d");
    const next = { ...item, done: !open };
    if (opts.includeDone || !next.done) items.push(next);
  };

  // 1. What we read from the applicant's words, waiting for a click.
  for (const f of c.facts) {
    if (f.status !== "unconfirmed") continue;
    const label = factLabel(f.field);
    push({
      key: DETAIL_IDS.has(f.field) ? `field-${f.field}` : `fact-${f.id}`,
      kind: "fact",
      eyebrow: "Check what we read",
      title: `Is “${displayValue(f)}” your ${label.toLowerCase()}?`,
      context: f.source.quote ? `From ${f.source.ref}` : `Read from ${f.source.ref}`,
      quote: f.source.quote && f.source.quote !== displayValue(f) ? f.source.quote : undefined,
      why: "We read this from what you wrote. Nothing is used until you confirm it.",
      ref: f.id,
      done: false,
      optional: false,
    });
  }

  // 2. Code check, in the order the cards were found.
  for (const a of c.candidates) push(candidateItem(c, a));

  // 3. Open questions.
  for (const q of c.questions) {
    if (questionOnOtherCard(c, q.id, q.cardId)) continue;
    push({
      key: `q-${q.id}`,
      kind: "question",
      eyebrow: q.kind === "intake" || q.id.startsWith("q-identify-") ? "From code matching" : "A quick question",
      title: q.text,
      context: "Answer in your own words. A short answer is fine.",
      why: q.why,
      ref: q.id,
      done: Boolean(q.answer?.trim()),
      optional: false,
    });
  }

  // 4. Section A and B details, one per card.
  push({
    key: "authority",
    kind: "authority",
    eyebrow: "Section B · Reviewer",
    title: "Who will review your application?",
    context: `The authority that issues your permit: ${AUTHORITIES.map((a) => a.name).join(" or ")}. Skip it if you don’t know yet.`,
    why: "Each authority has its own submission rules. Batatis never picks one for you.",
    ref: "authority",
    done: Boolean(c.authority),
    optional: false,
  });
  for (const d of DETAIL_FIELDS) {
    const fact = factFor(c, d.id);
    if (fact?.status === "unconfirmed") continue; // asked on its "check what we read" card
    // A choice field counts only with one of its choices (a free-text answer elsewhere can land here).
    const filled = d.options ? valueText(fact) in d.options : Boolean(valueText(fact).trim());
    if (!d.required && filled && !opts.includeDone) continue;
    push({
      key: `field-${d.id}`,
      kind: "detail",
      eyebrow: d.section === "A" ? "Section A · Applicant" : "Section B · Project",
      title: DETAIL_QUESTION[d.id] ?? d.label,
      context: d.options && valueText(fact).trim() && !filled ? "You answered in words. Pick the choice that fits:" : DETAIL_CONTEXT[d.id] ?? d.hint ?? "",
      quote: d.options && valueText(fact).trim() && !filled ? valueText(fact).trim() : undefined,
      why: `Section ${d.section} of the variance form asks for the ${d.label.toLowerCase()}.`,
      ref: d.id,
      done: d.required ? filled : filled || seen.has(`field-${d.id}`),
      optional: !d.required,
    });
  }

  // 5. The alternative-solution case, written by the applicant.
  for (const p of PROCESS_FIELDS) {
    push({
      key: `field-${p.id}`,
      kind: "process",
      eyebrow: `Your case · ${p.label}`,
      title: PROCESS_QUESTION[p.id] ?? p.label,
      context: WRITTEN_BY_YOU,
      why: `The alternative-solution path needs a ${p.label.toLowerCase()} section. It is not skipped, and it has to come from you or your professional.`,
      ref: p.id,
      done: Boolean(c.process[p.id].trim()),
      optional: false,
    });
  }

  // 6. Section D: professional and evidence documents.
  if (sectionDRelevant(c, gaps)) {
    push({
      key: "section-d",
      kind: "section-d",
      eyebrow: "Section D · Supporting documents",
      title: "Who is responsible, and which documents back this up?",
      context: "Batatis lists what the evidence must address. Your engineer or architect writes it.",
      why: "Section D names the registered professional and lists the evidence for each rule you depart from. Batatis does not write professional evidence or judgement.",
      ref: "section-d",
      done: seen.has("section-d") && sectionDGaps(gaps).length === 0,
      optional: false,
    });
  }
  return items;
}

/** Answered out of tracked (non-optional) cards. */
export function deckProgress(items: DeckItem[]): { done: number; total: number } {
  const tracked = items.filter((i) => !i.optional);
  return { done: tracked.filter((i) => i.done).length, total: tracked.length };
}

/** Choices for a card, in keyboard order (1, 2, 3). */
export function choicesFor(item: DeckItem): { value: string; label: string }[] {
  if (item.kind === "fact") return [{ value: "confirm", label: "Yes, that’s right" }, { value: "dismiss", label: "Not right" }];
  if (item.kind === "authority") return AUTHORITIES.map((a) => ({ value: a.id, label: a.name }));
  if (item.kind === "candidate") {
    return item.provision
      ? [{ value: "yes", label: "Yes, it differs" }, { value: "no", label: "No, it follows" }, { value: "not-sure", label: "Not sure" }]
      : [{ value: "yes", label: "Yes" }, { value: "no", label: "No" }, { value: "not-sure", label: "Not sure" }];
  }
  if (item.kind === "detail") {
    const def = DETAIL_FIELDS.find((d) => d.id === item.ref);
    if (def?.options) return Object.entries(def.options).map(([value, label]) => ({ value, label }));
  }
  return [];
}
