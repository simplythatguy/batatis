/** Cached reads for the code library: the table of contents, verbatim text and article context. */
import { useCallback, useEffect, useState } from "react";
import { engine, EngineError, type CodeRecord } from "../api/client";
import { codeLibrary, type CodeContext, type CodeToc } from "../api/codeLibrary";

type Load<T> = { state: "loading" } | { state: "ready"; value: T } | { state: "error"; error: Error };

let toc: Promise<CodeToc> | null = null;
const contexts = new Map<string, Promise<CodeContext>>();
const texts = new Map<string, Promise<CodeRecord>>();

function cached<T>(map: Map<string, Promise<T>>, key: string, run: () => Promise<T>): Promise<T> {
  let p = map.get(key);
  if (!p) {
    p = run();
    map.set(key, p);
    // A failure is not cached; the next ask tries again.
    p.catch(() => map.delete(key));
  }
  return p;
}

export function loadToc(): Promise<CodeToc> {
  if (!toc) {
    toc = codeLibrary.toc("B");
    toc.catch(() => { toc = null; });
  }
  return toc;
}

export const loadContext = (id: string) => cached(contexts, id, () => codeLibrary.context(id, "B"));
export const loadText = (id: string) => cached(texts, id, () => engine.provision(id, "B"));

function useLoad<T>(key: string | null, run: (key: string) => Promise<T>): Load<T> & { retry: () => void } {
  const [attempt, setAttempt] = useState(0);
  const [got, setGot] = useState<{ key: string | null; attempt: number; load: Load<T> }>({ key: null, attempt: -1, load: { state: "loading" } });
  useEffect(() => {
    if (!key) return;
    let live = true;
    setGot({ key, attempt, load: { state: "loading" } });
    run(key).then(
      (value) => { if (live) setGot({ key, attempt, load: { state: "ready", value } }); },
      (error: unknown) => { if (live) setGot({ key, attempt, load: { state: "error", error: error instanceof Error ? error : new Error(String(error)) } }); },
    );
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, attempt]);
  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  const load: Load<T> = got.key === key && got.attempt === attempt ? got.load : { state: "loading" };
  return { ...load, retry };
}

export const useToc = (enabled = true) => useLoad<CodeToc>(enabled ? "B" : null, () => loadToc());
export const useContext = (id: string | null) => useLoad<CodeContext>(id, loadContext);
export const useText = (id: string | null) => useLoad<CodeRecord>(id, loadText);

export interface TocEntry {
  id: string;
  title: string | null;
  /** "Part 9 › 9.27. Cladding › 9.27.3. Sheathing Membranes" */
  path: string;
}

/** Article id → title and readable path, for palette rows and hover cards. */
export function tocIndex(t: CodeToc | undefined): Map<string, TocEntry> {
  const out = new Map<string, TocEntry>();
  if (!t) return out;
  for (const p of t.parts) {
    const part = `Part ${p.part}`;
    for (const s of p.sections) {
      const sec = `${s.id} ${s.title ?? ""}`.trim();
      for (const a of s.articles) out.set(a.id, { id: a.id, title: a.title, path: `${part} › ${sec}` });
      for (const ss of s.subsections) {
        const sub = `${ss.id} ${ss.title ?? ""}`.trim();
        for (const a of ss.articles) out.set(a.id, { id: a.id, title: a.title, path: `${part} › ${sec} › ${sub}` });
      }
    }
  }
  return out;
}

export function errorText(e: unknown): { text: string; technical: string } {
  if (e instanceof EngineError) return { text: e.detail, technical: e.technical };
  if (e instanceof Error) return { text: "Something went wrong loading the code.", technical: e.message };
  return { text: "Something went wrong loading the code.", technical: String(e) };
}

/** A branch the palette asked the library to open (consumed once). */
let pendingReveal: string | null = null;
export const setPendingReveal = (key: string | null) => { pendingReveal = key; };
export function takePendingReveal(): string | null {
  const k = pendingReveal;
  pendingReveal = null;
  return k;
}
