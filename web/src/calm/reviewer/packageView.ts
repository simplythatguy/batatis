/**
 * The officer's package review as plain views: summary, what's missing, documents, code checks,
 * Division C file items, the peer-review signal, the information request draft, the re-upload diff,
 * the refusal message and the close-out. Pure: everything is derived from a ReviewSession or CloseOut.
 * Administrative completeness only: nothing here judges the design.
 */
import type { DecisionItemInput, DecisionRequest } from "../../api/accounts";
import type {
  Attribute,
  CitationCheck,
  CloseOut,
  DocumentRow,
  Finding,
  InformationRequest,
  InformationRequestEdit,
  Pointer,
  ReviewSession,
  SectionCCheck,
} from "../../api/types.gen";

export type Tone = "blocking" | "warning" | "pending" | "done";
export type Section = Finding["section"];

/* —— Words —— */

export const SECTION_LABEL: Record<Section, string> = {
  A: "Section A · Applicant",
  B: "Section B · Project and variance",
  C: "Section C · Code references",
  D: "Section D · Supporting documents",
  process: "Alternative-path documentation",
};
const SECTION_ORDER: Section[] = ["A", "B", "C", "D", "process"];

export const sentence = (s: string) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);

/** Where a value or gap was read, in words: "Saved application", "scc-form.pdf · page 2 · field “Date2”". */
export function pointerLabel(p: Pointer | null | undefined): string {
  if (!p) return "";
  const parts: string[] = [];
  const file = p.file || "";
  if (file.startsWith("case:")) parts.push("Saved application");
  else if (/\.pdf$/i.test(file)) parts.push(file);
  else if (/description/i.test(file)) parts.push("Applicant’s description");
  else if (file) parts.push("Applicant’s answer");
  if (p.page) parts.push(`page ${p.page}`);
  if (p.form_field && !/^section_[cd]\[/.test(p.form_field)) parts.push(`field “${p.form_field}”`);
  return parts.join(" · ");
}

/** The quote behind a pointer, when it adds something beyond the value itself. */
export function pointerQuote(p: Pointer | null | undefined, value?: string | null): string {
  const q = p?.quote?.trim() ?? "";
  if (!q || (value && q === value.trim())) return "";
  return q.length > 220 ? `${q.slice(0, 217).trimEnd()}…` : q;
}

/** "NBC(AE) 2023 p2, Div C, Sentence 2.3.1.1.(3) [PDF p.739]" → { division: "C", id: "2.3.1.1.(3)" }. */
export function parseCitation(citation: string): { division: "A" | "B" | "C"; id: string } | null {
  const m = /Div(?:ision)?\s*([ABC])\b[^0-9]*?(\d+(?:\.\d+)+\.?(?:\(\d+\))?(?:\([a-z]\))?)/.exec(citation);
  if (!m) return null;
  return { division: m[1] as "A" | "B" | "C", id: m[2] };
}

/* —— Finding kinds —— */

export const PEER_KEY = "peer_review:signal";
export const isPeer = (f: Finding) => f.key === PEER_KEY;
export const isFileItem = (f: Finding) => f.key.startsWith("div_c.");
export const isDemonstrate = (f: Finding) => f.key.startsWith("demonstrate.");

/** Keys the information request asks of the applicant (the server decides; we only read it). */
function askable(s: ReviewSession): Set<string> {
  return new Set(s.information_request.items.map((i) => i.finding_key).filter((k): k is string => Boolean(k)));
}

/** "Look first": not found (ask the officer) or never asked of the applicant (officer-routed). */
export function isOfficerCheck(f: Finding, asked: Set<string>): boolean {
  return f.status === "not_found" || f.routed_to !== "applicant" || !asked.has(f.key);
}

export interface FindingView {
  key: string;
  title: string;
  message: string;
  tone: Tone;
  where: string;
  quote: string;
  citations: string[];
}

/** Findings are often worded to the applicant ("Your application …"); the officer reads them in the third person. */
export function officerVoice(message: string): string {
  return message.replace(/\bYour application\b/g, "The application").replace(/\byour application\b/g, "the application");
}

export function findingView(f: Finding): FindingView {
  const p = f.pointers[0];
  return {
    key: f.key,
    title: sentence(f.label),
    message: officerVoice(f.message),
    tone: f.status === "not_found" ? "pending" : f.severity === "blocking" ? "blocking" : "warning",
    where: pointerLabel(p),
    quote: pointerQuote(p),
    citations: f.citations,
  };
}

export interface MissingView {
  /** Asked of the applicant, grouped by form section in form order (Division C file items and the
   *  "demonstrate" prompts sit in the alternative-path group). */
  groups: { section: Section; label: string; items: FindingView[] }[];
  /** For the officer to look at first. */
  officer: FindingView[];
  /** Equals the summary's "to ask" plus "to check", so both screens show the same number. */
  total: number;
}

export function missingView(s: ReviewSession): MissingView {
  const asked = askable(s);
  const own = s.findings.filter((f) => !isPeer(f));
  const rank = (f: Finding) => (f.severity === "blocking" ? 0 : 1);
  const applicant = own.filter((f) => !isOfficerCheck(f, asked)).sort((a, b) => rank(a) - rank(b));
  const groups = SECTION_ORDER.map((section) => ({
    section,
    label: SECTION_LABEL[section],
    items: applicant.filter((f) => f.section === section).map(findingView),
  })).filter((g) => g.items.length);
  const officer = own.filter((f) => isOfficerCheck(f, asked)).map(findingView);
  return { groups, officer, total: applicant.length + officer.length };
}

/** Open applicant gaps that block acceptance (not-found items are the officer's checks, not gaps). */
export function blockingGaps(s: ReviewSession): number {
  const asked = askable(s);
  return s.findings.filter((f) => f.severity === "blocking" && !isPeer(f) && !isOfficerCheck(f, asked)).length;
}

/* —— Summary —— */

const OWNER = ["owner_name", "Owner", "owner", "Owner Print"];
const REP = ["representative", "Owner Rep", "applicant_name", "Owner Rep Print"];
const ADDRESS = ["civic_address", "Municipal Address", "municipal_address", "address", "single_location"];
const PROPOSAL = ["alternative_description", "alternative"];

function read(s: ReviewSession, names: string[]): string | null {
  for (const n of names) {
    const f = s.fields.find((x) => x.field === n && x.status === "present" && x.value?.trim());
    if (f) return f.value!.trim();
  }
  return null;
}

export interface SummaryView {
  headline: string;
  proposal: string | null;
  proposalWhere: string;
  provisions: string[];
  documents: string[];
  readFrom: string;
  present: number;
  blank: number;
  notFound: number;
  toAsk: number;
  toCheck: number;
  peer: boolean;
}

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

export function summaryView(s: ReviewSession): SummaryView {
  const owner = read(s, OWNER);
  const rep = read(s, REP);
  const address = read(s, ADDRESS);
  const who = owner ?? rep ?? "The applicant";
  const by = rep && owner && rep !== owner ? ` through ${rep}` : "";
  const headline = `${who}${by} asks for a variance${address ? ` at ${address}` : ""}.`;
  const proposalField = s.fields.find((f) => PROPOSAL.includes(f.field) && f.status === "present" && f.value?.trim());
  const provisions = [...new Set(s.citations.map((c) => c.provision_id || c.text).filter(Boolean))] as string[];
  const documents = s.documents.map((d) => [d.title.known ? d.title.value : "Untitled document", d.issuer.known ? d.issuer.value : null].filter(Boolean).join(", "));
  const pdfs = s.files.filter((f) => f.role !== "case_record");
  const form = pdfs.find((f) => f.role === "scc_form_fillable" || f.role === "scc_form_flattened");
  const readFrom = s.input_kind === "case"
    ? "Read from the saved application."
    : `Read from ${plural(pdfs.length, "PDF")}${form ? `: the SCC form (${form.role === "scc_form_fillable" ? "fillable" : "flattened"}, ${plural(form.pages, "page")})` : ", with no SCC form found"}${pdfs.length > (form ? 1 : 0) ? ` and ${plural(pdfs.length - (form ? 1 : 0), "attachment")}` : ""}.`;
  const asked = askable(s);
  const own = s.findings.filter((f) => !isPeer(f));
  return {
    headline,
    proposal: proposalField?.value?.trim() ?? null,
    proposalWhere: pointerLabel(proposalField?.pointer),
    provisions,
    documents,
    readFrom,
    present: s.fields.filter((f) => f.status === "present" && f.value?.trim()).length,
    blank: s.fields.filter((f) => f.status === "blank").length,
    notFound: s.fields.filter((f) => f.status === "not_found").length,
    toAsk: own.filter((f) => !isOfficerCheck(f, asked)).length,
    toCheck: own.filter((f) => isOfficerCheck(f, asked)).length,
    peer: s.findings.some(isPeer),
  };
}

/* —— Documents panel —— */

export interface Cell {
  label: string;
  value: string;
  known: boolean;
  where: string;
}

const cell = (label: string, a: Attribute): Cell => ({ label, value: a.known ? a.value : "unknown", known: a.known, where: a.known ? pointerLabel(a.source) : "" });

export function documentView(d: DocumentRow): { title: string; titleKnown: boolean; note: string; file: string | null; cells: Cell[] } {
  return {
    title: d.title.known ? d.title.value : "Untitled document",
    titleKnown: d.title.known,
    note: d.file ? (d.listed_in_section_d ? "Uploaded and listed in Section D." : "Uploaded; not listed in Section D.") : "Listed in Section D; no uploaded file with this name.",
    file: d.file,
    cells: [
      cell("Type", d.type),
      cell("Issued by", d.issuer),
      cell("Date", d.date),
      cell("Evidence type", d.evidence_rung),
      cell("Seal", d.seal),
      cell("Responsible person", d.responsible),
    ],
  };
}

/* —— Code checks —— */

export function citationView(c: CitationCheck): { id: string; tone: Tone; status: string; issues: string[] } {
  const id = c.provision_id || c.text;
  const issues = c.issues.map((i) => i.message);
  if (c.issues.some((i) => i.code === "lookup_skipped") || c.exists === null) return { id, tone: "pending", status: "Not looked up", issues };
  if (c.exists === false) return { id, tone: "blocking", status: "Not found in NBC(AE) 2023", issues };
  if (c.edition_ok === false) return { id, tone: "warning", status: "Found, but cited as another edition", issues };
  if (c.page_ok === false) return { id, tone: "warning", status: "Found, but the page reference differs", issues };
  if (issues.length) return { id, tone: "warning", status: "Found, with a note", issues };
  return { id, tone: "done", status: "Found in NBC(AE) 2023, 2nd printing", issues };
}

const SC_STATUS: Record<SectionCCheck["status"], [Tone, string]> = {
  match: ["done", "Matches the Division B table"],
  mismatch: ["blocking", "Differs from the Division B table"],
  no_table_row: ["warning", "No row in the Division B table"],
  provision_not_found: ["blocking", "Provision not found"],
  not_checked: ["pending", "Not checked"],
};

export function sectionCView(r: SectionCCheck): { row: number; id: string; tone: Tone; status: string; message: string; form: string; table: string } {
  const [tone, status] = SC_STATUS[r.status];
  return {
    row: r.row,
    id: r.provision_id || "—",
    tone,
    status,
    message: r.message,
    form: [r.form_objective, r.form_function].filter(Boolean).join(" · ") || "—",
    table: r.table_pairs.join(", ") || "—",
  };
}

/* —— Division C 2.3.1.1 file items and "demonstrate, don't assert" —— */

const FILE_ITEMS: [string, string, string][] = [
  ["div_c.code_analysis", "Code analysis with the attributed objectives and functions", "2.3.1.1.(3)"],
  ["div_c.testing_procedures", "Testing procedures, test methods or engineering studies", "2.3.1.1.(3)"],
  ["div_c.qualifications", "Qualifications of the people responsible", "2.3.1.1.(4)"],
  ["div_c.maintenance", "Maintenance, operation and commissioning needs", "2.3.1.1.(2)(b)"],
];
const DEMONSTRATE: [string, string, string][] = [
  ["demonstrate.failure_conditions", "What happens if a component fails", "2.3.1.1.(3)"],
  ["demonstrate.lapsed_maintenance", "What happens if maintenance lapses", "2.3.1.1.(2)(b)"],
  ["demonstrate.emergency_response", "What it assumes about emergency-services response", "2.3.1.1.(3)"],
];

export interface CheckRow {
  key: string;
  label: string;
  provision: string;
  tone: Tone;
  status: string;
  message: string;
}

/** Open Division C file items and "demonstrate" prompts, for the step's count. */
export const fileGaps = (s: ReviewSession) => s.findings.filter((f) => isFileItem(f) || isDemonstrate(f)).length;

export function fileItemsView(s: ReviewSession): { items: CheckRow[]; demonstrate: CheckRow[]; read: boolean } {
  // Nothing readable means nothing was checked; never show "no gap" for an unread package.
  const read = s.fields.some((f) => f.status === "present" && f.value?.trim());
  const found = (f: Finding, key: string, label: string, provision: string, demo: boolean): CheckRow => {
    const tone: Tone = f.status === "not_found" ? "pending" : demo ? "warning" : "blocking";
    return { key, label, provision, tone, status: f.status === "not_found" ? "Not found · check it" : demo ? "Not mentioned" : "Missing", message: officerVoice(f.message) };
  };
  const row = ([key, label, provision]: [string, string, string], demo: boolean): CheckRow => {
    const f = s.findings.find((x) => x.field === key);
    if (f) return found(f, key, label, provision, demo);
    return read ? { key, label, provision, tone: "done", status: "No gap found", message: "" } : { key, label, provision, tone: "pending", status: "Not checked", message: "" };
  };
  const items = FILE_ITEMS.map((i) => row(i, false));
  // Only listed when more than one person or firm takes responsibility and none co-ordinates.
  const coordinator = s.findings.find((f) => f.field === "div_c.coordinator");
  if (coordinator) items.push(found(coordinator, "div_c.coordinator", "A single co-ordinator for the design", "2.3.1.1.(6)", false));
  return { items, demonstrate: DEMONSTRATE.map((i) => row(i, true)), read };
}

/* —— Peer review (officer only) —— */

export function peerView(s: ReviewSession): { signal: boolean; reasons: string[] } {
  const f = s.findings.find(isPeer);
  if (!f) return { signal: false, reasons: [] };
  const body = f.message.replace(/^Peer review may be warranted:\s*/i, "").replace(/\.\s*This is the officer's call.*$/i, "");
  return { signal: true, reasons: body.split(/;\s*/).map((r) => sentence(r.trim().replace(/\.$/, ""))).filter(Boolean) };
}

/* —— Information request draft —— */

export interface DraftItem {
  /** Server id; absent for an officer item not yet saved. */
  id: string | null;
  /** Stable React key. */
  key: string;
  text: string;
  included: boolean;
  authored: "batatis" | "officer";
  officerCheck: boolean;
  section: Section | null;
  /** Drafted from a finding (it can be left out, not removed). */
  linked: boolean;
}

export function draftFrom(ir: InformationRequest): { intro: string; items: DraftItem[] } {
  return {
    intro: ir.intro,
    items: ir.items.map((i) => ({ id: i.id, key: i.id, text: i.text, included: i.included, authored: i.authored_by, officerCheck: i.officer_check, section: i.section, linked: Boolean(i.finding_key) })),
  };
}

/** The PUT body: the full list in order (text trimmed); empty officer items are dropped. */
export function toEdit(intro: string, items: DraftItem[]): InformationRequestEdit {
  return {
    intro: intro.trim(),
    items: items
      .filter((i) => i.id || i.text.trim())
      .map((i) => (i.id ? { id: i.id, text: i.text.trim(), included: i.included } : { text: i.text.trim(), included: i.included })),
  };
}

/** The text the applicant receives (mirrors the server's render: intro, blank line, numbered items). */
export function previewText(intro: string, items: DraftItem[]): string {
  const lines = [intro.trim(), ""];
  let n = 0;
  for (const i of items) if (i.included && i.text.trim()) lines.push(`${++n}. ${i.text.trim()}`);
  return lines.join("\n").trim();
}

export function sameDraft(a: InformationRequestEdit, b: InformationRequestEdit): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

export const includedCount = (items: DraftItem[]) => items.filter((i) => i.included && i.text.trim()).length;

/** The note that returns the application after a request, and the items it carries. Pure. */
export function returnAfterRequest(count: number): string {
  return `I sent you an information request with ${count} ${count === 1 ? "item" : "items"}. Please update the application and send it again.`;
}

export function requestItems(s: ReviewSession): DecisionItemInput[] {
  return s.information_request.items
    .filter((i) => i.included && i.text.trim())
    .map((i) => ({ field: (i.field || "information_request").slice(0, 200), note: i.text.trim().slice(0, 2000) }));
}

/* —— Re-upload diff —— */

export function diffView(s: ReviewSession): null | {
  statement: string;
  from: number;
  resolved: FindingView[];
  stillOpen: FindingView[];
  added: FindingView[];
  ratio: number;
} {
  const d = s.diff;
  if (!d) return null;
  const byKey = new Map(s.findings.map((f) => [f.key, f]));
  const view = (e: { key: string; label: string; message: string }, tone: Tone): FindingView => {
    const f = byKey.get(e.key);
    return f ? { ...findingView(f), tone } : { key: e.key, title: sentence(e.label), message: e.message, tone, where: "", quote: "", citations: [] };
  };
  return {
    statement: sentence(d.statement),
    from: d.previous_version,
    resolved: d.resolved.map((e) => view(e, "done")),
    stillOpen: d.still_open.map((e) => view(e, "warning")),
    added: d.new.map((e) => view(e, "blocking")),
    ratio: d.previous_gaps ? d.resolved.length / d.previous_gaps : 1,
  };
}

/* —— Refusal —— */

export const REFUSE_MIN = 10;

/** Safety Codes Council, Variances (engine/data/jurisdictions/provinces/AB.json, "ab-appeal"). */
export const APPEAL_NOTICE =
  "You can appeal this refusal to the Safety Codes Council within 30 days of being served with it. Send the Notice of Appeal form, a copy of the written notice of refusal and the $500 fee. A refusal issued by an Administrator is not appealable.";
export const APPEAL_SOURCE = "https://www.safetycodes.ab.ca/permits-inspections/variances/";

/** The officer's reasons, verbatim, then the appeal notice. Batatis writes no reasons of its own. */
export function refusalMessage(reasons: string): string {
  return ["Your variance request is refused for the reasons below.", "", reasons.trim(), "", `Appeal: ${APPEAL_NOTICE}`].join("\n").slice(0, 4000);
}

/**
 * A terminal refusal, with the officer's reasons and the existing appeal notice, pinned to the
 * version on screen. A refusal carries no correction list: it is not a return.
 */
export function refusalDecision(reasons: string, expectedVersion: number): DecisionRequest {
  return { outcome: "refuse", message: refusalMessage(reasons), expected_version: expectedVersion };
}

export function reasonsProblem(reasons: string): string {
  const n = reasons.trim().length;
  if (n >= REFUSE_MIN) return "";
  return n === 0 ? "Write your reasons for the refusal." : `At least ${REFUSE_MIN} characters · ${n} so far.`;
}

/* —— Close-out —— */

export function dayLabel(iso: string): string {
  const d = /^\d{4}-\d{2}-\d{2}$/.test(iso) ? new Date(`${iso}T12:00:00`) : new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-CA", { month: "short", day: "numeric", year: "numeric" });
}

export function dueView(c: CloseOut): { tone: Tone; text: string } {
  if (c.sent) return { tone: "done", text: `You recorded sending it${c.sent_at ? ` on ${dayLabel(c.sent_at)}` : ""}${c.sent_by_name ? ` (${c.sent_by_name})` : ""}.` };
  if (c.overdue) return { tone: "blocking", text: `Due ${dayLabel(c.due_date)} · ${plural(Math.abs(c.days_remaining), "day")} overdue` };
  if (c.days_remaining === 0) return { tone: "warning", text: `Due today, ${dayLabel(c.due_date)}` };
  return { tone: c.days_remaining <= 3 ? "warning" : "pending", text: `Due ${dayLabel(c.due_date)} · ${plural(c.days_remaining, "day")} left` };
}
