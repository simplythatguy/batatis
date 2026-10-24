// Exercises every engine route through the typed client. Needs a running engine (and, for the default
// base, the Vite dev server's /api proxy):  node scripts/smoke-api.ts [base]
// Default base: http://127.0.0.1:3000/api. Pass http://127.0.0.1:8000 to call the engine directly.
import assert from "node:assert/strict";
import { createEngine, EngineError } from "../src/api/client.ts";

const api = createEngine(process.argv[2] ?? "http://127.0.0.1:3000/api");

const created = await api.createCase({ title: "Smoke case", jurisdiction: { id: "calgary", name: "Calgary" } });
assert.match(created.id, /^case_/);
assert.deepEqual(created.facts, []);

const withFact = await api.addFact(created.id, {
  field: "assembly.ratio",
  value: 0.26,
  kind: "computed",
  source: { type: "code", ref: "formula" },
  formula: "RSI 0.88 / RSI 3.34",
  inputs: ["f-a", "f-b"],
  status: "confirmed",
});
assert.equal(withFact.facts.length, 1);
assert.deepEqual(withFact.facts[0].inputs, ["f-a", "f-b"]);

const again = await api.getCase(created.id);
assert.equal(again.facts[0].formula, "RSI 0.88 / RSI 3.34");

await assert.rejects(api.addFact(created.id, { field: "x", value: "y", kind: "proposed", source: { type: "user_text", ref: "r" }, status: "confirmed" }),
  (e) => e instanceof EngineError && e.status === 422);

const rec = await api.provision("9.25.5.2.(1)(b)", "B");
assert.equal(rec.level, "clause");
assert.match(rec.citation, /NBC\(AE\) 2023 p2, Div B, Clause 9\.25\.5\.2\.\(1\)\(b\)/);

const hits = await api.search("vapour barrier", { limit: 5 });
assert.ok(hits.length > 0 && hits.every((h) => h.division === "B"));

const rows = await api.sectionC(["9.25.5.2.(1)(b)", "9.23.17.3.(1)"]);
assert.deepEqual(rows.map((r) => r.attribution_status), ["inherited from parent", "no row in the attribution table"]);
assert.ok(rows[0].pairs.length > 0 && rows[1].pairs.length === 0);

await assert.rejects(api.sectionC(["99.99.99.99.(1)"]), (e) => e instanceof EngineError && e.status >= 400);

console.log(`ok: case ${created.id}, ${hits.length} search hits, ${rows.length} Section C rows`);
