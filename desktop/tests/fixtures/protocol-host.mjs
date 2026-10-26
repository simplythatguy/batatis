import assert from "node:assert/strict";
import { writeFile } from "node:fs/promises";
import { join } from "node:path";
import { PassThrough } from "node:stream";
import { DesktopHost } from "../../src/main/controller.ts";
import { Engine } from "../../src/main/engine.ts";
import { FrameDecoder } from "../../src/main/frames.ts";
import { unavailableProvider } from "../../src/main/providers.ts";
import { scratch } from "../helpers.ts";

const people = [
  { profile: "applicant", userId: "synthetic-applicant", kind: "applicant", name: "Test applicant", authority: null },
  { profile: "reviewer:calgary", userId: "synthetic-calgary", kind: "reviewer", name: "Test reviewer", authority: "calgary" },
];
const tokens = new Map(people.map((person, i) => [person.profile, String.fromCharCode(65 + i).repeat(43)]));

/** Real host and Engine framing, with a finite in-memory peer and synthetic credential operations. */
export async function protocolHost(t, events = []) {
  const cleanup = [];
  const userData = scratch({ after: (fn) => cleanup.push(fn) });
  await writeFile(join(userData, "settings.json"), JSON.stringify({ version: 1, workspace: "dev", devProfile: null }));
  const requests = [], remounts = [], engines = [], cancellations = [];
  const reviewerIssued = Promise.withResolvers();
  const provider = { ...unavailableProvider(), logout: async () => { events.push("provider:logout"); } };
  const host = new DesktopHost({
    paths: { userData, resources: userData, packaged: false, platform: process.platform },
    version: "protocol-test",
    command: (kind) => ({ command: "unused", args: [kind], env: {}, cwd: userData }),
    start: async (command) => {
      const engine = memoryEngine(command.args[0], requests, cancellations, reviewerIssued.resolve);
      engines.push(engine);
      return { kind: "ready", engine };
    },
    vault: {
      status: async () => "missing", use: async () => null,
      remove: async (id) => { events.push(`vault:remove:${id}`); },
      save: async (id) => { events.push(`vault:save:${id}`); return "saved"; },
    },
    localSession: { load: async () => null, save: async () => {} },
    provider, log: () => {}, notify: () => {},
    remount: (generation, route) => { remounts.push({ generation, route }); events.push("remount"); },
  });
  t.after(async () => { await host.dispose(); for (const fn of cleanup) fn(); });
  await host.boot();
  host.openWindow("#/settings");
  events.length = 0;
  return { host, requests, remounts, engines, cancellations, userData, reviewerIssued: reviewerIssued.promise };
}

function memoryEngine(kind, requests, cancellations, reviewerIssued) {
  const exit = Promise.withResolvers();
  const stdin = new PassThrough();
  const decoder = new FrameDecoder();
  const pending = new Map(), liveTokens = new Map();
  const engine = new Engine({ stdin, kill: () => exit.resolve(null) }, {
    workspace: { kind, id: `synthetic-${kind}` },
    codedb: { available: false, build: null, expectedBuild: "synthetic" },
    profiles: kind === "dev" ? people : [],
  }, exit.promise, async () => ({ ok: false, reason: "unavailable", message: "No provider in this test." }));
  stdin.on("data", (bytes) => {
    for (const { header, body } of decoder.push(bytes)) {
      if (header.t === "ctl" && header.op === "shutdown") exit.resolve(0);
      else if (header.t === "ctl" && header.op === "dev.session") {
        const token = tokens.get(header.args.profile);
        assert.ok(token);
        if (header.args.revoke) liveTokens.delete(header.args.revoke);
        liveTokens.set(token, header.args.profile);
        engine.receive({ t: "ctl.res", id: header.id, ok: true, value: { token } }, new Uint8Array());
        // The host awaits this synchronous control reply on the next microtask.
        if (header.args.profile === "reviewer:calgary") reviewerIssued();
      } else if (header.t === "req") pending.set(header.id, { ...header, parts: [] });
      else if (header.t === "body") {
        const request = pending.get(header.id);
        assert.ok(request);
        request.parts.push(body);
        if (header.more) continue;
        pending.delete(header.id);
        const cookie = request.headers.find(([name]) => name === "cookie")?.[1] ?? "";
        const actor = liveTokens.get(cookie.replace("batatis_session=", "")) ?? "unauthenticated";
        requests.push({ path: request.path, actor, body: Buffer.concat(request.parts).toString() });
        engine.receive({ t: "start", id: header.id, status: 200, headers: [["content-type", "application/json"]] }, new Uint8Array());
        engine.receive({ t: "body", id: header.id, more: request.path === "/api/stream" }, new TextEncoder().encode(JSON.stringify({ actor })));
      } else if (header.t === "cancel") cancellations.push(header.id);
      else assert.fail(`Unexpected frame ${header.t}`);
    }
  });
  return engine;
}
