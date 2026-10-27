import { useLayoutEffect, useRef, type ReactNode } from "react";
import { Modal } from "../ui";
import { useLast, usePresence, type Presence } from "./presence";

/** How long the list, the assistant and the phone sheet take to leave (calm.css keeps the same times). */
const EXIT_MS = 200;
/** Unmount a little after the exit ends; the exit holds its last frame meanwhile. */
const UNMOUNT_MS = EXIT_MS + 40;

/**
 * Keeps a panel mounted while it slides out. `display: contents`, so the panel stays the flex item;
 * `inert` while it leaves, so focus and clicks never land on something on its way out.
 */
function Slot({ state, children }: { state: Presence; children: ReactNode }) {
  if (state === "closed") return null;
  return <div className="cf-slot" data-state={state} inert={state === "closing" || undefined}>{children}</div>;
}

/**
 * Rail | list | work area (header over main) | assistant. The assistant is a full-height column
 * beside the work area: it pushes the work area (whose header re-centres its stage icons in the
 * remaining width) and never covers it. With the list collapsed only the rail stays.
 * Under 760px the rail and list move into a sheet opened from the header's sidebar button.
 * The list and the assistant slide in and out, and the work area resizes with them.
 */
export function AppLayout({
  rail,
  list,
  header,
  banner,
  assistant,
  listCollapsed,
  sheetOpen,
  onSheetClose,
  children,
}: {
  rail: ReactNode;
  list?: ReactNode;
  header: ReactNode;
  /** Shown at the top of the work area, above the page (an officer returned the application). */
  banner?: ReactNode;
  assistant?: ReactNode;
  listCollapsed?: boolean;
  sheetOpen?: boolean;
  onSheetClose?: () => void;
  children: ReactNode;
}) {
  const listOpen = Boolean(list) && !listCollapsed;
  const listState = usePresence(listOpen, UNMOUNT_MS);
  const lastList = useLast(list);
  const assistantState = usePresence(Boolean(assistant), UNMOUNT_MS);
  const lastAssistant = useLast(assistant);
  const sheetState = usePresence(Boolean(sheetOpen), UNMOUNT_MS);
  // The last list or assistant only stands in while it slides away; otherwise what is passed now.
  const listNow = listState === "closing" ? lastList : list;
  const sheetList = sheetState === "closing" ? list ?? lastList : sheetState === "closed" ? null : list;
  // Closing the assistant from inside it (Escape, its close button) hands focus back to Ask rather than
  // dropping it on the page body. Runs before the browser drops focus from the inert, leaving panel.
  const assistantWasOpen = useRef(false);
  useLayoutEffect(() => {
    const open = assistantState === "open" || assistantState === "entering";
    if (assistantWasOpen.current && !open) {
      const active = document.activeElement;
      const inside = document.querySelector(".cf-slot > .cf-assist")?.contains(active);
      if (!active || active === document.body || inside) document.querySelector<HTMLElement>(".cf-ask")?.focus({ preventScroll: true });
    }
    assistantWasOpen.current = open;
  }, [assistantState]);
  return (
    <div className="cf-app" data-list={list && !listCollapsed ? "open" : "closed"} data-assistant={assistant ? "open" : "closed"}>
      <div className="cf-sidebar">
        {rail}
        <Slot state={listState}>{listNow}</Slot>
      </div>
      <div className="cf-work">
        {header}
        <main className="cf-main" id="main">
          {banner}
          {children}
        </main>
      </div>
      <Slot state={assistantState}>{assistantState === "closing" ? lastAssistant : assistant}</Slot>
      {onSheetClose && (
        <Modal open={Boolean(sheetOpen)} onClose={onSheetClose} labelledBy="cf-sheet-title" className="cf-nav-sheet">
          <h2 id="cf-sheet-title" className="cf-sr">Navigation</h2>
          <div className="cf-nav-sheet-body" onClick={(e) => { if ((e.target as HTMLElement).closest("a, .cf-list-hit, .cf-list-new")) onSheetClose(); }}>
            {rail}
            {/* Mount the sheet copy only while open (and while it slides away), so the sidebar list keeps the shared ref on desktop. */}
            {sheetList}
          </div>
        </Modal>
      )}
    </div>
  );
}
