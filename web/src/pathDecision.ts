/**
 * The same path as engine/path_decision.py. A firm coded check chooses the package.
 * An unknown fork does not open the alternative package. Identify decisions are not consulted.
 */
import indexJson from "../../engine/data/rules/index.json" with { type: "json" };
import dampers from "../../engine/data/rules/fire-dampers.json" with { type: "json" };
import firewalls from "../../engine/data/rules/firewall-suite-rowhouses.json" with { type: "json" };
import glazed from "../../engine/data/rules/glazed-openings-houses.json" with { type: "json" };
import soffits from "../../engine/data/rules/soffits-houses.json" with { type: "json" };
import openings from "../../engine/data/rules/unprotected-openings.json" with { type: "json" };
import { evaluateAll, type RuleDef, type RuleIndex, type RuleResult } from "./rules/evaluate";
import type { Case, Fact } from "./types";

export type PathName = "acceptable" | "alternative" | "not_applicable" | "unresolved" | "redirect";
export type PathSource = "redirect" | "coded_check" | "recorded" | "wording" | "unresolved";

export interface PathDecision {
  path: PathName;
  ruleId: string | null;
  article: string | null;
  missing: string[];
  firm: boolean;
  source: PathSource;
  asksRuleInputs: boolean;
}

const INDEX = indexJson as unknown as RuleIndex;
const RULES = {
  "glazed-openings-houses": glazed,
  "unprotected-openings": openings,
  "soffits-houses": soffits,
  "firewall-suite-rowhouses": firewalls,
  "fire-dampers": dampers,
} as unknown as Record<string, RuleDef>;

const BUILDING_WIDE = new Set([
  "occupancy", "storeys", "building_area_m2", "dwelling_unit_above_another", "sprinklered",
  "fire_response_over_10_min", "adjacent_rooms_sprinklered", "industrial_hazard",
]);
const KEYWORDS: [string, string[]][] = [
  ["glazed-openings-houses", ["glazed", "glazing", "window"]],
  ["unprotected-openings", ["unprotected opening", "unprotected"]],
  ["soffits-houses", ["soffit", "overhang"]],
  ["firewall-suite-rowhouses", ["firewall", "secondary suite", "row house", "townhouse"]],
  ["fire-dampers", ["fire damper", "damper", "duct"]],
];
const STATE: Partial<Record<RuleResult["state"], PathName>> = {
  follows: "acceptable",
  departs: "alternative",
  not_applicable: "not_applicable",
};

const DEPARTS = new RegExp(
  String.raw`\binstead\s+of\b|\binstead\b|\brather\s+than\b|\bin\s+place\s+of\b|\bomit(?:s|ted|ting)?\b|\bleav(?:e|ing)\s+out\b` +
  String.raw`|\bskip(?:ping)?\b|\bdrop\s+the\b|\bwithout\s+(?:the|a|any|adding|designing|checking|demonstrating|a\s+separate)\b` +
  String.raw`|\bnot\s+(?:meet|meeting|offering|providing|provide|install|use|check)\b|\b(?:doesn'?t|does\s+not|don'?t|do\s+not)\s+meet\b` +
  String.raw`|\b(?:less|fewer|smaller|thinner|shorter|lower|closer|narrower|more|bigger|larger|longer|higher|taller|further|wider)\b` +
  String.raw`[^.!?;\n]{0,100}?\bthan\s+(?:(?:the\s+)?(?:(?:table|code|rules?|bylaw)\s+)?(?:allows?|permits?)|(?:is\s+)?(?:allowed|permitted))\b` +
  String.raw`|\b(?:less|fewer|smaller|thinner|shorter|lower|closer|narrower)\s+than\s+(?:the\s+)?(?:code|required|allowed|permitted|prescribed|table)` +
  String.raw`|\b(?:more|larger|longer|higher|taller|further|wider)\s+than\s+(?:the\s+)?(?:code|allowed|permitted|maximum|limit)` +
  String.raw`|\bexceed(?:s|ing)?\s+the\b|\btoo\s+close\b|\breduc(?:e|ed|ing)\b|\breplace(?:s|d)?\s+(?:the\s+)?(?:required|both)\b` +
  String.raw`|\bno\s+(?:fire\s+dampers?|sheathing|housewrap|separate|installed|rated|other)\b|\bonly\s+one\s+(?:exit|stair)\b` +
  String.raw`|\bsingle\s+(?:exit|stair(?:case)?)\b|\bdon'?t\s+fit\s+the\s+prescriptive\b|\bdo\s+not\s+want\s+to\s+add\b` +
  String.raw`|\bflagged\b|\brejected\b|\bneeds?\s+a\s+variance\b|\b(?:get|apply\s+for)\s+(?:a\s+)?variance\s+(?:for|so)\b` +
  String.raw`|\b(?:smaller|lighter|narrower|lower|shorter|thinner|less|fewer|higher|larger|wider)\s+than\s+(?:normal|usual|what|the\s+(?:minimum|maximum|required|usual))` +
  String.raw`|\b(?:below|short\s+of|under)\s+the\s+(?:\w+\s+)?(?:minimum|required)\b|\babove\s+what\b|\bcall\s+for\s+more\b` +
  String.raw`|\bno\s+(?:encapsulation|standard\s+listing|listing|connection|conformity|intervening|subsurface|Part\s+\d)\b` +
  String.raw`|\breplacing\s+the\s+required\b|\bnot\s+to\s+meet\b|\bagainst\s+the\s+direction\b|\b(?:left|leave|leaving)\s+(?:fully\s+)?exposed\b` +
  String.raw`|\bnot\s+(?:a|one\s+of\s+the)\b[^.]{0,40}\bprescriptive\b|\bon\s+the\s+strength\s+of\b[^.]{0,40}\balone\b` +
  String.raw`|\b\d+\s*%\s+(?:less|lower|fewer|smaller)\b|\b(?:just|only)\s+one\s+(?:\w+\s+)?(?:exit|stair)\b` +
  String.raw`|\bonly\b(?=.{0,40}\b(?:apart|procedure|checks?|data|test|alone|route|values?)\b)|\bpartly\b|\blet\s+the\b`,
  "i",
);
const FOLLOWS = new RegExp(
  String.raw`\b(?:meets?|meeting|follows?|following|according\s+to|per|as\s+(?:set\s+out\s+)?in|built\s+to|matches?|within)\s+` +
  String.raw`(?:the\s+|all\s+the\s+|every\s+)?(?:code|building\s+code|tables?|span\s+tables?|prescriptive|acceptable\s+solutions?|Part\s+9)` +
  String.raw`|\bstandard\s+(?:detail|assembly|construction|design)\b|\bas\s+the\s+code\s+(?:requires|says)\b|\bcode[-\s]conforming\b` +
  String.raw`|\bexactly\s+as\b|\bno\s+(?:changes?|deviations?|departures?)\b|\bnothing\s+(?:unusual|different)\b` +
  String.raw`|\bcode[-\s]minimum\b|\bmeets?\s+the\s+minimum\b|\bas\s+the\s+code\s+(?:describes|requires|says)\b` +
  String.raw`|\bprescriptive\s+(?:path|route|values?)\b|\b(?:straight\s+)?from\s+the\s+code\b|\blisted\s+in\s+the\b.{0,40}\bcode\b` +
  String.raw`|\bstandard\s+(?:loads?|stairs?|height)\b|\bstandard\s+[\w\s-]{0,20}\bdetail\b`,
  "i",
);

function latest(c: Case, ...fields: string[]): Fact | undefined {
  for (let i = c.facts.length - 1; i >= 0; i--) {
    if (fields.includes(c.facts[i].field)) return c.facts[i];
  }
  return undefined;
}

function confirmed(c: Case, ...fields: string[]): Fact["value"] | undefined {
  const fact = latest(c, ...fields);
  if (!fact || fact.status !== "confirmed" || fact.kind === "proposed" || fact.value == null) return undefined;
  return fact.value;
}

function designText(c: Case): string {
  const parts = [c.description.trim()];
  const described = latest(c, "project.description");
  if (typeof described?.value === "string" && described.value && !parts.join("\n").includes(described.value)) parts.push(described.value);
  const alternative = latest(c, "alternative_description", "alternative");
  if (typeof alternative?.value === "string" && alternative.value && !parts.join("\n").includes(alternative.value)) parts.push(alternative.value);
  return parts.filter(Boolean).join("\n").trim();
}

function redirects(c: Case): boolean {
  const fact = latest(c, "scope.redirect");
  if (fact && fact.status === "confirmed" && fact.kind !== "proposed" && fact.value === "overridden") return false;
  if (fact && fact.kind !== "proposed" && fact.value != null && fact.value !== "" && fact.value !== "overridden") return true;
  return c.intake?.record.plan?.scope.status === "redirect";
}

function sentences(text: string): string[] {
  return text.split(/\n|(?<=[.!?])\s+/).map((sentence) => sentence.trim()).filter(Boolean);
}

function cue(pattern: RegExp, text: string): boolean {
  return sentences(text).some((sentence) => !sentence.endsWith("?") && pattern.test(sentence));
}

function wording(text: string): "acceptable" | "alternative" | null {
  const departs = cue(DEPARTS, text);
  const follows = cue(FOLLOWS, text);
  if (departs && !follows) return "alternative";
  if (follows && !departs) return "acceptable";
  return null;
}

function recorded(c: Case): "acceptable" | "alternative" | null {
  const value = confirmed(c, "pathway", "path");
  if (value === "acceptable" || value === "acceptable_solution") return "acceptable";
  if (value === "alternative" || value === "variance") return "alternative";
  const route = confirmed(c, "journey.route");
  if (route === "standard") return "acceptable";
  if (route === "variance" || route === "different") return "alternative";
  return null;
}

function keywordHit(text: string, token: string): boolean {
  if (token.includes(" ")) return text.includes(token);
  return new RegExp(`\\b${token}s?\\b`, "i").test(text);
}

function selectRule(text: string): string | null {
  const titles = Object.values(RULES).filter((rule) => text.includes(rule.title)).map((rule) => rule.id);
  if (titles.length === 1) return titles[0];
  const low = text.toLowerCase();
  const scores = KEYWORDS.map(([ruleId, tokens]) => [tokens.reduce((n, token) => n + (keywordHit(low, token) ? 1 : 0), 0), ruleId] as const)
    .filter(([score]) => score > 0);
  if (!scores.length) return null;
  const best = Math.max(...scores.map(([score]) => score));
  const tied = scores.filter(([score]) => score === best);
  return tied.length === 1 ? tied[0][1] : null;
}

function givenFor(c: Case): Record<string, unknown> {
  const found = new Map<string, Fact>();
  for (const fact of c.facts) {
    const field = fact.field === "building.storeys" ? "storeys" : fact.field;
    if (field in INDEX.inputs) found.set(field, fact);
  }
  const given: Record<string, unknown> = {};
  for (const [field, fact] of found) {
    if (fact.kind === "proposed" || fact.value == null) continue;
    given[field] = fact.value;
  }
  return given;
}

function firm(result: RuleResult): boolean {
  return result.state in STATE && result.assumptions.length === 0;
}

function needs(result: RuleResult): string[] {
  const missing = result.missing.map((item) => item.field);
  if (result.assumptions.length) {
    const known = new Set(result.inputs.filter((item) => item.value != null).map((item) => item.field));
    for (const field of RULES[result.rule_id]?.inputs ?? []) {
      if (!known.has(field) && !missing.includes(field)) missing.push(field);
    }
  }
  return missing;
}

function inPlay(result: RuleResult): boolean {
  return result.inputs.some((item) => !BUILDING_WIDE.has(item.field) && item.value != null);
}

function fromCheck(result: RuleResult): PathDecision {
  return {
    path: STATE[result.state]!,
    ruleId: result.rule_id,
    article: result.provision.id,
    missing: [],
    firm: true,
    source: "coded_check",
    asksRuleInputs: false,
  };
}

function fallback(c: Case, text: string, ruleId: string | null, missing: string[]): PathDecision {
  const chosen = recorded(c) ?? wording(text);
  if (chosen) {
    return {
      path: chosen, ruleId, article: null, missing, firm: false,
      source: recorded(c) ? "recorded" : "wording", asksRuleInputs: missing.length > 0,
    };
  }
  return {
    path: "unresolved", ruleId, article: null, missing, firm: false, source: "unresolved",
    asksRuleInputs: missing.length > 0,
  };
}

/** Inputs of the one rule the description named, or null when no single rule was named. */
export function namedRuleInputs(ruleId: string | null): readonly string[] | null {
  if (!ruleId || !RULES[ruleId]) return null;
  return RULES[ruleId].inputs;
}

/** Package path for this case. Acceptable and alternative open a package; the others do not. */
export function decidePath(c: Case): PathDecision {
  const text = designText(c);
  if (redirects(c)) {
    return { path: "redirect", ruleId: null, article: null, missing: [], firm: false, source: "redirect", asksRuleInputs: false };
  }
  const results = evaluateAll(RULES, INDEX, givenFor(c));
  const byId = new Map(results.map((result) => [result.rule_id, result]));
  const named = selectRule(text);
  if (named) {
    const result = byId.get(named);
    if (result && firm(result)) return fromCheck(result);
    return fallback(c, text, named, result ? needs(result) : []);
  }
  const playing = results.filter(inPlay);
  const decided = playing.filter(firm);
  const departed = decided.find((result) => result.state === "departs");
  if (departed) return fromCheck(departed);
  if (playing.length && decided.length === playing.length && decided.every((result) => result.state === "follows")) return fromCheck(decided[0]);
  if (playing.length && decided.length === playing.length && decided.every((result) => result.state === "not_applicable")) return fromCheck(decided[0]);
  const missing = [...new Set(playing.filter((result) => !firm(result)).flatMap(needs))];
  return fallback(c, text, null, missing);
}

/** Short card copy. It names the missing fact and does not say the design complies or is safe. */
export function pathStopCopy(decision: PathDecision): { title: string; context: string } {
  if (decision.path === "not_applicable") {
    return { title: "This rule doesn’t apply", context: "No variance package is opened from this rule." };
  }
  const field = decision.missing[0]?.replaceAll("_", " ");
  return {
    title: "Path not decided",
    context: field
      ? `Still needed to decide the path: ${field}.`
      : "Whether the design departs from an acceptable solution is still missing.",
  };
}
