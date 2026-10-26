import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../scripts/component-harness.mjs";
import * as units from "./units.ts";

test("the feet toggle sends an explicit unit and a pasted measurement retains its words", async () => {
  let value = "";
  const props = () => ({ id: "distance", label: "Distance", unit: "m", value, onChange: (next: string) => { value = next; } });
  const h = await componentHarness(new URL("./UnitInput.tsx", import.meta.url), "UnitInput", { "./units": units });
  let tree = await h.render(props());
  const button = (name: string) => nodes(tree, (node) => node.type === "button" && text(node) === name)[0];
  const input = () => nodes(tree, (node) => node.type === "input")[0];
  button("ft").props.onClick();
  tree = await h.render(props());
  input().props.onChange({ target: { value: "4" } });
  tree = await h.render(props());
  assert.equal(value, "4 ft");
  assert.equal(input().props.value, "4");
  assert.match(text(tree), /= 1\.22 m/);
  input().props.onChange({ target: { value: "4 feet" } });
  tree = await h.render(props());
  assert.equal(value, "4 feet");
  assert.equal(button("ft").props["aria-pressed"], true);
  input().props.onChange({ target: { value: "1.2 m" } });
  tree = await h.render(props());
  assert.equal(button("m").props["aria-pressed"], true);
  assert.equal(value, "1.2 m");
  h.unmount();
});

test("bad units have an accessible inline error, and a reloaded answer replaces the draft", async () => {
  let value = '13\'6"';
  const props = () => ({ label: "Distance", unit: "m", value, onChange: (next: string) => { value = next; } });
  const h = await componentHarness(new URL("./UnitInput.tsx", import.meta.url), "UnitInput", { "./units": units });
  let tree = await h.render(props());
  assert.match(text(tree), /= 4\.11 m/);
  nodes(tree, (node) => node.type === "input")[0].props.onChange({ target: { value: "4 bananas" } });
  tree = await h.render(props());
  assert.equal(nodes(tree, (node) => node.type === "input")[0].props["aria-invalid"], true);
  assert.ok(nodes(tree, (node) => node.props?.role === "alert").length);
  value = "2 m";
  tree = await h.render(props());
  assert.equal(nodes(tree, (node) => node.type === "input")[0].props.value, "2 m");
  assert.match(text(tree), /= 2 m/);
  h.unmount();
});
