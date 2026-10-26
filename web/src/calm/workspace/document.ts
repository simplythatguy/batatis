import type { MessageItem } from "../../api/accounts";
import { engineField, localField } from "../../intakeFields";
import { DETAIL_FIELDS, PROCESS_FACT, PROCESS_FIELDS, factFor, valueText, type Action } from "../../model";
import type { Case, Gap, ProcessFieldId, SectionCRow } from "../../types";
import { gapKey } from "../deck";

export type SectionId = "A" | "B" | "case" | "C" | "D";
export type BlockTarget =
  | { kind: "detail"; field: string; section: "A" | "B" | "C" }
  | { kind: "process"; field: ProcessFieldId }
  | { kind: "card"; href: string };
export interface DocBlock {
  id: string;
  section: SectionId;
  label: string;
  text: string;
  target: BlockTarget;
  required: boolean;
  missing: boolean;
  notApplicable?: string;
  aiAccepted?: string;
  requests: { id: string; note: string }[];
  /** A reference's immutable attribution and code-text reader. Never an editable value. */
  reference?: SectionCRow;
  /** A legacy lookup explanation is AI text until explicitly accepted. */
  draft?: string;
}
export interface DocSection { id: SectionId; title: string; formLabel: string; blocks: DocBlock[] }
export type OfficerRequest = MessageItem & { id: string };

export function blockField(block: DocBlock): string {
  return block.target.kind === "detail" ? block.target.field
    : block.target.kind === "process" ? PROCESS_FACT[block.target.field] : block.id;
}

/** Draft proposals never become applicant ink, and a withdrawn/unconfirmed answer stays empty. */
export function confirmedText(c: Case, field: string): string {
  const fact = [...c.facts].reverse().find(f => localField(f.field) === localField(field) && f.kind !== "proposed");
  return fact?.status === "confirmed" ? valueText(fact) : "";
}

function notApplicable(c: Case, id: string): string | undefined {
  const aliases = id === "owner_rep_name" ? ["owner_rep", "owner_rep_name", "representative", "applicant_name"]
    : id === "permit_number" ? ["permit_number", "permit"] : [];
  // Select each field's newest revision before checking it, including a later withdrawal.
  const statements = aliases.map(key => factFor(c, `not_applicable.${key}`)).filter(f => f !== undefined);
  const f = statements.reverse().find(f => f.status === "confirmed" && f.kind !== "proposed"
    && (f.source.type === "user_text" || f.source.type === "user_click") && (f.value === true || typeof f.value === "string" && f.value.trim()));
  return f ? f.value === true ? "Marked not applicable by the applicant (no reason given)." : String(f.value) : undefined;
}

export function blockAction(block: DocBlock, value: string): Action | null {
  switch (block.target.kind) {
    case "detail": return { type: "setDetail", field: block.target.field, section: block.target.section, value };
    case "process": return { type: "setProcess", field: block.target.field, value };
    case "card": return null;
  }
}

/** Stable aliases for legacy links, gap fields, writing drafts and officer instructions. */
export function blockForField(sections: readonly DocSection[], field: string): DocBlock | undefined {
  const raw = field.replace(/^field-/, "");
  const canonical = Object.entries(PROCESS_FACT).find(([key]) => key === raw)?.[1] ?? raw;
  const key = localField(canonical);
  return sections.flatMap(s => s.blocks).find(b => b.id === raw || localField(b.id) === key || localField(blockField(b)) === key);
}

/** The paper derives from the case. Shared gaps alone decide which blocks carry a Missing mark. */
export function buildDocument(c: Case, gaps: readonly Gap[], requests: readonly OfficerRequest[] = []): DocSection[] {
  const sections: DocSection[] = [
    { id: "A", title: "About you", formLabel: "Section A", blocks: [] },
    { id: "B", title: "Your project", formLabel: "Section B", blocks: [] },
    { id: "case", title: "Your case", formLabel: "Appendix", blocks: [] },
    { id: "C", title: "Which rules apply", formLabel: "Section C", blocks: [] },
    { id: "D", title: "Supporting documents", formLabel: "Section D", blocks: [] },
  ];
  function add(section: SectionId, block: Omit<DocBlock, "section" | "missing" | "requests">) {
    sections.find(s => s.id === section)?.blocks.push({ ...block, section, missing: false, requests: [] });
  }
  add("A", { id: "authority", label: "Reviewing office", text: c.authority, target: { kind: "card", href: "#/questions?focus=authority" }, required: true });
  for (const f of DETAIL_FIELDS) {
    const id = engineField(f.id), na = notApplicable(c, id);
    const target: BlockTarget = f.options || f.inputType || na
      ? { kind: "card", href: `#/questions?focus=field-${f.id}` }
      : { kind: "detail", field: f.id, section: f.section };
    add(f.section, { id, label: f.label, text: confirmedText(c, f.id), target, required: f.required, ...(na ? { notApplicable: na } : {}) });
  }
  for (const f of PROCESS_FIELDS) add("case", {
    id: PROCESS_FACT[f.id], label: f.label, text: c.process[f.id], required: true, target: { kind: "process", field: f.id },
  });
  add("C", { id: "provisions", label: "Code references", text: c.candidates.filter(a => a.answer === "yes").map(a => a.provision).join(" · "), required: true, target: { kind: "card", href: "#/questions?first=code" } });
  for (const row of c.sectionC) {
    add("C", { id: `section_c.${row.provision}`, label: row.provision, text: row.citation, required: false,
      reference: row, target: { kind: "card", href: "#/references" } });
    const field = `section_c.${row.provision}.explanation`;
    add("C", { id: field, label: `Explanation · ${row.provision}`, text: confirmedText(c, field), draft: row.explanation,
      required: false, target: { kind: "detail", field, section: "C" } });
  }
  add("D", { id: "evidence", label: "Documents", text: listedDocuments(c).map(d => d.title).join("\n"), required: true,
    target: { kind: "card", href: "#/questions?focus=section-d" } });
  for (const gap of gaps) {
    const key = gapKey(c, gap);
    const block = (gap.field && blockForField(sections, gap.field)) || (key && blockForField(sections, key))
      || (/^(?:evidence|professional)/.test(gap.field ?? "") ? blockForField(sections, "evidence") : undefined);
    if (block) block.missing = true;
  }
  for (const r of requests) {
    const gap = gaps.find(g => g.id === r.gap_id);
    const block = blockForField(sections, r.field || gap?.field || "")
      ?? (/^(?:evidence|professional)/.test(r.field ?? gap?.field ?? "") ? blockForField(sections, "evidence") : undefined)
      ?? (/^(?:section_c|provisions)/.test(r.field ?? gap?.field ?? "") ? blockForField(sections, "provisions") : undefined);
    if (block && r.note?.trim()) block.requests.push({ id: r.id, note: r.note });
  }
  return sections;
}

export function listedDocuments(c: Case): { id: string; title: string }[] {
  const ids = new Set(c.facts.flatMap(f => /^evidence\.([^.]+)\.title$/.exec(f.field)?.[1] ?? []));
  return [...ids].filter(id => !c.unscopedEvidence?.includes(id) && !c.deletedEvidence?.includes(id))
    .flatMap(id => { const title = confirmedText(c, `evidence.${id}.title`).trim(); return title ? [{ id, title }] : []; });
}
