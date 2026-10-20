/**
 * POST/GET /cases/{id}/identify (engine PR #12, head c382ed7). The route has no response_model, so
 * types.gen.ts has no identify type; this is hand-typed from the API contract ("Identify" and
 * "Article card") and real responses. Field names are the engine's, unchanged.
 *
 * Fields marked `// proposed to Backy, not in #12 yet` are optional and absent today; the UI renders
 * them only when present.
 */
import type { AttributionPair, AttributionStatus, Case, CodeIdAnswer, SectionCRow } from "../types";
import { ATTRIBUTION_STATUS } from "./sectionC";
import type { SectionCRow as EngineRow } from "./types.gen";

export type IdentifyMode = "live" | "cached_demo" | "bm25_fallback";

export interface Explainer {
  text: string;
  quote: string | null;
  source: "deterministic" | "ai_written";
  /** "explanation" on article cards; absent on Section C rows. */
  label?: string | null;
}

export interface IdentifyPair {
  function: string;
  objective: string;
  condition: string | null;
}

/** One `section_c[]` (or `benchmark.section_c[]`) item. Keyed by `provision_id`, like SectionCRow. */
export interface IdentifySectionCRow {
  provision_id: string;
  division?: string;
  citation: string | null;
  attribution_status?: string;
  pairs: IdentifyPair[];
  explainer?: Explainer | null;
}

/** An objective or function with its code-derived title. */
export interface CodeTerm {
  id: string;
  label: string | null;
}

export interface Confidence {
  probability: number | null;
  calibration: string;
}

export interface IdentifyArticle {
  rank: number;
  /** Division B article id, e.g. "9.10.15.5." */
  provision: string;
  /** Sentence id, e.g. "9.10.15.5.(8)", only when exactly one codedb sentence holds the quote. */
  provision_id: string | null;
  link: string;
  citation: string | null;
  title: string;
  /** First 25 words of the codedb sentence: clipped, verbatim. */
  snippet: string | null;
  verifier_status: "committed" | "candidate" | "unknown";
  why: string | null;
  benchmark_acceptable_solution: string | null;
  explainer: Explainer | null;
  committed: boolean;
  probability: number | null;
  confidence?: Confidence;
  quote?: string | null;
  reason?: string | null;
  stage?: string;
  part?: number | null;
  division?: string;
  page?: number | null; // proposed to Backy, not in #12 yet
  printing?: number | string | null; // proposed to Backy, not in #12 yet
  clipped?: boolean; // proposed to Backy, not in #12 yet
  objectives?: CodeTerm[]; // proposed to Backy, not in #12 yet
  functions?: CodeTerm[]; // proposed to Backy, not in #12 yet
  attribution_missing?: boolean; // proposed to Backy, not in #12 yet
}

export interface Benchmark {
  identified: boolean;
  provision?: string;
  division?: string;
  role?: string;
  relation?: string;
  explanation: string | null;
  quote: string | null;
  citation: string | null;
  confidence?: Confidence;
  section_c: IdentifySectionCRow[];
  /** Asked when `identified` is false. */
  question?: string | null;
  provision_id?: string | null; // proposed to Backy, not in #12 yet
  requirement_snippet?: string | null; // proposed to Backy, not in #12 yet
  required_value?: number | string | null; // proposed to Backy, not in #12 yet
  required_unit?: string | null; // proposed to Backy, not in #12 yet
  proposed_value?: number | string | null; // proposed to Backy, not in #12 yet
  proposed_unit?: string | null; // proposed to Backy, not in #12 yet
  comparison?: string | null; // proposed to Backy, not in #12 yet
}

export interface OpenQuestion {
  field: string;
  text: string;
  why: string;
  status: "open" | "unknown";
  /** Candidate article ids this question would settle. */
  disambiguates: string[];
  answer: string | null;
}

export interface IdentifyResult {
  mode: IdentifyMode;
  source: "live" | "cache" | "bm25" | string;
  cached: boolean;
  generated_at?: string | null;
  articles: IdentifyArticle[];
  section_c: IdentifySectionCRow[];
  benchmark: Benchmark;
  open_questions: OpenQuestion[];
  questions: string[];
  variance_needed?: "not_indicated" | "likely" | "unknown" | null;
  variance_explanation?: string | null;
  intake_action?: string | null;
  redirect_to?: string | null;
  engineering_required?: string | null;
  model_ids: { screen: string | null; rerank: string | null; verifier: string | null; invoked: boolean };
  commit_policy?: { threshold: number; max_commits: number; status: string; [key: string]: unknown };
}

export interface IdentifyAnswer {
  field: string;
  answer: string;
}

// —— Helpers: every word below comes from the payload; nothing is filled in. ——

/** The sentence id when the engine resolved one, else the article id. Also what /identify/confirm takes. */
export const articleKey = (a: Pick<IdentifyArticle, "provision" | "provision_id">) => a.provision_id ?? a.provision;

/** The payload's Section C row for a sentence id (`section_c[]`, then `benchmark.section_c[]`). */
export function rowFor(r: IdentifyResult, provisionId: string | null | undefined): IdentifySectionCRow | undefined {
  if (!provisionId) return undefined;
  return [...(r.section_c ?? []), ...(r.benchmark?.section_c ?? [])].find((row) => row.provision_id === provisionId);
}

/** Objective-function pairs grouped by objective, in payload order. */
export function groupPairs(pairs: IdentifyPair[]): AttributionPair[] {
  const by = new Map<string, Set<string>>();
  for (const p of pairs) by.set(p.objective, (by.get(p.objective) ?? new Set()).add(p.function));
  return [...by].map(([objective, fns]) => ({ bracket: objective, objectives: [objective], functions: [...fns] }));
}

/** Pairs for an article: from `section_c` by provision_id, else from future `objectives`/`functions`. */
export function articlePairs(r: IdentifyResult, a: IdentifyArticle): { pairs: AttributionPair[]; terms: Record<string, string> } {
  const terms: Record<string, string> = {};
  for (const t of [...(a.objectives ?? []), ...(a.functions ?? [])]) if (t.label) terms[t.id] = t.label;
  const row = rowFor(r, a.provision_id);
  if (row?.pairs.length) return { pairs: groupPairs(row.pairs), terms };
  if (a.objectives?.length || a.functions?.length) {
    return {
      pairs: [{ bracket: "card", objectives: (a.objectives ?? []).map((t) => t.id), functions: (a.functions ?? []).map((t) => t.id) }],
      terms,
    };
  }
  return { pairs: [], terms };
}

const ENDS_SENTENCE = /[.:;)"”’]$/;
const isClipped = (text: string, flag?: boolean) => !!flag || !ENDS_SENTENCE.test(text.trim());

/**
 * The code text to show. `snippet` is the first 25 words of the sentence; it is clipped when the stored
 * `quote` is longer, when the engine says so, or when it stops mid-sentence. `full` is the longer
 * stored quote, itself marked clipped when it stops mid-sentence.
 */
export function quoteOf(a: Pick<IdentifyArticle, "snippet" | "quote" | "clipped">) {
  const text = a.snippet ?? a.quote ?? null;
  if (!text) return null;
  const longer = a.quote && a.quote.length > text.length ? a.quote : null;
  return {
    text,
    clipped: !!longer || isClipped(text, a.clipped),
    full: longer ? { text: longer, clipped: isClipped(longer, a.clipped) } : null,
  };
}

/** The benchmark's stored quote, marked clipped when it stops mid-sentence. */
export const benchmarkQuote = (b: Benchmark) => (b.quote ? { text: b.quote, clipped: isClipped(b.quote) } : null);

/** "2nd printing · PDF p.904": from the future page/printing fields, else parsed from the citation. */
export function printChip(a: { citation: string | null; page?: number | null; printing?: number | string | null }): string | null {
  const printing =
    a.printing != null ? (typeof a.printing === "number" ? ordinal(a.printing) : String(a.printing)) : /\bp2\b/.test(a.citation ?? "") ? "2nd" : null;
  const page = a.page ?? Number(/\[PDF p\.(\d+)\]/.exec(a.citation ?? "")?.[1] ?? NaN);
  const parts = [printing && `${printing.replace(/ printing$/i, "")} printing`, Number.isFinite(page) && `PDF p.${page}`].filter(Boolean);
  return parts.length ? parts.join(" · ") : null;
}

const ordinal = (n: number) => `${n}${n % 10 === 1 && n !== 11 ? "st" : n % 10 === 2 && n !== 12 ? "nd" : n % 10 === 3 && n !== 13 ? "rd" : "th"}`;

/** The proposed measured comparison, only when every required field is present. */
export function measuredComparison(b: Benchmark) {
  const { provision_id, required_value, required_unit, proposed_value, proposed_unit } = b;
  if (!provision_id || required_value == null || proposed_value == null || !required_unit || !proposed_unit) return null;
  return { provision_id, required: `${required_value} ${required_unit}`, proposed: `${proposed_value} ${proposed_unit}`, snippet: b.requirement_snippet ?? null, comparison: b.comparison ?? null };
}

export const MODE_LABEL: Record<IdentifyMode, string> = {
  cached_demo: "Cached demo run",
  bm25_fallback: "Keyword search (no AI key)",
  live: "Live run",
};

export function recordedAt(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

/** "Recorded … · not re-run · models: rerank/verifier" for cached runs; the model ids for live ones. */
export function runDetail(r: IdentifyResult): string {
  const models = [r.model_ids?.rerank, r.model_ids?.verifier].filter(Boolean).join("/");
  if (r.mode === "cached_demo") {
    const at = recordedAt(r.generated_at);
    return [at ? `Recorded ${at}` : "Recorded earlier", "not re-run", models && `models: ${models}`].filter(Boolean).join(" · ");
  }
  if (r.mode === "live") return [recordedAt(r.generated_at), models && `models: ${models}`].filter(Boolean).join(" · ");
  return "Keyword matches only · nothing checked or committed";
}

const STATUS_OF = (s: string | undefined): AttributionStatus =>
  s && s in ATTRIBUTION_STATUS ? ATTRIBUTION_STATUS[s as EngineRow["attribution_status"]] : "unavailable";

/**
 * Section C rows for the Code ID cards the applicant marked "Yes" (and, greyed, "Not sure"). Derived
 * from the stored identify payload: provision_id, citation, quote, pairs and explainer are the engine's.
 */
export function codeIdRows(c: Case): SectionCRow[] {
  const run = c.codeId;
  if (!run) return [];
  const r = run.result;
  return r.articles
    .filter((a) => run.answers[a.provision] === "yes" || run.answers[a.provision] === "not-sure")
    .map((a) => {
      const row = rowFor(r, a.provision_id);
      const { pairs, terms } = articlePairs(r, a);
      const q = quoteOf(a);
      const shown = q?.full ?? q;
      return {
        candidateId: a.provision,
        provision: articleKey(a),
        citation: a.citation ?? row?.citation ?? "",
        pairs,
        attributionStatus: a.attribution_missing ? "no-row" : row ? STATUS_OF(row.attribution_status) : "unavailable",
        intent: [],
        differs: false,
        terms,
        codeId: {
          title: a.title,
          answer: run.answers[a.provision] as CodeIdAnswer,
          quote: shown?.text ?? null,
          clipped: shown?.clipped ?? false,
          explainer: a.explainer ? { text: a.explainer.text, source: a.explainer.source } : undefined,
          mode: r.mode,
        },
      } satisfies SectionCRow;
    });
}
