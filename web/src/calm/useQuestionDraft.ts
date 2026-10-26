import { useReducer, type SetStateAction } from "react";
import { questionDrafts } from "./questionDrafts";

/** Reopening the exact card restores its text; switching applications uses a separate scope. */
export function useQuestionDraft(account: string | null, generation: number, engineId: string | null, card: string | undefined, base: string) {
  const [, render] = useReducer((n: number) => n + 1, 0);
  const scope = questionDrafts.scope(account, generation, engineId);
  const value = card ? questionDrafts.read(scope, card, base) : "";
  const setValue = (next: string) => { if (card) questionDrafts.write(scope, card, base, next); render(); };
  const choices = questionDrafts.readChoices(scope);
  const setChoices = (next: SetStateAction<Record<string, string>>) => {
    questionDrafts.writeChoices(scope, typeof next === "function" ? next(questionDrafts.readChoices(scope)) : next);
    render();
  };
  const conflict = Boolean(card && questionDrafts.conflicted(scope, card, base));
  const confirmValue = (value: string) => { if (card) questionDrafts.confirm(scope, card, value); render(); };
  return { value, setValue, choices, setChoices, conflict, confirmValue };
}
