/**
 * The accuracy report as the page shows it. The data is docs/accuracy/report.json, written by
 * scripts/accuracy_report.py and bundled at build time, so the page needs no engine call.
 * Everything here is pure: JSON in, display strings out (tested in report.test.ts).
 */

export interface Source {
  kind: "file" | "pr";
  paths?: string[];
  pr?: number | null;
  commit: string;
  command?: string | null;
  quote?: string;
  ref?: string | null;
}

export interface Figure {
  id: string;
  label: string;
  x: number;
  n: number;
  rate: number | null;
  value: string;
  interval: [number, number] | null;
  interval_kind: string | null;
  dataset: string;
  sample: string;
  date: string;
  tags: string[];
  note: string | null;
  source: Source;
}

export interface DetailTable {
  title: string;
  header: string[];
  rows: string[][];
}

export interface Section {
  id: string;
  title: string;
  plain: string;
  status: "measured" | "provisional" | "not_run";
  caveats: string[];
  figures: Figure[];
  detail?: DetailTable[];
  definition?: string;
  updates_when?: string;
}

export interface TestRef {
  id: string;
  file: string;
  name: string;
  runner: "pytest" | "node";
  result?: string;
}

export interface Claim {
  id: string;
  claim: string;
  detail: string;
  tests: TestRef[];
}

export interface Report {
  schema: string;
  generated_on: string;
  built_from: { commit: string; dirty: boolean };
  edition: string;
  intro: string;
  guaranteed: Claim[];
  verified: { date: string; commit: string; passed: number; skipped: number; total: number } | null;
  measured: Section[];
  not_measured: { title: string; why: string }[];
}

export const SCHEMA = "batatis-accuracy/1";

/** The parts of a report the page cannot do without. Throws with the reason instead of drawing half a page. */
export function checkReport(data: unknown): Report {
  const r = data as Partial<Report> | null;
  if (!r || r.schema !== SCHEMA) throw new Error("The accuracy report has an unknown format.");
  if (typeof r.generated_on !== "string" || typeof r.edition !== "string" || typeof r.intro !== "string" || typeof r.built_from?.commit !== "string") {
    throw new Error("The accuracy report is missing when and how it was built.");
  }
  if (!Array.isArray(r.guaranteed) || !Array.isArray(r.measured) || !Array.isArray(r.not_measured)) {
    throw new Error("The accuracy report is incomplete.");
  }
  for (const c of r.guaranteed) {
    if (!c.tests?.length) throw new Error(`Guaranteed claim ${c.id} names no test.`);
  }
  for (const s of r.measured) {
    if (!["measured", "provisional", "not_run"].includes(s.status as string)) throw new Error(`Section ${s.title} has an unknown status.`);
    for (const f of s.figures) {
      if (!f.source?.commit || !(f.source.paths?.length || f.source.pr)) throw new Error(`Figure ${f.id} has no source.`);
      if (!(f.n > 0)) throw new Error(`Figure ${f.id} has no sample size.`);
      if (typeof f.value !== "string" || typeof f.label !== "string" || !Number.isFinite(f.x)) throw new Error(`Figure ${f.id} is incomplete.`);
    }
  }
  return r as Report;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-10-21" -> "21 Oct 2026"; "2026-10-21 to 2026-10-22" keeps both ends. Anything else is shown as given. */
export function dateText(value: string): string {
  return value
    .split(" to ")
    .map((d) => {
      const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(d);
      return m ? `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]} ${m[1]}` : d;
    })
    .join(" to ");
}

export function percent(x: number | null): string {
  if (x == null) return "—";
  if (x >= 1) return "100%";
  if (x <= 0) return "0%";
  // Never round a rate below one up to 100%, or a rate above zero down to 0%.
  const v = Math.min(Math.max(x * 100, 0.1), 99.9);
  return `${v.toFixed(1)}%`;
}

/** "95% interval 97.6–100%" or null when the figure has none (a count of checks, a count of vectors). */
export function intervalText(f: Figure): string | null {
  if (!f.interval) return null;
  return `95% interval ${percent(f.interval[0]).replace("%", "")}–${percent(f.interval[1])}`;
}

export function sourceText(s: Source): string {
  const commit = s.commit.slice(0, 7);
  if (s.kind === "pr") return `PR #${s.pr} description, merge commit ${commit}`;
  const where = (s.paths ?? []).join(", ");
  const pr = s.pr ? `, PR #${s.pr}` : "";
  return `${where} at commit ${commit}${s.ref ? ` (${s.ref})` : ""}${pr}`;
}

const TAG: Record<string, string> = {
  "in-sample": "In sample",
  "model-checked": "Model-checked",
  "no longer blind": "No longer blind",
  blind: "Blind",
  "first run": "First run",
  unreviewed: "Unreviewed",
  provisional: "Provisional",
  "example data": "Example data",
  "selection folds": "Used to choose",
  "development folds": "Not used to choose",
  "relevance stage only": "Relevance stage only",
};

export function tagText(tag: string): string {
  return TAG[tag] ?? tag.charAt(0).toUpperCase() + tag.slice(1);
}

export interface FigureView {
  id: string;
  label: string;
  value: string;
  rate: string;
  interval: string | null;
  meta: string;
  tags: string[];
  note: string | null;
  source: string;
  quote: string | null;
  command: string | null;
}

export function figureView(f: Figure): FigureView {
  return {
    id: f.id,
    label: f.label,
    value: f.value,
    rate: percent(f.rate),
    interval: intervalText(f),
    meta: `${f.dataset} · ${f.sample} · ${dateText(f.date)}`,
    tags: f.tags.map(tagText),
    note: f.note,
    source: sourceText(f.source),
    quote: f.source.quote ?? null,
    command: f.source.command ?? null,
  };
}

export const STATUS_TEXT: Record<Section["status"], string | null> = {
  measured: null,
  provisional: "Provisional",
  not_run: "Not run yet",
};

export function builtText(r: Report): string {
  return `Built ${dateText(r.generated_on)} from commit ${r.built_from.commit.slice(0, 7)} · ${r.edition}`;
}

export function verifiedText(r: Report): string | null {
  const v = r.verified;
  if (!v) return null;
  const skipped = v.skipped ? `, ${v.skipped} skipped` : "";
  return `Last run: ${v.passed} of ${v.total} tests passed${skipped}, ${dateText(v.date)}.`;
}
