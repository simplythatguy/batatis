import type { Case, Gap } from "../../types";
import { gapKey } from "../deck";
import { preparationGaps } from "../preparation";
import { calmHref } from "../routes";
import { blockForField, type DocSection } from "./document";
import type { WorkspaceLoad } from "./useWorkspace";

export interface SigningFlag { id: string; label: string; href: string }
export function signingFlags(state: WorkspaceLoad, signaturesCurrent: boolean): SigningFlag[] {
  if (state.phase !== "ready") return [];
  const flags: SigningFlag[] = [];
  if (!state.record.consent?.agreed) flags.push({ id: "consent", label: "Consent to the described use of information", href: "#/application?step=sign" });
  for (const s of state.record.signers.filter(s => s.required)) {
    const signature = state.record.signatures.find(signature => signature.role === s.role);
    if (!signature || !signature.current || !signaturesCurrent) flags.push({ id: `signature-${s.role}`, label: `${s.role === "owner" ? "Owner" : "Owner’s representative"} · ${signature ? "changed since signed" : "unsigned"}`, href: "#/application?step=sign" });
  }
  return flags;
}
export function workspaceFixHref(c: Case, sections: readonly DocSection[], gap: Pick<Gap, "id" | "field" | "href">): string {
  const key = gapKey(c, { ...gap, severity: "blocking", label: "" });
  const block = (gap.field && blockForField(sections, gap.field)) || (key && blockForField(sections, key));
  return block ? `#/application?focus=${encodeURIComponent(block.id)}` : key ? `#/questions?focus=${encodeURIComponent(key)}` : calmHref(gap.href);
}
export function officerFlags(c: Case, gaps: Gap[], sections: readonly DocSection[], signatures: SigningFlag[]): SigningFlag[] {
  const work = preparationGaps(c, gaps);
  return [...work.applicant, ...work.officer, ...work.checkNeeded].map(g => ({ id: g.id, label: g.label, href: workspaceFixHref(c, sections, g) })).concat(signatures);
}
