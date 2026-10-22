import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { checkReport, dateText, figureView, intervalText, percent, sourceText, type Figure } from "./report.ts";

const RAW = JSON.parse(readFileSync(new URL("../../../docs/accuracy/report.json", import.meta.url), "utf8"));

test("the bundled report reads, and every figure renders with its value, n, date and source", () => {
  const r = checkReport(RAW);
  assert.ok(r.guaranteed.length >= 8, "the guaranteed claims");
  assert.ok(r.measured.length >= 6, "the measured sections");
  let figures = 0;
  for (const s of r.measured) {
    for (const f of s.figures) {
      const v = figureView(f);
      figures += 1;
      assert.match(v.value, /^\d+(\.\d)? of \d+$/, `${f.id} value`);
      assert.ok(v.meta.includes(f.sample) && v.meta.includes(f.dataset), `${f.id} meta`);
      assert.ok(v.source.includes(f.source.commit.slice(0, 7)), `${f.id} source names its commit`);
      if (f.interval) assert.match(v.interval ?? "", /^95% interval \d/, `${f.id} interval`);
      assert.doesNotMatch(v.label + v.meta + v.source, /undefined|null|NaN/, f.id);
    }
  }
  assert.ok(figures >= 20, `figures: ${figures}`);
  for (const c of r.guaranteed) assert.ok(c.tests.every((t) => t.file && t.name), c.id);
});

test("code identification is marked provisional or not run until the benchmark is finished", () => {
  const code = checkReport(RAW).measured.find((s) => s.id === "code-id");
  assert.ok(code, "the code identification section");
  if (code.status === "not_run") assert.equal(code.figures.length, 0, "no number without a run");
  if (code.status === "provisional") {
    assert.ok(code.caveats.some((c) => c.startsWith("Provisional")), "says why it is provisional");
    const product = code.figures.find((f) => f.id === "codeid.product");
    assert.ok(product?.tags.includes("provisional"), "the headline figure carries the label");
  }
});

test("a figure without a source, or a claim without a test, is refused", () => {
  const broken = structuredClone(RAW);
  broken.measured[0].figures[0].source = { kind: "file", paths: [], commit: "" };
  assert.throws(() => checkReport(broken), /has no source/);
  const untested = structuredClone(RAW);
  untested.guaranteed[0].tests = [];
  assert.throws(() => checkReport(untested), /names no test/);
  assert.throws(() => checkReport({ schema: "other" }), /unknown format/);
});

test("numbers and dates read plainly", () => {
  assert.equal(percent(1), "100%");
  assert.equal(percent(0.98148), "98.1%");
  assert.equal(percent(0), "0%");
  assert.equal(dateText("2026-10-21"), "21 Oct 2026");
  assert.equal(dateText("2026-10-21 to 2026-10-22"), "21 Oct 2026 to 22 Oct 2026");
  const f = { interval: [0.9764, 1] } as unknown as Figure;
  assert.equal(intervalText(f), "95% interval 97.6–100%");
  assert.equal(sourceText({ kind: "pr", pr: 54, commit: "d13e2d6ce680" }), "PR #54 description, merge commit d13e2d6");
});
