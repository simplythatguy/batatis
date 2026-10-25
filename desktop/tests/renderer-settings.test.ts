import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../web/scripts/component-harness.mjs";
import { protocolHost } from "./fixtures/protocol-host.mjs";
import { parseRows } from "../../web/src/desktop/host.ts";
import { saveBeforeSwitch } from "../../web/src/desktop/switching.ts";

async function settings(t, action: string, events: string[]) {
  let acknowledged = false;
  let save = Promise.withResolvers<boolean>();
  const operations: Promise<unknown>[] = [];
  t.after(async () => { save.resolve(false); await Promise.all(operations); });
  const state = await protocolHost(t, events);
  const session = { uploading: [], held: [], draft: "", draftFiles: [] };
  const store = {
    phase: "case", saveStatus: "failed", submitting: false, submissionDispatched: false,
    saveDraft: async () => {
      events.push("save:start");
      acknowledged = await save.promise;
      events.push(acknowledged ? "save:acknowledged" : "save:failed");
      store.saveStatus = acknowledged ? "saved" : "failed";
      return acknowledged ? "synthetic-case" : null;
    },
    readSync: () => ({ saved: acknowledged }),
  };
  const preparation = await componentHarness(new URL("../../web/src/desktop/People.tsx", import.meta.url), "PeopleMenu", {
    "../store": { useCase: () => store },
    "../calm/session": { getSession: () => session },
    "./switching": { saveBeforeSwitch },
  });
  t.after(() => preparation.unmount());
  const rows = parseRows(await state.host.providerRows());
  const key = rows.find((row) => row.kind === "key");
  const account = rows.find((row) => row.kind === "account");
  assert.ok(key && account);
  if (action === "replaceKey" || action === "removeKey") key.status = "saved";
  if (action === "retryKey") key.status = "secure-storage-unavailable";
  if (action === "disconnect") account.status = { state: "signed-in", plan: null };
  if (action === "connect") account.status = { state: "signed-out", last: null };
  if (action === "openLogin" || action === "cancelLogin") account.status = { state: "pending", userCode: "TEST", address: "https://example.invalid" };
  const track = (name: string, work: () => Promise<unknown>) => {
    events.push(`host:${name}`);
    const pending = work();
    operations.push(pending);
    return pending;
  };
  const h = await componentHarness(new URL("../../web/src/desktop/DesktopSettings.tsx", import.meta.url), "DesktopSettings", {
    "../calm/settings/rows": { Chips: "Chips", Row: "Row" },
    "./People": { useSaveBeforeSwitch: preparation.exports.useSaveBeforeSwitch, useSwitchPerson: () => ({}), personLabel: () => "Applicant" },
    "./host": {
      useDesktop: () => state.host.info(),
      desktop: {
        providers: async (operation: string, id: string) => {
          if (operation !== "list") await track(operation, async () => {
            if (operation === "enterKey") await state.host.saveKey(id, "synthetic-test-only");
            if (operation === "removeKey") await state.host.removeKey(id);
            if (operation === "disconnect") await state.host.disconnectProvider();
          });
          return rows;
        },
        configuration: async () => state.host.configuration(), onChange: () => () => {},
        selectGeneration: (value) => track("generation", () => state.host.selectGeneration(value)),
        selectScreening: (value) => track("screening", () => state.host.selectScreening(value)),
      },
    },
  });
  t.after(() => h.unmount());
  const root = await h.render();
  const connections = nodes(root, (node) => typeof node.type === "function" && node.type.name === "ConnectionsSection")[0];
  assert.ok(connections);
  h.exports.DesktopSettings = connections.type;
  const render = () => h.render();
  function invoke(tree) {
    if (action === "generation" || action === "screening") {
      const label = action === "generation" ? "AI generation" : "Optional screening";
      nodes(tree, (node) => node.type === "Chips" && node.props.label === label)[0].props.onPick(action === "generation" ? "openai" : "on");
    } else {
      const row = nodes(tree, (node) => node.type === "Row" && node.props.label === (action.endsWith("Key") ? key.label : account.label))[0];
      const controls = nodes(row.props.action, (node) => typeof node.type === "function")[0];
      const buttons = nodes(controls.type(controls.props), (node) => node.type === "button");
      const labels = { addKey: "Add key", replaceKey: "Replace", retryKey: "Try again", removeKey: "Remove", disconnect: "Disconnect", connect: "Connect", openLogin: "Open page", cancelLogin: "Cancel" };
      const button = buttons.find((node) => text(node) === labels[action]);
      assert.ok(button, `The ${action} control remains reachable`);
      button.props.onClick();
    }
  }
  return {
    ...state, store, session, render, invoke,
    finishSave: (ok: boolean) => save.resolve(ok),
    retrySave: () => { save = Promise.withResolvers<boolean>(); },
    settle: async () => { await render(); await Promise.all(operations); return render(); },
  };
}

for (const action of ["generation", "screening", "addKey", "replaceKey", "retryKey", "removeKey", "disconnect"]) {
  test(`${action} preserves the renderer on a failed save and changes the host only after a confirmed retry`, { timeout: 5000 }, async (t) => {
    const events: string[] = [];
    const s = await settings(t, action, events);
    const generation = s.host.generation;
    const configuration = s.host.configuration();
    s.invoke(await s.render());
    let tree = await s.render();
    assert.deepEqual(events, ["save:start"], "the host cannot act while save acknowledgement is pending");
    assert.ok(nodes(tree, (node) => node.type === "fieldset").every((node) => node.props.disabled));
    assert.ok(nodes(tree, (node) => node.type === "Row" && node.props.action).every((node) => node.props.action.props.disabled));
    s.finishSave(false);
    tree = await s.settle();
    assert.deepEqual(events, ["save:start", "save:failed"]);
    assert.equal(s.host.generation, generation, "the old renderer and its draft survive");
    assert.deepEqual(s.host.configuration(), configuration);
    assert.ok(nodes(tree, (node) => node.type === "fieldset").every((node) => !node.props.disabled));
    assert.match(text(nodes(tree, (node) => node.props?.role === "alert")), /didn’t save/);
    s.retrySave();
    s.invoke(tree);
    await s.render();
    assert.equal(s.host.generation, generation);
    s.finishSave(true);
    tree = await s.settle();
    const operation = action.endsWith("Key") && action !== "removeKey" ? "enterKey" : action;
    assert.deepEqual(events.slice(0, 5), ["save:start", "save:failed", "save:start", "save:acknowledged", `host:${operation}`]);
    assert.equal(events.at(-1), "remount");
    assert.equal(s.host.generation, generation + 1);
    assert.equal(nodes(tree, (node) => node.props?.role === "alert" && /didn’t save/.test(text(node))).length, 0);
    if (action === "generation") assert.equal(s.host.configuration().generation, "openai");
    if (action === "screening") assert.equal(s.host.configuration().screening, true);
  });
}

for (const action of ["connect", "openLogin", "cancelLogin"]) {
  test(`${action} and the initial connection/configuration reads do not save or remount`, async (t) => {
    const events: string[] = [];
    const s = await settings(t, action, events);
    const generation = s.host.generation;
    const tree = await s.render();
    assert.deepEqual(events, [], "loading is read-only even with a failed draft");
    s.invoke(tree);
    await s.settle();
    assert.deepEqual(events, [`host:${action}`]);
    assert.equal(s.host.generation, generation);
  });
}

test("an unstarted description blocks a generation change without discarding its text", async (t) => {
  const events: string[] = [];
  const s = await settings(t, "generation", events);
  s.store.phase = "who";
  s.store.saveStatus = "idle";
  s.session.draft = "My unsaved application description";
  const generation = s.host.generation;
  s.invoke(await s.render());
  const tree = await s.settle();
  assert.deepEqual(events, []);
  assert.equal(s.host.generation, generation);
  assert.equal(s.session.draft, "My unsaved application description");
  assert.match(text(nodes(tree, (node) => node.props?.role === "alert")), /Start or clear/);
});
