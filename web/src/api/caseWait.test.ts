import assert from "node:assert/strict";
import { mock, test } from "node:test";
import { CASE_WAIT_MS, createEngine, EngineError } from "./client.ts";

/**
 * A fetch that answers only when told to, and rejects as soon as its request is aborted.
 * A saved case carries its requirement ledger, so the payload takes seconds, not milliseconds.
 */
function heldFetch() {
  const held: { path: string; respond: (response: Response) => void }[] = [];
  globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) => new Promise<Response>((resolve, reject) => {
    const signal = init?.signal;
    signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")), { once: true });
    held.push({ path: new URL(String(input)).pathname, respond: resolve });
  })) as typeof fetch;
  return held;
}

const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });

function ledgerReads() {
  const api = createEngine("http://engine.test");
  return {
    read: api.getCase("case_1"),
    decide: api.decideRequirement("case_1", "NBC-AE:B:9.10.14.5.", {
      disposition: "include", role: "supporting", reason: "The applicant confirmed this rule applies.", expected_version: 7,
    }),
  };
}

test("a case read and a requirement decision wait past the 8 s command bound", async (t) => {
  mock.timers.enable({ apis: ["setTimeout"] });
  t.after(() => mock.timers.reset());
  const held = heldFetch();
  const { read, decide } = ledgerReads();
  assert.deepEqual(held.map((h) => h.path), [
    "/cases/case_1",
    "/cases/case_1/identify/requirements/NBC-AE%3AB%3A9.10.14.5./decision",
  ]);
  // The 2,091-row ledger measured ~9 s to read locally, already past the old bound.
  mock.timers.tick(30_000);
  held[0].respond(json({ id: "case_1", version: 7 }));
  held[1].respond(json({ case_version: 8 }));
  assert.deepEqual(await read, { id: "case_1", version: 7 });
  assert.deepEqual(await decide, { case_version: 8 });
});

test("a case read that never answers still ends at the shared bound, as a timeout", async (t) => {
  mock.timers.enable({ apis: ["setTimeout"] });
  t.after(() => mock.timers.reset());
  heldFetch();
  const { read, decide } = ledgerReads();
  let settled = false;
  void Promise.allSettled([read, decide]).then(() => { settled = true; });
  mock.timers.tick(CASE_WAIT_MS - 1);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(settled, false);
  mock.timers.tick(1);
  for (const request of [read, decide]) {
    await assert.rejects(request, (e: unknown) => e instanceof EngineError && e.status === 0 && /did not answer in time/.test(e.detail));
  }
});
