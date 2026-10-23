/**
 * The voice relay's public wire shapes (docs/api/voice.md) and the one place commands are built.
 * `VoiceCapability`, `VoiceCommand` and `VoiceScope` are generated from the engine schema; server
 * events are checked here field by field, and anything else is dropped.
 */
import type { VoiceCapability, VoiceCommand, VoiceScope } from "../../api/types.gen";

export const VOICE_PROTOCOL: VoiceCapability["protocol"] = "batatis.voice.v1";
export const RELAY_PATH: VoiceCapability["relay_path"] = "/api/voice/relay/session";

export type CommandType = Exclude<VoiceCommand["type"], "session.end">;
export type Destination = NonNullable<VoiceScope["destinations"]>[number];

/** A complete scope as sent on start and on each context update (every field explicit). */
export interface Scope {
  context_id: string;
  revision: number;
  case_id: string | null;
  case_version: number | null;
  screen: string;
  focus: { kind: string; id: string } | null;
  destinations: Destination[];
  attachment_ids: string[];
}

export interface Identity {
  session_id: string;
  context_id: string;
  revision: number;
}

export function command(type: CommandType, id: Identity, extra: { audio?: string; scope?: Scope } = {}): VoiceCommand {
  return { type, session_id: id.session_id, context_id: id.context_id, revision: id.revision, ...extra };
}

export const END_REASONS = ["ended", "expired", "disconnected", "authorization_changed", "context_changed", "invalid_request", "limit", "unavailable"] as const;
export type EndReason = (typeof END_REASONS)[number];
export const isEndReason = (v: unknown): v is EndReason => typeof v === "string" && (END_REASONS as readonly string[]).includes(v);

/** Every server event carries these; scope fields are null before start. */
export interface ServerEvent {
  type: string;
  session_id: string;
  context_id: string | null;
  revision: number | null;
  case_id: string | null;
  case_version: number | null;
  [key: string]: unknown;
}

const str = (v: unknown, max = 200): v is string => typeof v === "string" && v.length > 0 && v.length <= max;
const intOrNull = (v: unknown) => v === null || (typeof v === "number" && Number.isInteger(v) && v >= 0);

/** One socket message, or null when it is not a well-formed relay event. */
export function parseEvent(data: unknown): ServerEvent | null {
  if (typeof data !== "string" || data.length > 600_000) return null;
  let v: unknown;
  try {
    v = JSON.parse(data);
  } catch {
    return null;
  }
  if (!v || typeof v !== "object" || Array.isArray(v)) return null;
  const e = v as Record<string, unknown>;
  if (!str(e.type, 60) || !str(e.session_id, 80)) return null;
  if (!(e.context_id === null || str(e.context_id, 80)) || !intOrNull(e.revision) || !(e.case_id === null || str(e.case_id, 100)) || !intOrNull(e.case_version)) return null;
  return e as ServerEvent;
}

/**
 * The capability a voice start may trust: the documented protocol and same-origin relay path, a
 * real notice and a sane limit. Anything else reads as unavailable (never another URL).
 */
export function checkCapability(raw: unknown): VoiceCapability | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Partial<VoiceCapability>;
  if (r.protocol !== VOICE_PROTOCOL || r.relay_path !== RELAY_PATH) return null;
  if (typeof r.available !== "boolean" || typeof r.notice !== "string" || !r.notice.trim()) return null;
  if (typeof r.max_seconds !== "number" || !(r.max_seconds > 0) || r.max_seconds > 600) return null;
  return { available: r.available, reason: typeof r.reason === "string" ? r.reason : null, protocol: r.protocol, relay_path: r.relay_path, max_seconds: r.max_seconds, notice: r.notice };
}

/**
 * The relay's WebSocket URL on this page's own origin: `ws:`/`wss:` matching the page, the exact
 * documented path, no credentials, query or fragment. Null when the page cannot reach it that way
 * (another origin's engine, a file: page).
 */
export function relayUrl(page: { protocol: string; host: string }, path: string = RELAY_PATH): string | null {
  if (path !== RELAY_PATH) return null;
  if (page.protocol !== "https:" && page.protocol !== "http:") return null;
  if (!page.host || /[@/\\?#\s]/.test(page.host)) return null;
  const url = `${page.protocol === "https:" ? "wss:" : "ws:"}//${page.host}${path}`;
  try {
    const u = new URL(url);
    if (u.username || u.password || u.search || u.hash || u.pathname !== path || u.host !== page.host) return null;
  } catch {
    return null;
  }
  return url;
}
