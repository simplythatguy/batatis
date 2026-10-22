import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../../scripts/component-harness.mjs";

const key = (k: string, extra = {}) => ({ key: k, preventDefault() {}, stopPropagation() {}, nativeEvent: { isComposing: false }, ...extra });

async function editor(props: Record<string, unknown>) {
  const h = await componentHarness(new URL("./EditableTitle.tsx", import.meta.url), "EditableTitle", { "../rename": { TITLE_MAX: 500 } });
  let tree = await h.render(props);
  const api = {
    tree: () => tree,
    async rerender(next?: Record<string, unknown>) { tree = await h.render(next ?? props); return tree; },
    button: () => nodes(tree, (n) => n.type === "button" && String(n.props.className ?? "").startsWith("cf-title"))[0],
    input: () => nodes(tree, (n) => n.type === "input")[0],
    unmount: () => h.unmount(),
  };
  return api;
}

test("the name renames in place: double-click or F2, Enter saves one trimmed line, Escape cancels", async () => {
  const saved: string[] = [];
  const e = await editor({ value: "Infill sheathing", label: "Application name", onCommit: async (t: string) => { saved.push(t); return null; } });
  assert.equal(e.button().props.title, "Double-click to rename · F2");
  e.button().props.onDoubleClick();
  await e.rerender();
  assert.equal(e.input().props.value, "Infill sheathing", "edits the current name; no selection, caret at the end");
  assert.equal(e.input().props["aria-label"], "Application name");
  e.input().props.onChange({ target: { value: "  Rear   deck  guard " } });
  await e.rerender();
  e.input().props.onKeyDown(key("Escape"));
  await e.rerender();
  assert.equal(saved.length, 0, "Escape keeps the old name");
  assert.equal(text(e.button()), "Infill sheathing");
  e.button().props.onKeyDown(key("F2"));
  await e.rerender();
  e.input().props.onChange({ target: { value: "  Rear   deck  guard " } });
  await e.rerender();
  e.input().props.onKeyDown(key("Enter"));
  await e.rerender();
  assert.deepEqual(saved, ["Rear deck guard"]);
  // Unchanged or empty names save nothing.
  e.button().props.onDoubleClick();
  await e.rerender();
  e.input().props.onChange({ target: { value: "   " } });
  await e.rerender();
  e.input().props.onBlur();
  await e.rerender();
  assert.deepEqual(saved, ["Rear deck guard"]);
  e.unmount();
});

test("a failed save puts the old name back and keeps the typed one for Retry", async () => {
  let fail = true;
  const calls: string[] = [];
  const e = await editor({ value: "Infill sheathing", label: "Application name", onCommit: async (t: string) => { calls.push(t); return fail ? "Renaming isn’t available on this server yet." : null; } });
  e.button().props.onDoubleClick();
  await e.rerender();
  e.input().props.onChange({ target: { value: "Rear deck guard" } });
  await e.rerender();
  e.input().props.onBlur();
  const tree = await e.rerender();
  assert.equal(text(e.button()), "Infill sheathing", "the saved name stays until a save succeeds");
  const alert = nodes(tree, (n) => n.props?.role === "alert")[0];
  assert.match(text(alert), /isn’t available/);
  fail = false;
  nodes(alert, (n) => n.type === "button" && text(n) === "Retry")[0].props.onClick();
  await e.rerender();
  assert.deepEqual(calls, ["Rear deck guard", "Rear deck guard"], "Retry sends the kept name");
  assert.equal(nodes(e.tree(), (n) => n.props?.role === "alert").length, 0);
  e.unmount();
});

test("a sent or closed application shows its name as plain text", async () => {
  const e = await editor({ value: "Infill sheathing", label: "Application name", disabled: true, onCommit: async () => null });
  assert.equal(e.button(), undefined);
  assert.equal(text(e.tree()), "Infill sheathing");
  e.unmount();
});

test("the header shows only the name, never the city", async () => {
  const h = await componentHarness(new URL("./AppHeader.tsx", import.meta.url), "AppHeader", {
    "../icons": { Icon24: "Icon24" }, "../RelevanceRing": { Tip: "Tip" }, "./EditableTitle": { EditableTitle: "EditableTitle" },
  });
  const tree = await h.render({ title: "Infill sheathing", onRename: async () => null });
  h.unmount();
  const h1 = nodes(tree, (n) => n.type === "h1")[0];
  const title = nodes(h1, (n) => n.type === "EditableTitle")[0];
  assert.equal(title.props.value, "Infill sheathing");
  assert.doesNotMatch(JSON.stringify(h1.props), /Edmonton|Calgary/);
});

test("rename errors say what happened in plain words", async () => {
  const { titleError } = await import("../rename.ts");
  const { EngineError } = await import("../../api/client.ts");
  assert.equal(titleError(new EngineError(422, "too long")), "Use a name of 1 to 500 characters.");
  assert.equal(titleError(new EngineError(403, "sent")), "A sent or closed application can’t be renamed.");
  assert.equal(titleError(new EngineError(404, "Not Found")), "Renaming isn’t available on this server yet.");
  assert.equal(titleError(new EngineError(404, "case not found")), "This application no longer exists.");
  assert.equal(titleError(new EngineError(409, "conflict")), "The application changed somewhere else. Try again.");
});

test("a new case is created without the placeholder name; a chosen one is sent", async () => {
  const store = new Map<string, string>();
  const bodies: unknown[] = [];
  Object.assign(globalThis, {
    sessionStorage: { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => store.set(k, v), removeItem: (k: string) => store.delete(k) },
    fetch: async (_url: string, init?: { body?: string }) => { bodies.push(JSON.parse(init?.body ?? "{}")); return new Response(JSON.stringify({ id: `case_${bodies.length}`, version: 1, jurisdiction: null }), { status: 201 }); },
  });
  const sync = await import("../../api/sync.ts");
  sync.clearEngineSession();
  await sync.ensureEngineCase(null, "");
  sync.clearEngineSession();
  await sync.ensureEngineCase("Infill sheathing", "");
  assert.equal("title" in (bodies[0] as object), false);
  assert.equal((bodies[1] as { title: string }).title, "Infill sheathing");
});

test("a reopened case keeps its saved name", async () => {
  const { caseFromEngine } = await import("../openCase.ts");
  const c = caseFromEngine({ id: "case_1", title: "Infill sheathing", version: 3, facts: [{ id: "d", field: "project.description", value: "A long description of a two-storey house in Edmonton.", kind: "pointed", status: "confirmed", confidence: null, formula: null, inputs: [], source: { type: "user_text", ref: "Your description", quote: "A long description of a two-storey house in Edmonton.", page: null, bbox: null } }], provisions: [], jurisdiction: null, evidence: [], gaps: [], section_c: [] } as never, "homebuilder");
  assert.equal(c.title, "Infill sheathing");
  assert.equal(c.titleKept, true);
});
