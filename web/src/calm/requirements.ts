/**
 * The applicant's review of the requirement ledger (`screen: "requirements"`).
 *
 * Identification returns a source-backed ledger, not a short ranking: `committed` and `choices` are
 * empty and every candidate lives in `requirements`. This module turns that ledger into a bounded,
 * ordered batch of applicability questions. It never decides applicability, a departure, or
 * compliance, and it never hides a candidate from the ledger: unanswered rows keep their order, and
 * the rest stay in the code library.
 */
import type { IdentifyResult, RequirementRecord } from "../api/types.gen";

/** How many of the closest rules one pass asks about. Review is optional and advances in batches. */
export const REVIEW_BATCH = 6;

/** Applicability in the applicant's words: does this rule govern the proposed project? */
export type RequirementAnswer = "applies" | "does-not-apply" | "not-sure";

export interface RequirementQueue {
  /** The closest undecided Division B requirements, at most `limit`. */
  batch: RequirementRecord[];
  /** Division B requirements the applicant already answered; their cards stay so an answer can change. */
  answered: RequirementRecord[];
  /** Division B requirements still waiting for an applicant decision. */
  reviewable: number;
  /** Every Division B requirement in the project's Part (see `inScope`) the ledger discovered, decided or not. */
  found: number;
}

const decided = (record: RequirementRecord) => Boolean(record.confirmed_at) || record.human_confirmed;

/** A rule can be asked about only when its source is verified and it has a real Division B article. */
export function askable(record: RequirementRecord): boolean {
  return record.division === "B" && record.source_status === "verified"
    && Boolean(record.provision_id) && !decided(record);
}

/**
 * The building Part the project's own facts point to, from the engine's Part 9 entry check (Division A
 * 1.3.3.3.(1)): 9 when the confirmed height and area are within Part 9's limits, 3 when either is over
 * them, null while either is unknown. Occupancy stays with the applicant; this only narrows what is asked.
 */
export function projectPart(result: IdentifyResult | null | undefined): 3 | 9 | null {
  const nine = result?.scope_assessments?.find((assessment) => assessment.part === 9);
  if (!nine) return null;
  const size = nine.conditions.filter((condition) => condition.field === "storeys" || condition.field === "building_area_m2");
  if (nine.status === "boundary_not_met" || size.some((condition) => condition.status === "not_met")) return 3;
  return size.length === 2 && size.every((condition) => condition.status === "met") ? 9 : null;
}

/** A row found by more than a word match: named in the description, chosen by a person, kept from before, or picked by the ranker. */
const STRONG = new Set<RequirementRecord["discoveries"][number]["kind"]>(["explicit", "human", "previous", "model_search"]);

/**
 * Whether a ledger row belongs in the questions for this project. A Part 9 house is not asked about
 * Part 3, 4, 6 or 7 rules (water slides, chlorine rooms, seismic isolation) on a word match alone, and
 * a Part 3 building is not asked about Part 9. An answered row or a strong match always stays.
 */
export function inScope(record: RequirementRecord, part: 3 | 9 | null): boolean {
  if (part === null || decided(record)) return true;
  if (Number(record.provision_id?.split(".")[0]) === part) return true;
  return record.discoveries.some((discovery) => STRONG.has(discovery.kind));
}

/** Ledger rows are already ordered by the engine's deterministic rank; the batch keeps that order. */
export function requirementQueue(result: IdentifyResult | null | undefined, limit: number = REVIEW_BATCH): RequirementQueue {
  const part = projectPart(result);
  const rows = (result?.requirements ?? []).filter((record) => record.division === "B" && record.source_status === "verified" && inScope(record, part));
  const waiting = rows.filter(askable);
  const answered = rows.filter((record) => Boolean(record.provision_id) && decided(record));
  return { batch: waiting.slice(0, limit), answered, reviewable: waiting.length, found: rows.length };
}

/** The stored answer on a ledger row, or null while it still waits for the applicant. */
export function requirementAnswer(record: RequirementRecord): RequirementAnswer | null {
  if (!decided(record)) return null;
  if (record.disposition === "exclude") return "does-not-apply";
  if (record.disposition === "include") return "applies";
  return "not-sure";
}

/** A condition the ledger could not resolve keeps the rule conditional, never silently applicable. */
function roleOf(record: RequirementRecord): "supporting" | "conditional" {
  return record.conditions.some((condition) => condition.status !== "provided") ? "conditional" : "supporting";
}

/** The acknowledgement stored for "it applies": the decision itself, not a technical finding. */
export const APPLIES_REASON = "The applicant confirmed this rule applies to this project.";

export interface RequirementDecision {
  disposition: "include" | "exclude" | "review";
  role: "varied" | "supporting" | "admin" | "conditional" | "unresolved";
  reason: string;
}

/**
 * The request for one answer. Applicability and departure stay separate: "applies" records the
 * scope decision only, and the departure is asked afterwards on its own card.
 */
export function requirementDecision(record: RequirementRecord, answer: RequirementAnswer, reason = ""): RequirementDecision {
  if (answer === "applies") return { disposition: "include", role: roleOf(record), reason: APPLIES_REASON };
  const typed = reason.trim();
  if (!typed) throw new Error("A reason is required for this answer.");
  return answer === "does-not-apply"
    ? { disposition: "exclude", role: "unresolved", reason: typed }
    : { disposition: "review", role: "unresolved", reason: typed };
}

/** The plain name for a rule card: its article title, or the article number when the title is empty. */
export function requirementTopic(record: RequirementRecord): string {
  return record.title.trim() || record.provision_id || record.id;
}

/** How the decision reads back on the card and in the ledger. */
export const ANSWER_LABEL: Record<RequirementAnswer, string> = {
  applies: "Applies",
  "does-not-apply": "Doesn’t apply",
  "not-sure": "Not sure",
};
