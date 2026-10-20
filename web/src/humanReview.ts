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

export function roleNote(type: ApplicantType): { engineer: string; officer: string } {
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
  return questions.filter((q) => !q.answer && (q.id.startsWith("q-from-") || q.id.startsWith("q-scope-")));
}

/** Open questions returned by article ranking, once that route exists. */
export function rankingQuestions(questions: Question[]): Question[] {
  return questions.filter((q) => !q.answer && q.id.startsWith("q-identify-"));
}

export function professionalFlagLines(c: Pick<Case, "practiceOfEngineering" | "facts">): string[] {
  if (c.practiceOfEngineering === true) {
    return [
      professionalConfirmed(c.facts)
        ? "Practice of engineering is indicated. A registered professional is named on this application."
        : "Practice of engineering is indicated. The registered professional is not confirmed.",
    ];
  }
  if (c.practiceOfEngineering === false) return ["Practice of engineering was not indicated."];
  if (c.practiceOfEngineering === "unknown") return ["Practice of engineering is unknown."];
  return ["Practice of engineering has not been screened on this application."];
}

/**
 * What the applicant sees for one issue's practice flag.
 * A yes asks for the professional's name. It does not repeat an engineering judgment.
 * Unknown shows the question the issues route returned.
 */
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
      lead: "Name the registered professional and their seal or registration number. This screen does not state their engineering judgment.",
      question: null,
    };
  }
  return { lead: "Practice of engineering was not indicated.", question: null };
}

export interface CompletenessRecord {
  label: "Export blocked" | "Draft" | "Online review unavailable";
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
  lines.push("", "Open questions (Not sure)");
  if (!input.notSure.length) lines.push("No open Not sure answers.");
  for (const q of input.notSure) {
    lines.push(`- ${q.text}`);
    if (q.why) lines.push(`  ${q.why}`);
  }
  if (input.ranking.length) {
    lines.push("", "Open questions from article ranking");
    for (const q of input.ranking) lines.push(`- ${q.text}`);
  }
  lines.push("", "Professional");
  for (const line of input.professional) lines.push(`- ${line}`);
  lines.push("", input.record?.label ?? "No export has been requested yet.");
  if (input.record?.note) lines.push(input.record.note);
  for (const reason of input.record?.reasons ?? []) lines.push(`- ${reason}`);
  lines.push("", "Current missing items");
  if (!input.gaps.length) lines.push("No missing items in this record.");
  const groups = groupGaps(input.gaps);
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
