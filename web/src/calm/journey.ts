/** The applicant's order and responsibility, independent of the form's A–D layout. */
import { latestLocalFacts, localField } from "../intakeFields";
import type { Action } from "../model";
import type { Case } from "../types";
import type { DeckItem } from "./deck";
import { LEGAL_PART_FIELDS, legalFromParts, readCopy, readGroups, sourceLine, type ReadCopy } from "../intakeView";
import type { Fact } from "../types";

export type Stage = "understand" | "route" | "project" | "rules" | "case" | "proof" | "paperwork";
export type Answerer = "you" | "designer" | "office" | "batatis";
export const STAGES: { stage: Stage; label: string; hue: string }[] = [
  { stage: "understand", label: "Understand", hue: "blue" },
  { stage: "route", label: "Route", hue: "teal" },
  { stage: "project", label: "Project", hue: "teal" },
  { stage: "rules", label: "Rules", hue: "violet" },
  { stage: "case", label: "Case", hue: "amber" },
  { stage: "proof", label: "Proof", hue: "amber" },
  { stage: "paperwork", label: "Paperwork", hue: "blue" },
];
export const ANSWERERS: Answerer[] = ["you", "designer", "office", "batatis"];

const ANSWERER: Readonly<Record<string, Answerer>> = {
  part4_design: "designer",
  "assembly.description": "designer",
  industrial_hazard: "designer",
  fire_resistance_rating: "designer",
  fire_resistance_rating_minutes: "designer",
  duct_penetrates_rated_separation: "designer",
  max_suite_houses_between_firewalls: "designer",
  appendix_d_conforms: "designer",
  riser_negative_pressure: "designer",
  duct_melting_point_c: "designer",
  "professional.part4_design": "designer",
  "professional.professional_judgement_required": "designer",
  "professional.prescriptive_route_confirmed": "designer",
  "professional.special_safety_concerns": "designer",
  "professional.preserved_wood_foundation_part4": "designer",
  professional_judgement_required: "designer",
  professional_scope_resolved: "designer",
  "professional.professional_scope_resolved": "designer",
  fire_response_over_10_min: "office",
  "professional.ahj_requires_professional": "office",
};
export const PAPERWORK_FIELDS = new Set(["owner", "representative", "mailingAddress", "municipalAddress", "legalDescription", "permit", "date", "scope", "applicant_role"]);
const PROJECT = new Set(["storeys", "building_area_m2", "floor_area_m2", "occupancy", "sprinklered", "dwelling_units", "limiting_distance_m", "faces_public_way", "part4_design", "assembly.description"]);
type Positioned = Pick<DeckItem, "kind" | "ref" | "section"> & Partial<Pick<DeckItem, "plan" | "input" | "read" | "assumed" | "field">>;
const fieldOf = (item: Positioned) => localField(item.plan?.field ?? item.input?.field ?? item.field ?? item.ref);

export function stageOf(item: Positioned): Stage {
  const field = fieldOf(item);
  if (item.kind === "understood" || item.kind === "fact" || item.kind === "file" || item.kind === "reading" || item.plan?.kind === "conflict") return "understand";
  if (item.kind === "route" || item.kind === "route-detail" || item.kind === "product-scope" || item.kind === "product-notice" || item.kind === "scope" || field === "product_scope") return "route";
  if (item.kind === "paperwork" || item.kind === "role" || item.kind === "authority" || PAPERWORK_FIELDS.has(field)) return "paperwork";
  if (item.kind === "process" || field === "alternative") return "case";
  if (item.kind === "section-d" || field.startsWith("professional.") || field.startsWith("evidence.")) return "proof";
  if (item.kind === "storeys" || (item.kind === "plan" && item.plan?.priority !== "administrative") || PROJECT.has(field)) return "project";
  if (item.section === "C") return "rules";
  return item.section === "A" ? "paperwork" : "project";
}

export function answererOf(item: Positioned): Answerer {
  const field = fieldOf(item);
  if (ANSWERER[field] === "office") return "office";
  if (item.assumed || item.kind === "understood" || item.kind === "reading" || item.kind === "code-run") return "batatis";
  // Reading a designer's determination is a confirmation; only a missing determination is routed.
  if (item.kind === "fact") return "you";
  return ANSWERER[field] ?? "you";
}

const PAPERWORK_ORDER = ["owner", "applicant_role", "representative", "mailingAddress", "municipalAddress", "legalDescription", "permit", "date", "scope", "authority"];
export function orderJourney(items: DeckItem[]): DeckItem[] {
  const position = (item: DeckItem) => {
    if (item.stage !== "paperwork") return 0;
    const at = PAPERWORK_ORDER.indexOf(fieldOf(item));
    return at < 0 ? PAPERWORK_ORDER.length : at;
  };
  return [...items].sort((a, b) => STAGES.findIndex((s) => s.stage === a.stage) - STAGES.findIndex((s) => s.stage === b.stage) || position(a) - position(b));
}

export type JourneyAnswerValue = "not_sure" | "designer" | "later" | "acknowledged";
export interface JourneyAnswer {
  key: string;
  field: string;
  question: string;
  stage: Stage;
  answerer: Answerer;
  value: JourneyAnswerValue;
  required: boolean;
}
export const JOURNEY_ANSWER_PREFIX = "journey.answer.";
export const journeyAnswerField = (key: string) => `${JOURNEY_ANSWER_PREFIX}${encodeURIComponent(key)}`;

/** Uses the case's ordinary fact action and save queue; there is no separate persistence store. */
export function journeyAnswerAction(item: DeckItem, value: JourneyAnswerValue): Action {
  const answer: JourneyAnswer = { key: item.key, field: fieldOf(item), question: item.title, stage: item.stage, answerer: value === "designer" ? "designer" : item.answerer, value, required: !item.optional };
  return { type: "setDetail", field: journeyAnswerField(item.key), value: JSON.stringify(answer), section: item.section };
}
export function clearJourneyAnswerAction(item: DeckItem): Action {
  return { type: "setDetail", field: journeyAnswerField(item.key), value: "", section: item.section };
}

export function journeyAnswers(c: Case): Map<string, JourneyAnswer> {
  const answers = new Map<string, JourneyAnswer>();
  for (const fact of latestLocalFacts(c.facts)) {
    if (!fact.field.startsWith(JOURNEY_ANSWER_PREFIX) || typeof fact.value !== "string" || fact.status !== "confirmed" || fact.kind === "proposed" || fact.kind === "computed") continue;
    try {
      const a: unknown = JSON.parse(fact.value);
      if (!a || typeof a !== "object" || !("key" in a) || typeof a.key !== "string" || !("field" in a) || typeof a.field !== "string" || !("question" in a) || typeof a.question !== "string" || !("required" in a) || typeof a.required !== "boolean") continue;
      if (!("value" in a) || (a.value !== "not_sure" && a.value !== "designer" && a.value !== "later" && a.value !== "acknowledged")) continue;
      if (!("stage" in a) || !STAGES.some((s) => s.stage === a.stage) || !("answerer" in a) || !ANSWERERS.some((who) => who === a.answerer)) continue;
      const stage = STAGES.find((s) => s.stage === a.stage)!.stage;
      const answerer = ANSWERERS.find((who) => who === a.answerer)!;
      answers.set(a.key, { key: a.key, field: a.field, question: a.question, required: a.required, value: a.value, stage, answerer });
    } catch { /* An invalid saved annotation cannot suppress a real question. */ }
  }
  return answers;
}

export function routeChoice(c: Case): "standard" | "variance" | "different" | null {
  const fact = latestLocalFacts(c.facts).find((f) => f.field === "journey.route");
  const value = fact?.status === "confirmed" && fact.kind !== "proposed" && fact.kind !== "computed" ? fact.value : null;
  return value === "standard" || value === "variance" || value === "different" ? value : null;
}
export function productScope(c: Case): "site" | "product_acceptance" | null {
  const fact = latestLocalFacts(c.facts).find((f) => f.field === "product_scope");
  const value = fact?.status === "confirmed" && fact.kind !== "proposed" && fact.kind !== "computed" ? fact.value : null;
  return value === "site" || value === "product_acceptance" ? value : null;
}

export interface UnderstandingRow {
  key: string;
  field: string;
  ref: string;
  value: Fact["value"];
  ids: string[];
  copy: ReadCopy;
  sources: string[];
  assumed: boolean;
  separate: boolean;
  done: boolean;
  deferred?: JourneyAnswerValue;
}

/** Confirmation changes no part of this key; a fresh reading or changed rows does. */
export function understandingAnswerKey(c: Case, rows: UnderstandingRow[]): string {
  const signature = JSON.stringify([c.intake?.record.ran_at ?? null, rows.map((r) => [r.field, [...r.ids].sort()])]);
  // A bounded reading identity; personal values never become fact-field names.
  let hash = 0xcbf29ce484222325n;
  for (let i = 0; i < signature.length; i++) hash = BigInt.asUintN(64, (hash ^ BigInt(signature.charCodeAt(i))) * 0x100000001b3n);
  return `understood:${hash.toString(16)}`;
}

export const cleanReadValue = (value: string): string => value.trim().replace(/[.,;:!?]+$/, "").trimEnd();

function pictureFact(c: Case, fact: Fact): boolean {
  if (fact.kind !== "proposed" || fact.source.type !== "file") return false;
  const file = c.files.find((f) => f.engineId === fact.source.ref || f.id === fact.source.ref);
  const report = c.intake?.record.files.find((f) => f.file_id === fact.source.ref);
  // W1's vision pointers and image-only PDF pages stay individual confirmations.
  const pointer = c.intake?.record.pointers.find((p) => p.fact_id === fact.id);
  return /\.(?:jpe?g|png|webp)$/i.test(file?.name ?? report?.name ?? "") || (pointer && "method" in pointer && String(pointer.method) === "vision") || Boolean(fact.source.page && report?.pages_not_read.includes(fact.source.page)) || /vision|image.only|picture|drawing/i.test(fact.source.ref);
}

/** One row per value, retaining every source and every fact ID the confirmation must cover. */
export function understandingRows(c: Case, detailIds: ReadonlySet<string>): UnderstandingRow[] {
  const rows: UnderstandingRow[] = [];
  const answers = journeyAnswers(c);
  const latestByField = new Map(latestLocalFacts(c.facts).map((f) => [f.field, f]));
  for (const group of readGroups(c, detailIds, true)) {
    if (group.fact.field.startsWith("journey.")) continue;
    const field = localField(group.fact.field);
    const latest = latestByField.get(field);
    if (group.done && latest?.value == null && latest && !answers.has(group.key)) continue;
    const corrected = group.done && latest?.status === "confirmed" && latest.value != null && String(latest.value) !== String(group.fact.value);
    const shown = corrected ? latest : { ...group.fact, field };
    const assumed = shown.kind === "computed" || shown.kind === "proposed" || c.intake?.record.pointers.some((p) => p.fact_id === shown.id && p.verified === false) === true;
    const separate = pictureFact(c, group.fact) || Boolean(c.intake?.record.conflicts.some((conflict) => localField(conflict.field) === field));
    const read = readCopy(c, { ...group, fact: shown });
    const copy = { ...read, value: cleanReadValue(read.value), confirm: cleanReadValue(read.confirm) };
    const sources = corrected ? ["Your answer"] : group.ids.map((id) => c.facts.find((f) => f.id === id) ?? c.intake?.facts.find((f) => f.id === id)).filter((f): f is Fact => Boolean(f)).map((f) => sourceLine(c, f));
    const twin = !separate && rows.find((row) => !row.separate && row.field === field && row.copy.value.trim().toLowerCase() === copy.value.trim().toLowerCase());
    if (twin) {
      twin.ids = [...new Set([...twin.ids, ...group.ids])];
      twin.sources = [...new Set([...twin.sources, ...sources])];
      twin.done = twin.done && group.done;
    } else rows.push({ key: group.key, field, value: shown.value, ref: group.fact.id, ids: group.ids, copy, sources: [...new Set(sources)], assumed, separate, done: group.done || answers.has(group.key), deferred: answers.get(group.key)?.value });
  }
  return joinLegalRows(rows);
}

/** Lot, block and plan are one thing to the applicant: one "Legal description" row. */
function joinLegalRows(rows: UnderstandingRow[]): UnderstandingRow[] {
  const parts = rows.filter((r) => !r.separate && (LEGAL_PART_FIELDS as readonly string[]).includes(r.field));
  if (parts.length < 2) return rows;
  const value = legalFromParts(Object.fromEntries(parts.map((r) => [r.field, r.value])));
  const first = parts[0];
  const joined: UnderstandingRow = {
    ...first, field: "legalDescription", value, ids: [...new Set(parts.flatMap((r) => r.ids))],
    copy: { ...first.copy, title: "Legal description", value }, sources: [...new Set(parts.flatMap((r) => r.sources))],
    assumed: parts.some((r) => r.assumed), done: parts.every((r) => r.done), deferred: parts.find((r) => r.deferred)?.deferred,
  };
  return rows.flatMap((r) => (r === first ? [joined] : parts.includes(r) ? [] : [r]));
}

export function itemOpen(item: DeckItem): boolean {
  return !item.done || Boolean(item.settled) || Object.values(item.counts ?? {}).some((count) => count.open > 0);
}
const emptyCounts = (): Record<Answerer, number> => ({ you: 0, designer: 0, office: 0, batatis: 0 });

export function journeyProgress(items: DeckItem[]): { stages: { stage: Stage; open: number; done: number; total: number; byAnswerer: Record<Answerer, number> }[]; open: Record<Answerer, number>; yourPartDone: boolean } {
  const open = emptyCounts();
  const stages = STAGES.map(({ stage }) => {
    const byAnswerer = emptyCounts();
    let done = 0;
    for (const item of items.filter((i) => i.stage === stage && (!i.optional || i.counts))) {
      const counts = item.counts ?? { [item.answerer]: { open: itemOpen(item) ? 1 : 0, done: itemOpen(item) ? 0 : 1 } };
      for (const who of ANSWERERS) {
        const count = counts[who];
        if (!count) continue;
        byAnswerer[who] += count.open;
        open[who] += count.open;
        done += count.done;
      }
    }
    const left = Object.values(byAnswerer).reduce((n, count) => n + count, 0);
    return { stage, open: left, done, total: left + done, byAnswerer };
  });
  return { stages, open, yourPartDone: open.you + open.batatis === 0 };
}
