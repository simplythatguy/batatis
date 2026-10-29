/**
 * Relevance rings: pure band mapping, labels and tree aggregation.
 * A ring is an estimate from the applicant's description. It is never a compliance decision and
 * never the Section C list (Section C is only what the applicant confirmed).
 */
import type { CodeToc, RelevanceResult, TocPart, TocSection, TocSubsection } from "../api/codeLibrary";

/** "estimate": scored, but the response carries no fitted cut-offs, so it gets no likely/unlikely rating. */
export type Band = "unscored" | "estimate" | "zero" | "low" | "mid" | "high";

/**
 * Benchmark-derived cut-offs (docs/research/relevance-bands.md, x = 0.30, y = 0.85), fitted for
 * relevance-1 only. Also used for relevance-1 rows that still carry the old 0.2 / 0.6 placeholders.
 */
export const DEFAULT_BANDS = { x: 0.3, y: 0.85 } as const;

/**
 * `rated: false` means no cut-offs apply: every score shows as an estimate, never as "likely applies"
 * or "unlikely". The engine sends that for every configuration it has not fitted bands for.
 */
export type Cutoffs =
  | { rated: true; x: number; y: number; /** True for a legacy relevance-1 placeholder row read with DEFAULT_BANDS. */ fallback: boolean }
  | { rated: false; x: null; y: null; fallback: false };

const UNRATED: Cutoffs = { rated: false, x: null, y: null, fallback: false };

export function cutoffsOf(r: Pick<RelevanceResult, "bands" | "model"> | null | undefined): Cutoffs {
  const b = r?.bands;
  const status = typeof b?.status === "string" ? b.status : "";
  // 0 and 1 are the display range, not cut-offs; a status saying so (or no status) is never trusted.
  const fitted = b && Number.isFinite(b.x) && Number.isFinite(b.y) && b.x > 0 && b.y > b.x && b.y < 1
    && status.trim() !== "" && !/uncalibrated|placeholder|display range/i.test(status);
  if (fitted) return { rated: true, x: b.x, y: b.y, fallback: false };
  if (r?.model === "relevance-1" && /placeholder/i.test(status)) return { rated: true, ...DEFAULT_BANDS, fallback: true };
  return UNRATED;
}

/** The engine reports hundredths; bands compare round(p, 2). */
const hundredths = (p: number) => Math.round(p * 100) / 100;

/** p is a probability in [0, 1]. Missing means the article was not scored. */
export function bandFor(p: number | null | undefined, c: Pick<Cutoffs, "x" | "y">): Band {
  if (p == null || !Number.isFinite(p)) return "unscored";
  if (c.x == null || c.y == null) return "estimate";
  const q = hundredths(p);
  if (q <= 0) return "zero";
  if (q < c.x) return "low";
  if (q < c.y) return "mid";
  return "high";
}

export interface Shown {
  p: number | undefined;
  band: Band;
  /** Scored by the screen only: the rerank did not judge it, so it is never yellow or red. */
  screenedOnly: boolean;
}

/**
 * The guard from the band study: an article the rerank did not judge is never yellow or red.
 * It caps the flagged set at the rerank size (60) whatever the screen scores do.
 */
export function shownFor(id: string, display: Record<string, number> | undefined, rerank: Record<string, number> | undefined, c: Pick<Cutoffs, "x" | "y">): Shown {
  const p = display?.[id];
  const band = bandFor(p, c);
  const judged = Boolean(rerank && id in rerank);
  if (!judged && rerank && (band === "mid" || band === "high")) return { p, band: "low", screenedOnly: true };
  return { p, band, screenedOnly: !judged && p != null };
}

// "estimate" never mixes with the rated bands: one response is either rated or not.
const RANK: Record<Band, number> = { unscored: 0, zero: 1, estimate: 2, low: 2, mid: 3, high: 4 };

/** The strongest article among ids (band first, then p), for a section ring. */
export function strongestOf(ids: Iterable<string>, display: Record<string, number> | undefined, rerank: Record<string, number> | undefined, c: Pick<Cutoffs, "x" | "y">): Shown | undefined {
  if (!display) return undefined;
  let best: Shown | undefined;
  for (const id of ids) {
    if (display[id] == null) continue;
    const s = shownFor(id, display, rerank, c);
    if (!best || RANK[s.band] > RANK[best.band] || (RANK[s.band] === RANK[best.band] && (s.p ?? 0) > (best.p ?? 0))) best = s;
  }
  return best;
}

export const BAND_LABEL: Record<Band, string> = {
  unscored: "Not scored",
  estimate: "Estimate only",
  zero: "No relevance score",
  low: "Unlikely to apply",
  mid: "Might apply · check this",
  high: "Likely applies · address this",
};

/** Short form for aria-labels: "Relevance estimate 34%: might apply". */
export const BAND_SHORT: Record<Band, string> = {
  unscored: "not scored",
  estimate: "estimate only",
  zero: "no relevance score",
  low: "unlikely to apply",
  mid: "might apply",
  high: "likely applies",
};

export const pct = (p: number, digits = 0) => `${(p * 100).toFixed(digits)}%`;

/** Highest score among ids; undefined when none of them is scored. */
export function maxOf(ids: Iterable<string>, display: Record<string, number> | undefined): number | undefined {
  if (!display) return undefined;
  let best: number | undefined;
  for (const id of ids) {
    const p = display[id];
    if (p == null || !Number.isFinite(p)) continue;
    if (best === undefined || p > best) best = p;
  }
  return best;
}

export function subsectionArticles(s: TocSubsection): string[] {
  return s.articles.map((a) => a.id);
}

export function sectionArticles(s: TocSection): string[] {
  return [...s.articles.map((a) => a.id), ...s.subsections.flatMap(subsectionArticles)];
}

export function partArticles(p: TocPart): string[] {
  return p.sections.flatMap(sectionArticles);
}

/** Keep only branches with at least one article that passes `keep`. */
export function pruneToc(toc: CodeToc, keep: (articleId: string) => boolean): CodeToc {
  const parts = toc.parts
    .map((p) => ({
      ...p,
      sections: p.sections
        .map((s) => ({
          ...s,
          articles: s.articles.filter((a) => keep(a.id)),
          subsections: s.subsections
            .map((ss) => ({ ...ss, articles: ss.articles.filter((a) => keep(a.id)) }))
            .filter((ss) => ss.articles.length > 0),
        }))
        .filter((s) => s.articles.length > 0 || s.subsections.length > 0),
    }))
    .filter((p) => p.sections.length > 0);
  return { ...toc, parts };
}

/** The library's band toggles: likely (red), might (amber), and the rest (grey: unlikely or not scored). */
export const FILTER_BANDS = ["attention", "maybe", "other"] as const;
export type FilterBand = (typeof FILTER_BANDS)[number];
/** "all", "" (the default), or a comma list of the toggled bands in FILTER_BANDS order. */
export type Filter = string;

export function filterBands(filter: Filter): Set<FilterBand> {
  return new Set(FILTER_BANDS.filter((b) => filter.split(",").includes(b)));
}

/** The canonical filter for a set of toggled bands: "all" when none are on. */
export function filterOf(bands: Iterable<FilterBand>): Filter {
  const on = new Set(bands);
  return FILTER_BANDS.filter((b) => on.has(b)).join(",") || "all";
}

export function filterBandOf(band: Band): FilterBand {
  return band === "high" ? "attention" : band === "mid" ? "maybe" : "other";
}

export function filterKeep(filter: Filter, display: Record<string, number> | undefined, c: Cutoffs, rerank?: Record<string, number>): (id: string) => boolean {
  const want = filterBands(filter);
  if (!want.size || !display || !c.rated) return () => true;
  return (id) => want.has(filterBandOf(shownFor(id, display, rerank, c).band));
}

/** Article ids shown in a band (after the guard), highest first. */
export function rankedIn(display: Record<string, number> | undefined, c: Cutoffs, bands: Band[], rerank?: Record<string, number>): { id: string; p: number }[] {
  if (!display) return [];
  return Object.entries(display)
    .filter(([id]) => bands.includes(shownFor(id, display, rerank, c).band))
    .map(([id, p]) => ({ id, p }))
    .sort((a, b) => b.p - a.p);
}

/** Ids of every node on the way to an article, for auto-expanding the tree. */
export function ancestorsOf(toc: CodeToc, articleId: string): string[] {
  for (const p of toc.parts) {
    for (const s of p.sections) {
      if (s.articles.some((a) => a.id === articleId)) return [`part-${p.part}`, s.id];
      for (const ss of s.subsections) if (ss.articles.some((a) => a.id === articleId)) return [`part-${p.part}`, s.id, ss.id];
    }
  }
  return [];
}

/** "4 min ago" for a scored_at timestamp. */
export function ago(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return "";
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return "";
  const s = Math.max(0, Math.round((now - t) / 1000));
  if (s < 60) return "just now";
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} h ago`;
  return `${Math.round(h / 24)} d ago`;
}

/**
 * The code database keeps the PDF's hard line breaks. Reflow them, but keep a break before a
 * sentence or clause marker such as "2)", "a)" or "(iii)", so the structure still reads.
 */
export function reflow(text: string): string {
  return text
    .trim()
    .replace(/\r/g, "")
    .replace(/\n(?!\s*(?:\d+\)|[a-z]\)|\(?[ivx]+\)))\s*/g, " ")
    .replace(/[ \t]{2,}/g, " ");
}
