import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { engineGeneration } from "../../api/sync";
import { useCase } from "../../store";
import { accountSession } from "../account";
import { useCurrentApplication } from "../begin";
import { workspaceApi, workspaceFailure, type WorkspaceRecord } from "./api";
import { HistoryJournal } from "./history";

export type WorkspaceLoad =
  | { phase: "loading"; record: null; note: string }
  | { phase: "failed"; record: null; note: string }
  | { phase: "ready"; record: WorkspaceRecord; basis: string; note: string };

const journals = new Map<string, HistoryJournal>();
let journalSession = -1;
function journalFor(session: number, generation: number): HistoryJournal {
  if (journalSession !== session) { journals.clear(); journalSession = session; }
  const key = `${session}:${generation}`;
  let journal = journals.get(key);
  if (!journal) { journal = new HistoryJournal(); journals.set(key, journal); }
  return journal;
}

export function useWorkspace(contentKey: string) {
  const store = useCase();
  const { locked } = useCurrentApplication();
  const { engineId, factsEpoch } = store;
  const [state, setState] = useState<WorkspaceLoad>({ phase: "loading", record: null, note: "Loading signatures…" });
  const [attempt, setAttempt] = useState(0);
  const [historyNote, setHistoryNote] = useState("");
  const live = useRef({ store, contentKey, locked });
  live.current = { store, contentKey, locked };
  const ctl = useRef<AbortController | null>(null);
  const lifetime = useRef<AbortController>(new AbortController());
  const session = accountSession(), generation = engineGeneration();
  const journal = useMemo(() => journalFor(session, generation), [session, generation]);
  const history = useSyncExternalStore(journal.subscribe, journal.getSnapshot, journal.getSnapshot);

  const reload = useCallback(async () => {
    ctl.current?.abort();
    const request = new AbortController();
    ctl.current = request;
    const current = () => !request.signal.aborted && !lifetime.current.signal.aborted && accountSession() === session && engineGeneration() === generation;
    if (!engineId) {
      setState({ phase: "failed", record: null, note: "Save your application to enable signing." });
      return;
    }
    const basis = live.current.store.readSync().saved ? live.current.contentKey : "";
    try {
      const record = await workspaceApi.get(engineId, request.signal);
      if (!current()) return;
      journal.load(record.history);
      setState({ phase: "ready", record, basis, note: "" });
    } catch (e) {
      if (current()) setState({ phase: "failed", record: null, note: workspaceFailure(e, "Signing") });
    }
  }, [engineId, session, generation, journal]);

  useEffect(() => { void reload(); return () => ctl.current?.abort(); }, [reload, factsEpoch, attempt]);
  useEffect(() => {
    const scope = new AbortController();
    lifetime.current = scope;
    return () => { journal.edits.flush(); scope.abort(); };
  }, [journal]);

  const flushHistory = useCallback(async () => {
    journal.edits.flush();
    if (!journal.queue.size || live.current.locked) return;
    try {
      const current = live.current.store;
      const id = await current.saveDraft();
      if (lifetime.current.signal.aborted || accountSession() !== session || engineGeneration() !== generation) return;
      if (!id || !live.current.store.readSync().saved) throw new Error("Save to sync change history.");
      await journal.flush(entries => workspaceApi.history(id, entries, lifetime.current.signal));
      if (!lifetime.current.signal.aborted) setHistoryNote("");
    } catch (e) {
      if (!lifetime.current.signal.aborted) setHistoryNote(workspaceFailure(e, "History"));
    }
  }, [journal, generation, session]);

  useEffect(() => {
    if (!history.pending || locked) return;
    const timer = setTimeout(() => void flushHistory(), historyNote ? 10000 : 800);
    return () => clearTimeout(timer);
  }, [history.pending, historyNote, attempt, locked, flushHistory]);

  return { state, history: history.entries, historyPending: history.pending, historyNote, journal, flushHistory,
    reload, retry: () => setAttempt(n => n + 1), signal: lifetime.current.signal,
    signaturesCurrent: state.phase === "ready" && state.basis === contentKey && store.readSync().saved };
}
export type WorkspaceController = ReturnType<typeof useWorkspace>;
