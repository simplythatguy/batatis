/**
 * Jev relevance rings: pure band mapping, labels and tree aggregation.
 * A ring is an estimate from the applicant's description. It is never a compliance decision and
 * never the Section C list (Section C is only what the applicant confirmed).
 */
import type { CodeToc, RelevanceResult, TocPart, TocSection, TocSubsection } from "../api/codeLibrary";

export type Band = "unscored" | "zero" | "low" | "mid" | "high";

/** Placeholder cut-offs, used only when a response has no `bands` (a benchmark study replaces them). */
export const DEFAULT_BANDS = { x: 0.2, y: 0.6 } as const;

export interface Cutoffs {
  x: number;
  y: number;
  /** True when the response had no bands and the placeholders are in use. */
  fallback: boolean;
}

export function cutoffsOf(r: Pick<RelevanceResult, "bands"> | null | undefined): Cutoffs {
  const b = r?.bands;
  if (b && Number.isFinite(b.x) && Number.isFinite(b.y) && b.x > 0 && b.y > b.x) return { x: b.x, y: b.y, fallback: false };
  return { ...DEFAULT_BANDS, fallback: true };
}

/** p is a probability in [0, 1]. Missing means the article was not scored. */
export function bandFor(p: number | null | undefined, c: Pick<Cutoffs, "x" | "y">): Band {
  if (p == null || !Number.isFinite(p)) return "unscored";
  if (p <= 0) return "zero";
  if (p < c.x) return "low";
  if (p < c.y) return "mid";
  return "high";
}

export const BAND_LABEL: Record<Band, string> = {
  unscored: "Not scored",
  zero: "No sign it applies",
  low: "Unlikely to apply",
  mid: "Might apply · check this",
  high: "Likely applies · address this",
};

/** Short form for aria-labels: "Jev relevance 34%: might apply". */
export const BAND_SHORT: Record<Band, string> = {
  unscored: "not scored",
  zero: "no sign it applies",
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

export type Filter = "all" | "attention" | "maybe";

export function filterKeep(filter: Filter, display: Record<string, number> | undefined, c: Cutoffs): (id: string) => boolean {
  if (filter === "all" || !display) return () => true;
  const want: Band = filter === "attention" ? "high" : "mid";
  return (id) => bandFor(display[id], c) === want;
}

/** Article ids scored into a band, highest first. */
export function rankedIn(display: Record<string, number> | undefined, c: Cutoffs, bands: Band[]): { id: string; p: number }[] {
  if (!display) return [];
  return Object.entries(display)
    .filter(([, p]) => bands.includes(bandFor(p, c)))
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
