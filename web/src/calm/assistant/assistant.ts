/**
 * Assistant state shared by every entry point (Ask, Cmd/Ctrl+J, field Help, officer messages).
 * Answers come only from POST /assist; nothing is invented when they are
 * unavailable.
 *
 * One conversation per binding: the account (id, role, authority) and what it is about, either a
 * saved application, an unsaved draft (each new draft is its own context) or no application (the
 * code library's None). Turns, the unsent draft and attachments stay with their conversation:
 * closing keeps them, switching A → B → A restores A's, and nothing crosses accounts (signing out
 * or another account clears them all). A request belongs to the binding it
 * started in; a switch cancels it and its late reply or plan is ignored.
 */
import { useSyncExternalStore } from "react";
import { AccountsError, accounts, type AssistRequest, type AssistResponse, type AssistContextBinding, type AssistAttachment, type AssistDocumentReference } from "../../api/accounts";
import { engine, EngineError } from "../../api/client";
import { getAccountState } from "../account";
import { getSession } from "../session";
import { questionDrafts } from "../questionDrafts";
import { forgetPositions, savedPosition, savePosition } from "./follow";
import { matchesDocumentReply, sameIds } from "./documents";
import {
  bumpViewGeneration, capturePlace, checkPlan, destinationLabel, isDestination, offeredDestinations, openDestination, returnTo, viewGeneration,
  type DestinationId, type NavRole, type OpenDeps, type PageProbe, type ReturnPoint,
} from "./destinations";

export interface AssistContext {
  /** Screen name sent to the engine: "question", "review", "application", "code", "drawer". */
  screen: string;
  focus?: AssistRequest["focus"];
  /** Internal place label for navigation and return points. */
  label: string;
  /** Suggestion chips for this context. */
  suggestions?: string[];
}

export type NavState = "opening" | "opened" | "failed" | "moved-on" | "not-offered";
export type BackState = "idle" | "returning" | "returned" | "failed";

export interface Turn {
  id: number;
  role: "user" | "assistant";
  text: string;
  cited?: string[];
  removed?: string[];
  notice?: string | null;
  /** A question that got no answer (failed or stopped). Never sent back as history. */
  unanswered?: boolean;
  /** A navigation result: what opened (and the way back), or why it did not. */
  nav?: { label: string; state: NavState; back: ReturnPoint | null; backState: BackState };
  documents?: { attachments: AssistAttachment[]; references: AssistDocumentReference[] };
}

export interface Attachment {
  key: string;
  name: string;
  status: "uploading" | "ready" | "failed";
  /** The file id from POST /cases/{id}/files (or a PDF already on the application). */
  fileId?: string;
  error?: string;
}

export interface AssistError {
  status: number;
  text: string;
  technical: string;
  retryAt: number | null;
}

export interface Conversation {
  turns: Turn[];
  draft: string;
  pending: boolean;
  error: AssistError | null;
  /** The last unanswered question, for Retry. */
  failed: string | null;
  attachments: Attachment[];
  /** Files uploaded in this visit, including ones unselected from the next question. */
  uploaded: { id: string; name: string }[];
}

export type BindingMode = "case" | "draft" | "none";

/** Who is asking and about what. Set by the shell on every change. */
export interface AssistBinding {
  accountId: string | null;
  role: NavRole | null;
  authority: string | null;
  /** case: a saved application; draft: an unsaved new one; none: no application (library None). */
  mode: BindingMode;
  caseId: string | null;
  /** Local application lifetime, kept through its first save so its conversation can follow. */
  draftId?: string;
  /** The short application name for internal navigation. */
  caseName: string;
  /** The owner may add files to it (a draft or returned application). */
  canUpload: boolean;
  /** PDFs already uploaded to it (engine file ids). */
  files: { id: string; name: string }[];
}

export interface AssistantState {
  open: boolean;
  context: AssistContext;
  binding: AssistBinding;
  /** The current binding's conversation. */
  conv: Conversation;
}

const DEFAULT_CONTEXT: AssistContext = { screen: "app", label: "your application", suggestions: ["What happens after I submit?", "What is an alternative solution?"] };
const NO_BINDING: AssistBinding = { accountId: null, role: null, authority: null, mode: "none", caseId: null, caseName: "", canUpload: false, files: [] };
const EMPTY_CONV: Conversation = { turns: [], draft: "", pending: false, error: null, failed: null, attachments: [], uploaded: [] };
export const MAX_ATTACHMENTS = 3;
/** Backend bounds (engine/routes_assist.py): question and history turns ≤ 1500 characters, ≤ 8 turns. */
export const MAX_QUESTION = 1500;
const MAX_HISTORY = 8;
const MAX_CONVERSATIONS = 12;

// —— Dependencies (real by default; tests replace them) ————————————————————————————————

export interface AssistantDeps {
  assist(req: AssistRequest, signal: AbortSignal): Promise<AssistResponse>;
  caseVersion(caseId: string, signal: AbortSignal): Promise<number>;
  upload(caseId: string, file: File): Promise<{ id: string; name: string }>;
  /** The signed-in account right now (the binding must match it before anything is sent). */
  account(): { signedIn: boolean; userId: string | null; role: NavRole | null; authority: string | null };
  page: OpenDeps & PageProbe & { hash(): string; focusId(): string | null; focus(id: string | null): void };
  now(): number;
}

function browserDeps(): AssistantDeps {
  return {
    assist: (req, signal) => accounts.assist(req, signal),
    caseVersion: async (caseId, signal) => (await engine.getCase(caseId, signal)).version,
    upload: (caseId, file) => engine.upload(caseId, file),
    account: () => {
      const a = getAccountState();
      return { signedIn: a.phase === "signed-in" && Boolean(a.user), userId: a.user?.id ?? null, role: a.user?.role ?? null, authority: a.user?.authority ?? null };
    },
    page: {
      path: () => location.hash.replace(/^#/, "").split("?")[0] || "/",
      hash: () => location.hash || "#/",
      // The deck's open card: the session's current key (calm/session.ts), while the deck shows one.
      card: () => {
        if (!document.getElementById("cf-q")) return null;
        const s = getSession();
        return s.queue[s.index] ?? null;
      },
      shows: (selector) => Boolean(document.querySelector(selector)),
      go: (href) => { if (location.hash !== href) location.hash = href; },
      settle: () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))),
      focusId: () => (document.activeElement instanceof HTMLElement && document.activeElement.id ? document.activeElement.id : null),
      focus: (id) => {
        const el = (id && document.getElementById(id)) || document.getElementById("cf-q") || document.getElementById("main");
        if (el instanceof HTMLElement) el.focus({ preventScroll: false });
      },
    },
    now: () => Date.now(),
  };
}

let deps: AssistantDeps | null = null;
const d = (): AssistantDeps => (deps ??= browserDeps());

/** Tests: replace any dependency. */
export function setAssistantDeps(next: Partial<AssistantDeps>) {
  deps = { ...d(), ...next };
}

// —— Store ————————————————————————————————————————————————————————————————————————————

let state: AssistantState = { open: false, context: DEFAULT_CONTEXT, binding: NO_BINDING, conv: EMPTY_CONV };
const listeners = new Set<() => void>();
function emit() {
  for (const l of listeners) l();
}
function set(next: Partial<AssistantState>) {
  state = { ...state, ...next };
  emit();
}

/** Saved conversations by key (most recent last). */
const conversations = new Map<string, Conversation>();
/** A first save renames the same conversation; already approved native actions follow it. */
const savedKeys = new Map<string, string>();
const conversationKey = (k: string) => savedKeys.get(k) ?? k;
let key = "none";
/** Each unsaved draft gets its own number (a new one each time a draft follows an application). */
let draftSeq = 0;
let contextId = newContextId();
let typedRevision = 0;
let turnSeq = 0;
let attachSeq = 0;
let accountEpoch = 0;
let request: { ctl: AbortController; key: string; question: string } | null = null;

/** A fresh random identity per binding lifetime (a guard, not authorization). */
function newContextId(): string {
  const bytes = new Uint8Array(18);
  globalThis.crypto?.getRandomValues?.(bytes);
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return `ctx_${btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "")}`;
}

function keyOf(b: AssistBinding, draft: number): string {
  if (!b.accountId) return "none";
  const who = `${b.accountId}|${b.role ?? "-"}|${b.authority ?? "-"}`;
  if (b.mode === "case" && b.caseId) return `${who}|case:${b.caseId}`;
  return b.mode === "draft" ? `${who}|draft:${b.draftId ?? draft}` : `${who}|none`;
}

/** Change one conversation (the current one is mirrored into the state). */
function patchConv(k: string, patch: Partial<Conversation> | ((c: Conversation) => Partial<Conversation>)) {
  if (k === "none") return;
  const cur = conversations.get(k) ?? EMPTY_CONV;
  const next = { ...cur, ...(typeof patch === "function" ? patch(cur) : patch) };
  conversations.delete(k);
  conversations.set(k, next);
  while (conversations.size > MAX_CONVERSATIONS) {
    const oldest = conversations.keys().next().value as string;
    if (oldest === key) break;
    conversations.delete(oldest);
  }
  if (k === key) set({ conv: next });
}

const conv = () => state.conv;

/**
 * Who is asking and about what. A change of account clears every conversation; a change of
 * application keeps each one with its own binding, cancels what was in flight and retires pending replies.
 */
export function setAssistantBinding(next: AssistBinding) {
  const prev = state.binding;
  const accountChanged = prev.accountId !== next.accountId;
  if (accountChanged || prev.role !== next.role || prev.authority !== next.authority) {
    accountEpoch += 1;
    questionDrafts.clear();
    // A retained role conversation must never come back with an abandoned busy upload.
    for (const [k, c] of conversations) {
      conversations.set(k, { ...c, attachments: c.attachments.map((a) => a.status === "uploading" ? { ...a, status: "failed", error: "Upload interrupted" } : a) });
    }
  }
  if (accountChanged) {
    // Nothing of the previous account survives: not even its cancelled question.
    request?.ctl.abort();
    request = null;
    conversations.clear();
    savedKeys.clear();
    forgetPositions();
    questionDrafts.clear();
    draftSeq += 1;
  } else if (next.mode === "draft" && prev.mode === "case") {
    // A new unsaved application after a saved one: its own conversation.
    draftSeq += 1;
  }
  const nextKey = keyOf(next, draftSeq);
  const changed = nextKey !== key;
  const firstSave = !accountChanged && prev.role === next.role && prev.authority === next.authority
    && prev.mode === "draft" && next.mode === "case" && prev.draftId !== undefined && prev.draftId === next.draftId;
  state = { ...state, binding: next };
  if (!changed) {
    emit();
    return;
  }
  stopRequest(firstSave ? "changed" : "switched");
  if (firstSave && conversations.has(key) && !conversations.has(nextKey)) {
    savedKeys.set(key, nextKey);
    if (savedKeys.size > MAX_CONVERSATIONS) savedKeys.delete(savedKeys.keys().next().value!);
    conversations.set(nextKey, conversations.get(key)!);
    conversations.delete(key);
    const position = savedPosition(key);
    if (position) savePosition(nextKey, position);
  } else if (conversations.has(key)) {
    patchConv(key, (c) => ({ turns: c.turns.map((t) => t.nav ? { ...t, nav: { ...t.nav, state: t.nav.state === "opening" ? "failed" : t.nav.state, backState: t.nav.backState === "returning" ? "failed" : t.nav.backState } } : t) }));
  }
  key = nextKey;
  contextId = newContextId();
  typedRevision = 0;
  bumpViewGeneration();
  set({ conv: conversations.get(key) ?? EMPTY_CONV });
}

/** Kept for existing callers: an application id alone (no account) binds nothing. */
export function setAssistantCase(binding: AssistBinding | string | null) {
  if (binding && typeof binding === "object") setAssistantBinding(binding);
}

/** The key of the current conversation (tests). */
export const assistantKey = () => key;

/** Where the person is now. Only semantic changes retire a pending answer. */
export function setAssistantContext(context: AssistContext) {
  const same = context.screen === state.context.screen && context.focus?.id === state.context.focus?.id && context.focus?.kind === state.context.focus?.kind
    && context.focus?.prompt === state.context.focus?.prompt && context.focus?.why === state.context.focus?.why;
  if (same) {
    if (context.label !== state.context.label) set({ context });
    return;
  }
  changeTypedContext();
  // A different question can share a provision id; its older plans still expire.
  bumpViewGeneration();
  set({ context });
}

export function openAssistant(context?: AssistContext, question?: string) {
  if (context) setAssistantContext(context);
  set({ open: true });
  if (question) void ask(question);
}

/** Close the panel: the conversation stays. */
export function closeAssistant() {
  set({ open: false });
}

export function toggleAssistant() {
  if (state.open) closeAssistant();
  else set({ open: true });
}

export function setDraft(text: string) {
  patchConv(key, { draft: text.slice(0, MAX_QUESTION) });
}

// —— Typed questions ——————————————————————————————————————————————————————————————————

function offered(): DestinationId[] {
  return offeredDestinations({ role: state.binding.role, caseId: state.binding.mode === "case" ? state.binding.caseId : null });
}

/** The binding still belongs to the account that is signed in now (no render race). */
function bound(): boolean {
  const a = d().account();
  return a.signedIn && a.userId !== null && a.userId === state.binding.accountId && a.role === state.binding.role && a.authority === state.binding.authority && key !== "none";
}

const historyOf = (turns: Turn[]) =>
  turns.filter((t) => !t.nav && !t.documents && !t.unanswered && t.text.trim()).slice(-MAX_HISTORY).map((t) => ({ role: t.role, text: t.text.slice(0, MAX_QUESTION) }));

const turn = (t: Omit<Turn, "id">): Turn => ({ id: ++turnSeq, ...t });

/** Cancel the request in flight. Its question stays, unanswered, with Retry. */
function stopRequest(why: "stopped" | "switched" | "changed") {
  const r = request;
  if (!r) return;
  request = null;
  r.ctl.abort();
  patchConv(r.key, (c) => ({
    pending: false,
    failed: r.question,
    error: { status: -1, text: why === "switched" ? "Not answered · you switched" : why === "changed" ? "Not answered · the context changed. Try again here." : "Stopped", technical: "", retryAt: null },
    turns: c.turns.map((t, i) => (i === c.turns.length - 1 && t.role === "user" ? { ...t, unanswered: true } : t)),
  }));
}

function changeTypedContext() {
  stopRequest("changed");
  if (typedRevision >= 1_000_000) { contextId = newContextId(); typedRevision = 0; }
  else typedRevision += 1;
}

export function cancelQuestion() {
  stopRequest("stopped");
}

export async function ask(question: string) {
  const q = question.trim().slice(0, MAX_QUESTION);
  if (!q || conv().pending || !bound()) return;
  const k = key;
  const asked = { key: k, generation: viewGeneration() };
  const ctl = new AbortController();
  request = { ctl, key: k, question: q };
  const history = historyOf(conv().turns);
  const ctx = state.context;
  const b = state.binding;
  const attachmentIds = selectedAttachmentIds();
  const capturedContext = contextId, capturedRevision = typedRevision;
  patchConv(k, (c) => ({ turns: [...c.turns.filter((t) => !t.unanswered || t.text !== q), turn({ role: "user", text: q })], pending: true, error: null, failed: null, draft: c.draft.trim() === q ? "" : c.draft }));
  try {
    let documentBinding: AssistContextBinding | null = null;
    if (attachmentIds.length) {
      if (!b.caseId || !b.accountId) throw new Error("No application for these files");
      const version = await d().caseVersion(b.caseId, ctl.signal);
      if (ctl.signal.aborted || request?.ctl !== ctl || key !== k) return;
      if (!bound()) { stopRequest("changed"); return; }
      if (!Number.isInteger(version) || version < 1) throw new Error("No saved application version");
      documentBinding = { user_id: b.accountId, case_id: b.caseId, case_version: version, context_id: capturedContext, revision: capturedRevision, attachment_ids: attachmentIds };
    }
    const r = await d().assist(
      {
        ...(b.mode === "case" && b.caseId ? { case_id: b.caseId } : {}),
        ...(documentBinding ? { case_version: documentBinding.case_version!, context_id: documentBinding.context_id, revision: documentBinding.revision, attachment_ids: documentBinding.attachment_ids } : {}),
        screen: ctx.screen,
        ...(ctx.focus ? { focus: ctx.focus } : {}),
        question: q,
        history: attachmentIds.length ? [] : history,
        // Only ids the server knows today; a registered extra id is sent once its contract lands.
        destinations: offered() as AssistRequest["destinations"],
      },
      ctl.signal,
    );
    if (ctl.signal.aborted || request?.ctl !== ctl || key !== k) return;
    if (!bound()) { stopRequest("changed"); return; }
    if (contextId !== capturedContext || typedRevision !== capturedRevision || !sameIds(selectedAttachmentIds(), attachmentIds)) { stopRequest("changed"); return; }
    if (documentBinding && !matchesDocumentReply(r, documentBinding)) throw new AccountsError(409, "The document reply no longer matches these files. Try again.", "Document binding or coverage mismatch");
    request = null;
    patchConv(k, { pending: false });
    if (r.navigation) {
      await applyPlan(r.navigation, asked);
      return;
    }
    patchConv(k, (c) => ({ turns: [...c.turns, turn({ role: "assistant", text: r.answer, cited: r.cited ?? [], removed: r.removed_citations ?? [], notice: r.notice, ...(documentBinding ? { documents: { attachments: r.attachments!, references: r.document_references! } } : {}) })] }));
  } catch (e) {
    if (ctl.signal.aborted || request?.ctl !== ctl) return;
    request = null;
    const err = e instanceof AccountsError || e instanceof EngineError ? e : null;
    const status = err?.status ?? 0;
    const retryAfter = e instanceof AccountsError ? e.retryAfter : null;
    patchConv(k, (c) => ({
      pending: false,
      failed: q,
      // The question stays in the box so nothing typed is lost.
      draft: c.draft.trim() ? c.draft : q,
      turns: c.turns.map((t, i) => (i === c.turns.length - 1 && t.role === "user" ? { ...t, unanswered: true } : t)),
      error: {
        status,
        text: status === 401 ? "Sign in to use the assistant." : status === 503 || status === 404 || status === 0 ? "The assistant isn’t available right now." : status === 429 ? "Too many questions right now." : err?.detail ?? "The assistant did not answer.",
        technical: err?.technical ?? String(e),
        retryAt: status === 429 ? d().now() + (retryAfter ?? 15) * 1000 : null,
      },
    }));
  }
}

/** Ask the unanswered question again. */
export function retry() {
  const q = conv().failed;
  if (!q || conv().pending) return;
  patchConv(key, (c) => ({ error: null, failed: null, draft: c.draft.trim() === q ? "" : c.draft }));
  void ask(q);
}

// —— Navigation ———————————————————————————————————————————————————————————————————————

function patchTurn(k: string, id: number, patch: (t: Turn) => Partial<Turn>) {
  k = conversationKey(k);
  if (!conversations.has(k)) return;
  patchConv(k, (c) => ({ turns: c.turns.map((t) => (t.id === id ? { ...t, ...patch(t) } : t)) }));
}

/** Apply a server plan after re-checking it here; the conversation says what happened. */
async function applyPlan(plan: { destination: unknown }, asked: { key: string; generation: number }) {
  const k = asked.key;
  const epoch = accountEpoch;
  const check = checkPlan(plan, asked, { key, generation: viewGeneration(), offered: offered() });
  const label = isDestination(plan.destination) ? destinationLabel(plan.destination) : "That page";
  if (check !== "apply") {
    if (k === key) patchConv(k, (c) => ({ turns: [...c.turns, turn({ role: "assistant", text: "", nav: { label, state: check, back: null, backState: "idle" } })] }));
    return;
  }
  const page = d().page;
  const back = capturePlace(page, state.context.label);
  const t = turn({ role: "assistant", text: "", nav: { label, state: "opening", back, backState: "idle" } });
  patchConv(k, (c) => ({ turns: [...c.turns, t] }));
  const caseId = state.binding.mode === "case" ? state.binding.caseId : null;
  const ok = await openDestination(plan.destination as DestinationId, caseId, page);
  if (epoch !== accountEpoch || key !== conversationKey(k)) return;
  patchTurn(k, t.id, (x) => ({ nav: { ...x.nav!, state: ok ? "opened" : "failed", back: ok && back.href !== page.hash() ? back : null } }));
  // The chat stays open after it navigates, on phones too (user decision 2026-10-22); only the person closes it.
}

/** Go back to where the person was before the assistant opened something. */
export async function goBack(turnId: number) {
  const k = key;
  const epoch = accountEpoch;
  const t = conv().turns.find((x) => x.id === turnId);
  if (!t?.nav?.back || t.nav.backState === "returning") return;
  const back = t.nav.back;
  patchTurn(k, turnId, (x) => ({ nav: { ...x.nav!, backState: "returning" } }));
  const ok = await returnTo(back, d().page);
  if (epoch !== accountEpoch || key !== conversationKey(k)) return;
  patchTurn(k, turnId, (x) => ({ nav: { ...x.nav!, backState: ok ? "returned" : "failed" } }));
}

// —— Attachments (authorized stored file IDs) ——————————————

const uploadError = (e: unknown): string => {
  const status = e instanceof EngineError ? e.status : 0;
  if (status === 409 || status === 403) return "Read-only application";
  if (status === 413) return "Too large";
  if (status === 415 || status === 422) return "PDF only";
  if (status === 404) return "Application not found";
  if (status === 0) return "Couldn’t upload · offline?";
  return "Couldn’t upload";
};

const live = (c: Conversation) => c.attachments.filter((a) => a.status !== "failed");

/** The selected file ids in order; filenames and browser text never authorize a source. */
export function selectedAttachmentIds(c: Conversation = conv()): string[] {
  return c.attachments.filter((a) => a.status === "ready" && a.fileId).map((a) => a.fileId!).slice(0, MAX_ATTACHMENTS);
}

export function canAttach(): boolean {
  return state.binding.mode === "case" && Boolean(state.binding.caseId) && bound();
}

/** The conversation lifetime a browser file chooser was opened in. */
export interface AttachPick { key: string; context: string; epoch: number }

/** Call as the file chooser opens; its files are used only while this lifetime is still current. */
export function beginAttachPick(): AttachPick {
  return { key, context: contextId, epoch: accountEpoch };
}

/**
 * Upload PDFs to the bound application through the normal upload route. The result is recorded
 * on the conversation it was started in (the same application), even after a switch. Files from
 * a chooser (`pick`) opened before a switch of application or account (even A → B → A) are
 * dropped: they were chosen for an application that is no longer the one open.
 */
export async function attachFiles(files: File[], pick?: AttachPick) {
  if (pick && (pick.key !== key || pick.context !== contextId || pick.epoch !== accountEpoch)) return;
  const b = state.binding;
  const caseId = b.caseId;
  if (!canAttach() || !caseId || !b.canUpload) return;
  const k = key;
  const epoch = accountEpoch;
  for (const file of files) {
    if (epoch !== accountEpoch || !boundForUpload(b)) return;
    const pdf = file.type === "application/pdf" || /\.pdf$/i.test(file.name);
    const full = live(conversations.get(k) ?? EMPTY_CONV).length >= MAX_ATTACHMENTS;
    const a: Attachment = { key: `a${++attachSeq}`, name: file.name, status: pdf && !full ? "uploading" : "failed", error: !pdf ? "PDF only" : full ? `Up to ${MAX_ATTACHMENTS}` : undefined };
    patchConv(k, (c) => ({ attachments: [...c.attachments, a] }));
    if (!pdf || full) continue;
    try {
      const saved = await d().upload(caseId, file);
      // Signed out or another account since: that conversation is gone; record nothing.
      if (epoch !== accountEpoch || !conversations.has(k)) return;
      if (!saved?.id || typeof saved.id !== "string") throw new Error("No file id");
      patchConv(k, (c) => ({
        attachments: c.attachments.map((x) => (x.key === a.key ? { ...x, status: "ready", fileId: saved.id } : x)),
        uploaded: [...c.uploaded.filter((x) => x.id !== saved.id), { id: saved.id, name: saved.name || file.name }],
      }));
      if (k === key) { changeTypedContext(); }
    } catch (e) {
      if (epoch !== accountEpoch || !conversations.has(k)) return;
      patchConv(k, (c) => ({ attachments: c.attachments.map((x) => (x.key === a.key ? { ...x, status: "failed", error: uploadError(e) } : x)) }));
    }
  }
}

/** A batch can continue for its original application, but never under a replacement sign-in. */
function boundForUpload(b: AssistBinding): boolean {
  const a = d().account();
  return a.signedIn && a.userId === b.accountId && a.role === b.role && a.authority === b.authority;
}

/** Use a PDF already uploaded to this application. */
export function attachExisting(fileId: string, name: string) {
  if (!canAttach() || ![...state.binding.files, ...conv().uploaded].some((f) => f.id === fileId)) return;
  const c = conv();
  if (c.attachments.some((a) => a.fileId === fileId && a.status !== "failed")) return;
  if (live(c).length >= MAX_ATTACHMENTS) return;
  changeTypedContext();
  patchConv(key, (x) => ({ attachments: [...x.attachments, { key: `a${++attachSeq}`, name, status: "ready", fileId }] }));
}

export function removeAttachment(attachmentKey: string) {
  const was = conv().attachments.find((a) => a.key === attachmentKey);
  if (was?.status === "ready") changeTypedContext();
  patchConv(key, (c) => ({ attachments: c.attachments.filter((a) => a.key !== attachmentKey) }));
}

/** A hash can change without changing the screen/focus sent to the assistant. */
export function assistantRouteChanged() {
  bumpViewGeneration();
}

/**
 * The person chose another application: a plan asked before that never applies, even when the
 * switch then fails and this application stays open. The conversation itself is kept.
 */
export function invalidateAssistantNavigation() {
  assistantRouteChanged();
}

if (typeof window !== "undefined") {
  // Any route change is manual navigation unless the assistant itself is opening something.
  window.addEventListener("hashchange", assistantRouteChanged);
}

/** Tests: forget everything (conversations and binding). */
export function resetAssistant() {
  stopRequest("stopped");
  conversations.clear();
  savedKeys.clear();
  key = "none";
  state = { open: false, context: DEFAULT_CONTEXT, binding: NO_BINDING, conv: EMPTY_CONV };
  emit();
}

function subscribe(l: () => void) {
  listeners.add(l);
  return () => { listeners.delete(l); };
}

/** The state outside React (tests, event handlers). */
export const getAssistantState = (): AssistantState => state;

export function useAssistant(): AssistantState {
  return useSyncExternalStore(subscribe, () => state, () => state);
}

/**
 * Split an answer into prose and quoted code. Lines starting with ">" are quotes; the engine
 * keeps verbatim code text in quotes so it can be shown in the code-text style.
 */
export function answerBlocks(text: string): { kind: "p" | "quote"; text: string }[] {
  const out: { kind: "p" | "quote"; text: string }[] = [];
  let cur: { kind: "p" | "quote"; lines: string[] } | null = null;
  const flush = () => {
    if (cur && cur.lines.join(" ").trim()) out.push({ kind: cur.kind, text: cur.lines.join(" ").replace(/\s+/g, " ").trim() });
    cur = null;
  };
  for (const line of text.split("\n")) {
    // The engine verifies quote lines that start with spaces or tabs and ">"; anything else is plain text.
    const quote = /^[ \t]*>/.test(line);
    if (!line.trim()) { flush(); continue; }
    const kind = quote ? "quote" : "p";
    if (!cur || cur.kind !== kind) { flush(); cur = { kind, lines: [] }; }
    cur.lines.push(quote ? line.replace(/^[ \t]*>[ \t]?/, "") : line);
  }
  flush();
  return out;
}
