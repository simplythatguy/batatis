/**
 * Assistant state shared by every entry point (Ask, Cmd/Ctrl+J, "Ask the assistant" links).
 * Answers come only from POST /assist; nothing is written locally when it is unavailable.
 */
import { useSyncExternalStore } from "react";
import { AccountsError, accounts } from "../../api/accounts";

export interface AssistContext {
  /** Screen name sent to the engine: "question", "review", "application", "code", "drawer". */
  screen: string;
  focus?: { kind: string; id: string };
  /** What the panel says it is looking at, e.g. "question 10 and 9.23.17.3.(1)". */
  label: string;
  /** Suggestion chips for this context. */
  suggestions?: string[];
}

export interface Turn {
  role: "user" | "assistant";
  text: string;
  cited?: string[];
  removed?: string[];
  notice?: string | null;
}

export interface AssistantState {
  open: boolean;
  context: AssistContext;
  turns: Turn[];
  pending: boolean;
  /** Last failure: 503 means "not on this server"; the panel shows it instead of an answer. */
  error: { status: number; text: string; technical: string; retryAt: number | null } | null;
}

const DEFAULT_CONTEXT: AssistContext = { screen: "app", label: "your application", suggestions: ["What happens after I submit?", "What is an alternative solution?"] };

let state: AssistantState = { open: false, context: DEFAULT_CONTEXT, turns: [], pending: false, error: null };
const listeners = new Set<() => void>();
const set = (next: Partial<AssistantState>) => {
  state = { ...state, ...next };
  for (const l of listeners) l();
};
let ctl: AbortController | null = null;
let caseIdNow: string | null = null;

/** The engine case the assistant may read. Set by the shell whenever it changes. */
export function setAssistantCase(id: string | null) {
  if (id !== caseIdNow) {
    caseIdNow = id;
    ctl?.abort();
    set({ turns: [], pending: false, error: null });
  }
}

/** Where the user is now; the panel shows it and sends it with the next question. */
export function setAssistantContext(context: AssistContext) {
  if (context.label === state.context.label && context.screen === state.context.screen && context.focus?.id === state.context.focus?.id) return;
  set({ context });
}

export function openAssistant(context?: AssistContext, question?: string) {
  set({ open: true, ...(context ? { context } : {}) });
  if (question) void ask(question);
}

export function closeAssistant() {
  set({ open: false });
}

export function toggleAssistant() {
  set({ open: !state.open });
}

export async function ask(question: string) {
  const q = question.trim();
  if (!q || state.pending) return;
  ctl?.abort();
  const c = new AbortController();
  ctl = c;
  const history = state.turns.slice(-8).map((t) => ({ role: t.role, text: t.text }));
  set({ turns: [...state.turns, { role: "user", text: q }], pending: true, error: null });
  try {
    const r = await accounts.assist(
      { ...(caseIdNow ? { case_id: caseIdNow } : {}), screen: state.context.screen, ...(state.context.focus ? { focus: state.context.focus } : {}), question: q, history },
      c.signal,
    );
    if (c.signal.aborted) return;
    set({ turns: [...state.turns, { role: "assistant", text: r.answer, cited: r.cited ?? [], removed: r.removed_citations ?? [], notice: r.notice }], pending: false });
  } catch (e) {
    if (c.signal.aborted) return;
    const err = e instanceof AccountsError ? e : null;
    const status = err?.status ?? 0;
    set({
      pending: false,
      error: {
        status,
        text: status === 503 || status === 404 || status === 0 ? "The assistant isn't available on this server." : err?.detail ?? "The assistant did not answer.",
        technical: err?.technical ?? String(e),
        retryAt: status === 429 ? Date.now() + (err?.retryAfter ?? 15) * 1000 : null,
      },
    });
  }
}

function subscribe(l: () => void) {
  listeners.add(l);
  return () => listeners.delete(l);
}

export function useAssistant(): AssistantState {
  return useSyncExternalStore(subscribe, () => state, () => state);
}

/**
 * Split an answer into prose and quoted code. Lines starting with ">" are quotes; the engine
 * keeps verbatim code text in quotes so it can be shown in the code-text style.
 */
export function answerBlocks(text: string): { kind: "p" | "quote"; text: string }[] {
  const out: { kind: "p" | "quote"; text: string }[] = [];
  let cur: { kind: "p" | "quote"; lines: string[] } | null = null;
  const flush = () => {
    if (cur && cur.lines.join(" ").trim()) out.push({ kind: cur.kind, text: cur.lines.join(" ").replace(/\s+/g, " ").trim() });
    cur = null;
  };
  for (const line of text.split("\n")) {
    const quote = /^\s*>/.test(line);
    if (!line.trim()) { flush(); continue; }
    const kind = quote ? "quote" : "p";
    if (!cur || cur.kind !== kind) { flush(); cur = { kind, lines: [] }; }
    cur.lines.push(quote ? line.replace(/^\s*>\s?/, "") : line);
  }
  flush();
  return out;
}
