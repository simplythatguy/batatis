/**
 * Start over / New application while another application is still saving or opening: the new draft
 * wins. The late switch neither clears the new draft's visit state (its description and staged PDFs)
 * nor navigates away or leaves a stale note (U3's Shell seam, proposal 77984e52). Drives the actual
 * Shell with its store, list and session mocked.
 */
import assert from "node:assert/strict";
import { test } from "node:test";
import { componentHarness, nodes } from "../../../scripts/component-harness.mjs";
import { emptyCase } from "../../intake.ts";
import * as library from "../libraryContext.ts";

type Tree = Parameters<typeof nodes>[0];

function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => { resolve = r; });
  return { promise, resolve };
}

async function shell(over: { saveStatus?: string; saveDraft?: () => Promise<boolean>; openCase?: () => Promise<string | null> } = {}) {
  const calls: string[] = [];
  const location = { hash: "#/questions", replace() {} };
  const account = { phase: "signed-in", user: { id: "owner", role: "applicant", authority: null }, applications: [
    { id: "c1", title: "First", status: "draft", authority: "edmonton", updated_at: "", submitted_at: null, completeness: { answered: 0, total: 1 }, unread_messages: 0, reviewer: null, archived: false, pinned: false },
    { id: "c2", title: "Second", status: "draft", authority: "edmonton", updated_at: "", submitted_at: null, completeness: { answered: 0, total: 1 }, unread_messages: 0, reviewer: null, archived: false, pinned: false },
  ] };
  const store = {
    c: emptyCase("homebuilder"), gaps: [], engineGaps: [], phase: "case", engineId: "c1", checkStatus: "idle",
    saveStatus: over.saveStatus ?? "saved",
    saveDraft: over.saveDraft ?? (async () => true),
    openCase: over.openCase ?? (async () => null),
    resetToWho: () => { calls.push("resetToWho"); location.hash = "#/"; },
    requestCheck() {}, renameCase: async () => null,
    // The synchronous save state the switch reads (an answer derived since the last render is unsaved too).
    readSync: () => ({ saved: store.saveStatus === "saved", reviewed: false, detail: "" }),
    refreshCurrentCase: async () => null,
  };
  const h = await componentHarness(new URL("../Shell.tsx", import.meta.url), "Shell", {
    "../store": { useCase: () => store },
    "../humanReview": { groupGaps: () => new Map() },
    "./account": { useAccount: () => account, bootAccount() {}, refreshApplications: async () => {}, accountSession: () => "session-1" },
    "./notifications/notifications": { useNotifications: () => ({ phase: "idle", items: [] }) },
    "./applications": { readOnly: () => false, groupApplications: () => ({ pinned: [], active: [] }) },
    "./assistant/assistant": { invalidateAssistantNavigation() {}, setAssistantCase() {}, setAssistantContext() {}, toggleAssistant() {}, useAssistant: () => ({ open: false }) },
    "./assistant/destinations": { OPEN_APPLICATIONS: "cf:open-applications" },
    "./assistant/AskButton": { AskButton: "AskButton", AskHost: { Provider: "fragment" } },
    "./begin": { roleOf: () => "homebuilder" },
    "./CodePalette": { OPEN_PALETTE: "cf:open-palette" },
    "./codeScope": { useCodeScope: () => "application", ApplicationSwitchContext: { Provider: "fragment" } },
    "./libraryContext": library,
    "./deck": { buildDeck: () => [], deckProgress: () => ({ done: 0, total: 0 }) },
    "./useDeckExtras": { useDeckExtras: () => ({ options: {} }) },
    "./routes": { STAGES: [{ screen: "start" }, { screen: "questions" }], rememberStage() {} },
    "./comments/opening": { setOpenProblem() {} },
    "./session": { useSession: () => ({ seen: [] }), getSession: () => ({ draft: "" }), resetSession: () => calls.push("resetSession") },
    "./shell/AppLayout": { AppLayout: "AppLayout" },
    "./shell/ApplicationList": { ApplicationList: "ApplicationList" },
    "../router": { useRoute: () => ({ path: "/questions", params: new URLSearchParams() }) },
    "../api/sync": { engineGeneration: () => 1, engineCaseId: () => store.engineId, isEngineGeneration: () => true },
    "./useRelevance": { resetRelevance: () => calls.push("resetRelevance") },
    "./ui": { MOD_KEY: "⌘" },
  }, {
    sessionStorage: { getItem: () => null, setItem() {}, removeItem() {} },
    location,
    document: { addEventListener() {}, removeEventListener() {}, getElementById: () => null },
    window: { addEventListener() {}, removeEventListener() {}, matchMedia: () => ({ matches: false }), setTimeout: () => 0 },
  });
  const render = () => h.render({ active: "questions", children: null });
  const list = (tree: Tree) => nodes(tree, (n) => n.type === "AppLayout")[0].props.list;
  return { h, render, list, calls, location };
}

const flush = async () => { for (let i = 0; i < 10; i++) await Promise.resolve(); };

test("New application while another application is opening keeps the new draft and stays put", async () => {
  const opened = deferred<string | null>();
  const s = await shell({ openCase: () => opened.promise });
  try {
    const select = s.list(await s.render()).props.onSelect;
    select("c2");
    await flush();
    s.list(await s.render()).props.onNew(); // New application (signed in, in a case)
    assert.deepEqual(s.calls, ["resetSession", "resetRelevance", "resetToWho"]);
    opened.resolve(null); // the store drops an abandoned open and reports no error
    await flush();
    await s.render();
    assert.deepEqual(s.calls, ["resetSession", "resetRelevance", "resetToWho"], "the late switch clears nothing of the new draft");
    assert.equal(s.location.hash, "#/", "and does not navigate away from it");
  } finally { s.h.unmount(); }
});

test("New application while the open draft is still saving leaves no stale switch note", async () => {
  const saved = deferred<boolean>();
  const s = await shell({ saveStatus: "unsaved", saveDraft: () => saved.promise });
  try {
    s.list(await s.render()).props.onSelect("c2");
    await flush();
    s.list(await s.render()).props.onNew();
    saved.resolve(false); // the old draft's save fails after Start over
    await flush();
    const note = s.list(await s.render()).props.note;
    assert.notEqual(note, library.KEEP_OPEN_NOTE);
    assert.equal(s.location.hash, "#/");
  } finally { s.h.unmount(); }
});

test("without Start over the switch settles and opens the questions as before", async () => {
  const s = await shell();
  try {
    s.location.hash = "#/review";
    s.list(await s.render()).props.onSelect("c2");
    await flush();
    await s.render();
    assert.deepEqual(s.calls, ["resetSession", "resetRelevance"]);
    assert.equal(s.location.hash, "#/questions");
  } finally { s.h.unmount(); }
});
