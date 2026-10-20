/**
 * One planted administrative package for the officer screen.
 * Names and the street address are example data, marked as such. The gaps are empty fields and a placeholder,
 * the same classes the engine flags without needing a code citation.
 */
import type { EngineGap } from "./api/client";
import type { Fact } from "./types";

const PLACEHOLDERS = new Set(["tbd", "tobedetermined", "tobeprovided", "unknown", "pending", "na", "notprovided", "placeholder"]);

function fact(field: string, value: string): Fact {
  return {
    id: `planted-${field}`,
    field,
    value,
    kind: "pointed",
    status: "confirmed",
    source: { type: "user_text", ref: "Planted package", quote: value },
  };
}

const shared: Fact[] = [
  fact("alternative", "Hempcrete walls for a garden suite behind an existing house in Edmonton."),
  fact("municipalAddress", "000 Example Avenue NW, Edmonton (EXAMPLE DATA)"),
  fact("mailingAddress", "000 Example Avenue NW, Edmonton (EXAMPLE DATA)"),
  fact("scope", "site"),
  fact("process.mitigating_measures", "The walls stay above grade, with a rainscreen and a capillary break at the sill."),
  fact("process.assumptions_and_limits", "One storey, one suite, no second dwelling unit inside the garden suite."),
  fact("process.rationale", "The owner wants hempcrete instead of the Part 9 wall the acceptable solution describes."),
];

export const PLANTED_BEFORE: Fact[] = [
  ...shared,
  fact("legalDescription", "TBD"),
];

export const PLANTED_AFTER: Fact[] = [
  ...shared,
  fact("owner", "Example Applicant"),
  fact("representative", "Example Applicant"),
  fact("date", "2026-10-20"),
  fact("legalDescription", "Lot 1, Block 1, Plan EXAMPLE"),
  fact("process.risk_assessment", "If the hempcrete stays wet, the wall can lose strength and the suite can grow mould."),
  fact("process.maintenance_operation", "The owner checks the rainscreen vents once a year."),
  fact("process.qualifications", "No professional is named yet."),
];

const CHECKS: { id: string; section: EngineGap["section"]; field: string; label: string; aliases: string[] }[] = [
  { id: "D01:owner_name", section: "A", field: "owner_name", label: "the owner name", aliases: ["owner", "owner_name"] },
  { id: "admin:representative", section: "A", field: "representative", label: "the applicant representative", aliases: ["representative"] },
  { id: "D02:application_date", section: "A", field: "application_date", label: "the application date", aliases: ["date", "request_date"] },
  { id: "admin:mailing_address", section: "A", field: "mailing_address", label: "the mailing address", aliases: ["mailingAddress", "mailing_address"] },
  { id: "D03:civic_address", section: "B", field: "civic_address", label: "the civic address", aliases: ["municipalAddress", "municipal_address"] },
  { id: "D04:legal_description", section: "B", field: "legal_description", label: "a completed legal description", aliases: ["legalDescription", "legal_description"] },
  { id: "admin:alternative_description", section: "B", field: "alternative_description", label: "the description of the proposed alternative", aliases: ["alternative"] },
  { id: "D09:risk_assessment", section: "process", field: "risk_assessment", label: "the applicant-written risk assessment", aliases: ["process.risk", "process.risk_assessment"] },
  { id: "D10:mitigating_measures", section: "process", field: "mitigating_measures", label: "the applicant-written mitigating measures", aliases: ["process.mitigation", "process.mitigating_measures"] },
  { id: "D11:assumptions_and_limits", section: "process", field: "assumptions_and_limits", label: "the applicant-written assumptions and limits", aliases: ["process.assumptions", "process.assumptions_and_limits"] },
];

function confirmed(facts: Fact[], aliases: string[]): string | null {
  for (let i = facts.length - 1; i >= 0; i--) {
    const f = facts[i];
    if (!aliases.includes(f.field) || f.status !== "confirmed" || f.kind === "proposed") continue;
    return f.value == null ? "" : String(f.value);
  }
  return null;
}

function blank(value: string | null): boolean {
  if (value == null || !value.trim()) return true;
  return PLACEHOLDERS.has(value.toLowerCase().replace(/\W/g, ""));
}

/** Browser stand-in used only when GET /cases/{id}/gaps does not return. */
export function browserPlantedGaps(facts: Fact[]): EngineGap[] {
  return CHECKS.filter((c) => blank(confirmed(facts, c.aliases))).map((c) => ({
    id: c.id,
    section: c.section,
    field: c.field,
    severity: "blocking" as const,
    message: `Your application appears to be missing ${c.label}.`,
    fix_hint: `Ask the applicant to enter or confirm ${c.label}.`,
    citation: null,
  }));
}

export const SECTION_ORDER = ["A", "B", "C", "D", "process"] as const;

export const SECTION_LABEL: Record<(typeof SECTION_ORDER)[number], string> = {
  A: "Part 1 · Section A",
  B: "Part 1 · Section B",
  C: "Part 1 · Section C",
  D: "Part 1 · Section D",
  process: "Alternative path",
};
