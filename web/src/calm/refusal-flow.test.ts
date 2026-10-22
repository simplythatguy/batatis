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

test("same-file summary updates reload refusal correspondence while preserving a typed reply", async () => {
  const h = await bannerHarness([refusal]);
  let tree = await h.render({ app: app() });
  click(tree, "Reply");
  tree = await h.render();
  nodes(tree, (n) => n.type === "textarea")[0].props.onChange({ target: { value: "My unsent question" } });
  h.setMessages([refusal, applicantReply, officerReply]);
  tree = await h.render({ app: app({ updated_at: officerReply.created_at }) });
  assert.equal(h.loads, 2);
  assert.ok(text(tree).includes(officerReply.body));
  assert.equal(nodes(tree, (n) => n.type === "textarea")[0].props.value, "My unsent question");
  h.unmount();
});

test("returned-for-information keeps its missing-item links and reply submission", async () => {
  const returned = message("1", "Please provide the owner name.", { kind: "decision", items: [{ note: "Owner name", field: "owner_name" }] });
  const h = await bannerHarness([returned]);
  let tree = await h.render({ app: app({ status: "returned" }) });
  assert.match(text(tree), /returned this/);
  assert.ok(nodes(tree, (n) => n.type === "a" && text(n).includes("Fix 1 item")).length);
  click(tree, "Reply");
  tree = await h.render();
  nodes(tree, (n) => n.type === "textarea")[0].props.onChange({ target: { value: "I will add the owner name." } });
  tree = await h.render();
  nodes(tree, (n) => n.type === "form")[0].props.onSubmit({ preventDefault() {} });
  tree = await h.render();
  assert.match(text(tree), /Reply sent to the officer/);
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
    "./applications": { authorityName: () => "Edmonton" },
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
    assert.doesNotMatch(text(requestTree), /Start reviewing \(or take over\)/);
    assert.equal(nodes(requestTree, (n) => n.type === "fieldset")[0].props.disabled, true);
    assert.equal(nodes(requestTree, (n) => n.type === "button" && text(n).startsWith("Send to"))[0].props.disabled, true);
    ir.unmount(); h.unmount();
  }
});

test("an unclaimed editable file keeps takeover guidance; standalone packages keep copy", async () => {
  const h = await componentHarness(new URL("./reviewer/InfoRequest.tsx", import.meta.url), "InfoRequest", { "./packageView": packageView });
  const props = { target: { kind: "case", id: "c1" }, session: request, latest: true, canEdit: false, applicant: "Mira", onChange() {} };
  assert.match(text(await h.render(props)), /Start reviewing \(or take over\)/);
  const tree = await h.render({ ...props, target: { kind: "package", id: "p1" }, canEdit: true });
  assert.ok(nodes(tree, (n) => n.type === "button" && text(n) === "Copy the text").length);
  assert.doesNotMatch(text(tree), /historical|Start reviewing/);
  h.unmount();
});
