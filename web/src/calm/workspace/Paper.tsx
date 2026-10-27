import { useEffect, useRef, useState } from "react";
import { quoteKind } from "../../rules";
import { useCase } from "../../store";
import { authorityName } from "../applications";
import { setAssistantContext } from "../assistant/assistant";
import { CodeDrawer, type DrawerState } from "../CodeDrawer";
import { Icon24 } from "../icons";
import { acceptedAI } from "./history";
import { blockForField, type SectionId } from "./document";
import { blockId, PaperBlock, textId } from "./PaperBlock";
import { SelectionBar } from "./SelectionBar";
import { canRewrite } from "./suggestions";
import { passageContext, type Editing } from "./useEditing";

/** Section letters and the hue that marks "you are here" (A blue, B teal, C violet, D amber). */
const MARK: Record<SectionId, { mark: string; hue: string }> = {
  A: { mark: "A", hue: "is-blue" },
  B: { mark: "B", hue: "is-teal" },
  case: { mark: "¶", hue: "is-slate" },
  C: { mark: "C", hue: "is-violet" },
  D: { mark: "D", hue: "is-amber" },
};

export function Paper({ editing, focus, zoom, statusWord }: { editing: Editing; focus: string | null; zoom: number; statusWord: string }) {
  const { c } = useCase();
  const { sections, blocks, workspace, locked, selection, setSelection } = editing;
  const pane = useRef<HTMLDivElement>(null);
  const [drawer, setDrawer] = useState<DrawerState | null>(null);
  const [current, setCurrent] = useState<SectionId>("A");
  const selectedBlock = selection && blocks.find(b => b.id === selection.blockId);
  const unpinned = editing.requests.filter(r => !blocks.some(b => b.requests.some(q => q.id === r.id)));

  // Arriving from a gap, a legacy link or Send's Fix: scroll to that block and put the caret in it.
  useEffect(() => {
    if (!focus) return;
    const block = blockForField(sections, focus);
    const el = block
      ? document.getElementById(textId(block.id)) ?? document.getElementById(blockId(block.id))
      : document.getElementById(`aw-section-${focus.replace(/^section-/, "")}`);
    if (el instanceof HTMLElement) {
      el.scrollIntoView({ block: "center" });
      el.focus({ preventScroll: true });
    }
    // Only a new focus target scrolls; later edits must not jump the page.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus]);

  // The section index follows the reader: the last section whose heading has reached the top of the pane.
  function spy() {
    const root = pane.current;
    if (!root) return;
    const top = root.getBoundingClientRect().top + 140;
    let at: SectionId = sections[0]?.id ?? "A";
    for (const s of sections) {
      const el = document.getElementById(`aw-section-${s.id}`);
      if (el && el.getBoundingClientRect().top <= top) at = s.id;
    }
    setCurrent(at);
  }
  useEffect(spy, [sections.length]);

  // Selecting read-only words (a value, an officer request) still offers Ask.
  useEffect(() => {
    function onSelection() {
      const s = window.getSelection();
      if (!s?.rangeCount || s.isCollapsed || !s.anchorNode || !s.focusNode) return;
      const start = s.anchorNode instanceof Element ? s.anchorNode : s.anchorNode.parentElement;
      const end = s.focusNode instanceof Element ? s.focusNode : s.focusNode.parentElement;
      const holder = start?.closest("[data-aw-text]");
      if (!holder || holder !== end?.closest("[data-aw-text]")) return;
      const block = blocks.find(b => b.id === holder.closest<HTMLElement>("[data-aw-block]")?.dataset.awBlock);
      if (!block) return;
      const rect = s.getRangeAt(0).getBoundingClientRect();
      setSelection({ blockId: block.id, text: block.text, start: 0, end: 0, selected: s.toString(), left: rect.left, top: rect.top, bottom: rect.bottom, readOnly: true });
    }
    document.addEventListener("selectionchange", onSelection);
    return () => document.removeEventListener("selectionchange", onSelection);
  }, [blocks, setSelection]);

  return (
    <div className="aw-edit">
      <nav className="aw-index" aria-label="Sections">
        {sections.map(s => (
          <button key={s.id} type="button" className={`aw-index-item ${MARK[s.id].hue}`} aria-current={current === s.id ? "location" : undefined}
            aria-label={s.title} title={s.title} onClick={() => document.getElementById(`aw-section-${s.id}`)?.scrollIntoView({ block: "start", behavior: "smooth" })}>
            {MARK[s.id].mark}
            {s.blocks.some(b => b.missing) && <span className="aw-index-dot" aria-hidden="true" />}
          </button>
        ))}
      </nav>
      <div className="aw-pane" ref={pane} onScroll={() => { editing.closeSelection(); spy(); }}>
        {(editing.requestsFailed || unpinned.length > 0) && (
          <div className="aw-notes">
            {editing.requestsFailed && <p className="aw-note" role="status">Officer requests didn’t load.<button type="button" className="cf-link-btn" onClick={editing.retryRequests}>Try again</button></p>}
            {unpinned.length > 0 && <p className="aw-note"><Icon24 name="msg" size={14} />{unpinned.length} more from the officer<a className="cf-link-btn" href="#/comments">Read</a></p>}
          </div>
        )}
        <article className="aw-paper" style={{ zoom: zoom / 100 }} aria-label="Application"
          onFocusCapture={e => {
            const el = e.target instanceof Element ? e.target.closest<HTMLElement>("[data-aw-block]") : null;
            const block = blocks.find(b => b.id === el?.dataset.awBlock);
            if (block) setAssistantContext(passageContext(block));
          }}>
          <header className="aw-paper-head">
            <h1>Request for an alternative solution</h1>
            <p>{[c.codeEdition, authorityName(c.authority)].filter(Boolean).join(" · ")}{locked ? ` · ${statusWord}, read-only` : ""}</p>
          </header>
          {sections.map(section => (
            <section key={section.id} id={`aw-section-${section.id}`} className="aw-section" tabIndex={-1} aria-labelledby={`aw-h-${section.id}`}>
              <h2 id={`aw-h-${section.id}`}>{section.title}<span>{section.formLabel}</span></h2>
              {section.blocks.map(block => {
                const candidate = block.reference ? c.candidates.find(a => a.id === block.reference?.candidateId) : undefined;
                return (
                  <PaperBlock key={block.id} block={block} locked={locked}
                    aiAccepted={acceptedAI(workspace.history, block.id, block.text)}
                    suggestions={editing.suggestions.filter(s => s.blockId === block.id)}
                    code={candidate && quoteKind(candidate) === "code" ? candidate.quote : undefined}
                    onEdit={editing.type} onCommit={id => workspace.journal.edits.flush(id)}
                    onSelect={setSelection} onAsk={editing.ask} onAccept={editing.accept} onReject={editing.reject}
                    onReference={candidateId => setDrawer({ mode: "code", candidateId })} />
                );
              })}
            </section>
          ))}
          <footer className="aw-paper-foot">
            <a className="cf-btn is-sm" href="#/application?step=sign"><Icon24 name="sign" size={15} />Sign</a>
          </footer>
        </article>
      </div>
      {selection && selectedBlock && (
        <SelectionBar key={`${selection.blockId}:${selection.start}:${selection.end}`} selection={selection} block={selectedBlock}
          allowRewrite={!locked && !selection.readOnly && canRewrite(selectedBlock)} busy={editing.rewriteBusy}
          onAsk={() => editing.ask(selectedBlock, selection.selected)} onRewrite={i => void editing.rewrite(i)} onClose={editing.closeSelection} />
      )}
      <CodeDrawer state={drawer} onClose={() => setDrawer(null)} onAdded={() => setDrawer(null)} />
    </div>
  );
}
