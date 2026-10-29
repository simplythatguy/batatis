import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../scripts/component-harness.mjs";
import * as filter from "./authorityFilter.ts";
import * as config from "../config.ts";

test("search accepts a known Alberta place and a hamlet absent from the suggestions", async () => {
  const picks: string[] = [];
  const h = await componentHarness(new URL("./AuthorityPicker.tsx", import.meta.url), "AuthorityPicker", { "./authorityFilter": filter, "../config": config });
  const props = { options: config.AUTHORITIES, value: "", label: "Office", onPick: (value: string) => picks.push(value) };
  let tree = await h.render(props);
  const input = () => nodes(tree, (node) => node.type === "input")[0];
  input().props.onChange({ target: { value: "Red Deer" } });
  tree = await h.render(props);
  nodes(tree, (node) => node.props?.role === "option" && text(node) === "Red Deer")[0].props.onClick();
  tree = await h.render(props);
  assert.deepEqual(picks, ["red-deer"]);
  input().props.onChange({ target: { value: "Example Hamlet" } });
  tree = await h.render(props);
  input().props.onKeyDown({ key: "Enter", preventDefault() {} });
  assert.deepEqual(picks, ["red-deer", "Example Hamlet"]);
  h.unmount();
});

test("the site place confirms in one tap and Not sure is a deliberate choice", async () => {
  const picks: string[] = [];
  const h = await componentHarness(new URL("./AuthorityPicker.tsx", import.meta.url), "AuthorityPicker", { "./authorityFilter": filter, "../config": config });
  const props = { options: config.AUTHORITIES, value: "", suggested: { id: "red-deer", name: "Red Deer" }, label: "Office", onPick: (value: string) => picks.push(value) };
  let tree = await h.render(props);
  nodes(tree, (node) => node.type === "button" && text(node) === "Yes, Red Deer")[0].props.onClick();
  tree = await h.render(props);
  nodes(tree, (node) => node.type === "button" && text(node) === "Not sure")[0].props.onClick();
  assert.deepEqual(picks, ["red-deer", "unsure"]);
  tree = await h.render({ ...props, unsure: true });
  assert.equal(nodes(tree, (node) => node.type === "input")[0].props.value, "Not sure");
  h.unmount();
});

test("a known place typed another way is listed once, and an unknown name is offered as typed", async () => {
  const h = await componentHarness(new URL("./AuthorityPicker.tsx", import.meta.url), "AuthorityPicker", { "./authorityFilter": filter, "../config": config });
  const props = { options: config.AUTHORITIES, value: "", label: "Office", onPick: () => {} };
  let tree = await h.render(props);
  const input = () => nodes(tree, (node) => node.type === "input")[0];
  const options = () => nodes(tree, (node) => node.props?.role === "option").map((node) => text(node));
  for (const [typed, first, offeredAsTyped] of [["St. Johns", "St. John's", false], ["Red Deer, AB", "Red Deer", false],
    ["Strathcona", "Strathcona County", true]] as const) {
    input().props.onChange({ target: { value: typed } });
    tree = await h.render(props);
    assert.equal(options()[0], first, typed);
    assert.equal(options().includes(typed), offeredAsTyped, `${typed} offered as typed`);
  }
  input().props.onChange({ target: { value: "Example Hamlet" } });
  tree = await h.render(props);
  assert.ok(options().includes("Example Hamlet"));
  h.unmount();
});
