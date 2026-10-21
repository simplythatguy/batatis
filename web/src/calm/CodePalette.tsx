import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { engine, EngineError, type CodeHit } from "../api/client";
import { setPendingReveal, tocIndex, useToc } from "./codeData";
import { RelevanceRing } from "./RelevanceRing";
import { BAND_LABEL, rankedIn } from "./relevance";
import { codeHref } from "./routes";
import { articleOf, useRelevance } from "./useRelevance";
import { CIcon, Modal } from "./ui";

/** Any surface can open the palette (the library header, the ... menu); the Shell owns it. */
export const OPEN_PALETTE = "cf:open-palette";
export const openPalette = () => window.dispatchEvent(new Event(OPEN_PALETTE));

type Row =
  | { kind: "open" | "hit" | "ranked"; key: string; id: string; target: string; title: string; path: string; p?: number }
  | { kind: "part"; key: string; part: number; title: string }
  | { kind: "score"; key: string; title: string };

const NUMBER = /^\d+(\.\d+)+\.?(\(\d+\))*$/;

/** ⌘K: search the code or jump to an article number. Enter opens it in the library. */
export function CodePalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const rel = useRelevance();
  // Mounted with the shell, so nothing is fetched until the palette opens.
  const toc = useToc(open);
  const index = useMemo(() => tocIndex(toc.state === "ready" ? toc.value : undefined), [toc]);
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<CodeHit[]>([]);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [active, setActive] = useState(0);
  const list = useRef<HTMLUListElement>(null);

  useEffect(() => {
    if (!open) return;
    setQ("");
    setHits([]);
    setNote("");
    setActive(0);
    rel.refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Debounced search; the route is rate-limited, so a 429 is a calm note, not an error wall.
  useEffect(() => {
    const term = q.trim();
    if (!open || term.length < 2) { setHits([]); setNote(""); setBusy(false); return; }
    const ctl = new AbortController();
    const t = window.setTimeout(() => {
      setBusy(true);
      engine.search(term, { division: "B", limit: 12 }, ctl.signal).then(
        (rows) => { setHits(rows); setNote(rows.length ? "" : "Nothing matched. Try other words or an article number."); setBusy(false); },
        (e: unknown) => {
          if (ctl.signal.aborted) return;
          setHits([]);
          setBusy(false);
          setNote(e instanceof EngineError && e.status === 429 ? "Too many searches at once. Wait a moment and keep typing." : e instanceof EngineError ? e.detail : "Search did not answer.");
        },
      );
    }, 220);
    return () => { ctl.abort(); window.clearTimeout(t); };
  }, [q, open]);

  const rows: Row[] = useMemo(() => {
    const term = q.trim();
    if (term.length >= 2) {
      const out: Row[] = [];
      if (NUMBER.test(term)) {
        const id = term.includes("(") || term.endsWith(".") ? term : `${term}.`;
        const article = articleOf(id) ?? id;
        out.push({ kind: "open", key: `open-${id}`, id, target: article, title: index.get(article)?.title ?? "Open this number", path: index.get(article)?.path ?? "" });
      }
      for (const h of hits) {
        const target = h.level === "article" ? h.id : articleOf(h.id) ?? h.id;
        // One row per article: its sentences open the same page.
        if (out.some((r) => "target" in r && (r.id === h.id || r.target === target))) continue;
        out.push({ kind: "hit", key: `hit-${h.id}`, id: h.id, target, title: h.article_title || h.title || "", path: index.get(target)?.path ?? h.citation ?? "" });
      }
      return out;
    }
    if (rel.display) {
      return rankedIn(rel.display, rel.cutoffs, ["high", "mid"], rel.rerank).slice(0, 10).map((r) => ({
        kind: "ranked" as const, key: `rank-${r.id}`, id: r.id, target: r.id, title: index.get(r.id)?.title ?? "", path: index.get(r.id)?.path ?? "", p: r.p,
      }));
    }
    const out: Row[] = [];
    if (!rel.blocked && rel.phase !== "running") out.push({ kind: "score", key: "score", title: "Score relevance for my project" });
    if (toc.state === "ready") for (const p of toc.value.parts) out.push({ kind: "part", key: `part-${p.part}`, part: p.part, title: p.title ?? "" });
    return out;
  }, [q, hits, rel.display, rel.cutoffs, rel.rerank, rel.blocked, rel.phase, index, toc]);

  useEffect(() => { setActive(0); }, [q, rows.length]);
  useEffect(() => {
    list.current?.querySelector<HTMLElement>(`[data-i="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  function choose(r: Row | undefined) {
    if (!r) return;
    if (r.kind === "score") { void rel.score(); return; }
    onClose();
    if (r.kind === "part") { setPendingReveal(`part-${r.part}`); location.hash = codeHref(null, "all"); return; }
    location.hash = codeHref(r.target);
  }

  function onKey(e: KeyboardEvent) {
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((n) => Math.min(rows.length - 1, n + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((n) => Math.max(0, n - 1)); }
    else if (e.key === "Enter") { e.preventDefault(); choose(rows[active]); }
  }

  const heading = q.trim().length >= 2 ? null : rel.display ? "Likely related to your project" : null;
  return (
    <Modal open={open} onClose={onClose} labelledBy="cf-palette-label" className="cf-palette">
      <div className="cf-palette-input">
        <CIcon name="search" />
        <label id="cf-palette-label" className="cf-sr" htmlFor="cf-palette-q">Search the code</label>
        <input
          id="cf-palette-q"
          autoFocus
          role="combobox"
          aria-expanded={rows.length > 0}
          aria-controls="cf-palette-list"
          aria-activedescendant={rows[active] ? `cf-pal-${active}` : undefined}
          autoComplete="off"
          spellCheck={false}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={onKey}
          placeholder="Search the code or type an article number"
        />
        {busy && <span className="cf-dot is-pending cf-pulse" aria-hidden="true" />}
        <span className="cf-kbd is-dark" aria-hidden="true">esc</span>
      </div>
      <div className="cf-palette-body">
        {heading && <div className="cf-list-label">{heading}</div>}
        {rel.phase === "running" && !q.trim() && <p className="cf-faint cf-small cf-palette-note" role="status">Scoring your project… this can take a little while.</p>}
        {note && <p className="cf-faint cf-small cf-palette-note" role="status">{note}</p>}
        <ul id="cf-palette-list" ref={list} role="listbox" aria-label="Results" className="cf-palette-list">
          {rows.map((r, i) => (
            <li
              key={r.key}
              id={`cf-pal-${i}`}
              data-i={i}
              role="option"
              aria-selected={i === active}
              className={`cf-pal-row${i === active ? " is-active" : ""}`}
              onPointerMove={() => setActive(i)}
              onClick={() => choose(r)}
            >
              {r.kind === "score" ? (
                <><span className="cf-pal-icon"><CIcon name="retry" size={14} /></span><span className="cf-pal-title">{r.title}</span><span className="cf-faint cf-small">Estimates from your description</span></>
              ) : r.kind === "part" ? (
                <><span className="cf-pal-icon"><CIcon name="doc" size={14} /></span><span className="cf-mono">Part {r.part}</span><span className="cf-pal-title">{r.title}</span></>
              ) : (
                <>
                  <RelevanceRing id={r.target} focusable={false} />
                  <span className="cf-mono cf-pal-id">{r.id}</span>
                  <span className="cf-pal-title">{r.title}</span>
                  <span className="cf-faint cf-small cf-pal-path">
                    {r.kind === "ranked" ? BAND_LABEL[rel.shown(r.id).band] : r.path}
                  </span>
                </>
              )}
            </li>
          ))}
        </ul>
        {rows.length === 0 && !note && q.trim().length >= 2 && busy && <p className="cf-faint cf-small cf-palette-note">Searching…</p>}
      </div>
      <div className="cf-palette-foot cf-faint cf-small">
        <span><span className="cf-kbd is-dark">↑</span> <span className="cf-kbd is-dark">↓</span> move</span>
        <span><span className="cf-kbd is-dark">↵</span> open in the library</span>
        <span>Rings are Jev estimates, not compliance.</span>
      </div>
    </Modal>
  );
}
