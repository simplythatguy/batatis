import assert from "node:assert/strict";
import { mock, test } from "node:test";
import { APPLICANT_DRAFT_WAIT_MS, createEngine, EngineError } from "./client.ts";
import { replaceAccountRequests } from "./requestLifetime.ts";

function heldFetch() {
  const held: { path: string; method: string | undefined; body: string | null | undefined; respond: (response: Response) => void }[] = [];
  globalThis.fetch = (input, init) => new Promise<Response>((resolve, reject) => {
    init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")), { once: true });
    held.push({ path: new URL(String(input)).pathname, method: init?.method,
      body: typeof init?.body === "string" ? init.body : null, respond: resolve });
  });
  return held;
}
const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });

test("draft endpoints use saved versions and survive sequential generation, audit and registry work", async t => {
  const original = globalThis.fetch;
  mock.timers.enable({ apis: ["setTimeout"] });
  t.after(() => { globalThis.fetch = original; mock.timers.reset(); });
  const held = heldFetch();
  const api = createEngine("http://engine.test");
  const generate = api.generateApplicantDrafts("case/1", 7);
  mock.timers.tick(390_000);
  held[0].respond(json({ id: "case/1", version: 8, drafting: { drafts: [] } }));
  assert.equal((await generate).version, 8);
  const accept = api.decideApplicantDraft("case/1", "draft/1", 8, "accept");
  held[1].respond(json({ id: "case/1", version: 9 }));
  await accept;
  const read = api.applicantDrafts("case/1");
  held[2].respond(json(null));
  assert.equal(await read, null);
  assert.deepEqual(held.map(h => [h.path, h.method, h.body]), [
    ["/cases/case%2F1/drafts", "POST", JSON.stringify({ expected_version: 7 })],
    ["/cases/case%2F1/drafts/draft%2F1/decision", "POST", JSON.stringify({ expected_version: 8, decision: "accept" })],
    ["/cases/case%2F1/drafts", "GET", undefined],
  ].map(([path, method, body]) => [path, method, body ?? null]));
});

test("a hung generation ends at its bound; account replacement still cancels instead of timing out", async t => {
  const original = globalThis.fetch;
  mock.timers.enable({ apis: ["setTimeout"] });
  t.after(() => { globalThis.fetch = original; mock.timers.reset(); });
  heldFetch();
  const api = createEngine("http://engine.test");
  const generation = api.generateApplicantDrafts("case1", 1);
  const timeout = assert.rejects(generation, error => error instanceof EngineError && error.status === 0 && /in time/.test(error.detail));
  mock.timers.tick(APPLICANT_DRAFT_WAIT_MS);
  await timeout;
  const other = api.generateApplicantDrafts("case1", 1);
  const aborted = assert.rejects(other, error => error instanceof DOMException && error.name === "AbortError");
  replaceAccountRequests();
  await aborted;
});
