/**
 * What intake read and what code identification offers, in plain words for the question deck.
 * Pure: everything is derived from `Case.facts`, `Case.intake` (docs/api/intake.md) and
 * `Case.identify` (docs/api/identify.md). Nothing here confirms a fact or invents an article.
 */
import type { FileReport, Fork, IdentifyResult, Question as PlanQuestion } from "./api/types.gen";
import { confirmedAnswer, localField } from "./intakeFields";
import type { Candidate, CandidateAnswer, Case, Fact } from "./types";
import { metricUnit, parseMeasurement } from "./calm/units";

/* —— Values in words —— */

const OCCUPANCY: Record<string, string> = {
  single_family: "a single-family house",
  multi_family: "apartments or other multi-unit housing",
  hotel: "a hotel or motel",
  assembly: "a place people gather (assembly)",
  care: "a care home",
  treatment: "a treatment facility",
  detention: "a detention facility",
  business: "an office or other business",
  mercantile: "a store",
  industrial: "an industrial building",
  farm: "a farm building",
  relocatable_industrial_camp: "a relocatable industrial camp",
  mixed: "mixed uses",
};

const ROLE: Record<string, string> = {
  owner: "the owner",
  designer: "a designer",
  "architect-engineer": "an architect or engineer",
  contractor: "a contractor",
  homebuilder: "a homebuilder",
  manufacturer: "a manufacturer",
};

const SPRINKLERED: Record<string, string> = { yes: "sprinklered", no: "not sprinklered", partial: "partly sprinklered" };

function unit(field: string): string {
  if (field.endsWith("_m2")) return " m²";
  if (field.endsWith("_ft2")) return " sq ft";
  if (field.endsWith("_mm")) return " mm";
  if (field.endsWith("_ft")) return " ft";
  if (field.endsWith("_m")) return " m";
  return "";
}

/** A fact's value as a person would say it ("2 storeys", "210 m²", "a single-family house"). */
export function spokenValue(field: string, value: Fact["value"]): string {
  if (value == null || value === "") return "";
  if (field === "storeys") return `${value} ${Number(value) === 1 ? "storey" : "storeys"}`;
  if (field === "dwelling_units") return `${value} ${Number(value) === 1 ? "home" : "homes"}`;
  if (field === "occupancy") return OCCUPANCY[String(value)] ?? String(value);
  if (field === "applicant_role") return ROLE[String(value)] ?? String(value);
  if (field === "sprinklered") return SPRINKLERED[String(value)] ?? String(value);
  if (field === "scope") return value === "jurisdiction" ? "the whole jurisdiction" : value === "site" ? "one site" : String(value);
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value === "number") return `${Number.isInteger(value) ? value : Number(value.toFixed(2))}${unit(field)}`;
  return String(value);
}

const READ_QUESTION: Record<string, string> = {
  storeys: "How many storeys is the building?",
  building_area_m2: "What is the building area?",
  floor_area_m2: "What is the floor area of each storey?",
  occupancy: "What is the building used for?",
  municipality: "Where is the site?",
  limiting_distance_m: "How far is the wall from the property line?",
  sprinklered: "Is the building sprinklered?",
  dwelling_units: "How many homes or suites are in the building?",
  building_height_m: "How tall is the building?",
  top_floor_height_m: "How high is the top floor above the ground?",
  span_m: "What is the structural span?",
  part4_design: "Is the structure designed by an engineer under Part 4?",
  applicant_role: "Who is applying?",
  scope: "Is this for one building site, or for every site in the municipality?",
  claimed_provision: "Is this the code article you mean?",
  owner: "Owner",
  representative: "Representative",
  mailingAddress: "Mailing address",
  municipalAddress: "Site address",
  legalDescription: "Legal description",
  permit: "Permit number",
  date: "Request date",
  alternative: "Is this what you want to do differently?",
  lot: "What is the lot number?",
  block: "What is the block number?",
  plan: "What is the plan number?",
};

/** Long answers are confirmed as a whole ("Yes, that’s it"), not repeated on the button. */
const LONG = (field: string) => field === "alternative" || field.startsWith("statement.") || field === "assembly.description";

/* —— What we read —— */

export interface ReadGroup {
  /** Deck key: `field-<id>` for a Section A or B field, otherwise `fact-<id>` of the shown fact. */
  key: string;
  /** The fact the card shows (a computed value wins over the value as written). */
  fact: Fact;
  /** Every fact one click confirms or rejects: the shown one, its inputs, and the same words read twice. */
  ids: string[];
  /** Answered: none of its facts is still waiting for a click. */
  done: boolean;
}

const pointerFor = (c: Case, id: string) => c.intake?.record.pointers.find((p) => p.fact_id === id);

/**
 * One card per thing to check: facts intake read (the latest run, answered or not) and any other
 * unconfirmed proposal on the case. A computed value takes its input with it; the model's statement
 * of the same words as a rules fact joins that fact.
 */
export function readGroups(c: Case, detailIds: ReadonlySet<string>, includeConfirmed = false): ReadGroup[] {
  const waiting = new Set(c.facts.filter((f) => f.status === "unconfirmed").map((f) => f.id));
  const own = (f: Fact) => f.field !== "scope.redirect" && f.field !== "project.description" && f.field !== "applicant_role";
  const fromRun = (c.intake?.facts ?? []).filter((f) => own(f) && (includeConfirmed || f.status === "unconfirmed"));
  const runIds = new Set(fromRun.map((f) => f.id));
  const all = [...fromRun, ...c.facts.filter((f) => waiting.has(f.id) && !runIds.has(f.id) && own(f))];
  const used = new Set<string>();
  const groups: Omit<ReadGroup, "key" | "done">[] = [];
  for (const f of all) {
    if (f.kind !== "computed") continue;
    const inputs = (f.inputs ?? []).filter((id) => all.some((x) => x.id === id));
    groups.push({ fact: f, ids: [f.id, ...inputs] });
    for (const id of [f.id, ...inputs]) used.add(id);
  }
  const same = (a: Fact, b: Fact) => [b.value, b.source.quote].includes(a.value as string);
  for (const f of all) {
    if (used.has(f.id)) continue;
    used.add(f.id);
    const twin = f.field.startsWith("statement.") ? groups.find((g) => same(f, g.fact)) : undefined;
    if (twin) twin.ids.push(f.id);
    else groups.push({ fact: f, ids: [f.id] });
  }
  // A statement read before its rules twin still joins it.
  for (const g of [...groups]) {
    if (!g.fact.field.startsWith("statement.")) continue;
    const twin = groups.find((x) => x !== g && !x.fact.field.startsWith("statement.") && same(g.fact, x.fact));
    if (twin) {
      twin.ids.push(...g.ids);
      groups.splice(groups.indexOf(g), 1);
    }
  }
  const order = (g: { fact: Fact }) => pointerFor(c, g.fact.id)?.start ?? Number.MAX_SAFE_INTEGER;
  return groups
    .map((g) => ({ ...g, key: detailIds.has(g.fact.field) ? `field-${g.fact.field}` : `fact-${g.fact.id}`, done: !g.ids.some((id) => waiting.has(id)) }))
    .sort((a, b) => order(a) - order(b));
}

export interface Sureness {
  tone: "done" | "warning" | "pending";
  text: string;
}

/** How sure we are: read from the applicant's words, copied from a form, worked out, or a guess. */
export function sureness(c: Case, f: Fact): Sureness {
  if (f.kind === "proposed" || pointerFor(c, f.id)?.verified === false) return { tone: "warning", text: "A guess from your words. Check it." };
  if (f.kind === "computed") return { tone: "pending", text: f.formula ? `Worked out from your words: ${f.formula}` : "Worked out from your words." };
  if (f.kind === "exact") return { tone: "done", text: "Copied from the form." };
  return { tone: "done", text: "Read from your words." };
}

/** Where a fact came from: the description, a PDF and page, or a form field. */
export function sourceLine(c: Case, f: Fact): string {
  const s = f.source;
  if (s.type === "file") {
    const name = c.intake?.record.files.find((r) => r.file_id === s.ref)?.name ?? c.files.find((x) => x.engineId === s.ref)?.name ?? "your PDF";
    const page = s.page ? `, page ${s.page}` : "";
    return f.kind === "exact" && s.bbox ? `A form field in ${name}${page}` : `${name}${page}`;
  }
  if (s.ref === "intake answer") return "Your answer";
  return "Your description";
}

export interface Snippet {
  before: string;
  mark: string;
  after: string;
}

const isEnd = (t: string, i: number) => t[i] === "\n" || (/[.!?]/.test(t[i]) && (i + 1 >= t.length || /\s/.test(t[i + 1])));

/** The applicant's sentence around the words a fact points at, with those words marked. */
export function snippet(text: string, start: number | null | undefined, end: number | null | undefined): Snippet | null {
  if (start == null || end == null || start < 0 || end > text.length || end <= start) return null;
  let a = start;
  while (a > 0 && !isEnd(text, a - 1)) a--;
  let b = end;
  while (b < text.length && !isEnd(text, b)) b++;
  if (b < text.length && text[b] !== "\n") b++;
  let before = text.slice(a, start).replace(/^\s+/, "");
  let after = text.slice(end, b).replace(/\s+$/, "");
  if (before.length > 90) before = `…${before.slice(-88).replace(/^\S*\s/, "")}`;
  if (after.length > 90) after = `${after.slice(0, 88).replace(/\s\S*$/, "")}…`;
  return { before, mark: text.slice(start, end), after };
}

export interface ReadCopy {
  title: string;
  value: string;
  confirm: string;
  dismiss: string;
  source: string;
  sure: Sureness;
  /** The applicant's own words with the span marked; null for a form field or a lost pointer. */
  words: Snippet | null;
  /** The quote when there is no span to mark (a file, a form field). */
  quote: string;
}

const clip = (t: string, n: number) => (t.length > n ? `${t.slice(0, n - 1).trimEnd()}…` : t);

export function readCopy(c: Case, g: ReadGroup): ReadCopy {
  const f = g.fact;
  const value = spokenValue(f.field, f.value);
  const pointer = pointerFor(c, f.id) ?? g.ids.map((id) => pointerFor(c, id)).find(Boolean);
  const words = pointer?.source_ref === "description" && c.intake?.text ? snippet(c.intake.text, pointer.start, pointer.end) : null;
  const long = LONG(f.field);
  const title = f.field.startsWith("statement.") ? "Did we read this right?" : READ_QUESTION[f.field] ?? `What is the ${f.field.replace(/[._]/g, " ").replace(/\bm2\b/, "area")}?`;
  return {
    title,
    value,
    confirm: long ? (f.field === "alternative" ? "Yes, that’s what I want to do" : "Yes, that’s right") : `Yes, ${clip(value, 46)}`,
    dismiss: long ? "No, not quite" : "No, something else",
    source: sourceLine(c, f),
    sure: sureness(c, f),
    words,
    quote: (f.source.quote ?? "").trim(),
  };
}

/** Files intake could not read in full, with the engine's reason. */
export function fileNotes(c: Case): FileReport[] {
  return (c.intake?.record.files ?? []).filter((f) => f.status !== "read");
}

/* —— The plan: at most five questions —— */

export interface PlanInput {
  kind: "choices" | "number" | "text" | "area";
  choices?: { value: string; label: string }[];
  unit?: string;
}

/** How a planner question is answered: choices for yes/no and enums, a number, or words. */
export function planInput(field: string): PlanInput {
  if (field === "faces_public_way") return { kind: "choices", choices: [
    { value: "neighbour", label: "Neighbour’s lot" }, { value: "lane", label: "A lane" }, { value: "street", label: "A street" },
  ] };
  if (field === "product_scope") return { kind: "choices", choices: [{ value: "site", label: "One building or site" }, { value: "product_acceptance", label: "Across Alberta" }] };
  if (field === "sprinklered") return { kind: "choices", choices: [{ value: "yes", label: "Yes" }, { value: "no", label: "No" }, { value: "partial", label: "Partly" }] };
  if (field === "part4_design") return { kind: "choices", choices: [{ value: "yes", label: "Yes" }, { value: "no", label: "No" }] };
  if (field === "scope") return { kind: "choices", choices: [{ value: "site", label: "One building or site" }, { value: "jurisdiction", label: "Many sites, or across Alberta" }] };
  if (field === "storeys" || field === "dwelling_units") return { kind: "number" };
  if (/_m2$/.test(field)) return { kind: "number", unit: "m²" };
  if (/_m$/.test(field)) return { kind: "number", unit: "m" };
  if (/_mm$/.test(field)) return { kind: "number", unit: "mm" };
  if (field === "assembly.description" || field === "alternative_description") return { kind: "area" };
  return { kind: "text" };
}

/** Typed controls write a single canonical fact, preserving the complete entry as its quote. */
export function planFactAnswer(field: string, raw: string): { value: number | boolean; quote: string } | { error: string } | null {
  if (field === "faces_public_way") {
    const choice = planInput(field).choices?.find((choice) => choice.value === raw);
    return choice ? { value: raw !== "neighbour", quote: choice.label } : null;
  }
  const unit = metricUnit(planInput(field).unit);
  if (!unit) return null;
  const parsed = parseMeasurement(raw, unit);
  return parsed.kind === "value" ? { value: parsed.value, quote: parsed.quote }
    : { error: parsed.kind === "error" ? parsed.error : "Enter a measurement." };
}

export const NOT_SURE = "Not sure";

/** Issued questions stay reachable and editable when a later plan replaces its current batch. */
export function planQuestions(c: Case): { q: PlanQuestion; done: boolean; notSure: boolean }[] {
  const plan = c.intake?.record.plan;
  if (!plan || plan.scope.status === "redirect") return [];
  const has = (field: string) => Boolean(confirmedAnswer(c.facts, field));
  // A conflict between readings is settled only by the applicant's own answer, typed or picked here.
  const answeredByApplicant = (field: string) => {
    const f = confirmedAnswer(c.facts, field);
    return Boolean(f && f.source.type !== "file" && !String(f.source.ref ?? "").startsWith("intake:"));
  };
  const questions = new Map([...(plan.asked ?? []), ...plan.questions].map((q) => [q.id, q]));
  const conflicts = new Set(plan.questions.filter((q) => q.kind === "conflict").map((q) => q.id));
  return [...questions.values()].map((q) => {
    const notSure = plan.not_sure.includes(q.id);
    return { q, notSure, done: notSure || (conflicts.has(q.id) ? answeredByApplicant(q.field) : has(q.field)) };
  });
}

/** Local Section A/B fields a planner question asks (so the form card does not ask them again). */
export function plannedFields(c: Case): Map<string, { notSure: boolean }> {
  const plan = c.intake?.record.plan;
  const out = new Map<string, { notSure: boolean }>();
  if (!plan) return out;
  for (const { q, notSure } of planQuestions(c)) out.set(localField(q.field), { notSure });
  for (const id of plan.not_sure) {
    const field = id.startsWith("intake.") ? localField(id.slice("intake.".length)) : "";
    if (field && !out.has(field)) out.set(field, { notSure: true });
  }
  return out;
}

/* —— Scope, fork and the note before you submit —— */

export function scopeRedirect(c: Case) {
  const scope = c.intake?.record.plan?.scope;
  return scope?.status === "redirect" && scope.regime ? scope : null;
}

export function forkOf(c: Case): Fork | null {
  return c.intake?.record.plan?.fork ?? null;
}

/** The fork in one plain line; the API's own explanation sits under it. */
export function forkLine(fork: Fork): string {
  if (fork.variance_needed === "likely") return "Your design seems to differ from the code’s standard way, so this is a variance request.";
  if (fork.variance_needed === "not_indicated") return "Nothing so far differs from the code’s standard way. You may not need a variance.";
  return "We can’t tell yet whether your design differs from the code’s standard way.";
}

/** The two halves of an accepted variance, in plain words first (the official term follows). */
export const HALF_PLAIN: Record<string, string> = {
  variance_request: "Permission to build it differently",
  alternative_solution: "Proof that it works at least as well",
};

/* —— Code identification: committed articles and at most three quoted choices —— */

function answerOf(result: IdentifyResult, article: string): CandidateAnswer | null {
  const d = result.decisions?.[article]?.decision;
  return d === "yes" || d === "no" ? d : d === "not_sure" ? "not-sure" : null;
}

const articleOf = (id: string) => id.match(/^\d+\.\d+\.\d+\.\d+\./)?.[0] ?? id;

/**
 * The code-check cards one identification offers: committed articles (Part 9, calibrated), then the
 * quoted choices. Every provision comes from the result (code database ids); the rest of the
 * ranking stays in the code library. Answers come from the stored decisions, else the earlier card.
 */
export function identifyCandidates(result: IdentifyResult, previous: Candidate[]): Candidate[] {
  const out: Candidate[] = [];
  const seen = new Set<string>();
  const add = (rank: "committed" | "choice", article: string, provision: string, title: string, part: number, quote: string, citation: string | null) => {
    if (!/^\d/.test(provision) || seen.has(article)) return;
    seen.add(article);
    const prev = previous.find((a) => a.provision === provision || a.id === `id-${provision}`);
    const stored = answerOf(result, article);
    const answer = stored ?? prev?.answer ?? null;
    // An answer carried from the earlier card that the engine never stored stays pending (open, resendable).
    const pending = stored === null && prev?.answer != null && prev.pending ? true : undefined;
    out.push({
      id: `id-${provision}`,
      topic: title || provision,
      provision,
      part: part || Number(provision.split(".")[0]) || 0,
      benchmark: answer === "yes",
      identified: true,
      suggestion: "identify",
      rank,
      quote: quote.trim()
        ? { text: quote.trim(), citation: citation ?? "Quoted from the code database.", source: "code" }
        : { text: "", citation: citation ?? "", source: "code" },
      departure: "do something other than what this sentence requires",
      clarifyingQuestion: "Which part of this sentence does the design not follow?",
      answer,
      ...(pending ? { pending } : {}),
    });
  };
  for (const id of result.committed ?? []) {
    const a = result.articles.find((x) => x.provision === id || x.provision_id === id);
    if (a) add("committed", a.provision, a.provision_id ?? a.provision, a.title, a.part, a.quote ?? "", a.citation);
  }
  for (const ch of (result.choices ?? []).slice(0, 3)) add("choice", articleOf(ch.provision), ch.provision_id ?? ch.provision, ch.title, ch.part, ch.quote, ch.citation);
  // Keep the complete keyword shortlist inspectable without making every sentence a required question.
  if (result.mode === "bm25_fallback") {
    for (const a of result.articles) add("choice", articleOf(a.provision), a.provision_id ?? a.provision, a.title, a.part, a.quote ?? "", a.citation);
  }
  return out;
}

/** Plain-language question for an identified rule; the article and the code sentence stay behind "Show the code". */
export function codeQuestion(topic: string): string {
  const t = topic.trim();
  if (!t || /^\d/.test(t)) return "Does your design do something different from this rule?";
  // Code titles are in title case; a question reads in sentence case (acronyms such as NBC stay).
  const words = t.split(/(\s+)/).map((w) => (/^[A-Z][a-z]/.test(w) ? w.toLowerCase() : w)).join("");
  return `Does your design do something different from the rule on ${words}?`;
}

export interface StageView {
  id: string;
  label: string;
  state: "waiting" | "running" | "done";
  detail: string;
}

const STAGES: { id: string; label: string }[] = [
  { id: "screen", label: "Reading every rule in the building code" },
  { id: "rerank", label: "Re-checking the closest ones" },
  { id: "verify", label: "Reading the top matches in full" },
  { id: "questions", label: "Choosing what to ask you" },
];

/** Stage progress from the stream's events (`seen` maps a stage to its counts once done). */
export function stageViews(seen: Record<string, Record<string, unknown>>, running: boolean): StageView[] {
  const firstOpen = STAGES.findIndex((s) => !seen[s.id]);
  return STAGES.map((s, i) => {
    const d = seen[s.id];
    const n = (k: string) => (typeof d?.[k] === "number" ? (d[k] as number) : null);
    let detail = "";
    if (d) {
      if (s.id === "screen" && n("articles") != null) detail = `${n("articles")!.toLocaleString("en-CA")} articles`;
      if (s.id === "rerank" && n("articles") != null) detail = `${n("articles")} re-checked`;
      if (s.id === "verify" && n("picks") != null) detail = `${n("picks")} kept`;
      if (s.id === "questions" && n("choices") != null) detail = `${n("choices")} to confirm`;
    }
    return { ...s, state: d ? "done" : running && i === firstOpen ? "running" : "waiting", detail };
  });
}

/** "1 page", "3 pages": one count for both the number and the plural. */
export function pagesLabel(count: number): string {
  return `${count} ${count === 1 ? "page" : "pages"}`;
}

/** What intake actually covered. Uploading callers pass no report until the read completes. */
/** Lot, block and plan (or an ATS location) read as parts, joined the way the form writes a legal description. */
export const LEGAL_PART_FIELDS = ["lot", "block", "plan", "ats_qtr", "ats_sec", "ats_twp", "ats_rge", "ats_mer"] as const;

export function legalFromParts(parts: Readonly<Record<string, unknown>>): string {
  const v = (k: string) => (parts[k] == null ? "" : String(parts[k]).trim());
  const lbp = [["Lot", v("lot")], ["Block", v("block")], ["Plan", v("plan")]].filter(([, x]) => x).map(([k, x]) => `${k} ${x}`).join(", ");
  const ats = v("ats_sec") && v("ats_twp") && v("ats_rge")
    ? [v("ats_qtr"), v("ats_sec"), v("ats_twp"), v("ats_rge"), v("ats_mer") ? `W${v("ats_mer").replace(/^W/i, "")}` : ""].filter(Boolean).join("-")
    : "";
  return [lbp, ats].filter(Boolean).join("; ");
}

/** The legal description a case already has as confirmed parts, as engine/completeness.py accepts it: all of lot, block and plan, or a full ATS location. */
export function legalFromFacts(facts: readonly Fact[]): string {
  const value = (k: string) => confirmedAnswer(facts, k)?.value;
  for (const set of [["lot", "block", "plan"], ["ats_qtr", "ats_sec", "ats_twp", "ats_rge", "ats_mer"]]) {
    if (set.every((k) => value(k) != null && String(value(k)).trim())) return legalFromParts(Object.fromEntries(set.map((k) => [k, value(k)])));
  }
  return "";
}

/** The engine's reason while pictures wait for the applicant's OK (pixels cannot be scrubbed like text). */
export const PICTURES_WAITING = "waiting for your OK";
export const PICTURES_FIELD = "privacy.pictures";

/** The applicant allowed this application's pictures to be sent for reading. */
export function picturesAllowed(c: Case): boolean {
  const fact = [...c.facts].reverse().find((f) => f.field === PICTURES_FIELD);
  return fact?.status === "confirmed" && fact.value === true;
}

/** Files whose pictures are waiting for that OK. */
export function picturesWaiting(c: Case): boolean {
  return !picturesAllowed(c) && Boolean(c.intake?.record.files.some((r) => r.pictures_not_read_reason === PICTURES_WAITING));
}

export function fileReadLabel(report: FileReport | null | undefined): { tone: "done" | "warning" | "blocking" | "pending"; label: string; reason?: string } {
  if (!report) return { tone: "pending", label: "Waiting to read" };
  const images = new Set(report.image_pages_read ?? []).size;
  const text = new Set(report.text_pages_read ?? report.pages_read).size;
  if (report.pages_read.length && !text && !images && report.form !== "scc_variance" && !report.semantic_reason) {
    return { tone: "warning", label: "Read again", reason: "Coverage needs checking" };
  }
  const pictures = report.pictures_not_read_reason ? `Pictures not read: ${report.pictures_not_read_reason}` : undefined;
  const semantic = report.semantic_reason;
  const reason = pictures ?? (semantic === "AI is off" ? "Text read; AI is off" : semantic) ?? report.reason ?? undefined;
  const warning = report.status !== "read" || Boolean(reason);
  if (images && !text) return { tone: warning ? "warning" : "done", label: `${images} ${images === 1 ? "drawing" : "drawings"} looked at`, ...(reason ? { reason } : {}) };
  if (report.status === "not_read" && !text) return { tone: pictures ? "warning" : "blocking", label: pictures ?? "Not read", ...(reason ? { reason } : {}) };
  const read = semantic && semantic !== "AI is off"
    ? new Set([...(report.semantic_pages_read ?? []), ...(report.image_pages_read ?? [])]).size
    : new Set(report.pages_read).size;
  const detail = reason ?? (images ? `${images} ${images === 1 ? "drawing" : "drawings"} looked at` : undefined);
  return { tone: warning ? "warning" : "done", label: report.media_type === "text/plain" ? "Read" : `Read · ${read} of ${report.pages ?? read} pages`, ...(detail ? { reason: detail } : {}) };
}
