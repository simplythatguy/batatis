import { applyDescription } from "./intake";
import { professionalConfirmed, type ScopeField } from "./professional";
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

/**
 * Canonical process fact ids. GET /process-fields returns these names
 * (risk_assessment, mitigating_measures, assumptions_and_limits).
 */
export const PROCESS_FACT: Record<ProcessFieldId, string> = {
  rationale: "process.rationale",
  risk: "process.risk_assessment",
  mitigation: "process.mitigating_measures",
  assumptions: "process.assumptions_and_limits",
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
  "professional.prescriptive_route_confirmed": "Prescriptive route",
  "professional.professional_judgement_required": "Reserved professional judgement",
  "professional.role": "Registered professional",
  "professional.registration_number": "Registration number",
  "professional.seal": "Professional seal",
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
  if (!c.authority) {
    gaps.push({
      id: "detail-jurisdiction",
      severity: "blocking",
      label: "Reviewing authority missing",
      href: "#/describe",
    });
  }
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
  if (c.practiceOfEngineering === true && !professionalConfirmed(c.facts)) {
    gaps.push({
      id: "needs-professional",
      severity: "blocking",
      label: "Registered professional not confirmed",
      href: "#/application?tab=D&focus=prof-role",
    });
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
  | { type: "setFileResult"; id: string; error: string | null; read?: boolean; pages?: number; sha256?: string; unreachable?: boolean }
  | { type: "removeFile"; id: string }
  | { type: "confirmFact"; id: string }
  | { type: "dismissFact"; id: string }
  | { type: "setDetail"; field: string; value: string; section: string }
  | { type: "answerQuestion"; id: string; answer: string }
  | { type: "answerCandidate"; id: string; answer: CandidateAnswer }
  | { type: "setProcess"; field: ProcessFieldId; value: string }
  | { type: "setAuthority"; authority: Case["authority"] }
  | { type: "addCandidate"; candidate: Candidate }
  | {
      type: "addIdentified";
      articles: { provision: string; title: string | null; part: number; quote: string | null; reason: string | null; committed?: boolean }[];
    }
  | { type: "saveEvidence"; itemId: string; document: string; responsible: string; date: string }
  | { type: "setProfessionalFact"; field: string; value: string | number | boolean }
  | { type: "answerScope"; field: ScopeField; answer: "yes" | "no" | "not-sure" }
  | { type: "notePractice"; value: true | false | "unknown" }
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
        files: c.files.map((f) =>
          f.id === a.id
            ? {
                ...f,
                error: a.error ?? undefined,
                read: a.read ?? f.read,
                pages: a.pages ?? f.pages,
                sha256: a.sha256 ?? f.sha256,
                unreachable: a.error ? Boolean(a.unreachable) : false,
              }
            : f,
        ),
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
    case "addIdentified": {
      const made: Candidate[] = a.articles
        .filter((article) => /^\d/.test(article.provision))
        .map((article) => {
          const prev = c.candidates.find((card) => card.provision === article.provision);
          const quote = article.quote?.trim();
          return {
            id: `id-${article.provision}`,
            topic: article.title || article.provision,
            provision: article.provision,
            part: article.part,
            benchmark: Boolean(article.committed),
            identified: true,
            suggestion: "identify" as const,
            quote: quote
              ? { text: quote, citation: "Quoted from the code database." }
              : { text: article.reason || "No sentence was returned for this article.", citation: "No code sentence was returned." },
            departure: "do something other than what this sentence requires",
            clarifyingQuestion: "Which part of this sentence does the design not follow?",
            answer: prev?.answer ?? null,
          };
        });
      const rest = c.candidates.filter((card) => !made.some((item) => item.provision === card.provision));
      return { ...c, candidates: [...rest, ...made] };
    }
    case "saveEvidence": {
      const ref = a.document.trim();
      const who = a.responsible.trim();
      const date = a.date.trim();
      if (!ref || !who) return c;
      const taken = new Set(c.facts.filter((f) => f.field.startsWith("evidence.")).map((f) => f.field.split(".")[1]));
      let slot = a.itemId;
      if (taken.has(a.itemId)) {
        let n = 2;
        while (taken.has(`${a.itemId}~${n}`)) n += 1;
        slot = `${a.itemId}~${n}`;
      }
      const prefix = `evidence.${slot}.`;
      const pointed = (field: string, value: string, source: Fact["source"]): Fact => ({
        id: newId("f"),
        field,
        value,
        kind: "pointed",
        status: "confirmed",
        confidence: null,
        formula: null,
        inputs: [],
        source,
      });
      const facts = [
        ...c.facts,
        pointed(`${prefix}file_ref`, ref, { type: "file", ref, quote: ref }),
        pointed(`${prefix}title`, ref, { type: "user_text", ref: "Your evidence", quote: ref }),
        pointed(`${prefix}responsible_party`, who, { type: "user_text", ref: "Your evidence", quote: who }),
      ];
      if (date) facts.push(pointed(`${prefix}date`, date, { type: "user_text", ref: "Your evidence", quote: date }));
      return { ...c, facts };
    }
    case "answerScope": {
      const qid = `q-scope-${a.field}`;
      const text =
        a.field === "prescriptive_route_confirmed"
          ? "Is the design following the prescriptive route?"
          : "Does any proposed analysis require reserved professional judgement?";
      const questions = c.questions.filter((q) => q.id !== qid);
      const facts = c.facts.filter((f) => f.field !== `professional.${a.field}`);
      if (a.answer === "not-sure") {
        return {
          ...c,
          facts,
          questions: [
            ...questions,
            {
              id: qid,
              text,
              why: "You answered Not sure. This stays an open question for the officer.",
              field: `professional.${a.field}`,
            },
          ],
        };
      }
      return reducer(
        { ...c, facts, questions },
        { type: "setProfessionalFact", field: a.field, value: a.answer === "yes" },
      );
    }
    case "notePractice":
      return { ...c, practiceOfEngineering: a.value };
    case "setProfessionalFact": {
      const field = `professional.${a.field}`;
      const quote = typeof a.value === "boolean" ? (a.value ? "yes" : "no") : String(a.value);
      return {
        ...c,
        facts: upsertUserFact(c, field, String(a.value), { type: "user_click", ref: "Your answer", quote }).map((f) =>
          f.field === field && f.source.ref === "Your answer" ? { ...f, value: a.value } : f,
        ),
      };
    }
    case "reset":
      return a.to;
  }
}

export const candidateById = (c: Case, id: string): Candidate | undefined => c.candidates.find((x) => x.id === id);
