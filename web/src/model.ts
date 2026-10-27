import type { IntakeRecord, IntakeResult, IdentifyResult } from "./api/types.gen";
import { AUTHORITIES } from "./config";
import { AI_ACCEPTED_REF, applyDescription } from "./intake";
import { asLocal, confirmedAnswer, isWritingField, localField } from "./intakeFields";
import { codeQuestion, identifyCandidates, readGroups } from "./intakeView";
import { AUTHORITY_ONLY_FIELDS, professionalConfirmed } from "./professional";
import type { Candidate, CandidateAnswer, Case, EvidenceDraft, Fact, Gap, ListedEvidence, ProcessFieldId, SectionCRow } from "./types";
import { canonicalProvision, isProvision, keywordCandidate, reconcileSectionC } from "./provisions";
import { evidenceBinding } from "./evidence";

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
    options: { site: "One building site", jurisdiction: "Every site in the municipality (jurisdiction-wide)" },
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

/** What a missing Section A or B field means, in plain words. */
const DETAIL_GAP: Record<string, string> = {
  owner: "The owner’s name",
  representative: "Who signs for the applicant",
  mailingAddress: "A mailing address for the officer",
  date: "The date of the request",
  scope: "Whether this is for one site or every site (jurisdiction-wide)",
  municipalAddress: "The site’s street address",
  legalDescription: "The site’s legal description (lot, block and plan)",
  alternative: "What you want to do differently (the proposed alternative)",
};

/** Plain names for the applicant's case, with the form's term in brackets. */
export const PROCESS_PLAIN: Record<ProcessFieldId, string> = {
  rationale: "Why your design works (rationale)",
  risk: "What could go wrong (risk assessment)",
  mitigation: "What reduces the risk (mitigating measures)",
  assumptions: "When your case holds (assumptions and limits)",
  maintenance: "Upkeep after construction (maintenance and operation)",
  qualifications: "Who is responsible (qualifications)",
};

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
  storeys: "Storeys",
  building_area_m2: "Building area",
  floor_area_m2: "Floor area per storey",
  occupancy: "Use of the building",
  municipality: "Where the site is",
  limiting_distance_m: "Distance to the property line",
  sprinklered: "Sprinklers",
  dwelling_units: "Homes or suites",
  building_height_m: "Building height",
  top_floor_height_m: "Top floor height",
  span_m: "Structural span",
  part4_design: "Part 4 design",
  applicant_role: "Who is applying",
  claimed_provision: "Article you named",
  "assembly.description": "The assembly, layer by layer",
  "scope.redirect": "Which code this is",
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
  if (field.startsWith("statement.")) return "What we read";
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
  // Known fields belong to the browser draft, including an explicitly cleared answer.
  return localId ? process[localId].trim() : remote?.trim() || "";
}

/** The gap names the question the engine sent, when the message does not already include it. */
export function gapLabel(message: string, hint?: string | null): string {
  const question = hint?.trim();
  if (!question || message.includes(question)) return message;
  return `${message} ${question}`;
}

/** Newest fact for a field. Matches the engine, where the latest entry wins. */
export const factFor = (c: Case, field: string): Fact | undefined => {
  for (let i = c.facts.length - 1; i >= 0; i--) if (localField(c.facts[i].field) === localField(field)) return c.facts[i];
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
  if (text === "not_sure") return "Not sure";
  if (text === "not_engaged") return "Not engaged yet";
  if (text === "not_engaged_yet") return "Not engaged yet";
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
export function codeCheckLabel(topic: string, question?: string, provision?: string): string {
  // The article number stays behind "Show the code"; the rule's name says what it is about.
  if (provision && isProvision(provision)) return /^\d/.test(topic.trim()) ? `Answer whether your design differs from rule ${provision}` : codeQuestion(topic);
  const using = topic.match(/^using\s+(.+)$/i);
  if (using) {
    const rest = using[1].charAt(0).toLowerCase() + using[1].slice(1);
    return `Answer whether your design relies on ${rest}`;
  }
  if (/^what you described$/i.test(topic.trim()) && question?.trim()) return question.trim();
  const named = topic.charAt(0).toLowerCase() + topic.slice(1);
  return `Answer whether your design relies on ${named}`;
}

/** Words for the text record. The fact kind and status enums are not printed. */
export function plainFactStatus(kind: string, status: string): string {
  if (kind === "proposed") return "proposed, needs your check";
  if (status === "confirmed" && kind === "exact") return "from the form";
  if (status === "confirmed") return "from what you entered";
  return "needs your check";
}

/** Derived gap list: the only list any surface renders. */
/**
 * Starter questions whose answer is the description itself ("What is the product called, and what
 * does it do?", "What are you building…?"). Start asks that once; with a description they are
 * neither asked again in the deck nor listed as open.
 */
const ANSWERED_BY_DESCRIPTION: ReadonlySet<string> = new Set(["q-product", "q-job"]);

export function answeredByDescription(c: Pick<Case, "description">, questionId: string): boolean {
  return ANSWERED_BY_DESCRIPTION.has(questionId) && Boolean(c.description.trim());
}

/** A question about a field can reuse an explicit answer, never a candidate's technical uncertainty. */
export function questionAnsweredByFact(c: Case, q: Case["questions"][number]): boolean {
  return !q.cardId && q.kind !== "article" && !q.id.startsWith("q-from-")
    && q.field !== "project.description"
    && Boolean(confirmedAnswer(c.facts, q.field));
}

export function getGaps(c: Case): Gap[] {
  const gaps: Gap[] = [];
  const redirect = c.facts.find((f) => f.field === "scope.redirect" && f.status === "unconfirmed");
  if (redirect) {
    const regime = c.intake?.record.plan?.scope.regime?.name ?? String(redirect.value ?? "another regime");
    gaps.push({
      id: `confirm-${redirect.id}`,
      severity: "blocking",
      label: `This reads as a ${regime} question. Say whether it is a building-code question before export.`,
      href: "#/questions?focus=scope",
      field: "scope.redirect",
    });
  }
  if (!c.authority) {
    gaps.push({
      id: "detail-jurisdiction",
      severity: "blocking",
      label: "Who reviews your application (the reviewing authority) isn’t chosen yet",
      href: "#/describe?focus=authority",
    });
  }
  for (const d of DETAIL_FIELDS) {
    const fact = factFor(c, d.id);
    if (d.required && !valueText(fact).trim()) {
      gaps.push({ id: `detail-${d.id}`, severity: "blocking", label: DETAIL_GAP[d.id] ?? `${d.label} missing`, href: routeForDetail(d.id), field: d.id });
    }
  }
  // One gap per thing to check: a value with its unit conversion, or the same words read twice, is one card.
  for (const g of readGroups(c, DETAIL_IDS)) {
    if (g.done) continue;
    const f = g.fact;
    gaps.push({
      id: `confirm-${f.id}`,
      severity: "blocking",
      label: `Confirm ${factLabel(f.field).toLowerCase()}`,
      href: DETAIL_IDS.has(f.field) ? routeForDetail(f.field) : `#/describe?focus=fact-${f.id}`,
      field: f.field,
    });
  }
  for (const a of c.candidates) {
    if (a.id === "desc-storeys" && confirmedAnswer(c.facts, "storeys")) continue;
    const keywordLead = keywordCandidate(c, a) && a.answer !== "yes";
    if (!keywordLead && isProvision(a.provision) && !c.sectionC.some(r => canonicalProvision(r.provision) === canonicalProvision(a.provision))) {
      gaps.push({ id: `lookup-${a.id}`, severity: "blocking", label: `Rule ${a.provision} is still loading from the code`, href: "#/section-c", field: `candidate.${a.id}` });
    }
    if (a.answer === null && !keywordLead) {
      gaps.push({
        id: `answer-${a.id}`,
        severity: "blocking",
        label: codeCheckLabel(a.topic, a.clarifyingQuestion, a.provision),
        href: `#/code-check?focus=cand-${a.id}`,
        field: `candidate.${a.id}`,
      });
    }
  }
  if (c.candidates.some((a) => keywordCandidate(c, a) && a.answer === null)) {
    gaps.push({ id: "keyword-triage", severity: "warning", label: "Keyword matches are unconfirmed leads. Review them by topic, or choose a code reference yourself.", href: "#/questions?focus=code-triage", field: "identify.keyword_triage" });
  }
  for (const p of PROCESS_FIELDS) {
    if (!c.process[p.id].trim()) {
      gaps.push({
        id: `process-${p.id}`,
        severity: "blocking",
        label: `${PROCESS_PLAIN[p.id]} isn’t written yet`,
        href: `#/application?tab=alt&focus=field-${p.id}`,
        field: PROCESS_FACT[p.id],
      });
    }
  }
  for (const q of c.questions) {
    if (q.id.startsWith("q-prof-") || answeredByDescription(c, q.id) || questionAnsweredByFact(c, q)) continue;
    if (!q.answer) {
      const article = q.kind === "article" || q.id.startsWith("q-from-") || q.id.startsWith("oq_") || Boolean(q.cardId);
      const intake = q.kind === "intake" || q.id.startsWith("q-identify-");
      const scope = q.id.startsWith("q-scope-");
      const routed = article || intake || scope;
      const card = q.cardId || (q.id.startsWith("q-from-") ? q.id.slice("q-from-".length) : "");
      const uncertain = card ? c.candidates.find((a) => a.id === card && a.answer === "not-sure") : undefined;
      gaps.push({
        id: `question-${q.id}`,
        severity: "warning",
        label: uncertain ? `Open question for the officer: ${uncertain.topic}${isProvision(uncertain.provision) ? ` (${uncertain.provision})` : ""}. ${q.text}` : routed ? `Open question: ${q.text}` : `Open question: ${factLabel(q.field).toLowerCase()}`,
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
        "A registered professional is required and is not confirmed. Name the engineer or architect and their seal or registration number.",
      href: "#/application?tab=D&focus=prof-role",
      field: "professional.role",
    });
  }
  if (c.practiceOfEngineering === "unknown" && !professionalConfirmed(c.facts)) {
    gaps.push({
      id: "practice-unknown",
      severity: "blocking",
      label: "Routed to the officer: whether a registered professional is required. The draft PDF stays available; the official PDF waits for this.",
      href: "#/application?tab=D&focus=prof-role",
      field: "professional_requirement",
    });
  }
  if (c.questions.some((q) => q.id.startsWith("q-prof-") && !q.answer)) {
    gaps.push({
      id: "professional-not-engaged",
      severity: "blocking",
      label: c.practiceOfEngineering === true
        ? "The required professional is not confirmed. Not sure or Not engaged yet does not waive that duty."
        : "The professional requirement is for the officer to determine. Official export waits for that determination.",
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
  | { type: "adoptCase"; to: Case }
  | { type: "setDescription"; text: string }
  | { type: "addFiles"; files: { id: string; name: string }[] }
  | { type: "setFileResult"; id: string; error: string | null; read?: boolean; pages?: number; sha256?: string; unreachable?: boolean; engineId?: string }
  | { type: "removeFile"; id: string }
  | { type: "confirmFact"; id: string }
  | { type: "dismissFact"; id: string }
  /** One click on a "what we read" card: every fact of the group, confirmed or marked not right. */
  | { type: "confirmFacts"; ids: string[] }
  | { type: "rejectFacts"; ids: string[] }
  /** Derived: an intake run's facts (unconfirmed, renamed for the browser) and its record. */
  | { type: "noteIntake"; result: IntakeResult; text: string }
  /** Derived: a saved case reopened; its stored intake run without adding facts (the case has its latest). */
  | { type: "restoreIntake"; result: IntakeResult; text: string | null }
  /** Derived: officer requests change without an applicant fact edit. */
  | { type: "restoreReviewQuestions"; questions: Case["questions"] }
  /** Derived: a newer intake record (plan after an answer, an override or code identification). */
  | { type: "noteIntakeRecord"; record: IntakeRecord }
  /** Derived: facts the engine wrote on an intake route (answers, scope), adopted as saved. */
  | { type: "adoptFacts"; facts: Fact[]; drop?: string[] }
  /** Derived: one server-confirmed applicant draft answer, preserving all other local work. */
  | { type: "adoptApplicantDraft"; fact: Fact }
  /** Derived: the latest code identification; its committed articles and choices become code cards. */
  | { type: "noteIdentify"; result: IdentifyResult }
  | { type: "markDecisionPending"; id: string; pending: boolean }
  | { type: "setDetail"; field: string; value: string; section: string; origin?: "ai" }
  | { type: "answerQuestion"; id: string; answer: string }
  | { type: "setStoreyCount"; value: string }
  | { type: "answerCandidate"; id: string; answer: CandidateAnswer | null }
  | { type: "setProcess"; field: ProcessFieldId; value: string; origin?: "ai" }
  | { type: "setAuthority"; authority: Case["authority"] }
  /** The applicant's own name (already saved, or kept for when the case is created). */
  | { type: "renameCase"; title: string }
  | { type: "addCandidate"; candidate: Candidate }
  | {
      type: "addIdentified";
      articles: { provision: string; title: string | null; part: number; quote: string | null; reason: string | null }[];
    }
  | { type: "noteIdentifyQuestions"; questions: { id?: string; field: string; text: string; why?: string | null }[] }
  | { type: "bindOpenQuestion"; candidateId: string; questionId: string }
  | { type: "noteSectionC"; rows: SectionCRow[] }
  /** `basis` guards stale lookups; `preserve` keeps acknowledged cards unchanged by display lookup. */
  | { type: "reconcileSectionC"; rows: SectionCRow[]; basis?: string; preserve?: string[] }
  | { type: "noteUnscopedEvidence"; ids: string[] }
  | { type: "removeCandidate"; id: string }
  | { type: "editEvidenceDraft"; itemId: string; patch: Partial<EvidenceDraft> }
  /** `slot` edits that saved document; without it a new document is staged. */
  | { type: "saveEvidence"; itemId: string; document: string; responsible: string; date: string; evidenceType: string; provisionId: string; slot?: string; fileRef?: string | null }
  | { type: "removeEvidence"; id: string }
  /**
   * The engine's answer to evidence writes. `facts` replaces the browser's evidence mirror.
   * `refreshed` marks an explicit fresh read: a staged new listing already saved exactly as typed
   * is acknowledged by it; one whose ID is now taken by a different listing gets a new ID.
   */
  | { type: "ackEvidence"; acked?: { id: string; rev: number }[]; deleted?: string[]; rejected?: { id: string; rev?: number; reason: string }[]; facts?: Fact[] | null; refreshed?: boolean; error?: string | null }
  | { type: "deferProfessional"; field: string; choice: "not_sure" | "not_engaged_yet"; label: string }
  | { type: "setProfessionalFact"; field: string; value: string | number | boolean }
  /** A coded-rule input answered on its deck card (docs/api/rules.md): a confirmed fact, or null to clear it. */
  | { type: "setRuleInput"; field: string; value: number | boolean | string | null; rule: string; quote: string }
  | { type: "answerScope"; field: string; answer: "yes" | "no" | "not-sure" | "clear"; text?: string }
  | { type: "notePractice"; value: true | false | "unknown" }
  | { type: "reset"; to: Case };

/** Source ref of a "Not right" click on a fact intake read. */
export const NOT_RIGHT = "Not right, said the applicant";

/** The applicant's confirmation of a read value: a new pointed user_click fact (a proposed fact is never confirmed in place). */
function confirmedCopy(old: Fact): Fact {
  const quote = old.source.quote ?? (old.value == null ? "" : String(old.value));
  return {
    id: newId("f"), field: old.field, value: old.value, kind: "pointed", status: "confirmed",
    confidence: null, formula: null, inputs: [],
    source: { type: "user_click", ref: "Confirmed by applicant", quote },
  };
}

/** Saved answers to code-check cards read from the description: `codecheck.<card id>`. */
export const CODECHECK_PREFIX = "codecheck.";

let seq = 0;
const newId = (p: string) => `${p}-${Date.now().toString(36)}-${(seq++).toString(36)}`;

/** Replace any fact for `field` with one the applicant typed or clicked. */
function upsertUserFact(c: Case, field: string, value: string, source: Fact["source"]): Fact[] {
  const rest = c.facts.filter((f) => f.field !== field);
  if (!value.trim()) return rest;
  // The applicant's own typed words are the quote: the value is grounded in what they wrote.
  return [...rest, { id: newId("f"), field, value, kind: "pointed", source: { ...source, quote: value }, status: "confirmed" }];
}

/** The slot a ledger field belongs to, read the same way as the engine (`.covers.` first). */
export function evidenceSlot(field: string): string | null {
  if (!field.startsWith("evidence.")) return null;
  const name = field.slice("evidence.".length);
  if (name.includes(".covers.")) return name.split(".covers.")[0];
  const dot = name.lastIndexOf(".");
  return dot > 0 ? name.slice(0, dot) : null;
}

/** Slots the engine has acknowledged (the browser's evidence facts are its mirror). */
function savedSlots(c: Case): Set<string> {
  return new Set(c.facts.map((fact) => evidenceSlot(fact.field)).filter((slot): slot is string => !!slot));
}

/** The task id for the first document, then task~2, task~3… never reusing a known or removing slot. */
function nextSlot(c: Case, task: string): string {
  const taken = new Set([...savedSlots(c), ...(c.listedEvidence ?? []).map((item) => item.id), ...(c.deletedEvidence ?? [])]);
  if (!taken.has(task)) return task;
  let n = 2;
  while (taken.has(`${task}~${n}`)) n += 1;
  return `${task}~${n}`;
}

/** The text of a refused listing goes back to its task's form, so nothing typed is lost. */
function restoreDraft(c: Case, op: ListedEvidence, note: string, editing?: string): Case {
  const current = c.evidenceDrafts?.[op.taskId];
  if (current && (current.document.trim() || current.responsible.trim() || current.date.trim())) {
    return { ...c, evidenceIssues: { ...c.evidenceIssues, [op.id]: `${note} Not saved: ${op.description}` } };
  }
  const draft: EvidenceDraft = { document: op.description, evidenceType: op.evidenceType, responsible: op.responsible ?? "", date: op.date ?? "", fileRef: op.fileRef, note, step: 0, ...(editing ? { editing } : {}) };
  return { ...c, evidenceDrafts: { ...c.evidenceDrafts, [op.taskId]: draft } };
}

/** Same content, same object: an acknowledgement that changes nothing must not look like an edit. */
const same = (a: unknown, b: unknown) => a === b || JSON.stringify(a) === JSON.stringify(b);

/**
 * Every save acknowledges the stored evidence ledger. When it changes nothing the case keeps its
 * identity; new arrays with the same content re-armed the autosave effect and polled the engine.
 */
function ackEvidence(c: Case, a: Extract<Action, { type: "ackEvidence" }>): Case {
  const next = applyAck(c, a);
  const keep = <K extends "facts" | "listedEvidence" | "deletedEvidence" | "evidenceIssues" | "evidenceDrafts">(k: K) => (same(c[k], next[k]) ? c[k] : next[k]);
  const kept: Case = { ...next, facts: keep("facts"), listedEvidence: keep("listedEvidence"), deletedEvidence: keep("deletedEvidence"), evidenceIssues: keep("evidenceIssues"), evidenceDrafts: keep("evidenceDrafts") };
  return (Object.keys(kept) as (keyof Case)[]).every((k) => kept[k] === c[k]) && Object.keys(c).length === Object.keys(kept).length ? c : kept;
}

function applyAck(c: Case, a: Extract<Action, { type: "ackEvidence" }>): Case {
  let next: Case = c;
  if (a.facts) next = { ...next, facts: [...next.facts.filter((fact) => !fact.field.startsWith("evidence.")), ...a.facts] };
  let ops = [...(next.listedEvidence ?? [])];
  for (const ack of a.acked ?? []) {
    // A newer edit of the same document stays staged; once its slot exists it is an update.
    ops = ops.flatMap((op) => op.id !== ack.id ? [op] : op.rev === ack.rev ? [] : [{ ...op, operation: "update" as const }]);
  }
  let deleted = (next.deletedEvidence ?? []).filter((id) => !(a.deleted ?? []).includes(id));
  const issues = { ...next.evidenceIssues };
  for (const id of a.deleted ?? []) delete issues[id];
  next = { ...next, listedEvidence: ops, deletedEvidence: deleted, evidenceIssues: issues };
  for (const refused of a.rejected ?? []) {
    const op = (next.listedEvidence ?? []).find((item) => item.id === refused.id && item.rev === refused.rev);
    if (op) {
      next = { ...next, listedEvidence: (next.listedEvidence ?? []).filter((item) => item !== op) };
      next = restoreDraft(next, op, refused.reason, op.operation === "update" && savedSlots(next).has(op.id) ? op.id : undefined);
    } else if (refused.rev === undefined) {
      deleted = (next.deletedEvidence ?? []).filter((id) => id !== refused.id);
      next = { ...next, deletedEvidence: deleted, evidenceIssues: { ...next.evidenceIssues, [refused.id]: refused.reason } };
    }
  }
  if (a.refreshed) {
    const saved = savedSlots(next);
    const value = (slot: string, field: string) => {
      const found = factFor(next, `evidence.${slot}.${field}`)?.value;
      return typeof found === "string" ? found : undefined;
    };
    for (const op of [...(next.listedEvidence ?? [])]) {
      if (op.operation === "create" && saved.has(op.id)) {
        const same = value(op.id, "title") === op.description && value(op.id, "evidence_type") === op.evidenceType
          && (op.responsible == null || value(op.id, "responsible_party") === op.responsible)
          && (op.date == null || value(op.id, "date") === op.date)
          && (op.fileRef === undefined || (evidenceBinding(next.facts, op.id)?.fileId ?? null) === op.fileRef);
        const rest = (next.listedEvidence ?? []).filter((item) => item !== op);
        next = same ? { ...next, listedEvidence: rest }
          : { ...next, listedEvidence: [...rest, { ...op, id: nextSlot({ ...next, listedEvidence: rest }, op.taskId) }] };
      } else if (op.operation === "update" && !saved.has(op.id)) {
        next = { ...next, listedEvidence: (next.listedEvidence ?? []).filter((item) => item !== op) };
        next = restoreDraft(next, op, "This document was removed somewhere else. Your text is still here.");
      }
    }
  }
  return next;
}

export function reducer(c: Case, a: Action): Case {
  switch (a.type) {
    case "setDescription":
      return applyDescription(c, a.text);
    case "addFiles":
      return { ...c, files: [...c.files, ...a.files.map((f) => ({ id: f.id, name: f.name, read: false }))],
        intake: c.intake && a.files.length ? { ...c.intake, filesChanged: true } : c.intake };
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
                engineId: a.engineId ?? f.engineId,
                unreachable: a.error ? Boolean(a.unreachable) : false,
              }
            : f,
        ),
      };
    case "removeFile":
      return { ...c, files: c.files.filter((f) => f.id !== a.id),
        intake: c.intake && c.files.some((f) => f.id === a.id) ? { ...c.intake, filesChanged: true } : c.intake };
    case "confirmFact":
      return reducer(c, { type: "confirmFacts", ids: [a.id] });
    case "dismissFact":
      // A writing proposal is separate from the applicant's confirmed answer.
      if (c.facts.some(f => f.id === a.id && f.kind === "proposed" && isWritingField(f.field))) return { ...c, facts: c.facts.filter(f => f.id !== a.id) };
      return reducer(c, { type: "rejectFacts", ids: [a.id] });
    case "confirmFacts": {
      let next = c;
      for (const id of a.ids) {
        // A value intake read that was marked not right can still be confirmed from its card.
        const old = next.facts.find((f) => f.id === id) ?? next.intake?.facts.find((f) => f.id === id);
        if (!old) continue;
        next = { ...next, facts: next.facts.filter((f) => f.id !== old.id && !(f.field === old.field && f.source.ref === NOT_RIGHT)).concat(confirmedCopy(old)) };
        // The site's municipality is the reviewing authority when it is one Batatis knows.
        const authority = old.field === "municipality" ? AUTHORITIES.find((x) => x.name.toLowerCase() === String(old.value).trim().toLowerCase()) : undefined;
        if (authority && !next.authority) next = { ...next, authority: authority.id };
      }
      return next;
    }
    case "rejectFacts": {
      // "Not right" is the applicant's own click: recorded as a confirmed empty answer, so the field
      // is asked again and the engine never keeps the rejected reading as an open, unconfirmed value.
      const gone = c.facts.filter((f) => a.ids.includes(f.id));
      if (!gone.length) return c;
      const fields = [...new Set(gone.map((f) => f.field))];
      const rest = c.facts.filter((f) => !a.ids.includes(f.id));
      const marks: Fact[] = fields.map((field) => ({
        id: newId("f"), field, value: null, kind: "pointed", status: "confirmed", confidence: null, formula: null, inputs: [],
        source: { type: "user_click", ref: NOT_RIGHT, quote: "" },
      }));
      return { ...c, facts: [...rest, ...marks] };
    }
    case "noteIntake": {
      const previous = new Set(c.intake?.factIds ?? []);
      // A re-run replaces what the last run left unconfirmed (the engine does the same) and keeps every confirmed value.
      let facts = c.facts.filter((f) => !(previous.has(f.id) && f.status === "unconfirmed") && !(f.field === "scope.redirect" && f.kind === "computed"));
      for (const raw of a.result.facts) {
        if (raw.status !== "unconfirmed" || raw.field === "project.description") continue;
        const f = asLocal(raw) as Fact;
        if (facts.some((x) => x.id === f.id)) continue;
        // The same value already confirmed under the browser's name is not asked twice: it is confirmed again.
        const previousAnswer = confirmedAnswer(facts, f.field);
        const confirmedBefore = previousAnswer && String(previousAnswer.value).trim() === String(f.value ?? "").trim();
        facts = [...facts, confirmedBefore && f.field !== "scope.redirect" ? confirmedCopy(f) : f];
      }
      return { ...c, facts, intake: { text: a.text, record: a.result.record, factIds: a.result.facts.map((f) => f.id), facts: a.result.facts.map((f) => asLocal(f) as Fact) } };
    }
    case "restoreIntake":
      return { ...c, intake: { text: a.text, record: a.result.record, factIds: a.result.facts.map((f) => f.id), facts: a.result.facts.map((f) => asLocal(f) as Fact) } };
    case "restoreReviewQuestions": {
      const questions = [...c.questions.filter(q => !q.field.startsWith("clarification.")),
        ...a.questions.filter(q => q.field.startsWith("clarification."))];
      return JSON.stringify(questions) === JSON.stringify(c.questions) ? c : { ...c, questions };
    }
    case "noteIntakeRecord":
      return c.intake ? { ...c, intake: { ...c.intake, record: a.record } } : c;
    case "adoptFacts": {
      const drop = new Set([...(a.drop ?? []), ...a.facts.map((f) => f.id)]);
      return { ...c, facts: [...c.facts.filter((f) => !drop.has(f.id)), ...a.facts] };
    }
    case "adoptApplicantDraft": {
      const fact = asLocal(a.fact);
      const process = { ...c.process };
      for (const p of PROCESS_FIELDS) {
        if (PROCESS_FACT[p.id] === fact.field && typeof fact.value === "string") process[p.id] = fact.value;
      }
      return { ...c, process, facts: [...c.facts.filter(f => f.field !== fact.field), fact] };
    }
    case "noteIdentify": {
      const made = identifyCandidates(a.result, c.candidates);
      const articleOf = (p: string) => p.match(/^\d+\.\d+\.\d+\.\d+\./)?.[0] ?? p;
      // Articles the applicant said Yes to on an identify card. A saved reference to one of them (a reopened
      // case stores sentence ids such as 9.27.3.4.(1)) is the same card, not a second one.
      const decidedYes = new Set(made.filter((m) => m.answer === "yes").map((m) => articleOf(m.provision)));
      // The rest of the ranking stays in the code library.
      const rest = c.candidates.filter((x) => x.suggestion !== "identify" && !(x.id.startsWith("search-") && decidedYes.has(articleOf(x.provision))));
      const candidates = [...rest, ...made.filter((m) => !rest.some((x) => canonicalProvision(x.provision) === canonicalProvision(m.provision)))];
      return {
        ...c,
        identify: a.result,
        candidates,
        questions: c.questions.filter((q) => q.kind !== "intake" && (!q.cardId || candidates.some((x) => x.id === q.cardId))),
      };
    }
    case "markDecisionPending":
      return { ...c, candidates: c.candidates.map((x) => (x.id === a.id ? { ...x, pending: a.pending || undefined } : x)) };
    case "setDetail":
      return { ...c, facts: upsertUserFact(c, a.field, a.value, { type: "user_text", ref: a.origin === "ai" ? AI_ACCEPTED_REF : `${TYPED_REF} Section ${a.section}` }) };
    case "answerQuestion": {
      const q = c.questions.find((x) => x.id === a.id);
      if (!q) return c;
      return {
        ...c,
        questions: c.questions.map((x) => (x.id === a.id ? { ...x, answer: a.answer } : x)),
        facts: upsertUserFact(c, q.field, a.answer, { type: "user_text", ref: "Your answer", quote: a.answer }),
      };
    }
    case "setStoreyCount": {
      const value = a.value.trim();
      const known = value !== "" && Number.isInteger(Number(value)) && Number(value) > 0;
      const facts = c.facts.filter(f => localField(f.field) !== "storeys");
      if (known) facts.push({ id: newId("f"), field: "storeys", value: Number(value), kind: "pointed", status: "confirmed", source: { type: "user_text", ref: "Your storey count", quote: value } });
      const next = { ...c, facts, questions: c.questions.map(q => q.id === "q-desc-storeys" ? { ...q, answer: known ? value : undefined } : q) };
      return reducer(next, { type: "answerCandidate", id: "desc-storeys", answer: known ? "no" : "not-sure" });
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
      // A card read from the description has no provision the engine keeps, so its answer is
      // saved as a fact; reopening the application restores it (calm/openCase.ts).
      let facts = c.facts;
      if (cand && !isProvision(cand.provision)) {
        const field = `${CODECHECK_PREFIX}${a.id}`;
        facts = [
          ...c.facts.filter((f) => f.field !== field),
          ...(a.answer ? [{ id: newId("f"), field, value: a.answer, kind: "pointed" as const, status: "confirmed" as const, confidence: null, formula: null, inputs: [], source: { type: "user_click" as const, ref: "Your code check answer", quote: a.id === "desc-storeys" ? "How many storeys is the building?" : `Does your design ${cand.departure}?` } }] : []),
        ];
      }
      return { ...c, candidates, questions, facts };
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
          source: { type: "user_text", ref: a.origin === "ai" ? AI_ACCEPTED_REF : "Typed on the alternative path", quote: value },
        });
      }
      return { ...c, process: { ...c.process, [a.field]: value }, facts };
    }
    case "renameCase":
      return { ...c, title: a.title, titleKept: true };
    case "setAuthority":
      return { ...c, authority: a.authority };
    case "addCandidate": {
      const existing = c.candidates.find((x) => canonicalProvision(x.provision) === canonicalProvision(a.candidate.provision));
      // Choosing a keyword lead manually opens its ordinary decision card. Preserve its answer,
      // ids and lookup rows; selecting it in the library is still not a Yes.
      if (existing) return keywordCandidate(c, existing) && a.candidate.suggestion === "search"
        ? { ...c, candidates: c.candidates.map((x) => x === existing ? { ...x, suggestion: "search" as const } : x) }
        : c;
      return { ...c, candidates: [...c.candidates, a.candidate] };
    }
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
              ? { text: quote, citation: "Quoted from the code database.", source: "code" as const }
              : { text: article.reason || "No sentence was returned for this article.", citation: "No code sentence was returned.", source: "ranking" as const },
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
    case "removeCandidate":
      return { ...c, candidates: c.candidates.filter(x => x.id !== a.id), sectionC: c.sectionC.filter(r => r.candidateId !== a.id), questions: c.questions.filter(q => q.cardId !== a.id && q.id !== `q-from-${a.id}`) };
    case "reconcileSectionC":
      // Rows looked up for an older candidate list must not reorder or drop newer answers.
      if (a.basis !== undefined && a.basis !== lookupBasis(c)) return c;
      return reconcileSectionC(c, a.rows, a.preserve);
    case "noteUnscopedEvidence": {
      const next = [...new Set([...(c.unscopedEvidence ?? []), ...a.ids])];
      if (next.length === (c.unscopedEvidence ?? []).length) return c;
      // An "Added" receipt on that task's editor would imply a link that no longer exists.
      // Unfinished typed text in the editor is kept.
      const drafts = { ...c.evidenceDrafts };
      for (const id of a.ids) {
        const task = id.split("~")[0];
        if (drafts[task]?.note.startsWith("Added:")) drafts[task] = { ...drafts[task], note: "" };
      }
      return { ...c, unscopedEvidence: next, evidenceDrafts: drafts };
    }
    case "noteSectionC": {
      const rest = c.sectionC.filter(
        (row) => !a.rows.some((next) => next.candidateId === row.candidateId && next.provision === row.provision),
      );
      return { ...c, sectionC: [...rest, ...a.rows] };
    }
    case "editEvidenceDraft":
      return { ...c, evidenceDrafts: { ...c.evidenceDrafts, [a.itemId]: {
        document: "", responsible: "", date: "", evidenceType: "", note: "",
        ...c.evidenceDrafts?.[a.itemId], ...a.patch,
      } } };
    case "saveEvidence": {
      const description = a.document.trim();
      const evidenceType = a.evidenceType.trim();
      if (!description || !evidenceType) return c;
      const who = a.responsible.trim();
      const date = a.date.trim();
      const rev = (c.evidenceRev ?? 0) + 1;
      const staged = (c.listedEvidence ?? []).find((item) => item.id === a.slot);
      let op: ListedEvidence;
      if (a.slot && (staged || savedSlots(c).has(a.slot))) {
        const saved = (field: string) => {
          const value = factFor(c, `evidence.${a.slot}.${field}`)?.value;
          return typeof value === "string" ? value : "";
        };
        // Unchanged details are omitted (kept); a cleared saved value is withdrawn with null.
        const detail = (value: string, field: string) => value ? (value === saved(field) ? undefined : value) : saved(field) ? null : undefined;
        op = staged?.operation === "create"
          ? { ...staged, rev, description, evidenceType, responsible: who || undefined, date: date || undefined }
          : { id: a.slot, rev, operation: "update", taskId: a.itemId, provisionId: a.provisionId.trim(), description, evidenceType,
              responsible: detail(who, "responsible_party"), date: detail(date, "date") };
      } else {
        op = { id: nextSlot(c, a.itemId), rev, operation: "create", taskId: a.itemId, provisionId: a.provisionId.trim(),
          description, evidenceType, responsible: who || undefined, date: date || undefined };
      }
      if (a.fileRef !== undefined) op.fileRef = a.fileRef;
      const drafts = { ...c.evidenceDrafts };
      delete drafts[a.itemId];
      const issues = { ...c.evidenceIssues };
      delete issues[op.id];
      return {
        ...c,
        evidenceRev: rev,
        listedEvidence: [...(c.listedEvidence ?? []).filter((item) => item.id !== op.id), op],
        evidenceDrafts: drafts,
        evidenceIssues: issues,
      };
    }
    case "removeEvidence": {
      const id = a.id.trim();
      if (!id) return c;
      const drafts = Object.fromEntries(Object.entries(c.evidenceDrafts ?? {}).filter(([, d]) => d.editing !== id));
      return {
        ...c,
        // Shown as removing until the engine confirms; a listing never sent needs no request.
        listedEvidence: (c.listedEvidence ?? []).filter((item) => item.id !== id),
        deletedEvidence: [...new Set([...(c.deletedEvidence ?? []), id])],
        evidenceDrafts: drafts,
      };
    }
    case "ackEvidence":
      return ackEvidence(c, a);
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
        // This confirms the applicant's honest answer, never a role, credential or requirement.
        status: "confirmed",
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
        status: "confirmed" as const,
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
    case "notePractice":
      // An applicant answer, including one the engine reads as "no", must not store false.
      if (a.value === false) return c.practiceOfEngineering === true ? c : { ...c, practiceOfEngineering: "unknown" };
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
    case "setRuleInput": {
      const rest = c.facts.filter((f) => f.field !== a.field);
      if (a.value === null) return { ...c, facts: rest };
      const type = typeof a.value === "number" ? "user_text" : "user_click";
      return { ...c, facts: [...rest, { id: newId("f"), field: a.field, value: a.value, kind: "pointed", status: "confirmed", source: { type, ref: `rules:${a.rule}`, quote: a.quote } }] };
    }
    case "adoptCase":
    case "reset":
      return a.to;
  }
}

/** The candidate list a Section C lookup is computed for. */
export function lookupBasis(c: Case): string {
  return c.candidates.filter((a) => isProvision(a.provision)).map((a) => `${a.id}=${a.provision}`).join("|");
}

export const candidateById = (c: Case, id: string): Candidate | undefined => c.candidates.find((x) => x.id === id);

export type SectionDView = {
  phase: "idle" | "loading" | "live" | "error" | "unreachable";
  note: string;
  plan: unknown;
  issues: unknown;
  professional: unknown;
  fields: unknown[];
  issuesNote: string | null;
};

/** A refresh after facts are pushed keeps the screen the applicant is filling in. */
export function sectionDWhileRefreshing<T extends SectionDView>(previous: T): T {
  const hasData = previous.plan != null || previous.issues != null || previous.professional != null;
  return {
    ...previous,
    phase: "loading",
    note: hasData ? "Updating Section D…" : "Loading Section D…",
  };
}

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

/** Every listed document slot with a title, in entry order. */
function documentTitles(c: Case): Map<string, string> {
  const titles = new Map<string, string>();
  for (const fact of c.facts) {
    const match = /^evidence\.([^.]+)\.title$/.exec(fact.field);
    if (match && typeof fact.value === "string" && fact.value.trim()) titles.set(match[1], fact.value.trim());
  }
  return titles;
}

/** Document slots that belong to none of these acknowledged plan tasks. */
export function orphanedEvidence(c: Case, taskIds: Iterable<string>): string[] {
  const tasks = new Set(taskIds);
  return [...documentTitles(c).keys()].filter((slot) => !tasks.has(slot.split("~")[0]));
}

/** Documents kept after their reference was withdrawn. */
export function keptDocuments(c: Case): { id: string; title: string }[] {
  const kept = new Set(c.unscopedEvidence ?? []);
  return [...documentTitles(c)].filter(([id]) => kept.has(id)).map(([id, title]) => ({ id, title }));
}

export function evidenceDocuments(c: Case, itemId: string): { id: string; title: string }[] {
  const titles = new Map<string, string>();
  const kept = new Set(c.unscopedEvidence ?? []);
  for (const fact of c.facts) {
    const match = /^evidence\.([^.]+)\.title$/.exec(fact.field);
    if (!match) continue;
    const slot = match[1];
    if (kept.has(slot)) continue;
    if (slot !== itemId && !slot.startsWith(`${itemId}~`)) continue;
    if (typeof fact.value === "string" && fact.value.trim()) titles.set(slot, fact.value.trim());
  }
  return [...titles].map(([id, title]) => ({ id, title }));
}
