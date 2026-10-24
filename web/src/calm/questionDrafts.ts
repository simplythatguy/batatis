/** Visit-local, unconfirmed form answers. Never writes to the case or confirms an answer. */
export class QuestionDrafts {
  private account: string | null = null;
  private text = new Map<string, { base: string; value: string }>();
  private choices = new Map<string, Record<string, string>>();
  private adopted = new Set<string>();

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
    // A confirmed/server answer changed: an older local draft must not overwrite it.
    if (draft && draft.base !== base) this.text.delete(key);
    return draft?.base === base ? draft.value : base;
  }

  write(scope: string, card: string, base: string, value: string) {
    const key = JSON.stringify([scope, card]);
    if (value === base) this.text.delete(key);
    else this.text.set(key, { base, value });
  }

  readChoices(scope: string) { return this.choices.get(scope) ?? {}; }
  writeChoices(scope: string, value: Record<string, string>) { this.choices.set(scope, value); }
  clear() { this.text.clear(); this.choices.clear(); this.adopted.clear(); }
}

export const questionDrafts = new QuestionDrafts();
