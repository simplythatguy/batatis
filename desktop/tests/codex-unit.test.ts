import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";
import { EFFORT, MODEL } from "../src/main/codex/config.ts";
import { AdapterError, assertRequirements, classifyErrorInfo, outputValidator, parseAccount, parseModels, parseThread, parseUsage, rpcFailure } from "../src/main/codex/protocol.ts";
import { CompletionTurn } from "../src/main/codex/turn.ts";
import type { CompleteJsonRequest } from "../src/main/providers.ts";

const request: CompleteJsonRequest = { task: "fixture", system: "system", user: "user", model: MODEL, effort: EFFORT, maxOutputTokens: null,
  schema: { type: "object", required: ["found"], properties: { found: { type: "boolean" } }, additionalProperties: false } };
const final = { type: "agentMessage", id: "answer-1", text: '{"found":true}', phase: "final_answer" };

function tracker(value: CompleteJsonRequest = request) {
  const poisoned: AdapterError[] = [];
  return { turn: new CompletionTurn("thread-1", value, (error) => poisoned.push(error)), poisoned };
}

function item(turn: CompletionTurn, value: unknown, threadId = "thread-1", turnId = "turn-1") {
  turn.accept({ method: "item/completed", params: { threadId, turnId, item: value } });
}
function terminal(turn: CompletionTurn, items: unknown[], status = "completed", error: unknown = null) {
  turn.accept({ method: "turn/completed", params: { threadId: "thread-1", turn: { id: "turn-1", status, items, error } } });
}
function start(turn: CompletionTurn) { turn.startResponse({ turn: { id: "turn-1", status: "inProgress", items: [] } }); }

test("only completed final item and matching successful terminal turn can produce JSON", async () => {
  const { turn } = tracker();
  item(turn, final);
  terminal(turn, [final]);
  assert.equal(turn.isDone, false, "early notifications await start acknowledgement");
  start(turn);
  assert.deepEqual(await turn.result, { ok: true, json: { found: true }, model: MODEL, effort: EFFORT, usage: null });
});

test("a final item only in a terminal summary cannot substitute for completed agent output", async () => {
  const { turn } = tracker();
  start(turn);
  terminal(turn, [final]);
  const result = await turn.result;
  assert.equal(result.ok, false);
  if (!result.ok) assert.equal(result.reason, "incomplete");
});

test("stale events for another thread or turn do not contaminate the current answer", async () => {
  const { turn } = tracker();
  start(turn);
  item(turn, { ...final, text: "garbage" }, "old-thread");
  item(turn, { ...final, text: "garbage" }, "thread-1", "old-turn");
  item(turn, final);
  terminal(turn, [final]);
  assert.equal((await turn.result).ok, true);
});

test("post-cancellation final output cannot replace the cancelled result", async () => {
  const { turn } = tracker();
  start(turn);
  turn.fail(new AdapterError("cancelled"));
  item(turn, final);
  terminal(turn, [final]);
  const result = await turn.result;
  assert.equal(result.ok, false);
  if (!result.ok) assert.equal(result.reason, "cancelled");
});

test("tool items and changed user input invalidate context instead of producing partial success", async () => {
  for (const value of [{ type: "webSearch", id: "tool-1" }, { type: "userMessage", id: "user-1", content: [{ type: "text", text: "changed" }] }]) {
    const { turn, poisoned } = tracker();
    start(turn);
    item(turn, value);
    const result = await turn.result;
    if (!result.ok) assert.equal(result.reason, "context_unverified");
    assert.equal(poisoned.length, 1);
  }
});

test("observed negative or fractional usage is never converted to zero", () => {
  for (const inputTokens of [-1, 0.5, null, "100"]) assert.throws(() => parseUsage({ total: { inputTokens, outputTokens: 5 } }), AdapterError);
  assert.deepEqual(parseUsage({ total: { inputTokens: 0, outputTokens: 0 } }), { inputTokens: 0, outputTokens: 0 });
});

test("strict schema validation neither coerces nor repairs provider JSON", () => {
  const validate = outputValidator(request.schema);
  assert.equal(validate({ found: true }), true);
  assert.equal(validate({ found: "true" }), false);
  assert.equal(validate({ found: true, extra: "not removed" }), false);
  assert.throws(() => outputValidator({ type: "object", properties: { a: { $ref: "https://untrusted.invalid/schema" } } }), AdapterError);
});

test("a locally observed token budget overrun is incomplete and never claims an upstream ceiling", async () => {
  const { turn } = tracker({ ...request, maxOutputTokens: 5 });
  start(turn);
  turn.accept({ method: "thread/tokenUsage/updated", params: { threadId: "thread-1", turnId: "turn-1", tokenUsage: { total: { inputTokens: 1, outputTokens: 6 } } } });
  item(turn, final);
  terminal(turn, [final]);
  const result = await turn.result;
  if (!result.ok) assert.equal(result.reason, "incomplete");
  assert.equal(result.ok, false);
});

test("safe error mapping uses structured status and never exposes provider messages", () => {
  for (const [info, expected] of [
    ["rateLimitExceeded", "quota"], ["sessionBudgetExceeded", "quota"], ["unauthorized", "auth"],
    [{ responseStreamConnectionFailed: { httpStatusCode: 429 } }, "quota"],
    [{ responseStreamDisconnected: { httpStatusCode: 403 } }, "auth"], ["contextWindowExceeded", "incomplete"],
  ]) assert.equal(classifyErrorInfo(info), expected);
  const error = rpcFailure({ code: -32000, message: "SECRET TOKEN", data: { codexErrorInfo: "usageLimitExceeded" } });
  assert.equal(error.reason, "quota");
  assert.equal(error.message.includes("SECRET"), false);
});

test("unobservable or nonempty managed instructions fail closed", () => {
  assertRequirements({ requirements: null });
  assertRequirements({ requirements: { additionalDeveloperInstructions: "" } });
  assertRequirements({ requirements: { additionalDeveloperInstructions: null } });
  for (const value of [{}, { requirements: {} }, { requirements: { additionalDeveloperInstructions: "managed" } }]) assert.throws(() => assertRequirements(value), AdapterError);
});

test("account data cannot silently switch to an API key or token bridge", () => {
  for (const type of ["apiKey", "chatgptAuthTokens", "amazonBedrock", "unknown"]) assert.throws(() => parseAccount({ account: { type }, requiresOpenaiAuth: true }), AdapterError);
  assert.deepEqual(parseAccount({ account: null, requiresOpenaiAuth: true }), { state: "signed-out" });
  assert.throws(() => parseAccount({ requiresOpenaiAuth: true }), AdapterError);
});

test("thread metadata must echo the isolated model, effort and context", () => {
  const reply = { model: MODEL, modelProvider: "openai", cwd: "/empty", approvalPolicy: "never", approvalsReviewer: "user", sandbox: { type: "readOnly" }, reasoningEffort: EFFORT, instructionSources: [], runtimeWorkspaceRoots: [],
    thread: { id: "thread-1", cwd: "/empty", ephemeral: true, model: MODEL, modelProvider: "openai", reasoningEffort: EFFORT, environments: [], turns: [] } };
  assert.equal(parseThread(reply, "/empty"), "thread-1");
  for (const change of [{ instructionSources: undefined }, { sandbox: { type: "dangerFullAccess" } }, { reasoningEffort: "max" }, { runtimeWorkspaceRoots: ["/repo"] }]) assert.throws(() => parseThread({ ...reply, ...change }, "/empty"), AdapterError);
});

test("catalog metadata is bounded and does not grant model entitlement", () => {
  const model = { id: MODEL, model: MODEL, displayName: "Luna", description: "", hidden: false, isDefault: false, defaultReasoningEffort: "medium", supportedReasoningEfforts: [{ reasoningEffort: "medium", description: "" }] };
  assert.equal(parseModels({ data: [model], nextCursor: null }).models[0].id, MODEL);
  assert.throws(() => parseModels({ data: [model, model] }), AdapterError);
  assert.throws(() => parseModels({ data: [{ ...model, supportedReasoningEfforts: "medium" }] }), AdapterError);
});

test("catalog helper retains the reviewed exact output and rejects a source with the wrong digest", async () => {
  const path = resolve(import.meta.dirname, "../codex/fetch.mjs");
  const { deriveCatalog } = await import(pathToFileURL(path).href);
  const candidate = await readFile(resolve(import.meta.dirname, "../codex/luna-models.json"));
  assert.throws(() => deriveCatalog(candidate), /source digest mismatch/);
  const parsed = JSON.parse(candidate.toString("utf8"));
  assert.equal(parsed.models.length, 11);
  assert.equal(parsed.models[3].tool_mode, "direct");
  assert.equal(parsed.models[3].shell_type, "disabled");
});
