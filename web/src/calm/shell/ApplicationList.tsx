import { forwardRef, useCallback, useEffect, useId, useImperativeHandle, useRef, useState, type ReactNode } from "react";
import type { ApplicationSummary } from "../../api/accounts";
import { groupApplications, statusLine } from "../applications";
import { Icon24 } from "../icons";
import { MOD_KEY } from "../ui";
import type { MenuAnchor } from "./placement";
import { pointAnchor, rectAnchor, RowMenu, type RowAction } from "./RowMenu";
import { RowPreview } from "./RowPreview";

export interface ApplicationListHandle {
  focusSearch: () => void;
}

type Line = { text: string; tone: string; attention: boolean; unread?: number };

/** What a row needs from the list: open its menu, show or hide its preview. */
interface RowHooks {
  menuOpenFor: string | null;
  openMenu?: (a: ApplicationSummary, anchor: MenuAnchor, trigger: HTMLElement) => void;
  hover: (a: ApplicationSummary, row: HTMLElement, how: "pointer" | "focus") => void;
  leave: () => void;
  previewId: string | null;
  previewFor: string | null;
}

const isMenuKey = (e: React.KeyboardEvent) => e.key === "ContextMenu" || (e.shiftKey && e.key === "F10");

/**
 * One row: title and one context line, soft fill when selected. Unread officer messages read as a
 * message icon and the count at the right; the words are for screen readers and the preview.
 * Right-click, the ⋯ button and Shift+F10 open the same menu.
 */
function Row({ a, selected, onSelect, line, hooks }: { a: ApplicationSummary; selected: boolean; onSelect: (id: string) => void; line?: Line; hooks: RowHooks }) {
  const l: Line = line ?? statusLine(a);
  const unread = l.unread ?? 0;
  const name = a.title || "Untitled application";
  const pinned = a.pinned && !a.archived;
  const { openMenu } = hooks;
  return (
    <li
      className={`cf-list-row${selected ? " is-selected" : ""}`}
      data-status={a.status}
      onContextMenu={openMenu ? (e) => { e.preventDefault(); openMenu(a, pointAnchor(e.clientX, e.clientY), e.currentTarget.querySelector<HTMLElement>(".cf-list-hit") ?? e.currentTarget); } : undefined}
      onPointerEnter={(e) => { if (e.pointerType === "mouse") hooks.hover(a, e.currentTarget, "pointer"); }}
      onPointerLeave={(e) => { if (e.pointerType === "mouse") hooks.leave(); }}
    >
      <button
        type="button"
        className="cf-list-hit"
        aria-current={selected ? "page" : undefined}
        aria-describedby={hooks.previewFor === a.id && hooks.previewId ? hooks.previewId : undefined}
        onClick={() => { hooks.leave(); onSelect(a.id); }}
        onKeyDown={openMenu ? (e) => { if (isMenuKey(e)) { e.preventDefault(); openMenu(a, rectAnchor(e.currentTarget, "start"), e.currentTarget); } } : undefined}
        onFocus={(e) => hooks.hover(a, e.currentTarget.parentElement ?? e.currentTarget, "focus")}
        onBlur={() => hooks.leave()}
      >
        <span className="cf-list-title">
          {pinned && <span className="cf-list-pin" aria-hidden="true"><Icon24 name="pin" size={12} stroke={1.8} /></span>}
          {name}
        </span>
        <span className={`cf-list-line is-${l.tone}${l.attention ? " is-attention" : ""}`}>
          {unread > 0 ? (
            <>
              <span className="cf-list-unread" aria-hidden="true"><Icon24 name="msg" size={13} />{unread}</span>
              <span className="cf-sr">{l.text}</span>
            </>
          ) : l.text}
          {pinned && <span className="cf-sr"> · Pinned</span>}
        </span>
      </button>
      {openMenu && (
        <div className="cf-list-actions">
          <button
            type="button"
            className="cf-list-more"
            aria-label={`Options for ${name}`}
            title="Options"
            aria-haspopup="menu"
            aria-expanded={hooks.menuOpenFor === a.id}
            onClick={(e) => openMenu(a, rectAnchor(e.currentTarget, "end"), e.currentTarget)}
          >
            <Icon24 name="more" size={18} />
          </button>
        </div>
      )}
    </li>
  );
}

const PREVIEW_DELAY = 450;
/** After a preview closes, the next row's opens at once for this long (moving down the list). */
const PREVIEW_WARM = 400;
/** Time to move the pointer from the row onto the preview. */
const PREVIEW_GRACE = 200;
const finePointer = () => typeof window !== "undefined" && window.matchMedia?.("(hover: hover) and (pointer: fine)").matches;

/**
 * Email-client style list of applications: search, New application, pinned rows, active rows, a
 * quiet Settled group, and an Archived shelf (collapsed, with its count) at the foot.
 */
export const ApplicationList = forwardRef<ApplicationListHandle, {
  title?: string;
  items: ApplicationSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onNew?: () => void;
  loading?: boolean;
  error?: string;
  /** Shown above the rows (for example "Saved for this visit only."). */
  note?: ReactNode;
  empty?: ReactNode;
  /** The row menu (⋯, right-click, Shift+F10). An empty list hides the ⋯. */
  actionsFor?: (a: ApplicationSummary) => RowAction[];
  lineFor?: (a: ApplicationSummary) => Line;
}>(function ApplicationList({ title = "Applications", items, selectedId, onSelect, onNew, loading, error, note, empty, actionsFor, lineFor }, ref) {
  const [query, setQuery] = useState("");
  const [shelfOpen, setShelfOpen] = useState(false);
  const search = useRef<HTMLInputElement>(null);
  const aside = useRef<HTMLElement>(null);
  useImperativeHandle(ref, () => ({ focusSearch: () => search.current?.focus() }), []);
  const { pinned, active, settled, archived } = groupApplications(items, query);
  const shelfId = useId();
  const previewId = useId();

  // An application archived while open stays selected: the shelf opens so the row stays in view.
  const selectedArchived = archived.some((a) => a.id === selectedId);
  useEffect(() => { if (selectedArchived) setShelfOpen(true); }, [selectedArchived]);
  const shelfShown = shelfOpen || Boolean(query.trim());

  const [menu, setMenu] = useState<{ id: string; anchor: MenuAnchor; trigger: HTMLElement } | null>(null);
  const menuApp = menu ? items.find((a) => a.id === menu.id) ?? null : null;
  const menuNow = useRef(menu);
  menuNow.current = menu;
  const closeMenu = useCallback((refocus: boolean) => {
    const m = menuNow.current;
    setMenu(null);
    if (m && refocus && m.trigger.isConnected) m.trigger.focus({ preventScroll: true });
  }, []);

  const [preview, setPreview] = useState<{ id: string; row: HTMLElement } | null>(null);
  const previewApp = preview && !menu ? items.find((a) => a.id === preview.id) ?? null : null;
  const timer = useRef(0);
  const warmUntil = useRef(0);
  const shown = useRef(false);
  shown.current = Boolean(previewApp);
  const hover = useCallback((a: ApplicationSummary, row: HTMLElement, how: "pointer" | "focus") => {
    window.clearTimeout(timer.current);
    if (row.closest("dialog")) return;
    if (how === "pointer" ? !finePointer() : !row.querySelector(".cf-list-hit:focus-visible")) return;
    const delay = how === "focus" || shown.current || Date.now() < warmUntil.current ? 0 : PREVIEW_DELAY;
    timer.current = window.setTimeout(() => setPreview({ id: a.id, row }), delay);
  }, []);
  const leave = useCallback(() => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      if (shown.current) warmUntil.current = Date.now() + PREVIEW_WARM;
      setPreview(null);
    }, PREVIEW_GRACE);
  }, []);
  const hidePreview = useCallback(() => { window.clearTimeout(timer.current); setPreview(null); }, []);
  useEffect(() => () => window.clearTimeout(timer.current), []);
  // Escape dismisses the preview without moving focus; scrolling or pressing anywhere hides it.
  useEffect(() => {
    if (!previewApp) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") hidePreview(); };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", hidePreview, true);
    window.addEventListener("blur", hidePreview);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", hidePreview, true);
      window.removeEventListener("blur", hidePreview);
    };
  }, [previewApp, hidePreview]);

  const hooks = (a: ApplicationSummary): RowHooks => ({
    menuOpenFor: menu?.id ?? null,
    openMenu: actionsFor && actionsFor(a).length
      ? (row, anchor, trigger) => {
          hidePreview();
          setMenu((m) => (m?.id === row.id && trigger.classList.contains("cf-list-more") ? null : { id: row.id, anchor, trigger }));
        }
      : undefined,
    hover,
    leave,
    previewId,
    previewFor: previewApp?.id ?? null,
  });
  const row = (a: ApplicationSummary) => <Row key={a.id} a={a} selected={a.id === selectedId} onSelect={onSelect} line={lineFor?.(a)} hooks={hooks(a)} />;
  const nothing = !pinned.length && !active.length && !settled.length && !archived.length;

  return (
    <aside ref={aside} className="cf-list" aria-label={title}>
      <div className="cf-list-head">
        <h2>{title}</h2>
        <div className="cf-list-tools">
          {onNew && (
            <button type="button" className="cf-icon-btn is-plain cf-list-new" aria-label="New application" title="New application" onClick={onNew}>
              <Icon24 name="compose" size={17} />
            </button>
          )}
        </div>
      </div>
      <label className="cf-list-search">
        <Icon24 name="search" size={15} />
        <span className="cf-sr">Search applications</span>
        <input ref={search} type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search applications" onKeyDown={(e) => { if (e.key === "Escape") { setQuery(""); e.currentTarget.blur(); } }} />
        <span className="cf-kbd is-dark" aria-hidden="true">{MOD_KEY} K</span>
      </label>
      <div className="cf-list-scroll" onScroll={hidePreview}>
        {note && <div className="cf-applist-note" role="status">{note}</div>}
        {error && <p className="cf-applist-note is-error" role="status">{error}</p>}
        {loading && !items.length && <p className="cf-applist-note" role="status">Loading applications…</p>}
        {!loading && !items.length && !error && (empty ?? <p className="cf-applist-note">No applications yet.</p>)}
        {query && nothing && items.length > 0 && <p className="cf-applist-note">Nothing matches “{query}”.</p>}
        {pinned.length > 0 && <ul className="cf-list-rows is-pinned" aria-label="Pinned">{pinned.map(row)}</ul>}
        <ul className="cf-list-rows">{active.map(row)}</ul>
        {settled.length > 0 && (
          <>
            <div className="cf-list-group">Settled</div>
            <ul className="cf-list-rows is-settled">{settled.map(row)}</ul>
          </>
        )}
        {archived.length > 0 && (
          <div className="cf-list-shelf">
            <button type="button" className="cf-list-shelf-btn" aria-expanded={shelfShown} aria-controls={shelfId} onClick={() => setShelfOpen((v) => !v)}>
              <Icon24 name="archive" size={15} />
              <span>Archived</span>
              <span className="cf-list-shelf-count">{archived.length}</span>
              <span className="cf-list-shelf-chev" aria-hidden="true"><Icon24 name="chevRight" size={14} /></span>
            </button>
            {shelfShown && <ul id={shelfId} className="cf-list-rows is-settled is-archived" aria-label="Archived">{archived.map(row)}</ul>}
          </div>
        )}
      </div>
      {menu && menuApp && actionsFor && aside.current && (
        <RowMenu
          label={`Options for ${menuApp.title || "Untitled application"}`}
          actions={actionsFor(menuApp)}
          anchor={menu.anchor}
          trigger={menu.trigger}
          container={aside.current}
          onClose={closeMenu}
        />
      )}
      {previewApp && preview && aside.current && (
        <RowPreview id={previewId} app={previewApp} row={preview.row} sidebar={aside.current} onPointerEnter={() => window.clearTimeout(timer.current)} onPointerLeave={leave} />
      )}
    </aside>
  );
});
