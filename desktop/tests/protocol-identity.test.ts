import assert from "node:assert/strict";
import test from "node:test";
import { BODY_LIMIT, createAppProtocol, type ApiGate } from "../src/main/protocol.ts";
import { SessionJar } from "../src/main/session.ts";
import { protocolHost } from "./fixtures/protocol-host.mjs";

const APPLICANT = "A".repeat(43), REVIEWER = "B".repeat(43);

function delayedBody() {
  const bytes = Promise.withResolvers<Uint8Array>();
  return {
    request: new Request("batatis://app/api/review/synthetic-case/claim", {
      method: "POST", headers: { "content-type": "application/json" }, duplex: "half",
      body: new ReadableStream({ async start(controller) { controller.enqueue(await bytes.promise); controller.close(); } }),
    }),
    finish: () => bytes.resolve(new TextEncoder().encode('{"claim":true}')),
  };
}

test("a delayed applicant body cannot reach the real host's old engine as the new reviewer", { timeout: 5000 }, async (t) => {
  const state = await protocolHost(t);
  const generation = state.host.generation;
  const before = state.host.gate(generation);
  assert.equal(before.kind, "open");
  if (before.kind !== "open") throw new Error("Host did not start");
  const epoch = before.jar.epoch;
  const api = createAppProtocol({ distDir: state.userData, gate: () => state.host.gate(generation) });
  const input = delayedBody();
  const pending = api(input.request);
  assert.equal(state.engines[0].busy, 0, "a body being read is outside the engine's drain");
  const switching = state.host.switchPerson("reviewer:calgary");
  await state.reviewerIssued;
  await Promise.resolve();
  assert.ok(before.jar.epoch > epoch, "the host replaced the same jar before yielding for settings I/O");
  assert.equal(before.jar.token, REVIEWER);
  assert.equal(state.host.gate(generation).kind, "closed");
  input.finish();
  const reply = await pending;
  await switching;
  assert.equal(reply.status, 503, JSON.stringify(state.requests));
  assert.deepEqual(state.requests, [], "no old body is dispatched under either identity");
  assert.equal(state.host.info().person?.profile, "reviewer:calgary");
});

for (const change of ["closed", "engine", "jar", "epoch", "cookie", "same gate object"] as const) {
  test(`a delayed body is refused when its ${change} changes before dispatch`, async () => {
    let calls = 0;
    const peer = { request: async () => { calls += 1; return { status: 200, headers: [], body: new Response("{}").body! }; } };
    const jar = new SessionJar(APPLICANT);
    const initial: ApiGate = { kind: "open", engine: peer, jar };
    let current: ApiGate = initial;
    const api = createAppProtocol({ distDir: "/unused", gate: () => current });
    const input = delayedBody();
    const pending = api(input.request);
    if (change === "closed") current = { kind: "closed", detail: "Switching person" };
    if (change === "engine") current = { ...initial, engine: { request: peer.request } };
    if (change === "jar") current = { ...initial, jar: new SessionJar(APPLICANT) };
    if (change === "epoch") jar.replace(APPLICANT);
    if (change === "cookie") await jar.apply([`batatis_session=${REVIEWER}`], jar.epoch);
    if (change === "same gate object") initial.jar = new SessionJar(REVIEWER);
    input.finish();
    assert.equal((await pending).status, 503);
    assert.equal(calls, 0, "a changed identity or engine never receives the earlier body");
  });
}

test("a stable delayed body reaches the engine exactly once with the original cookie and bytes", async (t) => {
  const state = await protocolHost(t);
  const api = createAppProtocol({ distDir: state.userData, gate: () => state.host.gate(state.host.generation) });
  const input = delayedBody();
  const pending = api(input.request);
  input.finish();
  assert.equal((await (await pending).json()).actor, "applicant");
  assert.deepEqual(state.requests, [{ path: "/api/review/synthetic-case/claim", actor: "applicant", body: '{"claim":true}' }]);
});

test("a late reply cannot persist a session after its gate or identity has changed", async () => {
  for (const change of ["closed", "engine", "jar", "epoch", "cookie"]) {
    const stored: (string | null)[] = [];
    const jar = new SessionJar(APPLICANT, { save: async (token) => { stored.push(token); } });
    const sent = Promise.withResolvers<void>();
    const answer = Promise.withResolvers<{ status: number; headers: [string, string][]; body: ReadableStream<Uint8Array> }>();
    const peer = { request: () => { sent.resolve(); return answer.promise; } };
    const initial: ApiGate = { kind: "open", engine: peer, jar };
    let current: ApiGate = initial;
    const api = createAppProtocol({ distDir: "/unused", gate: () => current });
    const pending = api(new Request("batatis://app/api/auth/me"));
    await sent.promise;
    if (change === "closed") current = { kind: "closed", detail: "Switching" };
    if (change === "engine") current = { ...initial, engine: { request: peer.request } };
    if (change === "jar") current = { ...initial, jar: new SessionJar(APPLICANT) };
    if (change === "epoch") jar.replace(REVIEWER);
    if (change === "cookie") await jar.apply([`batatis_session=${REVIEWER}`], jar.epoch);
    stored.length = 0;
    answer.resolve({ status: 200, headers: [["set-cookie", `batatis_session=${"C".repeat(43)}`]], body: new Response("{}").body! });
    const response = await pending;
    assert.equal(response.status, 200, "the earlier request may finish as its original person");
    assert.equal(response.headers.get("set-cookie"), null);
    assert.deepEqual(stored, [], change);
    assert.equal(jar.token, change === "epoch" || change === "cookie" ? REVIEWER : APPLICANT, change);
  }
});

test("the protocol still cancels real Engine streams on abort or reader cancellation", async (t) => {
  const state = await protocolHost(t);
  const api = createAppProtocol({ distDir: state.userData, gate: () => state.host.gate(state.host.generation) });
  for (const stop of ["signal", "reader"]) {
    const abort = new AbortController();
    const response = await api(new Request("batatis://app/api/stream", { signal: abort.signal }));
    const reader = response.body!.getReader();
    assert.equal(new TextDecoder().decode((await reader.read()).value), '{"actor":"applicant"}');
    const pending = reader.read();
    if (stop === "signal") {
      const rejected = assert.rejects(pending, { name: "AbortError" });
      abort.abort();
      await rejected;
    } else {
      await reader.cancel();
      assert.equal((await pending).done, true);
    }
    assert.equal(state.engines[0].busy, 0);
  }
  assert.equal(state.cancellations.length, 2, "one cancellation frame per stopped request");
  const abort = new AbortController();
  abort.abort();
  await assert.rejects(api(new Request("batatis://app/api/cases", { signal: abort.signal })), { name: "AbortError" });
  assert.equal(state.requests.length, 2, "a pre-aborted request never reaches the peer");
});

test("HEAD and empty response statuses discard the engine body without exposing session headers", async () => {
  for (const [method, status] of [["HEAD", 200], ["GET", 204], ["GET", 205], ["GET", 304]] as const) {
    let cancelled = 0;
    const jar = new SessionJar(APPLICANT);
    const peer = { request: async () => ({ status, headers: [["set-cookie", `batatis_session=${REVIEWER}`], ["x-batatis-notice", "kept"]],
      body: new ReadableStream<Uint8Array>({ cancel: () => { cancelled += 1; } }) }) };
    const api = createAppProtocol({ distDir: "/unused", gate: () => ({ kind: "open", engine: peer, jar }) });
    const response = await api(new Request("batatis://app/api/cases", { method }));
    assert.equal(response.status, status);
    assert.equal(response.body, null);
    assert.equal(cancelled, 1);
    assert.equal(response.headers.get("set-cookie"), null);
    assert.equal(response.headers.get("x-batatis-notice"), "kept");
    assert.equal(jar.token, REVIEWER);
  }
});

test("declared and streamed oversized bodies never dispatch, while the exact limit is accepted", async () => {
  let calls = 0;
  const jar = new SessionJar(APPLICANT);
  const peer = { request: async (request) => {
    calls += 1;
    assert.equal(request.body.length, BODY_LIMIT);
    return { status: 200, headers: [], body: new Response("{}").body! };
  } };
  const api = createAppProtocol({ distDir: "/unused", gate: () => ({ kind: "open", engine: peer, jar }) });
  const declared = new Request("batatis://app/api/cases", { method: "POST", body: "x", headers: { "content-length": String(BODY_LIMIT + 1) } });
  assert.equal((await api(declared)).status, 413);
  assert.equal((await api(new Request("batatis://app/api/cases", { method: "POST", body: new Uint8Array(BODY_LIMIT + 1) }))).status, 413);
  assert.equal(calls, 0);
  assert.equal((await api(new Request("batatis://app/api/cases", { method: "POST", body: new Uint8Array(BODY_LIMIT) }))).status, 200);
  assert.equal(calls, 1);
});
