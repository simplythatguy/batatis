import type { ReactNode } from "react";
import { Modal } from "../ui";

/**
 * Rail | list | work area (header over main) | assistant. The assistant is a full-height column
 * beside the work area: it pushes the work area (whose header re-centres its stage icons in the
 * remaining width) and never covers it. With the list collapsed only the rail stays.
 * Under 760px the rail and list move into a sheet opened from the header's sidebar button.
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
  return (
    <div className="cf-app" data-list={list && !listCollapsed ? "open" : "closed"} data-assistant={assistant ? "open" : "closed"}>
      <div className="cf-sidebar">
        {rail}
        {list && !listCollapsed && list}
      </div>
      <div className="cf-work">
        {header}
        <main className="cf-main" id="main">
          {banner}
          {children}
        </main>
      </div>
      {assistant}
      {onSheetClose && (
        <Modal open={Boolean(sheetOpen)} onClose={onSheetClose} labelledBy="cf-sheet-title" className="cf-nav-sheet">
          <h2 id="cf-sheet-title" className="cf-sr">Navigation</h2>
          <div className="cf-nav-sheet-body" onClick={(e) => { if ((e.target as HTMLElement).closest("a, .cf-list-hit, .cf-list-new")) onSheetClose(); }}>
            {rail}
            {/* Mount the sheet copy only while open, so the sidebar list keeps the shared ref on desktop. */}
            {sheetOpen && list}
          </div>
        </Modal>
      )}
    </div>
  );
}
