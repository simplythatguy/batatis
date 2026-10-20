import type { IdentifyResult } from "./api/identify";
import type { Candidate, CandidateAnswer, Case, CodeIdAnswer, CodeIdQuestion, CodeIdRun, Fact, Gap, ProcessFieldId } from "./types";

/** Section A and B fields. Values live only in `case.facts`; nothing here holds a default. */
export interface DetailField {
  id: string;
  label: string;
  section: "A" | "B";
  required: boolean;
  hint?: string;
  multiline?: boolean;
  options?: Record<string, string>;
}

export const DETAIL_FIELDS: DetailField[] = [
  { id: "owner", label: "Owner", section: "A", required: true },
  { id: "representative", label: "Representative", section: "A", required: true, hint: "Person who signs for the applicant" },
  { id: "mailingAddress", label: "Mailing address", section: "A", required: true },
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
];

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
  "site.climate": "Where it is installed",
  "code.edition": "Code edition",
  ...Object.fromEntries(DETAIL_FIELDS.map((f) => [f.id, f.label])),
};

export const factLabel = (field: string) => FACT_LABELS[field] ?? field;

export const factFor = (c: Case, field: string): Fact | undefined => c.facts.find((f) => f.field === field);

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
export const unresolvedCandidates = (c: Case) => c.candidates.filter((a) => a.answer !== "yes" && a.answer !== "no");

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
  if (c.codeId) gaps.push(...codeIdGaps(c.codeId));
  else {
    // Fixture candidates (example data) until Code ID has run. Never a blocking gap: no one is forced to pick.
    for (const a of c.candidates) {
      if (a.answer === null || a.answer === "not-sure") {
        gaps.push({
          id: `answer-${a.id}`,
          severity: "warning",
          label: `${a.answer === null ? "Not answered" : "Not sure yet"}: ${a.topic.toLowerCase()}`,
          href: `#/code-check?focus=cand-${a.id}`,
        });
      }
    }
    if (c.candidates.length && !unresolvedCandidates(c).length && !answeredYes(c).length) {
      gaps.push({
        id: "no-departure",
        severity: "warning",
        label: "No departure confirmed: you may not need a variance",
        href: "#/code-check",
      });
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
  return gaps;
}

export const OFFICER_QUESTION_ID = "cq-none-fit";
export const acceptedArticles = (run: CodeIdRun) => run.result.articles.filter((a) => run.answers[a.provision] === "yes");

function codeIdGaps(run: CodeIdRun): Gap[] {
  const gaps: Gap[] = run.questions.map((q) => ({
    id: `codeid-${q.id}`,
    severity: "warning",
    label: q.to === "officer" ? "Ask the officer: which article applies" : `Not sure: article ${q.provision}`,
    href: q.to === "officer" ? "#/code-check?focus=none-fit" : `#/code-check?focus=card-${q.provision}`,
  }));
  if (!acceptedArticles(run).length && !run.questions.some((q) => q.to === "officer")) {
    gaps.push({ id: "codeid-none", severity: "warning", label: "No code article chosen for Section C yet", href: "#/code-check" });
  }
  return gaps;
}

/** The question a "Not sure" adds: the engine's open question that settles this article, else a plain one. */
function notSureQuestion(r: IdentifyResult, provision: string): CodeIdQuestion {
  const q = r.open_questions.find((x) => x.disambiguates.includes(provision) && !x.answer);
  const title = r.articles.find((a) => a.provision === provision)?.title;
  return {
    id: `cq-${provision}`,
    provision,
    to: "applicant",
    text: q?.text ?? `Does your project do something differently from Article ${provision}${title ? ` (${title})` : ""}?`,
    why: q?.why ?? "You marked this article Not sure. Answer it here, or raise it with your Safety Codes Officer.",
  };
}

export type Action =
  | { type: "setDescription"; text: string }
  | { type: "addFiles"; names: string[] }
  | { type: "removeFile"; id: string }
  | { type: "confirmFact"; id: string }
  | { type: "dismissFact"; id: string }
  | { type: "setDetail"; field: string; value: string; section: string }
  | { type: "answerQuestion"; id: string; answer: string }
  | { type: "answerCandidate"; id: string; answer: CandidateAnswer }
  | { type: "setProcess"; field: ProcessFieldId; value: string }
  | { type: "setEngineCase"; id: string }
  | { type: "identified"; prose: string; result: IdentifyResult }
  | { type: "answerArticle"; provision: string; answer: CodeIdAnswer | null }
  | { type: "askOfficer"; ask: boolean }
  | { type: "codeIdConfirmed"; confirm: NonNullable<CodeIdRun["confirm"]> }
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
      return { ...c, description: a.text };
    case "addFiles":
      return { ...c, files: [...c.files, ...a.names.map((name) => ({ id: newId("file"), name, read: false }))] };
    case "removeFile":
      return { ...c, files: c.files.filter((f) => f.id !== a.id) };
    case "confirmFact":
      return { ...c, facts: c.facts.map((f) => (f.id === a.id ? { ...f, status: "confirmed" } : f)) };
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
    case "answerCandidate":
      return { ...c, candidates: c.candidates.map((x) => (x.id === a.id ? { ...x, answer: a.answer } : x)) };
    case "setProcess":
      return { ...c, process: { ...c.process, [a.field]: a.value } };
    case "setEngineCase":
      return { ...c, engineCaseId: a.id };
    case "identified": {
      // A new run keeps answers and questions for articles it returns again, and the officer question.
      const ids = new Set(a.result.articles.map((x) => x.provision));
      const prev = c.codeId;
      return {
        ...c,
        codeId: {
          prose: a.prose,
          result: a.result,
          answers: Object.fromEntries(Object.entries(prev?.answers ?? {}).filter(([k]) => ids.has(k))),
          questions: (prev?.questions ?? []).filter((q) => q.provision === null || ids.has(q.provision)),
        },
      };
    }
    case "answerArticle": {
      const run = c.codeId;
      if (!run) return c;
      const answers = { ...run.answers };
      if (a.answer) answers[a.provision] = a.answer;
      else delete answers[a.provision];
      const questions = run.questions.filter((q) => q.provision !== a.provision);
      if (a.answer === "not-sure") questions.push(notSureQuestion(run.result, a.provision));
      return { ...c, codeId: { ...run, answers, questions } };
    }
    case "askOfficer": {
      const run = c.codeId;
      if (!run) return c;
      const questions = run.questions.filter((q) => q.id !== OFFICER_QUESTION_ID);
      if (a.ask) {
        questions.push({
          id: OFFICER_QUESTION_ID,
          provision: null,
          to: "officer",
          text: "None of the suggested articles fit this project. Which requirement should it be measured against?",
          why: "Recorded for your Safety Codes Officer. You can continue; the application lists it as an open question.",
        });
      }
      return { ...c, codeId: { ...run, questions } };
    }
    case "codeIdConfirmed":
      return c.codeId ? { ...c, codeId: { ...c.codeId, confirm: a.confirm } } : c;
    case "reset":
      return a.to;
  }
}

export const candidateById = (c: Case, id: string): Candidate | undefined => c.candidates.find((x) => x.id === id);
