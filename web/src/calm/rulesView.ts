/**
 * Coded rules in the deck (docs/api/rules.md). Pure: case facts in, plain-language cards out.
 *
 * The browser evaluator (rules/evaluate.ts) gives the live result as the applicant answers; the
 * engine's `GET /cases/{id}/rules` is the state of record and wins whenever it read the same inputs.
 * A rule check is a departure flag against one acceptable solution. Nothing here says a design
 * complies, is safe, approved or adequate, and every rule is shown as not yet reviewed by an expert.
 */
import type { CaseRules } from "../api/types.gen";
import { evaluateAll, fmt, type InputSpec, type RuleDef, type RuleIndex, type RuleResult, type Value } from "../rules/evaluate";
import type { Candidate, Case, Fact } from "../types";

export interface RuleData {
  index: RuleIndex;
  rules: Record<string, RuleDef>;
}

/** Where a number on a rule card came from, in plain words. */
export interface InputOrigin {
  text: string;
  confirmed: boolean;
}

export interface ShownRule extends RuleResult {
  /** Inputs read from values the applicant has not confirmed yet. */
  unconfirmed_inputs: string[];
  origins: Record<string, InputOrigin>;
  /** True when the engine's stored result (same inputs) is what is shown. */
  stored: boolean;
}

export const RULE_REF = "rules:";
export const NOT_REVIEWED = "Checked by Batatis, not yet reviewed by an expert.";

export const articleOf = (id: string) => id.match(/^\d+\.\d+\.\d+\.\d+\./)?.[0] ?? id;

/** The latest usable fact per rule input, read like the engine's `case_inputs`: never a proposed fact. */
export function ruleFacts(c: Case, index: RuleIndex): Map<string, Fact> {
  const found = new Map<string, Fact>();
  for (let i = c.facts.length - 1; i >= 0; i--) {
    const f = c.facts[i];
    if (!(f.field in index.inputs) || found.has(f.field) || f.kind === "proposed" || f.value === null || f.value === undefined) continue;
    found.set(f.field, f);
  }
  return found;
}

function originOf(f: Fact): InputOrigin {
  const confirmed = f.status === "confirmed";
  const ref = f.source.ref ?? "";
  if (ref.startsWith(RULE_REF) || ref === "intake answer" || f.source.type === "user_click") return { text: "your answer", confirmed };
  if (ref.startsWith("intake")) return { text: confirmed ? "from your description, confirmed" : "from your description, not confirmed yet", confirmed };
  return { text: confirmed ? "your answer" : "not confirmed yet", confirmed };
}

const sameInputs = (a: { field: string; value: unknown }[], b: { field: string; value: unknown }[]) =>
  JSON.stringify(a.map((x) => [x.field, x.value])) === JSON.stringify(b.map((x) => [x.field, x.value]));

/**
 * Every rule for this case: live from the browser evaluator, replaced by the engine's stored result
 * whenever the engine read exactly the same inputs (the state of record).
 */
export function caseRuleResults(c: Case, data: RuleData, stored?: CaseRules | null): ShownRule[] {
  const facts = ruleFacts(c, data.index);
  const given: Record<string, unknown> = {};
  for (const [field, f] of facts) given[field] = f.value;
  const live = evaluateAll(data.rules, data.index, given);
  return live.map((r) => {
    const origins: Record<string, InputOrigin> = {};
    for (const i of r.inputs) {
      const f = facts.get(i.field);
      if (f && i.value !== null) origins[i.field] = originOf(f);
    }
    const unconfirmed = r.inputs.filter((i) => i.value !== null && origins[i.field] && !origins[i.field].confirmed).map((i) => i.field);
    const api = stored?.results.find((x) => x.rule_id === r.rule_id);
    if (api && sameInputs(api.inputs, r.inputs)) {
      return { ...(api as unknown as RuleResult), unconfirmed_inputs: api.unconfirmed_inputs, origins, stored: true };
    }
    return { ...r, unconfirmed_inputs: unconfirmed, origins, stored: false };
  });
}

/**
 * Inputs most rules share (occupancy, storeys, building area) say what the building is, not that a
 * rule is in play. Derived from the data: an input used by most rules.
 */
export function sharedInputs(data: RuleData): Set<string> {
  const ids = data.index.rules;
  const counts = new Map<string, number>();
  for (const id of ids) for (const f of data.rules[id]?.inputs ?? []) counts.set(f, (counts.get(f) ?? 0) + 1);
  return new Set([...counts].filter(([, n]) => n > ids.length / 2).map(([f]) => f));
}

/** The code-check card for this rule's article, if the case has one the applicant has not ruled out. */
export function linkedCandidate(c: Case, rule: { article: string }): Candidate | undefined {
  return c.candidates.find((a) => articleOf(a.provision) === rule.article && a.answer !== "no");
}

/**
 * A rule joins the deck when the case points at it: a code-check card for its article, or one of the
 * rule's own inputs (a number only this kind of rule uses, such as the limiting distance) is known.
 */
export function ruleInPlay(c: Case, data: RuleData, r: ShownRule, shared = sharedInputs(data)): boolean {
  if (linkedCandidate(c, r)) return true;
  const facts = ruleFacts(c, data.index);
  return (data.rules[r.rule_id]?.inputs ?? []).some((f) => !shared.has(f) && facts.has(f));
}

/** A value with its unit, the way the engine writes it ("1.2 m", "4 m²", "Yes"). */
export function valueWithUnit(value: Value | null, unit: string | null | undefined, spec?: InputSpec): string {
  if (value === null) return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "string") return spec?.choices?.find((c) => c.value === value)?.label ?? value;
  const n = fmt(value);
  return unit ? `${n} ${unit}` : n;
}

const num = (r: RuleResult, name: string) => {
  const v = r.computed.find((x) => x.name === name)?.value ?? r.inputs.find((x) => x.field === name)?.value ?? null;
  return typeof v === "number" ? v : null;
};
/** " at 1.2 m" (the distance the rule used), or "" when it is not known. */
const at = (r: RuleResult) => {
  const v = num(r, "limiting_distance_used_m") ?? num(r, "limiting_distance_m");
  return v === null ? "" : ` at ${fmt(v)} m`;
};

/** Plain wording for each rule's result: what it means, without the code's terms. */
const PLAIN: Record<string, { topic: string; departs: (r: RuleResult) => string; follows: (r: RuleResult) => string; limit?: { name: string; label: string } }> = {
  "glazed-openings-houses": {
    topic: "Window area in a wall near the property line",
    departs: (r) => r.outcome_id === "departs_no_openings"
      ? `${at(r).replace(" at", "At") || "At this distance"} from the property line, the code’s table allows no windows in this wall.`
      : `Your window area is more than the code’s table allows${at(r)}.`,
    follows: (r) => r.outcome_id === "follows_own_garage"
      ? "This wall faces your own detached garage, so the window limits don’t apply."
      : `Your window area is within what the code allows${at(r)}.`,
    limit: { name: "sentence_1_limit_m2", label: "Most window area the code’s table allows" },
  },
  "unprotected-openings": {
    topic: "Openings in a wall near the property line",
    departs: (r) => r.outcome_id === "departs_no_openings"
      ? `${at(r).replace(" at", "At") || "At this distance"} from the property line, the code’s table allows no unprotected openings in this wall.`
      : `Your opening area is more than the code’s table allows${at(r)}.`,
    follows: (r) => `Your opening area is within what the code allows${at(r)}.`,
    limit: { name: "sentence_1_limit_m2", label: "Most opening area the code’s table allows" },
  },
  "soffits-houses": {
    topic: "Roof overhangs near the property line",
    departs: (r) => r.outcome_id === "departs_close_face"
      ? "The code’s standard way allows no roof overhang above a wall this close to the property line."
      : "Your roof overhang comes closer to the property line than the code’s 0.45 m.",
    follows: () => "Your roof overhang stays far enough from the property line.",
  },
  "firewall-suite-rowhouses": {
    topic: "Firewalls between row houses with suites",
    departs: () => "More than two neighbouring houses with a secondary suite share one section without a firewall between them.",
    follows: () => "No more than two neighbouring houses with a suite sit between firewalls.",
  },
  "fire-dampers": {
    topic: "Ducts through a fire separation",
    departs: () => "A duct passes through a fire separation without a fire damper.",
    follows: () => "The duct through the fire separation follows the code’s standard way.",
  },
};

export function ruleTopic(r: { rule_id: string; title: string }): string {
  return PLAIN[r.rule_id]?.topic ?? r.title;
}

/** The headline and the one line under it. Plain words first; the official term second. */
export function plainResult(r: RuleResult): { title: string; line: string } {
  const p = PLAIN[r.rule_id];
  if (r.state === "departs") {
    return {
      title: p?.departs(r) ?? `Your design differs from the code’s standard way for ${r.title.toLowerCase()}.`,
      line: "That is a departure from the code’s standard way (the acceptable solution): you’ll need an alternative solution.",
    };
  }
  if (r.state === "follows") {
    return {
      title: p?.follows(r) ?? `Your numbers follow the code’s standard way for ${r.title.toLowerCase()}.`,
      line: "That follows the code’s standard way (the acceptable solution) for this rule. Nothing to add for it.",
    };
  }
  if (r.state === "not_applicable") return { title: "This rule doesn’t apply to your project.", line: r.message };
  return { title: `Batatis needs a few numbers to compare your design with ${r.provision.id}.`, line: "Answer the questions and the result appears here." };
}

/** The numbers a result used, each with where it came from, plus the limit it was compared with. */
export function numbersUsed(r: ShownRule, index: RuleIndex): { label: string; value: string; origin: string; muted?: boolean }[] {
  const rows: { label: string; value: string; origin: string; muted?: boolean }[] = r.inputs
    .filter((i) => i.value !== null)
    .map((i) => ({ label: i.label, value: valueWithUnit(i.value, i.unit, index.inputs[i.field]), origin: r.origins[i.field]?.text ?? "" }));
  const limit = PLAIN[r.rule_id]?.limit;
  const v = limit ? r.computed.find((x) => x.name === limit.name) : undefined;
  if (limit && v && v.value !== null) rows.push({ label: limit.label, value: valueWithUnit(v.value, v.unit), origin: `${r.provision.id}`, muted: true });
  const used = r.computed.find((x) => x.name === "limiting_distance_used_m");
  const given = r.inputs.find((x) => x.field === "limiting_distance_m")?.value;
  if (used && used.value !== null && given !== undefined && given !== null && used.value !== given) {
    rows.push({ label: "Distance used (halved for a slow fire response)", value: valueWithUnit(used.value, used.unit), origin: "the code’s rule", muted: true });
  }
  return rows;
}

/** The next step for a departure, in plain words (the engine's full sentence sits behind Show the code). */
export const DEPARTS_NEXT = "To build it this way, you prepare an alternative solution that performs at least as well, and ask for a variance. A safety codes officer decides.";

/** A rule input card's answer choices (yes/no, a list, or a number), always with Not sure. */
export function inputChoices(spec: InputSpec): { value: string; label: string }[] {
  if (spec.type === "bool") return [{ value: "true", label: "Yes" }, { value: "false", label: "No" }, { value: NOT_SURE_RULE, label: "Not sure" }];
  if (spec.type === "enum") return [...(spec.choices ?? []), { value: NOT_SURE_RULE, label: "Not sure" }];
  return [];
}

export const NOT_SURE_RULE = "not-sure";

/** A typed number for this input, or an error in plain words. */
export function readNumber(spec: InputSpec, text: string): { value: number } | { error: string } {
  const t = text.trim().replace(",", ".");
  if (!t) return { error: "Type a number." };
  const n = Number(t);
  if (!Number.isFinite(n)) return { error: "Type a number, for example 2.5." };
  if (spec.type === "int" && !Number.isInteger(n)) return { error: "Type a whole number." };
  if (spec.min !== undefined && n < spec.min) return { error: `The smallest value is ${fmt(spec.min)}.` };
  if (spec.max !== undefined && n > spec.max) return { error: `The largest value is ${fmt(spec.max)}.` };
  return { value: n };
}

/** A choice's stored value: booleans are JSON true/false, everything else the choice value. */
export function choiceValue(spec: InputSpec, value: string): boolean | string {
  return spec.type === "bool" ? value === "true" : value;
}
