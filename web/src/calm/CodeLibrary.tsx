import { useEffect, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";
import type { CodeToc } from "../api/codeLibrary";
import { NrcCredit } from "../components";
import { canonicalProvision, withinProvision } from "../provisions";
import { provisionCandidate } from "../screens/SectionC";
import { useCase } from "../store";
import { errorText, takePendingReveal, tocIndex, useContext, useText, useToc } from "./codeData";
import { BandPill, RelevanceRing, RingGlyph, RingLegend, Tip } from "./RelevanceRing";
import {
  ancestorsOf, reflow, BAND_LABEL, bandFor, filterKeep, maxOf, partArticles, pct, pruneToc, rankedIn, sectionArticles, subsectionArticles, ago, type Filter,
} from "./relevance";
import { codeHref, type CalmRoute } from "./routes";
import { scoreFor, useRelevance } from "./useRelevance";
import { openPalette } from "./CodePalette";
import { CIcon, Eyebrow, MOD_KEY } from "./ui";

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
export function ScoreStatus({ compact = false }: { compact?: boolean }) {
  const rel = useRelevance();
  const elapsed = useElapsed(rel.phase === "running" ? rel.startedAt : null);
  useElapsed(rel.retryAt && rel.retryAt > Date.now() ? rel.retryAt : null);
  const wait = rel.retryAt ? Math.max(0, Math.ceil((rel.retryAt - Date.now()) / 1000)) : 0;
  const err = rel.error ? errorText(rel.error) : null;
  if (rel.phase === "running") {
    return <span className="cf-score is-running" role="status"><span className="cf-dot is-pending cf-pulse" aria-hidden="true" />Scoring your project… {elapsed} s</span>;
  }
  if (rel.phase === "loading") return <span className="cf-score" role="status"><span className="cf-dot is-pending" aria-hidden="true" />Checking for scores…</span>;
  const scoreBtn = (label: string, primary: boolean) => (
    <button type="button" className={`cf-btn is-sm${primary ? " is-primary" : ""}`} disabled={Boolean(rel.blocked) || wait > 0} onClick={() => void rel.score()}>
      {label}
    </button>
  );
  return (
    <div className="cf-score-wrap">
      {rel.result ? (
        rel.stale ? (
          <span className="cf-score is-stale"><span className="cf-dot is-warning" aria-hidden="true" />Out of date {scoreBtn("Rescore", false)}</span>
        ) : (
          <span className="cf-score" title={rel.result.model ? `Model ${rel.result.model}` : undefined}>
            <span className="cf-dot is-done" aria-hidden="true" />Scored for your project{rel.result.scored_at ? ` · ${ago(rel.result.scored_at)}` : ""}
          </span>
        )
      ) : rel.phase === "error" ? (
        <span className="cf-score is-error"><span className="cf-dot is-warning" aria-hidden="true" />Scores unavailable {scoreBtn("Try again", false)}</span>
      ) : (
        scoreBtn(compact ? "Score relevance" : "Score relevance for my project", true)
      )}
      {(rel.blocked || wait > 0) && <span className="cf-faint cf-small">{wait > 0 ? `Try again in ${wait} s.` : rel.result ? "" : rel.blocked}</span>}
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

/** Hover / focus peek: path, exact score, band, the first words and objective codes. */
function Peek({ id, anchor, path }: { id: string; anchor: HTMLElement; path: string }) {
  const text = useText(id);
  const ctx = useContext(id);
  const rel = useRelevance();
  const p = scoreFor(rel.display, id);
  const band = bandFor(p, rel.cutoffs);
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
  const objectives = ctx.state === "ready" ? ctx.value.objectives.map((o) => o.code) : [];
  return createPortal(
    <div ref={card} className="cf-peek" role="tooltip" style={pos ?? { left: -9999, top: -9999 }}>
      <div className="cf-faint cf-small cf-peek-path">{path}</div>
      <div className="cf-peek-score">
        <RingGlyph p={p} band={band} />
        <span className="cf-mono">{band === "unscored" ? "Not scored" : pct(p!, 1)}</span>
        <span className={`cf-band is-${band}`}>{BAND_LABEL[band]}</span>
      </div>
      <p className="cf-peek-text">{text.state === "loading" ? "Loading…" : text.state === "error" ? "The wording did not load." : words ? (words.length > 160 ? `${words.slice(0, 157)}…` : words) : "Article heading. Open it to read its sentences."}</p>
      {objectives.length > 0 && <div className="cf-peek-codes">{objectives.map((o) => <span key={o} className="cf-code-chip is-static">{o}</span>)}</div>}
    </div>,
    document.body,
  );
}

function Tree({ toc, selected, filter, revealKey }: { toc: CodeToc; selected: string | null; filter: Filter; revealKey: { key: string; n: number } | null }) {
  const rel = useRelevance();
  const shown = useMemo(() => pruneToc(toc, filterKeep(filter, rel.display, rel.cutoffs)), [toc, filter, rel.display, rel.cutoffs]);
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
  // Breadcrumbs reveal a branch.
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
    else if (e.key === "Escape") endPeek();
  }

  function rows(list: TNode[], level: number): ReactNode {
    return list.map((n) => {
      const branch = n.children.length > 0;
      const expanded = branch && open.has(n.key);
      const p = n.kind === "article" ? scoreFor(rel.display, n.id) : maxOf(n.articles, rel.display);
      return (
        <li key={n.key} role="none">
          <div
            role="treeitem"
            data-key={n.key}
            aria-level={level}
            aria-expanded={branch ? expanded : undefined}
            aria-selected={n.kind === "article" ? n.id === selected : undefined}
            aria-label={`${n.label} ${n.title ?? ""}${p != null ? `, Jev ${pct(p)}${n.kind === "article" ? "" : " highest"}` : ""}`}
            tabIndex={n.key === focusKey ? 0 : -1}
            className={`cf-tree-row is-${n.kind}${n.id === selected ? " is-selected" : ""}`}
            style={{ paddingLeft: 10 + (level - 1) * 14 }}
            onClick={() => { setFocus(n.key); go(n); }}
            onPointerEnter={(e) => startPeek(n, e.currentTarget)}
            onPointerLeave={endPeek}
            onFocus={(e) => { setFocus(n.key); if (e.currentTarget === e.target) startPeek(n, e.currentTarget); }}
            onBlur={endPeek}
          >
            <span className={`cf-chev${expanded ? " is-open" : ""}`} aria-hidden="true">{branch ? <CIcon name="chev" size={12} /> : null}</span>
            <span className="cf-mono cf-tree-id">{n.label}</span>
            <span className="cf-tree-title">{n.title ?? ""}</span>
            <RelevanceRing p={p} aggregate={n.kind === "article" ? undefined : n.kind} focusable={false} />
          </div>
          {expanded && <ul role="group">{rows(n.children, level + 1)}</ul>}
        </li>
      );
    });
  }

  return (
    <>
      {nodes.length === 0 ? (
        <p className="cf-faint cf-tree-empty">{filter === "all" ? "No chapters returned." : "Nothing in this filter. Choose All to see every chapter."}</p>
      ) : (
        <ul ref={box} role="tree" aria-label="Chapters" className="cf-tree" onKeyDown={onKey}>
          {rows(nodes, 1)}
        </ul>
      )}
      {peek && <Peek id={peek.id} anchor={peek.el} path={index.get(peek.id)?.path ?? ""} />}
    </>
  );
}

/* —— Reading pane —— */

function TermChip({ code, title }: { code: string; title: string | null }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [open, setOpen] = useState(false);
  const id = `term-${code}`;
  return (
    <>
      <span ref={ref} className="cf-code-chip" tabIndex={0} aria-describedby={open ? id : undefined} onPointerEnter={() => setOpen(true)} onPointerLeave={() => setOpen(false)} onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}>
        {code}
      </span>
      <Tip anchor={ref.current} open={open} id={id}><p>{title ?? "Title not returned by the lookup."}</p></Tip>
    </>
  );
}

function Reading({ id, filter, onReveal, index }: { id: string; filter: Filter; onReveal: (key: string) => void; index: ReturnType<typeof tocIndex> }) {
  const { c, dispatch } = useCase();
  const text = useText(id);
  const ctx = useContext(id);
  const [added, setAdded] = useState(false);
  useEffect(() => setAdded(false), [id]);
  const title = (ctx.state === "ready" ? ctx.value.title : null) ?? (text.state === "ready" ? text.value.article_title ?? text.value.title : null) ?? index.get(id)?.title ?? "";
  const inCase = c.candidates.some((a) => canonicalProvision(a.provision) === canonicalProvision(id) || withinProvision(a.provision, id));
  // The same statement or term can repeat (one per objective); show each once.
  const raw = ctx.state === "ready" ? ctx.value : null;
  const cx = raw && {
    ...raw,
    intent: [...new Map(raw.intent.map((i) => [i.text, i])).values()],
    objectives: [...new Map(raw.objectives.map((o) => [o.code, o])).values()],
    functions: [...new Map(raw.functions.map((f) => [f.code, f])).values()],
  };
  const chips = (ids: string[]) => (
    <div className="cf-chip-row">{ids.map((r) => <a key={r} className="cf-code-chip is-link" href={codeHref(r, filter === "all" ? "" : filter)}>{r}</a>)}</div>
  );
  return (
    <article className="cf-read" aria-labelledby="cf-read-title">
      <nav className="cf-crumbs" aria-label="Where this is">
        {(cx?.path ?? []).map((p, n) => (
          <span key={p.id}>
            {n > 0 && <span className="cf-faint" aria-hidden="true"> › </span>}
            <button type="button" className="cf-crumb" onClick={() => onReveal(p.level === "part" || /^\d+$/.test(p.id) ? `part-${p.id.replace(/\D.*$/, "")}` : p.id)}>
              {p.level === "part" || /^\d+$/.test(p.id) ? `Part ${p.id.replace(/\D.*$/, "")}` : p.id} {p.title ?? ""}
            </button>
          </span>
        ))}
      </nav>
      <h1 id="cf-read-title" className="cf-read-title"><span className="cf-mono">{id}</span> {title}</h1>
      <div className="cf-read-score">
        <RelevanceRing id={id} size={22} />
        <BandPill id={id} />
      </div>

      {text.state === "loading" ? (
        <p className="cf-faint" role="status">Loading the code text…</p>
      ) : text.state === "error" ? (
        <div className="cf-sect"><p className="cf-faint">{errorText(text.error).text}</p><button type="button" className="cf-btn is-sm" onClick={text.retry}>Try again</button></div>
      ) : text.value.text.trim() ? (
        <>
          <Eyebrow>Code text · verbatim</Eyebrow>
          <blockquote className="cf-code-text">{reflow(text.value.text)}</blockquote>
          <div className="cf-code-src">{cx?.citation ?? text.value.citation}</div>
          <div className="cf-code-src"><NrcCredit /></div>
        </>
      ) : (
        <p className="cf-faint">This heading has no sentences of its own.</p>
      )}

      <section className="cf-sect" aria-labelledby="cf-roots">
        <Eyebrow id="cf-roots" as="h2">Roots</Eyebrow>
        {ctx.state === "loading" ? (
          <p className="cf-faint cf-body" role="status">Looking up objectives and intent…</p>
        ) : ctx.state === "error" ? (
          <div className="cf-body"><p className="cf-faint">{errorText(ctx.error).text}</p><button type="button" className="cf-btn is-sm" onClick={ctx.retry}>Try again</button></div>
        ) : (
          <div className="cf-body">
            {cx!.objectives.length || cx!.functions.length ? (
              <>
                {cx!.objectives.length > 0 && <div className="cf-roots-row"><span className="cf-faint cf-small">Objectives</span><div className="cf-chip-row">{cx!.objectives.map((o) => <TermChip key={o.code} code={o.code} title={o.title} />)}</div></div>}
                {cx!.functions.length > 0 && <div className="cf-roots-row"><span className="cf-faint cf-small">Functions</span><div className="cf-chip-row">{cx!.functions.map((f) => <TermChip key={f.code} code={f.code} title={f.title} />)}</div></div>}
                {cx!.inherited_from && <p className="cf-faint cf-small">Uses the attribution row of {cx!.inherited_from}.</p>}
              </>
            ) : (
              <p className="cf-faint">The attribution table has no row for this provision.</p>
            )}
            {cx!.intent.length > 0 && (
              <div className="cf-sect is-tight">
                <span className="cf-faint cf-small">Why this rule exists · NBC 2020 intent statement, explanatory only</span>
                {cx!.intent.map((i) => <p key={i.text} className="cf-muted">{i.objective && <span className="cf-mono cf-faint">{i.objective} · </span>}{i.text}</p>)}
                {cx!.intent_differs && <p className="cf-note"><span className="cf-dot is-warning" aria-hidden="true" />{cx!.intent_differs_detail ?? "The NBC 2020 intent statement is attributed differently from NBC(AE) 2023."}</p>}
                <div className="cf-code-src"><NrcCredit source="intent" /></div>
              </div>
            )}
            {cx!.notes.length > 0 && (
              <details className="cf-notes">
                <summary>Appendix notes ({cx!.notes.length})</summary>
                {cx!.notes.map((n) => <div key={n.id} className="cf-note-item"><span className="cf-mono cf-faint">{n.id}</span> {n.title}<p>{n.excerpt}</p></div>)}
              </details>
            )}
            {cx!.references.length > 0 && <div className="cf-roots-row"><span className="cf-faint cf-small">Cites</span>{chips(cx!.references)}</div>}
            {cx!.referenced_by.length > 0 && <div className="cf-roots-row"><span className="cf-faint cf-small">Cited by</span>{chips(cx!.referenced_by)}</div>}
          </div>
        )}
      </section>

      <div className="cf-read-actions">
        {inCase ? (
          <a className="cf-btn is-sm" href="#/questions?first=code"><CIcon name="check" size={13} />In your application</a>
        ) : (
          <button
            type="button"
            className="cf-btn is-sm is-primary"
            disabled={text.state !== "ready"}
            onClick={() => {
              if (text.state !== "ready") return;
              const r = text.value;
              dispatch({ type: "addCandidate", candidate: provisionCandidate({ id, article_title: r.article_title, title: r.title, text: r.text, citation: r.citation }) });
              setAdded(true);
            }}
          >
            Add to my application
          </button>
        )}
        {added && <span className="cf-faint cf-small" role="status">Added as a Code check card. <a className="cf-inline-link" href="#/questions?first=code">Answer it</a></span>}
      </div>
      <p className="cf-faint cf-small cf-disclaimer">Rings are Jev estimates from your description. They are not a compliance decision and not your Section C, which lists only the rules you confirm.</p>
    </article>
  );
}

/* —— Page —— */

export function CodeLibrary({ route }: { route: CalmRoute }) {
  const rel = useRelevance();
  const toc = useToc();
  const [reveal, setReveal] = useState<{ key: string; n: number } | null>(() => {
    const k = takePendingReveal();
    return k ? { key: k, n: 1 } : null;
  });
  const { engineId } = useCase();
  // Free GET on open; scoring itself waits for the button.
  useEffect(() => { rel.refresh(); }, [engineId]); // eslint-disable-line react-hooks/exhaustive-deps

  const high = rankedIn(rel.display, rel.cutoffs, ["high"]);
  const mid = rankedIn(rel.display, rel.cutoffs, ["mid"]);
  const filter: Filter = route.filter || (rel.display && high.length ? "attention" : "all");
  const index = useMemo(() => tocIndex(toc.state === "ready" ? toc.value : undefined), [toc]);
  const setFilter = (f: Filter) => { location.hash = codeHref(route.article, f); };
  const edition = toc.state === "ready" ? toc.value.edition : "NBC(AE) 2023";

  return (
    <div className={`cf-lib${route.article ? " has-article" : ""}`}>
      <header className="cf-lib-head">
        <div className="cf-lib-titles">
          <Eyebrow>Code library</Eyebrow>
          <h1 className="cf-lib-title">{edition} · Division B</h1>
        </div>
        <ScoreStatus />
        <div className="cf-lib-tools">
          <div className="cf-filters" role="group" aria-label="Show">
            <button type="button" className="cf-chip" aria-pressed={filter === "all"} onClick={() => setFilter("all")}>All</button>
            {rel.display && (
              <>
                <button type="button" className="cf-chip" aria-pressed={filter === "attention"} onClick={() => setFilter("attention")}><span className="cf-dot is-blocking" aria-hidden="true" />Needs attention <span className="cf-faint">{high.length}</span></button>
                <button type="button" className="cf-chip" aria-pressed={filter === "maybe"} onClick={() => setFilter("maybe")}><span className="cf-dot is-warning" aria-hidden="true" />Maybe <span className="cf-faint">{mid.length}</span></button>
              </>
            )}
            <RingLegend />
          </div>
          <div className="cf-lib-links">
            <button type="button" className="cf-btn is-sm" onClick={openPalette}><CIcon name="search" size={13} />Search the code <span className="cf-kbd is-dark" aria-hidden="true">{MOD_KEY} K</span></button>
            <a className="cf-btn is-ghost is-sm" href="#/references">Your Section C references <CIcon name="arrow" size={13} /></a>
          </div>
        </div>
      </header>
      <div className="cf-lib-body">
        <nav className="cf-glass cf-lib-tree" aria-label="Chapters">
          {toc.state === "loading" ? (
            <p className="cf-faint cf-tree-empty" role="status">Loading chapters…</p>
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
        <section className="cf-glass cf-lib-read" aria-label="Reading">
          {route.article && (
            <a className="cf-btn is-ghost is-sm cf-lib-back" href={codeHref(null, route.filter)}><CIcon name="back" size={13} />Chapters</a>
          )}
          {route.article ? (
            <Reading key={route.article} id={route.article} filter={filter} index={index} onReveal={(key) => setReveal((r) => ({ key, n: (r?.n ?? 0) + 1 }))} />
          ) : (
            <div className="cf-read-empty">
              <h2 className="cf-read-title">Pick an article to read it.</h2>
              <p className="cf-muted">Open a chapter on the left, or search with <span className="cf-kbd is-dark">{MOD_KEY} K</span>. The code stays out of your way until you want it.</p>
              {high.length + mid.length > 0 && (
                <>
                  <div className="cf-list-label">Likely related to your project</div>
                  <ul className="cf-rows">
                    {[...high, ...mid].slice(0, 8).map((r) => (
                      <li key={r.id} className="cf-row">
                        <RelevanceRing p={r.p} />
                        <a className="cf-row-text cf-plain-link" href={codeHref(r.id, filter === "all" ? "" : filter)}><span className="cf-mono">{r.id}</span> {index.get(r.id)?.title ?? ""}</a>
                        <span className={`cf-band is-${bandFor(r.p, rel.cutoffs)}`}>{BAND_LABEL[bandFor(r.p, rel.cutoffs)]}</span>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
