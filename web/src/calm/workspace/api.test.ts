import assert from "node:assert/strict";
import test from "node:test";
import { EngineError } from "../../api/client.ts";
import { acknowledgeWrite, acknowledgedVersion, clearEngineSession } from "../../api/sync.ts";
import { parsePreview, parseWorkspace, workspaceApi, workspaceFailure } from "./api.ts";

test("workspace responses validate signer roles, signature provenance and history at the boundary", () => {
  const w = { content_hash: "h", signers: [{ role: "owner", name: "Ada", required: true }], signatures: [{ role: "owner", name: "Ada", signed_on: "2026-10-26", method: "typed", image: "data:image/png;base64,eA==", current: false }], consent: { agreed: false, at: null }, history: [] };
  assert.deepEqual(parseWorkspace(w), w);
  assert.throws(() => parseWorkspace({ ...w, signers: [{ role: "professional", name: "Engineer", required: true }] }), EngineError);
  assert.throws(() => parseWorkspace({ ...w, signatures: [{ ...w.signatures[0], current: "yes" }] }), EngineError);
  assert.throws(() => parseWorkspace({ ...w, consent: undefined }), EngineError);
});
test("windowed previews retain the real page count and offset, without requiring PDF bytes", () => {
  const p = { filename: "package.pdf", page_count: 15, start: 6, pages: [{ width: 612, height: 792, image: "data:image/png;base64,eA==" }] };
  assert.deepEqual(parsePreview(p), p);
  assert.throws(() => parsePreview({ ...p, page_count: "15" }), EngineError);
  assert.throws(() => parsePreview({ ...p, pages: [{ ...p.pages[0], image: "https://elsewhere/image.png" }] }), EngineError);
});
test("unsupported routes have quiet, visible feature-specific unavailability messages", () => {
  for (const status of [404, 405, 501]) assert.equal(workspaceFailure(new EngineError(status, "raw"), "Signing"), "Signing isn’t available on this server.");
  assert.equal(workspaceFailure(new EngineError(401, "Sign in to continue."), "History"), "Sign in to continue.");
});
test("workspace writes record the case version they create, so the next save is not a false conflict", async t => {
  // Node 22 (CI) has no Web Storage; clearEngineSession() clears the session keys, also in the cleanup below.
  if (!("sessionStorage" in globalThis)) {
    const items = new Map<string, string>();
    Object.assign(globalThis, { sessionStorage: { getItem: (k: string) => items.get(k) ?? null, setItem: (k: string, v: string) => items.set(k, String(v)), removeItem: (k: string) => items.delete(k), clear: () => items.clear() } });
  }
  // QA 2026-10-28: draft save (v8) -> history save (v9) -> the next draft save still sent 8 and got a 409.
  const original = globalThis.fetch;
  t.after(() => { globalThis.fetch = original; clearEngineSession(); });
  clearEngineSession();
  let version = 8;
  const seen: string[] = [];
  globalThis.fetch = async (input, init) => {
    seen.push(`${init?.method} ${new URL(String(input), "http://engine.test").pathname}`);
    version += 1;
    const body = String(input).endsWith("/consent") ? { agreed: true, at: "2026-10-28T12:00:00Z", case_version: version } : { history: [], case_version: version };
    return new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
  };
  acknowledgeWrite("case-1", 8);
  await workspaceApi.history("case-1", [], undefined);
  assert.equal(acknowledgedVersion("case-1"), 9);
  await workspaceApi.consent("case-1", true);
  await workspaceApi.remove("case-1", "owner");
  assert.equal(acknowledgedVersion("case-1"), 11);
  assert.deepEqual(seen.map(s => s.replace(/^.*\/cases/, "")), ["/case-1/history", "/case-1/consent", "/case-1/signatures/owner"]);
});
