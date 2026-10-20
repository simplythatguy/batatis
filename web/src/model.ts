import { applyDescription } from "./intake";
import type { Candidate, CandidateAnswer, Case, Fact, Gap, ProcessFieldId } from "./types";

/** Section A and B fields. Values live only in `case.facts`; nothing here holds a default. */
export interface DetailField {
  id: string;
  label: string;
  section: "A" | "B";
  required: boolean;
  hint?: string;
  multiline?: boolean;
  inputType?: string;
  options?: Record<string, string>;
}

export const DETAIL_FIELDS: DetailField[] = [
  { id: "owner", label: "Owner", section: "A", required: true },
  { id: "representative", label: "Representative", section: "A", required: true, hint: "Person who signs for the applicant" },
  { id: "mailingAddress", label: "Mailing address", section: "A", required: true },
  { id: "date", label: "Date of request", section: "A", required: true, inputType: "date" },
  {
    id: "scope",
    label: "Jurisdiction-wide variance",
    section: "B",
    required: true,
    options: { site: "No, one site", jurisdiction: "Yes, jurisdiction-wide" },
  },
  { id: "permit", label: "Permit number", section: "B", required: false, hint: "Only if a permit was issued" },
  { id: "municipalAddress", label: "Municipal address", section: "B", required: true },
  { id: "legalDescription", label: "Legal description", section: "B", required: true, hint: "Lot, block, plan or ATS" },
  { id: "alternative", label: "Proposed alternative", section: "B", required: true, multiline: true },
];

export const PROCESS_FIELDS: { id: ProcessFieldId; label: string; prompts: string[] }[] = [
  {
    id: "rationale",
    label: "Rationale",
    prompts: [
      "Why is the alternative needed instead of the acceptable solution?",
      "Why do you expect it to perform at least as well?",
    ],
  },
  {
    id: "risk",
    label: "Risk assessment",
    prompts: ["What could go wrong if it under-performs?", "Who or what would be affected, and how likely is it?"],
  },
  {
    id: "mitigation",
    label: "Mitigating measures",
    prompts: ["What reduces each risk: testing, inspection, installation limits, monitoring?"],
  },
  {
    id: "assumptions",
    label: "Assumptions and limits",
    prompts: ["Under which conditions does your case hold: climate, building types, installation?"],
  },
  {
    id: "maintenance",
    label: "Maintenance and operation",
    prompts: ["What has to be operated, maintained, or commissioned after construction?"],
  },
  {
    id: "qualifications",
    label: "Qualifications",
    prompts: ["Who takes responsibility, and what is their scope? This tool does not write that opinion."],
  },
];

/** Fact field names the engine's process checker accepts. */
export const PROCESS_FACT: Record<ProcessFieldId, string> = {
  rationale: "process.rationale",
  risk: "process.risk",
  mitigation: "process.mitigation",
  assumptions: "process.assumptions",
  maintenance: "process.maintenance_operation",
  qualifications: "process.qualifications",
};

export const FACT_LABELS: Record<string, string> = {
  "product.name": "Product",
  "product.role": "What it does",
  "product.permeance": "Vapour permeance",
  "product.rsi": "Board thermal resistance",
  "product.facerStandard": "Facer test standard",
  "assembly.cavityRsi": "Stud-cavity insulation",
  "assembly.ratio": "Outside-to-inside insulation ratio",
  "assembly.claddingAttachment": "Siding attachment",
  "building.part": "Code part",
  "building.storeys": "Storeys",
  "building.form": "Building form",
  "project.description": "What you described",
  "site.climate": "Where it is installed",
  "code.edition": "Code edition",
  ...Object.fromEntries(DETAIL_FIELDS.map((f) => [f.id, f.label])),
};

export const factLabel = (field: string) => FACT_LABELS[field] ?? field;

/** Newest fact for a field. Matches the engine, where the latest entry wins. */
export const factFor = (c: Case, field: string): Fact | undefined => {
  for (let i = c.facts.length - 1; i >= 0; i--) if (c.facts[i].field === field) return c.facts[i];
  return undefined;
};

/** A fact's value as text. Engine values may be numbers or booleans; null reads as empty. */
export const valueText = (f: Fact | undefined): string => (f?.value == null ? "" : String(f.value));

/** The displayed value of a fact (select-backed fields show their option label). */
export function displayValue(f: Fact): string {
  const def = DETAIL_FIELDS.find((d) => d.id === f.field);
  const text = valueText(f);
  return def?.options?.[text] ?? text;
}

/** Source ref prefix for values the applicant typed into a field. */
export const TYPED_REF = "Typed in";
export const isTyped = (f: Fact) => f.source.type === "user_text" && f.source.ref.startsWith(TYPED_REF);

export const DETAIL_IDS = new Set(DETAIL_FIELDS.map((f) => f.id));

export function routeForDetail(id: string) {
  const def = DETAIL_FIELDS.find((f) => f.id === id);
  return `#/application?tab=${def?.section ?? "A"}&focus=field-${id}`;
}

export const answeredYes = (c: Case) => c.candidates.filter((a) => a.answer === "yes");
/** Unanswered cards block Continue. "Not sure" is an open question and does not. */
export const unresolvedCandidates = (c: Case) => c.candidates.filter((a) => a.answer === null);

/** Derived gap list: the only list any surface renders. */
export function getGaps(c: Case): Gap[] {
  const gaps: Gap[] = [];
  for (const d of DETAIL_FIELDS) {
    const fact = factFor(c, d.id);
    if (d.required && !valueText(fact).trim()) {
      gaps.push({ id: `detail-${d.id}`, severity: "blocking", label: `${d.label} missing`, href: routeForDetail(d.id) });
    }
  }
  for (const f of c.facts) {
    if (f.status !== "unconfirmed") continue;
    gaps.push({
      id: `confirm-${f.id}`,
      severity: "blocking",
      label: `Confirm ${factLabel(f.field).toLowerCase()}`,
      href: DETAIL_IDS.has(f.field) ? routeForDetail(f.field) : `#/describe?focus=fact-${f.id}`,
    });
  }
  for (const a of c.candidates) {
    if (a.answer === null) {
      gaps.push({ id: `answer-${a.id}`, severity: "blocking", label: `Answer: ${a.topic.toLowerCase()}`, href: `#/code-check?focus=cand-${a.id}` });
    }
  }
  for (const p of PROCESS_FIELDS) {
    if (!c.process[p.id].trim()) {
      gaps.push({
        id: `process-${p.id}`,
        severity: "blocking",
        label: `${p.label} empty`,
        href: `#/application?tab=alt&focus=field-${p.id}`,
      });
    }
  }
  for (const q of c.questions) {
    if (!q.answer) {
      gaps.push({ id: `question-${q.id}`, severity: "warning", label: `Open question: ${factLabel(q.field).toLowerCase()}`, href: `#/describe?focus=q-${q.id}` });
    }
  }
  const blocking = gaps.some((g) => g.severity === "blocking");
  const allNo = c.candidates.length > 0 && c.candidates.every((a) => a.answer === "no");
  if (!blocking && allNo) {
    gaps.push({
      id: "no-departure",
      severity: "warning",
      label: "No departure confirmed. You may not need a variance.",
      href: "#/code-check",
    });
  }
  return gaps;
}

export type Action =
  | { type: "setDescription"; text: string }
  | { type: "addFiles"; files: { id: string; name: string }[] }
  | { type: "setFileResult"; id: string; error: string | null; read?: boolean }
  | { type: "removeFile"; id: string }
  | { type: "confirmFact"; id: string }
  | { type: "dismissFact"; id: string }
  | { type: "setDetail"; field: string; value: string; section: string }
  | { type: "answerQuestion"; id: string; answer: string }
  | { type: "answerCandidate"; id: string; answer: CandidateAnswer }
  | { type: "setProcess"; field: ProcessFieldId; value: string }
  | { type: "setAuthority"; authority: Case["authority"] }
  | { type: "addCandidate"; candidate: Candidate }
  | { type: "reset"; to: Case };

let seq = 0;
const newId = (p: string) => `${p}-${Date.now().toString(36)}-${(seq++).toString(36)}`;

/** Replace any fact for `field` with one the applicant typed or clicked. */
function upsertUserFact(c: Case, field: string, value: string, source: Fact["source"]): Fact[] {
  const rest = c.facts.filter((f) => f.field !== field);
  if (!value.trim()) return rest;
  return [...rest, { id: newId("f"), field, value, kind: "pointed", source, status: "confirmed" }];
}

export function reducer(c: Case, a: Action): Case {
  switch (a.type) {
    case "setDescription":
      return applyDescription(c, a.text);
    case "addFiles":
      return { ...c, files: [...c.files, ...a.files.map((f) => ({ id: f.id, name: f.name, read: false }))] };
    case "setFileResult":
      return {
        ...c,
        files: c.files.map((f) => (f.id === a.id ? { ...f, error: a.error ?? undefined, read: a.read ?? f.read } : f)),
      };
    case "removeFile":
      return { ...c, files: c.files.filter((f) => f.id !== a.id) };
    case "confirmFact": {
      const old = c.facts.find((f) => f.id === a.id);
      if (!old) return c;
      const quote = old.source.quote ?? (old.value == null ? "" : String(old.value));
      const confirmed: Fact = {
        id: newId("f"),
        field: old.field,
        value: old.value,
        kind: "pointed",
        status: "confirmed",
        confidence: null,
        formula: null,
        inputs: [],
        source: { type: "user_click", ref: "Confirmed by applicant", quote },
      };
      return { ...c, facts: c.facts.filter((f) => f.id !== old.id).concat(confirmed) };
    }
    case "dismissFact":
      return { ...c, facts: c.facts.filter((f) => f.id !== a.id) };
    case "setDetail":
      return { ...c, facts: upsertUserFact(c, a.field, a.value, { type: "user_text", ref: `${TYPED_REF} Section ${a.section}` }) };
    case "answerQuestion": {
      const q = c.questions.find((x) => x.id === a.id);
      if (!q) return c;
      return {
        ...c,
        questions: c.questions.map((x) => (x.id === a.id ? { ...x, answer: a.answer } : x)),
        facts: upsertUserFact(c, q.field, a.answer, { type: "user_text", ref: "Your answer", quote: a.answer }),
      };
    }
    case "answerCandidate": {
      const cand = c.candidates.find((x) => x.id === a.id);
      const candidates = c.candidates.map((x) => (x.id === a.id ? { ...x, answer: a.answer } : x));
      const qid = `q-from-${a.id}`;
      let questions = c.questions.filter((q) => q.id !== qid);
      if (a.answer === "not-sure" && cand) {
        questions = [
          ...questions,
          {
            id: qid,
            text: cand.clarifyingQuestion,
            why: `You answered Not sure on “${cand.topic}”.`,
            field: "project.description",
          },
        ];
      }
      return { ...c, candidates, questions };
    }
    case "setProcess": {
      const field = PROCESS_FACT[a.field];
      const value = a.value;
      const facts = c.facts.filter((f) => f.field !== field);
      if (value.trim()) {
        facts.push({
          id: newId("f"),
          field,
          value,
          kind: "pointed",
          status: "confirmed",
          confidence: null,
          formula: null,
          inputs: [],
          source: { type: "user_text", ref: "Typed on the alternative path", quote: value },
        });
      }
      return { ...c, process: { ...c.process, [a.field]: value }, facts };
    }
    case "setAuthority":
      return { ...c, authority: a.authority };
    case "addCandidate":
      return c.candidates.some((x) => x.provision === a.candidate.provision)
        ? c
        : { ...c, candidates: [...c.candidates, a.candidate] };
    case "reset":
      return a.to;
  }
}

export const candidateById = (c: Case, id: string): Candidate | undefined => c.candidates.find((x) => x.id === id);
