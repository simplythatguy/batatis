import type { Case, Gap } from "../../types";
import { gapKey } from "../deck";
import { preparationGaps } from "../preparation";
import { calmHref } from "../routes";
import { blockForField, type DocSection } from "./document";
import type { WorkspaceLoad } from "./useWorkspace";

export type FlagGroup = "answers" | "rules" | "documents" | "signing" | "officer";
export interface SigningFlag { id: string; label: string; href: string; group?: FlagGroup }
export interface FlagRow { key: string; label: string; href: string; count: number; /** Every label this row stands for, when they differ only by article. */ all: string[] }

export const GROUP_LABEL: Record<FlagGroup, string> = {
  answers: "Your answers",
  rules: "Code questions",
  documents: "Documents",
  signing: "Signing",
  officer: "For the officer",
};
const ORDER: FlagGroup[] = ["answers", "rules", "documents", "signing", "officer"];

export function signingFlags(state: WorkspaceLoad, signaturesCurrent: boolean): SigningFlag[] {
  if (state.phase !== "ready") return [];
  const flags: SigningFlag[] = [];
  if (!state.record.consent?.agreed) flags.push({ id: "consent", label: "Consent not given", href: "#/application?step=sign", group: "signing" });
  for (const s of state.record.signers.filter(s => s.required)) {
    const signature = state.record.signatures.find(signature => signature.role === s.role);
    if (!signature || !signature.current || !signaturesCurrent) {
      flags.push({
        id: `signature-${s.role}`,
        label: `${s.role === "owner" ? "Owner" : "Owner’s representative"} ${signature ? "signed an older version" : "hasn’t signed"}`,
        href: "#/application?step=sign",
        group: "signing",
      });
    }
  }
  return flags;
}

export function workspaceFixHref(c: Case, sections: readonly DocSection[], gap: Pick<Gap, "id" | "field" | "href">): string {
  const key = gapKey(c, { ...gap, severity: "blocking", label: "" });
  const block = (gap.field && blockForField(sections, gap.field)) || (key && blockForField(sections, key));
  return block ? `#/application?focus=${encodeURIComponent(block.id)}` : key ? `#/questions?focus=${encodeURIComponent(key)}` : calmHref(gap.href);
}

function groupOf(gap: Pick<Gap, "field" | "id">): FlagGroup {
  const f = `${gap.field ?? ""} ${gap.id}`;
  if (/(^|\s)(evidence|professional|responsible|supporting_doc|section_d)/.test(f)) return "documents";
  if (/(^|\s)(candidate|provision|citation|article|decision|identify|section_c|q-from|rule)/.test(f)) return "rules";
  return "answers";
}

/** The shared completeness results plus signing, in the groups an applicant fixes them by. */
export function officerFlags(c: Case, gaps: Gap[], sections: readonly DocSection[], signatures: SigningFlag[]): SigningFlag[] {
  const work = preparationGaps(c, gaps);
  const flag = (g: Gap, group?: FlagGroup): SigningFlag => ({ id: g.id, label: g.label, href: workspaceFixHref(c, sections, g), group: group ?? groupOf(g) });
  return [
    ...work.applicant.map(g => flag(g)),
    ...work.checkNeeded.map(g => flag(g)),
    ...work.officer.map(g => flag(g, "officer")),
    ...signatures,
  ];
}

const ARTICLE = /\b\d+(?:\.\d+)+\.?(?:\(\d+\))*(?:\([a-z]+\))?/g;

/**
 * Identical items read as one row with a count; items that differ only by article number (one question
 * asked of five sentences) read as one row naming the first and how many more.
 */
export function groupFlags(flags: readonly SigningFlag[]): { group: FlagGroup; rows: FlagRow[] }[] {
  const groups = new Map<FlagGroup, Map<string, FlagRow>>();
  for (const f of flags) {
    const group = f.group ?? "answers";
    const rows = groups.get(group) ?? new Map<string, FlagRow>();
    const key = f.label.replace(ARTICLE, "#");
    const row = rows.get(key);
    if (!row) rows.set(key, { key: f.id, label: f.label, href: f.href, count: 1, all: [f.label] });
    else if (row.all.includes(f.label)) row.count += 1;
    else row.all.push(f.label);
    groups.set(group, rows);
  }
  return ORDER.filter(g => groups.has(g)).map(group => ({
    group,
    rows: [...groups.get(group)!.values()].map(r => r.all.length > 1 ? { ...r, label: `${r.all[0]} and ${r.all.length - 1} more` } : r),
  }));
}
