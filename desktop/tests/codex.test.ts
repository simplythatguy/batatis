import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtemp, readFile, readdir, realpath, rm, writeFile } from "node:fs/promises";
import { homedir, tmpdir } from "node:os";
import { join, resolve } from "node:path";
import test from "node:test";
import { codexProviderFactory, CODEX_CONTEXT_FINGERPRINT, type CodexProviderOptions, type SpawnFn } from "../src/main/codex.ts";
import { EFFORT, MODEL, RUNTIME_ARGS, processConfig } from "../src/main/codex/config.ts";
import { bundledRuntime, childEnvironment, prepareHome } from "../src/main/codex/binary.ts";
import { CATALOG } from "../src/main/codex/release.ts";
import type { CompleteJsonRequest, HostProvider } from "../src/main/providers.ts";

const REPO = resolve(import.meta.dirname, "../..");
const RUNTIME_HASH = "f".repeat(64);
const request: CompleteJsonRequest = {
  task: "fixture", system: "Only the supplied workflow.\nExact SYSTEM bytes. 🥔", user: "Exact request bytes.\nÉcole plans.",
  schema: { type: "object", properties: { answer: { type: "string" } }, required: ["answer"], additionalProperties: false },
  model: MODEL, effort: EFFORT, maxOutputTokens: null,
};

const server = String.raw`
import { appendFileSync } from 'node:fs';
import { createInterface } from 'node:readline';
const mode = JSON.parse(process.argv[2]);
const capture = process.argv[3];
let signedIn = mode.signedIn !== false;
let thread = 0;
let currentThread = null;
let currentTurn = null;
let timers = [];
function send(value) {
  const line = Buffer.from(JSON.stringify(value) + (mode.crlf ? '\r\n' : '\n'));
  if (mode.fragment) {
    const index = Math.max(1, line.indexOf(Buffer.from('é')) + 1);
    process.stdout.write(line.subarray(0, index));
    process.stdout.write(line.subarray(index));
  } else process.stdout.write(line);
}
function reply(id, result) { send({id, result}); }
function notify(method, params) { send({method, params}); }
function later(fn, ms = 10) { timers.push(setTimeout(fn, ms)); }
const model = {id:'gpt-6-luna',model:'gpt-6-luna',displayName:'GPT-6 Luna',description:'é',hidden:false,isDefault:true,defaultReasoningEffort:'medium',supportedReasoningEfforts:[{reasoningEffort:'medium',description:'Medium'}]};
function finalItem(text = '{"answer":"accepted"}') { return {type:'agentMessage',id:'final-1',text,phase:'final_answer'}; }
function terminal(items, status='completed', error=null) { return {id:currentTurn,status,items,error,itemsView:'summary'}; }
const reader = createInterface({input:process.stdin,crlfDelay:Infinity});
reader.on('line', line => {
  const msg = JSON.parse(line);
  appendFileSync(capture, JSON.stringify(msg)+'\n');
  const p = msg.params;
  if (!msg.method) return;
  switch(msg.method) {
    case 'initialize':
      if (mode.badFrame === 'utf8') { process.stdout.write(Buffer.from([0xff,10])); return; }
      if (mode.badFrame === 'oversize') { process.stdout.write('x'.repeat(4*1024*1024+1)+'\n'); return; }
      if (mode.badFrame === 'json') { process.stdout.write('bad\n'); return; }
      if (mode.badFrame === 'unknown-id') { send({id:msg.id+1,result:{}}); return; }
      if (mode.badFrame === 'truncated') { process.stdout.write('{'); process.exit(0); }
      if (mode.badFrame === 'jsonrpc') { send({id:msg.id,jsonrpc:'2.0',result:{}}); return; }
      if (mode.hangInitialize) return;
      reply(msg.id, {codexHome:mode.wrongHome?'wrong':process.env.CODEX_HOME,platformFamily:'fixture',platformOs:'fixture',userAgent:'codex-fixture'});
      if (mode.nativeStartup) notify('remoteControl/status/changed',{status:mode.remoteEnabled?'connected':'disabled',serverName:'fixture',installationId:'fixture',environmentId:null});
      break;
    case 'initialized': break;
    case 'account/read':
      if (mode.readError) { send({id:msg.id,error:{code:-32000,message:mode.readError}}); break; }
      reply(msg.id,{account:signedIn?{type:mode.accountType||'chatgpt',planType:'plus',email:null}:null,requiresOpenaiAuth:true});
      break;
    case 'account/login/start': {
      if (mode.prerequisite) { send({id:msg.id,error:{code:-32000,message:'device-code sign-in disabled for workspace'}}); break; }
      const complete = () => {
        if (mode.loginSuccess !== false) signedIn = true;
        notify('account/login/completed',{loginId:'login-1',success:mode.loginSuccess!==false,error:mode.loginSuccess===false?'SENSITIVE RAW ERROR':null});
        notify('account/updated',{authMode:signedIn?'chatgpt':null,planType:signedIn?'plus':null});
      };
      if (mode.earlyLogin) complete();
      reply(msg.id,{type:mode.loginType||'chatgptDeviceCode',loginId:'login-1',verificationUrl:mode.badUrl?'https://evil.invalid/device':'https://auth.openai.com/codex/device',userCode:'ABCD-EFGH'});
      if (mode.foreignLogin) later(()=>notify('account/login/completed',{loginId:'foreign-login',success:true,error:null}));
      if (mode.autoLogin) later(complete,30);
      break;
    }
    case 'account/login/cancel':
      if (mode.cancelRace) signedIn = true;
      reply(msg.id,{status:mode.cancelRace?'notFound':'canceled'});
      break;
    case 'account/logout':
      signedIn = false;
      if (!mode.noLogoutNotice) notify('account/updated',{authMode:null,planType:null});
      reply(msg.id,{});
      break;
    case 'model/list':
      if (mode.modelCursor) { reply(msg.id,{data:[],nextCursor:'same'}); break; }
      if (mode.modelPages && !p.cursor) { reply(msg.id,{data:[],nextCursor:'next'}); break; }
      reply(msg.id,{data:mode.noModel?[]:[...(mode.nativeStartup?[{...model,id:'gpt-6.1-sol',model:'gpt-6.1-sol',supportedReasoningEfforts:[{reasoningEffort:'ultra',description:'Ultra'}]}]:[]),mode.wrongModel?{...model,model:'different'}:mode.noEffort?{...model,supportedReasoningEfforts:[]}:model],nextCursor:null});
      break;
    case 'configRequirements/read':
      reply(msg.id,mode.missingRequirements?{}:{requirements:mode.managed?{additionalDeveloperInstructions:'PRIVATE MANAGED TEXT'}:null});
      break;
    case 'thread/start':
      currentThread = 'thread-'+(++thread);
      reply(msg.id,{model:mode.substitute?'different':'gpt-6-luna',modelProvider:'openai',cwd:p.cwd,approvalPolicy:'never',approvalsReviewer:'user',sandbox:{type:'readOnly',networkAccess:false},reasoningEffort:'medium',instructionSources:mode.instructions?['PRIVATE AGENTS']:[],runtimeWorkspaceRoots:[],thread:{id:currentThread,cwd:p.cwd,ephemeral:true,model:'gpt-6-luna',modelProvider:'openai',reasoningEffort:'medium',environments:[],turns:[]}});
      if (mode.nativeStartup) {
        notify('deprecationNotice',{summary:'\x60[features].memory_tool\x60 is deprecated. Use \x60[features].memories\x60 instead.',details:'Enable it with \x60--enable memories\x60 or \x60[features].memories\x60 in config.toml. See https://developers.openai.com/codex/config-basic#feature-flags for details.'});
        notify('warning',{threadId:currentThread,message:'Under-development features enabled: skip_host_skill_discovery. Under-development features are incomplete and may behave unpredictably. To suppress this warning, set \x60suppress_unstable_features_warning = true\x60 in '+process.env.CODEX_HOME+(process.platform==='win32'?'\\':'/')+'config.toml.'});
      }
      if (mode.unknownWarning) notify('warning',{threadId:currentThread,message:'Unexpected configuration contribution'});
      break;
    case 'turn/start': {
      currentTurn = 'turn-'+thread;
      if (mode.exitTurn) { process.exit(7); }
      if (mode.unknownRequest) {
        send({id:'server-1',method:'item/tool/call',params:{threadId:currentThread,turnId:currentTurn}});
        return;
      }
      const run = () => {
        notify('turn/started',{threadId:currentThread,turn:terminal([],'inProgress')});
        if (mode.hangTurn) return;
        if (mode.unknownNotice) { notify('unexpected/tool',{threadId:currentThread,turnId:currentTurn}); return; }
        if (mode.reroute) { notify('model/rerouted',{threadId:currentThread,turnId:currentTurn,fromModel:'gpt-6-luna',toModel:'other'}); return; }
        const common = {threadId:currentThread,turnId:currentTurn,completedAtMs:0};
        if (mode.tool) { notify('item/completed',{...common,item:{type:'commandExecution',id:'tool-1'}}); return; }
        if (mode.quota || mode.authError) {
          const error = {message:'SENSITIVE RAW ERROR',codexErrorInfo:mode.quota?'usageLimitExceeded':'unauthorized'};
          notify('turn/completed',{threadId:currentThread,turn:terminal([],'failed',error)});
          return;
        }
        notify('item/completed',{...common,item:{type:'userMessage',id:'user-1',content:[{type:'text',text:mode.mutateUser?'changed':p.input[0].text}]}});
        if (mode.commentary) notify('item/completed',{...common,item:{type:'agentMessage',id:'comment-1',text:'{"answer":"commentary"}',phase:'commentary'}});
        const answer = finalItem(mode.text);
        if (mode.partial) answer.phase = 'partial_answer';
        if (mode.async) answer.delivery = 'async';
        if (mode.noPhase) delete answer.phase;
        if (!mode.noFinal) notify('item/completed',{...common,item:answer});
        if (mode.twoFinals) notify('item/completed',{...common,item:{...answer,id:'final-2'}});
        if (mode.usage) notify('thread/tokenUsage/updated',{...common,tokenUsage:{total:{inputTokens:50,outputTokens:15}}});
        if (mode.nonRetryError) notify('error',{...common,willRetry:false,error:{message:'RAW',codexErrorInfo:'unauthorized'}});
        const summary = mode.mismatch?{...answer,text:'{"answer":"different"}'}:answer;
        notify('turn/completed',{threadId:mode.wrongThread?'other-thread':currentThread,turn:terminal(mode.noFinal?[]:[summary],mode.interrupted?'interrupted':'completed')});
      };
      if (mode.earlyTurn) run();
      reply(msg.id,{turn:{...terminal([],'inProgress'),...(mode.nativeStartup?{itemsView:'notLoaded'}:{})}});
      if (!mode.earlyTurn) later(run);
      break;
    }
    case 'turn/interrupt':
      reply(msg.id,{});
      if (!mode.ignoreInterrupt) notify('turn/completed',{threadId:currentThread,turn:terminal([],'interrupted')});
      break;
    case 'thread/unsubscribe': reply(msg.id,{status:'unsubscribed'}); break;
    default: send({id:msg.id,error:{code:-32601,message:'unknown method'}});
  }
});
reader.on('close',()=>{
  for(const timer of timers) clearTimeout(timer);
  if (mode.ignoreEof) setInterval(()=>{},1000);
});
`;

async function setup(t: { after(fn: () => Promise<void>): void }, mode: Record<string, unknown> = {}, override: CodexProviderOptions = {}) {
  const dir = await mkdtemp(join(tmpdir(), "batatis-codex-école-"));
  const script = join(dir, "fake sidecar.mjs");
  const capture = join(dir, "capture.jsonl");
  await writeFile(script, server);
  await writeFile(capture, "");
  const context = { stateDir: join(dir, "private home"), workDir: join(dir, "empty work"), resourcesDir: REPO, appVersion: "0.1.0", log: (line: string) => logs.push(line) };
  const logs: string[] = [];
  const children: ReturnType<typeof spawn>[] = [];
  const commands: { command: string; args: readonly string[]; options: Parameters<SpawnFn>[2] }[] = [];
  const fakeSpawn: SpawnFn = (command, args, options) => {
    commands.push({ command, args, options });
    const child = spawn(process.execPath, [script, JSON.stringify(mode), capture], options);
    children.push(child);
    return child;
  };
  const provider = codexProviderFactory({
    runtime: async () => ({ executable: process.execPath, sha256: RUNTIME_HASH, catalog: await readFile(join(REPO, "desktop/codex/luna-models.json")) }),
    verifiedContext: { evidence: "offline fixture only", runtimeSha256: RUNTIME_HASH, contextFingerprint: CODEX_CONTEXT_FINGERPRINT },
    spawn: fakeSpawn, timing: { requestMs: 1000, completionMs: 2000, interruptMs: 100, stopMs: 50, loginMs: 5000 },
    ...override,
  })(context);
  t.after(async () => {
    await provider.dispose();
    for (const child of children) assert.ok(child.exitCode !== null || child.signalCode !== null, "owned fixture child exited");
    await rm(dir, { recursive: true, force: true });
  });
  const messages = async (): Promise<Record<string, unknown>[]> => (await readFile(capture, "utf8")).split("\n").filter(Boolean).map((line) => JSON.parse(line));
  return { provider, dir, context, commands, children, messages, logs };
}

async function waitFor(check: () => Promise<boolean>): Promise<void> {
  const end = Date.now() + 3000;
  while (!await check()) {
    if (Date.now() > end) throw new Error("Fixture deadline exceeded");
    await new Promise((done) => setTimeout(done, 10));
  }
}

async function complete(provider: HostProvider, value = request, signal = new AbortController().signal) { return provider.completeJson(value, signal); }

test("closed context gate performs no spawn or native account request", async (t) => {
  const fixture = await setup(t, {}, { verifiedContext: undefined });
  assert.equal((await complete(fixture.provider)).ok, false);
  assert.deepEqual(await fixture.provider.workflowReadiness(), { ready: false, reason: "context_unverified", message: "Application work is unavailable until this exact local runtime and context configuration are verified." });
  assert.equal(fixture.commands.length, 0);
});

test("private child, exact workflow, startup configuration, final JSON and unknown usage", async (t) => {
  const f = await setup(t, { commentary: true, crlf: true, fragment: true, earlyTurn: true, modelPages: true }, { environment: { ...process.env, OPENAI_API_KEY: "DO NOT INHERIT", CODEX_HOME: join(tmpdir(), "foreign-codex-home"), T3_SECRET: "PRIVATE" } });
  const result = await complete(f.provider);
  assert.deepEqual(result, { ok: true, json: { answer: "accepted" }, model: MODEL, effort: EFFORT, usage: null });
  const command = f.commands[0];
  const home = await realpath(f.context.stateDir);
  const cwd = await realpath(f.context.workDir);
  assert.deepEqual(command.args, RUNTIME_ARGS);
  assert.equal(command.options.shell, false);
  assert.deepEqual(command.options.stdio, ["pipe", "pipe", "ignore"]);
  assert.equal(command.options.env.OPENAI_API_KEY, undefined);
  assert.equal(command.options.env.T3_SECRET, undefined);
  assert.equal(command.options.env.CODEX_HOME, home);
  assert.equal(command.options.cwd, cwd);
  const config = await readFile(join(f.context.stateDir, "config.toml"), "utf8");
  assert.equal(config, processConfig(join(home, "luna-models.json")));
  assert.match(config, /cli_auth_credentials_store = "keyring"/);
  const messages = await f.messages();
  const thread = messages.find((message) => message.method === "thread/start");
  assert.deepEqual(thread?.params, { model: "gpt-6-luna", modelProvider: "openai", cwd, approvalPolicy: "never", approvalsReviewer: "user", sandbox: "read-only", baseInstructions: request.system, developerInstructions: "", ephemeral: true, dynamicTools: [], environments: [], runtimeWorkspaceRoots: [], selectedCapabilityRoots: [], allowProviderModelFallback: false });
  const turn = messages.find((message) => message.method === "turn/start");
  assert.deepEqual(turn?.params, { threadId: "thread-1", input: [{ type: "text", text: request.user }], model: "gpt-6-luna", effort: "medium", outputSchema: request.schema, environments: [], runtimeWorkspaceRoots: [] });
  assert.equal(messages.some((message) => /resume|fork|steer/.test(String(message.method))), false);
  assert.equal(f.logs.length, 0);
  assert.deepEqual(await readdir(f.context.workDir), []);
});

test("independent calls get new ephemeral threads and observed usage stays unpriced", async (t) => {
  const f = await setup(t, { usage: true, noPhase: true });
  for (let i = 0; i < 2; i++) {
    const result = await complete(f.provider);
    assert.equal(result.ok, true);
    if (result.ok) assert.deepEqual(result.usage, { inputTokens: 50, outputTokens: 15 });
  }
  const turns = (await f.messages()).filter((message) => message.method === "turn/start");
  assert.notDeepEqual(turns[0].params, turns[1].params);
});

test("observed native startup notices, catalog efforts and unloaded start view remain compatible", async (t) => {
  const f = await setup(t, { nativeStartup: true });
  assert.equal((await complete(f.provider)).ok, true);
});

test("device-only login waits for the correlated completion, ignores a stale login", async (t) => {
  const f = await setup(t, { signedIn: false, foreignLogin: true, autoLogin: true });
  let changed = 0;
  const unlisten = f.provider.onChange(() => changed++);
  const pending = await f.provider.startLogin();
  assert.deepEqual(pending, { state: "pending", loginId: "login-1", verificationUrl: "https://auth.openai.com/codex/device", userCode: "ABCD-EFGH" });
  assert.deepEqual(await f.provider.startLogin(), pending);
  await waitFor(async () => (await f.provider.status()).state === "signed-in");
  assert.ok(changed > 0);
  assert.deepEqual((await f.messages()).find((message) => message.method === "account/login/start")?.params, { type: "chatgptDeviceCode" });
  unlisten();
});

test("login notification arriving before the start response is correlated", async (t) => {
  const f = await setup(t, { signedIn: false, earlyLogin: true });
  assert.equal((await f.provider.startLogin()).state, "signed-in");
});

test("failed device login reports fixed text without exposing the server error", async (t) => {
  const f = await setup(t, { signedIn: false, autoLogin: true, loginSuccess: false });
  await f.provider.startLogin();
  await waitFor(async () => (await f.provider.status()).state === "signed-out");
  const state = await f.provider.status();
  assert.equal(state.state, "signed-out");
  if (state.state === "signed-out") assert.equal(state.last?.result, "failed");
  assert.equal(JSON.stringify(state).includes("SENSITIVE"), false);
});

test("device prerequisite and unsafe URL fail without a browser-flow fallback", async (t) => {
  const f = await setup(t, { signedIn: false, prerequisite: true });
  const state = await f.provider.startLogin();
  assert.equal(state.state, "signed-out");
  if (state.state === "signed-out") assert.equal(state.last?.result, "prerequisite");
  const bad = await setup(t, { signedIn: false, badUrl: true });
  assert.equal((await bad.provider.startLogin()).state, "error");
  assert.ok((await bad.messages()).some((message) => message.method === "account/login/cancel"));
});

test("cancel reports real account state when successful login wins the race", async (t) => {
  const f = await setup(t, { signedIn: false, cancelRace: true });
  await f.provider.startLogin();
  assert.equal((await f.provider.cancelLogin("login-1")).state, "signed-in");
});

test("logout requires RPC success, signed-out notification and account confirmation then stops child", async (t) => {
  const f = await setup(t);
  assert.equal((await f.provider.status()).state, "signed-in");
  assert.deepEqual(await f.provider.logout(), { state: "signed-out", last: null });
  assert.ok(f.children.every((child) => child.exitCode !== null || child.signalCode !== null));
  const missing = await setup(t, { noLogoutNotice: true }, { timing: { requestMs: 100, stopMs: 30 } });
  assert.equal((await missing.provider.logout()).state, "error");
});

for (const [mode, reason] of [
  [{ managed: true }, "context_unverified"], [{ instructions: true }, "context_unverified"],
  [{ missingRequirements: true }, "context_unverified"], [{ substitute: true }, "model_unavailable"],
  [{ wrongModel: true }, "model_unavailable"], [{ noModel: true }, "model_unavailable"], [{ noEffort: true }, "model_unavailable"],
  [{ accountType: "apiKey" }, "auth"], [{ signedIn: false }, "auth"], [{ tool: true }, "context_unverified"],
  [{ unknownRequest: true }, "context_unverified"], [{ unknownNotice: true }, "context_unverified"],
  [{ nativeStartup: true, remoteEnabled: true }, "context_unverified"], [{ unknownWarning: true }, "context_unverified"],
  [{ reroute: true }, "model_unavailable"], [{ mutateUser: true }, "context_unverified"], [{ async: true }, "context_unverified"],
  [{ partial: true }, "incomplete"], [{ noFinal: true }, "incomplete"], [{ twoFinals: true }, "incomplete"],
  [{ mismatch: true }, "incomplete"], [{ interrupted: true }, "incomplete"], [{ quota: true }, "quota"], [{ authError: true }, "auth"],
  [{ nonRetryError: true }, "auth"], [{ text: '{"answer":' }, "refused_or_invalid"],
  [{ text: '{"wrong":"value"}' }, "refused_or_invalid"], [{ text: 'I cannot help.' }, "refused_or_invalid"],
  [{ exitTurn: true }, "runtime"],
] satisfies [Record<string, unknown>, string][]) {
  test(`completion fails closed for ${JSON.stringify(mode)}`, async (t) => {
    const f = await setup(t, mode);
    const result = await complete(f.provider);
    assert.equal(result.ok, false);
    if (!result.ok) assert.equal(result.reason, reason);
    assert.equal(JSON.stringify(result).includes("SENSITIVE"), false);
    assert.equal(f.logs.some((line) => /PRIVATE|SENSITIVE/.test(line)), false);
    if (mode.unknownRequest) {
      await waitFor(async () => (await f.messages()).some((message) => message.id === "server-1"));
      const response = (await f.messages()).find((message) => message.id === "server-1");
      assert.deepEqual(response, { id: "server-1", error: { code: -32601, message: "This client does not support server requests." } });
    }
  });
}

for (const badFrame of ["utf8", "oversize", "json", "unknown-id", "truncated", "jsonrpc"]) {
  test(`invalid stdio framing is rejected (${badFrame})`, async (t) => {
    const f = await setup(t, { badFrame });
    assert.equal((await f.provider.status()).state, "error");
  });
}

test("model pagination cannot loop forever or silently select another model", async (t) => {
  const f = await setup(t, { modelCursor: true });
  assert.deepEqual(await f.provider.models(), []);
  assert.equal((await f.messages()).filter((message) => message.method === "model/list").length, 2);
});

test("caller cancellation interrupts the matching turn and discards late output", async (t) => {
  const f = await setup(t, { hangTurn: true });
  const abort = new AbortController();
  const result = complete(f.provider, request, abort.signal);
  await waitFor(async () => (await f.messages()).some((message) => message.method === "turn/start"));
  await new Promise((done) => setTimeout(done, 30));
  abort.abort();
  const value = await result;
  assert.equal(value.ok, false);
  if (!value.ok) assert.equal(value.reason, "cancelled");
  const interrupt = (await f.messages()).find((message) => message.method === "turn/interrupt");
  assert.deepEqual(interrupt?.params, { threadId: "thread-1", turnId: "turn-1" });
});

test("logout cancels running and queued workflows before confirming local sign-out", async (t) => {
  const f = await setup(t, { hangTurn: true });
  const first = complete(f.provider);
  const queued = complete(f.provider);
  await waitFor(async () => (await f.messages()).some((message) => message.method === "turn/start"));
  await new Promise((done) => setTimeout(done, 30));
  const logout = f.provider.logout();
  for (const result of await Promise.all([first, queued])) {
    assert.equal(result.ok, false);
    if (!result.ok) assert.equal(result.reason, "cancelled");
  }
  assert.deepEqual(await logout, { state: "signed-out", last: null });
  assert.equal((await f.messages()).filter((message) => message.method === "turn/start").length, 1);
});

test("the pending operation bound refuses excess requests and dispose drains them", async (t) => {
  const f = await setup(t, { hangInitialize: true }, { timing: { requestMs: 100, stopMs: 30 } });
  const pending = Array.from({ length: 16 }, () => f.provider.status());
  assert.ok((await Promise.all(pending)).every((state) => state.state === "error"));
  await f.provider.dispose();
});

test("deadline stops an uncooperative turn and dispose stops an EOF-resistant child", async (t) => {
  const f = await setup(t, { hangTurn: true, ignoreInterrupt: true, ignoreEof: true }, { timing: { completionMs: 150, interruptMs: 50, stopMs: 30 } });
  const result = await complete(f.provider);
  assert.equal(result.ok, false);
  if (!result.ok) assert.equal(result.reason, "incomplete");
  await f.provider.dispose();
  assert.ok(f.children.every((child) => child.exitCode !== null || child.signalCode !== null));
});

test("a workflow deadline includes time queued behind another completion", async (t) => {
  const f = await setup(t, { hangTurn: true }, { timing: { completionMs: 150, interruptMs: 50, stopMs: 30 } });
  const results = await Promise.all([complete(f.provider), complete(f.provider)]);
  for (const result of results) {
    assert.equal(result.ok, false);
    if (!result.ok) assert.equal(result.reason, "incomplete");
  }
  assert.equal((await f.messages()).filter((message) => message.method === "turn/start").length, 1);
});

test("mismatched context proof and request model cannot start a workflow", async (t) => {
  const f = await setup(t, {}, { verifiedContext: { evidence: "fixture", runtimeSha256: "0".repeat(64), contextFingerprint: CODEX_CONTEXT_FINGERPRINT } });
  const result = await complete(f.provider);
  if (!result.ok) assert.equal(result.reason, "context_unverified");
  assert.equal((await f.messages()).some((message) => message.method === "thread/start"), false);
  const wrong = await setup(t);
  const model = "different";
  const { isModelId } = await import("../src/main/providers.ts");
  assert.ok(isModelId(model));
  const rejected = await complete(wrong.provider, { ...request, model });
  if (!rejected.ok) assert.equal(rejected.reason, "model_unavailable");
  assert.equal(wrong.commands.length, 0);
});

test("invalid local schema and nonempty work directory never reach turn/start", async (t) => {
  const f = await setup(t);
  const invalid = await complete(f.provider, { ...request, schema: { type: "invalid" } });
  assert.equal(invalid.ok, false);
  assert.equal(f.commands.length, 0);
  await f.provider.status();
  await writeFile(join(f.context.workDir, "AGENTS.md"), "unwanted context");
  const blocked = await complete(f.provider);
  if (!blocked.ok) assert.equal(blocked.reason, "context_unverified");
  assert.equal((await f.messages()).some((message) => message.method === "thread/start"), false);
});

test("plaintext credentials in the private home are refused without being read", async (t) => {
  const f = await setup(t);
  await f.provider.status();
  await writeFile(join(f.context.stateDir, "auth.json"), "SENSITIVE NOT JSON");
  const state = await f.provider.status();
  assert.equal(state.state, "unavailable");
  if (state.state === "unavailable") assert.equal(state.reason, "keyring-unavailable");
  assert.equal(JSON.stringify(state).includes("SENSITIVE"), false);
});

test("catalog pin and binary digest reject altered resources before any execution", async (t) => {
  const f = await setup(t);
  const bytes = await readFile(join(REPO, "desktop/codex/luna-models.json"));
  assert.equal(bytes.length, CATALOG.bytes);
  assert.equal(createHash("sha256").update(bytes).digest("hex"), CATALOG.sha256);
  await assert.rejects(bundledRuntime({ executable: process.execPath })(f.context, "darwin", "arm64"), /verified local AI runtime is missing/);
  await assert.rejects(prepareHome({ ...f.context, stateDir: join(homedir(), ".codex") }, process.env, bytes), /exact local runtime/);
});

test("environment allow-list drops provider, proxy, agent and inherited path variables", () => {
  const source = { HOME: "/private/person", USER: "person", PATH: "/malicious", OPENAI_API_KEY: "key", HTTP_PROXY: "proxy", T3_TOKEN: "secret", CODEX_AUTH: "token", RUST_LOG: "debug" };
  assert.deepEqual(childEnvironment("/private/app/home", "darwin", source), { CODEX_HOME: "/private/app/home", HOME: "/private/person", USER: "person", PATH: "/usr/bin:/bin:/usr/sbin:/sbin" });
});
