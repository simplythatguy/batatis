import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../scripts/component-harness.mjs";

class EngineError extends Error { status: number; constructor(status: number) { super("x"); this.status = status; } }
class ExportBlockedError extends EngineError { reasons: string[]; constructor(reasons: string[]) { super(409); this.reasons = reasons; } }

async function viewer({ locked = false, fail = 0 } = {}) {
  const calls: string[] = [];
  let failures = fail, epoch = 1;
  // Saving moves the sync epoch, as the real store does; only a changed answer makes the PDF out of date.
  let c = { facts: [{ field: "owner", value: "Ada", status: "confirmed" }], process: {}, authority: "edmonton", sectionC: [] };
  const store = { engineId: "case_1", get c() { return c; }, get factsEpoch() { return epoch; }, saveDraft: async () => { calls.push("save"); epoch++; return "case_1"; } };
  const h = await componentHarness(new URL("./FormViewer.tsx", import.meta.url), "FormViewer", {
    "../api/client": { EngineError, ExportBlockedError, engine: { exportPdf: async (id: string, draft: boolean) => {
      calls.push(`export ${id} draft=${draft}`);
      if (failures-- > 0) throw new EngineError(500);
      return { blob: new Blob(["%PDF-1.7"], { type: "application/pdf" }), filename: "x.pdf", notice: "" };
    } } },
    "../store": { useCase: () => store },
    "./ui": { CIcon: "CIcon" },
  }, { URL, Blob });
  let tree = await h.render({ locked });
  await new Promise((r) => setTimeout(r, 0));
  tree = await h.render({ locked });
  return { h, calls, get tree() { return tree; }, async rerender() { tree = await h.render({ locked }); return tree; }, bump() { epoch++; c = { ...c, facts: [{ field: "owner", value: `Ada ${epoch}`, status: "confirmed" }] }; } };
}

test("the form is the engine's own draft PDF, filled after the draft is saved", async () => {
  const v = await viewer();
  assert.deepEqual(v.calls, ["save", "export case_1 draft=true"]);
  const frame = nodes(v.tree, (n) => n.type === "iframe")[0];
  assert.match(frame.props.src, /^blob:.*#toolbar=0/);
  assert.equal(frame.props.title, "Application form, draft PDF");
  assert.match(text(v.tree), /Draft/);
  assert.equal(nodes(await v.rerender(), (n) => n.type === "button" && text(n).includes("Update")).length, 0, "its own save does not make it out of date");
  assert.doesNotMatch(JSON.stringify(v.tree), /cf-sheet|Official/, "no drawn imitation and no official claim");
  // An answer changed: Update makes a new one.
  v.bump();
  let tree = await v.rerender();
  const update = nodes(tree, (n) => n.type === "button" && text(n).includes("Update"))[0];
  assert.ok(update);
  update.props.onClick();
  await new Promise((r) => setTimeout(r, 0));
  tree = await v.rerender();
  assert.deepEqual(v.calls.slice(2), ["save", "export case_1 draft=true"]);
  assert.equal(nodes(tree, (n) => n.type === "button" && text(n).includes("Update")).length, 0);
  v.h.unmount();
});

test("a read-only application is shown as saved, without saving", async () => {
  const v = await viewer({ locked: true });
  assert.deepEqual(v.calls, ["export case_1 draft=true"]);
  v.bump();
  assert.equal(nodes(await v.rerender(), (n) => n.type === "button" && text(n).includes("Update")).length, 0);
  v.h.unmount();
});

test("a failed fill says so and can be tried again", async () => {
  const v = await viewer({ fail: 1 });
  const alert = nodes(v.tree, (n) => n.props?.role === "alert")[0];
  assert.match(text(alert), /didn’t load/);
  nodes(alert, (n) => n.type === "button" && text(n) === "Try again")[0].props.onClick();
  await new Promise((r) => setTimeout(r, 0));
  const tree = await v.rerender();
  assert.ok(nodes(tree, (n) => n.type === "iframe").length);
  v.h.unmount();
});
