import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../scripts/component-harness.mjs";
import * as filter from "./authorityFilter.ts";
import * as config from "../config.ts";

test("search picks a supported office, and never picks another place", async () => {
  const picks: string[] = [];
  const h = await componentHarness(new URL("./AuthorityPicker.tsx", import.meta.url), "AuthorityPicker", { "./authorityFilter": filter, "../config": config });
  const props = { options: config.AUTHORITIES, value: "", label: "Office", onPick: (value: string) => picks.push(value) };
  let tree = await h.render(props);
  const input = () => nodes(tree, (node) => node.type === "input")[0];
  input().props.onChange({ target: { value: "Edmonton" } });
  tree = await h.render(props);
  nodes(tree, (node) => node.props?.role === "option" && text(node) === "Edmonton")[0].props.onClick();
  tree = await h.render(props);
  assert.deepEqual(picks, ["edmonton"]);
  input().props.onChange({ target: { value: "Example Hamlet" } });
  tree = await h.render(props);
  input().props.onKeyDown({ key: "Enter", preventDefault() {} });
  assert.deepEqual(picks, ["edmonton"], "Enter on another place picks nothing, not even Not sure");
  h.unmount();
});

test("the site place confirms in one tap and Not sure is a deliberate choice", async () => {
  const picks: string[] = [];
  const h = await componentHarness(new URL("./AuthorityPicker.tsx", import.meta.url), "AuthorityPicker", { "./authorityFilter": filter, "../config": config });
  const props = { options: config.AUTHORITIES, value: "", suggested: { id: "calgary", name: "Calgary" }, label: "Office", onPick: (value: string) => picks.push(value) };
  let tree = await h.render(props);
  nodes(tree, (node) => node.type === "button" && text(node) === "Yes, Calgary")[0].props.onClick();
  tree = await h.render(props);
  nodes(tree, (node) => node.type === "button" && text(node) === "Not sure")[0].props.onClick();
  assert.deepEqual(picks, ["calgary", "unsure"]);
  tree = await h.render({ ...props, unsure: true });
  assert.equal(nodes(tree, (node) => node.type === "input")[0].props.value, "Not sure");
  h.unmount();
});

test("a supported office typed another way is listed once, and any other place says at once it is not covered", async () => {
  const h = await componentHarness(new URL("./AuthorityPicker.tsx", import.meta.url), "AuthorityPicker", { "./authorityFilter": filter, "../config": config });
  const props = { options: config.AUTHORITIES, value: "", label: "Office", onPick: () => {} };
  let tree = await h.render(props);
  const input = () => nodes(tree, (node) => node.type === "input")[0];
  const options = () => nodes(tree, (node) => node.props?.role === "option").map((node) => text(node));
  for (const [typed, first] of [["Calgary, AB", "Calgary"], ["city of edmonton", "Edmonton"]] as const) {
    input().props.onChange({ target: { value: typed } });
    tree = await h.render(props);
    assert.equal(options()[0], first, typed);
    assert.ok(!options().includes(typed), `${typed} is not offered again as typed`);
  }
  input().props.onChange({ target: { value: "Red Deer" } });
  tree = await h.render(props);
  assert.deepEqual(options(), ["Not sure"]);
  const note = () => nodes(tree, (node) => node.type === "li" && node.props?.role === "presentation").map((node) => text(node));
  assert.deepEqual(note(), ["Batatis prepares applications only for Calgary and Edmonton."]);
  // The paperwork form's field offers only offices; its row has Later instead of Not sure.
  tree = await h.render({ ...props, compact: true });
  assert.deepEqual(options(), []);
  assert.deepEqual(note(), ["Batatis prepares applications only for Calgary and Edmonton."]);
  h.unmount();
});

test("an empty Office field names the offices Batatis prepares applications for", async () => {
  const h = await componentHarness(new URL("./AuthorityPicker.tsx", import.meta.url), "AuthorityPicker", { "./authorityFilter": filter, "../config": config });
  const tree = await h.render({ options: config.AUTHORITIES, value: "", label: "Office", onPick: () => {} });
  assert.equal(nodes(tree, (node) => node.type === "input")[0].props.placeholder, "Calgary or Edmonton");
  h.unmount();
});
