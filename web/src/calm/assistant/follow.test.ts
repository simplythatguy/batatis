import assert from "node:assert/strict";
import { test } from "node:test";
import { ChatFollow, type ScrollNode } from "./follow";

function fixture(reduced = false) {
  let top = 0, time = 0, seq = 0;
  const frames = new Map<number, () => void>();
  const listeners = new Map<string, EventListener>();
  const node: ScrollNode & { scrollHeight: number } = {
    scrollHeight: 1000, clientHeight: 300,
    get scrollTop() { return top; },
    set scrollTop(value) { top = Math.max(0, Math.min(value, this.scrollHeight - this.clientHeight)); },
    addEventListener(type, fn) { listeners.set(type, fn); },
    removeEventListener(type) { listeners.delete(type); },
  };
  const follow = new ChatFollow(node, {
    raf(fn) { const id = ++seq; frames.set(id, fn); return id; }, caf(id) { frames.delete(id); },
    now: () => time, reduced: () => reduced, onWindow: () => () => {},
  });
  const detach = follow.attach();
  const event = (name: string, values = {}) => listeners.get(name)?.({ target: node, ...values } as Event);
  const tick = () => { const all = [...frames.values()]; frames.clear(); time += 16; all.forEach((fn) => fn()); };
  const settle = () => { for (let i = 0; frames.size && i < 100; i++) tick(); assert.equal(frames.size, 0); };
  return { node, follow, event, tick, settle, detach, frames };
}

test("new replies ease to the end without programmatic scrolling unpinning", () => {
  const f = fixture(); f.follow.restore(undefined);
  assert.equal(f.node.scrollTop, 700);
  f.node.scrollHeight += 500; f.follow.grew(); f.tick();
  assert.ok(f.node.scrollTop > 700 && f.node.scrollTop < 1200);
  f.event("scroll"); assert.equal(f.follow.following, true);
  f.settle(); assert.equal(f.node.scrollTop, 1200);
});

test("reading history stops the glide and survives replies, close and application switches", () => {
  const f = fixture(); f.follow.restore(undefined); f.node.scrollHeight += 500; f.follow.grew();
  f.event("wheel", { deltaY: -120 }); f.node.scrollTop = 250; f.event("scroll");
  const position = f.follow.position(); f.detach();
  f.node.scrollHeight += 1000; f.follow.restore(position); f.follow.grew(); f.settle();
  assert.equal(f.node.scrollTop, 250); assert.equal(f.follow.following, false);
  f.follow.toEnd(false, true); f.settle(); assert.equal(f.node.scrollTop, 2200);
});

test("touch and keyboard reading are respected; returning to the end pins again", () => {
  const f = fixture(); f.follow.restore(undefined);
  f.event("touchstart"); f.node.scrollTop = 200; f.event("scroll"); f.event("touchend");
  assert.equal(f.follow.following, false);
  f.node.scrollTop = 680; f.event("scroll"); assert.equal(f.follow.following, true);
  f.event("keydown", { key: "Home" }); f.node.scrollTop = 0; f.event("scroll");
  assert.equal(f.follow.following, false);
});

test("reduced motion jumps; detaching cancels scheduled motion", () => {
  const f = fixture(true); f.follow.restore(undefined); f.node.scrollHeight += 200; f.follow.grew();
  assert.equal(f.node.scrollTop, 900); assert.equal(f.frames.size, 0);
  const g = fixture(); g.follow.restore(undefined); g.node.scrollHeight += 200; g.follow.grew(); g.detach();
  assert.equal(g.frames.size, 0);
});

test("Latest immediately after a wheel or touch gesture cancels old intent before its own scroll events", () => {
  for (const gesture of ["wheel", "touchstart"]) {
    const f = fixture(); f.follow.restore(undefined);
    f.event(gesture, { deltaY: -100 }); f.node.scrollTop = 100; f.event("scroll");
    f.follow.toEnd(false, true);
    for (let i = 0; f.frames.size && i < 100; i++) { f.tick(); f.event("scroll"); }
    assert.equal(f.node.scrollTop, 700); assert.equal(f.follow.following, true);
  }
});
