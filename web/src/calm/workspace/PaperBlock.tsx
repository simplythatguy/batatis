import { useEffect, useLayoutEffect, useRef, useState, type SyntheticEvent } from "react";
import { authorityName } from "../applications";
import { Icon24 } from "../icons";
import { CIcon, Dot, MoreIcon } from "../ui";
import type { DocBlock } from "./document";
import { canRewrite, changedWords, type Passage, type Suggestion } from "./suggestions";

export interface PassageSelection extends Passage { selected: string; left: number; top: number; wholeBlock?: boolean }
export const textId = (id: string) => `aw-text-${id}`;
export const blockId = (id: string) => `aw-block-${id}`;

export function PaperBlock({ block, locked, aiAccepted, suggestions, code, onEdit, onCommit, onSelect, onAsk, onAccept, onReject, onReference }: {
  block: DocBlock; locked: boolean; aiAccepted?: string; suggestions: Suggestion[]; code?: { text: string; citation: string };
  onEdit: (block: DocBlock, before: string, after: string) => void; onCommit: (id: string) => void;
  onSelect: (selection: PassageSelection | null) => void; onAsk: (block: DocBlock, passage?: string) => void;
  onAccept: (suggestion: Suggestion) => void; onReject: (suggestion: Suggestion) => void; onReference: (candidateId: string) => void;
}) {
  const textarea = useRef<HTMLTextAreaElement>(null), menu = useRef<HTMLDetailsElement>(null);
  const [value, setValue] = useState(block.text);
  const [menuUp, setMenuUp] = useState(false);
  const composing = useRef(false), sent = useRef(block.text);
  const editable = block.target.kind !== "card" && !locked;
  useEffect(() => {
    if (!composing.current && sent.current !== block.text) { sent.current = block.text; setValue(block.text); }
  }, [block.text]);
  useLayoutEffect(() => {
    const el = textarea.current;
    if (el) { el.style.height = "0px"; el.style.height = `${Math.max(el.scrollHeight, 24)}px`; }
  }, [value, editable]);
  useEffect(() => {
    const close = (event: globalThis.PointerEvent) => { if (event.target instanceof Node && !menu.current?.contains(event.target)) menu.current?.removeAttribute("open"); };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, []);

  function publish(after: string) {
    setValue(after);
    if (after === sent.current || locked) return;
    const before = sent.current; sent.current = after;
    onEdit(block, before, after);
  }
  function select(event: SyntheticEvent<HTMLTextAreaElement>) {
    if (composing.current) return;
    const el = event.currentTarget, start = el.selectionStart, end = el.selectionEnd;
    if (start === end) { onSelect(null); return; }
    const rect = el.getBoundingClientRect();
    onSelect({ blockId: block.id, text: el.value, start, end, selected: el.value.slice(start, end), left: rect.left, top: rect.top });
  }
  function wholeBlock() {
    menu.current?.removeAttribute("open");
    const rect = document.getElementById(blockId(block.id))?.getBoundingClientRect();
    onSelect({ blockId: block.id, text: block.text, start: 0, end: 0, selected: block.text, wholeBlock: true, left: rect?.left ?? 16, top: rect?.top ?? 100 });
  }
  const reference = block.reference;
  const diff = suggestions.map(s => ({ suggestion: s, change: changedWords(s.before, s.after) }));
  return <div id={blockId(block.id)} className={`aw-block${block.target.kind === "process" || block.id === "alternative_description" || block.section === "C" ? " is-narrative" : ""}`} data-aw-block={block.id} tabIndex={-1}
    onKeyDown={event => {
      if (event.shiftKey && event.key === "F10") { event.preventDefault(); if (menu.current) { menu.current.open = true; menu.current.querySelector<HTMLButtonElement>("button")?.focus(); } }
      if (event.key === "Escape" && menu.current?.open) { event.stopPropagation(); menu.current.open = false; menu.current.querySelector<HTMLElement>("summary")?.focus(); }
    }}>
    {aiAccepted && <span className="aw-ai-mark" title={`Drafted with AI · accepted ${new Date(aiAccepted).toLocaleString()}`}><Icon24 name="spark" size={14} /><span className="sr-only">Drafted with AI · accepted {aiAccepted}</span></span>}
    {block.requests.map(r => <aside className="aw-request" key={r.id}><span className="cf-faint cf-small">Officer request</span><p data-aw-text>{r.note}</p></aside>)}
    <div className="aw-block-label"><label htmlFor={editable ? textId(block.id) : undefined}>{block.label}</label></div>
    <div className="aw-block-content">
      {block.missing && <span className="aw-missing"><Dot tone="blocking" />Missing {editable && <button type="button" className="cf-link-btn" onClick={() => textarea.current?.focus()}>Write it</button>}</span>}
      {editable ? <textarea ref={textarea} id={textId(block.id)} className="aw-paper-input" rows={1} value={value} aria-label={block.label} spellCheck
        onChange={event => { setValue(event.target.value); if (!composing.current) publish(event.target.value); }}
        onCompositionStart={() => { composing.current = true; onSelect(null); }}
        onCompositionEnd={event => { composing.current = false; publish(event.currentTarget.value); }}
        onBlur={event => { if (!composing.current) publish(event.currentTarget.value); onCommit(block.id); }}
        onSelect={select}
        onPaste={event => {
          if (composing.current) return;
          event.preventDefault();
          const el = event.currentTarget, plain = event.clipboardData.getData("text/plain"), start = el.selectionStart;
          const after = el.value.slice(0, start) + plain + el.value.slice(el.selectionEnd);
          publish(after);
          requestAnimationFrame(() => el.setSelectionRange(start + plain.length, start + plain.length));
        }} />
        : <p className="aw-paper-value" data-aw-text>{block.id === "authority" ? authorityName(block.text) || block.text || "—" : block.text || (block.notApplicable ? "N/A" : "—")}</p>}
      {block.notApplicable && <p className="aw-na">N/A · {block.notApplicable}</p>}
      {reference && <div className="aw-reference">
        <button type="button" className="cf-cite" onClick={() => onReference(reference.candidateId)}>{reference.provision}<span>Show the code</span><CIcon name="external" size={12} /></button>
        <div className="aw-lookups"><span className="aw-lock" title="Looked up from the attribution table. Not editable."><svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><rect x="3" y="7" width="10" height="7" rx="1" /><path d="M5 7V4a3 3 0 0 1 6 0v3" /></svg>Lookup</span>
          {[...new Set(reference.pairs.flatMap(p => [...p.objectives, ...p.functions]))].map(term => <span className="aw-lookup" title={reference.terms?.[term]} key={term}>{term}</span>)}
          {reference.attributionStatus === "no-row" && <span className="cf-faint cf-small">No attribution row</span>}
        </div>
        {code && <><blockquote className="cf-code-text"><span className="aw-code-label">Code text · verbatim</span><span data-aw-text>{code.text}</span></blockquote><p className="cf-code-src">{code.citation}</p></>}
        {reference.intent.length > 0 && <details className="aw-intent"><summary>Why this rule exists</summary>{reference.intent.map(i => <p key={i.text}>{i.text}</p>)}<p className="cf-faint cf-small">NBC 2020 intent statements · explanatory only</p></details>}
      </div>}
      {block.target.kind === "card" && !locked && <a className="cf-link-btn aw-change" href={block.target.href}>Change</a>}
      {diff.map(({ suggestion, change }) => <div className="aw-suggestion" key={suggestion.id} aria-label={`AI suggestion for ${block.label}`}>
        <p>{change.prefix}<del>{change.removed}</del><ins>{change.added}</ins>{change.suffix}</p>
        <div className="aw-suggestion-actions"><span className="aw-suggestion-label"><Icon24 name="spark" size={13} />AI suggestion</span>
          {!locked && <><button type="button" className="cf-btn is-xs" onClick={() => onAccept(suggestion)}>Accept</button><button type="button" className="cf-btn is-ghost is-xs" onClick={() => onReject(suggestion)}>Reject</button></>}
        </div>
      </div>)}
    </div>
    <details className={`aw-block-menu${menuUp ? " opens-up" : ""}`} ref={menu} onToggle={event => { if (event.currentTarget.open) setMenuUp(event.currentTarget.getBoundingClientRect().top > window.innerHeight - 210); }}>
      <summary title={`Options for ${block.label}`} aria-label={`Options for ${block.label}`}><MoreIcon /></summary>
      <div className="aw-block-popover"><button type="button" onClick={() => { menu.current?.removeAttribute("open"); onAsk(block, code?.text); }}><Icon24 name="spark" size={14} />Ask</button>
        {!locked && canRewrite(block) && <button type="button" onClick={wholeBlock}><Icon24 name="pencil" size={14} />Rewrite</button>}
        {block.target.kind === "card" && !locked && <a href={block.target.href}>Change <CIcon name="arrow" size={12} /></a>}
      </div>
    </details>
  </div>;
}
