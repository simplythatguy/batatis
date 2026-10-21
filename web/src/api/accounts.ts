/**
 * Accounts, applications, messages and the assistant (branch api/accounts-review).
 * Typed by hand from the contract. Every call carries the session cookie when the engine allows it
 * (see engineAuth). A 404 on these routes means "not on this server": callers fall back to the
 * single-visit flow.
 */
import { EngineError } from "./client";
import { credentialsMode, ENGINE_BASE } from "./engineAuth";

export type Role = "applicant" | "reviewer";

export interface User {
  id: string;
  email: string;
  name: string | null;
  role: Role | null;
  applicant_type: string | null;
  authority: string | null;
  onboarded: boolean;
  created_at: string;
}

export type ApplicationStatus = "draft" | "submitted" | "in_review" | "returned" | "accepted" | "withdrawn";

export interface ApplicationSummary {
  id: string;
  title: string;
  status: ApplicationStatus;
  authority: string | null;
  updated_at: string;
  submitted_at: string | null;
  completeness: { answered: number; total: number } | null;
  unread_messages: number;
  reviewer: { name: string } | null;
}

export interface MessageItem {
  gap_id?: string | null;
  field?: string | null;
  note?: string | null;
}

export interface Message {
  id: string;
  author: { id: string; name: string; role: Role | null };
  body: string;
  items: MessageItem[];
  kind: "message" | "decision" | "status";
  created_at: string;
  read_by_me: boolean;
}

export interface AssistRequest {
  case_id?: string;
  screen: string;
  focus?: { kind: string; id: string };
  question: string;
  history?: { role: "user" | "assistant"; text: string }[];
}

export interface AssistResponse {
  answer: string;
  cited: string[];
  removed_citations: string[];
  notice: string | null;
}

export class AccountsError extends EngineError {
  readonly retryAfter: number | null;
  /** Parsed JSON body (409 submit carries the blocking gaps). */
  readonly body: unknown;
  constructor(status: number, detail: string, technical: string, body: unknown = null, retryAfter: number | null = null) {
    super(status, detail, technical);
    this.body = body;
    this.retryAfter = retryAfter;
  }
}

/** The route is not on this server (or the browser could not reach it with credentials). */
export const notAvailable = (e: unknown) => e instanceof EngineError && (e.status === 404 || e.status === 405 || e.status === 0);

function plain(status: number, raw: string, path: string): string {
  if (status === 0) return "The service did not respond.";
  if (status === 401) return "Sign in to continue.";
  if (status === 429) return "Too many requests right now. Try again in a moment.";
  if (path === "/assist" && status === 503) return "The assistant isn't available on this server.";
  if (status === 409 && /submit/.test(path)) return "Some required items are still missing.";
  if (status === 409) return raw || "This application changed or is read-only right now.";
  if (status === 404) return "Not available on this server.";
  return raw || `Request failed (${status}).`;
}

async function call<T>(method: "GET" | "POST", path: string, body?: unknown, signal?: AbortSignal, ms = 15000): Promise<T> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), ms);
  const onAbort = () => ctl.abort();
  if (signal?.aborted) ctl.abort();
  else signal?.addEventListener("abort", onAbort, { once: true });
  let res: Response;
  try {
    res = await fetch(`${ENGINE_BASE}${path}`, {
      method,
      credentials: credentialsMode(),
      signal: ctl.signal,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (e) {
    if (signal?.aborted) throw e;
    throw new AccountsError(0, ctl.signal.aborted ? "The service did not answer in time." : plain(0, "", path), e instanceof Error ? e.message : String(e));
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onAbort);
  }
  if (!res.ok) {
    let parsed: unknown = null;
    let raw = res.statusText;
    try {
      parsed = await res.json();
      const d = (parsed as { detail?: unknown })?.detail;
      raw = typeof d === "string" ? d : JSON.stringify(d ?? parsed);
    } catch {
      /* keep statusText */
    }
    const after = Number(res.headers.get("Retry-After"));
    throw new AccountsError(res.status, plain(res.status, raw, path), `${res.status} ${raw}`, parsed, Number.isFinite(after) && after > 0 ? after : null);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const enc = encodeURIComponent;

export const accounts = {
  me: (signal?: AbortSignal) => call<{ user: User }>("GET", "/auth/me", undefined, signal).then((r) => r.user ?? (r as unknown as User)),
  applications: (signal?: AbortSignal) =>
    call<{ applications: ApplicationSummary[] }>("GET", "/me/applications", undefined, signal).then((r) => r.applications ?? []),
  submit: (caseId: string, signal?: AbortSignal) => call<unknown>("POST", `/cases/${enc(caseId)}/submit`, {}, signal, 30000),
  messages: (caseId: string, signal?: AbortSignal) =>
    call<{ messages: Message[] }>("GET", `/cases/${enc(caseId)}/messages`, undefined, signal).then((r) => r.messages ?? []),
  postMessage: (caseId: string, body: string, signal?: AbortSignal) => call<Message>("POST", `/cases/${enc(caseId)}/messages`, { body }, signal),
  markRead: (caseId: string, signal?: AbortSignal) => call<unknown>("POST", `/cases/${enc(caseId)}/messages/read`, {}, signal),
  assist: (req: AssistRequest, signal?: AbortSignal) => call<AssistResponse>("POST", "/assist", req, signal, 60000),
};

/** Blocking gaps from a 409 submit body, whatever shape the engine settles on. */
export function submitBlockers(e: unknown): { id: string; field: string | null; label: string }[] {
  if (!(e instanceof AccountsError) || e.status !== 409) return [];
  const body = e.body as { detail?: unknown; gaps?: unknown; reasons?: unknown } | null;
  const d = (body?.detail ?? body) as { gaps?: unknown; reasons?: unknown; blocking?: unknown } | string | null;
  const list = (typeof d === "object" && d ? (d.gaps ?? d.blocking ?? d.reasons) : null) ?? body?.gaps ?? body?.reasons;
  if (!Array.isArray(list)) return typeof d === "string" ? [{ id: "submit", field: null, label: d }] : [];
  return list.map((g, n) => {
    if (typeof g === "string") return { id: `submit-${n}`, field: null, label: g };
    const o = g as { id?: string; field?: string; message?: string; label?: string; fix_hint?: string };
    return { id: o.id ?? `submit-${n}`, field: o.field ?? null, label: o.message ?? o.label ?? o.fix_hint ?? "Required item missing" };
  });
}
