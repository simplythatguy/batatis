import assert from "node:assert/strict";
import test from "node:test";
import * as libraryContext from "./libraryContext.ts";
import { componentHarness, nodes, text } from "../../scripts/component-harness.mjs";
import type { ApplicationSummary, Message } from "../api/accounts.ts";
import * as packageView from "./reviewer/packageView.ts";
import * as queue from "./reviewer/queue.ts";
import * as thread from "./comments/thread.ts";

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

/**
 * The comments page for the open application (`#/comments`). `render({ app })` sets the account's
 * summary for that application; `state` changes the open application, account, visibility or
 * the shell's switch problem between renders.
 */
async function bannerHarness(initial: Message[]) {
  let messages = initial, reads = 0, loads = 0;
  const patches = [];
  const state = { app: null as ApplicationSummary | null, engineId: "c1", accountId: "applicant", hidden: false, problem: null as { id: string; text: string } | null };
  const docListeners = new Set<() => void>();
  const pending: { id: string; resolve: (m: Message[]) => void; reject: (e: unknown) => void }[] = [];
  let mode: "auto" | "manual" | "fail" = "auto";
  const harness = await componentHarness(new URL("./comments/Comments.tsx", import.meta.url), "Comments", {
    "../../api/accounts": { accounts: {
      messages: (id: string) => {
        loads++;
        if (mode === "manual") return new Promise<Message[]>((resolve, reject) => pending.push({ id, resolve, reject }));
        if (mode === "fail") return Promise.reject(Object.assign(new Error("outage"), { detail: "The officer’s comments did not load." }));
        return Promise.resolve(messages);
      },
      markRead: async () => { reads++; },
      postMessage: async () => { throw new Error("one-way: applicants never post"); },
    } },
    "../../api/client": { EngineError: Error },
    "../../api/packageReview": { packageReview: { sent: async () => ({ requests: [] }) } },
    "../../store": { useCase: () => ({ c: {}, gaps: [], engineId: state.engineId }), hrefFor: () => "#/review" },
    "../../model": { factLabel: (f: string) => f },
    "../account": { initials: () => "MO", patchApplication: (...p) => patches.push(p), useAccount: () => ({ user: { id: state.accountId }, applications: state.app ? [state.app] : [] }) },
    "../routes": { calmHref: (href) => href, lastStageHash: () => "#/questions" },
    "./opening": { useOpenProblem: () => state.problem },
    "./thread": thread,
    "../ui": { CIcon: "CIcon", Dot: "Dot" },
    "../icons": { Icon24: "Icon24" },
  }, {
    document: {
      get visibilityState() { return state.hidden ? "hidden" : "visible"; },
      addEventListener(_t: string, f: () => void) { docListeners.add(f); },
      removeEventListener(_t: string, f: () => void) { docListeners.delete(f); },
    },
  });
  return {
    ...harness,
    state,
    pending,
    render: (props?: { app?: ApplicationSummary; caseParam?: string | null }) => {
      if (props?.app) { state.app = props.app; state.engineId = props.app.id; }
      return harness.render({ caseParam: props?.caseParam ?? null });
    },
    setMode: (m: typeof mode) => { mode = m; },
    setMessages: (next: Message[]) => { messages = next; },
    setHidden: (hidden: boolean) => { state.hidden = hidden; for (const l of docListeners) l(); },
    get reads() { return reads; }, get loads() { return loads; }, patches,
  };
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
  assert.doesNotMatch(shown, /See what’s missing|Fix \d|returned this/, "a refusal is final, never fix and resend");
  assert.ok(shown.includes("Refused · read-only"));
  assert.equal(h.reads, 1, "the fully displayed unread messages can be marked read");
  h.unmount();
});

test("an earlier unread message is on the page (Earlier), so clearing the thread never hides one", async () => {
  const earlier = message("0", "An earlier message before the decision.");
  const h = await bannerHarness([earlier, refusal, applicantReply, officerReply]);
  const tree = await h.render({ app: app() });
  const shown = text(tree);
  assert.ok(shown.includes(earlier.body), "the earlier unread message is displayed");
  assert.ok(shown.indexOf(officerReply.body) < shown.indexOf(earlier.body), "after the newest decision and what followed it");
  assert.equal(h.reads, 1);
  h.unmount();
});

test("a hidden page marks nothing read until it is actually visible", async () => {
  const h = await bannerHarness([refusal, officerReply]);
  h.state.hidden = true;
  await h.render({ app: app() });
  assert.equal(h.reads, 0, "loaded in a background tab: still unread");
  assert.equal(h.patches.length, 0);
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
  assert.ok(text(tree).includes(returned.body));
  const fix = nodes(tree, (n) => n.type === "a" && text(n).includes("Fix 1 item"))[0];
  assert.ok(fix, "fixing the application is the answer");
  assert.equal(fix.props.href, "#/review", "it opens the item's fix (the stubbed store href)");
  assert.equal(nodes(tree, (n) => n.type === "button" && text(n) === "Reply").length, 0);
  assert.equal(nodes(tree, (n) => n.type === "form").length, 0);
  h.unmount();
});

test("a notification for the open file refreshes only its summary and exposes the refusal banner", async () => {
  let remote = app({ status: "in_review", updated_at: "before" }), refreshes = 0, reopened = 0, saved = 0;
  const draft = { title: "My file", description: "My unsaved applicant changes", authority: "edmonton" };
  const account = { phase: "signed-in", user: { role: "applicant", applicant_type: "homebuilder" }, applications: [remote] };
  const route = { path: "/application", params: new URLSearchParams() };
  const h = await componentHarness(new URL("./Shell.tsx", import.meta.url), "Shell", {
    "../api/sync": { engineGeneration: () => 0 },
    "../store": { useCase: () => ({ c: draft, gaps: [], engineGaps: [], phase: "case", engineId: "c1", saveStatus: "unsaved", openCase: async () => { reopened++; }, saveDraft: async () => { saved++; } }) },
    "../humanReview": { groupGaps: () => new Map() },
    "./account": { useAccount: () => account, bootAccount() {}, refreshApplications: async () => { refreshes++; account.applications = [remote]; } },
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

const request = {
  package_id: "c1", version: 1, findings: [],
  information_request: { intro: "Please provide the requested drawing.", edited: false, sent_at: null, items: [] },
};

test("terminal officer files pass a historical read-only reason to the information request", async () => {
  for (const status of ["refused", "accepted"]) {
    const h = await componentHarness(new URL("./reviewer/ReviewDetail.tsx", import.meta.url), "ReviewDetail", {
      "../../api/client": { engine: { getCase: async () => ({ id: "c1", status, version: 1 }), gaps: async () => [] } },
      "../../api/accounts": { accounts: { messages: async () => [] } },
      "../../api/packageReview": { packageReview: { index: async () => ({ latest: request, sessions: [request], close_out: null }) } },
      "../account": { useAccount: () => ({ user: { id: "officer" } }) },
      "./reviewData": { useQueue: () => ({ rows: [{ id: "c1", status, applicant: { name: "Mira" } }] }), setBlocking() {} },
      "./queue": queue,
      "./packageView": packageView,
      "./InfoRequest": { InfoRequest: "InfoRequest" },
    });
    let tree = await h.render({ caseId: "c1" });
    click(tree, "Information request");
    tree = await h.render();
    const info = nodes(tree, (n) => n.type === "InfoRequest")[0];
    assert.ok(info);
    const ir = await componentHarness(new URL("./reviewer/InfoRequest.tsx", import.meta.url), "InfoRequest", { "./packageView": packageView });
    const requestTree = await ir.render(info.props);
    assert.match(text(requestTree), /historical.*read-only/i);
    assert.ok(text(requestTree).includes(status));
    assert.doesNotMatch(text(requestTree), /Pick up this application \(or take over\)/);
    assert.equal(nodes(requestTree, (n) => n.type === "fieldset")[0].props.disabled, true);
    assert.equal(nodes(requestTree, (n) => n.type === "button" && text(n).startsWith("Send to"))[0].props.disabled, true);
    ir.unmount(); h.unmount();
  }
});

test("an unclaimed editable file keeps takeover guidance; standalone packages keep copy", async () => {
  const h = await componentHarness(new URL("./reviewer/InfoRequest.tsx", import.meta.url), "InfoRequest", { "./packageView": packageView });
  const props = { target: { kind: "case", id: "c1" }, session: request, latest: true, canEdit: false, applicant: "Mira", onChange() {} };
  assert.match(text(await h.render(props)), /Pick up this application \(or take over\)/);
  const tree = await h.render({ ...props, target: { kind: "package", id: "p1" }, canEdit: true });
  assert.ok(nodes(tree, (n) => n.type === "button" && text(n) === "Copy the text").length);
  assert.doesNotMatch(text(tree), /historical|Pick up this application/);
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

const reviewSession = (version: number) => ({ package_id: "c1", version, case_version: 1, findings: [], information_request: { items: [] } });

async function reviewHarness(opts: { index: () => Promise<unknown> }) {
  const claim = { reviewer_id: "officer", reviewer_name: "Morgan", claimed_at: "2026-10-22T12:00:00Z" };
  const current = { id: "c1", title: "Synthetic review refresh", status: "in_review", version: 1, claim };
  class EngineError extends Error { status: number; constructor(status: number) { super("Synthetic failure"); this.status = status; } }
  let runs = 0;
  const h = await componentHarness(new URL("./reviewer/ReviewDetail.tsx", import.meta.url), "ReviewDetail", {
    "../../api/client": { EngineError, engine: { getCase: async () => current, gaps: async () => [] } },
    "../../api/accounts": { AccountsError: EngineError, accounts: { messages: async () => [] } },
    "../../api/packageReview": { packageReview: { index: opts.index, run: async () => { runs++; return reviewSession(2); } } },
    "../account": { useAccount: () => ({ user: { id: "officer", name: "Morgan" } }) },
    "./reviewData": { useQueue: () => ({ rows: [{ ...current, applicant: { name: "Mira", applicant_type: "homebuilder" } }] }), setBlocking() {} },
    "./queue": queue,
    "./packageView": packageView,
    "./PackageReview": { PackageReview: "PackageReview", StepTitle: "StepTitle" },
    "../shell/MoreMenu": { MoreMenu: "MoreMenu" },
    "./InfoRequest": { InfoRequest: "InfoRequest" },
  }, { EngineError });
  return { ...h, EngineError, get runs() { return runs; } };
}

const runAgain = (tree) => {
  const head = nodes(tree, (n) => n.props?.right)[0];
  const menu = nodes(head.props.right, (n) => n.type === "MoreMenu")[0];
  const item = menu.props.items.find((i) => i.label === "Run the review again");
  assert.ok(item, "the claimed case can run again");
  item.onClick();
};
/** Accept is in the failure panel, or in the review's last step (the PackageReview `final` prop). */
const accept = (tree) => {
  const isAccept = (n) => n.type === "button" && text(n).startsWith("Accept");
  const final = nodes(tree, (n) => n.type === "PackageReview")[0]?.props.final.content;
  return nodes(tree, isAccept)[0] ?? nodes(final, isAccept)[0];
};

test("a review that ran stays on screen when the background index refresh fails; Accept stays blocked", async () => {
  let failRefresh = false, Err: new (s: number) => Error;
  const h = await reviewHarness({ index: async () => { if (failRefresh) throw new Err(503); return { latest: reviewSession(1), sessions: [reviewSession(1)], close_out: null }; } });
  Err = h.EngineError;
  let tree = await h.render({ caseId: "c1" });
  assert.equal(nodes(tree, (n) => n.type === "PackageReview")[0]?.props.session.version, 1);
  failRefresh = true;
  runAgain(tree);
  tree = await h.render();
  const after = nodes(tree, (n) => n.type === "PackageReview");
  assert.equal(after.length, 1, "the successful review remains visible");
  assert.equal(after[0].props.session.version, 2, "the version that just ran stays selected");
  assert.equal(accept(tree)?.props.disabled, true, "an unknown index still blocks acceptance");
  assert.ok(nodes(tree, (n) => n.type === "button" && text(n) === "Try again").length, "the refresh failure has a retry");
  // Retrying succeeds with an index that lags behind: the selected version is not replaced.
  failRefresh = false;
  click(tree, "Try again");
  tree = await h.render();
  assert.equal(nodes(tree, (n) => n.type === "PackageReview")[0].props.session.version, 2, "retry keeps the selected newer version");
  assert.equal(nodes(tree, (n) => n.type === "button" && text(n) === "Try again").length, 0);
  h.unmount();
});

test("a first review load that fails still shows the error and retry, with Accept blocked", async () => {
  let fail = true, Err: new (s: number) => Error;
  const h = await reviewHarness({ index: async () => { if (fail) throw new Err(503); return { latest: reviewSession(1), sessions: [reviewSession(1)], close_out: null }; } });
  Err = h.EngineError;
  let tree = await h.render({ caseId: "c1" });
  assert.match(text(tree), /The review didn’t load/);
  assert.equal(nodes(tree, (n) => n.type === "PackageReview").length, 0);
  assert.equal(accept(tree)?.props.disabled, true);
  assert.equal(h.runs, 0, "an unknown index does not trigger a new review run");
  fail = false;
  click(tree, "Try again");
  tree = await h.render();
  assert.equal(nodes(tree, (n) => n.type === "PackageReview")[0]?.props.session.version, 1);
  h.unmount();
});

test("asking for more after a review ran but the index refresh failed: the newest run, no 'earlier', editing waits for the retry", async () => {
  let failRefresh = false, newest = 1, Err: new (s: number) => Error;
  const index = () => ({ latest: reviewSession(newest), sessions: [reviewSession(1), ...(newest > 1 ? [reviewSession(newest)] : [])], close_out: null });
  const h = await reviewHarness({ index: async () => { if (failRefresh) throw new Err(503); return index(); } });
  Err = h.EngineError;
  let tree = await h.render({ caseId: "c1" });
  failRefresh = true;
  runAgain(tree);
  tree = await h.render();
  const final = nodes(tree, (n) => n.type === "PackageReview")[0].props.final.content;
  const ask = nodes(final, (n) => n.type === "button" && /rv-choice is-amber/.test(n.props.className || ""))[0];
  ask.props.onClick();
  tree = await h.render();
  let ir = nodes(tree, (n) => n.type === "InfoRequest")[0];
  assert.equal(ir.props.session.version, 2, "the review that just ran stays");
  assert.equal(ir.props.latest, true, "an unknown index never makes the newest run 'an earlier version'");
  assert.equal(ir.props.canEdit, false, "editing and sending wait until the index is known again");
  assert.ok(nodes(tree, (n) => n.type === "button" && text(n) === "Try again").length, "the request view offers the retry");
  // The retry finds the run: the newest actual version is edited.
  failRefresh = false;
  newest = 2;
  click(tree, "Try again");
  tree = await h.render();
  ir = nodes(tree, (n) => n.type === "InfoRequest")[0];
  assert.deepEqual([ir.props.session.version, ir.props.latest, ir.props.canEdit], [2, true, true]);
  assert.equal(nodes(tree, (n) => n.type === "button" && text(n) === "Try again").length, 0);
  assert.equal(accept(tree), undefined, "no accept control in the request view");
  h.unmount();
});

test("after recovery the request moves to a newer version another run saved", async () => {
  let failRefresh = false, newest = 1, Err: new (s: number) => Error;
  const h = await reviewHarness({ index: async () => { if (failRefresh) throw new Err(503); return { latest: reviewSession(newest), sessions: [reviewSession(newest)], close_out: null }; } });
  Err = h.EngineError;
  let tree = await h.render({ caseId: "c1" });
  failRefresh = true;
  runAgain(tree);
  tree = await h.render();
  const final = nodes(tree, (n) => n.type === "PackageReview")[0].props.final.content;
  nodes(final, (n) => n.type === "button" && /rv-choice is-amber/.test(n.props.className || ""))[0].props.onClick();
  tree = await h.render();
  failRefresh = false;
  newest = 3;
  click(tree, "Try again");
  tree = await h.render();
  const ir = nodes(tree, (n) => n.type === "InfoRequest")[0];
  assert.deepEqual([ir.props.session.version, ir.props.latest, ir.props.canEdit], [3, true, true]);
  h.unmount();
});

test("a return's decision and the officer's note sent with it are both shown, so the thread can be marked read", async () => {
  // The engine records a return as a decision (with the items to fix) and, at the same moment, a
  // plain message. Showing only the last one left the decision unread and the sidebar stuck on 2.
  const at = "2026-10-22T19:40:56Z";
  const decision = message("1", "Returned for administrative information.\n\nPlease clarify the owner.", { kind: "decision", created_at: at, items: [{ note: "Owner name", field: "owner_name" }] });
  const note = message("2", "Please update the revision date, then send it again.", { created_at: at });
  const status = message("0", "Submitted for administrative review.", { kind: "status", created_at: "2026-10-22T19:00:00Z", author: applicantReply.author, read_by_me: true });
  const h = await bannerHarness([status, decision, note]);
  const tree = await h.render({ app: app({ status: "returned", unread_messages: 2 }) });
  const shown = text(tree);
  assert.ok(shown.includes("Please clarify the owner."), "the return decision is displayed");
  assert.ok(shown.includes(note.body), "the note sent with it is displayed");
  assert.ok(nodes(tree, (n) => n.type === "a" && text(n).includes("Fix 1 item")).length, "the decision's item still links to its fix");
  assert.equal(h.reads, 1, "both displayed, so the thread is marked read");
  await new Promise((r) => setTimeout(r));
  assert.equal(JSON.stringify(h.patches), JSON.stringify([["c1", { unread_messages: 0 }]]), "the sidebar count clears");
  assert.equal(nodes(tree, (n) => n.type === "button" && text(n) === "Reply").length, 0, "still one-way");
  h.unmount();
});

test("a return also lists the officer's unread messages from an earlier round, then marks the thread read", async () => {
  // An applicant can resend without opening the last return; those messages stay counted, so they are shown.
  const old = message("0", "An earlier round's note.", { created_at: "2026-10-20T10:00:00Z" });
  const seen = message("5", "An earlier note already read.", { created_at: "2026-10-20T09:00:00Z", read_by_me: true });
  const decision = message("1", "Returned again.", { kind: "decision", created_at: "2026-10-22T10:00:00Z", items: [{ note: "Owner name", field: "owner_name" }] });
  const h = await bannerHarness([seen, old, decision]);
  const tree = await h.render({ app: app({ status: "returned", unread_messages: 2 }) });
  const shown = text(tree);
  assert.ok(shown.indexOf("Returned again.") < shown.indexOf(old.body), "the new return leads, the earlier unread note follows");
  assert.ok(shown.indexOf(old.body) < shown.indexOf(seen.body), "read history stays on the page, after the unread note");
  assert.equal(h.reads, 1);
  h.unmount();
});

test("the sidebar offers Delete on every owned application; the server's DELETE policy decides", async () => {
  const statuses = ["draft", "submitted", "in_review", "returned", "accepted", "refused", "withdrawn"] as const;
  const owned = statuses.map((status, i) => app({ id: `c${i}`, status, archived: false, pinned: false }));
  const account = { phase: "signed-in", user: { role: "applicant", applicant_type: "homebuilder" }, applications: owned };
  const h = await componentHarness(new URL("./Shell.tsx", import.meta.url), "Shell", {
    "../api/sync": { engineGeneration: () => 0 },
    "../store": { useCase: () => ({ c: { title: "", description: "", authority: "" }, gaps: [], engineGaps: [], phase: "who", engineId: null }) },
    "../humanReview": { groupGaps: () => new Map() },
    "./account": { useAccount: () => account, bootAccount() {}, refreshApplications: async () => {} },
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
