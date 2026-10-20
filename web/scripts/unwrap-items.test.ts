// Every list route must come back as an array. The engine wraps those bodies as { items, meta }.
import assert from "node:assert/strict";
import { ARRAY_ROUTES, createEngine, unwrapItems, type Engine } from "../src/api/client.ts";

const notice = "Do not upload personal information. Demo data may be deleted.";

assert.deepEqual(unwrapItems([{ id: "raw" }]), [{ id: "raw" }]);
const wrapped = unwrapItems({ items: [{ id: "wrapped" }], meta: { notice } });
assert.deepEqual(wrapped, [{ id: "wrapped" }]);
assert.equal("meta" in wrapped, false);

const seen: { method: string; path: string }[] = [];
globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
  const url = new URL(String(input), "http://engine.test");
  seen.push({ method: init?.method ?? "GET", path: url.pathname });
  return new Response(JSON.stringify({ items: [{ id: url.pathname }], meta: { notice } }), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}) as typeof fetch;

const api = createEngine("http://engine.test");
const calls: Record<(typeof ARRAY_ROUTES)[number]["name"], () => Promise<unknown[]>> = {
  search: () => api.search("egress", { limit: 5 }),
  sectionC: () => api.sectionC(["9.1.1.1.(1)"]),
  gaps: () => api.gaps("case_1"),
  processFields: () => api.processFields("case_1"),
  sectionDIssues: () => api.sectionDIssues("case_1"),
};

const engineKeys = new Set(Object.keys(calls));
assert.deepEqual(
  ARRAY_ROUTES.map((route) => route.name),
  [...engineKeys],
);

for (const route of ARRAY_ROUTES) {
  const rows = await calls[route.name]();
  assert.ok(Array.isArray(rows), route.name);
  assert.equal(rows.length, 1);
  assert.equal(Object.prototype.hasOwnProperty.call(rows, "meta"), false);
  assert.equal(Object.prototype.hasOwnProperty.call(rows, "items"), false);
  const hit = seen.at(-1);
  assert.ok(hit, route.name);
  assert.equal(hit.method, route.method);
  assert.equal(hit.path, route.path.replace("{caseId}", "case_1"));
}

void (api satisfies Engine);
console.log(`ok: unwrapped ${ARRAY_ROUTES.length} array routes`);
