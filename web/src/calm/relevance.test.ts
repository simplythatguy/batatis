import assert from "node:assert/strict";
import test from "node:test";
import type { CodeToc } from "../api/codeLibrary.ts";
import { reflow, ancestorsOf, BAND_LABEL, bandFor, cutoffsOf, DEFAULT_BANDS, filterKeep, maxOf, partArticles, pruneToc, rankedIn, sectionArticles, shownFor, strongestOf } from "./relevance.ts";
import { codeHref, resolveRoute } from "./routes.ts";

const C = { rated: true, x: 0.2, y: 0.6, fallback: false } as const;

test("band edges: 0 is grey, x is moderate, y is high, missing is not scored", () => {
  assert.equal(bandFor(0, C), "zero");
  assert.equal(bandFor(0.01, C), "low");
  assert.equal(bandFor(0.19, C), "low");
  assert.equal(bandFor(0.2, C), "mid");
  assert.equal(bandFor(0.59, C), "mid");
  assert.equal(bandFor(0.6, C), "high");
  assert.equal(bandFor(1, C), "high");
  assert.equal(bandFor(undefined, C), "unscored");
  assert.equal(bandFor(null, C), "unscored");
  assert.equal(bandFor(Number.NaN, C), "unscored");
});

const HISTORICAL = { model: "relevance-1", bands: { x: 0.3, y: 0.85, status: "benchmark-derived, not field-calibrated" } };
const LEGACY_PLACEHOLDER = { model: "relevance-1", bands: { x: 0.2, y: 0.6, status: "placeholder_uncalibrated" } };
/** The exact bands engine/relevance.py scoring_bands() returns for any non-historical configuration. */
const UNCALIBRATED = { model: "relevance-2", bands: { x: 0, y: 1, status: "uncalibrated; display range only" } };
const UNRATED = { rated: false, x: null, y: null, fallback: false };

test("cut-offs: the historical benchmark bands are used; legacy relevance-1 placeholder rows read with the benchmark defaults", () => {
  assert.deepEqual(DEFAULT_BANDS, { x: 0.3, y: 0.85 });
  assert.deepEqual(cutoffsOf(HISTORICAL), { rated: true, x: 0.3, y: 0.85, fallback: false });
  assert.deepEqual(cutoffsOf(LEGACY_PLACEHOLDER), { rated: true, x: 0.3, y: 0.85, fallback: true });
});

test("cut-offs: the pinned Elephant relevance-3 payload stays an estimate; a zero score and an unscored article stay distinct", () => {
  // engine/relevance.py scoring_bands() for any non-historical configuration, Elephant's included.
  const ELEPHANT = { model: "relevance-3", bands: { x: 0, y: 1, status: "uncalibrated; display range only" } };
  const c = cutoffsOf(ELEPHANT);
  assert.deepEqual(c, UNRATED, "no relevance-1 benchmark (or any other) thresholds are borrowed");
  assert.equal(bandFor(0, c), "estimate", "0 is a score, shown as an estimate");
  assert.equal(bandFor(0.97, c), "estimate", "never 'likely applies' without fitted cut-offs");
  assert.equal(bandFor(null, c), "unscored");
  assert.equal(bandFor(undefined, c), "unscored");
});

test("cut-offs: uncalibrated, missing or malformed bands give no likely/unlikely rating, never the historical thresholds", () => {
  assert.deepEqual(cutoffsOf(UNCALIBRATED), UNRATED, "the exact backend payload");
  assert.deepEqual(cutoffsOf({ ...UNCALIBRATED, model: "relevance-1" }), UNRATED, "a relevance-1 run outside the benchmark configuration is uncalibrated too");
  assert.deepEqual(cutoffsOf({ model: "relevance-2", bands: { x: 0.3, y: 0.85, status: "uncalibrated" } }), UNRATED, "the status wins over plausible numbers");
  assert.deepEqual(cutoffsOf({ model: "relevance-2", bands: { x: 0.2, y: 0.6, status: "placeholder_uncalibrated" } }), UNRATED, "the benchmark defaults belong to relevance-1 only");
  assert.deepEqual(cutoffsOf({ model: "relevance-2", bands: null }), UNRATED);
  assert.deepEqual(cutoffsOf({ model: "relevance-1", bands: null }), UNRATED, "missing bands are not assumed historical");
  assert.deepEqual(cutoffsOf(null), UNRATED);
  assert.deepEqual(cutoffsOf({ model: "relevance-1", bands: { x: 0.7, y: 0.3, status: "benchmark-derived, not field-calibrated" } }), UNRATED, "inverted");
  assert.deepEqual(cutoffsOf({ model: "relevance-1", bands: { x: 0.3, y: 0.85 } }), UNRATED, "no status");
  assert.deepEqual(cutoffsOf({ model: "relevance-1", bands: { x: Number.NaN, y: 0.85, status: "benchmark-derived, not field-calibrated" } }), UNRATED, "not a number");
  // The 0 and 1 boundaries are the display range, not cut-offs, whatever the status says.
  assert.deepEqual(cutoffsOf({ model: "relevance-1", bands: { x: 0, y: 0.85, status: "benchmark-derived, not field-calibrated" } }), UNRATED);
  assert.deepEqual(cutoffsOf({ model: "relevance-1", bands: { x: 0.3, y: 1, status: "benchmark-derived, not field-calibrated" } }), UNRATED);
});

test("uncalibrated scores stay estimates: never likely-applies, unlikely or no-relevance (independent review repro)", () => {
  const c = cutoffsOf(UNCALIBRATED);
  assert.deepEqual(shownFor("synthetic", { synthetic: 0.9 }, { synthetic: 0.9 }, c), { p: 0.9, band: "estimate", screenedOnly: false });
  for (const p of [0, 0.004, 0.29, 0.3, 0.85, 1]) assert.equal(bandFor(p, c), "estimate", `p=${p}`);
  assert.equal(bandFor(undefined, c), "unscored");
  const display = { a: 0.95, b: 0.5, c: 0 }, rerank = { a: 0.95 };
  assert.equal(shownFor("b", display, rerank, c).band, "estimate", "screened-only stays an estimate, not unlikely");
  assert.deepEqual(rankedIn(display, c, ["high", "mid", "low", "zero"], rerank), [], "nothing lands in a rated list");
  assert.equal(filterKeep("attention", display, c, rerank)("a"), true, "rating filters show everything rather than an empty tree");
  assert.deepEqual(strongestOf(["b", "a"], display, rerank, c), { p: 0.95, band: "estimate", screenedOnly: false });
  assert.equal(BAND_LABEL.estimate, "Estimate only");
  assert.deepEqual(display, { a: 0.95, b: 0.5, c: 0 }, "raw probabilities are untouched");
});

test("bands compare hundredths, as the engine reports them", () => {
  const B = { x: 0.3, y: 0.85 };
  assert.equal(bandFor(0.849, B), "high", "0.849 rounds to 0.85");
  assert.equal(bandFor(0.844, B), "mid");
  assert.equal(bandFor(0.295, B), "mid", "0.295 rounds to 0.30");
  assert.equal(bandFor(0.004, B), "zero", "rounds to 0.00");
});

test("the guard: an article the rerank did not judge is never yellow or red (live NorthCore values)", () => {
  const B = cutoffsOf(LEGACY_PLACEHOLDER);
  const display = { "9.27.3.4.": 0.88, "9.25.1.1.": 0.85, "9.25.5.2.": 0.76, "9.23.17.3.": 0.71, "9.27.3.2.": 0.47, "9.1.1.1.": 0.05 };
  const rerank = { "9.27.3.4.": 0.88, "9.25.1.1.": 0.85, "9.25.5.2.": 0.76, "9.23.17.3.": 0.71 };
  assert.equal(shownFor("9.27.3.4.", display, rerank, B).band, "high");
  assert.equal(shownFor("9.25.1.1.", display, rerank, B).band, "high");
  assert.equal(shownFor("9.25.5.2.", display, rerank, B).band, "mid");
  assert.equal(shownFor("9.23.17.3.", display, rerank, B).band, "mid");
  assert.deepEqual(shownFor("9.27.3.2.", display, rerank, B), { p: 0.47, band: "low", screenedOnly: true });
  assert.equal(shownFor("9.1.1.1.", display, rerank, B).band, "low");
  assert.equal(shownFor("1.1.1.1.", display, rerank, B).band, "unscored");
  assert.deepEqual(rankedIn(display, B, ["mid"], rerank).map((r) => r.id), ["9.25.5.2.", "9.23.17.3."]);
  assert.equal(filterKeep("maybe", display, B, rerank)("9.27.3.2."), false);
  // A section ring takes its strongest shown article: band first, then p.
  assert.deepEqual(strongestOf(["9.27.3.2.", "9.23.17.3."], display, rerank, B), { p: 0.71, band: "mid", screenedOnly: false });
});

const TOC: CodeToc = {
  division: "B",
  edition: "NBC(AE) 2023",
  parts: [
    {
      part: 9,
      title: "Housing and Small Buildings",
      sections: [
        {
          id: "9.27.",
          title: "Cladding",
          articles: [{ id: "9.27.1.1.", title: "Application" }],
          subsections: [
            { id: "9.27.3.", title: "Sheathing Membranes", articles: [{ id: "9.27.3.4.", title: "Insulating Sheathing" }, { id: "9.27.3.5.", title: "Membranes in lieu" }] },
          ],
        },
        { id: "9.25.", title: "Heat Transfer", articles: [], subsections: [{ id: "9.25.2.", title: "Insulation", articles: [{ id: "9.25.2.2.", title: "Insulation Materials" }] }] },
      ],
    },
  ],
};

test("sections show the highest article score, including subsections", () => {
  const display = { "9.27.3.4.": 0.72, "9.27.1.1.": 0.1, "9.25.2.2.": 0.3 };
  assert.equal(maxOf(sectionArticles(TOC.parts[0].sections[0]), display), 0.72);
  assert.equal(maxOf(partArticles(TOC.parts[0]), display), 0.72);
  assert.equal(maxOf(["9.27.3.5."], display), undefined, "an unscored branch has no max");
  assert.equal(maxOf(["9.27.3.4."], undefined), undefined);
});

test("filters prune branches with no matching article", () => {
  const display = { "9.27.3.4.": 0.72, "9.25.2.2.": 0.3 };
  const attention = pruneToc(TOC, filterKeep("attention", display, C));
  assert.deepEqual(attention.parts[0].sections.map((s) => s.id), ["9.27."]);
  assert.deepEqual(attention.parts[0].sections[0].articles, []);
  assert.deepEqual(attention.parts[0].sections[0].subsections[0].articles.map((a) => a.id), ["9.27.3.4."]);
  const maybe = pruneToc(TOC, filterKeep("maybe", display, C));
  assert.deepEqual(maybe.parts[0].sections.map((s) => s.id), ["9.25."]);
  assert.equal(pruneToc(TOC, filterKeep("all", display, C)).parts[0].sections.length, 2);
  assert.deepEqual(rankedIn({ a: 0.61, b: 0.9, c: 0.3, d: 0 }, cutoffsOf(HISTORICAL), ["high", "mid"]).map((r) => r.id), ["b", "a", "c"]);
});

test("tree ancestors auto-expand to an article", () => {
  assert.deepEqual(ancestorsOf(TOC, "9.27.3.4."), ["part-9", "9.27.", "9.27.3."]);
  assert.deepEqual(ancestorsOf(TOC, "9.27.1.1."), ["part-9", "9.27."]);
  assert.deepEqual(ancestorsOf(TOC, "1.1.1.1."), []);
});

test("code library routes parse the article and filter", () => {
  const r = resolveRoute("/code/9.27.3.4.(1)", new URLSearchParams("filter=attention"));
  assert.equal(r.screen, "code");
  assert.equal(r.article, "9.27.3.4.(1)");
  assert.equal(r.filter, "attention");
  assert.equal(resolveRoute("/code", new URLSearchParams()).article, null);
  assert.equal(resolveRoute("/code", new URLSearchParams("filter=bogus")).filter, "");
  assert.equal(codeHref("9.27.3.4."), "#/code/9.27.3.4.");
  assert.equal(codeHref("9.27.3.4.(1)", "maybe"), "#/code/9.27.3.4.(1)?filter=maybe");
  const back = codeHref("9.27.3.4.(1)").replace(/^#/, "");
  assert.equal(resolveRoute(back, new URLSearchParams()).article, "9.27.3.4.(1)");
  assert.equal(resolveRoute("/section-c", new URLSearchParams()).screen, "references");
});

test("code text reflows PDF line breaks but keeps clause markers on their own lines", () => {
  assert.equal(reflow("1) Where sheathing\nis applied,\n2) joints shall\nbe lapped:\na) not less than\n100 mm"), "1) Where sheathing is applied,\n2) joints shall be lapped:\na) not less than 100 mm");
});
