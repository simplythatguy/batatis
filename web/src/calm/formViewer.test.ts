import assert from "node:assert/strict";
import { resolveObjectURL } from "node:buffer";
import test from "node:test";
import { componentHarness, nodes, text } from "../../scripts/component-harness.mjs";

class EngineError extends Error { status: number; constructor(status: number) { super("x"); this.status = status; } }
class ExportBlockedError extends EngineError { reasons: string[]; constructor(reasons: string[]) { super(409); this.reasons = reasons; } }

const PDF = "%PDF-1.7 draft bytes";
const page = (n: number) => ({ width: 612, height: 792, image: `data:image/png;base64,${Buffer.from(`page ${n}`).toString("base64")}` });

async function viewer({ locked = false, fail = 0, status = undefined as string | undefined, total = 2, shown = 2 } = {}) {
  const calls: string[] = [];
  let failures = fail, epoch = 1;
  // Saving moves the sync epoch, as the real store does; only a changed answer makes the PDF out of date.
  let c = { facts: [{ field: "owner", value: "Ada", status: "confirmed" }], process: {}, authority: "edmonton", sectionC: [] };
  const store = { engineId: "case_1", get c() { return c; }, get factsEpoch() { return epoch; }, saveDraft: async () => { calls.push("save"); epoch++; return "case_1"; } };
  const h = await componentHarness(new URL("./FormViewer.tsx", import.meta.url), "FormViewer", {
    "../api/client": { EngineError, ExportBlockedError, engine: { exportPreview: async (id: string) => {
      calls.push(`preview ${id}`);
      if (failures-- > 0) throw new EngineError(500);
      return { filename: "x.pdf", pdf: `data:application/pdf;base64,${Buffer.from(PDF).toString("base64")}`,
        page_count: total, pages: Array.from({ length: shown }, (_, i) => page(i + 1)) };
    } } },
    "../store": { useCase: () => store },
    "./ui": { CIcon: "CIcon" },
  }, { URL, Blob, atob });
  let tree = await h.render({ locked, status });
  await new Promise((r) => setTimeout(r, 0));
  tree = await h.render({ locked, status });
  return { h, calls, get tree() { return tree; }, async rerender() { tree = await h.render({ locked, status }); return tree; }, bump() { epoch++; c = { ...c, facts: [{ field: "owner", value: `Ada ${epoch}`, status: "confirmed" }] }; } };
}

const pages = (tree: unknown) => nodes(tree, (n) => n.type === "img");
const opened = async (href: string) => Buffer.from(await resolveObjectURL(href)!.arrayBuffer()).toString();

test("the form is the engine's own draft PDF, drawn as its pages after the draft is saved", async () => {
  const v = await viewer();
  assert.deepEqual(v.calls, ["save", "preview case_1"]);
  const region = nodes(v.tree, (n) => n.props?.role === "region")[0];
  assert.equal(region.props["aria-label"], "Application form, draft PDF");
  assert.equal(region.props.tabIndex, 0, "the page column scrolls from the keyboard");
  assert.deepEqual(pages(v.tree).map((n) => [n.props.src, n.props.alt]), [[page(1).image, "Page 1 of 2"], [page(2).image, "Page 2 of 2"]]);
  assert.equal(nodes(v.tree, (n) => n.type === "iframe").length, 0, "no browser PDF viewer and its dark frame");
  const open = nodes(v.tree, (n) => n.type === "a")[0];
  assert.match(open.props.href, /^blob:/);
  assert.equal(await opened(open.props.href), PDF, "the new tab opens the bytes the pages were drawn from");
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
  assert.deepEqual(v.calls.slice(2), ["save", "preview case_1"]);
  assert.equal(nodes(tree, (n) => n.type === "button" && text(n).includes("Update")).length, 0);
  v.h.unmount();
});

test("pages past the response budget stay one link away in the PDF", async () => {
  const v = await viewer({ total: 30, shown: 2 });
  assert.equal(pages(v.tree).length, 2);
  assert.equal(pages(v.tree)[1].props.alt, "Page 2 of 30");
  const more = nodes(v.tree, (n) => n.type === "a" && text(n).includes("more pages"))[0];
  assert.equal(text(more), "28 more pages in the PDF");
  assert.equal(await opened(more.props.href), PDF);
  const all = await viewer();
  assert.equal(nodes(all.tree, (n) => n.type === "a" && text(n).includes("more")).length, 0, "nothing to add when every page is shown");
  v.h.unmount();
  all.h.unmount();
});

test("a read-only application is shown as saved, without saving", async () => {
  const v = await viewer({ locked: true });
  assert.deepEqual(v.calls, ["preview case_1"]);
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
  assert.equal(pages(tree).length, 2);
  v.h.unmount();
});

test("a sent or closed application keeps its own status apart from the draft PDF on screen", async () => {
  for (const status of ["Sent", "Accepted", "Refused"]) {
    const v = await viewer({ locked: true, status });
    const tree = await v.rerender();
    const bar = nodes(tree, (n) => n.props?.className === "cf-form-bar")[0];
    assert.equal(text(bar).startsWith(`${status}Draft PDF`), true, `${status}: the application's status, then what the file is`);
    assert.match(nodes(tree, (n) => n.props?.role === "region")[0].props["aria-label"], /draft PDF/);
    const open = nodes(tree, (n) => n.type === "a")[0];
    assert.match(open.props["aria-label"], /draft PDF/, "the new tab link says it opens the draft");
    assert.doesNotMatch(text(tree), /official/i, "status never labels the draft bytes official");
    v.h.unmount();
  }
  const draft = await viewer();
  assert.equal(text(nodes(await draft.rerender(), (n) => n.props?.className === "cf-form-bar")[0]).trim().startsWith("Draft PDF"), true, "an editable draft: just the file's label");
  draft.h.unmount();
});
