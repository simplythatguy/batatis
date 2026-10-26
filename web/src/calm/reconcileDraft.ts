import type { DraftSnapshot } from "../api/sync";
import type { ApplicantDraft } from "../api/types.gen";
import { evidenceSlot } from "../model";
import { factSignature } from "../rules";
import type { Case, Fact } from "../types";
import { DESCRIPTION_DRAFT } from "./applicantDraft";
import { selectedArticles } from "./openCase";

export type ReconciliationChoices = Record<string, "mine" | "saved">;
export type ReconciliationConflict = { id: string; label: string; mine: string; saved: string };
export type SaveConflictReview = { kind: "closed" } | { kind: "loading" } | {
  kind: "review"; conflicts: ReconciliationConflict[]; saving: boolean; note: string;
};

export interface ReconciliationInput {
  local: Case;
  remote: Case;
  draft: ApplicantDraft;
  savedDraft: ApplicantDraft | null | undefined;
  baselineDraft: ApplicantDraft | null | undefined;
  localFacts: Map<string, Fact | null>;
  remoteFacts: Map<string, Fact | null>;
  baselineAuthority: string | null | undefined;
  localSelectionChanged: boolean;
  remoteSelectionChanged: boolean;
  baselineEvidence: Fact[];
}

const key = (value: unknown): string | undefined => JSON.stringify(value, (_key, item: unknown) =>
  item && typeof item === "object" && !Array.isArray(item) ? Object.fromEntries(Object.entries(item).sort(([a], [b]) => a.localeCompare(b))) : item);
const equal = (left: unknown, right: unknown) => key(left) === key(right);
const show = (value: unknown): string => value === undefined || value === null ? "Removed / unanswered"
  : typeof value === "string" ? value || "Empty" : JSON.stringify(value, null, 2);
const fieldLabel = (field: string) => {
  const text = field.replace(/^process\./, "").replace(/([a-z])([A-Z])/g, "$1 $2").replace(/[_.]/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
};

/** Three-way review: untouched local fields take the saved value. Overlapping changes require
 * an explicit choice; this function neither adopts a version nor mutates either draft. */
export function reconcileDraft(input: ReconciliationInput, choices: ReconciliationChoices = {}) {
  const { local, remote, draft, savedDraft, baselineDraft } = input;
  const conflicts: ReconciliationConflict[] = [];
  function choose<T>(id: string, label: string, mine: T, saved: T, localChanged: boolean, remoteChanged: boolean, display: (value: T) => string = show): T {
    if (!localChanged) return saved;
    if (!remoteChanged || equal(mine, saved)) return mine;
    conflicts.push({ id, label, mine: display(mine), saved: display(saved) });
    return choices[id] === "saved" ? saved : mine;
  }
  function value<T>(id: string, label: string, base: T, mine: T, saved: T, display?: (item: T) => string): T {
    return choose(id, label, mine, saved, !equal(mine, base), !equal(saved, base), display);
  }
  function record<T>(prefix: string, label: string, base: Record<string, T>, mine: Record<string, T>, saved: Record<string, T>, display?: (item: T | undefined) => string) {
    const result: Record<string, T> = {};
    for (const id of new Set([...Object.keys(base), ...Object.keys(mine), ...Object.keys(saved)])) {
      const next = value<T | undefined>(`${prefix}:${id}`, label, base[id], mine[id], saved[id], display);
      if (next !== undefined) result[id] = next;
    }
    return result;
  }
  function membership(prefix: string, base: string[], mine: string[], saved: string[]) {
    return [...new Set([...saved, ...mine, ...base])].filter(id =>
      value(`${prefix}:${id}`, "Question progress", base.includes(id), mine.includes(id), saved.includes(id)));
  }
  const localFacts = new Map(local.facts.map(fact => [fact.field, fact]));
  const remoteFacts = new Map(remote.facts.map(fact => [fact.field, fact]));
  const facts: Fact[] = [];
  for (const field of new Set([...localFacts.keys(), ...remoteFacts.keys()])) {
    if (field === "project.description") continue;
    const fact = choose(`fact:${field}`, fieldLabel(field), localFacts.get(field), remoteFacts.get(field),
      input.localFacts.has(field), input.remoteFacts.has(field), fact => fact ? show(fact.value) : show(null));
    if (fact) facts.push(fact);
  }
  const localDescription = { text: local.description, fact: localFacts.get("project.description"), editor: draft.question_text[DESCRIPTION_DRAFT] };
  const savedDescription = { text: remote.description, fact: remoteFacts.get("project.description"), editor: savedDraft?.question_text[DESCRIPTION_DRAFT] };
  const description = choose("description", "Description", localDescription, savedDescription,
    input.localFacts.has("project.description") || !equal(localDescription.editor, baselineDraft?.question_text[DESCRIPTION_DRAFT]),
    input.remoteFacts.has("project.description") || !equal(savedDescription.editor, baselineDraft?.question_text[DESCRIPTION_DRAFT]), item => show(item.text));
  if (description.fact) facts.push(description.fact);
  const withoutDescription = (text: ApplicantDraft["question_text"] = {}) => Object.fromEntries(Object.entries(text).filter(([id]) => id !== DESCRIPTION_DRAFT));
  const text = record("text", "Unfinished answer", withoutDescription(baselineDraft?.question_text), withoutDescription(draft.question_text), withoutDescription(savedDraft?.question_text), item => show(item?.value));
  if (description.editor) text[DESCRIPTION_DRAFT] = description.editor;
  const authority = choose("authority", "Reviewing authority", local.authority, remote.authority,
    (local.authority || null) !== input.baselineAuthority, (remote.authority || null) !== input.baselineAuthority);
  const selected = choose("selection", "Code check answers", selectedArticles(local), selectedArticles(remote), input.localSelectionChanged, input.remoteSelectionChanged);
  const mergedDraft: ApplicantDraft = {
    role: value("role", "Applicant type", baselineDraft?.role ?? local.applicantType, draft.role, savedDraft?.role ?? remote.applicantType),
    intake_file_ids: value("files", "Reading attachments", baselineDraft?.intake_file_ids ?? [], draft.intake_file_ids ?? [], savedDraft?.intake_file_ids ?? []),
    question_text: text,
    choices: record("choice", "Answer choice", baselineDraft?.choices ?? {}, draft.choices, savedDraft?.choices ?? {}),
    skipped: membership("skipped", baselineDraft?.skipped ?? [], draft.skipped, savedDraft?.skipped ?? []),
    seen: membership("seen", baselineDraft?.seen ?? [], draft.seen, savedDraft?.seen ?? []),
    authority_unsure: value("authority-unsure", "Authority answer", baselineDraft?.authority_unsure ?? false, draft.authority_unsure, savedDraft?.authority_unsure ?? false),
    packages: record("package", "Standing package answer", baselineDraft?.packages ?? {}, draft.packages, savedDraft?.packages ?? {}),
    rule_unsure: membership("rule-unsure", baselineDraft?.rule_unsure ?? [], draft.rule_unsure, savedDraft?.rule_unsure ?? []),
    evidence_drafts: record("evidence-draft", "Unfinished document", baselineDraft?.evidence_drafts ?? {}, draft.evidence_drafts, savedDraft?.evidence_drafts ?? {}),
  };
  const evidenceKey = (values: Fact[], id: string) => key(values.filter(fact => evidenceSlot(fact.field) === id).map(factSignature));
  const evidenceChanged = (id: string) => evidenceKey(input.baselineEvidence, id) !== evidenceKey(remote.facts, id);
  const listedEvidence = (local.listedEvidence ?? []).filter(item => choose(`document:${item.id}`, "Document changes", item, undefined, true, evidenceChanged(item.id), item => item ? show(item.description) : "Keep saved document") !== undefined);
  const deletedEvidence = (local.deletedEvidence ?? []).filter(id => choose(`document:${id}`, "Remove document", id, undefined, true, evidenceChanged(id), item => item ? "Remove document" : "Keep saved document") !== undefined);
  const files = (mergedDraft.intake_file_ids ?? []).flatMap(id => {
    const file = [...remote.files, ...local.files].find(file => file.engineId === id);
    return file ? [file] : [];
  }).concat(local.files.filter(file => !file.engineId));
  const snapshot: DraftSnapshot = { facts, authority, selected, draft: mergedDraft };
  return { snapshot, conflicts, files, listedEvidence, deletedEvidence };
}
