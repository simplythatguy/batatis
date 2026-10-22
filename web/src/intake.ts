/**
 * An empty case per applicant type, and the description as the applicant's own words.
 * Reading facts out of the description is the engine's intake route (docs/api/intake.md).
 */
import { CODE_EDITION } from "./config";
import type { ApplicantType, Case, Fact } from "./types";

export const FROM_YOU = "Your description";

const EMPTY_PROCESS: Case["process"] = {
  rationale: "",
  risk: "",
  mitigation: "",
  assumptions: "",
  maintenance: "",
  qualifications: "",
};

export function defaultTitle(type: ApplicantType): string {
  if (type === "manufacturer") return "New product application";
  if (type === "contractor") return "New construction application";
  if (type === "homebuilder" || type === "builder") return "New house application";
  return "New application";
}

export function applicantLabel(type: ApplicantType): string {
  if (type === "manufacturer") return "Manufacturer";
  if (type === "contractor") return "General contractor";
  if (type === "homebuilder" || type === "builder") return "Homebuilder";
  if (type === "designer") return "Designer";
  return "Owner";
}

export function emptyCase(type: ApplicantType): Case {
  const shaped = type === "contractor" || type === "homebuilder" || type === "manufacturer" ? type : "homebuilder";
  return {
    id: `case-${shaped}`,
    title: defaultTitle(shaped),
    applicantType: shaped,
    codeEdition: CODE_EDITION,
    authority: "",
    description: "",
    files: [],
    facts: [],
    // The intake planner asks the starting questions once the description is read (docs/api/intake.md).
    questions: [],
    candidates: [],
    sectionC: [],
    process: { ...EMPTY_PROCESS },
  };
}

function isUserKept(f: Fact): boolean {
  return (
    f.source.ref.startsWith("Typed in") ||
    f.source.ref === "Your answer" ||
    f.source.ref === "Confirmed by applicant" ||
    f.source.ref === "Typed on the alternative path"
  );
}

function detach(c: Case): Case {
  return {
    ...c,
    exampleId: undefined,
    facts: c.facts.filter(isUserKept),
    candidates: c.candidates.filter((a) => a.id.startsWith("search-")),
    sectionC: [],
    questions: c.questions.filter((q) => q.id.startsWith("q-from-")),
    title: defaultTitle(c.applicantType),
  };
}

/**
 * The description is the applicant's own words, kept as a confirmed fact. Everything read *from*
 * it (owner, address, storeys, the departure) comes from the intake route as unconfirmed facts
 * that point at those words; nothing is guessed here.
 */
export function applyDescription(c: Case, text: string): Case {
  const base = c.exampleId && text !== c.description ? detach(c) : c;
  const trimmed = text.trim();
  const facts = base.facts.filter((f) => f.source.ref !== FROM_YOU);
  if (!trimmed) {
    return { ...base, description: text, title: base.exampleId ? base.title : defaultTitle(base.applicantType), facts };
  }
  const sentence = trimmed.split(/(?<=[.!?])\s+/)[0] ?? trimmed;
  const title = sentence.length > 72 ? `${sentence.slice(0, 69)}…` : sentence;
  facts.push({ id: "desc-description", field: "project.description", value: trimmed, kind: "pointed", status: "confirmed", source: { type: "user_text", ref: FROM_YOU, quote: trimmed } });
  return { ...base, description: text, title: base.exampleId ? base.title : title, facts };
}
