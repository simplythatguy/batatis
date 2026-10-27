import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, realpathSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";
import { opencodeProviderFactory, type OpencodeProviderOptions, type OpencodeSpawn } from "../src/main/opencode/provider.ts";
import { opencodePin } from "../src/main/opencode/release.ts";
import type { CompleteJsonRequest, ModelId, ReasoningEffort } from "../src/main/providers.ts";
import type { RuntimePin } from "../src/main/runtime-install.ts";
import { DESKTOP, scratch } from "./helpers.ts";

const FAKE = readFileSync(join(DESKTOP, "tests", "fixtures", "fake-opencode.cjs"));
const EXECUTABLE = process.platform === "win32" ? "opencode.exe" : "opencode";
const sha = (bytes: Buffer | string) => createHash("sha256").update(bytes).digest("hex");

const request: CompleteJsonRequest = {
  task: "intake",
  system: "Answer as JSON only.",
  user: "Is a ramp required?",
  schema: { type: "object", properties: { answer: { type: "string" } }, required: ["answer"], additionalProperties: false },
  model: "nemotron-3.5-super-vl-free" as ModelId,
  effort: "medium" as ReasoningEffort,
  maxOutputTokens: null,
};

const text = (value: string) => ({ type: "text", part: { type: "text", text: value } });
const finish = (input: number, output: number) => ({ type: "step_finish", part: { type: "step-finish", tokens: { input, output } } });
const failure = (type: string, message: string, status: number) => ({ type: "error", error: { type, message, status } });

function setup(t: { after(fn: () => Promise<void>): void }, events: unknown[] = [], extra: { kind?: "hang"; exitCode?: number } = {}, tamper = false, withKey?: OpencodeProviderOptions["withKey"]) {
  const dir = scratch(t);
  const root = join(dir, "install root");
  const folder = join(root, "runtime", "test-platform");
  mkdirSync(folder, { recursive: true });
  writeFileSync(join(folder, EXECUTABLE), tamper ? `${FAKE}\n// changed` : FAKE);
  const pin: RuntimePin = {
    version: "9.9.9", key: "test-platform", url: "https://github.com/anomalyco/opencode/releases/download/v9.9.9/x.zip",
    download: { asset: "x.zip", bytes: 1, sha256: sha("synthetic download"), member: EXECUTABLE }, executable: EXECUTABLE, executables: [sha(FAKE)],
  };
  writeFileSync(join(folder, "codex-runtime.json"), JSON.stringify({ version: "9.9.9", platform: "test-platform", archiveSha256: pin.download.sha256, executableSha256: sha(FAKE) }));
  const capture = join(dir, "capture.jsonl"), control = join(dir, "control.json");
  writeFileSync(capture, "");
  writeFileSync(control, JSON.stringify({ capture, completion: { events, ...extra } }));
  const children: ReturnType<OpencodeSpawn>[] = [];
  const fakeSpawn: OpencodeSpawn = (command, args, options) => {
    const child = spawn(process.execPath, [command, control, ...args], options);
    children.push(child);
    return child;
  };
  const context = { stateDir: join(dir, "state"), workDir: join(dir, "work"), resourcesDir: DESKTOP, appVersion: "0.1.0", log: () => {} };
  const environment: NodeJS.ProcessEnv = { HOME: dir, PATH: "/opt/evil/bin", LANG: "en_CA.UTF-8", OPENAI_API_KEY: "sk-secret", OPENCODE_API_KEY: "oc-secret", NODE_OPTIONS: "--require=/tmp/x.js" };
  const systemRoot = Object.entries(process.env).find(([name]) => name.toLowerCase() === "systemroot")?.[1];
  if (systemRoot) environment.SystemRoot = systemRoot;
  const provider = opencodeProviderFactory({ runtimeRoot: root, pin, spawn: fakeSpawn, environment, completionMs: 5000, withKey })(context);
  t.after(async () => {
    await provider.dispose();
    for (const child of children) assert.ok(child.exitCode !== null || child.signalCode !== null, "every fake child exited");
  });
  const captured = () => readFileSync(capture, "utf8").split("\n").filter(Boolean).map((line) => JSON.parse(line) as { cwd: string; args: string[]; config: string; env: Record<string, string> });
  return { provider, dir, captured };
}

test("the pin names OpenCode 2.2.0 per platform and nothing for Linux", () => {
  const expected: [NodeJS.Platform, string, string, number][] = [
    ["darwin", "arm64", "opencode-darwin-arm64.zip", 102507526],
    ["darwin", "x64", "opencode-darwin-x64.zip", 107678260],
    ["win32", "x64", "opencode-windows-x64.zip", 118610002],
    ["win32", "arm64", "opencode-windows-arm64.zip", 112077419],
  ];
  for (const [platform, arch, asset, bytes] of expected) {
    const pin = opencodePin(platform, arch);
    assert.equal(pin?.url, `https://github.com/anomalyco/opencode/releases/download/v2.2.0/${asset}`);
    assert.equal(pin?.download.bytes, bytes);
    assert.equal(pin?.download.member, platform === "win32" ? "opencode.exe" : "opencode");
    assert.equal(pin?.executables.length, 1);
  }
  assert.equal(opencodePin("linux", "x64"), null);
  assert.equal(opencodePin("win32", "toString"), null);
});

test("a verified install is a ready connection with no sign-in, and a changed executable is not", async (t) => {
  const ok = setup(t);
  assert.deepEqual(await ok.provider.status(), { state: "signed-in", plan: "Free models" });
  assert.deepEqual(await ok.provider.workflowReadiness(), { ready: true });
  assert.deepEqual(await ok.provider.logout(), { state: "signed-in", plan: "Free models" });
  const changed = setup(t, [], {}, true);
  assert.equal((await changed.provider.status()).state, "unavailable");
  assert.equal((await changed.provider.workflowReadiness()).ready, false);
  const refused = await changed.provider.completeJson(request, new AbortController().signal);
  assert.deepEqual([refused.ok, !refused.ok && refused.reason], [false, "unavailable"]);
});

test("a completion runs the pinned model in a locked-down private home and returns the checked JSON with its usage", async (t) => {
  const f = setup(t, [text('```json\n{"answer":"yes"}\n```'), finish(12, 5)]);
  const result = await f.provider.completeJson(request, new AbortController().signal);
  assert.deepEqual(result, { ok: true, json: { answer: "yes" }, model: request.model, effort: "medium", usage: { inputTokens: 12, outputTokens: 5 } });
  const [run] = f.captured();
  assert.deepEqual(run.args, ["run", "--standalone", "--agent", "batatis", "--format", "json", "-m", "opencode/nemotron-3.5-super-vl-free", "Is a ramp required?"]);
  const config = JSON.parse(run.config);
  assert.deepEqual([config.permission, config.share, config.autoupdate], [{ "*": "deny" }, "disabled", false]);
  assert.match(config.agent.batatis.prompt, /^Answer as JSON only\./);
  assert.match(config.agent.batatis.prompt, /"required":\["answer"\]/);
  assert.equal(run.env.OPENAI_API_KEY, undefined);
  assert.equal(run.env.OPENCODE_API_KEY, undefined);
  assert.equal(run.env.NODE_OPTIONS, undefined);
  assert.ok(run.env.HOME.startsWith(join(f.dir, "state")), "OpenCode's own settings and history stay out of the person's home");
  assert.equal(run.cwd, realpathSync(join(f.dir, "work")));
});

test("a failed or malformed answer maps to the reason the person can act on", async (t) => {
  const cases: [unknown[], string][] = [
    [[failure("provider.free-limit", "Free usage limit reached.", 429)], "quota"],
    [[failure("provider.invalid-request", "Upstream request failed: Model is unavailable.", 400)], "model_unavailable"],
    [[failure("provider.invalid-request", "Bad key", 401)], "auth"],
    [[failure("unknown", "boom", 500)], "runtime"],
    [[text("I think the ramp is required.")], "refused_or_invalid"],
    [[text('{"answer": 3}')], "refused_or_invalid"],
    [[], "refused_or_invalid"],
  ];
  for (const [events, reason] of cases) {
    const result = await setup(t, events).provider.completeJson(request, new AbortController().signal);
    assert.deepEqual([result.ok, !result.ok && result.reason], [false, reason], JSON.stringify(events));
  }
});

test("only the listed models and the one effort are accepted", async (t) => {
  const f = setup(t, [text('{"answer":"yes"}')]);
  const ultra = await f.provider.completeJson({ ...request, model: "nemotron-3-ultra-free" as ModelId }, new AbortController().signal);
  assert.deepEqual([ultra.ok, !ultra.ok && ultra.reason], [false, "model_unavailable"]);
  const high = await f.provider.completeJson({ ...request, effort: "high" as ReasoningEffort }, new AbortController().signal);
  assert.deepEqual([high.ok, !high.ok && high.reason], [false, "model_unavailable"]);
  assert.equal(f.captured().length, 0, "nothing was started");
  assert.deepEqual((await f.provider.models()).map((m) => m.id), ["nemotron-3.5-super-vl-free", "nemotron-3.5-lightning-free"]);
});

test("cancelling stops the running child", async (t) => {
  const f = setup(t, [], { kind: "hang" });
  const abort = new AbortController();
  const pending = f.provider.completeJson(request, abort.signal);
  while (f.captured().length === 0) await new Promise((done) => setTimeout(done, 20));
  abort.abort();
  const result = await pending;
  assert.deepEqual([result.ok, !result.ok && result.reason], [false, "cancelled"]);
});

test("the person's OpenCode key is handed to the runtime only for the request, and an answer that echoes it is discarded", async (t) => {
  const key = "oc-test";
  const withKey: OpencodeProviderOptions["withKey"] = (work) => work(key);
  const f = setup(t, [text('{"answer":"yes"}')], {}, false, withKey);
  assert.equal((await f.provider.completeJson(request, new AbortController().signal)).ok, true);
  const [run] = f.captured();
  assert.equal(run.env.OPENCODE_API_KEY, key);
  assert.ok(!run.config.includes(key) && !run.args.join(" ").includes(key), "the key is in the environment only");
  const leaky = setup(t, [text(`{"answer":"${key}"}`)], {}, false, withKey);
  const result = await leaky.provider.completeJson(request, new AbortController().signal);
  assert.deepEqual([result.ok, !result.ok && result.reason], [false, "runtime"]);
  const none = setup(t, [text('{"answer":"yes"}')], {}, false, (work) => work(null));
  await none.provider.completeJson(request, new AbortController().signal);
  assert.equal(none.captured()[0].env.OPENCODE_API_KEY, undefined, "no key, no variable");
});
