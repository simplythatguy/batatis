/** Placement and presentation only. Counts, dispositions and acceptance belong to the server. */
import type { Case, Finding, FindingState, InputFile, Pointer, RequestTarget, ReviewSession, RulebookGap, Workspace } from "../../api/types.gen";
import type { ReviewQuestion } from "../../api/client";
import { localField } from "../../intakeFields";
import { pointerLabel, SECTION_LABEL } from "./packageView";
import type { SheetRow, SheetView } from "./sheet";

export type Section = Finding["section"];
export type FindingFilter = "all" | "required" | "to_check" | "dismissed";
export const SECTIONS: Section[] = ["A", "B", "C", "process", "D"];
export interface SheetAnchor { id: string; section: Section; field: string; label: string }
export interface WorkspaceRow extends SheetAnchor { reading: SheetRow }

export function sheetRows(sheet: SheetView, session: ReviewSession | null, historical = false): WorkspaceRow[] {
  const rows: WorkspaceRow[] = [];
  const add = (section: Section, reading: SheetRow) => {
    const field = reading.field ?? reading.label;
    const old = historical ? session?.fields.find(f => localField(f.field) === localField(field)) : null;
    rows.push({ id: `${section}:${field}`, section, field, label: reading.label,
      reading: historical ? { ...reading, value: old?.status === "present" ? old.value : null, unconfirmed: false } : reading });
  };
  sheet.applicant.forEach(r => add("A", r));
  sheet.project.forEach(r => add("B", r));
  add("B", sheet.alternative);
  sheet.process.forEach(r => add("process", r));
  sheet.supporting.forEach(r => add("D", r));
  // Fields on an uploaded or older form may not exist in the current applicant editor.
  for (const f of session?.fields ?? []) {
    if (rows.some(r => localField(r.field) === localField(f.field))) continue;
    if (/^(section_c[.\[]|citation[.\[]|evidence\.|document\.|div_c\.|demonstrate\.)/.test(f.field)) continue;
    add(f.section, { field: f.field, label: f.label, value: f.status === "present" ? f.value : null, required: false });
  }
  return rows;
}

export function allAnchors(rows: WorkspaceRow[], sheet: SheetView, session: ReviewSession | null): SheetAnchor[] {
  const refs = [...new Set([...sheet.references.map(r => r.provision), ...(session?.citations ?? []).map(c => c.provision_id || c.text), ...(session?.section_c ?? []).map(c => c.provision_id).filter((p): p is string => Boolean(p))])];
  const docs = new Map(sheet.documents.map(d => [d.id, d.title]));
  for (const d of session?.documents ?? []) if (!docs.has(d.id)) docs.set(d.id, d.title.known ? d.title.value : "Untitled document");
  return [...rows,
    ...refs.map(provision => ({ id: `C:${provision}`, section: "C" satisfies Section, field: `section_c.${provision}`, label: provision })),
    ...[...docs].map(([id, title]) => ({ id: `D:document:${id}`, section: "D" satisfies Section, field: `evidence.${id}`, label: title })),
    { id: "process:file-checklist", section: "process", field: "div_c", label: "File checklist" },
  ];
}

/** Exact field, document/reference family, then the end of the supplied section. Nothing is lost. */
export function anchorFor(item: { section: Section | null; field: string | null }, rows: SheetAnchor[]): string {
  const section = item.section ?? "D";
  const field = item.field ?? "";
  const canonical = localField(field);
  const exact = rows.find(r => r.section === section && localField(r.field) === canonical);
  if (exact) return exact.id;
  if (/^(evidence|document|section_d)\./.test(field)) {
    const id = field.split(".")[1];
    const doc = rows.find(r => r.section === "D" && r.field === `evidence.${id}`);
    if (doc) return doc.id;
  }
  if (/^(section_c|citation)[.\[]/.test(field)) {
    const refs = rows.filter(r => r.section === "C" && r.field.startsWith("section_c."));
    const ref = refs.find(r => field.includes(r.label));
    if (ref) return ref.id;
    const ordinal = /^(?:section_c|citation)(?:\[|\.)(\d+)(?:\]|\.|$)/.exec(field);
    if (ordinal && refs[Number(ordinal[1])]) return refs[Number(ordinal[1])].id;
  }
  if (/^(div_c\.|demonstrate\.)/.test(field)) return "process:file-checklist";
  if (/^(professional[._]|registered_professional\.)/.test(field)) {
    const professional = rows.find(r => r.section === "D" && r.field.startsWith("professional."));
    if (professional) return professional.id;
  }
  return `${section}:end`;
}

export function anchoredItems<T extends { section: Section | null; field: string | null }>(items: T[], anchors: SheetAnchor[]): Map<string, T[]> {
  const result = new Map<string, T[]>();
  for (const item of items) {
    const id = anchorFor(item, anchors);
    result.set(id, [...(result.get(id) ?? []), item]);
  }
  return result;
}

export interface FindingSource { where: string; quote: string | null; page: number | null; fileId: string | null; href: string | null }
export function filePath(caseId: string, fileId: string, page?: number | null): string {
  return `/cases/${encodeURIComponent(caseId)}/files/${encodeURIComponent(fileId)}${page ? `#page=${page}` : ""}`;
}
export function findingSources(pointers: Pointer[], files: InputFile[], caseId: string): FindingSource[] {
  return pointers.map(p => {
    const file = files.find(f => f.name === p.file);
    const fileId = file?.file_id ?? null;
    return { where: pointerLabel(p), quote: p.quote, page: p.page, fileId, href: fileId ? filePath(caseId, fileId, p.page) : null };
  });
}

export function targetOptions(session: ReviewSession | null, anchors: SheetAnchor[]): RequestTarget[] {
  const options = new Map<string, RequestTarget>();
  const add = (target: RequestTarget) => {
    const key = `${target.section}:${target.field ? localField(target.field) : ""}`;
    if (!options.has(key)) options.set(key, target);
  };
  for (const section of SECTIONS) add({ section, field: null, label: SECTION_LABEL[section] });
  for (const f of session?.fields ?? []) add({ section: f.section, field: f.field, label: `${SECTION_LABEL[f.section]} · ${f.label}` });
  for (const r of anchors) add({ section: r.section, field: r.field, label: `${SECTION_LABEL[r.section]} · ${r.label}` });
  return [...options.values()];
}

export function clarificationSuggestions(questions: ReviewQuestion[], items: { target: RequestTarget | null }[]): { text: string; target: RequestTarget }[] {
  const included = new Set(items.map(i => i.target?.field));
  return questions.filter(q => q.state !== "answered" && !included.has(`clarification.${q.id}`)).map(q => ({
    text: `Please clarify: ${q.text}`,
    target: { section: "B", field: `clarification.${q.id}`, label: `Applicant question · ${q.text}` },
  }));
}

export function changedFields(c: Pick<Case, "submissions">): Map<string, Case["submissions"][number]["changes"][number]> {
  return new Map((c.submissions?.at(-1)?.changes ?? []).map(change => [localField(change.field), change]));
}

/** Historical versions use their saved dispositions; current versions use Workspace.states. */
export function findingState(f: Finding, session: ReviewSession, workspace: Workspace | null): FindingState {
  return workspace?.states.find(s => s.key === f.key) ?? {
    locked: false, key: f.key, state: f.status === "not_found" || f.routed_to !== "applicant" ? "verify" : "ask",
    reason: null, note: "", at: null, by_name: null, ...session.dispositions?.find(s => s.key === f.key),
  };
}
export function visibleFinding(f: Finding, state: FindingState, filter: FindingFilter): boolean {
  if (filter === "all") return true;
  if (filter === "dismissed") return state.state === "dismissed";
  return state.state !== "dismissed" && f.severity === (filter === "required" ? "blocking" : "warning");
}
export const visibleRulebook = (_gap: RulebookGap, filter: FindingFilter) => filter === "all" || filter === "required";

/** Local save/ownership holds only. Never reimplement or recount the server's acceptance gate. */
export function workspaceDecision({ workspace, editable, pending, busy }: { workspace: Workspace | null; editable: boolean; pending: boolean; busy: boolean }) {
  const hold = !editable ? "This version is read-only." : pending ? "Save the request changes first." : busy ? "An action is in progress." : "";
  const returnReason = hold || (!workspace ? "Waiting for the saved review." : !workspace.tally.asked ? "Add an item to return the application." : "");
  const acceptReason = hold || (!workspace ? "Waiting for the saved review." : workspace.gate.reason);
  return { canReturn: !returnReason, canAccept: !hold && Boolean(workspace?.gate.can_accept), canRefuse: editable && !pending && !busy, returnReason, acceptReason };
}
