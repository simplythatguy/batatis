import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../scripts/component-harness.mjs";
import type { ApplicationSummary, Message } from "../api/accounts.ts";
import * as packageView from "./reviewer/packageView.ts";
import * as queue from "./reviewer/queue.ts";

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

async function bannerHarness(initial: Message[]) {
  let messages = initial, reads = 0, loads = 0;
  const patches = [];
  const harness = await componentHarness(new URL("./shell/ReturnedBanner.tsx", import.meta.url), "ReturnedBanner", {
    "../../api/accounts": { accounts: {
      messages: async () => { loads++; return messages; },
      markRead: async () => { reads++; },
      postMessage: async (_id, body) => message("4", body, { author: applicantReply.author, read_by_me: true }),
    } },
    "../../api/client": { EngineError: Error },
    "../../store": { useCase: () => ({ c: {}, gaps: [] }), hrefFor: () => "#/review" },
    "../account": { initials: () => "MO", patchApplication: (...p) => patches.push(p) },
    "../applications": { authorityName: () => "Edmonton" },
    "../routes": { calmHref: (href) => href },
  });
  return { ...harness, setMessages: (next: Message[]) => { messages = next; }, get reads() { return reads; }, get loads() { return loads; }, patches };
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
  assert.doesNotMatch(shown, /See what’s missing|Fix \d|returned this/);
  assert.equal(h.reads, 1, "the fully displayed unread messages can be marked read");
  h.unmount();
});

test("the banner leaves hidden earlier unread correspondence unread", async () => {
  const hidden = message("0", "An earlier message before the decision.");
  const h = await bannerHarness([hidden, refusal, applicantReply, officerReply]);
  const tree = await h.render({ app: app() });
  assert.equal(h.reads, 0, "the bulk-read endpoint must not clear a message the banner never displayed");
  assert.equal(h.patches.length, 0, "the local unread count is not falsely cleared");
  assert.ok(text(tree).includes(officerReply.body));
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
  assert.match(text(tree), /returned this/);
  assert.ok(nodes(tree, (n) => n.type === "a" && text(n).includes("Fix 1 item")).length, "fixing the application is the answer");
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
    "../store": { useCase: () => ({ c: draft, gaps: [], engineGaps: [], phase: "case", engineId: "c1", saveStatus: "unsaved", openCase: async () => { reopened++; }, saveDraft: async () => { saved++; } }) },
    "../humanReview": { groupGaps: () => new Map() },
    "./account": { useAccount: () => account, bootAccount() {}, refreshApplications: async () => { refreshes++; account.applications = [remote]; } },
    "./applications": { authorityName: () => "Edmonton", readOnly: () => false },
    "./assistant/assistant": { useAssistant: () => ({ open: false }), setAssistantCase() {}, setAssistantContext() {} },
    "./session": { useSession: () => ({ seen: [] }), getSession: () => ({ draft: "" }) },
    "./deck": { buildDeck: () => [], deckProgress: () => ({ done: 0, total: 0 }) },
    "./useDeckExtras": { useDeckExtras: () => ({ options: {} }) },
    "./routes": { STAGES: [{ screen: "application" }] },
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
  assert.ok(text(await b.render(banner.props)).includes(refusal.body));
  remote = app({ updated_at: officerReply.created_at });
  route.params = new URLSearchParams("case=c1");
  await h.render();
  tree = await h.render();
  banner = nodes(tree, (n) => n.type === "AppLayout")[0].props.banner;
  b.setMessages([refusal, applicantReply, officerReply]);
  assert.ok(text(await b.render(banner.props)).includes(officerReply.body), "a later same-file notification also refreshes correspondence");
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

test("a failed refusal-notice load offers a retry that shows the notice once it loads", async () => {
  let fail = true, loads = 0, reads = 0;
  const h = await componentHarness(new URL("./shell/ReturnedBanner.tsx", import.meta.url), "ReturnedBanner", {
    "../../api/accounts": { accounts: {
      messages: async () => { loads++; if (fail) throw Object.assign(new Error("outage"), { detail: "The officer’s message did not load." }); return [refusal]; },
      markRead: async () => { reads++; },
    } },
    "../../api/client": { EngineError: Error },
    "../../store": { useCase: () => ({ c: {}, gaps: [] }), hrefFor: () => "#/review" },
    "../account": { initials: () => "MO", patchApplication() {} },
    "../applications": { authorityName: () => "Edmonton" },
    "../routes": { calmHref: (href) => href },
  });
  let tree = await h.render({ app: app() });
  assert.equal(loads, 1);
  assert.match(text(tree), /did not load/);
  assert.doesNotMatch(text(tree), /A refusal was recorded/, "an unknown notice is not described as missing");
  assert.equal(reads, 0, "nothing is marked read while the notice is not shown");
  fail = false;
  click(tree, "Try again");
  tree = await h.render();
  assert.equal(loads, 2);
  assert.ok(text(tree).includes(refusal.body), "the final refusal reasons and appeal notice appear after the retry");
  assert.doesNotMatch(text(tree), /did not load/);
  assert.equal(nodes(tree, (n) => n.type === "button" && text(n) === "Try again").length, 0);
  assert.equal(nodes(tree, (n) => n.type === "textarea").length, 0, "still no reply box");
  h.unmount();
});

test("a retry started for one file never shows its notice on another file", async () => {
  const pending: { id: string; resolve: (m: Message[]) => void; reject: (e: unknown) => void }[] = [];
  const h = await componentHarness(new URL("./shell/ReturnedBanner.tsx", import.meta.url), "ReturnedBanner", {
    "../../api/accounts": { accounts: {
      messages: (id: string) => new Promise<Message[]>((resolve, reject) => pending.push({ id, resolve, reject })),
      markRead: async () => {},
    } },
    "../../api/client": { EngineError: Error },
    "../../store": { useCase: () => ({ c: {}, gaps: [] }), hrefFor: () => "#/review" },
    "../account": { initials: () => "MO", patchApplication() {} },
    "../applications": { authorityName: () => "Edmonton" },
    "../routes": { calmHref: (href) => href },
  });
  await h.render({ app: app() });
  pending[0].reject(Object.assign(new Error("outage"), { detail: "The officer’s message did not load." }));
  let tree = await h.render();
  click(tree, "Try again");
  tree = await h.render();
  assert.equal(pending.length, 2);
  tree = await h.render({ app: app({ id: "c2" }) });
  assert.equal(pending[2].id, "c2");
  pending[1].resolve([refusal]);
  tree = await h.render();
  assert.ok(!text(tree).includes(refusal.body), "the first file's late answer is ignored");
  pending[2].resolve([officerReply]);
  tree = await h.render();
  assert.ok(text(tree).includes(officerReply.body));
  h.unmount();
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
