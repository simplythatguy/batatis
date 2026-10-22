import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Icon24, type IconName } from "../icons";
import { placeMenu, type MenuAnchor, type MenuPlacement } from "./placement";

export interface RowAction {
  id: string;
  label: string;
  icon: IconName;
  onSelect: () => void;
  disabled?: boolean;
  /** Why it is unavailable, a word or two shown at the item's right. */
  hint?: string;
  destructive?: boolean;
  separatorBefore?: boolean;
}

/** Anchor at the pointer (right-click). */
export const pointAnchor = (x: number, y: number): MenuAnchor => ({ x, y, flipY: y, align: "start" });

/** Anchor under an element: the ⋯ button lines up its right edge, a row its left. */
export function rectAnchor(el: Element, align: MenuAnchor["align"]): MenuAnchor {
  const r = el.getBoundingClientRect();
  return { x: align === "end" ? r.right : r.left + 12, y: r.bottom + 4, flipY: r.top - 4, align };
}

/**
 * The row menu, one for the ⋯ button, right-click and Shift+F10 / the context-menu key. Rendered
 * inside the sidebar list and kept inside its measured box (see placement.ts), so it is never
 * wider than the sidebar and never crosses its left edge. Arrow keys, Home and End move; Escape
 * and Tab close and return focus to what opened it; a pointer outside or a scroll closes it.
 */
export function RowMenu({ label, actions, anchor, trigger, container, onClose }: {
  label: string;
  actions: RowAction[];
  anchor: MenuAnchor;
  /** What opened it. A menu button toggles the menu through its own click, so a press on it is not "outside". */
  trigger: HTMLElement;
  /** The sidebar list: the menu's bounds and its positioning parent. */
  container: HTMLElement;
  /** `refocus`: return focus to the trigger (keyboard close, or an item chosen). */
  onClose: (refocus: boolean) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [place, setPlace] = useState<MenuPlacement | null>(null);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const box = container.getBoundingClientRect();
    // Measured boxes are in zoomed pixels and styles are not (CSS zoom); convert between the two.
    const k = box.width ? container.offsetWidth / box.width : 1;
    const p = placeMenu(anchor, { width: el.offsetWidth / k, height: el.scrollHeight / k }, box, { width: window.innerWidth, height: window.innerHeight });
    // Positioned inside the list, so its coordinates are the list's.
    setPlace({ left: (p.left - box.left) * k, top: (p.top - box.top) * k, width: p.width * k, maxHeight: p.maxHeight * k });
  }, [anchor, container]);

  useEffect(() => {
    if (place) ref.current?.querySelector<HTMLElement>("[role=menuitem]:not([aria-disabled=true])")?.focus({ preventScroll: true });
  }, [place !== null]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const outside = (e: Event) => {
      const toggle = trigger.getAttribute("aria-haspopup") === "menu" && trigger.contains(e.target as Node);
      if (ref.current?.contains(e.target as Node) || toggle) return;
      onClose(false);
    };
    const scrolled = (e: Event) => { if (!ref.current?.contains(e.target as Node)) onClose(false); };
    const resized = () => onClose(false);
    document.addEventListener("pointerdown", outside, true);
    document.addEventListener("contextmenu", outside, true);
    container.addEventListener("scroll", scrolled, true);
    window.addEventListener("resize", resized);
    window.addEventListener("blur", resized);
    return () => {
      document.removeEventListener("pointerdown", outside, true);
      document.removeEventListener("contextmenu", outside, true);
      container.removeEventListener("scroll", scrolled, true);
      window.removeEventListener("resize", resized);
      window.removeEventListener("blur", resized);
    };
  }, [container, trigger, onClose]);

  function onKey(e: React.KeyboardEvent) {
    const items = [...(ref.current?.querySelectorAll<HTMLElement>("[role=menuitem]:not([aria-disabled=true])") ?? [])];
    const at = items.indexOf(document.activeElement as HTMLElement);
    const to = (n: number) => { e.preventDefault(); items[(n + items.length) % items.length]?.focus(); };
    if (e.key === "ArrowDown") to(at + 1);
    else if (e.key === "ArrowUp") to(at < 0 ? -1 : at - 1);
    else if (e.key === "Home") to(0);
    else if (e.key === "End") to(items.length - 1);
    else if (e.key === "Escape" || e.key === "Tab") {
      e.preventDefault();
      // The shell's own Escape handlers (sheet, assistant) must not also run.
      e.nativeEvent.stopImmediatePropagation();
      e.stopPropagation();
      onClose(true);
    }
  }

  return (
    <div
      ref={ref}
      className="cf-row-menu"
      role="menu"
      aria-label={label}
      onKeyDown={onKey}
      onContextMenu={(e) => e.preventDefault()}
      style={place ? { left: place.left, top: place.top, width: place.width, maxHeight: place.maxHeight } : { left: 0, top: 0, visibility: "hidden" }}
    >
      {actions.map((a) => (
        <div key={a.id} role="none">
          {a.separatorBefore && <hr role="separator" />}
          <button
            type="button"
            role="menuitem"
            tabIndex={-1}
            className={a.destructive ? "is-destructive" : undefined}
            aria-disabled={a.disabled || undefined}
            onClick={() => {
              if (a.disabled) return;
              onClose(true);
              a.onSelect();
            }}
          >
            <Icon24 name={a.icon} size={16} />
            <span className="cf-row-menu-label">{a.label}</span>
            {a.hint && <span className="cf-row-menu-hint">{a.hint}</span>}
          </button>
        </div>
      ))}
    </div>
  );
}
