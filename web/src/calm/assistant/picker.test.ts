/**
 * The PDF chooser belongs to the application it was opened for (R8 review, 567d0ead): a file chosen
 * after switching application or account is never uploaded to the new one. Adapted from the
 * reviewer's probes; it drives the actual AttachButton handlers and the actual assistant store.
 */
import assert from "node:assert/strict";
import { test } from "node:test";
import { componentHarness, nodes } from "../../../scripts/component-harness.mjs";
import * as A from "./assistant.ts";
import type { AssistBinding } from "./assistant.ts";

const flush = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
const binding = (caseId: string, who = "u1"): AssistBinding => ({ accountId: who, role: "applicant", authority: null, mode: "case", caseId, caseName: caseId, canUpload: true, files: [] });
const file = () => new File(["synthetic PDF"], "A-selected.pdf", { type: "application/pdf" });

function fixture() {
  A.resetAssistant();
  const uploads: { caseId: string; name: string }[] = [];
  let who = "u1";
  A.setAssistantDeps({
    account: () => ({ signedIn: true, userId: who, role: "applicant", authority: null }),
    upload: async (caseId, f) => { uploads.push({ caseId, name: f.name }); return { id: `file_${caseId}`, name: f.name }; },
    caseVersion: async () => 7,
    assist: async () => ({ answer: "Current administrative help", cited: [], removed_citations: [], notice: "" }),
    page: { path: () => "/questions", hash: () => "#/questions", card: () => "field-owner", shows: () => false, focusId: () => null, focus() {}, go() {}, settle: async () => {} },
    setTimer: () => 0, clearTimer() {}, now: () => 1_000_000,
  });
  A.setAssistantBinding(binding("A"));
  return { uploads, principal: (value: string) => { who = value; } };
}

async function picker() {
  return componentHarness(new URL("./VoiceControls.tsx", import.meta.url), "AttachButton", {
    "./assistant": A, "../icons": { Icon24: "icon" }, "./ToolButton": { ToolButton: "tool-button" },
  });
}

type Tree = Parameters<typeof nodes>[0];
const input = (tree: Tree) => nodes(tree, (n) => n.type === "input")[0];

/** Press the actual Upload control, which opens the browser's chooser. */
function openChooser(tree: Tree) {
  let opened = 0;
  input(tree).props.ref.current = { click() { opened++; } };
  nodes(tree, (n) => n.type === "tool-button")[0].props.onClick();
  assert.equal(opened, 1, "the Upload control opened the chooser");
}

const choose = async (tree: Tree) => { input(tree).props.onChange({ target: { files: [file()], value: "selection" } }); await flush(); };

test("a file chosen for A after switching to B is not uploaded to B", async () => {
  const f = fixture(); const h = await picker();
  try {
    openChooser(await h.render({ a: A.getAssistantState() }));
    A.setAssistantBinding(binding("B"));
    await choose(await h.render({ a: A.getAssistantState() }));
    assert.deepEqual(f.uploads, [], "nothing is uploaded to B (or to A, which is no longer open)");
    assert.deepEqual(A.getAssistantState().conv.attachments, []);
    A.setAssistantBinding(binding("A"));
    assert.deepEqual(A.getAssistantState().conv.attachments, [], "A's conversation gains nothing either");
  } finally { h.unmount(); A.resetAssistant(); }
});

test("a chooser opened in A is refused after A → B → A (a new lifetime)", async () => {
  const f = fixture(); const h = await picker();
  try {
    openChooser(await h.render({ a: A.getAssistantState() }));
    A.setAssistantBinding(binding("B"));
    A.setAssistantBinding(binding("A"));
    await choose(await h.render({ a: A.getAssistantState() }));
    assert.deepEqual(f.uploads, []);
  } finally { h.unmount(); A.resetAssistant(); }
});

test("a chooser from the previous account cannot upload for the next one", async () => {
  const f = fixture(); const h = await picker();
  try {
    openChooser(await h.render({ a: A.getAssistantState() }));
    f.principal("u2"); A.setAssistantBinding(binding("B", "u2"));
    await choose(await h.render({ a: A.getAssistantState() }));
    assert.deepEqual(f.uploads, []);
  } finally { h.unmount(); A.resetAssistant(); }
});

test("the current application's chooser uploads and selects its stored file id", async () => {
  const f = fixture(); const h = await picker();
  try {
    const tree = await h.render({ a: A.getAssistantState() });
    openChooser(tree);
    await choose(tree);
    assert.deepEqual(f.uploads, [{ caseId: "A", name: "A-selected.pdf" }]);
    assert.deepEqual(A.selectedAttachmentIds(), ["file_A"]);
  } finally { h.unmount(); A.resetAssistant(); }
});

test("an ordinary rerender with the same binding still accepts the chosen file", async () => {
  const f = fixture(); const h = await picker();
  try {
    openChooser(await h.render({ a: A.getAssistantState() }));
    A.setDraft("Ordinary composer edit");
    await choose(await h.render({ a: A.getAssistantState() }));
    assert.deepEqual(f.uploads, [{ caseId: "A", name: "A-selected.pdf" }]);
  } finally { h.unmount(); A.resetAssistant(); }
});

test("a chooser result is refused once its application became read-only", async () => {
  const f = fixture(); const h = await picker();
  try {
    const tree = await h.render({ a: A.getAssistantState() });
    openChooser(tree);
    A.setAssistantBinding({ ...binding("A"), canUpload: false });
    await choose(tree);
    assert.deepEqual(f.uploads, []);
  } finally { h.unmount(); A.resetAssistant(); }
});
