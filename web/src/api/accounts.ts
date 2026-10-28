/**
 * Accounts, applications, messages and the assistant (branch api/accounts-review).
 * Typed by hand from the contract. Every call carries the session cookie when the engine allows it
 * (see engineAuth). A 404 on these routes means "not on this server": callers fall back to the
 * single-visit flow.
 */
import { EngineError } from "./client";
import { credentialsMode, ENGINE_BASE } from "./engineAuth";
import { accountRequestSignal } from "./requestLifetime";
import type { AssistFocus, AssistNavigation, Case, ProfessionalRequirementRequest } from "./types.gen";

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

export type ApplicationStatus = "draft" | "submitted" | "in_review" | "returned" | "accepted" | "refused" | "withdrawn";

export interface ApplicationSummary {
  id: string;
  title: string;
  status: ApplicationStatus;
  authority: string | null;
  updated_at: string;
  submitted_at: string | null;
  submission_number?: number;
  expires_at?: string | null;
  completeness: { answered: number; total: number } | null;
  unread_messages: number;
  reviewer: { name: string } | null;
  /** The owner's own sidebar shelf. Organises the list only; it never withdraws a sent application. */
  archived: boolean;
  /** Kept above the other applications (and kept while archived, shown again on restore). */
  pinned: boolean;
}

/** PATCH /me/applications/{id}/preferences: at least one of the two. */
export type ApplicationPreferences = { archived?: boolean; pinned?: boolean };

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

export interface Conversation {
  messages: Message[];
  decision: Case["decision"];
}

export interface AssistRequest {
  case_id?: string;
  case_version?: number;
  context_id?: string;
  revision?: number;
  attachment_ids?: string[];
  screen: string;
  focus?: AssistFocus;
  question: string;
  history?: { role: "user" | "assistant"; text: string }[];
  /** Destination ids this browser can open right now (docs/api/assistant-navigation.md); never URLs. */
  destinations?: (AssistNavigation["destination"] | "comments")[];
}

/** Additive typed-excerpt contract: docs/api/assistant-documents.md. No document body is sent. */
export interface AssistContextBinding {
  user_id: string;
  context_id: string;
  revision: number;
  case_id: string | null;
  case_version: number | null;
  attachment_ids: string[];
}
export interface AssistAttachment {
  case_id: string;
  file_id: string;
  name: string;
  content_state: "not_read" | "text_excerpt";
  pages: number[];
  truncated: boolean;
  reason?: string | null;
}
export interface AssistDocumentReference {
  case_id: string;
  file_id: string;
  page: number;
  quote: string;
}

export interface AssistResponse {
  answer: string;
  cited: string[];
  removed_citations: string[];
  notice: string | null;
  /** A plan for an explicit "open …" request. The browser checks and applies it; it is not proof anything opened. */
  navigation?: AssistNavigation | { destination: "comments" } | null;
  context?: AssistContextBinding | null;
  attachments?: AssistAttachment[];
  document_references?: AssistDocumentReference[];
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

export class QueueSessionChanged extends AccountsError {
  constructor() {
    super(409, "Your sign-in changed. Sign in again before loading this queue.", "queue reviewer/authority mismatch");
  }
}

/** The route is not on this server (or the browser could not reach it with credentials). */
export const notAvailable = (e: unknown) => e instanceof EngineError && (e.status === 404 || e.status === 405 || e.status === 0);

function plain(status: number, raw: string, path: string): string {
  if (status === 0) return "The service did not respond.";
  if (status === 401 && path === "/auth/login") return "Email or password is incorrect.";
  if (status === 401) return "Sign in to continue.";
  if (status === 429) return "Too many attempts right now. Try again in a moment.";
  if (status === 422) return "Some of what you entered isn't valid.";
  if (status === 403) return raw || "You don't have access to this.";
  if (path === "/assist" && status === 503) return "The assistant isn't available on this server.";
  if (status === 409 && /submit/.test(path)) return "Some required items are still missing.";
  if (status === 409) return raw || "This application changed or is read-only right now.";
  if (status === 404) return "Not available on this server.";
  return raw || `Request failed (${status}).`;
}

export async function call<T>(method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE", path: string, body?: unknown, parent?: AbortSignal, ms = 15000): Promise<T> {
  const signal = accountRequestSignal(parent);
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
      // FormData sets its own multipart boundary; everything else is JSON.
      headers: body === undefined || body instanceof FormData ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body),
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
  /** Every owned application, archived ones included; a server without preferences reads as neither. */
  applications: (signal?: AbortSignal) =>
    call<{ applications: ApplicationSummary[] }>("GET", "/me/applications", undefined, signal).then((r) =>
      (r.applications ?? []).map((a) => ({ ...a, archived: a.archived === true, pinned: a.pinned === true }))),
  /** Pin or archive in the owner's list. Changes no case content, status or version. */
  preferences: (id: string, patch: ApplicationPreferences, signal?: AbortSignal) =>
    call<{ archived: boolean; pinned: boolean }>("PATCH", `/me/applications/${enc(id)}/preferences`, patch, signal).then((r) => ({
      archived: r.archived === true,
      pinned: r.pinned === true,
    })),
  /** Permanently delete an owned application (204). */
  deleteCase: (id: string, signal?: AbortSignal) => call<void>("DELETE", `/cases/${enc(id)}`, undefined, signal),
  /** Submits exactly the displayed saved revision (`expected_version`); a newer save is a 409. */
  submit: (caseId: string, expectedVersion: number, signal?: AbortSignal) =>
    call<Case>("POST", `/cases/${enc(caseId)}/submit`, { expected_version: expectedVersion }, signal, 30000),
  messages: (caseId: string, signal?: AbortSignal) =>
    call<{ messages: Message[] }>("GET", `/cases/${enc(caseId)}/messages`, undefined, signal).then((r) => r.messages ?? []),
  conversation: (caseId: string, signal?: AbortSignal) =>
    call<Conversation>("GET", `/cases/${enc(caseId)}/messages`, undefined, signal),
  // Communication leaves Case.version unchanged. Never adopt a content revision from the thread.
  postMessage: (caseId: string, body: string, signal?: AbortSignal) => call<Message>("POST", `/cases/${enc(caseId)}/messages`, { body }, signal),
  markRead: (caseId: string, messageIds?: string[], signal?: AbortSignal) =>
    call<void>("POST", `/cases/${enc(caseId)}/messages/read`, messageIds ? { message_ids: messageIds } : {}, signal),
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

/* —— Sign-in, onboarding, review queue, decisions and notifications (U2) —— */

export interface AuthProvider {
  id: string;
  label: string;
}

export type ApplicantKind = "manufacturer" | "contractor" | "homebuilder";
export type AuthorityKey = "calgary" | "edmonton";

export interface OnboardingRequest {
  role: Role;
  applicant_type?: ApplicantKind;
  authority?: AuthorityKey;
  access_code?: string;
}

export interface Claim {
  reviewer_id: string;
  reviewer_name: string;
  claimed_at: string;
}

export interface QueueApplication {
  id: string;
  title: string | null;
  applicant: { name: string; applicant_type: string | null };
  authority: string | null;
  status: ApplicationStatus;
  submitted_at: string | null;
  submission_number?: number;
  expires_at?: string | null;
  updated_at: string;
  completeness: { answered: number; total: number } | null;
  claim: Claim | null;
  decision: { outcome: "accept" | "return" | "refuse"; by_name: string; at: string } | null;
  unread_messages: number;
}

export interface DecisionItemInput {
  gap_id?: string;
  field?: string;
  section?: "A" | "B" | "C" | "D" | "process";
  label?: string;
  request_item_id?: string;
  finding_key?: string;
  note: string;
}

export type DecisionRequest =
  | { outcome: "accept"; expected_version: number; review_version?: number }
  | { outcome: "return"; message: string; items: DecisionItemInput[]; expected_version?: number }
  | { outcome: "refuse"; message: string; expected_version: number };

export interface AppNotification {
  id: string;
  case_id: string;
  case_title: string | null;
  kind: "status" | "message";
  status: string | null;
  submission_number?: number | null;
  actor: { name: string; role: Role | null } | null;
  summary: string;
  created_at: string;
  read: boolean;
}

/** The claim inside a 409 from POST /review/{id}/claim ("Already being reviewed"). */
export function claimConflict(e: unknown): Claim | null {
  if (!(e instanceof AccountsError) || e.status !== 409) return null;
  const c = (e.body as { claim?: Claim } | null)?.claim;
  return c && typeof c.reviewer_name === "string" ? c : null;
}

const userOf = (r: { user?: User } | User) => ("user" in r && r.user ? r.user : (r as User));

export const auth = {
  providers: (signal?: AbortSignal) =>
    call<{ providers: AuthProvider[] }>("GET", "/auth/providers", undefined, signal).then((r) => r.providers ?? []),
  /** "code" where an access code is the only way in (the hosted site); "password" for a local engine. */
  signInMode: (signal?: AbortSignal) =>
    call<{ sign_in?: string }>("GET", "/auth/providers", undefined, signal).then((r) => (r.sign_in === "code" ? "code" as const : "password" as const)),
  codeLogin: (body: { code: string; name: string }) => call<{ user: User }>("POST", "/auth/code-login", body).then(userOf),
  signup: (body: { name: string; email: string; password: string }) => call<{ user: User }>("POST", "/auth/signup", body).then(userOf),
  login: (body: { email: string; password: string }) => call<{ user: User }>("POST", "/auth/login", body).then(userOf),
  logout: () => call<void>("POST", "/auth/logout", {}),
  onboarding: (body: OnboardingRequest) => call<{ user: User }>("POST", "/auth/onboarding", body).then(userOf),
  /** Full-page navigation target for an OAuth provider; `redirect` is the app path to land on. */
  oauthStart: (provider: string, redirect: string) =>
    `${ENGINE_BASE}/auth/oauth/${enc(provider)}/start?redirect=${enc(redirect)}`,
};

export const review = {
  queue: (signal?: AbortSignal, expected?: { id: string; authority: string | null }) =>
    call<{ applications: QueueApplication[]; reviewer_id: string; authority: string }>("GET", "/review/queue", undefined, signal).then(r => {
      if (expected && (r.reviewer_id !== expected.id || r.authority !== expected.authority)) throw new QueueSessionChanged();
      return r.applications ?? [];
    }),
  claim: (caseId: string, takeOver = false, signal?: AbortSignal) =>
    call<{ claim: Claim }>("POST", `/review/${enc(caseId)}/claim`, takeOver ? { take_over: true } : {}, signal).then((r) => r.claim),
  release: (caseId: string) => call<void>("DELETE", `/review/${enc(caseId)}/claim`),
  decide: (caseId: string, body: DecisionRequest) => call<Case>("POST", `/review/${enc(caseId)}/decision`, body, undefined, 30000),
  resolveProfessional: (caseId: string, body: ProfessionalRequirementRequest) =>
    call<Case>("POST", `/review/${enc(caseId)}/professional-requirement`, body, undefined, 30000),
};

export const notifications = {
  list: (signal?: AbortSignal) =>
    call<{ notifications: AppNotification[]; unread: number }>("GET", "/me/notifications", undefined, signal).then((r) => ({
      notifications: r.notifications ?? [],
      unread: typeof r.unread === "number" ? r.unread : (r.notifications ?? []).filter((n) => !n.read).length,
    })),
  markAllRead: (signal?: AbortSignal) => call<void>("POST", "/me/notifications/read", {}, signal),
};

/** Whether this server needs an access code for AI, and whether the signed-in account has a current one. */
export interface AiAccess { required: boolean; granted: boolean }

/** One AI access code as the site admin sees it; the code itself is shown only when it is made. */
export interface AccessCodeInfo {
  name: string;
  source: "managed" | "environment";
  max_users: number | null;
  accounts: number;
  in_use: number;
  revoked: boolean;
}

export const aiAccess = {
  read: () => call<AiAccess>("GET", "/auth/ai-access"),
  enter: (code: string) => call<AiAccess>("POST", "/auth/ai-access", { code }),
  remove: () => call<AiAccess>("DELETE", "/auth/ai-access", {}),
};

export const adminCodes = {
  list: () => call<{ codes: AccessCodeInfo[] }>("GET", "/admin/access-codes").then((r) => r.codes),
  create: (name: string, max_users: number | null) => call<{ code: string; info: AccessCodeInfo }>("POST", "/admin/access-codes", { name, max_users }),
  change: (name: string, patch: { max_users?: number | null; revoked?: boolean }) => call<AccessCodeInfo>("PATCH", `/admin/access-codes/${enc(name)}`, patch),
};
