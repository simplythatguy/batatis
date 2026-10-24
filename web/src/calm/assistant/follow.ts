/**
 * Keeps the conversation pinned to its end while the person is there (after Irsal's
 * hooks/use-chat-follow.ts at 5dd3f93). `following` is the single source of truth: only the
 * person's own wheel, touch, key or scrollbar movement unpins it, so programmatic glides and late
 * layout growth never read as "reading history". Returning within PIN_DISTANCE of the end pins it
 * again. New content eases to the end over a few frames; reduced motion jumps.
 *
 * The controller is plain TypeScript over a scroll node (the DOM element in the app, a fake in
 * tests). Reading positions are kept per conversation so switching applications or closing the
 * panel comes back to the same place.
 */

export const PIN_DISTANCE = 40;

export interface ScrollNode {
  scrollTop: number;
  readonly scrollHeight: number;
  readonly clientHeight: number;
  addEventListener(type: string, fn: EventListener, opts?: boolean | AddEventListenerOptions): void;
  removeEventListener(type: string, fn: EventListener): void;
}

export interface FollowDeps {
  raf(fn: () => void): number;
  caf(id: number): void;
  now(): number;
  reduced(): boolean;
  /** For the scrollbar's pointerup, which lands outside the node. */
  onWindow(type: "pointerup", fn: () => void): () => void;
}

export interface ReadingPosition {
  following: boolean;
  /** Appended replies must not move someone reading an earlier message. */
  scrollTop: number;
}

export class ChatFollow {
  following = true;
  private frame = 0;
  private intentUntil = 0;
  private holding = false;
  private readonly node: ScrollNode;
  private readonly deps: FollowDeps;
  private readonly changed: (following: boolean, distance: number) => void;

  constructor(node: ScrollNode, deps: FollowDeps, changed: (following: boolean, distance: number) => void = () => {}) {
    this.node = node;
    this.deps = deps;
    this.changed = changed;
  }

  distance(): number {
    const n = this.node;
    return Math.max(0, n.scrollHeight - n.scrollTop - n.clientHeight);
  }

  stop() {
    if (this.frame) this.deps.caf(this.frame);
    this.frame = 0;
  }

  private glide = () => {
    this.frame = 0;
    if (!this.following) return;
    const n = this.node;
    const target = Math.max(0, n.scrollHeight - n.clientHeight);
    const gap = target - n.scrollTop;
    if (gap <= 1) {
      n.scrollTop = target;
      this.changed(true, 0);
      return;
    }
    n.scrollTop += Math.max(1, Math.ceil(gap * 0.28));
    this.frame = this.deps.raf(this.glide);
  };

  /** Ease to the end (only while following, unless `force`). Reduced motion or `instant` jumps. */
  toEnd(instant = false, force = false) {
    if (force) {
      this.following = true;
      this.intentUntil = 0;
      this.holding = false;
    }
    if (!this.following) return;
    if (instant || this.deps.reduced()) {
      this.stop();
      this.node.scrollTop = this.node.scrollHeight;
      this.changed(true, 0);
      return;
    }
    if (!this.frame) this.frame = this.deps.raf(this.glide);
  }

  /** Content grew or arrived: follow it if pinned; never move a reader. */
  grew() {
    if (this.following) this.toEnd();
    else this.changed(false, this.distance());
  }

  /** A scroll happened (anyone's). Only the person's own scrolling can unpin. */
  observe() {
    const distance = this.distance();
    if (distance <= PIN_DISTANCE) this.following = true;
    else if (this.holding || this.deps.now() < this.intentUntil) {
      this.following = false;
      this.stop();
    }
    this.changed(this.following, distance);
  }

  position(): ReadingPosition {
    return { following: this.following, scrollTop: this.node.scrollTop };
  }

  /** Land on a saved reading position (or the end) at once: a restored conversation never animates. */
  restore(pos: ReadingPosition | undefined) {
    this.stop();
    const n = this.node;
    if (!pos || pos.following) {
      this.following = true;
      n.scrollTop = n.scrollHeight;
    } else {
      this.following = false;
      n.scrollTop = Math.max(0, Math.min(pos.scrollTop, n.scrollHeight - n.clientHeight));
      if (this.distance() <= PIN_DISTANCE) this.following = true;
    }
    this.changed(this.following, this.distance());
  }

  /** Listen for the person's own scrolling. Returns the cleanup. */
  attach(): () => void {
    const n = this.node;
    const intent = (ms: number) => { this.intentUntil = Math.max(this.intentUntil, this.deps.now() + ms); };
    const unpin = () => {
      this.following = false;
      this.stop();
      this.changed(false, this.distance());
    };
    const wheel = (e: Event) => {
      intent(250);
      if ((e as WheelEvent).deltaY < 0) unpin();
    };
    const touchstart = () => { this.holding = true; intent(250); };
    // Momentum continues after the finger lifts.
    const touchend = () => { this.holding = false; intent(1200); };
    const keydown = (e: Event) => {
      if ((e.target as unknown) !== n) return;
      const key = (e as KeyboardEvent).key;
      if (["ArrowUp", "PageUp", "Home"].includes(key)) { intent(600); unpin(); }
      else if (["ArrowDown", "PageDown", "End", " "].includes(key)) intent(600);
    };
    // Dragging the scrollbar targets the scroller itself.
    const pointerdown = (e: { target: unknown }) => { if (e.target === n) this.holding = true; };
    const pointerup = () => {
      if (!this.holding) return;
      this.holding = false;
      intent(300);
    };
    const scroll = () => this.observe();
    n.addEventListener("wheel", wheel as EventListener, { passive: true });
    n.addEventListener("touchstart", touchstart, { passive: true });
    n.addEventListener("touchend", touchend, { passive: true });
    n.addEventListener("touchcancel", touchend, { passive: true });
    n.addEventListener("keydown", keydown as EventListener);
    n.addEventListener("pointerdown", pointerdown as EventListener);
    n.addEventListener("scroll", scroll, { passive: true });
    const offUp = this.deps.onWindow("pointerup", pointerup);
    return () => {
      this.stop();
      n.removeEventListener("wheel", wheel as EventListener);
      n.removeEventListener("touchstart", touchstart);
      n.removeEventListener("touchend", touchend);
      n.removeEventListener("touchcancel", touchend);
      n.removeEventListener("keydown", keydown as EventListener);
      n.removeEventListener("pointerdown", pointerdown as EventListener);
      n.removeEventListener("scroll", scroll);
      offUp();
    };
  }
}

// —— Reading positions per conversation (visit-local; cleared with the account) ——————————————

const positions = new Map<string, ReadingPosition>();

export function savedPosition(key: string): ReadingPosition | undefined {
  return positions.get(key);
}

export function savePosition(key: string, pos: ReadingPosition) {
  if (key === "none") return;
  positions.delete(key);
  positions.set(key, pos);
  if (positions.size > 24) positions.delete(positions.keys().next().value as string);
}

export function forgetPositions() {
  positions.clear();
}
