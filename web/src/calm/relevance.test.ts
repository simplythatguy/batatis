import assert from "node:assert/strict";
import test from "node:test";
import type { CodeToc } from "../api/codeLibrary.ts";
import { reflow, ancestorsOf, bandFor, cutoffsOf, DEFAULT_BANDS, filterKeep, maxOf, partArticles, pruneToc, rankedIn, sectionArticles } from "./relevance.ts";
import { codeHref, resolveRoute } from "./routes.ts";

const C = { x: 0.2, y: 0.6 };

test("band edges: 0 is grey, x is moderate, y is high, missing is not scored", () => {
  assert.equal(bandFor(0, C), "zero");
  assert.equal(bandFor(0.0001, C), "low");
  assert.equal(bandFor(0.1999, C), "low");
  assert.equal(bandFor(0.2, C), "mid");
  assert.equal(bandFor(0.5999, C), "mid");
  assert.equal(bandFor(0.6, C), "high");
  assert.equal(bandFor(1, C), "high");
  assert.equal(bandFor(undefined, C), "unscored");
  assert.equal(bandFor(null, C), "unscored");
  assert.equal(bandFor(Number.NaN, C), "unscored");
});

test("cut-offs come from the response; placeholders only when it has none", () => {
  assert.deepEqual(cutoffsOf({ bands: { x: 0.3, y: 0.7 } }), { x: 0.3, y: 0.7, fallback: false });
  assert.deepEqual(cutoffsOf({ bands: null }), { ...DEFAULT_BANDS, fallback: true });
  assert.deepEqual(cutoffsOf(null), { ...DEFAULT_BANDS, fallback: true });
  assert.equal(cutoffsOf({ bands: { x: 0.7, y: 0.3 } }).fallback, true, "inverted bands are rejected");
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
  assert.deepEqual(rankedIn({ a: 0.61, b: 0.9, c: 0.3, d: 0 }, cutoffsOf(null), ["high", "mid"]).map((r) => r.id), ["b", "a", "c"]);
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
