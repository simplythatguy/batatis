import assert from "node:assert/strict";
import { ChildProcess } from "node:child_process";
import { EventEmitter, once } from "node:events";
import { readFileSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { PassThrough } from "node:stream";
import test from "node:test";
import { DesktopHost } from "../src/main/controller.ts";
import { KeyVault } from "../src/main/credentials.ts";
import { Engine, startEngine, type HostCall } from "../src/main/engine.ts";
import { FrameDecoder } from "../src/main/frames.ts";
import { ProviderRpc } from "../src/main/provider-rpc.ts";
import { createAppProtocol } from "../src/main/protocol.ts";
import { withProviderCancellation } from "../src/main/provider-protocol.ts";
import { unavailableProvider, type HostProvider } from "../src/main/providers.ts";
import { DESKTOP, pythonCommand, REPO, scratch, text } from "./helpers.ts";

const fixture = readFileSync(join(DESKTOP, "tests", "fixtures", "request-lifetime.py"), "utf8");

function deferred() {
  let resolve = () => {};
  const promise = new Promise<void>((done) => { resolve = done; });
  return { promise, resolve };
}

const request = (path: string) => ({ method: "POST", path, query: "", headers: [], body: new Uint8Array() });

function inMemoryEngine(onCall: HostCall) {
  const child = new ChildProcess();
  child.stdin = new PassThrough();
  const frames = new EventEmitter();
  const decoder = new FrameDecoder();
  const requests: string[] = [];
  child.stdin.on("data", (data: Buffer) => {
    for (const frame of decoder.push(data)) {
      if (frame.header.t === "req" && typeof frame.header.id === "string") requests.push(frame.header.id);
      frames.emit(String(frame.header.id), frame.header);
    }
  });
  const engine = new Engine(child, { workspace: { kind: "local", id: "synthetic" }, profiles: [],
    codedb: { available: false, build: null, expectedBuild: "synthetic" } }, new Promise(() => {}), onCall);
  const call = async (id: string, op: string, requestId: unknown) => {
    const reply = once(frames, id);
    engine.receive({ t: "call", id, op, requestId, args: {} }, new Uint8Array());
    return (await reply)[0];
  };
  const finish = (id: string) => {
    engine.receive({ t: "start", id, status: 200, headers: [] }, new Uint8Array());
    engine.receive({ t: "body", id, more: false }, new Uint8Array());
  };
  return { engine, requests, frames, call, finish };
}

test("provider authority requires a live HTTP request, including every transfer operation and controls", async () => {
  const operations: string[] = [];
  const h = inMemoryEngine(async (op) => { operations.push(op); return { ok: true, value: {} }; });
  const completed = h.engine.request(request("/finished"));
  const finishedId = h.requests[0];
  h.finish(finishedId);
  await completed;
  const live = h.engine.request(request("/live"));
  const liveId = h.requests[1];
  void h.engine.control("profile");
  for (const [index, origin] of [undefined, null, 4, "unknown", "k3", finishedId].entries()) {
    for (const op of ["provider.profile", "provider.completeJson", "provider.jev", "provider.transfer.begin",
      "provider.transfer.chunk", "provider.transfer.finish", "provider.transfer.read"]) {
      const reply = await h.call(`denied-${index}-${op}`, op, origin);
      assert.equal(reply.ok, false, `${op} cannot use an unbound, control or completed origin`);
    }
  }
  assert.deepEqual(operations, []);
  assert.equal((await h.call("allowed", "provider.profile", liveId)).ok, true);
  assert.deepEqual(operations, ["provider.profile"]);
  h.finish(liveId);
  await live;
});

for (const ending of ["abort", "finish", "fail", "reader-cancel"]) {
  test(`request ${ending} aborts only its provider callback and rejects a late successful answer`, async () => {
    const entered = deferred();
    const release = deferred();
    const signals: AbortSignal[] = [];
    const h = inMemoryEngine(async (_op, _args, signal) => {
      signals.push(signal);
      entered.resolve();
      await release.promise;
      return { ok: true, value: { lease: "late-answer" } };
    });
    const abort = new AbortController();
    const original = h.engine.request(request("/origin"), abort.signal);
    const settled = original.catch((error: unknown) => error);
    const id = h.requests[0];
    if (ending === "reader-cancel") h.engine.receive({ t: "start", id, status: 200, headers: [] }, new Uint8Array());
    const late = h.call("held", "provider.profile", id);
    await entered.promise;
    const other = h.engine.request(request("/other"));
    const independent = h.call("independent", "provider.profile", h.requests[1]);
    assert.equal(signals.length, 2);
    if (ending === "abort") abort.abort();
    else if (ending === "finish") h.finish(id);
    else if (ending === "fail") h.engine.receive({ t: "fail", id, detail: "synthetic failure" }, new Uint8Array());
    else await (await original).body.cancel();
    assert.equal(signals[0].aborted, true);
    assert.equal(signals[1].aborted, false, "another live request keeps its callback");
    release.resolve();
    assert.equal((await late).ok, false, "a late profile cannot restore a finished request's authority");
    assert.equal((await independent).ok, true);
    h.finish(h.requests[1]);
    await Promise.all([settled, other]);
  });
}

async function fixtureEngine(t: Parameters<typeof scratch>[0], onCall: HostCall) {
  const markers = new EventEmitter();
  const command = pythonCommand(scratch(t), "local");
  const started = await startEngine({ ...command, args: ["-c", fixture] }, { onCall, log: (line) => {
    const prefix = "engine: request-lifetime: completed ";
    if (line.startsWith(prefix)) markers.emit(line.slice(prefix.length));
  } });
  assert.equal(started.kind, "ready");
  if (started.kind !== "ready") throw new Error("synthetic fixture failed to start");
  t.after(async () => { await started.engine.stop(); assert.equal(await started.engine.exited, 0); });
  return { engine: started.engine, markers };
}

const profile = { lease: "synthetic-lease", generation: "chatgpt", screening: true, billing: "subscription" };

for (const cancelled of [false, true]) {
  test(cancelled ? "cancelled Jev batches stop active and queued workers without disabling subsequent screening"
    : "optional Jev screening keeps its origin through real Judge worker threads", { timeout: 15_000 }, async (t) => {
    const firstWorkers = deferred();
    const release = deferred();
    const signals: AbortSignal[] = [];
    let phase = "origin";
    const calls: string[] = [];
    const rpc = new ProviderRpc(async (op, args, signal) => {
      if (op === "provider.profile") return { ok: true, value: profile };
      assert.equal(op, "provider.jev");
      assert.ok(typeof args === "object" && args !== null && "body" in args && typeof args.body === "string");
      const body = JSON.parse(args.body);
      calls.push(phase);
      if (phase === "origin") {
        signals.push(signal);
        if (signals.length === 2) firstWorkers.resolve();
        await release.promise;
      }
      return { ok: true, value: { status: 200, body: JSON.stringify({ model: "jev-1.13.0",
        answers: Object.fromEntries(Object.keys(body.questions).map((key) => [key, { type: "noul", noul: 0.7 }])),
        usage: { input_tokens: 7, output_tokens: 3 } }) } };
    }, (lease) => lease === profile.lease);
    const { engine, markers } = await fixtureEngine(t, rpc.call);
    t.after(() => release.resolve());
    const abort = new AbortController();
    const completed = once(markers, "origin");
    const pending = engine.request({ ...request("/api/screen"), query: "origin" }, abort.signal);
    const rejected = cancelled ? assert.rejects(pending, { name: "AbortError" }) : null;
    await firstWorkers.promise;
    if (cancelled) abort.abort();
    release.resolve();
    if (rejected) await rejected;
    else {
      const reply = await pending;
      const result = JSON.parse(await text(reply.body));
      assert.equal(reply.status, 200);
      assert.equal(result.threads.length, 2);
      assert.deepEqual(Object.values(result.scores), [0.7, 0.7, 0.7, 0.7]);
    }
    await completed;
    assert.equal(calls.filter((value) => value === "origin").length, cancelled ? 2 : 4);
    if (cancelled) assert.equal(signals.every((signal) => signal.aborted), true, "both active callbacks lose authority");
    phase = "fresh";
    const freshDone = once(markers, "fresh");
    const reply = await engine.request({ ...request("/api/screen"), query: "fresh" });
    assert.equal(reply.status, 200);
    assert.deepEqual(Object.values(JSON.parse(await text(reply.body)).scores), [0.7, 0.7, 0.7, 0.7]);
    await freshDone;
    assert.equal(calls.filter((value) => value === "fresh").length, 4);
  });
}

test("a cancelled chunked transfer cannot dispatch and a fresh large request preserves its bytes", { timeout: 15_000 }, async (t) => {
  const chunk = deferred();
  const release = deferred();
  const users: string[] = [];
  const rpc = new ProviderRpc(async (op, args) => {
    if (op === "provider.profile") return { ok: true, value: profile };
    assert.equal(op, "provider.completeJson");
    assert.ok(typeof args === "object" && args !== null && "user" in args && typeof args.user === "string");
    users.push(args.user);
    return { ok: true, value: { json: { facts: [] }, model: "gpt-6-luna", effort: "medium", usage: null } };
  }, (lease) => lease === profile.lease);
  let held = false;
  const { engine, markers } = await fixtureEngine(t, async (op, args, signal) => {
    if (op === "provider.transfer.chunk" && !held) { held = true; chunk.resolve(); await release.promise; }
    return rpc.call(op, args, signal);
  });
  t.after(() => release.resolve());
  const abort = new AbortController();
  const completed = once(markers, "origin");
  const pending = engine.request({ ...request("/api/large"), query: "origin" }, abort.signal);
  const rejected = assert.rejects(pending, { name: "AbortError" });
  await chunk.promise;
  abort.abort();
  release.resolve();
  await rejected;
  await completed;
  assert.equal(users.length, 0, "no finish can dispatch the cancelled transfer");
  const freshDone = once(markers, "fresh");
  const reply = await engine.request({ ...request("/api/large"), query: "fresh" });
  assert.equal(reply.status, 200);
  assert.deepEqual(JSON.parse(await text(reply.body)), { facts: [] });
  await freshDone;
  assert.deepEqual(users, ["éç".repeat(40_000)]);
});

test("generation and screening closures retain their origin across worker pools and later requests", { timeout: 15_000 }, async (t) => {
  const operations: string[] = [];
  const rpc = new ProviderRpc(async (op, args) => {
    if (op === "provider.profile") return { ok: true, value: profile };
    operations.push(op);
    if (op === "provider.jev") return { ok: true, value: { status: 200, body: JSON.stringify({ model: "jev-1.13.0",
      answers: { q: { type: "noul", noul: 0.7 } }, usage: { input_tokens: 7, output_tokens: 3 } }) } };
    assert.equal(op, "provider.completeJson");
    assert.ok(typeof args === "object" && args !== null && "model" in args && "effort" in args);
    return { ok: true, value: { json: {}, model: args.model, effort: args.effort, usage: null } };
  }, (lease) => lease === profile.lease);
  const { engine, markers } = await fixtureEngine(t, rpc.call);
  const send = async (path: string) => {
    const completed = once(markers, path);
    const reply = await engine.request({ ...request(`/api/${path}`), query: path });
    const result = JSON.parse(await text(reply.body));
    await completed;
    assert.equal(reply.status, 200);
    return result;
  };
  assert.deepEqual((await send("parallel")).results, ["ok", "ok", "ok", "ok"]);
  assert.equal(operations.length, 4);
  assert.deepEqual(await send("capture"), { captured: 4 });
  const before = operations.length;
  assert.deepEqual((await send("reuse")).results, ["closed", "closed", "closed", "closed"]);
  assert.equal(operations.length, before, "a fresh request cannot lend authority to completed-request closures");
  assert.deepEqual((await send("parallel")).results, ["ok", "ok", "ok", "ok"]);
});

for (const cancelled of [false, true]) {
  test(cancelled ? "an intake cancelled during profile acquisition cannot dispatch and a fresh request still works"
    : "the real intake route dispatches intake and synthetic PDF review", { timeout: 15_000 }, async (t) => {
    const userData = scratch(t);
    await mkdir(join(userData, "engine-home"));
    await writeFile(join(userData, "settings.json"), JSON.stringify({ version: 1, workspace: "local", devProfile: null,
      ai: { generation: "chatgpt", screening: true } }));
    const firstStatus = deferred();
    const releaseStatus = deferred();
    const completed = deferred();
    const freshCompleted = deferred();
    const abort = new AbortController();
    let statusCount = 0;
    let phase = "origin";
    const calls: { phase: string; task: string; signal: AbortSignal }[] = [];
    const vault = new KeyVault(join(userData, "providers"), {
      available: async () => false, encrypt: async () => { throw new Error("credential access forbidden"); },
    });
    vault.status = async () => {
      if (++statusCount === 1) { firstStatus.resolve(); await releaseStatus.promise; }
      return "saved";
    };
    const provider: HostProvider = {
      ...unavailableProvider(), workflowReadiness: async () => ({ ready: true }),
      completeJson: async (request, signal) => {
        calls.push({ phase, task: request.task, signal });
        const json = request.task === "document-review"
          ? { documents: [], flags: [], facts: [], conflicts: [], provisions: [], missing: [], questions: [] }
          : { facts: [] };
        return { ok: true, json, model: request.model, effort: request.effort, usage: null };
      },
    };
    const host = new DesktopHost({
      paths: { userData, resources: REPO, packaged: false, platform: process.platform }, version: "offline-test",
      command: (kind) => ({ ...pythonCommand(userData, kind), args: ["-c", fixture] }),
      vault, provider, localSession: { load: async () => "s".repeat(43), save: async () => {} },
      log: (line) => {
        if (line === "engine: request-lifetime: completed origin") completed.resolve();
        if (line === "engine: request-lifetime: completed fresh") freshCompleted.resolve();
      },
      remount: () => {}, notify: () => {},
    });
    t.after(async () => { releaseStatus.resolve(); await host.dispose(); });
    await host.boot();
    const gate = host.gate(host.generation);
    assert.equal(gate.kind, "open");
    if (gate.kind !== "open") return;
    const engine = gate.engine;
    const api = withProviderCancellation(createAppProtocol({ distDir: userData, gate: () => host.gate(host.generation) }),
      (kind) => kind === "identity" ? host.prepareSessionChange() : host.cancelAI());
    const intake = (tag: string, signal?: AbortSignal) => api(new Request(`batatis://app/api/cases/case_synthetic/intake?${tag}`, {
      method: "POST", signal, headers: { "content-type": "application/json" },
      body: JSON.stringify({ text: "A synthetic novel wall is proposed.", file_ids: ["file_synthetic"] }),
    }));
    const pending = intake("origin", abort.signal).then(async (response) => ({ status: response.status, body: await response.text() }));
    const rejected = cancelled ? assert.rejects(pending, { name: "AbortError" }) : null;
    await firstStatus.promise;
    if (cancelled) abort.abort();
    releaseStatus.resolve();
    if (rejected) await rejected;
    else assert.equal((await pending).status, 200);
    await completed.promise;
    assert.deepEqual(calls.filter((call) => call.phase === "origin").map((call) => call.task),
      cancelled ? [] : ["intake", "intake", "document-review"], "a cancelled worker cannot reacquire provider authority");
    assert.equal(engine.busy, 0);
    phase = "fresh";
    assert.equal((await intake("fresh")).status, 200);
    await freshCompleted.promise;
    assert.deepEqual(calls.filter((call) => call.phase === "fresh").map((call) => call.task), ["intake", "intake", "document-review"]);
    await host.dispose();
    assert.equal(await engine.exited, 0, "the owned synthetic bridge exits cleanly");
  });
}
