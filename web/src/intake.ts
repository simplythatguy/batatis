/**
 * Turn the applicant's own words into facts and code-check cards.
 * Cards from this module are questions, not ranked articles. Search and identify run from Section C.
 */
import { CODE_EDITION } from "./config";
import type { ApplicantType, Candidate, CandidateAnswer, Case, Fact, Question } from "./types";

export const FROM_YOU = "Your description";
export const NOT_IDENTIFIED = "Your description. No article has been ranked yet.";

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

const STARTER: Record<"manufacturer" | "contractor" | "homebuilder", Question[]> = {
  manufacturer: [
    {
      id: "q-product",
      text: "What is the product called, and what does it do?",
      why: "A manufacturer application starts from the product, not from one house.",
      field: "product.name",
    },
    {
      id: "q-where",
      text: "Where will it be installed, and is that one site or many?",
      why: "That decides whether the variance is jurisdiction-wide.",
      field: "scope",
    },
  ],
  contractor: [
    {
      id: "q-job",
      text: "What are you building, and which requirement can you not follow as written?",
      why: "A contractor application is about one job's departure.",
      field: "alternative",
    },
    {
      id: "q-site",
      text: "What is the municipal address of the job?",
      why: "Section B needs the site.",
      field: "municipalAddress",
    },
  ],
  homebuilder: [
    {
      id: "q-storeys",
      text: "How many storeys is the house, and is that under 3?",
      why: "Storey count decides which part of the code is the benchmark.",
      field: "building.storeys",
    },
    {
      id: "q-suite",
      text: "Is this a house, a garden suite, or both?",
      why: "A suite changes the articles that can apply.",
      field: "building.form",
    },
  ],
};

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
    questions: STARTER[shaped].map((q) => ({ ...q })),
    candidates: [],
    sectionC: [],
    process: { ...EMPTY_PROCESS },
  };
}

const STOREY = /\b(\d+|one|two|three|four|five|six)[\s-]*storeys?\b/i;

const SUBJECTS: { re: RegExp; topic: string; departure: string; ask: string }[] = [
  {
    re: /hempcrete/i,
    topic: "Hempcrete walls",
    departure: "use hempcrete walls instead of the wall an acceptable solution would specify",
    ask: "Which part of the wall is hempcrete, and what would the acceptable solution have used?",
  },
  {
    re: /garden suite/i,
    topic: "Garden suite",
    departure: "build a garden suite that does not follow an acceptable solution as written",
    ask: "What about the suite does not follow the acceptable solution?",
  },
  {
    re: /soffit/i,
    topic: "Roof soffit",
    departure: "build a soffit that does not follow the acceptable solution as written",
    ask: "How is the soffit built, and which limit does it pass?",
  },
  {
    re: /fire damper|\bdamper/i,
    topic: "Fire dampers",
    departure: "omit fire dampers where an acceptable solution would require them",
    ask: "What is proposed instead of the damper?",
  },
  {
    re: /sheathing|housewrap|membrane/i,
    topic: "Sheathing membrane",
    departure: "use something other than the sheathing membrane an acceptable solution names",
    ask: "What is taking the place of the membrane?",
  },
];

const ADMIN_LINES: { field: "owner" | "representative" | "mailingAddress" | "municipalAddress" | "legalDescription" | "permit"; re: RegExp }[] = [
  { field: "owner", re: /^(?:owner(?: name)?)\s*[:\-]\s*(.+)$/i },
  { field: "representative", re: /^(?:representative|rep)\s*[:\-]\s*(.+)$/i },
  { field: "mailingAddress", re: /^(?:mailing address)\s*[:\-]\s*(.+)$/i },
  { field: "municipalAddress", re: /^(?:municipal address|civic address|site address|site|address)\s*[:\-]\s*(.+)$/i },
  { field: "legalDescription", re: /^(?:legal description|legal)\s*[:\-]\s*(.+)$/i },
  { field: "permit", re: /^(?:permit(?:\s+number|\s*#)?)\s*[:\-]\s*(.+)$/i },
];

export interface ExtractedAdmin {
  owner?: string;
  representative?: string;
  mailingAddress?: string;
  municipalAddress?: string;
  legalDescription?: string;
  permit?: string;
  /** Only a line the applicant labeled as the proposed alternative. */
  alternative?: string;
  narrative: string;
}

const ALTERNATIVE_LINE = /^(?:proposed alternative|alternative solution|alternative)\s*[:\-]\s*(.+)$/i;

/** Pull labeled owner, address, legal description, and permit lines out of pasted text. */
export function extractAdmin(text: string): ExtractedAdmin {
  const found: Omit<ExtractedAdmin, "narrative"> = {};
  const kept: string[] = [];
  for (const line of text.split(/\n/)) {
    const trimmed = line.trim();
    if (!found.alternative && ALTERNATIVE_LINE.test(trimmed)) {
      found.alternative = trimmed.match(ALTERNATIVE_LINE)?.[1]?.trim() ?? "";
      continue;
    }
    const hit = ADMIN_LINES.find((label) => label.re.test(trimmed) && !found[label.field]);
    if (hit) {
      found[hit.field] = trimmed.match(hit.re)?.[1]?.trim() ?? "";
      continue;
    }
    kept.push(line);
  }
  const rest = kept.join("\n");
  if (!found.permit) {
    const permit = rest.match(/\b(BP-[A-Za-z0-9-]+)\b/);
    if (permit) found.permit = permit[1];
  }
  if (!found.legalDescription) {
    const legal = rest.match(/\b(Lot\s+\S+,?\s*Block\s+\S+,?\s*Plan\s+\S+)/i);
    if (legal) found.legalDescription = legal[1].replace(/\s+/g, " ").trim();
  }
  if (!found.municipalAddress) {
    const address = rest.match(
      /\b(\d{1,6}\s+[A-Za-z0-9.'-]+(?:\s+[A-Za-z0-9.'-]+){0,4}\s(?:Avenue|Street|Crescent|Way|Road|Drive|Boulevard)\s+(?:NW|NE|SW|SE)(?:,\s*[A-Za-z. ]+)?)/,
    );
    if (address) found.municipalAddress = address[1].replace(/\s+/g, " ").trim();
  }
  return { ...found, narrative: rest.trim() };
}

function pointed(id: string, field: string, value: string): Fact {
  return {
    id,
    field,
    value,
    kind: "pointed",
    status: "confirmed",
    source: { type: "user_text", ref: FROM_YOU, quote: value },
  };
}

function card(id: string, topic: string, departure: string, ask: string, quote: string, prev: CandidateAnswer | null): Candidate {
  return {
    id,
    topic,
    provision: "",
    part: 0,
    benchmark: false,
    identified: false,
    quote: { text: quote, citation: NOT_IDENTIFIED },
    departure,
    clarifyingQuestion: ask,
    answer: prev,
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

/** Replace description-derived facts and cards. Example content drops once the text changes. */
export function applyDescription(c: Case, text: string): Case {
  const base = c.exampleId && text !== c.description ? detach(c) : c;
  const trimmed = text.trim();
  const facts = base.facts.filter((f) => f.source.ref !== FROM_YOU);
  const candidates = base.candidates.filter((a) => !a.id.startsWith("desc-"));
  const questions = base.questions.filter((q) => !q.id.startsWith("q-desc-"));
  if (!trimmed) {
    return { ...base, description: text, title: base.exampleId ? base.title : defaultTitle(base.applicantType), facts, candidates, questions };
  }

  const sentence = trimmed.split(/(?<=[.!?])\s+/)[0] ?? trimmed;
  const title = sentence.length > 72 ? `${sentence.slice(0, 69)}…` : sentence;
  facts.push(pointed("desc-description", "project.description", trimmed));
  const extracted = extractAdmin(trimmed);
  const adminFields = ["owner", "representative", "mailingAddress", "municipalAddress", "legalDescription", "permit"] as const;
  for (const field of adminFields) {
    const value = extracted[field];
    if (!value) continue;
    const existing = facts.find((f) => f.field === field);
    if (existing && isUserKept(existing)) continue;
    const rest = facts.filter((f) => f.field !== field);
    rest.push(pointed(`desc-${field}`, field, value));
    facts.length = 0;
    facts.push(...rest);
  }
  // The paste stays in the description. Proposed alternative is filled only from a labeled line,
  // so the rest of the brief is not copied into that field.
  if (extracted.alternative) {
    const existing = facts.find((f) => f.field === "alternative");
    if (!existing || !isUserKept(existing)) {
      const rest = facts.filter((f) => f.field !== "alternative");
      rest.push(pointed("desc-alternative", "alternative", extracted.alternative));
      facts.length = 0;
      facts.push(...rest);
    }
  }

  const storey = trimmed.match(STOREY);
  // A count read out of the sentence is a proposal. It is not a confirmed fact.
  if (storey && !facts.some((f) => f.field === "building.storeys")) {
    facts.push({
      id: "desc-storeys",
      field: "building.storeys",
      value: storey[0],
      kind: "proposed",
      status: "unconfirmed",
      confidence: null,
      formula: null,
      inputs: [],
      source: { type: "user_text", ref: FROM_YOU, quote: storey[0] },
    });
  }

  const made: Candidate[] = [];
  const hits = SUBJECTS.filter((s) => s.re.test(trimmed)).slice(0, 2);
  const subjects = hits.length
    ? hits
    : [
        {
          topic: "What you described",
          departure: "do something other than an acceptable solution",
          ask: "What would the acceptable solution have required here?",
        },
      ];
  subjects.forEach((s, i) => {
    const id = `desc-subject-${i}`;
    made.push(card(id, s.topic, s.departure, s.ask, sentence, base.candidates.find((a) => a.id === id)?.answer ?? null));
  });
  if (!storey) {
    const id = "desc-storeys";
    made.push(
      card(
        id,
        "Storey count",
        "build it without stating whether it is under 3 storeys",
        "How many storeys is it? Is that under 3?",
        sentence,
        base.candidates.find((a) => a.id === id)?.answer ?? null,
      ),
    );
    if (!questions.some((q) => q.field === "building.storeys")) {
      questions.push({
        id: "q-desc-storeys",
        text: "How many storeys is it? Is that under 3?",
        why: "You have not stated a storey count. The count decides which part is the benchmark.",
        field: "building.storeys",
        answer: base.questions.find((q) => q.id === "q-desc-storeys")?.answer,
      });
    }
  }

  for (const cand of made) {
    if (cand.answer !== "not-sure") continue;
    if (questions.some((q) => q.id === `q-from-${cand.id}`)) continue;
    questions.push({
      id: `q-from-${cand.id}`,
      text: cand.clarifyingQuestion,
      why: `You answered Not sure on “${cand.topic}”.`,
      field: "project.description",
    });
  }

  return {
    ...base,
    description: text,
    title: base.exampleId ? base.title : title,
    facts,
    candidates: [...candidates, ...made],
    questions,
  };
}
