import assert from "node:assert/strict";
import { mkdirSync, symlinkSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";
import { EngineFailed, EngineLost, type EngineReply, type EngineRequest } from "../src/main/engine.ts";
import { BODY_LIMIT, createAppProtocol, CSP, type ApiGate } from "../src/main/protocol.ts";
import { SessionJar } from "../src/main/session.ts";
import { scratch } from "./helpers.ts";

const TOKEN = `tok_${"0123456789".repeat(3)}abcdefghi`;
const NEXT = "N".repeat(43);

function site(t: { after(fn: () => void): void }) {
  const root = scratch(t);
  const dist = join(root, "dist");
  mkdirSync(join(dist, "assets"), { recursive: true });
  writeFileSync(join(dist, "index.html"), "<!doctype html><div id=root></div>");
  writeFileSync(join(dist, "assets", "app.js"), "console.log(1)");
  writeFileSync(join(root, "secret.txt"), "outside the app");
  symlinkSync(join(root, "secret.txt"), join(dist, "assets", "link.txt"));
  return { root, dist };
}

function engine(reply: (request: EngineRequest) => EngineReply | Promise<EngineReply>) {
  const seen: EngineRequest[] = [];
  return {
    seen,
    request: async (request: EngineRequest) => {
      seen.push(request);
      return reply(request);
    },
  };
}

const body = (value: string) => new Response(value).body!;
const ok = (headers: [string, string][] = [], status = 200, payload = "{}"): EngineReply => ({ status, headers, body: body(payload) });

test("the app page is served from the build with a strict content security policy", async (t) => {
  const { dist } = site(t);
  const handle = createAppProtocol({ distDir: dist, gate: () => ({ kind: "closed", detail: "x" }) });
  const page = await handle(new Request("batatis://app/"));
  assert.equal(page.status, 200);
  assert.equal(page.headers.get("content-security-policy"), CSP);
  assert.match(CSP, /script-src 'self'(;|$)/);
  assert.doesNotMatch(CSP, /unsafe-eval|unsafe-inline|https?:/);
  assert.equal(await (await handle(new Request("batatis://app/assets/app.js"))).text(), "console.log(1)");
  for (const path of ["/assets/../../secret.txt", "/%2e%2e/secret.txt", "/assets/link.txt", "/assets/missing.js", "/..%5csecret.txt"]) {
    assert.equal((await handle(new Request(`batatis://app${path}`))).status, 404, path);
  }
  assert.equal((await handle(new Request("batatis://elsewhere/index.html"))).status, 404);
});

test("only the listed headers reach the engine, and the host adds its own session cookie", async (t) => {
  const { dist } = site(t);
  const jar = new SessionJar(TOKEN);
  const fake = engine(() => ok());
  const handle = createAppProtocol({ distDir: dist, gate: () => ({ kind: "open", engine: fake, jar }) });
  await handle(new Request("batatis://app/api/cases?x=1", {
    method: "POST", body: '{"a":1}',
    headers: { "content-type": "application/json", accept: "application/json", cookie: "batatis_session=forged", "x-forwarded-for": "10.0.0.1", "x-dev-role": "reviewer", authorization: "Bearer x" },
  }));
  const [sent] = fake.seen;
  assert.equal(sent.method, "POST");
  assert.equal(sent.path, "/api/cases");
  assert.equal(sent.query, "x=1");
  assert.equal(Buffer.from(sent.body).toString(), '{"a":1}');
  assert.deepEqual(sent.headers, [["accept", "application/json"], ["content-type", "application/json"], ["cookie", `batatis_session=${TOKEN}`]]);
});

test("Set-Cookie is kept by the host and never reaches the page", async (t) => {
  const { dist } = site(t);
  const jar = new SessionJar();
  const handle = createAppProtocol({ distDir: dist, gate: () => ({ kind: "open", engine: engine(() => ok([["set-cookie", `batatis_session=${NEXT}; HttpOnly; Path=/`], ["x-batatis-notice", "notice"]])), jar }) });
  const response = await handle(new Request("batatis://app/api/auth/login", { method: "POST", body: "{}", headers: { "content-type": "application/json" } }));
  assert.equal(response.headers.get("set-cookie"), null);
  assert.equal(response.headers.get("x-batatis-notice"), "notice");
  assert.equal(jar.token, NEXT);
});

test("an answer to a request sent before a person switch cannot change the new session", async (t) => {
  const { dist } = site(t);
  const jar = new SessionJar(TOKEN);
  let release!: (reply: EngineReply) => void;
  const slow = engine(() => new Promise<EngineReply>((done) => { release = done; }));
  const handle = createAppProtocol({ distDir: dist, gate: () => ({ kind: "open", engine: slow, jar }) });
  const pending = handle(new Request("batatis://app/api/me/applications"));
  await new Promise((done) => setTimeout(done, 10));
  jar.replace(NEXT);
  release(ok([["set-cookie", `batatis_session=${TOKEN}; Max-Age=2592000`]]));
  await pending;
  assert.equal(jar.token, NEXT);
});

test("a closed gate, a lost engine and a failed answer are honest errors, never a retry", async (t) => {
  const { dist } = site(t);
  const jar = new SessionJar();
  let calls = 0;
  const gates: Record<string, ApiGate> = {
    closed: { kind: "closed", detail: "Switching person…" },
    lost: { kind: "open", jar, engine: engine(() => { calls += 1; throw new EngineLost("gone"); }) },
    failed: { kind: "open", jar, engine: engine(() => { calls += 1; throw new EngineFailed("boom"); }) },
  };
  const expect: Record<string, number> = { closed: 503, lost: 503, failed: 502 };
  for (const [name, gate] of Object.entries(gates)) {
    const handle = createAppProtocol({ distDir: dist, gate: () => gate });
    const response = await handle(new Request("batatis://app/api/cases", { method: "POST", body: "{}" }));
    assert.equal(response.status, expect[name], name);
    assert.equal(typeof (await response.json()).detail, "string");
  }
  assert.equal(calls, 2, "each request reached the engine at most once");
});

test("bodies over the engine's limit, unknown methods and empty statuses are handled at the edge", async (t) => {
  const { dist } = site(t);
  const fake = engine(() => ({ status: 204, headers: [], body: body("") }));
  const handle = createAppProtocol({ distDir: dist, gate: () => ({ kind: "open", engine: fake, jar: new SessionJar() }) });
  const tooBig = await handle(new Request("batatis://app/api/cases/c1/files", { method: "POST", body: new Uint8Array(BODY_LIMIT + 1) }));
  assert.equal(tooBig.status, 413);
  assert.equal(fake.seen.length, 0);
  const trace = await handle(new Request("batatis://app/api/cases", { method: "OPTIONS" }));
  assert.equal(trace.status, 405);
  const deleted = await handle(new Request("batatis://app/api/cases/c1", { method: "DELETE" }));
  assert.equal(deleted.status, 204);
  assert.equal(deleted.body, null);
});
