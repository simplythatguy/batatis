import assert from "node:assert/strict";
import test from "node:test";
import { albertaDate, inkBounds } from "./signature.ts";

test("signature cropping keeps exactly the drawn alpha bounds and detects an empty pad", () => {
  const data = new Uint8ClampedArray(8 * 6 * 4);
  assert.equal(inkBounds(data, 8, 6), null);
  data[(2 * 8 + 3) * 4 + 3] = 255; data[(4 * 8 + 6) * 4 + 3] = 1;
  assert.deepEqual(inkBounds(data, 8, 6), { x: 3, y: 2, width: 4, height: 3 });
});
test("signature dates follow the Alberta calendar day at midnight UTC in autumn and winter", () => {
  assert.equal(albertaDate(new Date("2026-10-26T01:00:00Z")), "2026-10-25");
  assert.equal(albertaDate(new Date("2026-12-01T01:30:00Z")), "2026-11-30");
});
