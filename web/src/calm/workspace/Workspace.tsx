import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { accounts } from "../../api/accounts";
import { quoteKind } from "../../rules";
import { useCase } from "../../store";
import { openAssistant, setAssistantContext, type AssistContext } from "../assistant/assistant";
import { useAccount } from "../account";
import { useCurrentApplication } from "../begin";
import { arrange } from "../comments/thread";
import { CodeDrawer, type DrawerState } from "../CodeDrawer";
import { Icon24, type IconName } from "../icons";
import type { WorkspaceStep } from "../routes";
import { CIcon, Dot } from "../ui";
import { workspaceApi, workspaceFailure } from "./api";
import { blockAction, blockForField, buildDocument, type DocBlock, type OfficerRequest } from "./document";
import { acceptedAI, entryId, historyEntry, inverseEntry, type HistoryEntry } from "./history";
import { HistoryDrawer } from "./HistoryDrawer";
import { blockId, PaperBlock, textId, type PassageSelection } from "./PaperBlock";
import { SelectionBar } from "./SelectionBar";
import { Sign } from "./Sign";
import { Send } from "./Send";
import { acceptSuggestion, canRewrite, draftSuggestions, freshSuggestions, rejectSuggestion, rewriteRange, rewriteSuggestion, type Suggestion } from "./suggestions";
import { useWorkspace } from "./useWorkspace";
import "./workspace.css";

const STEPS: { id: WorkspaceStep; label: string; icon: IconName }[] = [
  { id: "edit", label: "Edit", icon: "compose" }, { id: "sign", label: "Sign", icon: "pencil" }, { id: "send", label: "Send", icon: "send" },
];
const STATUS: Record<string, string> = { draft: "Draft", submitted: "Sent", in_review: "In review", returned: "Returned", accepted: "Accepted", refused: "Refused", withdrawn: "Withdrawn" };
function passageContext(block: DocBlock, passage = block.text): AssistContext {
  return { screen: "application", label: block.label, focus: { kind: "passage", id: block.id, prompt: passage.slice(0, 600), why: block.label.slice(0, 1200) } };
}

export function Workspace({ step, focus, download }: { step: WorkspaceStep; focus: string | null; download: "" | "options" | "draft" }) {
  const { c, gaps, engineId, dispatch, saveDraft, readSync, applicationStatus } = useCase();
  const { app, locked, readOnly } = useCurrentApplication();
  const account = useAccount();
  const [requests, setRequests] = useState<OfficerRequest[]>([]);
  const [requestNote, setRequestNote] = useState("");
  const [requestAttempt, setRequestAttempt] = useState(0);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const seenDrafts = useRef(new Set<string>());
  const [selection, setSelection] = useState<PassageSelection | null>(null);
  const [rewriteBusy, setRewriteBusy] = useState(false);
  const rewriting = useRef<AbortController | null>(null);
  const [note, setNote] = useState("");
  const [toast, setToast] = useState<{ text: string; undo?: HistoryEntry } | null>(null);
  const [zoom, setZoom] = useState(100);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [drawer, setDrawer] = useState<DrawerState | null>(null);
  const outline = useRef<HTMLDetailsElement>(null);
  const paperPane = useRef<HTMLDivElement>(null);
  const sections = useMemo(() => buildDocument(c, gaps, requests), [c, gaps, requests]);
  const blocks = sections.flatMap(s => s.blocks);
  const contentKey = JSON.stringify([c.description, c.authority, c.facts.filter(f => f.status === "confirmed" && f.kind !== "proposed").map(f => [f.field, f.value]), c.process, c.sectionC.map(r => [r.provision, r.pairs]), c.candidates.filter(a => a.answer === "yes").map(a => a.provision)]);
  const workspace = useWorkspace(contentKey);
  const live = useRef({ blocks, locked }); live.current = { blocks, locked };
  const fresh = freshSuggestions(suggestions, blocks).filter(s => s.origin !== "draft" || s.factId || !workspace.history.some(entry => entry.block === s.blockId));
  const selectedBlock = selection && blocks.find(b => b.id === selection.blockId);
  const status = STATUS[app?.status ?? applicationStatus ?? "draft"] ?? "Status unavailable";
  const signers = workspace.state.record?.signers.filter(s => s.required) ?? [];
  const signed = signers.filter(s => workspace.signaturesCurrent && workspace.state.record?.signatures.some(signature => signature.role === s.role && signature.current)).length;
  const editCount = fresh.length + requests.length;

  useEffect(() => {
    if (!engineId || account.phase !== "signed-in") return;
    const ctl = new AbortController();
    setRequestNote("");
    void accounts.messages(engineId, ctl.signal).then(messages => {
      if (ctl.signal.aborted) return;
      const thread = arrange(messages);
      const current = [...(thread.latest ? [thread.latest] : []), ...thread.since.filter(m => m.author.role === "reviewer")];
      setRequests(current.flatMap(m => m.items.map((item, n) => ({ ...item, id: `${m.id}:${n}` }))));
    }).catch(() => { if (!ctl.signal.aborted) setRequestNote("Officer requests didn’t load."); });
    return () => ctl.abort();
  }, [engineId, account.phase, app?.updated_at, requestAttempt]);
  useEffect(() => {
    const incoming = draftSuggestions(c, sections).filter(s => !seenDrafts.current.has(s.id));
    for (const s of incoming) seenDrafts.current.add(s.id);
    if (incoming.length) setSuggestions(previous => [...previous, ...incoming]);
  }, [c, sections]);
  useEffect(() => {
    setSuggestions(previous => {
      const next = freshSuggestions(previous, blocks);
      return next.length === previous.length ? previous : next;
    });
  }, [contentKey]);
  useEffect(() => () => rewriting.current?.abort(), []);
  useEffect(() => {
    setSelection(null);
    workspace.journal.edits.flush();
  }, [step, workspace.journal]);
  useEffect(() => {
    if (step !== "edit" || !focus) return;
    const block = blockForField(sections, focus);
    const element = block ? document.getElementById(textId(block.id)) ?? document.getElementById(blockId(block.id))
      : document.getElementById(focus.startsWith("section-") ? `aw-${focus}` : `aw-section-${focus}`);
    if (element instanceof HTMLElement) { element.scrollIntoView({ block: "center" }); element.focus({ preventScroll: true }); }
  }, [focus, step]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 12000);
    return () => clearTimeout(timer);
  }, [toast]);

  function edit(block: DocBlock, before: string, after: string) {
    if (live.current.locked) return;
    const action = blockAction(block, after);
    if (!action) return;
    dispatch(action); workspace.journal.edits.change(block.id, block.label, before, after);
  }
  function change(block: DocBlock, after: string, by: HistoryEntry["by"]) {
    if (live.current.locked) return;
    workspace.journal.edits.flush(block.id);
    const action = blockAction(block, after), entry = historyEntry(block.id, block.label, block.text, after, by);
    if (!action || !entry) return;
    dispatch(action); workspace.journal.add(entry);
    return entry;
  }
  function undo(entry = workspace.history.at(-1)) {
    if (!entry || live.current.locked) return;
    workspace.journal.edits.flush();
    const block = live.current.blocks.find(b => b.id === entry.block);
    if (!block || !inverseEntry(entry, block.text)) { setToast({ text: "This block changed again. Use History to restore a version." }); return; }
    change(block, entry.before, "restore");
    setToast({ text: "Change undone" });
  }
  useEffect(() => {
    function key(event: KeyboardEvent) {
      const el = event.target;
      if (!(event.metaKey || event.ctrlKey) || event.altKey || event.shiftKey || event.key.toLowerCase() !== "z" || locked) return;
      if (el instanceof Element && el.closest("input, textarea, [contenteditable=true], dialog")) return;
      event.preventDefault(); undo();
    }
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [workspace.history, contentKey, locked]);

  function accept(suggestion: Suggestion) {
    const block = live.current.blocks.find(b => b.id === suggestion.blockId);
    if (!block || live.current.locked || !acceptSuggestion(suggestion, block)) return;
    // Consume a writing draft as well, so it cannot reappear after a later manual edit.
    if (suggestion.factId) dispatch({ type: "dismissFact", id: suggestion.factId });
    const entry = change(block, suggestion.after, "ai");
    setSuggestions(previous => previous.filter(s => s.id !== suggestion.id));
    if (entry) setToast({ text: "AI change accepted", undo: entry });
  }
  function reject(suggestion: Suggestion) {
    if (live.current.locked) return;
    const action = rejectSuggestion(suggestion);
    if (action) dispatch(action);
    setSuggestions(previous => previous.filter(s => s.id !== suggestion.id));
  }
  function ask(block: DocBlock, passage?: string) {
    openAssistant(passageContext(block, passage)); setSelection(null);
  }
  async function rewrite(instruction: string) {
    if (!selection || !selectedBlock || locked || rewriteBusy || !canRewrite(selectedBlock)) return;
    const passage = selection, block = selectedBlock;
    const ctl = new AbortController(); rewriting.current?.abort(); rewriting.current = ctl;
    setRewriteBusy(true); setNote(""); workspace.journal.edits.flush(block.id);
    try {
      const id = await saveDraft();
      if (ctl.signal.aborted) return;
      if (!id || !readSync().saved) { setNote("Save your application before rewriting."); return; }
      if (live.current.locked || live.current.blocks.find(b => b.id === block.id)?.text !== passage.text) { setNote("This passage changed. Select it again."); return; }
      const result = await workspaceApi.rewrite(id, { field: block.id, text: passage.text, ...rewriteRange(passage), instruction }, ctl.signal);
      if (ctl.signal.aborted) return;
      if (live.current.blocks.find(b => b.id === block.id)?.text !== passage.text) { setNote("This passage changed. The old suggestion was dropped."); return; }
      const suggestion = rewriteSuggestion(entryId(), passage, result);
      setSuggestions(previous => [...previous.filter(s => s.blockId !== block.id || s.origin !== "rewrite"), suggestion]);
      setNote(result.notice || (suggestion.after === suggestion.before ? "No change suggested." : ""));
      setSelection(null);
    } catch (e) { if (!ctl.signal.aborted) setNote(workspaceFailure(e, "Rewriting")); }
    finally { if (!ctl.signal.aborted) setRewriteBusy(false); }
  }
  const closeSelection = useCallback(() => setSelection(null), []);
  function selectedText() {
    const s = window.getSelection();
    if (!s?.rangeCount || s.isCollapsed || !s.anchorNode || !s.focusNode) return;
    const element = s.anchorNode instanceof Element ? s.anchorNode : s.anchorNode.parentElement;
    const endElement = s.focusNode instanceof Element ? s.focusNode : s.focusNode.parentElement;
    const textElement = element?.closest("[data-aw-text]");
    if (!textElement || textElement !== endElement?.closest("[data-aw-text]")) return;
    const block = blocks.find(b => b.id === textElement.closest<HTMLElement>("[data-aw-block]")?.dataset.awBlock);
    if (!block) return;
    const selected = s.toString(), range = s.getRangeAt(0), rect = range.getBoundingClientRect();
    setSelection({ blockId: block.id, text: block.text, start: 0, end: 0, selected, left: rect.left, top: rect.top });
  }

  useEffect(() => {
    if (step !== "edit") return;
    document.addEventListener("selectionchange", selectedText);
    return () => document.removeEventListener("selectionchange", selectedText);
  }, [step, sections]);

  return <div className="aw-workspace">
    <div className="aw-subbar">
      <nav className="aw-steps" aria-label="Application steps">{STEPS.map(s => <a key={s.id} href={`#/application?step=${s.id}`} aria-current={step === s.id ? "step" : undefined} aria-label={`${s.label}${s.id === "edit" && editCount ? `, ${editCount} suggestions and requests` : s.id === "sign" ? `, ${signed} of ${signers.length} signed` : ""}`} title={s.label} onClick={() => workspace.journal.edits.flush()}>
        <Icon24 name={s.icon} size={17} />{step === s.id && <span>{s.label}</span>}{s.id === "edit" && editCount > 0 && <span className="aw-count">{editCount}</span>}{s.id === "sign" && <span className="aw-count">{workspace.state.phase === "ready" ? `${signed}/${signers.length}` : "—"}</span>}
      </a>)}</nav>
      {step === "edit" && <details className="aw-outline" ref={outline}><summary className="aw-tool" aria-label="Application outline" title="Application outline"><Icon24 name="menu" size={16} /></summary><nav aria-label="Sections">{sections.map(s => <button type="button" key={s.id} onClick={() => { document.getElementById(`aw-section-${s.id}`)?.scrollIntoView({ block: "start" }); outline.current?.removeAttribute("open"); }}>{s.id === "case" ? "¶" : s.id}<span>{s.title}</span></button>)}</nav></details>}
      <div className="aw-zoom"><button type="button" className="aw-tool" title="Zoom out" aria-label="Zoom out" disabled={zoom <= 80} onClick={() => setZoom(z => z - 10)}>−</button><span>{zoom}%</span><button type="button" className="aw-tool" title="Zoom in" aria-label="Zoom in" disabled={zoom >= 140} onClick={() => setZoom(z => z + 10)}>+</button></div>
      <button type="button" className="aw-tool aw-history-button" aria-label="History" title="History" onClick={() => { workspace.journal.edits.flush(); setHistoryOpen(true); }}><Icon24 name="clock" size={16} /><span>History</span></button>
      <span className="aw-status"><Dot tone={status === "Accepted" ? "done" : status === "Refused" ? "blocking" : "pending"} />{status}</span>
    </div>
    <span className="sr-only" role="status" aria-live="polite">{fresh.length ? `${fresh.length} AI suggestions available. Review each before accepting.` : ""}</span>
    {requestNote && <p className="aw-notice" role="status">{requestNote} <button type="button" className="cf-link-btn" onClick={() => setRequestAttempt(n => n + 1)}>Try again</button></p>}
    {requests.some(r => !blocks.some(b => b.requests.some(request => request.id === r.id))) && <p className="aw-notice"><a href="#/comments" className="cf-inline-link">Read the officer’s other requests</a></p>}
    {note && <p className="aw-notice" role="status">{note} <button type="button" className="cf-link-btn" onClick={() => setNote("")}>Dismiss</button></p>}
    {step === "edit" ? <div className="aw-paper-scroll" ref={paperPane} onScroll={closeSelection} onMouseUp={selectedText}>
      <article className="aw-paper" style={{ zoom: zoom / 100 }} aria-label="Application document" onFocusCapture={e => {
        const element = e.target instanceof Element ? e.target.closest<HTMLElement>("[data-aw-block]") : null;
        const block = blocks.find(b => b.id === element?.dataset.awBlock);
        if (block) setAssistantContext(passageContext(block));
      }}>
        <h1>Request for an alternative solution</h1><p className="aw-paper-meta">{c.codeEdition}</p>
        {readOnly && <p className="aw-read-only">{status} · Read-only</p>}
        {sections.map(section => <section id={`aw-section-${section.id}`} key={section.id} tabIndex={-1}><h2>{section.title}<span>{section.formLabel}</span></h2>
          {section.blocks.map(block => {
            const candidate = block.reference ? c.candidates.find(a => a.id === block.reference?.candidateId) : undefined;
            return <PaperBlock key={block.id} block={block} locked={locked} aiAccepted={acceptedAI(workspace.history, block.id, block.text)} suggestions={fresh.filter(s => s.blockId === block.id)} code={candidate && quoteKind(candidate) === "code" ? candidate.quote : undefined}
              onEdit={edit} onCommit={id => workspace.journal.edits.flush(id)} onSelect={setSelection} onAsk={ask} onAccept={accept} onReject={reject} onReference={candidateId => setDrawer({ mode: "code", candidateId })} />;
          })}
        </section>)}
        <a className="cf-btn is-ghost aw-next" href="#/application?step=sign">Sign <CIcon name="arrow" size={14} /></a>
      </article>
      {selection && selectedBlock && <SelectionBar key={`${selection.blockId}:${selection.start}:${selection.end}`} selection={selection} block={selectedBlock} allowRewrite={!locked && canRewrite(selectedBlock)} busy={rewriteBusy} onAsk={() => ask(selectedBlock, selection.selected)} onRewrite={instruction => void rewrite(instruction)} onClose={closeSelection} />}
    </div> : step === "sign" ? <Sign workspace={workspace} /> : <Send download={download} workspace={workspace} sections={sections} zoom={zoom} />}
    {toast && <div className="aw-toast" role="status"><span>{toast.text}</span>{toast.undo && !locked && <button type="button" onClick={() => undo(toast.undo)}>Undo</button>}<button type="button" onClick={() => setToast(null)} aria-label="Dismiss notification">×</button></div>}
    <HistoryDrawer open={historyOpen} onClose={() => setHistoryOpen(false)} workspace={workspace} blocks={blocks} locked={locked} onRestore={entry => {
      const block = live.current.blocks.find(b => b.id === entry.block);
      if (block && change(block, entry.after, "restore")) setToast({ text: "Version restored" });
    }} />
    <CodeDrawer state={drawer} onClose={() => setDrawer(null)} onAdded={() => setDrawer(null)} />
  </div>;
}
