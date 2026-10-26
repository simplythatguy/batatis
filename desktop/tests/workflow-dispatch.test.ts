import assert from "node:assert/strict";
import test from "node:test";
import { join } from "node:path";
import { KeyVault } from "../src/main/credentials.ts";
import { ProviderDispatch, parseCompleteJson } from "../src/main/provider-dispatch.ts";
import { KeyProviders, type ProviderPost } from "../src/main/provider-http.ts";
import { unavailableProvider, type CompleteJsonResult, type HostProvider } from "../src/main/providers.ts";
import { DesktopHost } from "../src/main/controller.ts";
import { both, fakeCommand, scratch, waitFor } from "./helpers.ts";
import { defaultPick } from "../src/main/models.ts";

const signal = () => new AbortController().signal;
const shape = { type: "object", additionalProperties: false, required: ["answer"], properties: { answer: { type: "string" } } };
const exact = parseCompleteJson({ task: "assistant", system: "SYSTEM verbatim", user: '{"history":[],"question":"synthetic"}', schema: shape, model: "gpt-6-luna", effort: "medium", maxOutputTokens: 1200 });
assert.ok(exact);
const request = exact;
const box = { available: async () => true, encrypt: async (key: string) => Buffer.from(key), decrypt: async (sealed: Buffer) => sealed.toString() };
const ready = (complete: HostProvider["completeJson"]): HostProvider => ({ ...unavailableProvider(), workflowReadiness: async () => ({ ready: true }), completeJson: complete });
const good = (): string => JSON.stringify({ model: request.model, choices: [{ finish_reason: "stop", message: { content: '{"answer":"synthetic"}' } }] });

async function lease(dispatch: ProviderDispatch) {
  const reply = await dispatch.call("provider.profile", {}, signal());
  assert.ok(reply.ok && typeof reply.value === "object" && reply.value !== null && "lease" in reply.value);
  return reply.value.lease;
}
function setup(t: test.TestContext, provider: HostProvider = unavailableProvider(), post: ProviderPost = async () => { throw new Error("network forbidden"); }) {
  const vault = new KeyVault(join(scratch(t), "vault"), box);
  const dispatch = new ProviderDispatch({ account: () => provider, vault, keys: new KeyProviders(vault, post), accepting: () => true });
  t.after(() => dispatch.invalidate()); return { vault, dispatch };
}

test("Off dispatches neither generation nor optional screening, even with saved keys", async (t) => {
  let calls = 0;
  const { vault, dispatch } = setup(t, ready(async () => { calls++; throw new Error("forbidden"); }), async () => { calls++; throw new Error("forbidden"); });
  await vault.save("openai", "offline-api-synthetic"); await vault.save("jev", "offline-screen-synthetic");
  dispatch.select(both("off", true)); const current = await lease(dispatch);
  assert.equal((await dispatch.call("provider.completeJson", { ...request, lease: current }, signal())).ok, false);
  assert.equal((await dispatch.call("provider.jev", { lease: current, body: "{}", timeout: 2 }, signal())).ok, false);
  assert.equal(calls, 0);
});

test("subscription failures never choose saved API billing", async (t) => {
  for (const reason of ["quota", "auth", "model_unavailable", "incomplete", "cancelled", "refused_or_invalid"] as const) {
    let api = 0;
    const { vault, dispatch } = setup(t, ready(async () => ({ ok: false, reason, message: "synthetic failure" })), async () => { api++; return { status: 200, body: good() }; });
    await vault.save("openai", "offline-api-synthetic"); dispatch.select(both("chatgpt", false));
    assert.deepEqual(await dispatch.call("provider.completeJson", { ...request, lease: await lease(dispatch) }, signal()), { ok: false, reason, message: "synthetic failure" }); assert.equal(api, 0);
  }
});

test("explicit API choice sends exact context, schema, model and effort with a main-only synthetic key", async (t) => {
  const captured: unknown[] = [];
  const { vault, dispatch } = setup(t, ready(async () => { throw new Error("subscription forbidden"); }), async (id, key, body) => {
    assert.equal(id, "openai"); assert.equal(key, "offline-api-synthetic"); captured.push(JSON.parse(body)); return { status: 200, body: good() };
  });
  await vault.save("openai", "offline-api-synthetic"); dispatch.select(both("openai", false));
  const reply = await dispatch.call("provider.completeJson", { ...request, lease: await lease(dispatch) }, signal());
  assert.deepEqual(captured, [{ model: request.model, reasoning_effort: request.effort, max_completion_tokens: 1200,
    messages: [{ role: "system", content: request.system }, { role: "user", content: request.user }],
    response_format: { type: "json_schema", json_schema: { name: "assistant", strict: true, schema: shape } } }]);
  assert.ok(reply.ok); assert.deepEqual(reply.value, { json: { answer: "synthetic" }, model: request.model, effort: request.effort, usage: null, served: { source: "openai", model: request.model, effort: request.effort }, billing: "api" }); assert.doesNotMatch(JSON.stringify(reply), /offline-api-synthetic/);
});

test("API quota, auth, redirects, wrong model, truncation, JSON and usage errors get one attempt", async (t) => {
  const cases = [
    { status: 429, body: "{}", reason: "quota" }, { status: 401, body: "{}", reason: "auth" }, { status: 307, body: "{}", reason: "runtime" },
    { status: 200, body: good().replace('"gpt-6-luna"', '"other-model"'), reason: "model_unavailable" },
    { status: 200, body: good().replace('"stop"', '"length"'), reason: "incomplete" }, { status: 200, body: "{", reason: "refused_or_invalid" },
    { status: 200, body: JSON.stringify({ ...JSON.parse(good()), usage: { prompt_tokens: "7", completion_tokens: 1 } }), reason: "refused_or_invalid" },
    { status: 200, body: JSON.stringify({ ...JSON.parse(good()), usage: { prompt_tokens: 7, completion_tokens: 1201 } }), reason: "incomplete" },
    { status: 200, body: good().replace("synthetic", "offline-api-synthetic"), reason: "refused_or_invalid" },
  ];
  for (const fixture of cases) {
    let calls = 0;
    const { vault, dispatch } = setup(t, unavailableProvider(), async () => { calls++; return fixture; });
    await vault.save("openai", "offline-api-synthetic"); dispatch.select(both("openai", false));
    const reply = await dispatch.call("provider.completeJson", { ...request, lease: await lease(dispatch) }, signal());
    assert.ok(!reply.ok); assert.equal(reply.reason, fixture.reason); assert.equal(calls, 1);
  }
});

test("a provider that ignores cancellation cannot publish a stale answer", async (t) => {
  let finish: ((result: CompleteJsonResult) => void) | undefined; let started = false;
  const { dispatch } = setup(t, ready(async () => { started = true; return new Promise((resolve) => { finish = resolve; }); }));
  dispatch.select(both("chatgpt", false)); const oldLease = await lease(dispatch);
  const pending = dispatch.call("provider.completeJson", { ...request, lease: oldLease }, signal());
  await waitFor(() => started); dispatch.select(both("off", false));
  const result = await pending; assert.ok(!result.ok); assert.equal(result.reason, "cancelled");
  finish?.({ ok: true, json: { answer: "late" }, model: request.model, effort: request.effort, usage: null });
  assert.equal((await dispatch.call("provider.completeJson", { ...request, lease: oldLease }, signal())).ok, false);
});

test("schema and effort echoes are checked at dispatch", async (t) => {
  for (const bad of [{ json: {}, effort: "medium" }, { json: { answer: "x" }, effort: "low" }]) {
    const { dispatch } = setup(t, ready(async () => {
      const parsed = parseCompleteJson({ ...request, effort: bad.effort }); assert.ok(parsed);
      return { ok: true, json: bad.json, model: parsed.model, effort: parsed.effort, usage: null };
    }));
    dispatch.select(both("chatgpt", false));
    assert.equal((await dispatch.call("provider.completeJson", { ...request, lease: await lease(dispatch) }, signal())).ok, false);
  }
});

test("key removal cancels work and actor changes replace the engine and session lease", async (t) => {
  const userData = scratch(t); const vault = new KeyVault(join(userData, "vault"), box);
  let called = false; let finish: ((result: CompleteJsonResult) => void) | undefined;
  const provider = ready(async () => { called = true; return new Promise((resolve) => { finish = resolve; }); });
  const host = new DesktopHost({ paths: { userData, resources: "/unused", packaged: true, platform: process.platform }, version: "0.1.0", command: fakeCommand,
    vault, localSession: { load: async () => null, save: async () => {} }, provider, log: () => {}, remount: () => {}, notify: () => {} });
  t.after(() => host.dispose()); await host.boot(); await host.switchWorkspace("dev"); await host.selectModel("workflow", defaultPick("chatgpt"));
  const first = await host.onCall("provider.profile", {}, signal()); assert.ok(first.ok && typeof first.value === "object" && first.value !== null && "lease" in first.value);
  const pending = host.onCall("provider.completeJson", { ...request, lease: first.value.lease }, signal()); await waitFor(() => called);
  assert.deepEqual(await host.removeKey("openai"), { ok: true }); assert.equal((await pending).ok, false);
  finish?.({ ok: true, json: { answer: "late" }, model: request.model, effort: request.effort, usage: null });
  assert.equal((await host.onCall("provider.completeJson", { ...request, lease: first.value.lease }, signal())).ok, false);
  const second = await host.onCall("provider.profile", {}, signal()); await host.switchPerson("reviewer:calgary");
  assert.equal(host.info().person?.profile, "reviewer:calgary"); assert.notDeepEqual(second, await host.onCall("provider.profile", {}, signal()));
});

test("missing keys and status never initialize OS storage", async (t) => {
  let os = 0;
  const vault = new KeyVault(join(scratch(t), "vault"), { available: async () => { os++; throw new Error("must not initialize"); }, encrypt: async () => { throw new Error("must not initialize"); } });
  assert.equal(await vault.status("openai"), "missing"); assert.equal(await vault.use("openai", async () => { throw new Error("must not use"); }), null); assert.equal(os, 0);
});

test("the macOS trusted record binds the current context and cannot identify the Windows binary", async () => {
  const { REVIEWED_MAC_CONTEXT } = await import("../src/main/trusted-context.ts");
  const { CODEX_CONTEXT_FINGERPRINT } = await import("../src/main/codex/config.ts");
  assert.equal(REVIEWED_MAC_CONTEXT.contextFingerprint, CODEX_CONTEXT_FINGERPRINT);
  assert.equal(REVIEWED_MAC_CONTEXT.runtimeSha256, "d8990e3ee7acfbc26f91265b12a1a83f0fee40d0e0f8f1f40a37d4ec21f499cf");
  assert.notEqual(REVIEWED_MAC_CONTEXT.runtimeSha256, "6f267830b029ee25d9339864aa867cd45de9f8fd4c5ea007d2e63c13a0c66d36");
  assert.match(REVIEWED_MAC_CONTEXT.evidence, /552f9b2ccbf9a9edd61122b75c7876e0ae18a388c14032eae265fbe21066fcdb/);
});

test("API cancellation after headers cancels the host and detaches at normal EOF", async () => {
  const { withProviderCancellation } = await import("../src/main/provider-protocol.ts");
  let cancelled = 0;
  const protocol = withProviderCancellation(async () => new Response(new ReadableStream<Uint8Array>({ start(controller) { controller.enqueue(new Uint8Array([1])); } })), () => { cancelled++; });
  const abort = new AbortController();
  const reply = await protocol(new Request("batatis://app/api/assist", { signal: abort.signal }));
  const reader = reply.body!.getReader(); await reader.read(); abort.abort(); assert.equal(cancelled, 1);
  await reader.cancel(); assert.equal(cancelled, 2);
  const completed = withProviderCancellation(async () => new Response("done"), () => { cancelled++; });
  const nextAbort = new AbortController(); const next = await completed(new Request("batatis://app/api/assist", { signal: nextAbort.signal }));
  assert.equal(await next.text(), "done"); nextAbort.abort(); assert.equal(cancelled, 2);
  await completed(new Request("batatis://app/api/auth/logout", { method: "POST" })); assert.equal(cancelled, 3);
});

test("quit during engine startup waits for its owned process and refuses remount or dispatch", async (t) => {
  const { startEngine } = await import("../src/main/engine.ts");
  const userData = scratch(t); let starting = false; let release: (() => void) | undefined; let stopped = false; let remounted = 0;
  const host = new DesktopHost({ paths: { userData, resources: "/unused", packaged: true, platform: process.platform }, version: "0.1.0", command: fakeCommand,
    start: async (...args) => {
      const ready = await startEngine(...args); assert.equal(ready.kind, "ready");
      if (ready.kind === "ready") void ready.engine.exited.then(() => { stopped = true; });
      starting = true; await new Promise<void>((resolve) => { release = resolve; }); return ready;
    },
    vault: new KeyVault(join(userData, "vault"), box), localSession: { load: async () => null, save: async () => {} }, provider: unavailableProvider(),
    log: () => {}, remount: () => { remounted++; }, notify: () => {} });
  const boot = host.boot(); await waitFor(() => starting); const quitting = host.dispose(); release?.();
  await Promise.all([boot, quitting]); host.openWindow(); assert.equal(remounted, 0); assert.equal(stopped, true);
  assert.equal((await host.onCall("provider.profile", {}, signal())).ok, false);
});

test("each kind of work goes to its own pick; the engine keeps its profile and learns what answered", async (t) => {
  const asked: { account: string; model: string; effort: string; task: string }[] = [];
  const answering = (account: "chatgpt" | "claude"): HostProvider => ({ ...ready(async (r) => {
    asked.push({ account, model: r.model, effort: r.effort, task: r.task });
    return { ok: true, json: { answer: account }, model: r.model, effort: r.effort, usage: { inputTokens: 3, outputTokens: 4 } };
  }), id: account });
  const accounts = { chatgpt: answering("chatgpt"), claude: answering("claude") };
  const vault = new KeyVault(join(scratch(t), "vault"), box);
  const dispatch = new ProviderDispatch({ account: (id) => accounts[id], vault, accepting: () => true });
  t.after(() => dispatch.invalidate());
  dispatch.select({ workflow: defaultPick("claude"), chat: defaultPick("chatgpt"), screening: false });

  const profile = async (slot: string) => {
    const reply = await dispatch.call("provider.profile", { slot }, signal());
    assert.ok(reply.ok); return reply.value as Record<string, unknown>;
  };
  assert.deepEqual([(await profile("workflow")).generation, (await profile("workflow")).billing], ["claude", "subscription"]);
  assert.deepEqual([(await profile("chat")).generation, (await profile("chat")).billing], ["chatgpt", "subscription"]);
  const leased = (await profile("workflow")).lease;

  const intake = await dispatch.call("provider.completeJson", { ...request, task: "intake", lease: leased }, signal());
  assert.ok(intake.ok);
  assert.deepEqual(intake.value, { json: { answer: "claude" }, model: "gpt-6-luna", effort: "medium", usage: { inputTokens: 3, outputTokens: 4 },
    served: { source: "claude", model: "claude-haiku-5-5", effort: "low" }, billing: "subscription" });
  const chat = await dispatch.call("provider.completeJson", { ...request, task: "assistant", lease: leased }, signal());
  assert.ok(chat.ok && (chat.value as { served: { source: string } }).served.source === "chatgpt");
  assert.deepEqual(asked, [
    { account: "claude", model: "claude-haiku-5-5", effort: "low", task: "intake" },
    { account: "chatgpt", model: "gpt-6-luna", effort: "medium", task: "assistant" },
  ]);
});

test("a chat-only pick leaves the workflow off and its screening closed", async (t) => {
  const { dispatch, vault } = setup(t, ready(async () => { throw new Error("must not be asked"); }));
  await vault.save("jev", "offline-jev-synthetic");
  dispatch.select({ workflow: { source: "off" }, chat: defaultPick("claude"), screening: true });
  const reply = await dispatch.call("provider.profile", { slot: "workflow" }, signal());
  assert.ok(reply.ok);
  const value = reply.value as Record<string, unknown>;
  assert.deepEqual([value.generation, value.screening, value.billing], ["off", false, "none"]);
  const refused = await dispatch.call("provider.completeJson", { ...request, task: "intake", lease: value.lease }, signal());
  assert.deepEqual(refused, { ok: false, reason: "unavailable", message: "AI is off in Settings." });
});

test("a model pick keeps the engine and window, sets both kinds the first time, and survives a restart", async (t) => {
  const userData = scratch(t);
  const windows: number[] = [];
  const make = () => new DesktopHost({ paths: { userData, resources: "/unused", packaged: true, platform: process.platform }, version: "0.1.0", command: fakeCommand,
    vault: new KeyVault(join(userData, "vault"), box), localSession: { load: async () => null, save: async () => {} }, provider: unavailableProvider(),
    log: () => {}, remount: (generation) => windows.push(generation), notify: () => {} });
  const host = make();
  t.after(() => host.dispose());
  await host.boot();
  const before = host.generation;
  assert.deepEqual(await host.selectModel("chat", defaultPick("claude")), { ok: true });
  assert.equal(host.generation, before, "no new window");
  assert.ok(!windows.includes(before + 1));
  assert.deepEqual([host.configuration().workflow, host.configuration().chat], [defaultPick("claude"), defaultPick("claude")]);
  assert.deepEqual(await host.selectModel("workflow", defaultPick("chatgpt")), { ok: true });
  assert.deepEqual([host.configuration().workflow, host.configuration().chat], [defaultPick("chatgpt"), defaultPick("claude")]);
  await host.dispose();
  const again = make();
  t.after(() => again.dispose());
  await again.boot();
  assert.deepEqual([again.configuration().workflow, again.configuration().chat], [defaultPick("chatgpt"), defaultPick("claude")]);
});
