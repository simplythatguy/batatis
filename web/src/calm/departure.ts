/** The departure card's comparison: what the code asks, what the design does, and the drafted difference. */
import type { DraftingRecord } from "../api/types.gen";
import { factFor, valueText } from "../model";
import { withinProvision } from "../provisions";
import { decidePath } from "../pathDecision";
import { quoteKind } from "../rules";
import { routeChoice } from "./journey";
import type { Candidate, Case } from "../types";

/** The engine's limit on a recorded departure (http_models.BenchmarkRequest). */
export const DEPARTURE_MAX = 300;

export interface DepartureComparison {
  /** Verbatim code text, when the card carries it. */
  code?: string;
  /** The applicant's own words for the design. */
  design: string;
  /** The drafted Section C explanation for this sentence; written by Batatis, never code text. */
  gap?: string;
  /** What Confirm records: the design, within the engine's limit. */
  departure: string;
}

/** Whole sentences up to `max` characters; one long sentence is cut with an ellipsis. */
export function fitDeparture(text: string, max = DEPARTURE_MAX): string {
  const t = text.replace(/\s+/g, " ").trim();
  if (t.length <= max) return t;
  const cut = t.slice(0, max);
  const end = Math.max(cut.lastIndexOf(". "), cut.lastIndexOf("! "), cut.lastIndexOf("? "));
  return end > 0 ? cut.slice(0, end + 1) : `${t.slice(0, max - 1).trimEnd()}…`;
}

export function departureComparison(c: Case, a: Candidate, drafting: Pick<DraftingRecord, "drafts"> | null): DepartureComparison {
  const alternative = factFor(c, "alternative");
  const design = (alternative?.source.quote || valueText(alternative)).trim() || c.description.trim();
  const explains = (field: string) => /^section_c\..+\.explanation$/.test(field) && withinProvision(field.slice("section_c.".length, -".explanation".length), a.provision);
  const gap = drafting?.drafts.filter((d) => d.text.trim() && explains(d.field)).at(-1)?.text.trim();
  return {
    code: quoteKind(a) === "code" ? a.quote.text.trim() : undefined,
    design,
    gap: gap || undefined,
    departure: fitDeparture(design),
  };
}

/** Confirming a departure records the variance route, unless a firm coded check decides the path or the route already says so. */
export function departureRecordsVariance(c: Case): boolean {
  const route = routeChoice(c);
  return !decidePath(c).firm && route !== "variance" && route !== "different";
}
