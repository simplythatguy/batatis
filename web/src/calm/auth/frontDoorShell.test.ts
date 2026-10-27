import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../../scripts/component-harness.mjs";
import { emptyCase } from "../../intake.ts";
import * as applications from "../applications.ts";

async function shell(signedIn: boolean, startRequested: boolean) {
  let opened = 0;
  const h = await componentHarness(new URL("../Shell.tsx", import.meta.url), "Shell", {
    "../store": { useCase: () => ({ c: emptyCase(null), phase: "who", engineId: null, gaps: [], engineGaps: [], openCase: async () => { opened++; return null; } }) },
    "../api/sync": { engineGeneration: () => 0, engineCaseId: () => null, isEngineGeneration: () => true },
    "../humanReview": { groupGaps: () => new Map() },
    "./account": { useAccount: () => ({ phase: signedIn ? "signed-in" : "signed-out", user: signedIn ? { id: "owner", role: "applicant", applicant_type: "manufacturer" } : null, applications: [] }), bootAccount() {}, accountSession: () => 1 },
    "./applications": applications,
    "./assistant/assistant": { useAssistant: () => ({ open: false }), setAssistantCase() {}, setAssistantContext() {} },
    "./assistant/AskButton": { AskHost: { Provider: "fragment" } },
    "./codeScope": { useCodeScope: () => "application", ApplicationSwitchContext: { Provider: "fragment" } },
    "./session": { useSession: () => ({ seen: [] }), getSession: () => ({ draft: "My new addition", startRequested }) },
    "./deck": { buildDeck: () => [], deckProgress: () => ({ done: 0, total: 0 }) },
    "./useDeckExtras": { useDeckExtras: () => ({ options: {} }) },
    "./routes": { rememberStage() {}, STAGES: [{ screen: "start" }] },
    "./notifications/notifications": { useNotifications: () => ({ phase: "idle", items: [] }) },
    "./shell/AppLayout": { AppLayout: "AppLayout" },
    "./shell/AppHeader": { AppHeader: "AppHeader" },
    "../router": { useRoute: () => ({ path: "/", params: new URLSearchParams() }) },
  }, {
    location: { hash: "#/" },
    sessionStorage: { getItem: (key: string) => key === "batatis-open-application-owner" ? "owner" : key === "batatis-open-application" ? "older-case" : null, setItem() {}, removeItem() {} },
    document: { addEventListener() {}, removeEventListener() {} },
    window: { addEventListener() {}, removeEventListener() {} },
  });
  return { h, opened: () => opened };
}

test("the signed-out header offers quiet Sign in without application navigation", async () => {
  const page = await shell(false, false);
  const tree = await page.h.render({ active: "start", children: "Start composer" });
  const layout = nodes(tree, (n: { type: string }) => n.type === "AppLayout")[0];
  assert.equal(layout.props.rail, null);
  assert.equal(layout.props.list, undefined);
  assert.equal(layout.props.header.props.title, "Batatis");
  assert.equal(layout.props.header.props.stages, undefined);
  const signin = layout.props.header.props.right;
  assert.equal(signin.props.href, "#/signin");
  assert.equal(text(signin), "Sign in");
  assert.match(signin.props.className, /is-ghost/);
  page.h.unmount();
});

test("a pending Start after OAuth cannot be overwritten by the previous open application", async () => {
  const page = await shell(true, true);
  await page.h.render({ active: "start", children: "Start composer" });
  assert.equal(page.opened(), 0);
  page.h.unmount();
});
