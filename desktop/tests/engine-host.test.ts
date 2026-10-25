import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";
import { DesktopHost, parseCompleteJson, type HostDeps } from "../src/main/controller.ts";
import { KeyVault } from "../src/main/credentials.ts";
import { EngineLost, startEngine, type Engine, type EngineCommand, type WorkspaceKind } from "../src/main/engine.ts";
import { createAppProtocol } from "../src/main/protocol.ts";
import { unavailableProvider, type CompleteJsonRequest, type CompleteJsonResult, type HostProvider } from "../src/main/providers.ts";
import { MODEL, EFFORT } from "../src/main/codex/config.ts";
import { fakeCommand, scratch, waitFor } from "./helpers.ts";

const log = () => {};
const onCall = async () => ({ ok: false as const, reason: "unavailable", message: "none" });

async function ready(command: EngineCommand): Promise<Engine> {
  const started = await startEngine(command, { onCall, log });
  assert.equal(started.kind, "ready");
  return (started as { engine: Engine }).engine;
}

async function fakeLog(engine: Engine): Promise<{ requests: { path: string; headers: [string, string][] }[]; cancelled: string[]; sessions: unknown[]; calls: Record<string, unknown>[] }> {
  const result = await engine.control("log");
  assert.ok(result.ok);
  return result.value as never;
}

const request = (path: string, method = "GET") => ({ method, path, query: "", headers: [], body: new Uint8Array(0) });

test("the handshake, a refusal and a broken protocol are told apart at start", async () => {
  const engine = await ready(fakeCommand("dev"));
  assert.deepEqual(engine.hello.workspace, { kind: "dev", id: "fake-workspace" });
  assert.deepEqual(engine.hello.profiles.map((p) => p.profile), ["applicant", "reviewer:calgary"]);
  await engine.stop();
  assert.deepEqual(await startEngine(fakeCommand("local", "refuse"), { onCall, log }), { kind: "refused", reason: "hosted configuration is not allowed" });
  assert.equal((await startEngine(fakeCommand("local", "garbage"), { onCall, log })).kind, "failed");
  assert.equal((await startEngine({ command: "/nonexistent/batatis-engine", args: [], cwd: "/", env: {} }, { onCall, log })).kind, "failed");
});

test("a stream is read as it arrives, and a reader that stops tells the engine", async () => {
  const engine = await ready(fakeCommand("local"));
  const reply = await engine.request(request("/api/stream"));
  const reader = reply.body.getReader();
  assert.equal(new TextDecoder().decode((await reader.read()).value), "event: first\n\n", "first chunk before the stream ends");
  await reader.cancel();
  await waitFor(() => engine.busy === 0);
  assert.equal((await fakeLog(engine)).cancelled.length, 1);
  await engine.stop();
});

test("aborting a request after response headers closes its stream and cancels the engine work", async (t) => {
  const engine = await ready(fakeCommand("local"));
  t.after(() => engine.stop());
  const abort = new AbortController();
  const reply = await engine.request(request("/api/stream"), abort.signal);
  const reader = reply.body.getReader();
  assert.equal(new TextDecoder().decode((await reader.read()).value), "event: first\n\n");
  const waiting = reader.read();
  const failure = assert.rejects(waiting, { name: "AbortError" });
  abort.abort();
  await Promise.all([failure, engine.control("release")]);
  assert.equal(engine.busy, 0);
  assert.equal((await fakeLog(engine)).cancelled.length, 1);
});

test("a crash fails every open request once and nothing is resent", async () => {
  const engine = await ready(fakeCommand("local"));
  const held = engine.request(request("/api/hold"));
  const crash = engine.request(request("/api/crash"));
  await assert.rejects(held, EngineLost);
  await assert.rejects(crash, EngineLost);
  assert.equal(await engine.exited, 9);
  await assert.rejects(engine.request(request("/api/cases")), EngineLost);
  assert.deepEqual(await engine.control("log"), { ok: false, error: "engine-lost" });
});

function host(t: { after(fn: () => void): void }, overrides: Partial<HostDeps> = {}) {
  const userData = scratch(t);
  const windows: { generation: number; route: string | null }[] = [];
  const deps: HostDeps = {
    paths: { userData, resources: "/unused", packaged: true, platform: process.platform },
    version: "0.1.0",
    command: (kind: WorkspaceKind) => fakeCommand(kind),
    vault: new KeyVault(join(userData, "providers"), { available: async () => false, encrypt: async () => Buffer.alloc(0) }),
    localSession: { load: async () => null, save: async () => {} },
    provider: unavailableProvider(),
    log,
    remount: (generation, route) => windows.push({ generation, route }),
    notify: () => {},
    ...overrides,
  };
  const desktop = new DesktopHost(deps);
  t.after(() => desktop.dispose());
  return { desktop, windows, userData };
}

function engineOf(desktop: DesktopHost, generation = desktop.generation): Engine {
  const gate = desktop.gate(generation);
  assert.equal(gate.kind, "open");
  return (gate as { engine: Engine }).engine;
}

test("switching person waits for in-flight work, then only the new window reaches the new session", async (t) => {
  const { desktop, windows, userData } = host(t);
  await desktop.boot();
  desktop.openWindow("#/");
  await desktop.switchWorkspace("dev");
  const before = desktop.generation;
  assert.equal(desktop.info().person?.profile, "applicant");
  const engine = engineOf(desktop);
  const api = createAppProtocol({ distDir: userData, gate: () => desktop.gate(before) });
  const inFlight = api(new Request("batatis://app/api/hold"));
  await waitFor(() => engine.busy === 1);

  const switching = desktop.switchPerson("reviewer:calgary");
  await waitFor(() => desktop.info().service.state === "busy");
  const blocked = await api(new Request("batatis://app/api/cases"));
  assert.equal(blocked.status, 503, "no new request while the switch drains");
  assert.equal(windows.at(-1)?.generation, before, "the window is not replaced before the drain");
  await engine.control("release");
  assert.equal((await inFlight).status, 200, "the earlier request finished as the earlier person");
  assert.deepEqual(await switching, { ok: true });

  assert.deepEqual(windows.at(-1), { generation: before + 1, route: "#/review" }, "a reviewer opens the queue, not a case");
  assert.equal(desktop.info().person?.profile, "reviewer:calgary");
  assert.equal((await api(new Request("batatis://app/api/cases"))).status, 503, "the replaced window is refused");
  const fresh = createAppProtocol({ distDir: userData, gate: () => desktop.gate(desktop.generation) });
  await fresh(new Request("batatis://app/api/me"));
  const replacement = engineOf(desktop);
  assert.notEqual(replacement, engine, "old workers cannot acquire the new person's provider lease");
  assert.equal(await engine.exited, 0);
  await assert.rejects(engine.request(request("/api/me")), EngineLost);
  const sent = (await fakeLog(replacement)).requests.at(-1)!;
  assert.deepEqual(sent.headers, [["cookie", `batatis_session=${"reviewer_calgary".padEnd(43, "t")}`]]);
  const sessions = (await fakeLog(replacement)).sessions.at(-1);
  assert.deepEqual(sessions, { profile: "reviewer:calgary" });
  assert.deepEqual(JSON.parse(readFileSync(join(userData, "settings.json"), "utf8")), { version: 1, workspace: "dev", devProfile: "reviewer:calgary" });
});

test("a failed switch keeps the earlier person, window and session", async (t) => {
  const { desktop, windows } = host(t);
  await desktop.switchWorkspace("dev");
  const generation = desktop.generation;
  const engine = engineOf(desktop);
  await engine.control("fail-next-session");
  const outcome = await desktop.switchPerson("reviewer:calgary");
  assert.equal(outcome.ok, false);
  assert.equal(desktop.info().person?.profile, "applicant");
  assert.equal(desktop.generation, generation);
  assert.equal(windows.at(-1)?.generation, generation);
  assert.equal(desktop.gate(generation).kind, "open");
  assert.equal((await desktop.switchPerson("reviewer:nowhere")).ok, false);
  assert.deepEqual(await desktop.switchPerson("applicant"), { ok: true }, "the current person is a no-op");
});

test("people never switch in the normal workspace", async (t) => {
  const { desktop } = host(t);
  await desktop.boot();
  assert.equal(desktop.info().workspace, "local");
  assert.deepEqual(desktop.info().people, []);
  assert.equal((await desktop.switchPerson("reviewer:calgary")).ok, false);
});

test("an engine crash closes the API until a deliberate restart", async (t) => {
  const { desktop } = host(t);
  await desktop.boot();
  desktop.openWindow();
  const api = createAppProtocol({ distDir: "/unused", gate: () => desktop.gate(desktop.generation) });
  const crashed = await api(new Request("batatis://app/api/crash"));
  assert.equal(crashed.status, 503);
  await waitFor(() => desktop.info().service.state === "failed");
  assert.equal((await api(new Request("batatis://app/api/cases"))).status, 503);
  assert.deepEqual(await desktop.restart(), { ok: true });
  assert.equal(desktop.info().service.state, "ready");
  assert.equal((await api(new Request("batatis://app/api/cases"))).status, 200);
});

function readyProvider(answer: (request: CompleteJsonRequest) => CompleteJsonResult): HostProvider & { asked: CompleteJsonRequest[] } {
  const asked: CompleteJsonRequest[] = [];
  return {
    ...unavailableProvider(),
    asked,
    workflowReadiness: async () => ({ ready: true }),
    completeJson: async (request) => { asked.push(request); return answer(request); },
  };
}

const call = { task: "intake", system: "s", user: "u", schema: { type: "object" }, model: MODEL, effort: EFFORT, maxOutputTokens: null };

async function selected(t: Parameters<typeof host>[0], provider: HostProvider = unavailableProvider()) {
  const instance = host(t, { provider });
  await instance.desktop.boot();
  await instance.desktop.switchWorkspace("dev");
  await instance.desktop.selectGeneration("chatgpt");
  const profile = await instance.desktop.onCall("provider.profile", {}, new AbortController().signal);
  assert.ok(profile.ok && typeof profile.value === "object" && profile.value !== null && "lease" in profile.value);
  return { ...instance, leased: { ...call, lease: profile.value.lease } };
}

test("engine model calls fail closed unless the connection says workflows may use it", async (t) => {
  const unready = await selected(t);
  assert.deepEqual(await unready.desktop.onCall("provider.completeJson", unready.leased, new AbortController().signal),
    { ok: false, reason: "unavailable", message: "This connection isn’t available in this version." });
  const unverified = await selected(t, { ...unavailableProvider(), workflowReadiness: async () => ({ ready: false, reason: "context_unverified", message: "Not verified" }), completeJson: async () => { throw new Error("must not be asked"); } });
  assert.deepEqual(await unverified.desktop.onCall("provider.completeJson", unverified.leased, new AbortController().signal), { ok: false, reason: "context_unverified", message: "Not verified" });

  const exact = readyProvider((r) => ({ ok: true, json: { facts: [] }, model: r.model, effort: r.effort, usage: null }));
  const working = await selected(t, exact);
  assert.deepEqual(await working.desktop.onCall("provider.completeJson", working.leased, new AbortController().signal),
    { ok: true, value: { json: { facts: [] }, model: MODEL, effort: EFFORT, usage: null, billing: "subscription" } });
  assert.deepEqual(exact.asked, [call]);
  const different = parseCompleteJson({ ...call, model: "model-b" });
  assert.ok(different);
  const substituted = await selected(t, readyProvider((r) => ({ ok: true, json: {}, model: different.model, effort: r.effort, usage: null })));
  const refused = await substituted.desktop.onCall("provider.completeJson", substituted.leased, new AbortController().signal);
  assert.ok(!refused.ok && refused.reason === "model_unavailable");
  assert.equal((await working.desktop.onCall("shell.run", {}, new AbortController().signal)).ok, false);
});

test("host calls from the engine are parsed before any provider sees them", () => {
  assert.deepEqual(parseCompleteJson(call), call);
  const document = { ...call, user: "x".repeat(600_000) };
  assert.deepEqual(parseCompleteJson(document), document);
  for (const bad of [null, [], { ...call, model: "" }, { ...call, model: "has space" }, { ...call, effort: "LOUD" }, { ...call, schema: "x" },
    { ...call, task: "Intake!" }, { ...call, maxOutputTokens: -1 }, { ...call, user: "x".repeat(2_500_000) }]) {
    assert.equal(parseCompleteJson(bad), null, JSON.stringify(bad)?.slice(0, 60));
  }
});

test("an engine-initiated call is answered on the same pipe", async () => {
  let asked: unknown = null;
  const started = await startEngine(fakeCommand("local"), { onCall: async (_op, args) => { asked = args; return { ok: true, value: { json: { a: 1 }, model: "m", effort: "low", usage: null } }; }, log });
  assert.equal(started.kind, "ready");
  const engine = (started as { engine: Engine }).engine;
  await engine.control("call", { task: "intake" });
  let calls: Record<string, unknown>[] = [];
  for (let attempt = 0; attempt < 100 && calls.length === 0; attempt += 1) {
    calls = (await fakeLog(engine)).calls;
    if (!calls.length) await new Promise((done) => setTimeout(done, 10));
  }
  assert.deepEqual(calls.map(({ t, ok, value }) => ({ t, ok, value })), [{ t: "call.res", ok: true, value: { json: { a: 1 }, model: "m", effort: "low", usage: null } }]);
  assert.deepEqual(asked, { task: "intake" });
  await engine.stop();
});
