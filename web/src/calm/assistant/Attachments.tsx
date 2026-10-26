import { useEffect, useId, useRef, useState } from "react";
import { Icon24 } from "../icons";
import { ToolButton } from "./ToolButton";
import { attachExisting, attachFiles, beginAttachPick, canAttach, MAX_ATTACHMENTS, removeAttachment, type AssistantState, type AttachPick } from "./assistant";

/** The selected PDFs, by actual stored file id. Coverage appears with each document reply. */
export function Attachments({ a }: { a: AssistantState }) {
  const list = a.conv.attachments;
  if (a.binding.mode !== "case" || !list.length) return null;
  return (
    <div className="cf-av-files">
      <span className="cf-av-files-label" title="Chat can find exact text excerpts. Up to three text-bearing pages per PDF; scans and images aren’t read.">
        <Icon24 name="clip" size={12} />Selected PDFs
      </span>
      {list.map((x) => (
        <span key={x.key} className={`cf-av-file is-${x.status}`} title={x.error ? `${x.name} · ${x.error}` : x.name}>
          <Icon24 name="clip" size={12} />
          <span className={`cf-av-file-name${x.status === "uploading" ? " cf-av-shimmer" : ""}`}>{x.name}</span>
          {x.status === "uploading" && <span className="cf-sr" role="status">Uploading</span>}
          {x.error && <span className="cf-av-file-error">{x.error}</span>}
          <ToolButton type="button" className="cf-av-file-x" aria-label={`Unselect ${x.name}`} title="Unselect PDF · keeps the stored file" onClick={() => removeAttachment(x.key)}><Icon24 name="x" size={12} /></ToolButton>
        </span>
      ))}
    </div>
  );
}

/** Add a PDF from this application, or upload one through its authorized file route. */
export function AttachButton({ a }: { a: AssistantState }) {
  const file = useRef<HTMLInputElement>(null);
  /** The application lifetime the open chooser belongs to; its files go nowhere else. */
  const pickFor = useRef<AttachPick | null>(null);
  const root = useRef<HTMLSpanElement>(null);
  const menuId = useId();
  const [menu, setMenu] = useState(false);
  const b = a.binding;
  const close = (focus = false) => { setMenu(false); if (focus) root.current?.querySelector<HTMLButtonElement>("button")?.focus(); };
  useEffect(() => { setMenu(false); }, [b.accountId, b.role, b.authority, b.caseId]);
  useEffect(() => {
    if (!menu) return;
    root.current?.querySelector<HTMLButtonElement>('[role="menuitem"]')?.focus();
    const outside = (e: PointerEvent) => { if (e.target instanceof Node && !root.current?.contains(e.target)) setMenu(false); };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [menu]);
  if (b.mode !== "case" || !canAttach()) return null;
  const list = a.conv.attachments;
  const live = list.filter((x) => x.status !== "failed").length;
  const known = new Map([...b.files, ...a.conv.uploaded].map((f) => [f.id, f]));
  const existing = [...known.values()].filter((f) => !list.some((x) => x.fileId === f.id && x.status !== "failed"));
  if (!b.canUpload && !existing.length) return null;
  const full = live >= MAX_ATTACHMENTS;
  const choose = () => { pickFor.current = beginAttachPick(); file.current?.click(); };
  const pick = () => (existing.length ? setMenu((m) => !m) : choose());
  const label = full ? `Up to ${MAX_ATTACHMENTS} selected PDFs` : existing.length ? "Select a PDF" : "Upload a PDF";
  return (
    <span ref={root} className="cf-av-add" onKeyDown={(e) => {
      if (menu && e.key === "Escape") { e.stopPropagation(); e.preventDefault(); close(true); return; }
      if (!existing.length || full) return;
      if (!menu && (e.key === "ArrowDown" || e.key === "ArrowUp")) { e.preventDefault(); setMenu(true); return; }
      if (!menu || !["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key)) return;
      e.preventDefault();
      const items = [...(root.current?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]') ?? [])];
      const current = items.indexOf(document.activeElement as HTMLButtonElement);
      const next = e.key === "Home" ? 0 : e.key === "End" ? items.length - 1 : (current + (e.key === "ArrowUp" ? -1 : 1) + items.length) % items.length;
      items[next]?.focus();
    }}>
      <ToolButton type="button" className="cf-icon-btn is-plain" aria-label={label} title={label} disabled={full} aria-haspopup={existing.length ? "menu" : undefined} aria-controls={menu ? menuId : undefined} aria-expanded={existing.length ? menu : undefined} onClick={pick}>
        <Icon24 name="clip" size={16} />
      </ToolButton>
      {menu && (
        <div id={menuId} className="cf-av-menu" role="menu" aria-label="Application PDFs">
          {existing.map((f) => (
            <button key={f.id} type="button" role="menuitem" onClick={() => { attachExisting(f.id, f.name); close(true); }}>
              <Icon24 name="file" size={14} /><span>{f.name}</span>
            </button>
          ))}
          {b.canUpload && (
            <button type="button" role="menuitem" onClick={() => { close(true); choose(); }}>
              <Icon24 name="up" size={14} /><span>Upload a PDF…</span>
            </button>
          )}
        </div>
      )}
      <input ref={file} type="file" accept="application/pdf,.pdf" multiple hidden onChange={(e) => {
        const files = [...(e.target.files ?? [])];
        e.target.value = "";
        const openedFor = pickFor.current;
        pickFor.current = null;
        if (openedFor) void attachFiles(files, openedFor);
      }} />
    </span>
  );
}
