import { applyDescription } from "./intake";
import { AUTHORITY_ONLY_FIELDS, professionalConfirmed } from "./professional";
import type { Candidate, CandidateAnswer, Case, Fact, Gap, ProcessFieldId, SectionCRow } from "./types";

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

const PROFESSIONAL_LABELS: Record<string, string> = {
  role: "Registered professional",
  discipline: "Registered professional",
  registration_number: "Registration number",
  registration: "Registration number",
  seal: "Professional seal",
  occupancy: "Occupancy",
  principal_dwelling_units: "Principal dwelling units",
  storeys: "Storeys",
  building_area_m2: "Building area",
  part4_design: "Part 4 design",
  ahj_requires_professional: "Authority requires a professional",
  special_safety_concerns: "Size or complexity",
  roof_trusses: "Wood roof trusses",
  preserved_wood_foundation_part4: "Preserved wood foundation",
  prescriptive_route_confirmed: "Prescriptive route",
  professional_judgement_required: "Reserved professional judgement",
  professional_scope_resolved: "Professional requirements resolved",
  fire_suppression: "Fire suppression",
  fire_alarm: "Fire alarm",
  farm_public_use: "Farm building for public use",
};

const EVIDENCE_LABELS: Record<string, string> = {
  file_ref: "Evidence document",
  title: "Evidence document",
  responsible_party: "Person responsible for the evidence",
  date: "Evidence date",
  professional_seal: "Seal on the evidence",
};

const OCCUPANCY_LABELS: Record<string, string> = {
  single_family: "Single-family house",
  multi_family: "Multi-family",
  hotel: "Hotel",
  assembly: "Assembly",
  care: "Care",
  treatment: "Treatment",
  detention: "Detention",
  business: "Business",
  mercantile: "Mercantile",
  industrial: "Industrial",
  farm: "Farm",
  relocatable_industrial_camp: "Relocatable industrial camp",
  mixed: "Mixed use",
  other: "Other",
};

function humanize(field: string): string {
  const last = field.split(".").pop() ?? field;
  const words = last.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** A label a person can read. A raw field key is never returned. */
export function factLabel(field: string): string {
  if (FACT_LABELS[field]) return FACT_LABELS[field];
  if (field.startsWith("evidence.")) return EVIDENCE_LABELS[field.split(".").pop() ?? ""] ?? "Evidence document";
  if (field.startsWith("professional.")) return PROFESSIONAL_LABELS[field.slice("professional.".length)] ?? humanize(field);
  if (field.startsWith("process.")) return humanize(field.slice("process.".length));
  if (field.includes(".") || field.includes("_")) return humanize(field);
  return field;
}

const ENGINE_PROCESS: Record<string, ProcessFieldId> = {
  rationale: "rationale",
  risk_assessment: "risk",
  risk: "risk",
  mitigating_measures: "mitigation",
  mitigation: "mitigation",
  assumptions_and_limits: "assumptions",
  assumptions: "assumptions",
  maintenance_operation: "maintenance",
  qualifications: "qualifications",
};

/** What Section D shows for a process answer. A value just typed wins over a stale engine copy. */
export function shownProcessAnswer(engineId: string, remote: string | null | undefined, process: Case["process"]): string {
  const localId = ENGINE_PROCESS[engineId];
  const local = localId ? process[localId].trim() : "";
  return local || remote?.trim() || "";
}

/** The gap names the question the engine sent, when the message does not already include it. */
export function gapLabel(message: string, hint?: string | null): string {
  const question = hint?.trim();
  if (!question || message.includes(question)) return message;
  return `${message} ${question}`;
}

/** Newest fact for a field. Matches the engine, where the latest entry wins. */
export const factFor = (c: Case, field: string): Fact | undefined => {
  for (let i = c.facts.length - 1; i >= 0; i--) if (c.facts[i].field === field) return c.facts[i];
  return undefined;
};

/** A fact's value as text. Engine values may be numbers or booleans; null reads as empty. */
export const valueText = (f: Fact | undefined): string => (f?.value == null ? "" : String(f.value));

/** The displayed value of a fact (select-backed fields show their option label). */
export function displayValue(f: Fact): string {
  if (typeof f.value === "boolean") return f.value ? "Yes" : "No";
  const def = DETAIL_FIELDS.find((d) => d.id === f.field);
  const text = valueText(f);
  if (f.field === "professional.occupancy" || f.field.endsWith(".occupancy")) return OCCUPANCY_LABELS[text] ?? text;
  if (text === "true") return "Yes";
  if (text === "false") return "No";
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

/** Unanswered code-check cards name the question. They do not say "Answer: what you described". */
export function codeCheckLabel(topic: string, question?: string): string {
  const using = topic.match(/^using\s+(.+)$/i);
  if (using) {
    const rest = using[1].charAt(0).toLowerCase() + using[1].slice(1);
    return `Code check: answer whether your design relies on ${rest}`;
  }
  if (/^what you described$/i.test(topic.trim()) && question?.trim()) return `Code check: ${question.trim()}`;
  const named = topic.charAt(0).toLowerCase() + topic.slice(1);
  return `Code check: answer whether your design relies on ${named}`;
}

/** Words for the text record. The fact kind and status enums are not printed. */
export function plainFactStatus(kind: string, status: string): string {
  if (kind === "proposed") return "proposed, needs your check";
  if (status === "confirmed" && kind === "exact") return "from the form";
  if (status === "confirmed") return "from what you entered";
  return "needs your check";
}

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
      gaps.push({ id: `detail-${d.id}`, severity: "blocking", label: `${d.label} missing`, href: routeForDetail(d.id), field: d.id });
    }
  }
  for (const f of c.facts) {
    if (f.status !== "unconfirmed") continue;
      gaps.push({
      id: `confirm-${f.id}`,
      severity: "blocking",
      label: `Confirm ${factLabel(f.field).toLowerCase()}`,
      href: DETAIL_IDS.has(f.field) ? routeForDetail(f.field) : `#/describe?focus=fact-${f.id}`,
      field: f.field,
    });
  }
  for (const a of c.candidates) {
    if (a.answer === null) {
      gaps.push({
        id: `answer-${a.id}`,
        severity: "blocking",
        label: codeCheckLabel(a.topic, a.clarifyingQuestion),
        href: `#/code-check?focus=cand-${a.id}`,
        field: `candidate.${a.id}`,
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
        field: PROCESS_FACT[p.id],
      });
    }
  }
  for (const q of c.questions) {
    if (q.id.startsWith("q-prof-")) continue;
    if (!q.answer) {
      const article = q.kind === "article" || q.id.startsWith("q-from-") || q.id.startsWith("oq_") || Boolean(q.cardId);
      const intake = q.kind === "intake" || q.id.startsWith("q-identify-");
      const scope = q.id.startsWith("q-scope-");
      const routed = article || intake || scope;
      const card = q.cardId || (q.id.startsWith("q-from-") ? q.id.slice("q-from-".length) : "");
      gaps.push({
        id: `question-${q.id}`,
        severity: "warning",
        label: routed ? `Open question: ${q.text}` : `Open question: ${factLabel(q.field).toLowerCase()}`,
        href: card
          ? `#/code-check?focus=cand-${card}`
          : scope
            ? "#/application?tab=D"
            : `#/describe?focus=q-${q.id}`,
        field: q.field,
      });
    }
  }
  if (c.practiceOfEngineering === true && !professionalConfirmed(c.facts)) {
    gaps.push({
      id: "needs-professional",
      severity: "blocking",
      label:
        "Registered professional not confirmed. Routed to the officer. Name an engineer or architect and their seal or registration number.",
      href: "#/application?tab=D&focus=prof-role",
      field: "professional.role",
    });
  }
  if (c.questions.some((q) => q.id.startsWith("q-prof-") && !q.answer)) {
    gaps.push({
      id: "professional-not-engaged",
      severity: "blocking",
      label: "Registered professional not confirmed. Not sure and not engaged yet are routed to the officer. Official export stays blocked.",
      href: "#/application?tab=D&focus=prof-role",
      field: "professional.role",
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
      articles: { provision: string; title: string | null; part: number; quote: string | null; reason: string | null }[];
    }
  | { type: "noteIdentifyQuestions"; questions: { id?: string; field: string; text: string; why?: string | null }[] }
  | { type: "bindOpenQuestion"; candidateId: string; questionId: string }
  | { type: "noteSectionC"; rows: SectionCRow[] }
  | { type: "saveEvidence"; itemId: string; document: string; responsible: string; date: string; evidenceType: string; provisionId: string }
  | { type: "removeEvidence"; id: string }
  | { type: "ackEvidenceDeletion"; ids: string[] }
  | { type: "deferProfessional"; field: string; choice: "not_sure" | "not_engaged_yet"; label: string }
  | { type: "setProfessionalFact"; field: string; value: string | number | boolean }
  | { type: "answerScope"; field: string; answer: "yes" | "no" | "not-sure" | "clear"; text?: string }
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
      const candidates = c.candidates.map((x) =>
        x.id === a.id ? { ...x, answer: a.answer, benchmark: a.answer === "yes" } : x,
      );
      const qid = `q-from-${a.id}`;
      let questions = c.questions.filter((q) => q.id !== qid && q.cardId !== a.id);
      if (a.answer === "not-sure" && cand) {
        questions = [
          ...questions,
          {
            id: qid,
            kind: "article",
            cardId: a.id,
            text: cand.clarifyingQuestion,
            why: `You answered Not sure on “${cand.topic}”. This stays an open question for the officer.`,
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
            benchmark: prev?.answer === "yes",
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
    case "noteIdentifyQuestions": {
      const rest = c.questions.filter((q) => q.kind !== "intake" && !q.id.startsWith("q-identify-"));
      const made = a.questions
        .filter((q) => q.field.trim() && q.text.trim())
        .map((q) => ({
          id: q.id?.trim() || `q-identify-${q.field.trim()}`,
          kind: "intake" as const,
          text: q.text.trim(),
          why: q.why?.trim() || "Article ranking left this open. It does not assume a value.",
          field: q.field.trim(),
        }));
      return { ...c, questions: [...rest, ...made] };
    }
    case "bindOpenQuestion": {
      const local = `q-from-${a.candidateId}`;
      if (!a.questionId.trim() || a.questionId === local) return c;
      return {
        ...c,
        questions: c.questions.map((q) =>
          q.id === local || q.cardId === a.candidateId ? { ...q, id: a.questionId, kind: "article" as const, cardId: a.candidateId } : q,
        ),
      };
    }
    case "noteSectionC": {
      const rest = c.sectionC.filter(
        (row) => !a.rows.some((next) => next.candidateId === row.candidateId && next.provision === row.provision),
      );
      return { ...c, sectionC: [...rest, ...a.rows] };
    }
    case "saveEvidence": {
      const description = a.document.trim();
      const who = a.responsible.trim();
      const date = a.date.trim();
      const evidenceType = a.evidenceType.trim();
      if (!description || !who || !evidenceType) return c;
      const taken = new Set(c.facts.filter((f) => f.field.startsWith("evidence.")).map((f) => f.field.split(".")[1]));
      let slot = a.itemId;
      if (taken.has(a.itemId)) {
        let n = 2;
        while (taken.has(`${a.itemId}~${n}`)) n += 1;
        slot = `${a.itemId}~${n}`;
      }
      const prefix = `evidence.${slot}.`;
      const text = (field: string, value: string): Fact => ({
        id: newId("f"),
        field,
        value,
        kind: "pointed",
        status: "confirmed",
        confidence: null,
        formula: null,
        inputs: [],
        source: { type: "user_text", ref: "Your evidence", quote: value },
      });
      const facts = [
        ...c.facts,
        text(`${prefix}description`, description),
        text(`${prefix}title`, description),
        text(`${prefix}responsible_party`, who),
        text(`${prefix}evidence_type`, evidenceType),
      ];
      if (date) facts.push(text(`${prefix}date`, date));
      const listed = [
        ...(c.listedEvidence ?? []),
        {
          id: slot,
          provisionId: a.provisionId.trim(),
          evidenceType,
          description,
          responsible: who,
          date,
        },
      ];
      return { ...c, facts, listedEvidence: listed };
    }
    case "removeEvidence": {
      const id = a.id.trim();
      if (!id) return c;
      const prefix = `evidence.${id}.`;
      return {
        ...c,
        facts: c.facts.filter((fact) => !fact.field.startsWith(prefix)),
        listedEvidence: (c.listedEvidence ?? []).filter((item) => item.id !== id),
        deletedEvidence: [...new Set([...(c.deletedEvidence ?? []), id])],
      };
    }
    case "deferProfessional": {
      const field = `professional.${a.field}`;
      const facts = c.facts.filter((f) => f.field !== field);
      const qid = `q-prof-${a.field}`;
      const why =
        a.choice === "not_sure"
          ? "You answered Not sure. This is routed to the officer. Official export stays blocked."
          : "You answered Not engaged yet. This is routed to the officer. Official export stays blocked.";
      facts.push({
        id: newId("f"),
        field,
        value: a.choice,
        kind: "pointed",
        status: "unconfirmed",
        confidence: null,
        formula: null,
        inputs: [],
        source: { type: "user_click", ref: "Your answer", quote: a.choice },
      });
      return {
        ...c,
        facts,
        questions: [...c.questions.filter((q) => q.id !== qid), { id: qid, text: a.label, why, field }],
      };
    }
    case "answerScope": {
      const qid = `q-scope-${a.field}`;
      const text =
        a.text?.trim() ||
        (a.field === "prescriptive_route_confirmed"
          ? "Is the design following the prescriptive route?"
          : a.field === "professional_judgement_required"
            ? "Does any proposed analysis require reserved professional judgement?"
            : "This question is still open.");
      const questions = c.questions.filter((q) => q.id !== qid && q.id !== `q-prof-${a.field}`);
      const facts = c.facts.filter((f) => f.field !== `professional.${a.field}`);
      if (a.answer === "clear") return { ...c, facts, questions };
      if (a.answer === "not-sure") {
        return {
          ...c,
          facts,
          questions: [
            ...questions,
            {
              id: qid,
              text,
              why: "You answered Not sure. This stays an open question for the officer. It does not decide whether a registered professional is required.",
              field: `professional.${a.field}`,
            },
          ],
        };
      }
      const quote = a.answer;
      const answered = {
        id: newId("f"),
        field: `professional.${a.field}`,
        value: a.answer === "yes",
        kind: "pointed" as const,
        status: "unconfirmed" as const,
        source: { type: "user_click" as const, ref: "Your answer", quote },
      };
      const authorityOnly = a.answer === "yes" && (AUTHORITY_ONLY_FIELDS as readonly string[]).includes(a.field);
      return {
        ...c,
        facts: [...facts, answered],
        questions: authorityOnly
          ? [
              ...questions,
              {
                id: `q-prof-${a.field}`,
                text,
                why: "An authority requirement does not name a registered professional. This is routed to the officer.",
                field: `professional.${a.field}`,
              },
            ]
          : questions,
      };
    }
    case "ackEvidenceDeletion": {
      const gone = new Set(a.ids);
      return { ...c, deletedEvidence: (c.deletedEvidence ?? []).filter((id) => !gone.has(id)) };
    }
    case "notePractice":
      return { ...c, practiceOfEngineering: a.value };
    case "setProfessionalFact": {
      const field = `professional.${a.field}`;
      const quote = typeof a.value === "boolean" ? (a.value ? "yes" : "no") : String(a.value);
      return {
        ...c,
        questions: c.questions.filter((q) => q.id !== `q-prof-${a.field}`),
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

/** Changes when a Section D answer, evidence item, or withdrawal is saved. */
export function sectionDRefreshKey(c: Case): string {
  const facts = c.facts
    .filter((fact) => fact.field.startsWith("professional.") || fact.field.startsWith("evidence."))
    .map((fact) => `${fact.field}:${String(fact.value)}:${fact.status ?? ""}`)
    .join("|");
  const listed = (c.listedEvidence ?? []).map((item) => `${item.id}:${item.description}`).join("|");
  const removed = (c.deletedEvidence ?? []).join("|");
  const questions = c.questions
    .filter((question) => question.id.startsWith("q-prof-") || question.id.startsWith("q-scope-"))
    .map((question) => `${question.id}:${question.answer ?? ""}`)
    .join("|");
  return `${facts}#${listed}#${removed}#${questions}`;
}

export function evidenceDocuments(c: Case, itemId: string): { id: string; title: string }[] {
  const titles = new Map<string, string>();
  for (const fact of c.facts) {
    const match = /^evidence\.([^.]+)\.title$/.exec(fact.field);
    if (!match) continue;
    const slot = match[1];
    if (slot !== itemId && !slot.startsWith(`${itemId}~`)) continue;
    if (typeof fact.value === "string" && fact.value.trim()) titles.set(slot, fact.value.trim());
  }
  return [...titles].map(([id, title]) => ({ id, title }));
}
