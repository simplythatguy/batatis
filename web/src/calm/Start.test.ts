import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../scripts/component-harness.mjs";
import { emptyCase } from "../intake.ts";
import { reducer, type Action } from "../model.ts";
import type { User } from "../api/accounts.ts";
import { getSession, resetSession, updateSession } from "./session.ts";

const person: User = { id: "u1", email: "owner@example.test", name: "Owner", role: "applicant", applicant_type: null, authority: null, onboarded: true, created_at: "2026-10-26" };

async function startPage(signedIn = false) {
  const account = { phase: signedIn ? "signed-in" : "signed-out", user: signedIn ? person : null };
  let c = emptyCase(null), phase = "who", starts = 0;
  const location = { hash: "#/" };
  const store = () => ({ c, phase, dispatch: (a: Action) => { c = reducer(c, a); }, beginEmpty: (role: Parameters<typeof emptyCase>[0]) => { c = emptyCase(role); phase = "case"; starts++; }, readDescription() {} });
  const begin = await componentHarness(new URL("./begin.ts", import.meta.url), "useBegin", {
    "../store": { useCase: store }, "./account": { useAccount: () => account }, "./session": { getSession, resetSession },
  }, { location });
  const auth = await componentHarness(new URL("./auth/useAuthGate.ts", import.meta.url), "useAuthGate", {
    "../session": { getSession, resetSession, updateSession },
  }, { location, sessionStorage: { getItem: () => null, setItem() {}, removeItem() {} } });
  const h = await componentHarness(new URL("./Start.tsx", import.meta.url), "Start", {
    "../store": { useCase: store },
    "./account": { useAccount: () => account },
    "./begin": { useBegin: begin.exports.useBegin, useCurrentApplication: () => ({ app: null, locked: false }) },
    "./session": { getSession, useSession: getSession, updateSession },
    "./auth/useAuthGate": { requestStartSignIn: auth.exports.requestStartSignIn },
    "./applications": {}, "../intakeView": { pagesLabel: (n: number) => `${n} pages` },
    "./ui": { Dot: "Dot", CIcon: "CIcon", Kbd: "Kbd", MOD_KEY: "⌘" },
  }, {
    location,
    window: { addEventListener() {}, removeEventListener() {} },
    document: { addEventListener() {}, removeEventListener() {} },
  });
  return { h, account, location, case: () => c, starts: () => starts };
}

const startButton = (tree: unknown) => nodes(tree, (n: { type: string; props: { className?: string } }) => n.type === "button" && n.props.className?.includes("is-primary"))[0];
const fileInput = (tree: unknown) => nodes(tree, (n: { type: string; props: { type?: string } }) => n.type === "input" && n.props.type === "file")[0];

test("a signed-out person attaches plans and Start signs in, then starts and reads with no second click", async () => {
  resetSession();
  const page = await startPage();
  let tree = await page.h.render();
  assert.equal(startButton(tree).props.disabled, true);
  assert.match(text(tree), /What are you building\?/);
  assert.doesNotMatch(text(tree), /Who is applying|differently/);
  assert.equal(nodes(tree, (n: { type: string }) => n.type === "textarea")[0].props.placeholder, "Or say it in a few words");
  const input = fileInput(tree);
  for (const extension of [".pdf", ".jpg", ".jpeg", ".png", ".webp", ".txt", ".md"]) assert.ok(input.props.accept.includes(extension), extension);
  const file = new File(["drawing"], "house.webp", { type: "image/webp" });
  input.props.onChange({ target: { files: [file], value: "" } });
  tree = await page.h.render();
  assert.equal(startButton(tree).props.disabled, false, "files alone are enough");
  startButton(tree).props.onClick();
  assert.equal(page.location.hash, "#/signin");
  assert.equal(page.starts(), 0);
  assert.equal(getSession().startRequested, true);
  assert.equal(getSession().draftFiles[0].file, file);
  page.account.phase = "signed-in";
  page.account.user = person;
  await page.h.render();
  assert.equal(page.starts(), 1);
  assert.equal(page.case().applicantType, null);
  assert.equal(getSession().held[0].file, file);
  assert.equal(getSession().readAfterStart, true);
  assert.equal(page.location.hash, "#/questions");
  await page.h.render();
  assert.equal(page.starts(), 1, "the sign-in continuation is consumed once");
  page.h.unmount(); resetSession();
});

test("OAuth reload waits for lost files and starts as soon as they are reattached", async () => {
  resetSession({ draft: "A rear addition", startRequested: true, draftFilesLost: true });
  const page = await startPage(true);
  let tree = await page.h.render();
  assert.equal(page.starts(), 0);
  assert.match(text(tree), /Attach your files again/);
  const file = new File(["plan"], "plan.png", { type: "image/png" });
  fileInput(tree).props.onChange({ target: { files: [file], value: "" } });
  tree = await page.h.render();
  assert.equal(page.starts(), 1);
  assert.equal(page.case().description, "A rear addition");
  assert.equal(getSession().held[0].file, file);
  page.h.unmount(); resetSession();
});

test("a text-only draft resumes after onboarding; visiting Start while signed in does not start it", async () => {
  resetSession({ draft: "A two-storey house" });
  const page = await startPage(true);
  await page.h.render();
  assert.equal(page.starts(), 0);
  page.account.user = { ...person, role: null, onboarded: false };
  updateSession({ startRequested: true });
  await page.h.render();
  assert.equal(page.starts(), 0);
  page.account.user = person;
  await page.h.render();
  assert.equal(page.starts(), 1);
  assert.equal(page.case().description, "A two-storey house");
  page.h.unmount(); resetSession();
});

test("text notes become the description and unsupported files explain the accepted types", async () => {
  resetSession();
  const page = await startPage();
  let tree = await page.h.render();
  fileInput(tree).props.onChange({ target: { files: [new File(["A rear addition"], "notes.md", { type: "text/markdown" })], value: "" } });
  tree = await page.h.render();
  assert.equal(getSession().draft, "A rear addition");
  assert.equal(startButton(tree).props.disabled, false);
  fileInput(tree).props.onChange({ target: { files: [new File(["not supported"], "archive.zip")], value: "" } });
  tree = await page.h.render();
  assert.equal(getSession().draftFiles.length, 0);
  assert.match(text(tree), /Use PDF, JPG, PNG, WebP, TXT or MD/);
  page.h.unmount(); resetSession();
});
