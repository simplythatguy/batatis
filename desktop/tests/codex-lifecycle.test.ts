import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { getEventListeners, once } from "node:events";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import test, { type TestContext } from "node:test";
import { codexProviderFactory, CODEX_CONTEXT_FINGERPRINT, type CodexTiming } from "../src/main/codex.ts";
import { EFFORT, MODEL } from "../src/main/codex/config.ts";
import type { CompleteJsonRequest, CompleteJsonResult } from "../src/main/providers.ts";
import { syntheticCodexEnvironment } from "./codex-fixture.ts";

const REPO = resolve(import.meta.dirname, "../..");
const request: CompleteJsonRequest = {
  task: "lifecycle-fixture", system: "Synthetic lifecycle instructions", user: "Synthetic lifecycle input",
  schema: { type: "object", properties: { answer: { type: "string" } }, required: ["answer"], additionalProperties: false },
  model: MODEL, effort: EFFORT, maxOutputTokens: null,
};

const server = String.raw`
import { appendFileSync } from 'node:fs';
import { createInterface } from 'node:readline';
const mode = JSON.parse(process.argv[2]);
const capture = process.argv[3];
const controls = new Map();
let thread = 0;
let currentThread;
let currentTurn;
const send = value => process.stdout.write(JSON.stringify(value)+'\n');
const reply = (id,result) => send({id,result});
const notify = (method,params) => send({method,params});
const turn = (status,items=[]) => ({id:currentTurn,status,items,error:null,itemsView:'summary'});
const model = {id:'gpt-6-luna',model:'gpt-6-luna',displayName:'Luna',description:'Synthetic',hidden:false,isDefault:true,defaultReasoningEffort:'medium',supportedReasoningEfforts:[{reasoningEffort:'medium',description:'Medium'}]};
const reader = createInterface({input:process.stdin});
reader.on('line',line=>{
  const msg = JSON.parse(line);
  if (msg.fixtureControl) { controls.get(msg.fixtureControl)?.(); controls.delete(msg.fixtureControl); return; }
  appendFileSync(capture,JSON.stringify(msg)+'\n');
  if (msg.method === mode.errorMethod) {
    const error = () => {
      send({id:msg.id,error:mode.errorValue});
      appendFileSync(capture,JSON.stringify({fixtureEvent:'error-sent',error:mode.errorValue})+'\n');
    };
    if (mode.holdError) controls.set('error',error); else error();
    return;
  }
  const p = msg.params;
  switch(msg.method) {
    case 'initialize': {
      const initialize = () => reply(msg.id,{codexHome:process.env.CODEX_HOME,userAgent:'fixture',platformFamily:'fixture',platformOs:'fixture'});
      if (mode.holdInitialize) controls.set('initialize',initialize); else initialize();
      break;
    }
    case 'initialized': break;
    case 'account/read': reply(msg.id,{account:{type:'chatgpt',planType:'plus',email:null},requiresOpenaiAuth:true}); break;
    case 'model/list': reply(msg.id,{data:[model],nextCursor:null}); break;
    case 'configRequirements/read': reply(msg.id,{requirements:null}); break;
    case 'thread/start':
      currentThread = 'thread-'+(++thread);
      reply(msg.id,{model:'gpt-6-luna',modelProvider:'openai',cwd:p.cwd,approvalPolicy:'never',approvalsReviewer:'user',sandbox:{type:'readOnly',networkAccess:false},reasoningEffort:'medium',instructionSources:[],runtimeWorkspaceRoots:[],thread:{id:currentThread,cwd:p.cwd,ephemeral:true,model:'gpt-6-luna',modelProvider:'openai',reasoningEffort:'medium',environments:[],turns:[]}});
      break;
    case 'turn/start':
      currentTurn = 'turn-'+thread;
      reply(msg.id,{turn:turn('inProgress')});
      notify('turn/started',{threadId:currentThread,turn:turn('inProgress')});
      controls.set('finish',()=>{
        const item = {type:'agentMessage',id:'final-'+thread,text:'{"answer":"accepted"}',phase:'final_answer'};
        notify('item/completed',{threadId:currentThread,turnId:currentTurn,item});
        notify('turn/completed',{threadId:currentThread,turn:turn('completed',[item])});
      });
      break;
    case 'turn/interrupt': {
      const interrupt = () => { reply(msg.id,{}); notify('turn/completed',{threadId:currentThread,turn:turn('interrupted')}); };
      if (mode.ignoreInterrupt) break;
      if (mode.holdInterrupt) controls.set('interrupt',interrupt); else interrupt();
      break;
    }
    case 'thread/unsubscribe': reply(msg.id,{status:'unsubscribed'}); break;
  }
});
reader.on('close',()=>{ if(mode.ignoreEof) setInterval(()=>{},1000); else process.exit(0); });
`;

const delay = (ms: number) => new Promise<void>((done) => setTimeout(done, ms));

async function within<T>(promise: Promise<T>, ms: number, message: string): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([promise, new Promise<never>((_, reject) => {
      timer = setTimeout(() => reject(new Error(message)), ms);
    })]);
  } finally { clearTimeout(timer); }
}

async function fixture(t: TestContext, mode: Record<string, unknown> = {}, timing: Partial<CodexTiming> = {}) {
  const dir = await mkdtemp(join(tmpdir(), "batatis-codex-lifecycle-"));
  const script = join(dir, "fake-child.mjs");
  const capture = join(dir, "requests.jsonl");
  await writeFile(script, server);
  await writeFile(capture, "");
  const children: ReturnType<typeof spawn>[] = [];
  const logs: string[] = [];
  const digest = "f".repeat(64);
  const provider = codexProviderFactory({
    runtime: async () => ({ executable: process.execPath, sha256: digest, catalog: await readFile(join(REPO, "desktop/codex/luna-models.json")) }),
    verifiedContext: { evidence: "Synthetic offline lifecycle fixture", runtimeSha256: digest, contextFingerprint: CODEX_CONTEXT_FINGERPRINT },
    environment: syntheticCodexEnvironment(dir),
    spawn: (_command, _args, options) => {
      const child = spawn(process.execPath, [script, JSON.stringify(mode), capture], options);
      children.push(child);
      return child;
    },
    timing: { requestMs: 1000, completionMs: 5000, interruptMs: 100, stopMs: 30, loginMs: 1000, ...timing },
  })({ stateDir: join(dir, "state"), workDir: join(dir, "work"), resourcesDir: REPO, appVersion: "fixture", log: (line) => logs.push(line) });
  let disposal: Promise<void> | undefined;
  const dispose = () => disposal ??= provider.dispose();
  const exited = (child: ReturnType<typeof spawn>) => child.exitCode !== null || child.signalCode !== null;
  t.after(async () => {
    try { await within(dispose(), 700, "fixture disposal must settle"); }
    finally {
      await Promise.all(children.filter((child) => !exited(child)).map(async (child) => {
        const closed = once(child, "close");
        child.kill("SIGKILL");
        await within(closed, 700, "owned synthetic child must exit");
      }));
      await rm(dir, { recursive: true, force: true });
    }
    assert.ok(children.every(exited), "every owned synthetic child exited");
  });
  const messages = async (): Promise<Record<string, unknown>[]> => (await readFile(capture, "utf8")).split("\n").filter(Boolean).map((line) => JSON.parse(line));
  const waitFor = async (check: () => Promise<boolean>) => {
    // Generous for cold process starts on hosted Windows runners; a passing run returns as soon as the state holds.
    const deadline = Date.now() + 10_000;
    while (!await check()) {
      assert.ok(Date.now() < deadline, "synthetic child reached the requested state");
      await delay(5);
    }
  };
  const waitMethod = (method: string, count = 1) => waitFor(async () => (await messages()).filter((message) => message.method === method).length >= count);
  const control = (command: string) => children[0].stdin?.write(JSON.stringify({ fixtureControl: command }) + "\n");
  return { provider, children, logs, messages, waitFor, waitMethod, control, dispose, exited };
}

function assertFailure(result: CompleteJsonResult, reason: string): void {
  assert.equal(result.ok, false);
  if (!result.ok) assert.equal(result.reason, reason);
}

for (const [name, errorValue] of [
  ["null", null], ["array", []], ["boolean", false], ["number", 7], ["string", "PRIVATE RESPONSE"],
  ["invalid fields", { code: "PRIVATE RESPONSE", message: 7 }],
  ["valid control", { code: -32000, message: "PRIVATE RESPONSE" }],
] satisfies [string, unknown][]) {
  test(`RPC error lifecycle settles initialization, queued status and disposal for ${name}`, async (t) => {
    const f = await fixture(t, { errorMethod: "initialize", errorValue, holdError: true }, { requestMs: 5000, completionMs: 10000 });
    const completion = f.provider.completeJson(request, new AbortController().signal);
    const status = f.provider.status();
    await f.waitMethod("initialize");
    assert.equal(f.children.some(f.exited), false);
    assert.equal((await f.messages()).some((message) => message.fixtureEvent === "error-sent"), false);
    f.control("error");
    await f.waitFor(async () => (await f.messages()).some((message) => message.fixtureEvent === "error-sent"));
    assert.deepEqual((await f.messages()).find((message) => message.fixtureEvent === "error-sent")?.error, errorValue);
    await f.waitFor(async () => f.children.some(f.exited));
    const values = await within(Promise.all([completion, status, f.dispose()]), 350, "malformed RPC errors must settle completion, followups and disposal after child exit");
    assertFailure(values[0], "runtime");
    assert.equal(values[1].state, "error");
    assert.equal(JSON.stringify([values, f.logs]).includes("PRIVATE RESPONSE"), false);
    assert.ok(f.children.every(f.exited));
  });
}

for (const errorMethod of ["account/read", "turn/start"]) {
  test(`RPC error lifecycle settles malformed ${errorMethod} responses after startup`, async (t) => {
    const f = await fixture(t, { errorMethod, errorValue: null }, { requestMs: 2000, completionMs: 4000 });
    const completion = f.provider.completeJson(request, new AbortController().signal);
    const status = f.provider.status();
    await f.waitMethod(errorMethod);
    await f.waitFor(async () => f.children.some(f.exited));
    const values = await within(Promise.all([completion, status, f.dispose()]), 350, "malformed responses must not orphan active requests or disposal");
    assertFailure(values[0], "runtime");
    assert.ok(f.children.every(f.exited));
  });
}

test("queued caller cancellation settles independently and never dispatches or interrupts active work", async (t) => {
  const f = await fixture(t);
  let firstSettled = false;
  const first = f.provider.completeJson(request, new AbortController().signal);
  void first.then(() => { firstSettled = true; });
  await f.waitMethod("turn/start");
  const abort = new AbortController();
  const queued = f.provider.completeJson(request, abort.signal);
  abort.abort();
  assertFailure(await within(queued, 250, "queued abort must settle before active work releases"), "cancelled");
  assert.equal(getEventListeners(abort.signal, "abort").length, 0);
  assert.equal(firstSettled, false);
  assert.equal(f.children.some(f.exited), false);
  assert.equal((await f.messages()).some((message) => message.method === "turn/interrupt"), false);
  f.control("finish");
  assert.equal((await within(first, 500, "active completion remains usable")).ok, true);
  assert.equal((await f.provider.status()).state, "signed-in");
  assert.equal((await f.messages()).filter((message) => message.method === "turn/start").length, 1);
});

test("queued deadline settles independently while initialization remains active", async (t) => {
  const f = await fixture(t, { holdInitialize: true }, { requestMs: 2000, completionMs: 60 });
  let firstSettled = false;
  const first = f.provider.models();
  void first.then(() => { firstSettled = true; });
  await f.waitMethod("initialize");
  const abort = new AbortController();
  const queued = f.provider.completeJson(request, abort.signal);
  assertFailure(await within(queued, 250, "queued deadline must settle before initialization releases"), "incomplete");
  assert.equal(getEventListeners(abort.signal, "abort").length, 0);
  assert.equal(firstSettled, false);
  assert.equal(f.children.some(f.exited), false);
  f.control("initialize");
  assert.equal((await within(first, 500, "initialization remains usable")).length, 1);
  assert.equal((await f.provider.status()).state, "signed-in");
  assert.equal((await f.messages()).some((message) => message.method === "turn/start"), false);
});

test("a workflow deadline includes time queued behind another completion", async (t) => {
  const completionMs = 10000;
  const f = await fixture(t, {}, { requestMs: 5000, completionMs });
  let activeSettled = false;
  const activeAbort = new AbortController();
  const active = f.provider.completeJson(request, activeAbort.signal);
  void active.then(() => { activeSettled = true; });
  await f.waitMethod("turn/start");
  assert.equal(activeSettled, false);
  const queuedAbort = new AbortController();
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const queued = f.provider.completeJson(request, queuedAbort.signal);
  t.mock.timers.tick(completionMs);
  t.mock.timers.reset();
  assertFailure(await within(queued, 250, "queued deadline must settle while the active turn remains held"), "incomplete");
  assert.equal(getEventListeners(queuedAbort.signal, "abort").length, 0);
  assert.equal(activeSettled, false);
  assert.equal(f.children.some(f.exited), false);
  assert.equal((await f.messages()).some((message) => message.method === "turn/interrupt"), false);
  assert.equal((await f.messages()).filter((message) => message.method === "turn/start").length, 1);
  f.control("finish");
  assert.equal((await within(active, 500, "active completion remains usable after queued expiry")).ok, true);
  assert.equal(getEventListeners(activeAbort.signal, "abort").length, 0);
  assert.equal((await f.provider.status()).state, "signed-in");
  assert.equal((await f.messages()).filter((message) => message.method === "turn/start").length, 1);
  const next = f.provider.completeJson(request, new AbortController().signal);
  await f.waitMethod("turn/start", 2);
  f.control("finish");
  assert.equal((await within(next, 500, "fresh work uses the queue after expired work was removed")).ok, true);
  assert.equal((await f.messages()).filter((message) => message.method === "turn/start").length, 2);
});

test("repeated queued cancellation frees capacity and preserves the pending-operation bound", async (t) => {
  const f = await fixture(t);
  const first = f.provider.completeJson(request, new AbortController().signal);
  await f.waitMethod("turn/start");
  for (let index = 0; index < 16; index++) {
    const abort = new AbortController();
    const queued = f.provider.completeJson(request, abort.signal);
    abort.abort();
    assertFailure(await within(queued, 250, "cancelled waiters must release queue capacity"), "cancelled");
    assert.equal(getEventListeners(abort.signal, "abort").length, 0);
  }
  const controllers = Array.from({ length: 7 }, () => new AbortController());
  const queued = controllers.map((abort) => f.provider.completeJson(request, abort.signal));
  assertFailure(await within(f.provider.completeJson(request, new AbortController().signal), 250, "excess work must be refused"), "runtime");
  for (const abort of controllers) abort.abort();
  for (const value of await within(Promise.all(queued), 250, "cancelled capacity must settle independently")) assertFailure(value, "cancelled");
  const replacement = f.provider.completeJson(request, new AbortController().signal);
  f.control("finish");
  assert.equal((await within(first, 500, "first turn remains usable")).ok, true);
  await f.waitMethod("turn/start", 2);
  f.control("finish");
  assert.equal((await within(replacement, 500, "replacement uses released capacity")).ok, true);
  assert.equal((await f.messages()).filter((message) => message.method === "turn/start").length, 2);
});

test("active cancellation waits for the interrupt response and terminal event before releasing the queue", async (t) => {
  const f = await fixture(t, { holdInterrupt: true }, { interruptMs: 500 });
  const abort = new AbortController();
  let settled = false;
  const active = f.provider.completeJson(request, abort.signal);
  void active.then(() => { settled = true; });
  await f.waitMethod("turn/start");
  await delay(20);
  abort.abort();
  await f.waitMethod("turn/interrupt");
  let statusSettled = false;
  const status = f.provider.status();
  void status.then(() => { statusSettled = true; });
  await delay(30);
  assert.equal(settled, false, "running cancellation still owns resource cleanup");
  assert.equal(statusSettled, false, "following work waits for active cancellation cleanup");
  assert.equal(f.children.some(f.exited), false);
  f.control("interrupt");
  assertFailure(await within(active, 500, "active cancellation settles after acknowledgement"), "cancelled");
  assert.equal((await within(status, 500, "queue resumes after acknowledgement")).state, "signed-in");
  assert.equal(getEventListeners(abort.signal, "abort").length, 0);
});

test("active cancellation waits for bounded child shutdown when interrupt is ignored", async (t) => {
  const f = await fixture(t, { ignoreInterrupt: true, ignoreEof: true }, { interruptMs: 50 });
  const abort = new AbortController();
  const active = f.provider.completeJson(request, abort.signal);
  await f.waitMethod("turn/start");
  await delay(20);
  abort.abort();
  assertFailure(await within(active, 500, "active cancellation must finish bounded child shutdown"), "cancelled");
  assert.ok(f.children.every(f.exited), "running work settles only after its owned child exits");
});
