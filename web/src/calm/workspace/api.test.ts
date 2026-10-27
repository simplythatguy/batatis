import assert from "node:assert/strict";
import test from "node:test";
import { EngineError } from "../../api/client.ts";
import { parsePreview, parseWorkspace, workspaceFailure } from "./api.ts";

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
