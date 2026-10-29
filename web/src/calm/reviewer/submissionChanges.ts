import type { SubmissionChange } from "../../api/types.gen";
import { changeLabel } from "./formFields";

/** Changes to fields on the form only. Old rounds stored the same evidence attribute as both a fact and listing. */
export function visibleSubmissionChanges(changes: readonly SubmissionChange[]): SubmissionChange[] {
  const byField = new Map(changes.map(change => [change.field, change]));
  return changes.filter(change => {
    if (!changeLabel(change.field, () => null)) return false;
    if (!change.field.startsWith("evidence.") || !change.field.includes(".listing.")) return true;
    const fact = byField.get(change.field.replace(".listing.", "."));
    // Keep conflicting representations visible; display never edits the saved history.
    return !fact || fact.before !== change.before || fact.after !== change.after;
  });
}
