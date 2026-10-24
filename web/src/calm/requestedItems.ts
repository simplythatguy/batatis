/** Requested instructions keep their stored identity; display/progress never records approval. */
import type { MessageItem } from "../api/accounts";
import { localField } from "../intakeFields";
import { DETAIL_FIELDS, DETAIL_IDS, factLabel, PROCESS_FACT } from "../model";
import type { Case, Gap } from "../types";
import { gapKey } from "./deck";
import { calmHref } from "./routes";
import { requestedUncertaintyRow } from "./uncertainty";

export function requestedItemLabel(item: MessageItem): string {
  const field = item.field ? localField(item.field) : null;
  return item.note?.trim() || (field ? DETAIL_FIELDS.find((detail) => detail.id === field)?.label || factLabel(field) : "Requested item");
}

/**
 * Old drafts copied the checked items into standalone bullets as well as `items`. Hide only
 * exact repeated bullets at display time. Other comments and body-only history stay verbatim;
 * the persisted body still identifies the authoritative decision in the conversation seam.
 */
export function requestedMessageBody(body: string, items: readonly MessageItem[]): string {
  const notes = new Set(items.map((item) => item.note?.trim().replace(/\s+/g, " ")).filter(Boolean));
  if (!notes.size) return body;
  const lines = body.split("\n");
  const kept = lines.filter((line) => {
    const bullet = /^\s*(?:[-*+•]|\d+[.)])\s+(.+?)\s*$/.exec(line);
    return !bullet || !notes.has(bullet[1].replace(/\s+/g, " "));
  });
  return kept.length === lines.length ? body : kept.join("\n").replace(/\n{3,}/g, "\n\n").trim();
}

function fieldHref(field: string | null | undefined): string {
  if (!field) return "#/application";
  const local = localField(field);
  if (DETAIL_IDS.has(local)) return `#/questions?focus=field-${encodeURIComponent(local)}`;
  const process = Object.entries(PROCESS_FACT).find(([, value]) => value === local)?.[0];
  if (process) return `#/questions?focus=field-${process}`;
  if (local === "jurisdiction" || local === "authority") return "#/questions?focus=authority";
  if (/^(evidence|professional|responsible_professional)/.test(local)) return "#/questions?focus=section-d";
  if (/^(section_c|provisions)/.test(local)) return "#/references";
  return "#/application";
}

export interface RequestedItemRow {
  label: string;
  href: string;
  state: "open" | "unsaved" | "pending" | "review";
  status: string;
  tone: "blocking" | "warning" | "pending";
}

/** Use the current shared gaps and acknowledged facts, never the newest officer follow-up. */
export function requestedItemRow(c: Case, gaps: Gap[], item: MessageItem, saved: boolean, checked = false): RequestedItemRow {
  const uncertainty = requestedUncertaintyRow(c, item, saved);
  if (uncertainty) return uncertainty;
  const field = item.field ? localField(item.field) : null;
  // A gap's id can change from the server's D04:* to the browser's detail-* after an edit.
  const gap = gaps.find((g) => item.gap_id && g.id === item.gap_id)
    ?? gaps.find((g) => field && g.field && localField(g.field) === field);
  const key = gap ? gapKey(c, gap) : null;
  const base = { label: requestedItemLabel(item), href: gap ? key ? `#/questions?focus=${encodeURIComponent(key)}` : calmHref(gap.href) : fieldHref(item.field) };
  if (gap) return { ...base, state: "open", status: "Still to address", tone: gap.severity === "blocking" && gap.submissionBlocking !== false ? "blocking" : "warning" };

  const fact = field ? [...c.facts].reverse().find((f) => localField(f.field) === field) : undefined;
  const answered = fact?.status === "confirmed" && fact.value != null && String(fact.value).trim() !== "";
  // An absent custom/legacy gap alone is not evidence that its freeform instruction was met.
  if (!answered && !checked) return { ...base, state: "review", status: "Review officer instruction", tone: "warning" };
  if (!saved) return { ...base, state: "unsaved", status: "Save correction before resubmitting", tone: "pending" };
  return { ...base, state: "pending", status: "Awaiting officer confirmation", tone: "pending" };
}
