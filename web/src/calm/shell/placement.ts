/**
 * Where the sidebar's row menu and row preview go. Pure, so the bounds can be tested without a browser.
 * The menu stays inside the sidebar (never wider than it, never past its left or right edge) and
 * inside the viewport; the preview sits to the sidebar's right only when it fits.
 */

export interface Box {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

export interface Size {
  width: number;
  height: number;
}

/**
 * `x`/`y`: where the menu wants its corner. `flipY`: the edge to open upward from when it does not
 * fit below (the ⋯ button's top, or the pointer). `align: "end"` lines the menu's right edge up with `x`.
 */
export interface MenuAnchor {
  x: number;
  y: number;
  flipY: number;
  align: "start" | "end";
}

export interface MenuPlacement {
  left: number;
  top: number;
  width: number;
  maxHeight: number;
}

export const EDGE = 8;

export function placeMenu(anchor: MenuAnchor, natural: Size, sidebar: Box, viewport: Size, gap = EDGE): MenuPlacement {
  const minX = Math.max(sidebar.left, 0) + gap;
  const maxX = Math.min(sidebar.right, viewport.width) - gap;
  const width = Math.max(0, Math.min(natural.width, maxX - minX));
  const wantLeft = anchor.align === "end" ? anchor.x - width : anchor.x;
  const left = Math.max(minX, Math.min(wantLeft, maxX - width));
  const minY = Math.max(sidebar.top, 0) + gap;
  const maxY = Math.min(sidebar.bottom, viewport.height) - gap;
  const maxHeight = Math.max(0, maxY - minY);
  const height = Math.min(natural.height, maxHeight);
  const top = anchor.y + height <= maxY ? anchor.y : anchor.flipY - height;
  return { left, top: Math.max(minY, Math.min(top, maxY - height)), width, maxHeight };
}

/** Beside the sidebar, top aligned with the row; null when there is no room on the right. */
export function placePreview(row: Box, sidebar: Box, size: Size, viewport: Size, gap = EDGE): { left: number; top: number } | null {
  const left = sidebar.right + gap;
  if (left + size.width > viewport.width - gap) return null;
  const top = Math.max(gap, Math.min(row.top, viewport.height - size.height - gap));
  return { left, top };
}
