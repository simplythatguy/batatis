import assert from "node:assert/strict";
import test from "node:test";
import { packageReview } from "../../api/packageReview.ts";
import { review } from "../../api/accounts.ts";

test("workspace writes use the atomic return, full-index edit, explicit issuance and pinned acceptance contracts", async t => {
  const calls: { url: string; method: string; body: unknown }[] = [];
  const index = { latest: { version: 3 }, workspace: { gate: { can_accept: true, reason: "" } } };
  t.mock.method(globalThis, "fetch", async (url: string, init: RequestInit) => {
    calls.push({ url, method: init.method || "", body: JSON.parse(String(init.body)) });
    return new Response(JSON.stringify(url.endsWith("information-request") ? index : {}), { status: 200 });
  });
  assert.deepEqual(await packageReview.edit({ kind: "case", id: "case/1" }, 3, { items: [], findings: [{ key: "read", state: "dismissed", reason: "checked", note: "Read the original." }] }), index);
  await packageReview.returnWithRequest("case/1", 3, { expected_version: 7, text: "Exact\nserver text" });
  await packageReview.recordIssued("case/1", "2026-10-26");
  await review.decide("case/1", { outcome: "accept", expected_version: 7, review_version: 3 });
  assert.deepEqual(calls, [
    { url: "/api/review/case%2F1/package-review/3/information-request", method: "PUT", body: { items: [], findings: [{ key: "read", state: "dismissed", reason: "checked", note: "Read the original." }] } },
    { url: "/api/review/case%2F1/package-review/3/return", method: "POST", body: { expected_version: 7, text: "Exact\nserver text" } },
    { url: "/api/review/case%2F1/close-out/issued", method: "POST", body: { issued_on: "2026-10-26" } },
    { url: "/api/review/case%2F1/decision", method: "POST", body: { outcome: "accept", expected_version: 7, review_version: 3 } },
  ]);
});
