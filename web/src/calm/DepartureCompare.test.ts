import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../scripts/component-harness.mjs";

const harness = () => componentHarness(new URL("./DepartureCompare.tsx", import.meta.url), "DepartureCompare", {});

test("the comparison shows the code, the design and the drafted difference; Edit opens the words", async () => {
  let edits = 0;
  const h = await harness();
  const lines = { code: "The unprotected openings shall not exceed 7%.", design: "More window area facing the neighbour.", gap: "The design adds window area this close to the line.", departure: "More window area facing the neighbour." };
  let tree = await h.render({ lines, onEdit: () => { edits++; } });
  assert.deepEqual(nodes(tree, (n) => n.type === "dt").map(text), ["Code", "Your design", "Difference"]);
  assert.equal(text(nodes(tree, (n) => n.type === "blockquote")[0]), lines.code, "code text keeps its own quote style");
  assert.match(text(nodes(tree, (n) => n.props?.className === "cf-compare-gap")[0]), /not code text/, "the drafted line says it is not code text");
  nodes(tree, (n) => n.type === "button" && text(n) === "Edit")[0].props.onClick();
  assert.equal(edits, 1);
  assert.doesNotMatch(text(tree), /complies|meets|safe|acceptable|approved/i);
  tree = await h.render({ lines: { ...lines, code: undefined, gap: undefined }, onEdit: () => {} });
  assert.deepEqual(nodes(tree, (n) => n.type === "dt").map(text), ["Your design"], "no drafted difference, no empty line");
  tree = await h.render({ lines: { ...lines, design: undefined, departure: "" }, onEdit: () => {} });
  assert.deepEqual(nodes(tree, (n) => n.type === "dt").map(text), ["Code", "Difference"], "no words for the design, no design line");
  assert.equal(nodes(tree, (n) => n.type === "button").length, 0, "the card's own action writes it");
  h.unmount();
});
