import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../scripts/component-harness.mjs";
import * as relevance from "./relevance.ts";

class CodeLibraryError extends Error {}

/** The real hook over a stubbed GET: what every ring, pill and list reads. */
async function hookWith(result: unknown) {
  let gets = 0;
  const h = await componentHarness(new URL("./useRelevance.ts", import.meta.url), "useRelevance", {
    "../api/codeLibrary": { CodeLibraryError, codeLibrary: { relevance: async () => { gets++; return result; } } },
    "../store": { useCase: () => ({ engineId: "c1", c: { description: "Synthetic project." }, phase: "case", saveDraft: async () => "c1" }) },
    "./codeScope": { useCodeScope: () => "application" },
    "./libraryContext": { libraryEpoch: () => 0 },
    "./relevance": relevance,
  });
  await h.render({});
  (await h.render()).refresh();
  // The store is outside React state: let the GET settle, then render what the rings read.
  await new Promise((resolve) => setImmediate(resolve));
  const rel = await h.render();
  return { rel, gets: () => gets, h };
}

const record = (model: string, bands: unknown) => ({
  status: "scored", model, scored_at: "2026-10-22T12:00:00Z", description_sha256: "0", stale: false,
  scores: { "9.10.1.1.": 0.9, "9.9.1.1.": 0.4, "9.8.1.1.": 0 }, rerank: { "9.10.1.1.": 0.9 }, display: { "9.10.1.1.": 0.9, "9.9.1.1.": 0.4, "9.8.1.1.": 0 },
  bands,
});

test("useRelevance: the exact uncalibrated payload shows estimates, never 'Likely applies'", async () => {
  const { rel, gets, h } = await hookWith(record("relevance-2", { x: 0, y: 1, status: "uncalibrated; display range only" }));
  assert.equal(gets(), 1);
  assert.equal(rel.phase, "ready");
  assert.deepEqual(rel.cutoffs, { rated: false, x: null, y: null, fallback: false });
  const top = rel.shown("9.10.1.1.(2)");
  assert.deepEqual(top, { p: 0.9, band: "estimate", screenedOnly: false }, "a sentence reads its article's estimate");
  assert.equal(relevance.BAND_LABEL[top.band], "Estimate only");
  assert.equal(rel.shown("9.9.1.1.").band, "estimate");
  assert.equal(rel.shown("9.8.1.1.").band, "estimate");
  assert.equal(rel.shown("1.1.1.1.").band, "unscored");
  assert.equal(rel.display?.["9.10.1.1."], 0.9, "the raw probability is kept");
  h.unmount();
});

test("useRelevance: a historical benchmark record keeps its likely / might / unlikely bands", async () => {
  const { rel, h } = await hookWith(record("relevance-1", { x: 0.3, y: 0.85, status: "benchmark-derived, not field-calibrated" }));
  assert.deepEqual(rel.cutoffs, { rated: true, x: 0.3, y: 0.85, fallback: false });
  assert.equal(rel.shown("9.10.1.1.").band, "high");
  assert.equal(relevance.BAND_LABEL[rel.shown("9.10.1.1.").band], "Likely applies · address this");
  assert.equal(rel.shown("9.9.1.1.").band, "low", "screened only: the guard still caps it");
  h.unmount();
});

test("useRelevance: missing bands are estimates, not historical thresholds", async () => {
  const { rel, h } = await hookWith(record("relevance-1", undefined));
  assert.equal(rel.cutoffs.rated, false);
  assert.equal(rel.shown("9.10.1.1.").band, "estimate");
  h.unmount();
});

const legendWith = async (cutoffs: relevance.Cutoffs) => {
  const h = await componentHarness(new URL("./RelevanceRing.tsx", import.meta.url), "RingLegend", {
    "./relevance": relevance,
    "./useRelevance": { useRelevance: () => ({ cutoffs, scope: "application" }) },
    "react-dom": { createPortal: (node) => node },
  });
  const tree = await h.render({});
  nodes(tree, (n) => n.type === "button")[0].props.onClick();
  const out = text(await h.render());
  h.unmount();
  return out;
};

test("the ring legend gives no cut-offs for uncalibrated estimates, and keeps them for the benchmark", async () => {
  const unrated = await legendWith(relevance.cutoffsOf({ model: "relevance-2", bands: { x: 0, y: 1, status: "uncalibrated; display range only" } }));
  assert.match(unrated, /Estimate only/);
  assert.doesNotMatch(unrated, /Likely applies|Unlikely|Might apply|yellow or red|30%|85%/);
  const rated = await legendWith(relevance.cutoffsOf({ model: "relevance-1", bands: { x: 0.3, y: 0.85, status: "benchmark-derived, not field-calibrated" } }));
  assert.match(rated, /Likely applies · address this\. 85% or more\./);
  assert.match(rated, /Unlikely to apply\. Above 0 and under 30%\./);
});

test("useRelevance: Score relevance acknowledges the case version the scores were saved under", async () => {
  const acknowledged: [string, unknown][] = [];
  const h = await componentHarness(new URL("./useRelevance.ts", import.meta.url), "useRelevance", {
    "../api/codeLibrary": { CodeLibraryError, codeLibrary: { score: async () => ({ ...record("relevance-2", null), case_version: 7 }) } },
    "../api/sync": { acknowledgeWrite: (id: string, version: unknown) => acknowledged.push([id, version]) },
    "../store": { useCase: () => ({ engineId: "c1", c: { description: "Synthetic project." }, phase: "case", saveDraft: async () => "c1" }) },
    "./codeScope": { useCodeScope: () => "application" },
    "./libraryContext": { libraryEpoch: () => 0 },
    "./relevance": relevance,
  });
  await (await h.render({})).score();
  assert.deepEqual(acknowledged, [["c1", 7]], "the next draft save sends the version scoring wrote, not a stale one");
  assert.equal((await h.render()).phase, "ready");
  h.unmount();
});
