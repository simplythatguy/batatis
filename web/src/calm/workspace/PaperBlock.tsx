import { useEffect, useLayoutEffect, useRef, useState, type SyntheticEvent } from "react";
import { authorityName } from "../applications";
import { Icon24 } from "../icons";
import { CIcon, Dot, MoreIcon } from "../ui";
import type { DocBlock } from "./document";
import { canRewrite, changedWords, type Passage, type Suggestion } from "./suggestions";

export interface PassageSelection extends Passage {
  selected: string;
  left: number;
  top: number;
  /** The whole block, chosen from its menu rather than by selecting words. */
  wholeBlock?: boolean;
  /** Words selected outside an editor: Ask only. */
  readOnly?: boolean;
}
export const textId = (id: string) => `aw-text-${id}`;
export const blockId = (id: string) => `aw-block-${id}`;

const isLong = (b: DocBlock) => b.target.kind === "process" || b.id === "alternative_description" || (b.target.kind === "detail" && b.target.section === "C");

/**
 * One line of the form. Free text is typed in place; anything else links to the question that sets it.
 * AI words never appear in the applicant's ink until accepted: a suggestion shows as a tracked change.
 */
export function PaperBlock({ block, locked, aiAccepted, suggestions, code, onEdit, onCommit, onSelect, onAsk, onAccept, onReject, onReference }: {
  block: DocBlock; locked: boolean; aiAccepted?: string; suggestions: Suggestion[]; code?: { text: string; citation: string };
  onEdit: (block: DocBlock, before: string, after: string) => void; onCommit: (id: string) => void;
  onSelect: (selection: PassageSelection | null) => void; onAsk: (block: DocBlock, passage?: string) => void;
  onAccept: (suggestion: Suggestion) => void; onReject: (suggestion: Suggestion) => void; onReference: (candidateId: string) => void;
}) {
  const textarea = useRef<HTMLTextAreaElement>(null);
  const menu = useRef<HTMLDetailsElement>(null);
  const [value, setValue] = useState(block.text);
  const composing = useRef(false);
  const sent = useRef(block.text);
  const editable = block.target.kind !== "card" && !locked;
  const reference = block.reference;

  useEffect(() => {
    if (!composing.current && sent.current !== block.text) { sent.current = block.text; setValue(block.text); }
  }, [block.text]);
  useLayoutEffect(() => {
    const el = textarea.current;
    if (el) { el.style.height = "0px"; el.style.height = `${Math.max(el.scrollHeight, 22)}px`; }
  }, [value, editable]);
  useEffect(() => {
    const close = (event: globalThis.PointerEvent) => {
      if (event.target instanceof Node && !menu.current?.contains(event.target)) menu.current?.removeAttribute("open");
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, []);

  function publish(after: string) {
    setValue(after);
    if (after === sent.current || locked) return;
    const before = sent.current;
    sent.current = after;
    onEdit(block, before, after);
  }
  function select(event: SyntheticEvent<HTMLTextAreaElement>) {
    if (composing.current) return;
    const el = event.currentTarget, start = el.selectionStart, end = el.selectionEnd;
    if (start === end) { onSelect(null); return; }
    // Anchor the bar above the editor's caret line, not its top edge.
    const rect = el.getBoundingClientRect();
    onSelect({ blockId: block.id, text: el.value, start, end, selected: el.value.slice(start, end), left: rect.left, top: rect.top });
  }
  function wholeBlock() {
    menu.current?.removeAttribute("open");
    const rect = document.getElementById(blockId(block.id))?.getBoundingClientRect();
    onSelect({ blockId: block.id, text: block.text, start: 0, end: 0, selected: block.text, wholeBlock: true, left: rect?.left ?? 16, top: rect?.top ?? 100 });
  }

  const shown = block.id === "authority" ? authorityName(block.text) || block.text : block.text;
  const cls = ["aw-block", isLong(block) ? "is-long" : "", reference ? "is-ref" : "", block.missing ? "is-missing" : ""].filter(Boolean).join(" ");

  return (
    <div id={blockId(block.id)} className={cls} data-aw-block={block.id} tabIndex={-1}
      onKeyDown={event => {
        if (event.shiftKey && event.key === "F10" && menu.current) {
          event.preventDefault();
          menu.current.open = true;
          menu.current.querySelector<HTMLButtonElement>("button")?.focus();
        }
        if (event.key === "Escape" && menu.current?.open) {
          event.stopPropagation();
          menu.current.open = false;
          menu.current.querySelector<HTMLElement>("summary")?.focus();
        }
      }}>
      {aiAccepted && (
        <span className="aw-ai-mark" title={`Drafted with AI · you accepted it ${new Date(aiAccepted).toLocaleDateString()}`}>
          <Icon24 name="spark" size={13} /><span className="sr-only">Drafted with AI, accepted by you</span>
        </span>
      )}
      {block.requests.map(r => (
        <aside className="aw-request" key={r.id} aria-label="Officer request">
          <Icon24 name="msg" size={14} />
          <p data-aw-text>{r.note}</p>
        </aside>
      ))}

      <div className="aw-label">
        {block.missing && <Dot tone="blocking" />}
        {editable ? <label htmlFor={textId(block.id)}>{block.label}</label> : <span>{block.label}</span>}
      </div>

      <div className="aw-value">
        {editable ? (
          <textarea ref={textarea} id={textId(block.id)} className="aw-input" rows={1} value={value} spellCheck
            placeholder={block.missing ? "Missing · write it here" : isLong(block) ? "Write it here" : "Empty"}
            onChange={e => { setValue(e.target.value); if (!composing.current) publish(e.target.value); }}
            onCompositionStart={() => { composing.current = true; onSelect(null); }}
            onCompositionEnd={e => { composing.current = false; publish(e.currentTarget.value); }}
            onBlur={e => { if (!composing.current) publish(e.currentTarget.value); onCommit(block.id); }}
            onSelect={select}
            onPaste={e => {
              if (composing.current) return;
              e.preventDefault();
              const el = e.currentTarget, plain = e.clipboardData.getData("text/plain"), start = el.selectionStart;
              publish(el.value.slice(0, start) + plain + el.value.slice(el.selectionEnd));
              requestAnimationFrame(() => el.setSelectionRange(start + plain.length, start + plain.length));
            }} />
        ) : reference ? (
          <div className="aw-ref">
            <button type="button" className="aw-cite" onClick={() => onReference(reference.candidateId)} title="Show the code text">
              <span>{reference.provision}</span><CIcon name="external" size={12} />
            </button>
            <Terms reference={reference} />
            {code && <span className="sr-only" data-aw-text>{code.text}</span>}
          </div>
        ) : block.target.kind === "card" && !locked ? (
          <a className={`aw-link${shown ? "" : " is-empty"}`} href={block.target.href} aria-label={`Change ${block.label}`}>
            {shown ? <span data-aw-text>{shown}</span> : block.notApplicable ? <span className="aw-na">N/A</span> : <span>{block.missing ? "Missing" : "Not answered"}</span>}
            <Icon24 name="chevRight" size={14} />
          </a>
        ) : (
          <p className="aw-text" data-aw-text>{shown || (block.notApplicable ? <span className="aw-na">N/A</span> : "—")}</p>
        )}
        {block.notApplicable && <p className="aw-na-reason" data-aw-text>{block.notApplicable}</p>}

        {suggestions.map(s => {
          const d = changedWords(s.before, s.after);
          return (
            <div className="aw-sugg" key={s.id} role="group" aria-label={`AI suggestion for ${block.label}`}>
              <p>{d.prefix.length > 160 ? `…${d.prefix.slice(-160)}` : d.prefix}<del>{d.removed}</del><ins>{d.added}</ins>{d.suffix.length > 160 ? `${d.suffix.slice(0, 160)}…` : d.suffix}</p>
              <div className="aw-sugg-bar">
                <span className="aw-sugg-tag"><Icon24 name="spark" size={13} />AI suggestion</span>
                {!locked && (
                  <>
                    <button type="button" className="aw-sugg-reject" onClick={() => onReject(s)}>Reject</button>
                    <button type="button" className="aw-sugg-accept" onClick={() => onAccept(s)}>Accept</button>
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <details className="aw-more" ref={menu}>
        <summary aria-label={`More for ${block.label}`} title="More"><MoreIcon /></summary>
        <div className="aw-menu" role="menu">
          <button type="button" role="menuitem" onClick={() => { menu.current?.removeAttribute("open"); onAsk(block, code?.text); }}>
            <Icon24 name="spark" size={14} />Ask
          </button>
          {!locked && canRewrite(block) && (
            <button type="button" role="menuitem" onClick={wholeBlock}><Icon24 name="pencil" size={14} />Rewrite</button>
          )}
          {block.target.kind === "card" && !locked && (
            <a role="menuitem" href={block.target.href}><Icon24 name="chevRight" size={14} />Change</a>
          )}
        </div>
      </details>
    </div>
  );
}

/** Objectives and functions from the attribution table: a lookup, never typed. Long lists fold. */
function Terms({ reference }: { reference: NonNullable<DocBlock["reference"]> }) {
  const [all, setAll] = useState(false);
  const terms = [...new Set(reference.pairs.flatMap(p => [...p.objectives, ...p.functions]))];
  const shown = all ? terms : terms.slice(0, 6);
  return (
    <span className="aw-terms" title="Looked up from the code’s attribution table. Not editable.">
      <Icon24 name="lock" size={12} />
      {shown.map(term => <span key={term} title={reference.terms?.[term]}>{term}</span>)}
      {terms.length > shown.length && (
        <button type="button" className="aw-terms-more" onClick={() => setAll(true)} aria-label={`Show all ${terms.length} objectives and functions`}>+{terms.length - shown.length}</button>
      )}
      {reference.attributionStatus === "no-row" && <span>no attribution row</span>}
    </span>
  );
}
