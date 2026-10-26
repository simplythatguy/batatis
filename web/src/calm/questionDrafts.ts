/** Unconfirmed editors. Their server snapshot never confirms an answer. */
import type { DraftText } from "../api/types.gen";
export type { DraftText } from "../api/types.gen";

export class QuestionDrafts {
  private account: string | null = null;
  private text = new Map<string, DraftText>();
  private choices = new Map<string, Record<string, string>>();
  private adopted = new Set<string>();
  private listeners = new Set<(scope: string) => void>();

  subscribe(listener: (scope: string) => void) {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  }

  selectAccount(account: string | null) {
    if (account !== this.account) { this.clear(); this.account = account; }
  }

  /** Saved IDs survive reopening. A visit generation separates cases before their first save. */
  scope(account: string | null, generation: number, engineId: string | null): string {
    this.selectAccount(account);
    const draft = JSON.stringify([account, "draft", generation]);
    if (!engineId) return draft;
    const saved = JSON.stringify([account, "case", engineId]);
    if (!this.adopted.has(draft)) {
      this.adopted.add(draft);
      for (const [key, value] of [...this.text]) {
        const [scope, card] = JSON.parse(key) as [string, string];
        if (scope !== draft) continue;
        const target = JSON.stringify([saved, card]);
        if (!this.text.has(target)) this.text.set(target, value);
        this.text.delete(key);
      }
      const choices = this.choices.get(draft);
      if (choices) { this.choices.set(saved, { ...choices, ...this.readChoices(saved) }); this.choices.delete(draft); }
    }
    return saved;
  }

  read(scope: string, card: string, base: string): string {
    const key = JSON.stringify([scope, card]);
    const draft = this.text.get(key);
    return draft?.value ?? base;
  }

  conflicted(scope: string, card: string, base: string): boolean {
    const draft = this.text.get(JSON.stringify([scope, card]));
    return Boolean(draft && draft.base !== base && draft.value !== base);
  }

  write(scope: string, card: string, base: string, value: string) {
    const key = JSON.stringify([scope, card]);
    if (this.read(scope, card, base) === value) return;
    if (value === base) this.text.delete(key);
    else this.text.set(key, { base, value });
    for (const listener of this.listeners) listener(scope);
  }

  readChoices(scope: string) { return this.choices.get(scope) ?? {}; }
  writeChoices(scope: string, value: Record<string, string>) {
    if (JSON.stringify(this.readChoices(scope)) === JSON.stringify(value)) return;
    this.choices.set(scope, value);
    for (const listener of this.listeners) listener(scope);
  }
  confirm(scope: string, card: string, value: string) {
    const key = JSON.stringify([scope, card]), draft = this.text.get(key);
    // An acknowledgement of older typing never consumes a later edit.
    if (!draft || draft.value.trim() !== value.trim()) return;
    this.text.delete(key);
    for (const listener of this.listeners) listener(scope);
  }
  snapshot(scope: string): { question_text: Record<string, DraftText>; choices: Record<string, string> } {
    const question_text: Record<string, DraftText> = {};
    for (const [key, value] of this.text) {
      const [owner, card]: unknown[] = JSON.parse(key);
      if (owner === scope && typeof card === "string") question_text[card] = { ...value };
    }
    return { question_text, choices: { ...this.readChoices(scope) } };
  }
  restore(scope: string, saved: ReturnType<QuestionDrafts["snapshot"]>) {
    for (const key of this.text.keys()) {
      const [owner]: unknown[] = JSON.parse(key);
      if (owner === scope) this.text.delete(key);
    }
    for (const [card, value] of Object.entries(saved.question_text)) this.text.set(JSON.stringify([scope, card]), { ...value });
    this.choices.set(scope, { ...saved.choices });
  }
  clear() { this.text.clear(); this.choices.clear(); this.adopted.clear(); }
}

export const questionDrafts = new QuestionDrafts();
