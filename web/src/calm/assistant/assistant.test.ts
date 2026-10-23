import assert from "node:assert/strict";
import { test, beforeEach } from "node:test";
import type { AssistRequest, AssistResponse } from "../../api/accounts.ts";
import { VoiceClient, type SocketLike, type VoiceAudio } from "../voice/session.ts";
import {
  ask, assistantKey, assistantRouteChanged, attachExisting, attachFiles, cancelQuestion, closeAssistant, goBack, loadVoiceCapability, openAssistant, removeAttachment, requestVoice, resetAssistant, retry,
  getAssistantState, selectedAttachmentIds, setAssistantBinding, setAssistantContext, setAssistantDeps, setDraft, startVoice, type AssistBinding, type AssistantDeps,
} from "./assistant.ts";
import { bumpViewGeneration, checkPlan, offeredDestinations, registerPanel } from "./destinations.ts";
import { clearEngineSession, engineGeneration } from "../../api/sync.ts";
import { questionDrafts } from "../questionDrafts.ts";

const state = () => getAssistantState();
const flush = async () => { for (let i = 0; i < 5; i++) await new Promise((r) => setTimeout(r, 0)); };

function deferred<T>() {
  let resolve!: (v: T) => void, reject!: (e: unknown) => void;
  const promise = new Promise<T>((a, b) => { resolve = a; reject = b; });
  return { promise, resolve, reject };
}

const USER = (id = "u1"): Pick<AssistBinding, "accountId" | "role" | "authority"> => ({ accountId: id, role: "applicant", authority: null });
const caseBinding = (caseId: string, over: Partial<AssistBinding> = {}): AssistBinding => ({ ...USER(), mode: "case", caseId, caseName: `App ${caseId}`, canUpload: true, files: [], ...over });
const draftBinding = (over: Partial<AssistBinding> = {}): AssistBinding => ({ ...USER(), mode: "draft", caseId: null, caseName: "", canUpload: false, files: [], ...over });
const signedOut: AssistBinding = { accountId: null, role: null, authority: null, mode: "none", caseId: null, caseName: "", canUpload: false, files: [] };

interface Fake {
  requests: { req: AssistRequest; signal: AbortSignal; reply: ReturnType<typeof deferred<AssistResponse>> }[];
  uploads: { caseId: string; reply: ReturnType<typeof deferred<{ id: string; name: string }>> }[];
  page: { path: string; card: string | null; hash: string; focused: string | null; went: string[]; redirect: ((href: string) => string) | null; shown: Set<string> };
  user: string | null;
  capabilityReads: (string | null)[];
  mic: { asked: number; stopped: number };
  sockets: FakeSocket[];
  notice: boolean;
}

class FakeSocket implements SocketLike {
  readyState = 1;
  bufferedAmount = 0;
  sent: Record<string, unknown>[] = [];
  closed = false;
  onmessage: ((e: { data: unknown }) => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;
  onerror: (() => void) | null = null;
  send(data: string) { this.sent.push(JSON.parse(data)); }
  close() { this.closed = true; this.readyState = 3; }
  emit(e: Record<string, unknown>) { this.onmessage?.({ data: JSON.stringify(e) }); }
}

const silentAudio = (): VoiceAudio => ({ async startCapture() {}, setMuted() {}, play() {}, clearPlayback() {}, clearCapture() {}, level: () => 0, speaking: () => false, close() {} });

let f: Fake;

beforeEach(() => {
  resetAssistant();
  f = { requests: [], uploads: [], page: { path: "/questions", card: "field-owner", hash: "#/questions", focused: "cf-q", went: [], redirect: null, shown: new Set() }, user: "u1", capabilityReads: [], mic: { asked: 0, stopped: 0 }, sockets: [], notice: false };
  const deps: Partial<AssistantDeps> = {
    assist: (req, signal) => { const reply = deferred<AssistResponse>(); f.requests.push({ req, signal, reply }); return reply.promise; },
    voiceCapability: async (caseId) => { f.capabilityReads.push(caseId); return { available: true, reason: null, protocol: "batatis.voice.v1", relay_path: "/api/voice/relay/session", max_seconds: 55, notice: "Voice sends your microphone audio to a third-party AI service." }; },
    caseVersion: async () => 7,
    upload: (caseId) => { const reply = deferred<{ id: string; name: string }>(); f.uploads.push({ caseId, reply }); return reply.promise; },
    account: () => ({ signedIn: f.user !== null, userId: f.user, role: "applicant", authority: null }),
    page: {
      path: () => f.page.path,
      hash: () => f.page.hash,
      card: () => f.page.card,
      shows: (sel) => f.page.shown.has(sel),
      go: (href) => {
        f.page.went.push(href);
        const to = f.page.redirect ? f.page.redirect(href) : href;
        const [path, query = ""] = to.replace(/^#/, "").split("?");
        f.page.path = path || "/";
        f.page.hash = to;
        f.page.card = new URLSearchParams(query).get("focus");
      },
      settle: async () => {},
      focusId: () => f.page.focused,
      focus: (id) => { f.page.focused = id; },
    },
    voice: (events) => new VoiceClient({
      socket: () => { const s = new FakeSocket(); f.sockets.push(s); return s; },
      microphone: async () => { f.mic.asked += 1; return { stop: () => { f.mic.stopped += 1; } }; },
      audio: () => silentAudio(),
      now: () => 1_000_000,
      setTimer: () => 0,
      clearTimer: () => {},
      page: () => ({ protocol: "https:", host: "batatis.example" }),
    }, events),
    phone: () => false,
    noticeSeen: () => f.notice,
    markNoticeSeen: () => { f.notice = true; },
    setTimer: (fn) => { queueMicrotask(fn); return 1; },
    clearTimer: () => {},
    now: () => 1_000_000,
  };
  setAssistantDeps(deps);
  setAssistantContext({ screen: "question", focus: { kind: "card", id: "field-owner" }, label: "question 1" });
});

test("a reply that arrives after switching A → B never lands in B; A keeps its question with Retry", async () => {
  setAssistantBinding(caseBinding("A"));
  void ask("What is a variance?");
  assert.equal(f.requests[0].req.case_id, "A");
  setAssistantBinding(caseBinding("B"));
  assert.equal(f.requests[0].signal.aborted, true, "the stale request is aborted");
  f.requests[0].reply.resolve({ answer: "A's answer", cited: [], removed_citations: [], notice: "" });
  await flush();
  assert.deepEqual(state().conv.turns, [], "B starts clean");
  setAssistantBinding(caseBinding("A"));
  const a = state().conv;
  assert.equal(a.turns.length, 1);
  assert.equal(a.turns[0].unanswered, true);
  assert.equal(a.failed, "What is a variance?");
  assert.match(a.error!.text, /switched/);
  assert.ok(!a.turns.some((t) => t.text === "A's answer"));
  retry();
  assert.equal(f.requests[1].req.case_id, "A");
  assert.equal(f.requests[1].req.question, "What is a variance?");
});

test("new unsaved local application identities cancel old requests and start separate conversations", () => {
  setAssistantBinding(draftBinding({ draftId: "local-first" }));
  setDraft("First application's draft"); void ask("First application's question");
  const key = assistantKey();
  setAssistantBinding(draftBinding({ draftId: "local-second" }));
  assert.notEqual(assistantKey(), key); assert.equal(f.requests[0].signal.aborted, true);
  assert.equal(state().conv.draft, ""); assert.equal(state().conv.turns.length, 0);
});

test("new unsaved applications use the store lifetime even when emptyCase reuses its local id", () => {
  const local = "case-homebuilder";
  setAssistantBinding(draftBinding({ draftId: `${engineGeneration()}:${local}` }));
  setDraft("Old application's draft"); void ask("Old application's question"); const before = assistantKey();
  clearEngineSession();
  setAssistantBinding(draftBinding({ draftId: `${engineGeneration()}:${local}` }));
  assert.notEqual(assistantKey(), before); assert.equal(f.requests[0].signal.aborted, true); assert.equal(state().conv.draft, "");
});

test("an old multi-file batch cannot resume after a new sign-in recreates the same case key", async () => {
  setAssistantBinding(caseBinding("A"));
  void attachFiles([{ name: "first.pdf", type: "application/pdf" } as File, { name: "second.pdf", type: "application/pdf" } as File]);
  f.user = null; setAssistantBinding(signedOut); f.user = "u1"; setAssistantBinding(caseBinding("A")); setDraft("New sign-in");
  f.uploads[0].reply.resolve({ id: "old-file", name: "first.pdf" }); await flush();
  assert.equal(f.uploads.length, 1); assert.deepEqual(state().conv.attachments, []);
});

test("a role change outside the deck clears unfinished form text immediately", () => {
  setAssistantBinding(caseBinding("A"));
  const who = JSON.stringify(["u1", "applicant", null]);
  const scope = questionDrafts.scope(who, 1, "A");
  questionDrafts.write(scope, "card", "", "Private unfinished text");
  setAssistantBinding(caseBinding("A", { role: "reviewer", authority: "edmonton" }));
  setAssistantBinding(caseBinding("A"));
  assert.equal(questionDrafts.read(questionDrafts.scope(who, 2, "A"), "card", ""), "");
});

test("the same application's first save retains conversation and typing, but retires an unbound request", async () => {
  setAssistantBinding(draftBinding({ draftId: "visit-1" }));
  void ask("What is an alternative solution?");
  f.requests[0].reply.resolve({ answer: "A draft explanation", cited: [], removed_citations: [], notice: "" }); await flush();
  void ask("Explain my current proposal"); setDraft("My next unfinished question");
  setAssistantBinding(caseBinding("A", { draftId: "visit-1" }));
  assert.equal(state().conv.turns[1].text, "A draft explanation");
  assert.equal(state().conv.draft, "My next unfinished question");
  assert.equal(state().conv.failed, "Explain my current proposal");
  assert.equal(f.requests[1].signal.aborted, true);
  f.requests[1].reply.resolve({ answer: "Obsolete unbound answer", cited: [], removed_citations: [], notice: "" }); await flush();
  assert.ok(!state().conv.turns.some(t => t.text === "Obsolete unbound answer"));
  setAssistantBinding(draftBinding({ draftId: "visit-2" }));
  assert.equal(state().conv.turns.length, 0); assert.equal(state().conv.draft, "");
});

test("an uploaded PDF can be unselected and selected again without uploading a second copy", async () => {
  setAssistantBinding(caseBinding("A")); void attachFiles([{ name: "report.pdf", type: "application/pdf" } as File]);
  f.uploads[0].reply.resolve({ id: "stored-report", name: "report.pdf" }); await flush();
  removeAttachment(state().conv.attachments[0].key);
  attachExisting("stored-report", "report.pdf");
  assert.deepEqual(selectedAttachmentIds(), ["stored-report"]); assert.equal(f.uploads.length, 1);
  setAssistantBinding(caseBinding("B")); attachExisting("stored-report", "report.pdf"); assert.deepEqual(selectedAttachmentIds(), []);
});

test("returning to an earlier role cannot revive an indefinitely uploading attachment", async () => {
  setAssistantBinding(caseBinding("A")); void attachFiles([{ name: "report.pdf", type: "application/pdf" } as File]);
  setAssistantBinding(caseBinding("A", { role: "reviewer", authority: "edmonton" }));
  f.uploads[0].reply.resolve({ id: "old-file", name: "report.pdf" }); await flush();
  setAssistantBinding(caseBinding("A")); setDraft("A fresh question");
  assert.ok(state().conv.attachments.every((a) => a.status !== "uploading"));
  void ask(state().conv.draft); assert.equal(f.requests.length, 1, "typing remains usable without manually removing the retired upload");
});

test("typed PDF requests use real IDs and current version, exclude history, and display matching coverage", async () => {
  setAssistantBinding(caseBinding("A", { files: [{ id: "stored-file", name: "report.pdf" }] }));
  attachExisting("stored-file", "report.pdf"); void ask("Which dimension is stated?"); await flush();
  const r = f.requests[0]; assert.equal(r.req.case_version, 7); assert.deepEqual(r.req.attachment_ids, ["stored-file"]);
  assert.match(r.req.context_id!, /^[A-Za-z0-9_-]{16,80}$/); assert.deepEqual(r.req.history, []);
  const context = { user_id: "u1", case_id: "A", case_version: 7, context_id: r.req.context_id!, revision: r.req.revision!, attachment_ids: ["stored-file"] };
  r.reply.resolve({ answer: "Exact excerpt: Width is 120 mm.", cited: [], removed_citations: [], notice: null, context, attachments: [{ case_id: "A", file_id: "stored-file", name: "report.pdf", content_state: "text_excerpt", pages: [1], truncated: true }], document_references: [{ case_id: "A", file_id: "stored-file", page: 1, quote: "Width is 120 mm." }] });
  await flush(); assert.equal(state().conv.turns.at(-1)?.documents?.references[0].page, 1);
});

test("changing selected PDFs aborts a request; a later mismatched source reply releases no answer", async () => {
  setAssistantBinding(caseBinding("A", { files: [{ id: "file", name: "report.pdf" }] }));
  attachExisting("file", "report.pdf"); void ask("Find the width"); await flush();
  const old = f.requests[0]; removeAttachment(state().conv.attachments[0].key);
  assert.equal(old.signal.aborted, true);
  old.reply.resolve({ answer: "Old PDF answer", cited: [], removed_citations: [], notice: null }); await flush();
  assert.ok(!state().conv.turns.some((t) => t.text === "Old PDF answer"));
  attachExisting("file", "report.pdf"); void ask("Find the width"); await flush();
  f.requests[1].reply.resolve({ answer: "Unbound answer", cited: [], removed_citations: [], notice: null }); await flush();
  assert.ok(!state().conv.turns.some((t) => t.text === "Unbound answer")); assert.equal(state().conv.error?.status, 409);
});

test("drafts and turns stay with their application across close and switch", async () => {
  setAssistantBinding(caseBinding("A"));
  void ask("First");
  f.requests[0].reply.resolve({ answer: "One", cited: [], removed_citations: [], notice: "" });
  await flush();
  setDraft("half-typed for A");
  closeAssistant();
  openAssistant();
  assert.equal(state().conv.draft, "half-typed for A", "closing keeps the draft");
  setAssistantBinding(caseBinding("B"));
  assert.equal(state().conv.draft, "");
  setDraft("for B");
  setAssistantBinding(caseBinding("A"));
  assert.equal(state().conv.draft, "half-typed for A");
  assert.deepEqual(state().conv.turns.map((t) => t.text), ["First", "One"]);
  setAssistantBinding(caseBinding("B"));
  assert.equal(state().conv.draft, "for B");
});

test("each new unsaved application is its own conversation, separate from saved ones", async () => {
  setAssistantBinding(draftBinding());
  void ask("Draft question");
  f.requests[0].reply.resolve({ answer: "Draft answer", cited: [], removed_citations: [], notice: "" });
  await flush();
  assert.equal(f.requests[0].req.case_id, undefined, "an unsaved draft sends no application id");
  const firstDraft = assistantKey();
  setAssistantBinding(caseBinding("A"));
  assert.deepEqual(state().conv.turns, []);
  setAssistantBinding(draftBinding());
  assert.notEqual(assistantKey(), firstDraft, "a new draft after a saved application is a new context");
  assert.deepEqual(state().conv.turns, []);
});

test("signing out clears every conversation; another account never sees them", async () => {
  setAssistantBinding(caseBinding("A"));
  void ask("Private question");
  f.requests[0].reply.resolve({ answer: "Private answer", cited: [], removed_citations: [], notice: "" });
  await flush();
  setDraft("unsent");
  f.user = null;
  setAssistantBinding(signedOut);
  assert.deepEqual(state().conv.turns, []);
  f.user = "u2";
  setAssistantBinding(caseBinding("A", USER("u2")));
  assert.deepEqual(state().conv.turns, [], "a new user starts clean, even on the same application id");
  assert.equal(state().conv.draft, "");
  f.user = "u1";
  setAssistantBinding(caseBinding("A"));
  assert.deepEqual(state().conv.turns, [], "the first account's conversation was cleared at sign-out");
});

test("signing out mid-question leaves nothing behind, not even the cancelled question", async () => {
  setAssistantBinding(caseBinding("A"));
  void ask("Asked just before signing out");
  f.user = null;
  setAssistantBinding(signedOut);
  assert.equal(f.requests[0].signal.aborted, true);
  f.requests[0].reply.resolve({ answer: "late", cited: [], removed_citations: [], notice: "" });
  await flush();
  f.user = "u1";
  setAssistantBinding(caseBinding("A"));
  assert.deepEqual(state().conv.turns, []);
  assert.equal(state().conv.failed, null);
});

test("nothing is sent while the binding does not match the signed-in account (render race)", async () => {
  setAssistantBinding(caseBinding("A"));
  f.user = "someone-else";
  void ask("Hello");
  assert.equal(f.requests.length, 0);
  f.user = null;
  void ask("Hello");
  assert.equal(f.requests.length, 0);
});

test("history is bounded (8 turns, 1500 characters); the question is too; a failure keeps the draft", async () => {
  setAssistantBinding(caseBinding("A"));
  for (let i = 0; i < 6; i++) {
    void ask(`q${i} ${"x".repeat(2000)}`);
    f.requests.at(-1)!.reply.resolve({ answer: `a${i}`, cited: [], removed_citations: [], notice: "" });
    await flush();
  }
  setDraft("next one");
  void ask("next one");
  const req = f.requests.at(-1)!.req;
  assert.equal(req.history!.length, 8);
  assert.ok(req.history!.every((t) => t.text.length <= 1500));
  assert.ok(f.requests[0].req.question.length <= 1500);
  f.requests.at(-1)!.reply.reject(Object.assign(new Error("down"), { status: 0 }));
  await flush();
  assert.equal(state().conv.draft, "next one", "the failed question is back in the box");
  assert.equal(state().conv.failed, "next one");
  assert.ok(state().conv.error);
});

test("cancel stops the request; its question stays with Retry", async () => {
  setAssistantBinding(caseBinding("A"));
  void ask("Slow one");
  cancelQuestion();
  assert.equal(f.requests[0].signal.aborted, true);
  assert.equal(state().conv.pending, false);
  assert.equal(state().conv.failed, "Slow one");
  f.requests[0].reply.resolve({ answer: "late", cited: [], removed_citations: [], notice: "" });
  await flush();
  assert.ok(!state().conv.turns.some((t) => t.text === "late"));
});

test("typed navigation opens the exact question card and returns to the exact prior card", async () => {
  setAssistantBinding(caseBinding("A"));
  void ask("Open the request date");
  assert.ok(f.requests[0].req.destinations!.includes("question-date"), "real question cards are offered with an application");
  f.requests[0].reply.resolve({ answer: "", cited: [], removed_citations: [], notice: "", navigation: { destination: "question-date" } });
  await flush();
  assert.deepEqual(f.page.went, ["#/questions?focus=field-date"]);
  const nav = state().conv.turns.at(-1)!.nav!;
  assert.equal(nav.state, "opened");
  assert.equal(nav.back!.href, "#/questions?focus=field-owner", "the card the person was on, exactly");
  await goBack(state().conv.turns.at(-1)!.id);
  assert.equal(f.page.went.at(-1), "#/questions?focus=field-owner");
  assert.equal(f.page.focused, "cf-q");
  assert.equal(state().conv.turns.at(-1)!.nav!.backState, "returned");
});

test("a plan whose page never shows (redirect, card missing) is reported as not opened", async () => {
  setAssistantBinding(caseBinding("A"));
  f.page.redirect = () => "#/";
  void ask("Open the officer view");
  f.requests[0].reply.resolve({ answer: "", cited: [], removed_citations: [], notice: "", navigation: { destination: "officer-view" } });
  await flush();
  const nav = state().conv.turns.at(-1)!.nav!;
  assert.equal(nav.state, "failed");
  assert.equal(nav.back, null);
  f.page.redirect = (href) => href.replace("field-permit", "field-owner");
  void ask("Open the permit");
  f.requests[1].reply.resolve({ answer: "", cited: [], removed_citations: [], notice: "", navigation: { destination: "question-permit" } });
  await flush();
  assert.equal(state().conv.turns.at(-1)!.nav!.state, "failed", "the route alone is not the card");
});

test("a plan is not applied after the person moved on, nor when it is not offered here", async () => {
  setAssistantBinding(caseBinding("A"));
  void ask("Open settings");
  bumpViewGeneration(); // they navigated while waiting
  f.requests[0].reply.resolve({ answer: "", cited: [], removed_citations: [], notice: "", navigation: { destination: "settings" } });
  await flush();
  assert.deepEqual(f.page.went, []);
  assert.equal(state().conv.turns.at(-1)!.nav!.state, "moved-on");
  setAssistantBinding(draftBinding());
  void ask("Open the rules I chose");
  assert.ok(!f.requests[1].req.destinations!.includes("references"), "application pages are not offered without one");
  f.requests[1].reply.resolve({ answer: "", cited: [], removed_citations: [], notice: "", navigation: { destination: "references" } });
  await flush();
  assert.deepEqual(f.page.went, []);
  assert.equal(state().conv.turns.at(-1)!.nav!.state, "not-offered");
});

test("leaving an application during native opening cannot leave its cached turn opening forever", async () => {
  setAssistantBinding(caseBinding("A"));
  setAssistantDeps({ page: {
    path: () => f.page.path, hash: () => f.page.hash, card: () => null, shows: () => false,
    go: () => {}, focusId: () => null, focus: () => {},
    settle: async () => { setAssistantBinding(caseBinding("B")); },
  } });
  void ask("Open settings"); f.requests[0].reply.resolve({ answer: "", cited: [], removed_citations: [], notice: "", navigation: { destination: "settings" } }); await flush();
  assert.equal(state().conv.turns.length, 0);
  setAssistantBinding(caseBinding("A")); assert.equal(state().conv.turns.at(-1)?.nav?.state, "failed");
});

test("an already approved native open and its exact Back follow the same application's first save", async () => {
  setAssistantBinding(draftBinding({ draftId: "native-visit" })); setDraft("Keep this unfinished question");
  f.page.redirect = (href) => { setAssistantBinding(caseBinding("A", { draftId: "native-visit" })); return href; };
  void ask("Open settings"); f.requests[0].reply.resolve({ answer: "", cited: [], removed_citations: [], notice: "", navigation: { destination: "settings" } }); await flush();
  const result = state().conv.turns.at(-1)!;
  assert.equal(result.nav?.state, "opened"); assert.equal(state().conv.draft, "Keep this unfinished question");
  await goBack(result.id); assert.equal(f.page.hash, "#/questions?focus=field-owner"); assert.equal(state().conv.turns.at(-1)?.nav?.backState, "returned");
});

test("a late upload lands on its own application's conversation; after sign-out it is dropped", async () => {
  setAssistantBinding(caseBinding("A"));
  void attachFiles([{ name: "plans.pdf", type: "application/pdf" } as File]);
  assert.equal(f.uploads[0].caseId, "A");
  setAssistantBinding(caseBinding("B"));
  f.uploads[0].reply.resolve({ id: "file_a1", name: "plans.pdf" });
  await flush();
  assert.deepEqual(selectedAttachmentIds(), [], "B has none");
  setAssistantBinding(caseBinding("A"));
  assert.deepEqual(selectedAttachmentIds(), ["file_a1"]);
  void attachFiles([{ name: "more.pdf", type: "application/pdf" } as File]);
  f.user = null;
  setAssistantBinding(signedOut);
  f.uploads[1].reply.resolve({ id: "file_a2", name: "more.pdf" });
  await flush();
  f.user = "u1";
  setAssistantBinding(caseBinding("A"));
  assert.deepEqual(selectedAttachmentIds(), []);
});

test("attachments: PDFs only, three at most, never on a read-only or unsaved application", async () => {
  setAssistantBinding(caseBinding("A"));
  await attachFiles([{ name: "photo.png", type: "image/png" } as File]);
  assert.equal(state().conv.attachments[0].status, "failed");
  assert.equal(f.uploads.length, 0);
  for (let i = 0; i < 4; i++) void attachFiles([{ name: `${i}.pdf`, type: "application/pdf" } as File]);
  assert.equal(f.uploads.length, 3);
  setAssistantBinding(caseBinding("R", { canUpload: false }));
  void attachFiles([{ name: "x.pdf", type: "application/pdf" } as File]);
  setAssistantBinding(draftBinding());
  void attachFiles([{ name: "x.pdf", type: "application/pdf" } as File]);
  assert.equal(f.uploads.length, 3);
});

/** Drive the real VoiceClient up to session.started. */
async function startedVoice() {
  await loadVoiceCapability();
  requestVoice();
  assert.equal(state().noticeOpen, true, "the notice comes first");
  assert.equal(f.mic.asked, 0, "no microphone before Start");
  await startVoice();
  await flush();
  const s = f.sockets.at(-1)!;
  s.emit({ type: "session.ready", session_id: "voice_1", context_id: null, revision: null, case_id: null, case_version: null });
  const start = s.sent[0] as { scope: { context_id: string; case_id: string; case_version: number; revision: number } };
  const ids = { session_id: "voice_1", context_id: start.scope.context_id, revision: 0, case_id: start.scope.case_id, case_version: start.scope.case_version };
  s.emit({ type: "session.started", ...ids, expires_at: 2000, max_seconds: 55 });
  return { s, ids, start };
}

test("voice: nothing on boot or capability read; notice, then Start; the exact case version is bound", async () => {
  setAssistantBinding(caseBinding("A"));
  assert.equal(f.capabilityReads.length, 0, "no read before the panel asks");
  const { start } = await startedVoice();
  assert.deepEqual(f.capabilityReads, ["A"]);
  assert.equal(f.mic.asked, 1);
  assert.equal(start.scope.case_id, "A");
  assert.equal(start.scope.case_version, 7);
  assert.equal(state().voice.status, "listening");
});

test("voice: switching applications ends it at once and drops the old session's late events", async () => {
  setAssistantBinding(caseBinding("A"));
  const { s, ids } = await startedVoice();
  setAssistantBinding(caseBinding("B"));
  assert.equal(f.mic.stopped, 1);
  assert.equal(state().voice.status, "idle");
  s.emit({ type: "audio.committed", ...ids, turn_id: "t1" });
  s.emit({ type: "transcript.completed", ...ids, turn_id: "t1", text: "Open settings", navigation: { destination: "settings" } });
  await flush();
  assert.deepEqual(f.page.went, []);
  assert.deepEqual(state().conv.turns, []);
});

test("voice: a granted microphone after closing is released, and no relay opens", async () => {
  setAssistantBinding(caseBinding("A"));
  let grant: (m: { stop(): void }) => void = () => {};
  let stopped = 0;
  setAssistantDeps({
    voice: (events) => new VoiceClient({
      socket: () => { const s = new FakeSocket(); f.sockets.push(s); return s; },
      microphone: () => new Promise((r) => { grant = r; }),
      audio: () => silentAudio(), now: () => 0, setTimer: () => 0, clearTimer: () => {},
      page: () => ({ protocol: "https:", host: "batatis.example" }),
    }, events),
  });
  await loadVoiceCapability();
  f.notice = true;
  requestVoice();
  await flush();
  closeAssistant();
  grant({ stop: () => { stopped += 1; } });
  await flush();
  assert.equal(stopped, 1);
  assert.equal(f.sockets.length, 0);
});

/** A microphone whose frames the test speaks. */
function talkingAudio() {
  let onFrame: ((pcm: Uint8Array) => void) | null = null;
  const audio: VoiceAudio = { async startCapture(fn) { onFrame = fn; }, setMuted() {}, play() {}, clearPlayback() {}, clearCapture() {}, level: () => 0, speaking: () => false, close() { onFrame = null; } };
  const frame = (voiced: boolean) => {
    const pcm = new Uint8Array(4800);
    const v = new DataView(pcm.buffer);
    for (let i = 0; i < 2400; i++) v.setInt16(i * 2, voiced ? (i % 2 ? 6000 : -6000) : 0, true);
    onFrame?.(pcm);
  };
  return { audio, say: () => { for (let i = 0; i < 5; i++) frame(false); for (let i = 0; i < 6; i++) frame(true); for (let i = 0; i < 10; i++) frame(false); } };
}

async function voiceWithSpeech() {
  const mic = talkingAudio();
  let clock = 1_000_000;
  setAssistantDeps({
    voice: (events) => new VoiceClient({
      socket: () => { const s = new FakeSocket(); f.sockets.push(s); return s; },
      microphone: async () => ({ stop() {} }),
      audio: () => mic.audio, now: () => (clock += 100), setTimer: () => 0, clearTimer: () => {},
      page: () => ({ protocol: "https:", host: "batatis.example" }),
    }, events),
  });
  const v = await startedVoice();
  await flush();
  const turn = (id: string, text: string, destination: string | null) => {
    mic.say();
    v.s.emit({ type: "audio.clear", ...v.ids });
    v.s.emit({ type: "audio.committed", ...v.ids, turn_id: id });
    v.s.emit({ type: "transcript.completed", ...v.ids, turn_id: id, text, navigation: destination ? { destination } : null });
  };
  return { ...v, turn };
}

test("voice: a completed spoken request opens a real destination only for the current identity", async () => {
  setAssistantBinding(caseBinding("A"));
  const v = await voiceWithSpeech();
  v.turn("t1", "Open settings", "settings");
  await flush();
  assert.deepEqual(f.page.went, ["#/settings"]);
  const turns = state().conv.turns;
  assert.equal(turns.at(-2)!.via, "voice");
  assert.equal(turns.at(-1)!.nav!.state, "opened");
  assert.equal(turns.at(-1)!.nav!.back!.href, "#/questions?focus=field-owner");
  // Old revision or another case version: nothing happens.
  v.s.emit({ type: "transcript.completed", ...v.ids, revision: 5, turn_id: "t1", text: "Open notifications", navigation: { destination: "notifications" } });
  v.s.emit({ type: "transcript.completed", ...v.ids, case_version: 8, turn_id: "t1", text: "Open notifications", navigation: { destination: "notifications" } });
  await flush();
  assert.deepEqual(f.page.went, ["#/settings"]);
});

test("voice: after the person navigates by hand, a plan for the old screen does not redirect them", async () => {
  setAssistantBinding(caseBinding("A"));
  const v = await voiceWithSpeech();
  bumpViewGeneration(); // a click elsewhere; the relay still holds the old screen
  v.turn("t1", "Open settings", "settings");
  await flush();
  assert.deepEqual(f.page.went, []);
  assert.equal(state().conv.turns.at(-1)!.nav!.state, "moved-on");
});

test("voice: going away and back still acknowledges a new revision before fresh spoken navigation", async () => {
  const timers = new Map<number, () => void>(); let seq = 0;
  setAssistantDeps({ setTimer: (fn) => { timers.set(++seq, fn); return seq; }, clearTimer: (id) => { timers.delete(id); } });
  setAssistantBinding(caseBinding("A")); const v = await voiceWithSpeech();
  setAssistantContext({ screen: "question", focus: { kind: "card", id: "field-date" }, label: "question 2" });
  setAssistantContext({ screen: "question", focus: { kind: "card", id: "field-owner" }, label: "question 1" });
  for (const [id, fn] of [...timers]) { timers.delete(id); fn(); }
  const update = v.s.sent.find((m) => m.type === "context.update"); assert.ok(update, "same text still needs a new revision");
  v.s.emit({ type: "audio.clear", ...v.ids });
  v.s.emit({ type: "context.updated", ...v.ids, revision: 1 });
  v.ids.revision = 1;
  v.turn("current", "Open settings", "settings"); await flush();
  assert.deepEqual(f.page.went, ["#/settings"]);
});

test("voice: a hash-only move invalidates old plans and acknowledges the same scope for new speech", async () => {
  setAssistantBinding(caseBinding("A")); const v = await voiceWithSpeech();
  assistantRouteChanged(); v.turn("old", "Open settings", "settings"); await flush();
  assert.deepEqual(f.page.went, []);
  assert.ok(v.s.sent.some(m => m.type === "context.update"));
  v.s.emit({ type: "audio.clear", ...v.ids }); v.s.emit({ type: "context.updated", ...v.ids, revision: 1 }); v.ids.revision = 1;
  v.turn("fresh", "Open settings", "settings"); await flush(); assert.deepEqual(f.page.went, ["#/settings"]);
});
