/**
 * Pure rules shared by the screens and the engine client.
 * Tests live in rules.test.ts.
 */
import { resolveOffice, EXIT_COUNT } from "./config";
import type { EngineGap } from "./api/client";
import type { AuthorityId, Candidate, Fact } from "./types";

export const EXAMPLE_BANNER = "EXAMPLE CASE. Not a real application.";
export const EXAMPLE_EXPORT_BLOCK = "Example cases are not exported. An example is not a real application.";
export const UPLOAD_UNAVAILABLE = "File upload isn't available yet.";
export const UPLOAD_UPFRONT = "Upload isn't available yet. Paste the text instead.";
export const CODED_DB_MESSAGE = "code database not found";

const EXIT_COUNT_TOPIC = /exit count|single exit|one exit|number of exits|only one exit/i;

export function jurisdictionBody(id: Exclude<AuthorityId, "">) {
  const row = resolveOffice(id);
  if (!row) throw new Error(`unknown authority ${id}`);
  return { id: row.id, name: row.name, authority: null as null };
}

/** Null until the applicant picks. Never a silent Calgary or Edmonton. */
export function jurisdictionForCreate(authority: AuthorityId) {
  return authority ? jurisdictionBody(authority) : null;
}

export function factSignature(fact: { id: string; field: string; value: unknown; status: string; kind: string }
  & Partial<Pick<Fact, "source" | "confidence" | "formula" | "inputs">>): string {
  const source = fact.source;
  return JSON.stringify([fact.id, fact.field, fact.value, fact.status, fact.kind,
    source ? [source.type, source.ref, source.quote ?? null, source.page ?? null, source.bbox ?? null] : null,
    fact.confidence ?? null, fact.formula ?? null, fact.inputs ?? []]);
}

/** The user's own case is replaced only after they confirm. */
export function shouldConfirmReplace(input: { description: string; factCount: number; fileCount: number }): boolean {
  return Boolean(input.description.trim() || input.factCount > 0 || input.fileCount > 0);
}

export function exampleExportBlocked(exampleId: string | undefined): boolean {
  return Boolean(exampleId);
}

export type FailureKind = "unreachable" | "missing-route" | "stale-case" | "codedb" | "other";

export function failureKind(status: number, detail: string): FailureKind {
  if (status === 0) return "unreachable";
  if (status === 404 && /case not found/i.test(detail)) return "stale-case";
  if (status === 404 && /provision not found/i.test(detail)) return "other";
  if (status === 404 && /identify result not found/i.test(detail)) return "other";
  if (status === 404) return "missing-route";
  if (/code database not found|code database is not available/i.test(detail)) return "codedb";
  return "other";
}

/** Applicant-facing text. A 404 shows the engine's detail in plain language. Never echoes a path. */
export function publicDetail(status: number, detail: string): string {
  const kind = failureKind(status, detail);
  if (kind === "unreachable") return "The review service did not respond.";
  if (/case not found/i.test(detail)) return "case not found";
  if (/provision not found|requirement not found/i.test(detail)) return "This rule isn’t in your code check. Check the code again.";
  if (/identify result not found/i.test(detail)) return "Check the code first.";
  if (kind === "missing-route") return "That isn't available yet.";
  if (kind === "codedb") return "The code database is not available.";
  if (status >= 500 && /[/\\]|BATATIS_/.test(detail)) return "The engine is missing a file it needs.";
  if (/^(bad gateway|internal server error|service unavailable)$/i.test(detail.trim())) return "The review service did not respond.";
  return detail;
}

export function uploadMessage(status: number, detail: string): string {
  const kind = failureKind(status, detail);
  if (kind === "missing-route") return UPLOAD_UNAVAILABLE;
  if (kind === "unreachable") return "The review service did not respond, so this PDF was not read.";
  if (kind === "codedb") return "The code database is not available.";
  return "This PDF was not read.";
}

/** "Retrieved verbatim" only for text the code database returned. Everything else is a summary. */
export function sectionCQuoteLabel(fromCodedb: boolean): { pill: string; meta: string } {
  if (fromCodedb) return { pill: "Code text", meta: "Retrieved verbatim" };
  return { pill: "Summary", meta: "Cached summary" };
}

/**
 * 9.9.4.4 covers openings near exterior exit stairs. It is not the exit-count rule.
 * Returns a correction when a card would cite it for exit count.
 */
export function exitCountWarning(provision: string, topic: string): string | null {
  if (!/9\.9\.4\.4/.test(provision)) return null;
  if (!EXIT_COUNT_TOPIC.test(topic)) return null;
  return `Sentence 9.9.4.4 covers openings near exterior exit stairs. Exit count is NBC(AE) Part 3 ${EXIT_COUNT.part3} (Part 9 equivalent ${EXIT_COUNT.part9}).`;
}

export interface SseEvent {
  event: string;
  data: string;
}

/** Split a text/event-stream buffer into complete events. `rest` is the incomplete tail. */
export function takeSseEvents(buffer: string): { events: SseEvent[]; rest: string } {
  const parts = buffer.split(/\n\n/);
  const rest = parts.pop() ?? "";
  const events: SseEvent[] = [];
  for (const part of parts) {
    if (!part.trim()) continue;
    let event = "message";
    const data: string[] = [];
    for (const line of part.split(/\n/)) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
    }
    events.push({ event, data: data.join("\n") });
  }
  return { events, rest };
}

/** Pull the first URL out of an engine notice so it renders as a link. `: <url>` collapses with it. */
export function splitNoticeUrl(message: string): { text: string; url: string | null } {
  const m = /:?\s*(https?:\/\/[^\s)]+?)(?=[.,]?(?:[\s)]|$))/.exec(message);
  if (!m) return { text: message, url: null };
  return { text: (message.slice(0, m.index) + message.slice(m.index + m[0].length)).replace(/\s{2,}/g, " ").trim(), url: m[1] };
}

export type QuoteKind = "code" | "applicant" | "summary" | "ranking" | "missing";

/** What a card's quote is. Only "code" gets the Code text label and the NRC credit. */
export function quoteKind(a: Pick<Candidate, "identified" | "quote">): QuoteKind {
  if (a.identified === false) return "applicant";
  if (a.quote.source === "ranking" || a.quote.citation === "No code sentence was returned.") return "ranking";
  if (a.quote.source === "summary" || a.quote.citation.includes("not the code sentence")) return "summary";
  if (!a.quote.text.trim()) return "missing";
  return "code";
}

export const QUOTE_LABEL: Record<QuoteKind, { pill: string; meta: string }> = {
  code: { pill: "Code text", meta: "The code says" },
  applicant: { pill: "Your words", meta: "From what you wrote. Not a ranked article." },
  summary: { pill: "Case summary", meta: "Cached summary, not the code sentence" },
  ranking: { pill: "AI-written", meta: "Why this article was ranked. Not code text." },
  missing: { pill: "Code text", meta: "The wording did not load. The citation is under Code reference." },
};

/** Engine gaps that are missing items. `info` items are advice and are never counted. */
export function missingFromEngine(engine: EngineGap[]): (EngineGap & { severity: "blocking" | "warning" })[] {
  return engine.filter((g): g is EngineGap & { severity: "blocking" | "warning" } => g.severity !== "info");
}

/** Messages of engine `info` items, once each. */
export function engineNotices(engine: EngineGap[]): string[] {
  return [...new Set(engine.filter((g) => g.severity === "info").map((g) => g.message.trim()).filter(Boolean))];
}

const EVIDENCE_LINE = /^(.*supporting evidence for )(\S+), (\S+?)\.$/;
export const EVIDENCE_HINT =
  "List the evidence that shows each function and objective is met, and who is responsible for it: for example a test report, a listed system, a product evaluation, or a registered professional's review. Not every evidence type is needed.";

/**
 * The engine sends one evidence line per function–objective pair of a sentence.
 * Lines for the same sentence become one item that names every pair, so the list is not 16 near-copies.
 */
export function groupEvidenceGaps(engine: EngineGap[]): EngineGap[] {
  const out: EngineGap[] = [];
  const groups = new Map<string, { index: number; head: string; pairs: string[] }>();
  for (const g of engine) {
    const m = g.field.startsWith("evidence.") ? EVIDENCE_LINE.exec(g.message.trim()) : null;
    if (!m) {
      out.push(g);
      continue;
    }
    const key = `${m[2]}|${g.severity}`;
    const group = groups.get(key);
    if (group) {
      if (!group.pairs.includes(m[3])) group.pairs.push(m[3]);
      continue;
    }
    groups.set(key, { index: out.length, head: m[1], pairs: [m[3]] });
    out.push(g);
  }
  for (const [key, group] of groups) {
    const provision = key.split("|")[0];
    const first = out[group.index];
    const pairs = group.pairs.length === 1 ? group.pairs[0] : `${group.pairs.length} function–objective pairs: ${group.pairs.join(", ")}`;
    out[group.index] = { ...first, message: `${group.head}${provision} (${pairs}).`, fix_hint: EVIDENCE_HINT };
  }
  return out;
}
