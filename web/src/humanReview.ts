/**
 * Human-review routing. Completeness stays administrative.
 * Contradictions, relevance, adequacy, and licence authenticity are for the officer.
 * No field here is invented for an endpoint that has not returned it.
 */
import type { ApplicantType, Case, Gap, Question } from "./types";
import { professionalConfirmed } from "./professional";

export const SCO_JUDGEMENT = [
  { id: "contradictions", label: "Contradictions between the written application and a document" },
  { id: "relevance", label: "Whether a cited provision is relevant" },
  { id: "adequacy", label: "Whether the evidence is adequate" },
  { id: "licence-authenticity", label: "Whether a licence or seal is authentic" },
] as const;

export const GROUP_LABEL: Record<string, string> = {
  A: "Section A · Applicant",
  B: "Section B · Project",
  C: "Section C · Code references",
  D: "Section D · Supporting information",
  process: "Alternative path",
  facts: "Facts and questions",
};

const ROLE_NOTES: Record<"manufacturer" | "contractor" | "homebuilder", { engineer: string; officer: string }> = {
  manufacturer: {
    engineer:
      "You need an engineer or architect when the way this product is used is practice of engineering. Name that person and their seal or registration number. This tool does not write their judgment.",
    officer:
      "The officer decides whether the file is complete enough to review, and decides contradictions, relevance, adequacy, and whether a licence is authentic.",
  },
  contractor: {
    engineer:
      "You need an engineer or architect when this job's design is practice of engineering. Name that person and their seal or registration number. This tool does not write their judgment.",
    officer:
      "The officer decides whether the file is complete enough to review, and decides contradictions, relevance, adequacy, and whether a licence is authentic.",
  },
  homebuilder: {
    engineer:
      "You need an engineer or architect when this house leaves the written prescriptive rules in a way that is practice of engineering. Name that person and their seal or registration number. This tool does not write their judgment.",
    officer:
      "The officer decides whether the file is complete enough to review, and decides contradictions, relevance, adequacy, and whether a licence is authentic.",
  },
};

export function roleNote(type: ApplicantType | null): { engineer: string; officer: string } {
  if (type === "manufacturer" || type === "contractor" || type === "homebuilder") return ROLE_NOTES[type];
  if (type === "builder") return ROLE_NOTES.homebuilder;
  return {
    engineer:
      "You need an engineer or architect when this design is practice of engineering. Name that person and their seal or registration number. This tool does not write their judgment.",
    officer: ROLE_NOTES.contractor.officer,
  };
}

/** Not sure on an article or on a professional-scope question. Intake starters are not included. */
export function notSureQuestions(questions: Question[]): Question[] {
  return questions.filter(
    (q) =>
      !q.answer &&
      (q.kind === "article" ||
        q.id.startsWith("q-from-") ||
        q.id.startsWith("q-scope-") ||
        q.id.startsWith("q-prof-") ||
        q.id.startsWith("oq_")),
  );
}

/** Open questions returned by article ranking, once that route exists. */
export function rankingQuestions(questions: Question[]): Question[] {
  return questions.filter((q) => !q.answer && (q.kind === "intake" || q.id.startsWith("q-identify-")));
}

export interface InformationItem {
  id: string;
  provision_id: string;
  text: string;
}

/** Engine items that are not already in the local Not sure list. */
export function unseenRequestItems(notSure: { id: string; text: string }[], items: InformationItem[]): InformationItem[] {
  const ids = new Set(notSure.map((q) => q.id));
  const texts = new Set(notSure.map((q) => q.text.trim()));
  return items.filter((item) => item.id.trim() && item.text.trim() && !ids.has(item.id) && !texts.has(item.text.trim()));
}

/** Officer line. "Not yet checked" until GET /professional has returned. */
export function officerProfessionalLines(
  checked: "pending" | "ready",
  practice: true | false | "unknown" | undefined,
  facts: Case["facts"],
): string[] {
  if (checked !== "ready") return ["Not yet checked."];
  if (practice === true) {
    return [
      professionalConfirmed(facts)
        ? "Practice of engineering is indicated. A registered professional is named on this application."
        : "Practice of engineering is indicated. The required registered professional is not confirmed. Provide their identity, registration or seal, and authenticated work; an engagement answer does not waive that duty.",
    ];
  }
  if (practice === false) return ["Practice of engineering was not indicated."];
  return ["More facts are needed before this screen can say whether practice of engineering applies. This is not a licence decision."];
}

export function professionalFlagLines(c: Pick<Case, "practiceOfEngineering" | "facts">): string[] {
  if (c.practiceOfEngineering === true) {
    return [
      professionalConfirmed(c.facts)
        ? "Practice of engineering is indicated. A registered professional is named on this application."
        : "Practice of engineering is indicated. The required registered professional is not confirmed. Provide their identity, registration or seal, and authenticated work; an engagement answer does not waive that duty.",
    ];
  }
  if (c.practiceOfEngineering === false) return ["Practice of engineering was not indicated."];
  if (c.practiceOfEngineering === "unknown") return ["Not yet known whether a registered professional is required. Routed to the officer."];
  return ["Practice of engineering has not been screened on this application."];
}

type ProfessionalGap = { id: string; field?: string };
const PROFESSIONAL_HOLD = /responsible_professional|professional_confirmation|professional_authentication|professional_qualifications|professional_requirement|professional_source|professional\.role|needs-professional|professional-not-engaged/;

/** A professional blocker the applicant cannot clear by inventing a seal. */
export function isProfessionalHold(gap: { id: string; field?: string }): boolean {
  return PROFESSIONAL_HOLD.test(gap.id) || PROFESSIONAL_HOLD.test(gap.field ?? "");
}

/** Requirement determination is distinct from a known duty's missing credentials or work. */
export function professionalHoldKind(gaps: ProfessionalGap[]): "source" | "requirement" | "confirmation" | null {
  if (gaps.some(g => /professional_source|professional:source_lookup/.test(`${g.id} ${g.field ?? ""}`))) return "source";
  if (gaps.some(g => /professional_confirmation|responsible_professional|professional_authentication|professional_qualifications|needs-professional/.test(`${g.id} ${g.field ?? ""}`))) return "confirmation";
  if (gaps.some(g => /professional_requirement|practice-unknown|professional-not-engaged/.test(`${g.id} ${g.field ?? ""}`))) return "requirement";
  return gaps.some(isProfessionalHold) ? "confirmation" : null;
}

export function professionalHoldReason(gaps: ProfessionalGap[]): string | null {
  const kind = professionalHoldKind(gaps);
  if (kind === "requirement") return "Waiting for the officer to determine whether a registered professional is required.";
  if (kind === "source") return "Waiting for the professional requirement’s source references to be resolved.";
  if (kind === "confirmation") return "Waiting for the required professional’s information or authenticated work.";
  return null;
}

/** What to do while the official PDF stays closed for a missing engineer or architect. */
export function professionalRouteNote(gaps: { id: string; field?: string }[]): string | null {
  const kind = professionalHoldKind(gaps);
  if (kind === "requirement") return "The unresolved professional requirement is routed to the officer. The officer determines whether one is required for this scope; no professional confirmation is being asserted. That does not open the official PDF or administrative acceptance. Submit the question with your application when the other required items are complete. A draft PDF remains available. Do not invent a number.";
  if (kind === "source") return "The professional requirement’s source references need review before the requirement can be determined. Submission, acceptance and the official PDF wait for those references. A draft PDF remains available.";
  if (kind === "confirmation") return "A professional is required for this scope. Provide their identity, registration or seal, and the required authenticated work before submission, administrative acceptance or the official PDF. Not sure and Not engaged yet do not waive that duty. A draft PDF remains available. Do not invent a number.";
  return null;
}

/** Keep the missing item, and say it goes to the officer with a next step. */
export function officerRoutedLabel(message: string): string {
  const base = message.trim();
  if (/routed to the officer/i.test(base)) return base;
  const sentence = base.endsWith(".") ? base : `${base}.`;
  return `${sentence} This item is routed to the officer. Choose Not sure or Not engaged yet to send it there, or name an engineer or architect and their seal or registration number. A draft PDF is available. Do not invent a number. The official PDF stays closed until that confirmation is real.`;
}

/** One line for the professional screen. The flag word is not repeated. */
export function practiceFlagLine(flag: "yes" | "no" | "depends"): string {
  if (flag === "yes") return "Practice of engineering is indicated. A registered professional is needed. This is not a licence decision.";
  if (flag === "no") return "The screen did not indicate practice of engineering.";
  return "More facts are needed before this screen can say whether practice of engineering applies. This is not a licence decision.";
}

export function practicePrompt(
  value: true | false | "unknown",
  question: string | null,
): { lead: string; question: string | null } {
  if (value === "unknown") {
    return {
      lead: "Practice of engineering is unknown. This is not a yes or a no.",
      question,
    };
  }
  if (value === true) {
    return {
      lead: "A registered professional is required for this scope. Name the registered professional and their seal or registration number, and supply the required authenticated work. Not sure or Not engaged yet does not waive the duty. This screen does not state their engineering judgment.",
      question: null,
    };
  }
  return { lead: "Practice of engineering was not indicated.", question: null };
}

export interface CompletenessRecord {
  label: "Export blocked" | "Draft" | "Online review unavailable" | "Not exported yet" | "Application PDF";
  /** Strings the export call returned. Empty when the block is the missing-item list. */
  reasons: string[];
  note: string;
}

export function groupOf(gap: Gap, section: string | undefined): string {
  if (section === "A" || section === "B" || section === "C" || section === "D" || section === "process") return section;
  const href = gap.href;
  if (href.includes("tab=A")) return "A";
  if (href.includes("tab=B")) return "B";
  if (href.includes("section-c") || href.includes("code-check") || href.includes("provisions")) return "C";
  if (href.includes("tab=D")) return "D";
  if (href.includes("tab=alt")) return "process";
  return "facts";
}

export function groupGaps(gaps: Gap[], sectionById: ReadonlyMap<string, string> = new Map()): Map<string, Gap[]> {
  const groups = new Map<string, Gap[]>();
  for (const gap of gaps) {
    const key = groupOf(gap, sectionById.get(gap.id));
    groups.set(key, [...(groups.get(key) ?? []), gap]);
  }
  return groups;
}

export interface RequestFile {
  name: string;
  pages?: number;
  read: boolean;
  error?: string;
}

export function officerRequest(input: {
  title: string;
  exampleLabel?: string;
  files: RequestFile[];
  gaps: Gap[];
  notSure: Question[];
  ranking: Question[];
  professional: string[];
  record: CompletenessRecord | null;
  role: { engineer: string; officer: string };
  reportNote: string | null;
  engineItems?: InformationItem[];
  sectionById?: ReadonlyMap<string, string>;
}): string {
  const lines = [
    ...(input.exampleLabel ? [`EXAMPLE — ${input.exampleLabel}`, "For practice. Not for submission."] : []),
    input.title || "Application",
    "Administrative completeness. This does not decide whether the design complies or is safe.",
    "",
    input.role.engineer,
    input.role.officer,
    "",
    "Documents",
  ];
  if (!input.files.length) {
    lines.push("No documents uploaded on this application.");
  } else {
    for (const file of input.files) {
      const pages = file.pages ? `, ${file.pages} pages` : "";
      const state = file.error ? file.error : file.read ? "stored" : "not read yet";
      lines.push(`- ${file.name}${pages} (${state})`);
    }
  }
  const engineItems = unseenRequestItems(input.notSure, input.engineItems ?? []);
  lines.push("", "Questions the applicant marked Not sure");
  if (!input.notSure.length && !engineItems.length) lines.push("No questions marked Not sure.");
  for (const q of input.notSure) {
    lines.push(`- ${q.text}`);
    if (q.why) lines.push(`  ${q.why}`);
  }
  for (const item of engineItems) {
    lines.push(`- ${item.text}`);
    lines.push(`  ${item.provision_id}`);
  }
  if (input.ranking.length) {
    lines.push("", "Questions from code matching");
    for (const q of input.ranking) lines.push(`- ${q.text}`);
  }
  lines.push("", "Professional");
  for (const line of input.professional) lines.push(`- ${line}`);
  lines.push("", input.record?.label ?? "No export has been requested yet.");
  if (input.record?.note) lines.push(input.record.note);
  for (const reason of input.record?.reasons ?? []) lines.push(`- ${reason}`);
  lines.push("", "Current missing items");
  if (!input.gaps.length) lines.push("No missing items in this record.");
  const groups = groupGaps(input.gaps, input.sectionById);
  for (const key of ["A", "B", "C", "D", "process", "facts"]) {
    const items = groups.get(key);
    if (!items?.length) continue;
    lines.push(GROUP_LABEL[key]);
    for (const gap of items) lines.push(`- ${gap.label}`);
  }
  if (input.reportNote) {
    lines.push("", "Grouped completeness report", input.reportNote);
  }
  lines.push("", "SCO judgement", "Administrative completeness does not decide these.");
  for (const item of SCO_JUDGEMENT) lines.push(`- ${item.label}`);
  return lines.join("\n");
}

export const UNSIGNED_LINE =
  "Unsigned. Officer Part 2 is blank. The attachment pages are generated by Batatis; they are not Appendix 1.";

/**
 * The text record's PDF line. Four outcomes, matching the draft-record contract:
 * downloaded, blocked with reasons, failed, or not prepared.
 * A completeness check that never asked for a PDF is "not prepared", not "blocked".
 */
export function pdfOutcomeLine(input: {
  example: boolean;
  downloaded: { name: string; draft: boolean; at: string } | null;
  blocked?: boolean;
  failed?: boolean;
  reasons?: string[];
}): string[] {
  if (input.example) return ["Example: PDF not offered."];
  if (input.downloaded) {
    const kind = input.downloaded.draft ? "draft PDF " : "";
    const lines = [`Application PDF: downloaded ${kind}${input.downloaded.name} at ${input.downloaded.at}.`];
    if (!input.downloaded.draft) lines.push(UNSIGNED_LINE);
    return lines;
  }
  if (input.blocked) {
    const reasons = (input.reasons ?? []).map((reason) => reason.trim()).filter(Boolean);
    return ["Application PDF: blocked. Reasons:", ...(reasons.length ? reasons : ["The PDF was blocked."]).map((reason) => `- ${reason}`)];
  }
  if (input.failed) {
    const detail = (input.reasons ?? []).map((reason) => reason.trim()).filter((reason) => reason && reason !== "The PDF could not be prepared.");
    return ["Application PDF: could not be prepared.", ...detail];
  }
  return ["Application PDF: not prepared in this session."];
}

export function textRecord(input: {
  exampleLabel?: string;
  title: string;
  description: string;
  factLines: string[];
  blockingCount: number;
  warningCount: number;
  checkedAt?: string;
  pdfLines: string[];
}): string {
  const questions = `${input.warningCount} open question${input.warningCount === 1 ? "" : "s"}`;
  const required = `${input.blockingCount} required item${input.blockingCount === 1 ? "" : "s"}`;
  return [
    ...(input.exampleLabel ? [`EXAMPLE — ${input.exampleLabel}`, "For practice. Not for submission.", ""] : []),
    input.title,
    input.description,
    "",
    ...input.factLines,
    "",
    input.checkedAt ? `Completeness: ${required}, ${questions}, checked at ${input.checkedAt}.` : "Completeness has not been checked for this draft revision.",
    "This does not decide whether the design complies or is safe.",
    "",
    ...input.pdfLines,
    "",
    "A text record is not the Safety Codes Council form.",
  ].join("\n");
}
