import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { evaluate, fmt, type RuleDef, type RuleIndex } from "./evaluate.ts";

// The same files the Python evaluator reads: engine/data/rules and evals_dev/rules.
const ROOT = join(dirname(fileURLToPath(import.meta.url)), "../../..");
const read = (path: string) => JSON.parse(readFileSync(join(ROOT, path), "utf8"));
const index: RuleIndex = read("engine/data/rules/index.json");
const rules: Record<string, RuleDef> = Object.fromEntries(index.rules.map((id) => [id, read(`engine/data/rules/${id}.json`)]));
const vectors: { id: string; rule: string; inputs: Record<string, unknown>; expect: Record<string, unknown> }[] =
  read("evals_dev/rules/vectors.json").vectors;
const golden: Record<string, unknown> = read("evals_dev/rules/outputs.json").outputs;

test("every vector gives the expected state, outcome, provision and questions", () => {
  for (const v of vectors) {
    const r = evaluate(rules[v.rule], v.inputs, index);
    const got: Record<string, unknown> = {
      state: r.state, outcome_id: r.outcome_id, provision: r.provision.id, missing: r.missing.map((m) => m.field),
    };
    if ("assumptions" in v.expect) got.assumptions = r.assumptions.length;
    assert.deepEqual(got, v.expect, v.id);
  }
});

test("cross-language agreement: every full output equals the Python evaluator's (outputs.json)", () => {
  assert.deepEqual(Object.keys(golden).sort(), vectors.map((v) => v.id).sort());
  for (const v of vectors) {
    // JSON round trip: the comparison is on the wire form both evaluators produce.
    const ts = JSON.parse(JSON.stringify(evaluate(rules[v.rule], v.inputs, index)));
    assert.deepEqual(ts, golden[v.id], `${v.id}: TypeScript and Python disagree`);
  }
});

test("at least 10 vectors per rule", () => {
  for (const id of index.rules) assert.ok(vectors.filter((v) => v.rule === id).length >= 10, id);
});

test("fmt rounds half up to two decimals like the Python fmt", () => {
  assert.deepEqual([2.1, 2, 0.125, 1.005, 7.066666, 1440, 0.45, -0.5].map(fmt), ["2.1", "2", "0.13", "1", "7.07", "1440", "0.45", "-0.5"]);
});
