import { useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { ApplicationSummary } from "../../api/accounts";
import { previewFacts } from "../applications";
import { Icon24 } from "../icons";
import { placePreview } from "./placement";

/**
 * A quiet card to the right of the sidebar while a row is hovered or keyboard-focused: the real
 * name, status, authority, reviewer, answered count, unread messages and last update. Not shown
 * when there is no room beside the sidebar (phones, the navigation sheet).
 */
export function RowPreview({ id, app, row, sidebar, onPointerEnter, onPointerLeave }: {
  id: string;
  app: ApplicationSummary;
  row: HTMLElement;
  sidebar: HTMLElement;
  onPointerEnter: () => void;
  onPointerLeave: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ left: number; top: number } | null | undefined>(undefined);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    setPos(placePreview(row.getBoundingClientRect(), sidebar.getBoundingClientRect(), { width: el.offsetWidth, height: el.offsetHeight }, { width: window.innerWidth, height: window.innerHeight }));
  }, [app, row, sidebar]);
  if (pos === null) return null;
  return createPortal(
    <div
      ref={ref}
      id={id}
      role="tooltip"
      className="cf-row-preview"
      style={pos ? { left: pos.left, top: pos.top } : { left: -9999, top: 0, visibility: "hidden" }}
      onPointerEnter={onPointerEnter}
      onPointerLeave={onPointerLeave}
    >
      <p className="cf-row-preview-title">{app.title || "Untitled application"}</p>
      <ul>
        {previewFacts(app).map((f) => (
          <li key={f.icon}>
            <Icon24 name={f.icon} size={14} />
            <span>{f.text}</span>
          </li>
        ))}
      </ul>
    </div>,
    document.body,
  );
}
