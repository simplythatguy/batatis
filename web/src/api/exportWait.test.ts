import assert from "node:assert/strict";
import { mock, test } from "node:test";
import { createEngine, EngineError, EXPORT_WAIT_MS } from "./client.ts";
import { replaceAccountRequests } from "./requestLifetime.ts";

/** A fetch that answers only when told to, and rejects as soon as its request is aborted. */
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
const draftPdf = () => new Response("%PDF-1.7", {
  status: 200, headers: { "content-type": "application/pdf", "content-disposition": 'attachment; filename="case_1-scc-variance-DRAFT.pdf"' },
});

function exports() {
  const api = createEngine("http://engine.test");
  return { preview: api.exportPreview("case_1"), download: api.exportPdf("case_1", true) };
}

test("the preview and the draft download both wait for a long export to finish", async (t) => {
  mock.timers.enable({ apis: ["setTimeout"] });
  t.after(() => mock.timers.reset());
  const held = heldFetch();
  const { preview, download } = exports();
  assert.deepEqual(held.map((h) => h.path), ["/cases/case_1/export/preview", "/cases/case_1/export"]);
  // The review's 500-reference draft took 49.8 s before the appendix cleanup; the old bound was 20 s.
  mock.timers.tick(50_000);
  held[0].respond(json({ kind: "too_large", page_count: 801, pdf_bytes: 3_704_527 }));
  held[1].respond(draftPdf());
  assert.deepEqual(await preview, { kind: "too_large", page_count: 801, pdf_bytes: 3_704_527 });
  const file = await download;
  assert.equal(file.filename, "case_1-scc-variance-DRAFT.pdf");
  assert.equal(await file.blob.text(), "%PDF-1.7");
});

test("an export that never answers still ends at the shared bound, as a timeout", async (t) => {
  mock.timers.enable({ apis: ["setTimeout"] });
  t.after(() => mock.timers.reset());
  heldFetch();
  const { preview, download } = exports();
  let settled = false;
  void Promise.allSettled([preview, download]).then(() => { settled = true; });
  mock.timers.tick(EXPORT_WAIT_MS - 1);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(settled, false);
  mock.timers.tick(1);
  for (const request of [preview, download]) {
    await assert.rejects(request, (e: unknown) => e instanceof EngineError && e.status === 0 && /did not answer in time/.test(e.detail));
  }
});

test("switching accounts cancels both at once, as a cancellation rather than a timeout", async () => {
  heldFetch();
  const { preview, download } = exports();
  replaceAccountRequests();
  for (const request of [preview, download]) {
    await assert.rejects(request, (e: unknown) => !(e instanceof EngineError) && (e as Error).name === "AbortError");
  }
});

test("the caller's own cancellation still ends the preview", async () => {
  heldFetch();
  const ctl = new AbortController();
  const preview = createEngine("http://engine.test").exportPreview("case_1", ctl.signal);
  ctl.abort();
  await assert.rejects(preview, (e: unknown) => !(e instanceof EngineError) && (e as Error).name === "AbortError");
});
