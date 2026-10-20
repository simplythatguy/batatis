/**
 * Pure rules shared by the screens and the engine client.
 * Tests live in rules.test.ts.
 */
import { AUTHORITIES, EXIT_COUNT } from "./config";
import type { AuthorityId } from "./types";

export const EXAMPLE_BANNER = "EXAMPLE CASE. Not a real application.";
export const EXAMPLE_EXPORT_BLOCK = "Example cases are not exported. An example is not a real application.";
export const UPLOAD_UNAVAILABLE = "File upload isn't available yet.";
export const UPLOAD_UPFRONT = "Upload isn't available yet. Paste the text instead.";
export const CODED_DB_MESSAGE = "code database not found";

const EXIT_COUNT_TOPIC = /exit count|single exit|one exit|number of exits|only one exit/i;

export function jurisdictionBody(id: Exclude<AuthorityId, "">) {
  const row = AUTHORITIES.find((a) => a.id === id);
  if (!row) throw new Error(`unknown authority ${id}`);
  return { id: row.id, name: row.name, authority: null as null };
}

/** Null until the applicant picks. Never a silent Calgary or Edmonton. */
export function jurisdictionForCreate(authority: AuthorityId) {
  return authority ? jurisdictionBody(authority) : null;
}

export function factSignature(fact: { id: string; field: string; value: unknown; status: string; kind: string }): string {
  const payload = JSON.stringify([fact.field, fact.value, fact.status, fact.kind]);
  let hash = 0;
  for (let i = 0; i < payload.length; i++) hash = (Math.imul(31, hash) + payload.charCodeAt(i)) | 0;
  return `${fact.id}:${(hash >>> 0).toString(36)}`;
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
  if (/code database not found/i.test(detail)) return "codedb";
  return "other";
}

/** Applicant-facing text. A 404 shows the engine's detail in plain language. Never echoes a path. */
export function publicDetail(status: number, detail: string): string {
  const kind = failureKind(status, detail);
  if (kind === "unreachable") return detail || "The engine could not be reached.";
  if (/case not found/i.test(detail)) return "case not found";
  if (/provision not found/i.test(detail)) return "provision not found";
  if (kind === "missing-route") return "That is not available on this engine yet.";
  if (kind === "codedb") return CODED_DB_MESSAGE;
  if (status === 503 || /[/\\]|BATATIS_/.test(detail)) return "The engine is missing a file it needs.";
  return detail;
}

export function uploadMessage(status: number, detail: string): string {
  const kind = failureKind(status, detail);
  if (kind === "missing-route") return UPLOAD_UNAVAILABLE;
  if (kind === "unreachable") return "The engine could not be reached, so this PDF was not read.";
  if (kind === "codedb") return CODED_DB_MESSAGE;
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
