import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode, type RefObject } from "react";
import { createPortal } from "react-dom";
import type { CodeRecord } from "../api/client";
import type { CodeToc } from "../api/codeLibrary";
import { NrcCredit } from "../components";
import { canonicalProvision, withinProvision } from "../provisions";
import { provisionCandidate } from "../screens/SectionC";
import { useCase } from "../store";
import { useCurrentApplication } from "./begin";
import { useApplicationSwitch, useCodeScope } from "./codeScope";
import { useAccount } from "./account";
import { chooseContext, contextOptions, NO_APPLICATION, setLibraryDetached } from "./libraryContext";
import { errorText, takePendingReveal, tocIndex, useContext, useText, useToc } from "./codeData";
import { parseArticle, previewOf, type Clause, type Sentence } from "./codeText";
import { BandPill, RelevanceRing, RingGlyph, RingLegend } from "./RelevanceRing";
import {
  ancestorsOf, BAND_LABEL, filterKeep, partArticles, pct, pruneToc, rankedIn, sectionArticles, strongestOf, subsectionArticles, ago, type Filter,
} from "./relevance";
import { codeHref, type CalmRoute } from "./routes";
import { articleOf, useRelevance } from "./useRelevance";
import { openPalette } from "./CodePalette";
import { Icon24 } from "./icons";
import { CIcon, MOD_KEY } from "./ui";

/* —— Scoring status —— */

function useElapsed(since: number | null): number {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!since) return;
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, [since]);
  return since ? Math.max(0, Math.round((now - since) / 1000)) : 0;
}

/** Scored / out of date / score / running / unavailable. The only place a POST starts. */
export function ScoreStatus() {
  const rel = useRelevance();
  const elapsed = useElapsed(rel.phase === "running" ? rel.startedAt : null);
  useElapsed(rel.retryAt && rel.retryAt > Date.now() ? rel.retryAt : null);
  const wait = rel.retryAt ? Math.max(0, Math.ceil((rel.retryAt - Date.now()) / 1000)) : 0;
  const err = rel.error ? errorText(rel.error) : null;
  if (rel.phase === "running") {
    return <span className="cf-score is-running" role="status"><span className="cf-dot is-pending cf-pulse" aria-hidden="true" />Scoring your project… {elapsed} s</span>;
  }
  if (rel.phase === "loading") return <span className="cf-score" role="status"><span className="cf-dot is-pending" aria-hidden="true" />Checking for scores…</span>;
  const scoreBtn = (label: string) => (
    <button type="button" className="cf-btn is-xs" disabled={Boolean(rel.blocked) || wait > 0} title={rel.blocked || undefined} onClick={() => void rel.score()}>
      {label}
    </button>
  );
  // Why Score is off (no description yet) sits on the button as its title; only a wait is shown.
  const why = wait > 0 ? `Try again in ${wait} s.` : "";
  return (
    <div className="cf-score-wrap">
      {rel.result ? (
        rel.stale ? (
          <span className="cf-score is-stale"><span className="cf-dot is-warning" aria-hidden="true" />Out of date {scoreBtn("Rescore")}</span>
        ) : (
          <span className="cf-score" title={rel.result.model ? `Estimate version ${rel.result.model}` : undefined}>
            <span className="cf-dot is-done" aria-hidden="true" />Scored for your project{rel.result.scored_at ? ` · ${ago(rel.result.scored_at)}` : ""}
          </span>
        )
      ) : rel.phase === "error" ? (
        <span className="cf-score is-error"><span className="cf-dot is-warning" aria-hidden="true" />Scores unavailable {scoreBtn("Try again")}</span>
      ) : (
        <span className="cf-score"><span className="cf-dot is-pending" aria-hidden="true" />Not scored {scoreBtn("Score relevance")}</span>
      )}
      {why && <span className="cf-score-why">{why}</span>}
      {err && (
        <details className="cf-tech is-inline">
          <summary>{err.text}</summary>
          <p>{err.technical}</p>
        </details>
      )}
    </div>
  );
}

/* —— Tree —— */

interface TNode {
  key: string;
  id: string;
  kind: "part" | "section" | "subsection" | "article";
  label: string;
  title: string | null;
  children: TNode[];
  articles: string[];
  parent: string | null;
}

function nodesOf(toc: CodeToc): TNode[] {
  return toc.parts.map((p) => {
    const pk = `part-${p.part}`;
    return {
      key: pk, id: pk, kind: "part", label: `Part ${p.part}`, title: p.title, parent: null, articles: partArticles(p),
      children: p.sections.map((s) => ({
        key: s.id, id: s.id, kind: "section", label: s.id, title: s.title, parent: pk, articles: sectionArticles(s),
        children: [
          ...s.articles.map((a): TNode => ({ key: a.id, id: a.id, kind: "article", label: a.id, title: a.title, parent: s.id, articles: [a.id], children: [] })),
          ...s.subsections.map((ss): TNode => ({
            key: ss.id, id: ss.id, kind: "subsection", label: ss.id, title: ss.title, parent: s.id, articles: subsectionArticles(ss),
            children: ss.articles.map((a): TNode => ({ key: a.id, id: a.id, kind: "article", label: a.id, title: a.title, parent: ss.id, articles: [a.id], children: [] })),
          })),
        ],
      })),
    };
  });
}

/** The same Set when nothing is new, so an effect that opens branches cannot loop. */
function addAll(set: Set<string>, keys: Iterable<string>): Set<string> {
  let next: Set<string> | null = null;
  for (const k of keys) if (!set.has(k)) (next ??= new Set(set)).add(k);
  return next ?? set;
}

function flatten(nodes: TNode[], open: Set<string>, out: { node: TNode; level: number }[] = [], level = 1) {
  for (const n of nodes) {
    out.push({ node: n, level });
    if (n.children.length && open.has(n.key)) flatten(n.children, open, out, level + 1);
  }
  return out;
}

/** Hover / focus peek: the roots (path), exact score, band, the first words and objective codes. */
function Peek({ id, anchor, path }: { id: string; anchor: HTMLElement; path: string }) {
  const text = useText(id);
  const ctx = useContext(id);
  const rel = useRelevance();
  const { p, band, screenedOnly } = rel.shown(id);
  const card = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);
  useLayoutEffect(() => {
    const r = anchor.getBoundingClientRect();
    const w = card.current?.offsetWidth ?? 320;
    const h = card.current?.offsetHeight ?? 160;
    const right = r.right + 12 + w < window.innerWidth;
    const left = right ? r.right + 12 : Math.max(8, Math.min(r.left, window.innerWidth - w - 8));
    const top = right ? Math.min(Math.max(8, r.top - 8), window.innerHeight - h - 8) : Math.min(r.bottom + 8, window.innerHeight - h - 8);
    setPos({ left, top });
  }, [anchor, text.state, ctx.state]);
  const words = text.state === "ready" ? text.value.text.replace(/\s+/g, " ").trim() : "";
  const objectives = ctx.state === "ready" ? [...new Set(ctx.value.objectives.map((o) => o.code))] : [];
  return createPortal(
    <div ref={card} className="cf-peek" role="tooltip" style={pos ?? { left: -9999, top: -9999 }}>
      <div className="cf-faint cf-small cf-peek-path">{path}</div>
      {rel.scope === "application" && (
        <div className="cf-peek-score">
          <RingGlyph p={p} band={band} />
          <span className="cf-mono">{band === "unscored" ? "Not scored" : pct(p!, 1)}</span>
          <span className={`cf-band is-${band}`}>{BAND_LABEL[band]}</span>
          {screenedOnly && band !== "unscored" && <span className="cf-faint cf-small">Screened only</span>}
        </div>
      )}
      <p className="cf-peek-text">{text.state === "loading" ? "Loading…" : text.state === "error" ? "The wording did not load." : words ? (words.length > 160 ? `${words.slice(0, 157)}…` : words) : "Article heading. Open it to read its sentences."}</p>
      {objectives.length > 0 && <div className="cf-peek-codes">{objectives.map((o) => <span key={o} className="cf-code-chip is-static">{o}</span>)}</div>}
    </div>,
    document.body,
  );
}

function Tree({ toc, selected, filter, revealKey }: { toc: CodeToc; selected: string | null; filter: Filter; revealKey: { key: string; n: number } | null }) {
  const rel = useRelevance();
  const shown = useMemo(() => pruneToc(toc, filterKeep(filter, rel.display, rel.cutoffs, rel.rerank)), [toc, filter, rel.display, rel.cutoffs, rel.rerank]);
  const nodes = useMemo(() => nodesOf(shown), [shown]);
  const index = useMemo(() => tocIndex(toc), [toc]);
  const [open, setOpen] = useState<Set<string>>(() => new Set(selected ? ancestorsOf(toc, selected) : []));
  const [focus, setFocus] = useState<string | null>(selected);
  const [peek, setPeek] = useState<{ id: string; el: HTMLElement } | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const box = useRef<HTMLUListElement>(null);

  // A filtered tree is short: open every branch so the handful of articles is visible at once.
  useEffect(() => {
    if (filter === "all") return;
    const all = new Set<string>();
    const walk = (ns: TNode[]) => ns.forEach((n) => { if (n.children.length) { all.add(n.key); walk(n.children); } });
    walk(nodes);
    setOpen((o) => addAll(o, all));
  }, [filter, nodes]);
  // Auto-expand to the selected article.
  useEffect(() => {
    if (!selected) return;
    setOpen((o) => addAll(o, ancestorsOf(toc, selected)));
    setFocus(selected);
  }, [selected, toc]);
  // A palette pick reveals its branch.
  useEffect(() => {
    if (!revealKey) return;
    const k = revealKey.key;
    const chain: string[] = [];
    const find = (ns: TNode[], trail: string[]): boolean => ns.some((n) => (n.key === k ? (chain.push(...trail, n.key), true) : find(n.children, [...trail, n.key])));
    find(nodes, []);
    setOpen((o) => addAll(o, chain));
    setFocus(k);
    window.setTimeout(() => box.current?.querySelector<HTMLElement>(`[data-key="${CSS.escape(k)}"]`)?.focus(), 0);
  }, [revealKey, nodes]);
  useEffect(() => {
    if (!selected) return;
    const t = window.setTimeout(() => box.current?.querySelector<HTMLElement>(`[data-key="${CSS.escape(selected)}"]`)?.scrollIntoView({ block: "nearest" }), 0);
    return () => window.clearTimeout(t);
  }, [selected, open]);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  const flat = flatten(nodes, open);
  const focusKey = flat.some((f) => f.node.key === focus) ? focus : flat[0]?.node.key ?? null;
  const toggle = (k: string, to?: boolean) => setOpen((o) => { const n = new Set(o); if (to ?? !n.has(k)) n.add(k); else n.delete(k); return n; });
  const go = (n: TNode) => { if (n.kind === "article") location.hash = codeHref(n.id, filter === "all" ? "all" : filter); else toggle(n.key); };
  const move = (k: string | undefined) => {
    if (!k) return;
    setFocus(k);
    box.current?.querySelector<HTMLElement>(`[data-key="${CSS.escape(k)}"]`)?.focus();
  };
  const startPeek = (n: TNode, el: HTMLElement) => {
    window.clearTimeout(timer.current);
    if (n.kind !== "article") return setPeek(null);
    timer.current = window.setTimeout(() => setPeek({ id: n.id, el }), 300);
  };
  const endPeek = () => { window.clearTimeout(timer.current); setPeek(null); };

  function onKey(e: KeyboardEvent) {
    const at = flat.findIndex((f) => f.node.key === focusKey);
    const cur = flat[at]?.node;
    if (!cur) return;
    const handled = () => { e.preventDefault(); e.stopPropagation(); };
    if (e.key === "ArrowDown") { handled(); move(flat[at + 1]?.node.key); }
    else if (e.key === "ArrowUp") { handled(); move(flat[at - 1]?.node.key); }
    else if (e.key === "Home") { handled(); move(flat[0]?.node.key); }
    else if (e.key === "End") { handled(); move(flat[flat.length - 1]?.node.key); }
    else if (e.key === "ArrowRight") {
      handled();
      if (cur.children.length && !open.has(cur.key)) toggle(cur.key, true);
      else if (cur.children.length) move(cur.children[0].key);
    } else if (e.key === "ArrowLeft") {
      handled();
      if (cur.children.length && open.has(cur.key)) toggle(cur.key, false);
      else if (cur.parent) move(cur.parent);
    } else if (e.key === "Enter" || e.key === " ") { handled(); go(cur); }
    else if (e.key === "Escape" && peek) { e.stopPropagation(); endPeek(); }
  }

  function rows(list: TNode[], level: number): ReactNode {
    return list.map((n) => {
      const branch = n.children.length > 0;
      const expanded = branch && open.has(n.key);
      const s = n.kind === "article" ? rel.shown(n.id) : strongestOf(n.articles, rel.display, rel.rerank, rel.cutoffs);
      const p = s?.p;
      return (
        <li key={n.key} role="none">
          <div
            role="treeitem"
            data-key={n.key}
            aria-level={level}
            aria-expanded={branch ? expanded : undefined}
            aria-selected={n.kind === "article" ? n.id === selected : undefined}
            aria-label={`${n.label} ${n.title ?? ""}${p != null ? `, relevance ${pct(p)}${n.kind === "article" ? "" : " highest"}` : ""}`}
            tabIndex={n.key === focusKey ? 0 : -1}
            className={`cf-tree-row is-${n.kind}${n.id === selected ? " is-selected" : ""}`}
            style={{ paddingLeft: 8 + (level - 1) * 12 }}
            onClick={() => { setFocus(n.key); go(n); }}
            onPointerEnter={(e) => startPeek(n, e.currentTarget)}
            onPointerLeave={endPeek}
            onFocus={(e) => { setFocus(n.key); if (e.currentTarget === e.target) startPeek(n, e.currentTarget); }}
            onBlur={endPeek}
          >
            <span className={`cf-chev${expanded ? " is-open" : ""}`} aria-hidden="true">{branch ? <CIcon name="chev" size={12} /> : null}</span>
            <span className="cf-tree-text">
              <span className="cf-mono cf-tree-id">{n.label}</span> <span className="cf-tree-title">{n.title ?? ""}</span>
            </span>
            <RelevanceRing shown={s} aggregate={n.kind === "article" ? undefined : n.kind} focusable={false} />
          </div>
          {expanded && <ul role="group">{rows(n.children, level + 1)}</ul>}
        </li>
      );
    });
  }

  return (
    <>
      {nodes.length === 0 ? (
        <p className="cf-tree-empty">{filter === "all" ? "No chapters returned." : "Nothing in this filter. Choose All to see every chapter."}</p>
      ) : (
        <ul ref={box} role="tree" aria-label="Chapters" className="cf-tree" onKeyDown={onKey}>
          {rows(nodes, 1)}
        </ul>
      )}
      {peek && <Peek id={peek.id} anchor={peek.el} path={index.get(peek.id)?.path ?? ""} />}
    </>
  );
}

/* —— Reader —— */

/** A disclosure with a count; collapsed by default so the code stays quiet until asked for. */
function Group({ id, title, count, children, note }: { id: string; title: string; count: number; children: ReactNode; note?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <section className="cf-group" aria-labelledby={`${id}-h`}>
      <h2 className="cf-group-h" id={`${id}-h`}>
        <button type="button" className="cf-group-btn" aria-expanded={open} aria-controls={`${id}-b`} onClick={() => setOpen((v) => !v)}>
          <span className="cf-group-title">{title}</span>
          <span className="cf-group-count">{count}</span>
          {note && <span className="cf-group-note">{note}</span>}
          <span className={`cf-chev${open ? " is-open" : ""}`} aria-hidden="true"><CIcon name="chev" size={12} /></span>
        </button>
      </h2>
      {open && <div className="cf-group-body" id={`${id}-b`}>{children}</div>}
    </section>
  );
}

function Clauses({ list, depth = 0 }: { list: Clause[]; depth?: number }) {
  if (!list.length) return null;
  return (
    <ol className={`cf-clauses${depth ? " is-sub" : ""}`}>
      {list.map((c) => (
        <li key={c.mark}>
          <span className="cf-clause-mark" aria-hidden="true">({c.mark})</span>
          <div className="cf-clause-text">
            <span className="cf-sr">Clause ({c.mark}) </span>
            {c.text}
            <Clauses list={c.sub} depth={depth + 1} />
          </div>
        </li>
      ))}
    </ol>
  );
}

function SentenceRow({ s, id, open, onToggle }: { s: Sentence; id: string; open: boolean; onToggle: () => void }) {
  const body = `${id}-s${s.n}`;
  return (
    <li className={`cf-sent${open ? " is-open" : ""}`}>
      {/* The number and chevron are the control; a click on a collapsed preview opens it too. */}
      <div className="cf-sent-row" onClick={(e) => { if (!open || !(e.target as HTMLElement).closest(".cf-sent-body")) onToggle(); }}>
        <button type="button" className="cf-sent-btn" aria-expanded={open} aria-controls={body} aria-label={`Sentence ${s.n}`}>
          <span className="cf-sent-n" aria-hidden="true">({s.n})</span>
        </button>
        {open ? (
          <div className="cf-sent-body" id={body}>
            {s.lead && <p>{s.lead}</p>}
            <Clauses list={s.clauses} />
          </div>
        ) : (
          <span className="cf-sent-preview" aria-hidden="true">{previewOf(s)}</span>
        )}
        <span className={`cf-chev${open ? " is-open" : ""}`} aria-hidden="true"><CIcon name="chev" size={12} /></span>
      </div>
    </li>
  );
}

function CodeText({ id, text }: { id: string; text: string }) {
  const parsed = useMemo(() => parseArticle(text), [text]);
  const n = parsed.sentences.length;
  const [open, setOpen] = useState<Set<number>>(() => new Set([0]));
  const all = n > 0 && open.size === n;
  return (
    <section className="cf-code" aria-labelledby="cf-code-h">
      <div className="cf-code-head">
        <h2 id="cf-code-h" className="cf-code-label">Code text · verbatim{n > 1 ? <span className="cf-faint"> · {n} sentences</span> : null}</h2>
        {n > 1 && (
          <button type="button" className="cf-link-btn" onClick={() => setOpen(all ? new Set() : new Set(parsed.sentences.map((_, i) => i)))}>
            {all ? "Collapse all" : "Expand all"}
          </button>
        )}
      </div>
      {parsed.intro && <p className="cf-code-intro">{parsed.intro}</p>}
      {n > 0 && (
        <ol className="cf-sents" aria-label="Sentences">
          {parsed.sentences.map((s, i) => (
            <SentenceRow key={s.n} s={s} id={id.replace(/[^\w]/g, "-")} open={open.has(i)} onToggle={() => setOpen((o) => { const x = new Set(o); if (x.has(i)) x.delete(i); else x.add(i); return x; })} />
          ))}
        </ol>
      )}
    </section>
  );
}

/**
 * The reader's one write: add the article to the application the library reads for (the open one).
 * Nothing under None; a sent or closed application says it is read-only (the code stays readable).
 * While a submission is on its way the button stays, paused.
 */
export function AddToApplication({ id, record }: { id: string; record: CodeRecord | null }) {
  const { c, dispatch, engineId } = useCase();
  const { locked, readOnly } = useCurrentApplication();
  const scope = useCodeScope();
  /** The case the article was added to, so the note never shows for another one. */
  const [addedTo, setAddedTo] = useState<string | null>(null);
  if (scope === "none") return null;
  const here = engineId ?? "this-visit";
  const inCase = c.candidates.some((a) => canonicalProvision(a.provision) === canonicalProvision(id) || withinProvision(a.provision, id));
  return (
    <div className="cf-read-actions">
      {readOnly ? (
        <span className="cf-faint cf-small">Your saved application is read-only. You can still read the code.</span>
      ) : inCase ? (
        <a className="cf-btn is-sm" href="#/questions?first=code"><CIcon name="check" size={13} />In your application</a>
      ) : (
        <button
          type="button"
          className="cf-btn is-sm"
          disabled={!record || locked}
          onClick={() => {
            if (!record || locked) return;
            dispatch({ type: "addCandidate", candidate: provisionCandidate({ id, article_title: record.article_title, title: record.title, text: record.text, citation: record.citation }) });
            setAddedTo(here);
          }}
        >
          <CIcon name="plus" size={13} />Add to my application
        </button>
      )}
      {addedTo === here && <span className="cf-faint cf-small" role="status">Added as a Code check card. <a className="cf-inline-link" href="#/questions?first=code">Answer it</a></span>}
    </div>
  );
}

function Reading({ id, filter, index, narrow }: { id: string; filter: Filter; index: ReturnType<typeof tocIndex>; narrow: boolean }) {
  const scope = useCodeScope();
  const text = useText(id);
  const ctx = useContext(id);
  const heading = useRef<HTMLHeadingElement>(null);
  // One pane at a time: opening an article moves focus into it (the tree is hidden). `narrow` is measured after
  // the first render, so a direct #/code/<id> visit sees it turn true; focus once, when it does.
  const focused = useRef(false);
  useEffect(() => {
    if (narrow && !focused.current) {
      focused.current = true;
      heading.current?.focus({ preventScroll: true });
    }
  }, [narrow]);
  const title = (ctx.state === "ready" ? ctx.value.title : null) ?? (text.state === "ready" ? text.value.article_title ?? text.value.title : null) ?? index.get(id)?.title ?? "";
  // The same statement or term can repeat (one per objective); show each once.
  const raw = ctx.state === "ready" ? ctx.value : null;
  const cx = raw && {
    ...raw,
    intent: [...new Map(raw.intent.map((i) => [i.text, i])).values()],
    objectives: [...new Map(raw.objectives.map((o) => [o.code, o])).values()],
    functions: [...new Map(raw.functions.map((f) => [f.code, f])).values()],
    references: [...new Set(raw.references.map((r) => articleOf(r) ?? r))].filter((r) => canonicalProvision(r) !== canonicalProvision(id)),
    referenced_by: [...new Set(raw.referenced_by.map((r) => articleOf(r) ?? r))].filter((r) => canonicalProvision(r) !== canonicalProvision(id)),
  };
  const link = (r: string) => <a key={r} className="cf-code-chip is-link" href={codeHref(r, filter)}>{r}</a>;
  const page = (cx?.pdf_page ?? (text.state === "ready" ? text.value.pdf_page : null)) || null;

  return (
    <article className="cf-read" aria-labelledby="cf-read-title">
      <a className="cf-lib-back" href={codeHref(null, filter === "all" ? "all" : filter)}><CIcon name="back" size={13} />Chapters</a>
      <h1 ref={heading} id="cf-read-title" className="cf-read-title" tabIndex={-1}>{title || id}</h1>
      <div className="cf-read-meta">
        <span className="cf-mono cf-read-id">Article {id}</span>
        <RelevanceRing id={id} />
        <BandPill id={id} />
      </div>

      <AddToApplication id={id} record={text.state === "ready" ? text.value : null} />

      {text.state === "loading" ? (
        <p className="cf-faint cf-read-wait" role="status">Loading the code text…</p>
      ) : text.state === "error" ? (
        <div className="cf-read-wait"><p className="cf-faint">{errorText(text.error).text}</p><button type="button" className="cf-btn is-sm" onClick={text.retry}>Try again</button></div>
      ) : text.value.text.trim() ? (
        <CodeText key={id} id={id} text={text.value.text} />
      ) : (
        <p className="cf-faint cf-read-wait">This heading has no sentences of its own.</p>
      )}

      <div className="cf-groups">
        {ctx.state === "loading" ? (
          <p className="cf-faint cf-small cf-read-wait" role="status">Looking up objectives and intent…</p>
        ) : ctx.state === "error" ? (
          <div className="cf-read-wait"><p className="cf-faint">{errorText(ctx.error).text}</p><button type="button" className="cf-btn is-sm" onClick={ctx.retry}>Try again</button></div>
        ) : (
          <>
            <Group id="cf-g-roots" title="Objectives and functions" count={cx!.objectives.length + cx!.functions.length}>
              {cx!.objectives.length || cx!.functions.length ? (
                <dl className="cf-pairs">
                  {[...cx!.objectives.map((o) => ({ ...o, kind: "Objective" })), ...cx!.functions.map((f) => ({ ...f, kind: "Function" }))].map((t) => (
                    <div key={t.code} className="cf-pair">
                      <dt><span className="cf-code-chip is-static" title={t.kind}>{t.code}</span></dt>
                      <dd>{t.title ?? "Title not returned by the lookup."}</dd>
                    </div>
                  ))}
                </dl>
              ) : (
                <p className="cf-faint">The attribution table has no row for this provision.</p>
              )}
              {cx!.inherited_from && <p className="cf-faint cf-small">Uses the attribution row of {cx!.inherited_from}.</p>}
            </Group>
            {cx!.intent.length > 0 && (
              <Group id="cf-g-intent" title="Why this rule exists" count={cx!.intent.length} note="NBC 2020 intent, explanatory only">
                <ul className="cf-intent">
                  {cx!.intent.map((i) => <li key={i.text}><span className="cf-intent-obj">{i.objective ?? ""}</span><span>{i.text}</span></li>)}
                </ul>
                {cx!.intent_differs && <p className="cf-note"><span className="cf-dot is-warning" aria-hidden="true" />{cx!.intent_differs_detail ?? "The NBC 2020 intent statement is attributed differently from NBC(AE) 2023."}</p>}
                <div className="cf-code-src"><NrcCredit source="intent" /></div>
              </Group>
            )}
            {cx!.notes.length > 0 && (
              <Group id="cf-g-notes" title="Notes" count={cx!.notes.length}>
                {cx!.notes.map((n) => <div key={n.id} className="cf-note-item"><span className="cf-mono cf-faint">{n.id}</span> {n.title}<p>{n.excerpt}</p></div>)}
              </Group>
            )}
            {cx!.references.length + cx!.referenced_by.length > 0 && (
              <Group id="cf-g-refs" title="Referenced articles" count={cx!.references.length + cx!.referenced_by.length}>
                {cx!.references.length > 0 && <div className="cf-refs"><span className="cf-refs-label">This article cites</span><div className="cf-chip-row">{cx!.references.map(link)}</div></div>}
                {cx!.referenced_by.length > 0 && <div className="cf-refs"><span className="cf-refs-label">Cited by</span><div className="cf-chip-row">{cx!.referenced_by.map(link)}</div></div>}
              </Group>
            )}
          </>
        )}
      </div>

      <footer className="cf-read-src">
        <span>{cx?.citation ?? (text.state === "ready" ? text.value.citation : `NBC(AE) 2023, Division B, Article ${id}`)}{page && !/PDF p/.test(cx?.citation ?? "") ? ` · PDF page ${page}` : ""}</span>
        <NrcCredit />
        {scope === "application" && <span>Rings are Batatis estimates from your description. They are not a compliance decision and not your Section C, which lists only the rules you confirm.</span>}
      </footer>
    </article>
  );
}

/* —— Application context —— */

/**
 * Which application the library reads for, or none. A listbox button: ↑ ↓ Home End move, Enter or
 * Space choose, Esc closes. Another application opens through the sidebar's guarded switch; None
 * only detaches the library (the open application and its unsaved answers stay as they are).
 */
function ContextPicker() {
  const sw = useApplicationSwitch();
  const scope = useCodeScope();
  const reviewer = useAccount().user?.role === "reviewer";
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const btn = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const listId = useId();
  const options = sw ? contextOptions(sw.items, sw.openId) : [];
  useEffect(() => {
    if (!open) return;
    list.current?.querySelector<HTMLElement>("[aria-selected='true']")?.focus();
    const away = (e: PointerEvent) => { if (!btn.current?.contains(e.target as Node) && !list.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("pointerdown", away);
    return () => document.removeEventListener("pointerdown", away);
  }, [open]);
  // Reviewers browse the code without an application of their own; with nothing to choose, no control.
  if (!sw || reviewer || !options.length) return null;
  const selected = scope === "none" ? NO_APPLICATION : sw.openId;
  const current = options.find((o) => o.id === selected);
  const busy = Boolean(sw.opening);
  const label = busy ? "Opening…" : current?.title ?? "No application";

  async function choose(id: string) {
    setOpen(false);
    btn.current?.focus();
    setNote("");
    if (id === selected || !sw) return;
    const error = await chooseContext(id, { openId: sw.openId, detach: setLibraryDetached, switchTo: sw.switchTo });
    if (error) setNote(error);
  }
  function onListKey(e: KeyboardEvent) {
    const items = [...(list.current?.querySelectorAll<HTMLElement>("[role='option']") ?? [])];
    const at = items.indexOf(document.activeElement as HTMLElement);
    const to = (n: number) => { e.preventDefault(); items[(n + items.length) % items.length]?.focus(); };
    if (e.key === "ArrowDown") to(at + 1);
    else if (e.key === "ArrowUp") to(at - 1);
    else if (e.key === "Home") to(0);
    else if (e.key === "End") to(items.length - 1);
    else if (e.key === "Enter" || e.key === " ") { e.preventDefault(); const id = items[at]?.dataset.id; if (id) void choose(id); }
    else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); setOpen(false); btn.current?.focus(); }
    else if (e.key === "Tab") setOpen(false);
  }
  const row = (id: string, title: string, meta?: string) => (
    <li key={id} role="option" data-id={id} aria-selected={id === selected} tabIndex={-1} className={`cf-ctx-opt${id === NO_APPLICATION ? " is-none" : ""}`} onClick={() => void choose(id)}>
      <span className="cf-ctx-check" aria-hidden="true">{id === selected ? <Icon24 name="check" size={14} /> : null}</span>
      <span className="cf-ctx-name">{title}</span>
      {meta && <span className="cf-ctx-meta">{meta}</span>}
    </li>
  );
  return (
    <div className="cf-ctx">
      <button
        ref={btn}
        type="button"
        className="cf-ctx-btn"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-label={`Application: ${label}`}
        aria-busy={busy || undefined}
        disabled={busy}
        onClick={() => setOpen((v) => !v)}
        onKeyDown={(e) => { if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); setOpen(true); } }}
      >
        <Icon24 name={selected === NO_APPLICATION ? "book" : "file"} size={15} />
        <span className="cf-ctx-label">{label}</span>
        <Icon24 name="down" size={14} />
      </button>
      {open && (
        <ul ref={list} id={listId} role="listbox" aria-label="Application" className="cf-pop cf-ctx-list" onKeyDown={onListKey}>
          {row(NO_APPLICATION, "No application")}
          {options.map((o) => row(o.id, o.title, o.readOnly ? "Read-only" : undefined))}
        </ul>
      )}
      {note && <p className="cf-ctx-note" role="alert">{note}</p>}
    </div>
  );
}

/* —— Page —— */

/** True while the element is narrower than `px` (one pane at a time). */
function useNarrow(ref: RefObject<HTMLElement | null>, px: number): boolean {
  const [narrow, setNarrow] = useState(false);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const check = () => setNarrow(el.clientWidth < px);
    check();
    const ro = new ResizeObserver(check);
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref, px]);
  return narrow;
}

export function CodeLibrary({ route }: { route: CalmRoute }) {
  const rel = useRelevance();
  const toc = useToc();
  const root = useRef<HTMLDivElement>(null);
  const narrow = useNarrow(root, 760);
  const [reveal] = useState<{ key: string; n: number } | null>(() => {
    const k = takePendingReveal();
    return k ? { key: k, n: 1 } : null;
  });
  const { engineId } = useCase();
  const none = rel.scope === "none";
  // Free GET on open and when the context changes; scoring itself waits for the button. None reads nothing.
  useEffect(() => { rel.refresh(); }, [engineId, rel.scope]); // eslint-disable-line react-hooks/exhaustive-deps

  const high = rankedIn(rel.display, rel.cutoffs, ["high"], rel.rerank);
  const mid = rankedIn(rel.display, rel.cutoffs, ["mid"], rel.rerank);
  // Estimates without cut-offs have no "needs attention" or "maybe" to filter by.
  const filter: Filter = !rel.cutoffs.rated ? "all" : route.filter || (rel.display && high.length ? "attention" : "all");
  const index = useMemo(() => tocIndex(toc.state === "ready" ? toc.value : undefined), [toc]);
  const setFilter = (f: Filter) => { location.hash = codeHref(route.article, f); };
  const edition = toc.state === "ready" ? toc.value.edition : "NBC(AE) 2023";
  const back = codeHref(null, filter === "all" ? "all" : filter);

  // One pane at a time: Esc closes the reader and returns to the chapters.
  useEffect(() => {
    if (!narrow || !route.article) return;
    const article = route.article;
    const on = (e: globalThis.KeyboardEvent) => {
      if (e.key !== "Escape" || e.defaultPrevented || document.querySelector("dialog[open]")) return;
      if ((e.target as HTMLElement | null)?.closest?.(".cf-assist, .cf-pop, [role='menu']")) return;
      e.preventDefault();
      location.hash = back;
      window.setTimeout(() => root.current?.querySelector<HTMLElement>(`[data-key="${CSS.escape(article)}"]`)?.focus(), 0);
    };
    document.addEventListener("keydown", on);
    return () => document.removeEventListener("keydown", on);
  }, [narrow, route.article, back]);

  return (
    <div ref={root} className={`cf-lib${route.article ? " has-article" : ""}${narrow ? " is-narrow" : ""}`}>
      <aside className="cf-lib-nav" aria-label="Code library">
        <div className="cf-lib-nav-head">
          <h1 className="cf-lib-name">Code library</h1>
          <details className="cf-lib-info">
            <summary aria-label="Code edition"><CIcon name="info" size={14} /></summary>
            <p>{edition} · Division B</p>
          </details>
        </div>
        <ContextPicker />
        <button type="button" className="cf-lib-search" onClick={openPalette}>
          <CIcon name="search" size={14} />
          <span>Search the code</span>
          <span className="cf-kbd is-dark" aria-hidden="true">{MOD_KEY} ⇧ K</span>
        </button>
        {!none && <div className="cf-lib-tools">
          <div className="cf-filters" role="group" aria-label="Show">
            <button type="button" className="cf-chip is-sm" aria-pressed={filter === "all"} onClick={() => setFilter("all")}>All</button>
            {rel.display && rel.cutoffs.rated && (
              <>
                <button type="button" className="cf-chip is-sm" aria-pressed={filter === "attention"} onClick={() => setFilter("attention")}><span className="cf-dot is-blocking" aria-hidden="true" />Needs attention <span className="cf-faint">{high.length}</span></button>
                <button type="button" className="cf-chip is-sm" aria-pressed={filter === "maybe"} onClick={() => setFilter("maybe")}><span className="cf-dot is-warning" aria-hidden="true" />Maybe <span className="cf-faint">{mid.length}</span></button>
              </>
            )}
          </div>
          <div className="cf-lib-score">
            <ScoreStatus />
            <RingLegend />
          </div>
        </div>}
        <nav className="cf-lib-tree" aria-label="Chapters">
          {toc.state === "loading" ? (
            <p className="cf-tree-empty" role="status">Loading chapters…</p>
          ) : toc.state === "error" ? (
            <div className="cf-tree-empty">
              <p>{errorText(toc.error).text}</p>
              <button type="button" className="cf-btn is-sm" onClick={toc.retry}>Try again</button>
              <details className="cf-tech"><summary>Technical detail</summary><p>{errorText(toc.error).technical}</p></details>
            </div>
          ) : (
            <Tree toc={toc.value} selected={route.article} filter={filter} revealKey={reveal} />
          )}
        </nav>
        {!none && <a className="cf-lib-foot" href="#/references">Rules you chose (Section C) <CIcon name="arrow" size={13} /></a>}
      </aside>
      <section className="cf-lib-reader" aria-label="Reading">
        {route.article ? (
          <Reading key={`${none ? NO_APPLICATION : engineId ?? "this-visit"}:${route.article}`} id={route.article} filter={filter} index={index} narrow={narrow} />
        ) : (
          <div className="cf-read-empty">
            <h2 className="cf-read-empty-title">Pick an article to read it.</h2>
            <p className="cf-read-empty-text">Open a chapter or search <span className="cf-kbd is-dark">{MOD_KEY} ⇧ K</span></p>
            {high.length + mid.length > 0 && (
              <>
                <h3 className="cf-read-empty-label">Likely related to your project</h3>
                <ul className="cf-likely">
                  {[...high, ...mid].slice(0, 8).map((r) => (
                    <li key={r.id}>
                      <a className="cf-likely-row" href={codeHref(r.id, filter)}>
                        <RelevanceRing id={r.id} focusable={false} />
                        <span className="cf-mono cf-likely-id">{r.id}</span>
                        <span className="cf-likely-title">{index.get(r.id)?.title ?? ""}</span>
                        <span className={`cf-band is-${rel.shown(r.id).band}`}>{BAND_LABEL[rel.shown(r.id).band]}</span>
                      </a>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
