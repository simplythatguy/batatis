import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { appendFileSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { realpath } from "node:fs/promises";
import { join } from "node:path";
import test from "node:test";
import { claudeProviderFactory, type ClaudeProviderOptions, type ClaudeSpawn } from "../src/main/claude/provider.ts";
import { claudePin } from "../src/main/claude/release.ts";
import type { CompleteJsonRequest, ModelId, ReasoningEffort } from "../src/main/providers.ts";
import type { RuntimePin } from "../src/main/runtime-install.ts";
import { DESKTOP, scratch, waitFor } from "./helpers.ts";

const FAKE = readFileSync(join(DESKTOP, "tests", "fixtures", "fake-claude.cjs"));
const EXECUTABLE = process.platform === "win32" ? "claude.exe" : "claude";
const sha = (bytes: Buffer | string) => createHash("sha256").update(bytes).digest("hex");
const SECRETS = { ANTHROPIC_API_KEY: "sk-ant-secret", ANTHROPIC_AUTH_TOKEN: "auth-secret", CLAUDE_CODE_OAUTH_TOKEN: "oauth-secret", OPENAI_API_KEY: "sk-openai-secret", NODE_OPTIONS: "--require=/tmp/x.js" };
const URL_SHOWN = "https://claude.com/cai/oauth/authorize?code=true&client_id=c&state=s";

const request: CompleteJsonRequest = {
  task: "intake",
  system: "Answer as JSON only.",
  user: "Is a ramp required?\nSecond line.",
  schema: { type: "object", properties: { answer: { type: "string" } }, required: ["answer"], additionalProperties: false },
  model: "claude-haiku-5-5" as ModelId,
  effort: "low" as ReasoningEffort,
  maxOutputTokens: null,
};

interface Mode {
  login?: { url?: string; urlDelayMs?: number; decoy?: string; outcome?: "success" | "fail" | "hang"; delayMs?: number };
  completion?: { kind?: "hang"; output?: unknown; exitCode?: number };
}
interface Captured { pid: number; cwd: string; args: string[]; env?: Record<string, string>; stdin?: string }

function setup(t: { after(fn: () => Promise<void>): void }, mode: Mode = {}, signedIn: { loggedIn: boolean; authMethod: string } = { loggedIn: true, authMethod: "claude.ai" }, override: Partial<ClaudeProviderOptions> = {}) {
  const dir = scratch(t);
  const root = join(dir, "install root");
  const folder = join(root, "runtime", "test-platform");
  mkdirSync(folder, { recursive: true });
  const executable = join(folder, EXECUTABLE);
  writeFileSync(executable, FAKE);
  const pin: RuntimePin = {
    version: "9.9.9", key: "test-platform", url: "https://downloads.claude.ai/claude-code-releases/9.9.9/test-platform/claude",
    download: { asset: EXECUTABLE, bytes: FAKE.length, sha256: sha("synthetic download"), member: null }, executable: EXECUTABLE, executables: [sha(FAKE)],
  };
  writeFileSync(join(folder, "codex-runtime.json"), JSON.stringify({ version: "9.9.9", platform: "test-platform", archiveSha256: pin.download.sha256, executableSha256: sha(FAKE) }));
  const capture = join(dir, "capture.jsonl"), state = join(dir, "state.json"), control = join(dir, "control.json");
  writeFileSync(capture, "");
  writeFileSync(state, JSON.stringify(signedIn));
  writeFileSync(control, JSON.stringify({ ...mode, capture, state }));
  const commands: { command: string; args: readonly string[] }[] = [];
  const children: ReturnType<ClaudeSpawn>[] = [];
  const fakeSpawn: ClaudeSpawn = (command, args, options) => {
    commands.push({ command, args });
    const child = spawn(process.execPath, [command, control, ...args], options);
    children.push(child);
    return child;
  };
  const logs: string[] = [];
  const context = { stateDir: join(dir, "state"), workDir: join(dir, "work"), resourcesDir: DESKTOP, appVersion: "0.1.0", log: (line: string) => logs.push(line) };
  const environment: NodeJS.ProcessEnv = { HOME: dir, USER: "synthetic", PATH: "/opt/evil/bin", LANG: "en_CA.UTF-8", ...SECRETS };
  const systemRoot = Object.entries(process.env).find(([name]) => name.toLowerCase() === "systemroot")?.[1];
  if (systemRoot) environment.SystemRoot = systemRoot;
  const provider = claudeProviderFactory({
    runtimeRoot: root, pin, spawn: fakeSpawn, environment,
    timing: { completionMs: 5000, commandMs: 5000, loginMs: 5000, urlMs: 1000, stopMs: 200 }, ...override,
  })(context);
  t.after(async () => {
    await provider.dispose();
    for (const child of children) assert.ok(child.exitCode !== null || child.signalCode !== null, "every fake child exited");
  });
  const captured = (): Captured[] => readFileSync(capture, "utf8").split("\n").filter(Boolean).map((line) => JSON.parse(line));
  const running = (child: ReturnType<ClaudeSpawn>) => child.exitCode === null && child.signalCode === null;
  return { provider, dir, context, commands, children, captured, logs, executable, state, running };
}

const success = (structured: unknown = { answer: "yes" }, usage: unknown = { input_tokens: 12, output_tokens: 5, cache_read_input_tokens: 100 }) => ({
  completion: { output: { type: "result", subtype: "success", is_error: false, result: "", structured_output: structured, usage } },
});

test("the pin names Claude Code 2.1.309 per platform and nothing for Linux", () => {
  const expected: [NodeJS.Platform, string, number, string][] = [
    ["darwin", "arm64", 275923296, "5eadc0009cdcdbc0d06e58110d7b2baf88ced6088b1c33a60a21217fe410619c"],
    ["darwin", "x64", 287157296, "200e0d775ae55c040db3bb8db8de3e22efcddbd7e0abff5ab50dd10f6853425d"],
    ["win32", "x64", 298624160, "5441781f2b6bbd07354b4a74560ee88c68c9bf05d6db3c7e24c452c91673dc53"],
    ["win32", "arm64", 282697888, "063f45f61dca573b76e378f06728dc4e8f1b8600905dbd19be6d210f8c882501"],
  ];
  for (const [platform, arch, bytes, digest] of expected) {
    const name = platform === "win32" ? "claude.exe" : "claude";
    assert.deepEqual(claudePin(platform, arch), {
      version: "2.1.309", key: `${platform}-${arch}`, url: `https://downloads.claude.ai/claude-code-releases/2.1.309/${platform}-${arch}/${name}`,
      download: { asset: name, bytes, sha256: digest, member: null }, executable: name, executables: [digest],
    });
  }
  assert.equal(claudePin("linux", "x64"), null);
  assert.equal(claudePin("darwin", "ia32"), null);
  assert.equal(claudePin("win32", "toString"), null);
});

test("status is signed in only for a Claude subscription", async (t) => {
  assert.deepEqual(await setup(t).provider.status(), { state: "signed-in", plan: null });
  assert.deepEqual(await setup(t, {}, { loggedIn: false, authMethod: "none" }).provider.status(), { state: "signed-out", last: null });
  for (const authMethod of ["api_key", "oauth_token", "api_key_helper"]) {
    const { provider } = setup(t, {}, { loggedIn: true, authMethod });
    assert.deepEqual(await provider.status(), { state: "signed-out", last: null }, authMethod);
    assert.deepEqual(await provider.workflowReadiness(), { ready: false, reason: "signed-out", message: "Sign in to Claude to continue." });
  }
  assert.deepEqual(await setup(t).provider.workflowReadiness(), { ready: true });
});

test("the child gets a minimal environment with an app-owned config dir and no inherited secret", async (t) => {
  const f = setup(t);
  await f.provider.status();
  const [entry] = f.captured();
  const env = entry.env ?? {};
  const configDir = join(f.context.stateDir, "claude-config");
  assert.equal(env.CLAUDE_CONFIG_DIR, configDir);
  assert.equal(env.DISABLE_UPDATES, "1");
  assert.equal(env.DISABLE_AUTOUPDATER, "1");
  for (const name of Object.keys(env)) assert.doesNotMatch(name, /^ANTHROPIC_|^CLAUDE_CODE_OAUTH|^OPENAI_|^NODE_OPTIONS$/i);
  for (const value of Object.values(env)) for (const secret of Object.values(SECRETS)) assert.ok(!value.includes(secret));
  assert.notEqual(env.PATH, "/opt/evil/bin");
  if (process.platform !== "win32") {
    assert.equal(env.PATH, "/usr/bin:/bin:/usr/sbin:/sbin");
    assert.equal(env.HOME, f.dir);
    assert.equal(env.LANG, "en_CA.UTF-8");
    assert.equal(statSync(configDir).mode & 0o777, 0o700);
  }
  assert.equal(await realpath(entry.cwd), await realpath(f.context.workDir));
  assert.equal(f.commands[0].command, await realpath(f.executable));
  assert.deepEqual(f.commands[0].args, ["auth", "status", "--json"]);
});

test("a completion runs headless with no tools or customizations and the prompt on stdin", async (t) => {
  const f = setup(t, success());
  const result = await f.provider.completeJson(request, new AbortController().signal);
  assert.deepEqual(result, { ok: true, json: { answer: "yes" }, model: "claude-haiku-5-5", effort: "low", usage: { inputTokens: 12, outputTokens: 5 } });
  const run = f.captured().find((entry) => entry.args[0] === "-p");
  assert.ok(run);
  assert.deepEqual(run.args, [
    "-p", "--output-format", "json", "--json-schema", JSON.stringify(request.schema), "--tools", "", "--safe-mode",
    "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence",
    "--permission-mode", "dontAsk", "--system-prompt", "Answer as JSON only.", "--model", "claude-haiku-5-5", "--effort", "low",
  ]);
  assert.ok(!run.args.includes("--bare"));
  assert.equal(run.stdin, request.user);
  assert.ok(!run.args.some((arg) => arg.includes("ramp")), "the user prompt never goes on the command line");
  assert.ok(!f.logs.some((line) => /ramp|JSON only|yes/.test(line)));
});

test("usage is unknown rather than invented when the runtime omits or garbles it", async (t) => {
  for (const usage of [null, {}, { input_tokens: -1, output_tokens: 3 }, { input_tokens: 1.5, output_tokens: 3 }, "12"]) {
    const result = await setup(t, success({ answer: "a" }, usage)).provider.completeJson(request, new AbortController().signal);
    assert.equal(result.ok && result.usage, null);
  }
});

test("only the listed models and efforts run, and nothing starts otherwise", async (t) => {
  const f = setup(t, success());
  const models = await f.provider.models();
  assert.deepEqual(models.map((item) => [item.id, item.label, item.defaultEffort, item.structuredOutput]), [
    ["claude-haiku-5-5", "Haiku 5.5", "low", true], ["claude-sonnet-5-5", "Sonnet 5.5", "medium", true], ["claude-opus-5-5", "Opus 5.5", "medium", true],
  ]);
  for (const item of models) assert.deepEqual(item.efforts, ["low", "medium", "high"]);
  for (const [model, effort] of [["claude-fable-5-5", "low"], ["claude-haiku-5-5", "max"], ["gpt-6-luna", "medium"]]) {
    const result = await f.provider.completeJson({ ...request, model: model as ModelId, effort: effort as ReasoningEffort }, new AbortController().signal);
    assert.equal(!result.ok && result.reason, "model_unavailable");
  }
  assert.equal(f.commands.length, 0);
});

test("runtime errors map to fixed reasons without leaking runtime text", async (t) => {
  const cases: [unknown, number, string][] = [
    [{ type: "result", subtype: "success", is_error: true, result: "Not logged in · Please run /login" }, 1, "auth"],
    [{ type: "result", subtype: "success", is_error: true, api_error_status: 429, result: "You've hit your limit · resets 4pm" }, 1, "quota"],
    [{ type: "result", subtype: "error_max_structured_output_retries", is_error: true, errors: [] }, 1, "refused_or_invalid"],
    [{ type: "result", subtype: "error_during_execution", is_error: true, errors: ["boom secret-detail"] }, 1, "runtime"],
    [{ type: "result", subtype: "success", is_error: false, structured_output: { other: 1 } }, 0, "refused_or_invalid"],
    [{ type: "result", subtype: "success", is_error: false, structured_output: "text" }, 0, "refused_or_invalid"],
    ["not json", 0, "runtime"],
  ];
  for (const [output, exitCode, reason] of cases) {
    const f = setup(t, { completion: { output, exitCode } });
    const result = await f.provider.completeJson(request, new AbortController().signal);
    assert.equal(!result.ok && result.reason, reason, JSON.stringify(output));
    assert.ok(!result.ok && !/secret-detail|resets 4pm|Please run/.test(result.message));
    assert.ok(!f.logs.some((line) => /secret-detail|resets 4pm|Please run/.test(line)));
  }
});

test("a signed-out connection never starts a completion", async (t) => {
  const f = setup(t, success(), { loggedIn: true, authMethod: "api_key" });
  const result = await f.provider.completeJson(request, new AbortController().signal);
  assert.deepEqual(result, { ok: false, reason: "auth", message: "Sign in to Claude to continue." });
  assert.ok(!f.commands.some((command) => command.args[0] === "-p"));
});

test("the deadline and a cancel both stop the child", async (t) => {
  const timed = setup(t, { completion: { kind: "hang" } }, undefined, { timing: { completionMs: 400, commandMs: 5000, stopMs: 200 } });
  const late = await timed.provider.completeJson(request, new AbortController().signal);
  assert.equal(!late.ok && late.reason, "incomplete");
  assert.ok(timed.children.length === 2 && timed.children.every((child) => !timed.running(child)));

  const f = setup(t, { completion: { kind: "hang" } });
  const controller = new AbortController();
  const pending = f.provider.completeJson(request, controller.signal);
  await waitFor(() => f.captured().some((entry) => entry.args[0] === "-p"));
  controller.abort();
  const result = await pending;
  assert.deepEqual(result, { ok: false, reason: "cancelled", message: "The request was cancelled." });
  assert.ok(f.children.every((child) => !f.running(child)));
});

test("completions run one at a time and a queued one can be cancelled", async (t) => {
  const f = setup(t, { completion: { kind: "hang" } });
  const first = new AbortController(), second = new AbortController();
  const one = f.provider.completeJson(request, first.signal);
  const two = f.provider.completeJson(request, second.signal);
  await waitFor(() => f.captured().some((entry) => entry.args[0] === "-p"));
  second.abort();
  assert.equal((await two).ok, false);
  assert.equal(f.captured().filter((entry) => entry.args[0] === "-p").length, 1);
  first.abort();
  assert.equal(!(await one).ok && (await one as { reason: string }).reason, "cancelled");
});

test("sign-in is pending with the printed page, then signed in with a change event", async (t) => {
  const f = setup(t, { login: { url: URL_SHOWN, decoy: "https://evil.example/login?code=1", outcome: "success", delayMs: 400 } }, { loggedIn: false, authMethod: "none" });
  let changes = 0;
  f.provider.onChange(() => { changes++; });
  const pending = await f.provider.startLogin();
  assert.equal(pending.state, "pending");
  assert.ok(pending.state === "pending");
  assert.match(pending.loginId, /^[0-9a-f-]{36}$/);
  assert.equal(pending.verificationUrl, URL_SHOWN);
  assert.equal(pending.userCode, "");
  assert.deepEqual(await f.provider.status(), pending);
  assert.deepEqual(await f.provider.startLogin(), pending);
  assert.deepEqual(f.commands.find((command) => command.args[1] === "login")?.args, ["auth", "login", "--claudeai"]);
  await waitFor(() => changes > 0);
  assert.deepEqual(await f.provider.status(), { state: "signed-in", plan: null });
  assert.ok(!f.logs.some((line) => line.includes("oauth") || line.includes("evil")));
});

test("a code pasted from the sign-in page reaches the CLI once, and only for the pending sign-in", async (t) => {
  const code = "AbC123-xyz_789#State_456-def";
  const f = setup(t, { login: { url: URL_SHOWN, outcome: "code", code } }, { loggedIn: false, authMethod: "none" });
  let changes = 0;
  f.provider.onChange(() => { changes++; });
  const pending = await f.provider.startLogin();
  assert.ok(pending.state === "pending" && pending.acceptsCode);
  assert.deepEqual(await f.provider.submitLoginCode("someone-else", code), pending);
  assert.deepEqual(await f.provider.submitLoginCode(pending.loginId, "short"), pending);
  assert.deepEqual(await f.provider.submitLoginCode(pending.loginId, `${code}\nauth logout`), pending);
  await f.provider.submitLoginCode(pending.loginId, code);
  await waitFor(() => changes > 0);
  assert.deepEqual(await f.provider.status(), { state: "signed-in", plan: null });
  assert.ok(!f.logs.some((line) => line.includes(code)), "the code never reaches the log");
});

test("a page the CLI prints late still reaches the pending state", async (t) => {
  const f = setup(t, { login: { url: URL_SHOWN, urlDelayMs: 300, outcome: "hang" } }, { loggedIn: false, authMethod: "none" }, { timing: { urlMs: 50, stopMs: 200 } });
  let changes = 0;
  f.provider.onChange(() => { changes++; });
  const pending = await f.provider.startLogin();
  assert.ok(pending.state === "pending");
  assert.equal(pending.verificationUrl, "");
  await waitFor(() => changes > 0);
  assert.deepEqual(await f.provider.status(), { ...pending, verificationUrl: URL_SHOWN });
  await f.provider.cancelLogin(pending.loginId);
});

test("a failed sign-in reports fixed text", async (t) => {
  const f = setup(t, { login: { url: URL_SHOWN, outcome: "fail", delayMs: 100 } }, { loggedIn: false, authMethod: "none" });
  let changes = 0;
  f.provider.onChange(() => { changes++; });
  const pending = await f.provider.startLogin();
  assert.ok(pending.state === "pending");
  await waitFor(() => changes > 0);
  assert.deepEqual(await f.provider.status(), { state: "signed-out", last: { loginId: pending.loginId, result: "failed", message: "Claude sign-in didn’t finish. Try again." } });
});

test("cancelling sign-in stops the CLI and records the cancel", async (t) => {
  const f = setup(t, { login: { url: URL_SHOWN, outcome: "hang" } }, { loggedIn: false, authMethod: "none" });
  let changes = 0;
  f.provider.onChange(() => { changes++; });
  const pending = await f.provider.startLogin();
  assert.ok(pending.state === "pending");
  const login = f.children.at(-1)!;
  assert.ok(f.running(login), "the CLI keeps waiting while its input stays open");
  assert.deepEqual(await f.provider.cancelLogin("someone-else"), pending);
  const after = await f.provider.cancelLogin(pending.loginId);
  assert.deepEqual(after, { state: "signed-out", last: { loginId: pending.loginId, result: "cancelled" } });
  assert.ok(!f.running(login));
  assert.equal(changes, 1);
});

test("sign-in gives up at its cap", async (t) => {
  const f = setup(t, { login: { url: URL_SHOWN, outcome: "hang" } }, { loggedIn: false, authMethod: "none" }, { timing: { loginMs: 300, stopMs: 200 } });
  let changes = 0;
  f.provider.onChange(() => { changes++; });
  const pending = await f.provider.startLogin();
  assert.ok(pending.state === "pending");
  await waitFor(() => changes > 0);
  assert.deepEqual(await f.provider.status(), { state: "signed-out", last: { loginId: pending.loginId, result: "failed", message: "Claude sign-in timed out. Try again." } });
});

test("signing out runs the CLI's logout and reads status again", async (t) => {
  const f = setup(t);
  let changes = 0;
  f.provider.onChange(() => { changes++; });
  assert.deepEqual(await f.provider.logout(), { state: "signed-out", last: null });
  assert.ok(f.commands.some((command) => command.args.join(" ") === "auth logout"));
  assert.equal(changes, 1);
  assert.deepEqual(await f.provider.status(), { state: "signed-out", last: null });
});

test("a changed, missing or unmanifested executable is never started", async (t) => {
  const unavailable = { state: "unavailable", reason: "runtime-missing", message: "The verified local AI runtime isn’t installed." };
  const changed = setup(t, success());
  appendFileSync(changed.executable, "\n// tampered");
  assert.deepEqual(await changed.provider.status(), unavailable);
  assert.deepEqual(await changed.provider.workflowReadiness(), { ready: false, reason: "unavailable", message: unavailable.message });
  assert.deepEqual(await changed.provider.startLogin(), unavailable);
  const result = await changed.provider.completeJson(request, new AbortController().signal);
  assert.deepEqual(result, { ok: false, reason: "unavailable", message: unavailable.message });
  assert.equal(changed.commands.length, 0);

  const manifest = setup(t);
  writeFileSync(join(manifest.executable, "..", "codex-runtime.json"), JSON.stringify({ version: "9.9.8", platform: "test-platform" }));
  assert.deepEqual(await manifest.provider.status(), unavailable);

  const missing = setup(t, {}, undefined, { runtimeRoot: join(scratch(t), "nothing here") });
  assert.deepEqual(await missing.provider.status(), unavailable);

  const unsupported = setup(t, {}, undefined, { pin: null });
  assert.equal((await unsupported.provider.status()).state, "unavailable");
  assert.equal(missing.commands.length + manifest.commands.length + unsupported.commands.length, 0);
});

test("dispose stops a pending sign-in and a running completion", async (t) => {
  const f = setup(t, { login: { url: URL_SHOWN, outcome: "hang" }, completion: { kind: "hang" } });
  const login = setup(t, { login: { url: URL_SHOWN, outcome: "hang" } }, { loggedIn: false, authMethod: "none" });
  assert.equal((await login.provider.startLogin()).state, "pending");
  const pending = f.provider.completeJson(request, new AbortController().signal);
  await waitFor(() => f.captured().some((entry) => entry.args[0] === "-p"));
  await Promise.all([f.provider.dispose(), login.provider.dispose()]);
  assert.equal(!(await pending).ok && (await pending as { reason: string }).reason, "cancelled");
  for (const child of [...f.children, ...login.children]) assert.ok(!f.running(child));
});

test("status read again within a few seconds reuses the answer; sign-out reads afresh", async (t) => {
  const s = setup(t);
  assert.equal((await s.provider.status()).state, "signed-in");
  assert.equal((await s.provider.status()).state, "signed-in");
  assert.equal(s.commands.length, 1, "one CLI status check for two reads");
  writeFileSync(s.state, JSON.stringify({ loggedIn: false, authMethod: "none" }));
  assert.equal((await s.provider.logout()).state, "signed-out");
  assert.equal((await s.provider.status()).state, "signed-out");
});

test("an executable changed in place after a verified start is hashed again and refused", async (t) => {
  const s = setup(t);
  assert.equal((await s.provider.status()).state, "signed-in");
  appendFileSync(s.executable, "\n// tampered");
  await s.provider.logout().catch(() => undefined);
  const state = await s.provider.status();
  assert.equal(state.state, "unavailable");
  assert.equal(state.state === "unavailable" && state.reason, "runtime-missing");
});
