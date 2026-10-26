import { useEffect, useRef, useState } from "react";
import { Icon24 } from "../icons";
import type { DocBlock } from "./document";
import type { PassageSelection } from "./PaperBlock";

export function SelectionBar({ selection, block, allowRewrite, busy, onAsk, onRewrite, onClose }: {
  selection: PassageSelection; block: DocBlock; allowRewrite: boolean; busy: boolean;
  onAsk: () => void; onRewrite: (instruction: string) => void; onClose: () => void;
}) {
  const [instruction, setInstruction] = useState("");
  const [rewriting, setRewriting] = useState(selection.wholeBlock === true);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const close = (event: PointerEvent) => { if (event.target instanceof Node && !ref.current?.contains(event.target)) onClose(); };
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") { event.stopPropagation(); onClose(); } };
    document.addEventListener("pointerdown", close); document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("pointerdown", close); document.removeEventListener("keydown", escape); };
  }, [onClose]);
  const width = Math.min(440, window.innerWidth - 24);
  return <div ref={ref} className="aw-selection-bar" role="toolbar" aria-label={`Passage actions for ${block.label}`}
    style={{ width, left: Math.max(12, Math.min(selection.left, window.innerWidth - width - 12)), top: Math.max(8, Math.min(selection.top - (rewriting ? 110 : 46), window.innerHeight - (rewriting ? 120 : 60))) }}
    onPointerDown={e => { if (e.target instanceof HTMLButtonElement) e.preventDefault(); }}>
    <div className="aw-selection-actions"><button type="button" onClick={onAsk}><Icon24 name="spark" size={14} />Ask</button>
      {allowRewrite && <><button type="button" disabled={busy} onClick={() => setRewriting(true)}>Rewrite</button><button type="button" disabled={busy} onClick={() => onRewrite("Make this clearer. Preserve all facts and citations.")}>Clearer</button><button type="button" disabled={busy} onClick={() => onRewrite("Make this shorter. Preserve all facts and citations.")}>Shorter</button></>}
      <button type="button" onClick={onClose} aria-label="Close passage actions" title="Close passage actions">×</button>
    </div>
    {rewriting && allowRewrite && <form className="aw-rewrite-form" onSubmit={e => { e.preventDefault(); if (instruction.trim()) onRewrite(instruction.trim()); }}><label className="sr-only" htmlFor="aw-rewrite-instruction">How should the passage change?</label><input id="aw-rewrite-instruction" placeholder="How should it change?" autoFocus maxLength={300} value={instruction} disabled={busy} onChange={e => setInstruction(e.target.value)} /><button type="submit" disabled={busy || !instruction.trim()}>{busy ? "Rewriting…" : "Rewrite"}</button></form>}
  </div>;
}
