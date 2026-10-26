import assert from "node:assert/strict";
import test from "node:test";
import { parseMeasurement } from "./units.ts";

test("a distance in feet is converted before it can become a metric fact", () => {
  const answer = parseMeasurement("4 ft", "m");
  assert.equal(answer.kind, "value");
  if (answer.kind !== "value") return;
  assert.equal(answer.value, 1.2192);
  assert.equal(answer.quote, "4 ft");
});

for (const [text, unit, expected] of [
  ["4 feet", "m", 1.2192], ["4'", "m", 1.2192], ["4 ft 6 in", "m", 1.3716], ["4 feet and 6 inches", "m", 1.3716],
  ['13\'6"', "m", 4.1148], ["1.2 m", "m", 1.2], ["120 cm", "m", 1.2], ["1500 mm", "m", 1.5],
  ["1500 sq ft", "m²", 139.35456], ["140 m²", "m²", 140], ["4 ft", "mm", 1219.2], ["1 m²", "cm²", 10000],
] as const) test(`${text} is stored as ${expected} ${unit}`, () => {
  const parsed = parseMeasurement(text, unit);
  assert.equal(parsed.kind, "value");
  if (parsed.kind === "value") assert.equal(parsed.value, expected);
});

test("the selected unit applies only when no unit was typed", () => {
  assert.deepEqual(parseMeasurement("4", "m", "ft"), { kind: "value", value: 1.2192, quote: "4", enteredUnit: "ft" });
  const explicit = parseMeasurement("4 m", "m", "ft");
  assert.equal(explicit.kind === "value" && explicit.value, 4);
});

test("unknown units, wrong dimensions and trailing garbage never become metric facts", () => {
  for (const text of ["garbage", "4 yards", "4ft garbage", "4 m high", "Infinity", "-4 ft", '4\'12"', "4 m²"]) {
    assert.equal(parseMeasurement(text, "m").kind, "error", text);
  }
  assert.equal(parseMeasurement("4 ft", "m²").kind, "error");
  assert.equal(parseMeasurement(`${"9".repeat(400)} ft 6 in`, "m").kind, "error");
  assert.equal(parseMeasurement("", "m").kind, "empty");
});
