import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness } from "../../../scripts/component-harness.mjs";

function target() {
  const listeners = new Map<string, Set<() => void>>();
  return {
    listeners,
    addEventListener: (type: string, fn: () => void) => { if (!listeners.has(type)) listeners.set(type, new Set()); listeners.get(type)!.add(fn); },
    removeEventListener: (type: string, fn: () => void) => { listeners.get(type)?.delete(fn); },
    fire: (type: string) => { for (const fn of [...(listeners.get(type) ?? [])]) fn(); },
  };
}

test("a popover closes when the app moves to another page", async () => {
  // QA 2026-10-28: the notifications popover stayed open after moving to other pages.
  const win = target(), doc = target();
  const h = await componentHarness(new URL("./bits.tsx", import.meta.url), "usePopover", {}, { window: win, document: doc });
  let pop = await h.render({}) as unknown as { open: boolean; setOpen: (v: boolean) => void };
  pop.setOpen(true);
  pop = await h.render({}) as unknown as typeof pop;
  assert.equal(pop.open, true);
  win.fire("hashchange");
  pop = await h.render({}) as unknown as typeof pop;
  assert.equal(pop.open, false);
  assert.equal(win.listeners.get("hashchange")?.size, 0);
});
