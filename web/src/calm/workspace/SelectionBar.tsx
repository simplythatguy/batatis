import { useEffect, useRef, useState } from "react";
import { Icon24 } from "../icons";
import type { DocBlock } from "./document";
import type { PassageSelection } from "./PaperBlock";

const CLEARER = "Make this clearer. Keep every fact, number and citation.";
const SHORTER = "Make this shorter. Keep every fact, number and citation.";

/** Floats over the selected words: Ask about them, or have the AI suggest a rewrite. */
export function SelectionBar({ selection, block, allowRewrite, busy, onAsk, onRewrite, onClose }: {
  selection: PassageSelection; block: DocBlock; allowRewrite: boolean; busy: boolean;
  onAsk: () => void; onRewrite: (instruction: string) => void; onClose: () => void;
}) {
  const [instruction, setInstruction] = useState("");
  const [custom, setCustom] = useState(selection.wholeBlock === true && allowRewrite);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const away = (e: PointerEvent) => { if (e.target instanceof Node && !ref.current?.contains(e.target)) onClose(); };
    const escape = (e: KeyboardEvent) => { if (e.key === "Escape") { e.stopPropagation(); onClose(); } };
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("pointerdown", away); document.removeEventListener("keydown", escape); };
  }, [onClose]);

  // From the keyboard the bar takes focus; when it closes, focus goes back to the words it was about.
  useEffect(() => {
    const node = ref.current;
    if (selection.viaKeyboard) node?.querySelector<HTMLButtonElement>("button")?.focus();
    return () => {
      const active = document.activeElement;
      if (!active || active === document.body || node?.contains(active)) {
        document.getElementById(`aw-text-${block.id}`)?.focus({ preventScroll: true });
      }
    };
  }, [selection.viaKeyboard, block.id]);

  const width = custom ? Math.min(420, window.innerWidth - 24) : undefined;
  const height = custom ? 126 : 44;
  const left = Math.max(12, Math.min(selection.left, window.innerWidth - (width ?? 360) - 12));
  // Above the words; below them when there is no room, and on touch screens, whose own copy menu sits above.
  const below = selection.top - height - 8 < 8 || window.matchMedia("(pointer: coarse)").matches;
  const top = below ? Math.max(8, Math.min(selection.bottom + 8, window.innerHeight - height - 8)) : selection.top - height - 8;

  return (
    <div ref={ref} className="aw-selbar" role="toolbar" aria-label={`Selected words in ${block.label}`} style={{ left, top, width }}
      // Keep the text selection alive while a button (or its icon) is pressed.
      onPointerDown={e => { if (e.target instanceof Element && e.target.closest("button")) e.preventDefault(); }}>
      <div className="aw-selbar-row">
        <button type="button" onClick={onAsk}><Icon24 name="spark" size={14} />Ask</button>
        {allowRewrite && (
          <>
            <span className="aw-selbar-sep" aria-hidden="true" />
            <button type="button" disabled={busy} aria-expanded={custom} onClick={() => setCustom(true)}><Icon24 name="pencil" size={14} />Rewrite</button>
            <button type="button" disabled={busy} onClick={() => onRewrite(CLEARER)}>Clearer</button>
            <button type="button" disabled={busy} onClick={() => onRewrite(SHORTER)}>Shorter</button>
          </>
        )}
        {busy && <span className="aw-selbar-busy" role="status"><span className="cf-dot is-pending cf-pulse" aria-hidden="true" />Writing…</span>}
      </div>
      {custom && allowRewrite && (
        <form className="aw-selbar-form" onSubmit={e => { e.preventDefault(); if (instruction.trim()) onRewrite(instruction.trim()); }}>
          <q className="aw-selbar-quote">{selection.selected.length > 90 ? `${selection.selected.slice(0, 90)}…` : selection.selected}</q>
          <label className="sr-only" htmlFor="aw-rewrite">How should it change?</label>
          <input id="aw-rewrite" placeholder="How should it change?" autoFocus maxLength={300} value={instruction} disabled={busy} onChange={e => setInstruction(e.target.value)} />
          <button type="submit" disabled={busy || !instruction.trim()} aria-label="Suggest a rewrite"><Icon24 name="right" size={14} /></button>
        </form>
      )}
    </div>
  );
}
