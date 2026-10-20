import assert from "node:assert/strict";
import { unwrapList } from "../src/api/client.ts";

const rows = [{ id: "9.10.15.5." }];
assert.deepEqual(unwrapList({ items: rows, meta: { notice: "n" } }), rows);
assert.deepEqual(unwrapList(rows), rows);
const plan = { items: rows, meta: { notice: "n" }, provisions: ["9.10.15.5."] };
assert.equal(unwrapList(plan), plan);
console.log("unwrap-list ok");
