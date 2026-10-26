import { localField } from "../../intakeFields";
import type { Action } from "../../model";
import type { Case } from "../../types";
import { blockAction, blockField, type DocBlock, type DocSection } from "./document";

export interface Suggestion {
  id: string; blockId: string; origin: "rewrite" | "draft"; before: string; after: string; factId?: string;
}
export interface RewriteResult { replacement: string; cited: string[]; removed_citations: string[]; notice: string | null }
export interface Passage { blockId: string; text: string; start: number; end: number }

export function canRewrite(block: DocBlock): boolean {
  return block.target.kind === "process" || block.target.kind === "detail" && (block.target.field === "alternative" || block.target.section === "C");
}

/** The server replaces only the selected range. The staleness basis is always the entire block. */
export function rewriteSuggestion(id: string, passage: Passage, result: RewriteResult): Suggestion {
  const { text, start, end } = passage;
  if (start < 0 || end < start || end > text.length) throw new Error("The selected passage changed. Select it again.");
  return { id, blockId: passage.blockId, origin: "rewrite", before: text,
    after: start === end ? result.replacement : text.slice(0, start) + result.replacement + text.slice(end) };
}

export function draftSuggestions(c: Case, sections: readonly DocSection[]): Suggestion[] {
  return sections.flatMap(s => s.blocks).filter(canRewrite).flatMap(block => {
    const fact = [...c.facts].reverse().find(f => localField(f.field) === localField(blockField(block)) && f.kind === "proposed");
    const after = typeof fact?.value === "string" ? fact.value : !fact ? block.draft : undefined;
    if (!after?.trim() || after === block.text) return [];
    return [{ id: fact ? `draft-${fact.id}` : `lookup-draft-${block.id}`, blockId: block.id, origin: "draft", before: block.text,
      after, ...(fact ? { factId: fact.id } : {}) } satisfies Suggestion];
  });
}

export const freshSuggestions = (suggestions: readonly Suggestion[], blocks: readonly DocBlock[]): Suggestion[] =>
  suggestions.filter(s => blocks.some(b => b.id === s.blockId && b.text === s.before && b.target.kind !== "card") && s.after !== s.before);

export function acceptSuggestion(suggestion: Suggestion, block: DocBlock): Action | null {
  return suggestion.blockId === block.id && suggestion.before === block.text ? blockAction(block, suggestion.after) : null;
}
export function rejectSuggestion(suggestion: Suggestion): Action | null {
  return suggestion.factId ? { type: "dismissFact", id: suggestion.factId } : null;
}

/** Common prefix/suffix keep a small rewrite legible without altering whitespace. */
export function changedWords(before: string, after: string): { prefix: string; removed: string; added: string; suffix: string } {
  let start = 0, end = 0;
  while (start < before.length && start < after.length && before[start] === after[start]) start++;
  while (end < before.length - start && end < after.length - start && before[before.length - end - 1] === after[after.length - end - 1]) end++;
  return { prefix: before.slice(0, start), removed: before.slice(start, before.length - end), added: after.slice(start, after.length - end), suffix: end ? before.slice(-end) : "" };
}
