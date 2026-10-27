import assert from "node:assert/strict";
import test from "node:test";
import * as libraryContext from "./libraryContext.ts";
import { componentHarness, nodes, text } from "../../scripts/component-harness.mjs";
import type { ApplicationSummary, Message } from "../api/accounts.ts";
import * as packageView from "./reviewer/packageView.ts";
import * as thread from "./comments/thread.ts";
import * as requestedItems from "./requestedItems.ts";
import * as requestDraft from "./reviewer/requestDraft.ts";
import * as workspaceView from "./reviewer/workspaceView.ts";
import { workspaceHarness, workspaceNode, reviewSession, indexFor, mine, menuItem, EngineError, AccountsError } from "./reviewer/tests/workspaceHarness.mjs";
import { emptyCase } from "../intake.ts";

const app = (over: Partial<ApplicationSummary> = {}): ApplicationSummary => ({
  id: "c1", title: "Applicant's file", status: "refused", authority: "edmonton", updated_at: "2026-10-22T12:00:00Z",
  submitted_at: "2026-10-21T12:00:00Z", completeness: null, unread_messages: 1, reviewer: { name: "Morgan" }, ...over,
});
const message = (id: string, body: string, over: Partial<Message> = {}): Message => ({
  id, body, author: { id: "officer", name: "Morgan", role: "reviewer" }, items: [], kind: "message",
  created_at: `2026-10-22T12:0${id}:00Z`, read_by_me: false, ...over,
});
const refusal = message("1", packageView.refusalMessage("The requested drawings were not provided."), { kind: "decision" });
const applicantReply = message("2", "Where can I send my appeal?", { author: { id: "applicant", name: "Mira", role: "applicant" }, read_by_me: true });
const officerReply = message("3", "Please use the contact listed in the written notice.");
const click = (tree, label: string) => {
  const button = nodes(tree, (n) => n.type === "button" && text(n) === label)[0];
  assert.ok(button, `button '${label}' is present`);
  button.props.onClick();
};

/** What the server sends as `decision`: the current return or refusal, apart from any later notice. */
function serverDecision(messages: Message[], status: string) {
  if (status !== "returned" && status !== "refused") return null;
  const m = [...messages].reverse().find((x) => x.kind === "decision" && x.author.role === "reviewer");
  return m ? { outcome: status === "refused" ? "refuse" : "return", by_id: m.author.id, by_name: m.author.name, at: m.created_at, message: m.body, items: m.items } : null;
}

/**
 * The comments page for the open application (`#/comments`) and its thread (ApplicationConversation).
 * `render({ app })` sets the account's summary for that application; `state` changes the open
 * application, account, visibility or the shell's switch problem between renders. The tree holds the
 * page and, when the page shows one, its thread.
 */
async function bannerHarness(initial: Message[]) {
  let messages = initial, loads = 0, refreshes = 0;
  const reads: string[][] = [];
  const state = { app: null as ApplicationSummary | null, engineId: "c1", accountId: "applicant", hidden: false, problem: null as { id: string; text: string } | null };
  const docListeners = new Set<() => void>();
  const pending: { id: string; resolve: (m: Message[]) => void; reject: (e: unknown) => void }[] = [];
  let mode: "auto" | "manual" | "fail" = "auto";
  // One account object per sign-in, as the account store keeps it.
  let user = { id: state.accountId };
  const currentUser = () => (user.id === state.accountId ? user : (user = { id: state.accountId }));
  // Stable, as useThreadRequests' callbacks are.
  const startRequest = () => new AbortController();
  const finishRequest = () => {};
  const conversation = (id: string) => {
    loads++;
    const status = state.app?.status ?? "draft";
    const wrap = (m: Message[]) => ({ messages: m, decision: serverDecision(m, status) });
    if (mode === "manual") return new Promise((resolve, reject) => pending.push({ id, resolve: (m) => resolve(wrap(m)), reject }));
    if (mode === "fail") return Promise.reject(Object.assign(new Error("outage"), { detail: "The officer’s comments did not load." }));
    return Promise.resolve(wrap(messages));
  };
  const page = await componentHarness(new URL("./comments/Comments.tsx", import.meta.url), "Comments", {
    "../../api/packageReview": { packageReview: { sent: async () => ({ requests: [] }) } },
    "../../store": { useCase: () => ({ engineId: state.engineId }) },
    "../account": { useAccount: () => ({ user: { id: state.accountId }, applications: state.app ? [state.app] : [] }) },
    "../routes": { lastStageHash: () => "#/questions" },
    "./opening": { useOpenProblem: () => state.problem },
    "../shell/ApplicationConversation": { ApplicationConversation: "ApplicationConversation" },
    "../ui": { CIcon: "CIcon", Dot: "Dot" },
    "../icons": { Icon24: "Icon24" },
  });
  const reader = await componentHarness(new URL("./shell/ApplicationConversation.tsx", import.meta.url), "ApplicationConversation", {
    "../../api/accounts": { accounts: {
      conversation,
      // Copied into this realm: the component runs in its own VM context.
      markRead: async (_id: string, ids: string[]) => { reads.push([...ids]); },
      postMessage: async () => { throw new Error("one-way: applicants never post"); },
    } },
    "../../api/client": { EngineError: Error },
    "../account": { refreshApplications: async () => { refreshes++; } },
    "../applications": { authorityName: (id: string | null) => (id === "edmonton" ? "Edmonton" : id ?? "") },
    "../assistant/assistant": { openAssistant() {} },
    "../comments/thread": thread,
    "../icons": { Icon24: "Icon24" },
    "../requestedItems": requestedItems,
    "../threadRequests": { useThreadRequests: () => ({ phase: "signed-in", user: currentUser(), startRequest, finishRequest }) },
    "./ReturnedBanner": { messageWhen: (iso: string) => iso, ReturnDecision: "ReturnDecision" },
    "../ui": { CIcon: "CIcon" },
  }, {
    document: {
      get visibilityState() { return state.hidden ? "hidden" : "visible"; },
      addEventListener(_t: string, f: () => void) { docListeners.add(f); },
      removeEventListener(_t: string, f: () => void) { docListeners.delete(f); },
    },
  });
  return {
    state,
    pending,
    render: async (props?: { app?: ApplicationSummary; caseParam?: string | null }) => {
      if (props?.app) { state.app = props.app; state.engineId = props.app.id; }
      const shell = await page.render({ caseParam: props?.caseParam ?? null });
      const body = nodes(shell, (n) => n.type === "ApplicationConversation")[0];
      return { type: "fragment", props: { children: [shell, body ? await reader.render(body.props) : null] } };
    },
    unmount: () => { page.unmount(); reader.unmount(); },
    setMode: (m: typeof mode) => { mode = m; },
    setMessages: (next: Message[]) => { messages = next; },
    setHidden: (hidden: boolean) => { state.hidden = hidden; for (const l of docListeners) l(); },
    /** Receipts sent, each with the displayed message ids it names. */
    get reads() { return reads.length; }, get readIds() { return reads; },
    get loads() { return loads; }, get refreshes() { return refreshes; },
  };
}

/** The current return in full (ReturnDecision), against a case and its shared gaps. */
async function returnDecision(gaps: unknown[]) {
  return componentHarness(new URL("./shell/ReturnedBanner.tsx", import.meta.url), "ReturnDecision", {
    "../../store": { useCase: () => ({ c: emptyCase("homebuilder"), gaps, saveStatus: "saved", gapsSource: "engine", checkStatus: "ready" }) },
    "../account": { initials: () => "MO" },
    "../applications": { authorityName: () => "Edmonton" },
    "../assistant/assistant": { openAssistant() {} },
    "../comments/thread": thread,
    "../icons": { Icon24: "Icon24" },
    "../requestedItems": requestedItems,
  });
}

test("refusal keeps the decision and appeal notice, then both sides' correspondence in order", async () => {
  const h = await bannerHarness([refusal, applicantReply, officerReply]);
  const tree = await h.render({ app: app() });
  const shown = text(tree);
  assert.ok(shown.includes(refusal.body), "the final officer-authored reasons and appeal notice remain prominent");
  assert.ok(shown.includes(applicantReply.body), "the applicant's actual reply is visible");
  assert.ok(shown.includes(officerReply.body), "the later officer follow-up is visible");
  assert.ok(shown.indexOf(refusal.body) < shown.indexOf(applicantReply.body));
  assert.ok(shown.indexOf(applicantReply.body) < shown.indexOf(officerReply.body));
  assert.ok(nodes(tree, (n) => typeof n.props?.className === "string" && n.props.className.includes("cf-refused")).length, "shown as the decision, apart from later notices");
  assert.doesNotMatch(shown, /See what’s missing|Fix \d|returned this|Address next item/, "a refusal is final, never fix and resend");
  assert.ok(shown.includes("Refused · read-only"));
  assert.deepEqual(h.readIds, [[refusal.id, officerReply.id]], "exactly the displayed unread messages are acknowledged, by id");
  assert.equal(h.refreshes, 1, "the list's count is read again from the server, never patched to zero");
  h.unmount();
});

test("an earlier unread message stays in the history and is acknowledged only as shown", async () => {
  const earlier = message("0", "An earlier message before the decision.");
  const h = await bannerHarness([earlier, refusal, applicantReply, officerReply]);
  const tree = await h.render({ app: app() });
  const shown = text(tree);
  assert.ok(shown.includes(earlier.body), "the earlier unread message is displayed");
  assert.ok(shown.indexOf(refusal.body) < shown.indexOf(earlier.body), "after the current decision, in the history");
  assert.ok(shown.indexOf(earlier.body) < shown.indexOf(officerReply.body), "the history reads oldest first");
  assert.deepEqual(h.readIds, [[earlier.id, refusal.id, officerReply.id]]);
  h.unmount();
});

test("a hidden page marks nothing read until it is actually visible", async () => {
  const h = await bannerHarness([refusal, officerReply]);
  h.state.hidden = true;
  await h.render({ app: app() });
  assert.equal(h.reads, 0, "loaded in a background tab: still unread");
  assert.equal(h.refreshes, 0);
  h.setHidden(false);
  await h.render();
  assert.equal(h.reads, 1, "shown: now it is read");
  h.unmount();
});

test("same-file summary updates reload refusal correspondence; there is no reply box (one-way messages)", async () => {
  const h = await bannerHarness([refusal]);
  let tree = await h.render({ app: app() });
  assert.equal(nodes(tree, (n) => n.type === "button" && text(n) === "Reply").length, 0, "the applicant cannot reply");
  assert.equal(nodes(tree, (n) => n.type === "textarea").length, 0);
  h.setMessages([refusal, officerReply]);
  tree = await h.render({ app: app({ updated_at: officerReply.created_at }) });
  assert.equal(h.loads, 2);
  assert.ok(text(tree).includes(officerReply.body));
  h.unmount();
});

test("returned-for-information keeps its missing-item links and offers no reply", async () => {
  const returned = message("1", "Please provide the owner name.", { kind: "decision", items: [{ note: "Owner name", field: "owner_name" }] });
  const h = await bannerHarness([returned]);
  const tree = await h.render({ app: app({ status: "returned" }) });
  const lead = nodes(tree, (n) => n.type === "ReturnDecision")[0];
  assert.ok(lead, "the current return leads, in full");
  assert.equal(lead.props.decision.message, returned.body);
  assert.deepEqual(lead.props.decision.items, returned.items, "its own items, never a later notice's");
  assert.equal(lead.props.messageId, returned.id);
  // The decision itself: the item opens its fix, and fixing (then resubmitting) is the answer.
  const banner = await returnDecision([{ id: "detail-owner", field: "owner", label: "Owner missing", severity: "blocking", href: "#/application?tab=A&focus=field-owner" }]);
  const b = await banner.render(lead.props);
  const row = nodes(b, (n) => n.type === "a" && text(n).includes("Owner name"))[0];
  assert.ok(row, "the item links to its fix");
  assert.match(text(row), /Still to address/);
  assert.equal(nodes(b, (n) => n.type === "a" && text(n) === "Address next item")[0]?.props.href, row.props.href, "the next step opens that fix");
  assert.equal(nodes(tree, (n) => n.type === "button" && text(n) === "Reply").length, 0);
  assert.equal(nodes(tree, (n) => n.type === "form").length + nodes(b, (n) => n.type === "form").length, 0);
  banner.unmount();
  h.unmount();
});

test("a notification for the open file refreshes only its summary and exposes the refusal banner", async () => {
  let remote = app({ status: "in_review", updated_at: "before" }), refreshes = 0, reopened = 0, saved = 0;
  const draft = { title: "My file", description: "My unsaved applicant changes", authority: "edmonton" };
  const account = { phase: "signed-in", user: { role: "applicant", applicant_type: "homebuilder" }, applications: [remote] };
  const route = { path: "/application", params: new URLSearchParams() };
  const h = await componentHarness(new URL("./Shell.tsx", import.meta.url), "Shell", {
    "../api/sync": { engineGeneration: () => 0, engineCaseId: () => "c1", isEngineGeneration: () => true },
    "../store": { useCase: () => ({ c: draft, gaps: [], engineGaps: [], phase: "case", engineId: "c1", saveStatus: "unsaved", openCase: async () => { reopened++; }, saveDraft: async () => { saved++; }, readSync: () => ({ saved: false, reviewed: false, detail: "" }), refreshCurrentCase: async () => null }) },
    "../humanReview": { groupGaps: () => new Map() },
    "./account": { useAccount: () => account, bootAccount() {}, accountSession: () => "applicant-session", refreshApplications: async () => { refreshes++; account.applications = [remote]; } },
    "./notifications/notifications": { useNotifications: () => ({ phase: "idle", items: [] }) },
    "./applications": { authorityName: () => "Edmonton", readOnly: () => false },
    "./assistant/assistant": { useAssistant: () => ({ open: false }), setAssistantCase() {}, setAssistantContext() {} },
    "./assistant/AskButton": { AskButton: () => null, AskHost: { Provider: "fragment" } },
    "./codeScope": { useCodeScope: () => "application", ApplicationSwitchContext: { Provider: "fragment" } },
    "./libraryContext": libraryContext,
    "./session": { useSession: () => ({ seen: [] }), getSession: () => ({ draft: "" }) },
    "./deck": { buildDeck: () => [], deckProgress: () => ({ done: 0, total: 0 }) },
    "./useDeckExtras": { useDeckExtras: () => ({ options: {} }) },
    "./routes": { rememberStage() {}, STAGES: [{ screen: "application" }] },
    "./shell/AppLayout": { AppLayout: "AppLayout" },
    "./shell/ReturnedBanner": { ReturnedBanner: "ReturnedBanner" },
    "./comments/opening": { setOpenProblem() {} },
    "../router": { useRoute: () => route },
  }, {
    sessionStorage: { getItem: () => null, setItem() {} },
    location: { hash: "#/application", replace() { route.params = new URLSearchParams(); } },
    document: { addEventListener() {}, removeEventListener() {} },
    window: { addEventListener() {}, removeEventListener() {} },
  });
  await h.render({ active: "application", children: null });
  refreshes = 0;
  remote = app();
  route.params = new URLSearchParams("case=c1");
  let tree = await h.render();
  assert.equal(refreshes, 1, "the same-file notification refreshes account summaries");
  // The account store normally schedules this rerender through useSyncExternalStore.
  tree = await h.render();
  let banner = nodes(tree, (n) => n.type === "AppLayout")[0].props.banner;
  assert.equal(banner.type, "ReturnedBanner");
  assert.equal(banner.props.app.status, "refused");
  const b = await bannerHarness([refusal]);
  assert.ok(text(await b.render(banner.props)).includes(refusal.body), "its comments page shows the refusal");
  remote = app({ updated_at: officerReply.created_at });
  route.params = new URLSearchParams("case=c1");
  await h.render();
  tree = await h.render();
  banner = nodes(tree, (n) => n.type === "AppLayout")[0].props.banner;
  b.setMessages([refusal, applicantReply, officerReply]);
  assert.ok(text(await b.render(banner.props)).includes(officerReply.body), "a later same-file notification also refreshes the comments");
  remote = app({ status: "returned", updated_at: "returned" });
  route.params = new URLSearchParams("case=c1");
  await h.render();
  assert.equal(reopened, 0, "no full case reload discards applicant changes");
  assert.equal(saved, 0, "the notification does not force a save");
  assert.equal(draft.description, "My unsaved applicant changes");
  b.unmount(); h.unmount();
});

test("terminal officer files keep the request in the workspace as a read-only record", async () => {
  for (const status of ["refused", "accepted", "returned"]) {
    const h = await workspaceHarness({ status }, { latest: reviewSession(1) });
    const tree = await h.render({ caseId: "c1" });
    const workspace = workspaceNode(tree);
    assert.ok(workspace, "the saved request remains alongside the sheet");
    assert.equal(workspace.props.editable, false);
    assert.equal(workspace.props.showDecision, false, "a decided or returned file has no decision bar");
    assert.equal(nodes(tree, n => n.type === "InfoRequest" || n.type === "Drawer").length, 0);
    h.unmount();
  }
});

test("a standalone package retains copy-out and never offers a case decision", async () => {
  let copied = "";
  const h = await componentHarness(new URL("./reviewer/InfoRequest.tsx", import.meta.url), "InfoRequest", {
    "./requestDraft": requestDraft, "./workspaceView": workspaceView,
  }, { navigator: { clipboard: { writeText: async (value: string) => { copied = value; } } } });
  const tree = await h.render({ target: { kind: "package", id: "pkg_1" }, session: reviewSession(1), latest: true, canEdit: true, onChange() {} });
  const copy = nodes(tree, n => n.type === "button" && text(n) === "Copy the text")[0];
  assert.ok(copy);
  await copy.props.onClick();
  await h.render();
  assert.equal(copied, "Exact server preview");
  assert.doesNotMatch(text(tree), /Send and return|Accept|Refuse|Take over/);
  h.unmount();
});

test("a failed comments load offers a retry that shows the notice once it loads", async () => {
  const h = await bannerHarness([refusal]);
  h.setMode("fail");
  let tree = await h.render({ app: app() });
  assert.equal(h.loads, 1);
  assert.match(text(tree), /did not load/);
  assert.doesNotMatch(text(tree), /No comments yet/, "an unknown thread is not described as empty");
  assert.equal(h.reads, 0, "nothing is marked read while nothing is shown");
  h.setMode("auto");
  click(tree, "Try again");
  tree = await h.render();
  assert.equal(h.loads, 2);
  assert.ok(text(tree).includes(refusal.body), "the final refusal reasons and appeal notice appear after the retry");
  assert.doesNotMatch(text(tree), /did not load/);
  assert.equal(nodes(tree, (n) => n.type === "textarea").length, 0, "still no reply box");
  h.unmount();
});

test("a late answer for one application or account never shows (or clears) another's comments", async () => {
  const h = await bannerHarness([]);
  h.setMode("manual");
  await h.render({ app: app() });
  // The person opens another application before c1's thread arrives.
  let tree = await h.render({ app: app({ id: "c2" }) });
  assert.deepEqual(h.pending.map((p) => p.id), ["c1", "c2"]);
  h.pending[0].resolve([refusal]);
  tree = await h.render();
  assert.ok(!text(tree).includes(refusal.body), "c1's late thread is ignored");
  assert.equal(h.reads, 0, "and nothing is marked read for it");
  h.pending[1].resolve([officerReply]);
  tree = await h.render();
  assert.ok(text(tree).includes(officerReply.body));
  assert.equal(h.reads, 1);
  // Another account on the same application id: a fresh load, the old one's answer dropped.
  h.state.accountId = "someone-else";
  tree = await h.render();
  assert.equal(h.pending.length, 3);
  assert.ok(!text(tree).includes(officerReply.body), "the previous account's thread is not shown");
  h.unmount();
});

test("a comments link for another application waits for the guarded switch, and says why it failed", async () => {
  const h = await bannerHarness([refusal]);
  let tree = await h.render({ app: app(), caseParam: "c9" });
  assert.match(text(tree), /Opening/);
  assert.equal(h.loads, 0, "the open application's thread is not shown for another's link");
  assert.equal(h.reads, 0);
  h.state.problem = { id: "c9", text: "Couldn’t save your changes, so this application stays open." };
  tree = await h.render({ caseParam: "c9" });
  assert.match(text(tree), /Couldn’t save your changes/);
  assert.equal(nodes(tree, (n) => n.type === "a" && n.props.href === "#/questions").length, 1, "Back returns to the open application");
  assert.equal(h.reads, 0);
  h.unmount();
});

test("the one-line notice links to comments, counts what is new, and reads nothing", async () => {
  const h = await componentHarness(new URL("./shell/ReturnedBanner.tsx", import.meta.url), "ReturnedBanner", {
    "../icons": { Icon24: "Icon24" }, "../comments/thread": thread,
  });
  const tree = await h.render({ app: app({ status: "returned", unread_messages: 2 }) });
  assert.equal(tree.type.name, "NoticeLine");
  const line = await componentHarness(new URL("./shell/ReturnedBanner.tsx", import.meta.url), "NoticeLine", { "../icons": { Icon24: "Icon24" }, "../comments/thread": thread });
  const a = await line.render({ app: app({ status: "returned", unread_messages: 2 }) });
  assert.equal(a.type, "a");
  assert.equal(a.props.href, "#/comments");
  assert.equal(a.props["aria-label"], "Returned for changes by Morgan, 2 new comments. Open comments");
  assert.match(text(a), /^Returned for changes2Comments$/);
  const refused = await line.render({ app: app({ unread_messages: 0 }) });
  assert.equal(refused.props["aria-label"], "Refused · read-only by Morgan. Open comments");
  assert.equal(await line.render({ app: app({ status: "accepted" }) }), null, "no line for accepted or draft files");
  h.unmount(); line.unmount();
});

test("a refusal pins the saved case version and includes the appeal notice without a correction list", async () => {
  const h = await workspaceHarness({ status: "in_review", claim: mine, version: 7 }, { latest: reviewSession(1, 7) });
  const tree = await h.render({ caseId: "c1" });
  const dialog = nodes(tree, n => typeof n.props?.onSend === "function" && typeof n.props?.onRefresh === "function")[0];
  await dialog.props.onSend("The requested fire separation drawings were not provided.");
  assert.deepEqual(h.calls.decisions, [{ outcome: "refuse", message: packageView.refusalMessage("The requested fire separation drawings were not provided."), expected_version: 7 }]);
  h.unmount();
});

test("acceptance pins both the case and the package-review version that was on screen", async () => {
  const h = await workspaceHarness({ status: "in_review", claim: mine, version: 7 }, { latest: reviewSession(3, 7) });
  let tree = await h.render({ caseId: "c1" });
  assert.equal(workspaceNode(tree).props.editable, true);
  workspaceNode(tree).props.onAccept();
  tree = await h.render();
  click(tree, "Accept");
  await h.render();
  assert.deepEqual(h.calls.decisions, [{ outcome: "accept", expected_version: 7, review_version: 3 }]);
  h.unmount();
});

test("return sends the exact saved server text and expected version in one call", async () => {
  const saved = reviewSession(3, 7);
  saved.information_request.text = "The server's exact\n\n1. Request — with punctuation.";
  const h = await workspaceHarness({ status: "in_review", claim: mine, version: 7 }, { latest: saved });
  let tree = await h.render({ caseId: "c1" });
  workspaceNode(tree).props.onReturn(); tree = await h.render();
  assert.match(text(tree), /Return to Mira\?/, "the confirmation names who receives it");
  click(tree, "Return"); await h.render();
  assert.deepEqual(h.calls.returns, [{ caseId: "c1", version: 3, body: { expected_version: 7, text: saved.information_request.text } }]);
  assert.deepEqual(h.calls.decisions, [], "no separate send or return decision can leave the applicant locked out");
  h.unmount();
});

test("after a return the same version is read again, so the rail shows the request as sent", async () => {
  const draft = reviewSession(3, 7);
  const sent = { ...draft, information_request: { ...draft.information_request, sent_at: "2026-10-26T14:41:00Z", message_id: "m1" } };
  let returned = false;
  const h = await workspaceHarness({ status: "in_review", claim: mine, version: 7 }, {
    index: async () => indexFor(returned ? sent : draft),
    returnWithRequest: async () => {
      returned = true; h.current.status = "returned";
      h.current.decision = { outcome: "return", by_id: mine.reviewer_id, by_name: mine.reviewer_name, at: "2026-10-26T14:41:00Z", message: "", items: [] };
      return { ...h.current };
    },
  });
  let tree = await h.render({ caseId: "c1" });
  workspaceNode(tree).props.onReturn(); tree = await h.render();
  click(tree, "Return"); tree = await h.render(); tree = await h.render(); tree = await h.render();
  assert.equal(workspaceNode(tree).props.session.information_request.sent_at, sent.information_request.sent_at, "never the stale draft");
  assert.equal(workspaceNode(tree).props.status, "returned");
  h.unmount();
});

test("a return conflict shows the server reason and refreshes without sending a second decision", async () => {
  let reads = 0;
  const h = await workspaceHarness({ status: "in_review", claim: mine }, { latest: reviewSession(1),
    getCase: async () => { reads++; return { ...h.current }; },
    returnWithRequest: async () => { throw new AccountsError(409, "The saved request changed. Review it again."); },
  });
  let tree = await h.render({ caseId: "c1" }); const before = reads;
  workspaceNode(tree).props.onReturn(); tree = await h.render(); click(tree, "Return"); tree = await h.render();
  assert.match(text(tree), /The saved request changed\. Review it again\./);
  assert.ok(reads > before, "the displayed application is read again after the 409");
  assert.equal(h.calls.returns.length, 1); assert.equal(h.calls.decisions.length, 0);
  assert.equal(nodes(tree, n => n.type === "button" && text(n) === "Return")[0].props.disabled, true);
  h.unmount();
});

test("a successful run stays visible when the index refresh fails; editing and decisions wait", async () => {
  let failing = false;
  const h = await workspaceHarness({ status: "in_review", claim: mine }, {
    index: async () => { if (failing) throw new EngineError(503); return indexFor(reviewSession(1)); },
    run: async () => reviewSession(2),
  });
  let tree = await h.render({ caseId: "c1" });
  failing = true; menuItem(tree, "Review again").onClick(); tree = await h.render();
  assert.equal(workspaceNode(tree).props.session.version, 2);
  assert.equal(workspaceNode(tree).props.editable, false);
  assert.match(text(tree), /The review didn’t load/);
  h.unmount();
});

test("a failed first index load offers a retry and never starts a review against an unknown index", async () => {
  let failing = true;
  const h = await workspaceHarness({ status: "in_review", claim: mine }, {
    index: async () => { if (failing) throw new EngineError(503); return indexFor(reviewSession(1)); },
  });
  let tree = await h.render({ caseId: "c1" });
  assert.equal(workspaceNode(tree), undefined); assert.equal(h.calls.run, 0);
  assert.match(text(tree), /The review didn’t load/);
  failing = false; click(tree, "Try again"); tree = await h.render();
  assert.equal(workspaceNode(tree).props.session.version, 1);
  assert.equal(workspaceNode(tree).props.editable, true);
  h.unmount();
});

test("unsaved request changes hold decisions, release and switching to another version", async () => {
  const h = await workspaceHarness({ status: "in_review", claim: mine }, { latest: reviewSession(2) });
  let tree = await h.render({ caseId: "c1" });
  workspaceNode(tree).props.onDraft({ pending: true, trouble: "", discard() {} }); tree = await h.render();
  assert.equal(menuItem(tree, "Stop reviewing").disabled, true);
  workspaceNode(tree).props.onAccept(); tree = await h.render();
  const open = nodes(tree, n => n.props?.labelledBy === "rw-decision-title")[0];
  assert.equal(open.props.open, false);
  assert.equal(h.calls.decisions.length, 0);
  h.unmount();
});

test("a draft the server refused shows in the status line with a way out", async () => {
  const h = await workspaceHarness({ status: "in_review", claim: mine }, { latest: reviewSession(2) });
  let tree = await h.render({ caseId: "c1" });
  let discarded = 0;
  workspaceNode(tree).props.onDraft({ pending: true, trouble: "The request changed. Review it again.", discard() { discarded++; } }); tree = await h.render();
  const alert = nodes(tree, n => n.props?.role === "alert").find(n => text(n).includes("The request changed"));
  assert.ok(alert, "the trouble is on screen, not only on the Request tab");
  nodes(alert, n => n.type === "button" && text(n) === "Discard my changes")[0].props.onClick();
  assert.equal(discarded, 1);
  h.unmount();
});

test("a return leads with its decision; the note sent with it waits in the history, unread until shown", async () => {
  // The engine records a return as a decision (with the items to fix) and, at the same moment, a
  // plain message. Receipts name what is on screen, so the folded note stays counted until opened.
  const at = "2026-10-22T19:40:56Z";
  const decision = message("1", "Returned for administrative information.\n\nPlease clarify the owner.", { kind: "decision", created_at: at, items: [{ note: "Owner name", field: "owner_name" }] });
  const note = message("2", "Please update the revision date, then send it again.", { created_at: at });
  const status = message("0", "Submitted for administrative review.", { kind: "status", created_at: "2026-10-22T19:00:00Z", author: applicantReply.author, read_by_me: true });
  const h = await bannerHarness([status, decision, note]);
  let tree = await h.render({ app: app({ status: "returned", unread_messages: 2 }) });
  assert.equal(nodes(tree, (n) => n.type === "ReturnDecision")[0]?.props.decision.message, decision.body, "the return decision is displayed in full");
  assert.match(text(tree), /Messages and history · 1 unread/, "the note sent with it is one click away, and counted");
  assert.deepEqual(h.readIds, [[decision.id]], "only the displayed decision is acknowledged");
  nodes(tree, (n) => n.type === "details")[0].props.onToggle({ currentTarget: { open: true } });
  tree = await h.render();
  assert.deepEqual(h.readIds, [[decision.id], [note.id]], "opened, the note is acknowledged by id");
  assert.doesNotMatch(text(tree), /unread/);
  assert.equal(h.refreshes, 2, "the list's count is read again from the server each time, never zeroed");
  assert.equal(nodes(tree, (n) => n.type === "button" && text(n) === "Reply").length, 0, "still one-way");
  h.unmount();
});

test("an earlier round's unread note stays counted in the history until it is shown", async () => {
  // An applicant can resend without opening the last return; those messages stay counted until read.
  const old = message("0", "An earlier round's note.", { created_at: "2026-10-20T10:00:00Z" });
  const seen = message("5", "An earlier note already read.", { created_at: "2026-10-20T09:00:00Z", read_by_me: true });
  const decision = message("1", "Returned again.", { kind: "decision", created_at: "2026-10-22T10:00:00Z", items: [{ note: "Owner name", field: "owner_name" }] });
  const h = await bannerHarness([seen, old, decision]);
  let tree = await h.render({ app: app({ status: "returned", unread_messages: 2 }) });
  assert.equal(nodes(tree, (n) => n.type === "ReturnDecision")[0]?.props.decision.message, "Returned again.", "the new return leads");
  assert.match(text(tree), /Messages and history · 1 unread/);
  assert.deepEqual(h.readIds, [[decision.id]]);
  nodes(tree, (n) => n.type === "details")[0].props.onToggle({ currentTarget: { open: true } });
  tree = await h.render();
  const shown = text(tree);
  assert.ok(shown.indexOf(seen.body) < shown.indexOf(old.body), "read history stays on the page, oldest first");
  assert.deepEqual(h.readIds, [[decision.id], [old.id]]);
  h.unmount();
});

test("the sidebar offers Delete on every owned application; the server's DELETE policy decides", async () => {
  const statuses = ["draft", "submitted", "in_review", "returned", "accepted", "refused", "withdrawn"] as const;
  const owned = statuses.map((status, i) => app({ id: `c${i}`, status, archived: false, pinned: false }));
  const account = { phase: "signed-in", user: { role: "applicant", applicant_type: "homebuilder" }, applications: owned };
  const h = await componentHarness(new URL("./Shell.tsx", import.meta.url), "Shell", {
    "../api/sync": { engineGeneration: () => 0, engineCaseId: () => null, isEngineGeneration: () => true },
    "../store": { useCase: () => ({ c: { title: "", description: "", authority: "" }, gaps: [], engineGaps: [], phase: "who", engineId: null, readSync: () => ({ saved: true, reviewed: false, detail: "" }), refreshCurrentCase: async () => null }) },
    "../humanReview": { groupGaps: () => new Map() },
    "./account": { useAccount: () => account, bootAccount() {}, accountSession: () => "applicant-session", refreshApplications: async () => {} },
    "./notifications/notifications": { useNotifications: () => ({ phase: "idle", items: [] }) },
    "./applications": await import("./applications.ts"),
    "./assistant/assistant": { useAssistant: () => ({ open: false }), setAssistantCase() {}, setAssistantContext() {} },
    "./assistant/AskButton": { AskButton: () => null, AskHost: { Provider: "fragment" } },
    "./codeScope": { useCodeScope: () => "application", ApplicationSwitchContext: { Provider: "fragment" } },
    "./libraryContext": libraryContext,
    "./session": { useSession: () => ({ seen: [] }), getSession: () => ({ draft: "" }) },
    "./deck": { buildDeck: () => [], deckProgress: () => ({ done: 0, total: 0 }) },
    "./useDeckExtras": { useDeckExtras: () => ({ options: {} }) },
    "./routes": { rememberStage() {}, STAGES: [{ screen: "start" }] },
    "./shell/AppLayout": { AppLayout: "AppLayout" },
    "../router": { useRoute: () => ({ path: "/", params: new URLSearchParams() }) },
  }, {
    sessionStorage: { getItem: () => null, setItem() {}, removeItem() {} },
    location: { hash: "#/", replace() {} },
    document: { addEventListener() {}, removeEventListener() {} },
    window: { addEventListener() {}, removeEventListener() {} },
  });
  const tree = await h.render({ active: "start", children: null });
  const list = nodes(tree, (n) => n.type === "AppLayout")[0].props.list;
  for (const a of owned) {
    const del = list.props.actionsFor(a).find((x) => x.id === "delete");
    assert.ok(del, `${a.status}: Delete is offered`);
    assert.equal(Boolean(del.disabled), false, `${a.status}: no client-side status gate`);
    assert.equal(del.hint, undefined, `${a.status}: no invented reason`);
  }
  h.unmount();
});
