import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../../scripts/component-harness.mjs";
import type { DocBlock } from "./document.ts";

const block: DocBlock = { id: "process.risk_assessment", section: "case", label: "Risk", text: "Original", target: { kind: "process", field: "risk" }, required: true, missing: false, requests: [] };
async function editor(locked = false) {
  const writes: string[][] = [], commits: string[] = [];
  const h = await componentHarness(new URL("./PaperBlock.tsx", import.meta.url), "PaperBlock", {
    "../applications": { authorityName: (name: string) => name }, "../icons": { Icon24: "Icon24" }, "../ui": { CIcon: "CIcon", Dot: "Dot", MoreIcon: "MoreIcon" },
    "./suggestions": { acceptable: () => true, canRewrite: () => true, changedWords: (before: string, after: string) => ({ prefix: "", removed: before, added: after, suffix: "" }) },
  }, { document: { addEventListener() {}, removeEventListener() {} }, requestAnimationFrame: (fn: () => void) => fn() });
  const props = { block, locked, suggestions: [], onEdit: (_block: DocBlock, before: string, after: string) => writes.push([before, after]), onCommit: (id: string) => commits.push(id), onSelect() {}, onAsk() {}, onAccept() {}, onReject() {}, onReference() {} };
  const tree = await h.render(props);
  return { h, tree, writes, commits, props };
}
test("composition stays local until it ends, then blur commits exactly the composed plain text", async () => {
  const e = await editor(), area = nodes(e.tree, n => n.type === "textarea")[0];
  area.props.onCompositionStart();
  area.props.onChange({ target: { value: "危" } });
  assert.deepEqual(e.writes, []);
  area.props.onCompositionEnd({ currentTarget: { value: "危険" } });
  area.props.onChange({ target: { value: "危険" } });
  assert.deepEqual(e.writes, [["Original", "危険"]]);
  area.props.onBlur({ currentTarget: { value: "危険" } });
  assert.deepEqual(e.commits, [block.id]);
  e.h.unmount();
});
test("read-only paper has no caret, keeps Ask and removes every writing or acceptance control", async () => {
  const e = await editor(true);
  const tree = await e.h.render({ ...e.props, suggestions: [{ id: "s", blockId: block.id, origin: "rewrite", before: "Original", after: "AI words" }] });
  assert.equal(nodes(tree, n => n.type === "textarea").length, 0);
  assert.match(text(tree), /Original/); assert.match(text(tree), /Ask/); assert.match(text(tree), /AI suggestion/);
  assert.equal(nodes(tree, n => n.type === "button" && /Accept|Reject|Rewrite|Write it/.test(text(n))).length, 0);
  e.h.unmount();
});
