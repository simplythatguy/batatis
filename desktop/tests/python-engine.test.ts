/** The host against the real engine of this checkout: no socket, the engine's own access rules. */
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";
import { DesktopHost } from "../src/main/controller.ts";
import { KeyVault } from "../src/main/credentials.ts";
import { createAppProtocol } from "../src/main/protocol.ts";
import { unavailableProvider } from "../src/main/providers.ts";
import { developmentPython, engineCommand } from "../src/main/runtime.ts";
import { SealedTokenStore } from "../src/main/session.ts";
import { pythonPaths, REPO, scratch } from "./helpers.ts";

const python = developmentPython(REPO, process.env);
const skip = existsSync(python) ? false : `no Python environment for ${REPO}`;
const box = { available: async () => true, encrypt: async (s: string) => Buffer.from(s).map((b) => b ^ 0x33), decrypt: async (b: Buffer) => Buffer.from(b.map((x) => x ^ 0x33)).toString() };

function host(userData: string) {
  const paths = pythonPaths(userData);
  const desktop = new DesktopHost({
    paths, version: "test",
    command: (kind) => engineCommand(paths, kind, process.env),
    vault: new KeyVault(join(userData, "providers"), box),
    localSession: new SealedTokenStore(join(userData, "workspaces", "local", "session.bin"), box),
    provider: unavailableProvider(), log: () => {}, remount: () => {}, notify: () => {},
  });
  const api = createAppProtocol({ distDir: join(REPO, "web", "dist"), gate: () => desktop.gate(desktop.generation) });
  return { desktop, api };
}

const json = (body: unknown, method = "POST") => ({ method, body: JSON.stringify(body), headers: { "content-type": "application/json" } });

test("Local development signs in its test people through the engine's own sessions", { skip }, async (t) => {
  const { desktop, api } = host(scratch(t));
  t.after(() => desktop.dispose());
  await desktop.switchWorkspace("dev");
  const info = desktop.info();
  assert.deepEqual(info.people.map((p) => p.profile), ["applicant", "reviewer:calgary", "reviewer:edmonton"]);
  const me = await (await api(new Request("batatis://app/api/auth/me"))).json();
  assert.equal(me.user.role, "applicant");
  assert.equal((await api(new Request("batatis://app/api/auth/onboarding", json({ role: "reviewer", authority: "calgary" })))).status, 403);

  assert.deepEqual(await desktop.switchPerson("reviewer:edmonton"), { ok: true });
  const reviewer = await (await api(new Request("batatis://app/api/auth/me"))).json();
  assert.deepEqual([reviewer.user.role, reviewer.user.authority], ["reviewer", "edmonton"]);
  assert.notEqual(reviewer.user.id, me.user.id);
  const queue = await (await api(new Request("batatis://app/api/review/queue"))).json();
  assert.deepEqual(queue.applications, []);
  assert.equal(queue.reviewer_id, reviewer.user.id);
});

test("the normal workspace keeps a real sign-in across a restart, sealed by the OS", { skip }, async (t) => {
  const userData = scratch(t);
  const first = host(userData);
  await first.desktop.boot();
  assert.equal((await first.api(new Request("batatis://app/api/auth/me"))).status, 401);
  const signup = await first.api(new Request("batatis://app/api/auth/signup", json({ name: "Local Applicant", email: "local@example.test", password: "correct horse battery" })));
  assert.equal(signup.status, 201);
  assert.equal(signup.headers.get("set-cookie"), null);
  assert.equal((await first.api(new Request("batatis://app/api/auth/me"))).status, 200);
  await first.desktop.dispose();

  const second = host(userData);
  t.after(() => second.desktop.dispose());
  await second.desktop.boot();
  const me = await (await second.api(new Request("batatis://app/api/auth/me"))).json();
  assert.equal(me.user.email, "local@example.test");
  assert.equal((await second.api(new Request("batatis://app/api/auth/logout", json({})))).status, 204);
  assert.equal(existsSync(join(userData, "workspaces", "local", "session.bin")), false, "sign-out removes the sealed session");
});

test("identify events arrive one by one and PDF bytes survive the private pipe", { skip }, async (t) => {
  const { desktop, api } = host(scratch(t));
  t.after(() => desktop.dispose());
  await desktop.boot();
  const created = await (await api(new Request("batatis://app/api/cases", json({ title: "Pipe test" })))).json();
  const stream = await api(new Request(`batatis://app/api/cases/${created.id}/identify`, {
    method: "POST", body: JSON.stringify({ prose: "A deck guard 900 mm high instead of 1070 mm." }),
    headers: { "content-type": "application/json", accept: "text/event-stream" },
  }));
  assert.equal(stream.status, 200);
  const reader = stream.body!.getReader();
  const first = new TextDecoder().decode((await reader.read()).value);
  assert.match(first, /^event: start/, "the first event is read before the run ends");
  let rest = "";
  for (;;) {
    const step = await reader.read();
    if (step.done) break;
    rest += new TextDecoder().decode(step.value);
  }
  assert.match(rest, /event: (done|error)/);

  const pdf = new Uint8Array(300_000).map((_, i) => (i * 7) % 256);
  pdf.set(new TextEncoder().encode("%PDF-1.4\n"), 0);
  const form = new FormData();
  form.append("file", new File([pdf], "plan.pdf", { type: "application/pdf" }));
  const uploaded = await api(new Request(`batatis://app/api/cases/${created.id}/files`, { method: "POST", body: form }));
  assert.equal(uploaded.status, 201);
  const saved = await uploaded.json();
  const download = await api(new Request(`batatis://app/api/cases/${created.id}/files/${saved.id}`));
  assert.deepEqual(new Uint8Array(await download.arrayBuffer()), pdf);
  assert.equal((await api(new Request(`batatis://app/api/cases/${created.id}`, { method: "DELETE" }))).status, 204);
});
