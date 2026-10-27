import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { accounts } from "../../api/accounts";
import { useCase } from "../../store";
import { openAssistant, type AssistContext } from "../assistant/assistant";
import { useAccount } from "../account";
import { useCurrentApplication } from "../begin";
import { arrange } from "../comments/thread";
import { workspaceApi, workspaceFailure } from "./api";
import { blockAction, buildDocument, type DocBlock, type OfficerRequest } from "./document";
import { acceptedAI, entryId, historyEntry, inverseEntry, type HistoryEntry } from "./history";
import type { PassageSelection } from "./PaperBlock";
import {
  acceptSuggestion, canRewrite, draftSuggestions, freshSuggestions, rejectSuggestion, rewriteRange, rewriteSuggestion,
  type Suggestion,
} from "./suggestions";
import { useWorkspace } from "./useWorkspace";

export interface Toast { text: string; undo?: HistoryEntry }

export function passageContext(block: DocBlock, passage = block.text): AssistContext {
  return {
    screen: "application",
    label: block.label,
    focus: { kind: "passage", id: block.id, prompt: passage.slice(0, 600), why: block.label.slice(0, 1200) },
  };
}

/** What the signers attest to, as the browser sees it. Signatures read as current only while this is unchanged. */
function contentKeyOf(c: ReturnType<typeof useCase>["c"]): string {
  return JSON.stringify([
    c.description, c.authority,
    c.facts.filter(f => f.status === "confirmed" && f.kind !== "proposed").map(f => [f.field, f.value]),
    c.process, c.sectionC.map(r => [r.provision, r.pairs]),
    c.candidates.filter(a => a.answer === "yes").map(a => a.provision),
  ]);
}

/**
 * Everything the paper does to the application: typing, AI suggestions, undo, restore, Ask and Rewrite.
 * Every write goes through the store's own actions, and every change lands in the history.
 */
export function useEditing() {
  const { c, gaps, engineId, dispatch, saveDraft, readSync } = useCase();
  const { app, locked } = useCurrentApplication();
  const account = useAccount();
  const [requests, setRequests] = useState<OfficerRequest[]>([]);
  const [requestsFailed, setRequestsFailed] = useState(false);
  const [requestAttempt, setRequestAttempt] = useState(0);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const seenDrafts = useRef(new Set<string>());
  const [selection, setSelection] = useState<PassageSelection | null>(null);
  const [rewriteBusy, setRewriteBusy] = useState(false);
  const rewriting = useRef<AbortController | null>(null);
  const [toast, setToast] = useState<Toast | null>(null);
  // Undo walks back through this visit's own changes only, never an earlier session's.
  const visitStart = useRef(new Date().toISOString());
  const undone = useRef(new Set<string>());

  const sections = useMemo(() => buildDocument(c, gaps, requests), [c, gaps, requests]);
  const blocks = useMemo(() => sections.flatMap(s => s.blocks), [sections]);
  const contentKey = contentKeyOf(c);
  const workspace = useWorkspace(contentKey);
  const live = useRef({ blocks, locked });
  live.current = { blocks, locked };

  // A writing draft the applicant already acted on (it has history) is not offered again.
  const fresh = freshSuggestions(suggestions, blocks)
    .filter(s => s.origin !== "draft" || s.factId || !workspace.history.some(e => e.block === s.blockId));

  useEffect(() => {
    if (!engineId || account.phase !== "signed-in") return;
    const ctl = new AbortController();
    setRequestsFailed(false);
    accounts.messages(engineId, ctl.signal).then(messages => {
      if (ctl.signal.aborted) return;
      const thread = arrange(messages);
      const current = [...(thread.latest ? [thread.latest] : []), ...thread.since.filter(m => m.author.role === "reviewer")];
      setRequests(current.flatMap(m => m.items.map((item, n) => ({ ...item, id: `${m.id}:${n}` }))));
    }).catch(() => { if (!ctl.signal.aborted) setRequestsFailed(true); });
    return () => ctl.abort();
  }, [engineId, account.phase, app?.updated_at, requestAttempt]);

  useEffect(() => {
    const incoming = draftSuggestions(c, sections).filter(s => !seenDrafts.current.has(s.id));
    for (const s of incoming) seenDrafts.current.add(s.id);
    if (incoming.length) setSuggestions(previous => [...previous, ...incoming]);
  }, [c, sections]);

  useEffect(() => {
    setSuggestions(previous => {
      const next = freshSuggestions(previous, blocks);
      return next.length === previous.length ? previous : next;
    });
    // Only a content change can make a suggestion stale.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contentKey]);

  useEffect(() => () => rewriting.current?.abort(), []);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 20000);
    return () => clearTimeout(timer);
  }, [toast]);

  const say = (text: string) => { if (text) setToast({ text }); };

  /** Typing: the store updates on every keystroke; the history coalesces a burst into one entry. */
  function type(block: DocBlock, before: string, after: string) {
    if (live.current.locked) return;
    // Typing into words the AI drafted keeps them marked as AI-drafted, now edited by the applicant.
    const action = blockAction(block, after, acceptedAI(workspace.history, block.id, block.text) ? "ai" : undefined);
    if (!action) return;
    dispatch(action);
    workspace.journal.edits.change(block.id, block.label, before, after);
  }

  function change(block: DocBlock, after: string, by: HistoryEntry["by"], origin?: "ai"): HistoryEntry | undefined {
    if (live.current.locked) return;
    workspace.journal.edits.flush(block.id);
    const action = blockAction(block, after, origin);
    const entry = historyEntry(block.id, block.label, block.text, after, by);
    if (!action || !entry) return;
    dispatch(action);
    workspace.journal.add(entry);
    return entry;
  }

  function undo(target?: HistoryEntry) {
    if (live.current.locked) return;
    workspace.journal.edits.flush();
    const entry = target ?? [...workspace.journal.getSnapshot().entries].reverse()
      .find(e => e.at >= visitStart.current && e.by !== "restore" && !undone.current.has(e.id));
    if (!entry) { setToast({ text: "Nothing to undo. Older versions are in History." }); return; }
    const block = live.current.blocks.find(b => b.id === entry.block);
    if (!block || !inverseEntry(entry, block.text)) {
      setToast({ text: `${entry.label} changed again since. Restore it from History.` });
      return;
    }
    if (!change(block, entry.before, "restore")) return;
    undone.current.add(entry.id);
    setToast({ text: `Undid ${entry.label}` });
  }

  function restore(entry: HistoryEntry) {
    const block = live.current.blocks.find(b => b.id === entry.block);
    if (block && change(block, entry.after, "restore", entry.by === "ai" ? "ai" : undefined)) setToast({ text: `Restored ${entry.label}` });
  }

  function accept(suggestion: Suggestion) {
    const block = live.current.blocks.find(b => b.id === suggestion.blockId);
    if (!block || live.current.locked || !acceptSuggestion(suggestion, block)) return;
    // Consume a writing draft too, so it cannot come back after a later edit.
    if (suggestion.factId) dispatch({ type: "dismissFact", id: suggestion.factId });
    const entry = change(block, suggestion.after, "ai", "ai");
    setSuggestions(previous => previous.filter(s => s.id !== suggestion.id));
    if (entry) setToast({ text: "AI change accepted", undo: entry });
  }

  function reject(suggestion: Suggestion) {
    if (live.current.locked) return;
    const action = rejectSuggestion(suggestion);
    if (action) dispatch(action);
    setSuggestions(previous => previous.filter(s => s.id !== suggestion.id));
  }

  function ask(block: DocBlock, passage?: string) {
    openAssistant(passageContext(block, passage));
    setSelection(null);
  }

  async function rewrite(instruction: string) {
    const passage = selection;
    const block = passage && live.current.blocks.find(b => b.id === passage.blockId);
    if (!passage || !block || locked || rewriteBusy || !canRewrite(block)) return;
    const ctl = new AbortController();
    rewriting.current?.abort();
    rewriting.current = ctl;
    const unchanged = () => live.current.blocks.find(b => b.id === block.id)?.text === passage.text;
    setRewriteBusy(true);
    workspace.journal.edits.flush(block.id);
    try {
      const id = await saveDraft();
      if (ctl.signal.aborted) return;
      if (!id || !readSync().saved) { say("Save your application before rewriting."); return; }
      if (live.current.locked || !unchanged()) { say("That passage changed. Select it again."); return; }
      const result = await workspaceApi.rewrite(id, { field: block.id, text: passage.text, ...rewriteRange(passage), instruction }, ctl.signal);
      if (ctl.signal.aborted) return;
      if (!unchanged()) { say("That passage changed while the AI was writing. Its suggestion was dropped."); return; }
      const suggestion = rewriteSuggestion(entryId(), passage, result);
      setSuggestions(previous => [...previous.filter(s => s.blockId !== block.id || s.origin !== "rewrite"), suggestion]);
      say(suggestion.after === suggestion.before ? "No change suggested." : "");
      setSelection(null);
    } catch (e) {
      if (!ctl.signal.aborted) say(workspaceFailure(e, "Rewriting"));
    } finally {
      if (!ctl.signal.aborted) setRewriteBusy(false);
    }
  }

  const closeSelection = useCallback(() => setSelection(null), []);

  return {
    sections, blocks, workspace, locked,
    requests, requestsFailed, retryRequests: () => setRequestAttempt(n => n + 1),
    suggestions: fresh, selection, setSelection, closeSelection, rewriteBusy,
    toast, clearToast: () => setToast(null),
    type, undo, restore, accept, reject, ask, rewrite,
  };
}
export type Editing = ReturnType<typeof useEditing>;
