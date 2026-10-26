import { useEffect, useState } from "react";
import { useCase } from "../../store";
import { useCurrentApplication } from "../begin";
import { Icon24, type IconName } from "../icons";
import type { WorkspaceStep } from "../routes";
import { HistoryDrawer } from "./HistoryDrawer";
import { Paper } from "./Paper";
import { Send } from "./Send";
import { Sign } from "./Sign";
import { useEditing, type Editing } from "./useEditing";
import "./workspace.css";

const STEPS: { id: WorkspaceStep; label: string; icon: IconName }[] = [
  { id: "edit", label: "Edit", icon: "compose" },
  { id: "sign", label: "Sign", icon: "sign" },
  { id: "send", label: "Send", icon: "send" },
];

const STATUS: Record<string, { word: string; tone: "pending" | "done" | "warning" | "blocking" }> = {
  draft: { word: "Draft", tone: "pending" },
  submitted: { word: "Sent", tone: "pending" },
  in_review: { word: "In review", tone: "pending" },
  returned: { word: "Returned", tone: "warning" },
  accepted: { word: "Accepted", tone: "done" },
  refused: { word: "Refused", tone: "blocking" },
  withdrawn: { word: "Withdrawn", tone: "pending" },
};

/** The application as a document you edit, sign and send. One step on screen at a time. */
export function Workspace({ step, focus, download }: { step: WorkspaceStep; focus: string | null; download: "" | "options" | "draft" }) {
  const editing = useEditing();
  const { app } = useCurrentApplication();
  const { applicationStatus } = useCase();
  const [zoom, setZoom] = useState(100);
  const [historyOpen, setHistoryOpen] = useState(false);
  const { workspace, locked } = editing;
  const status = STATUS[app?.status ?? applicationStatus ?? "draft"] ?? STATUS.draft;

  useEffect(() => {
    editing.closeSelection();
    workspace.journal.edits.flush();
    // A step change commits typing in progress and drops a stale selection.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (!(event.metaKey || event.ctrlKey) || event.altKey || event.shiftKey || event.key.toLowerCase() !== "z" || locked) return;
      const el = event.target;
      if (el instanceof Element && el.closest("input, textarea, [contenteditable=true], dialog")) return;
      event.preventDefault();
      editing.undo();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <div className="aw">
      <StepBar step={step} editing={editing} statusWord={status.word} statusTone={status.tone}
        zoom={zoom} onZoom={setZoom} onHistory={() => { workspace.journal.edits.flush(); setHistoryOpen(true); }} />
      {step === "edit" && <Paper editing={editing} focus={focus} zoom={zoom} statusWord={status.word} />}
      {step === "sign" && <Sign workspace={workspace} />}
      {step === "send" && <Send download={download} workspace={workspace} sections={editing.sections} zoom={zoom} />}
      {editing.toast && (
        <div className="aw-toast" role="status">
          <span>{editing.toast.text}</span>
          {editing.toast.undo && !locked && <button type="button" onClick={() => editing.undo(editing.toast?.undo)}>Undo</button>}
          <button type="button" className="aw-toast-x" onClick={editing.clearToast} aria-label="Dismiss"><Icon24 name="x" size={14} /></button>
        </div>
      )}
      <HistoryDrawer open={historyOpen} onClose={() => setHistoryOpen(false)} editing={editing} />
    </div>
  );
}

function StepBar({ step, editing, statusWord, statusTone, zoom, onZoom, onHistory }: {
  step: WorkspaceStep; editing: Editing; statusWord: string; statusTone: string;
  zoom: number; onZoom: (z: number) => void; onHistory: () => void;
}) {
  const { workspace, suggestions, requests } = editing;
  const record = workspace.state.phase === "ready" ? workspace.state.record : null;
  const signers = record?.signers.filter(s => s.required) ?? [];
  const signed = signers.filter(s => workspace.signaturesCurrent && record?.signatures.some(sig => sig.role === s.role && sig.current)).length;
  const toReview = suggestions.length + requests.length;
  const count = (id: WorkspaceStep) =>
    id === "edit" ? (toReview ? String(toReview) : "")
    : id === "sign" ? (record ? `${signed}/${signers.length}` : "")
    : "";
  const spoken = (id: WorkspaceStep, label: string) =>
    id === "edit" && toReview ? `${label}, ${toReview} to review`
    : id === "sign" && record ? `${label}, ${signed} of ${signers.length} signed`
    : label;

  return (
    <div className="aw-bar">
      <nav className="aw-steps" aria-label="Application steps">
        {STEPS.map(s => {
          const current = step === s.id;
          return (
            <a key={s.id} href={s.id === "edit" ? "#/application" : `#/application?step=${s.id}`} className="aw-step"
              aria-current={current ? "step" : undefined} aria-label={spoken(s.id, s.label)} title={current ? undefined : s.label}
              onClick={() => workspace.journal.edits.flush()}>
              <Icon24 name={s.icon} size={16} />
              {current && <span className="aw-step-word">{s.label}</span>}
              {count(s.id) && <span className="aw-step-count" aria-hidden="true">{count(s.id)}</span>}
            </a>
          );
        })}
      </nav>
      <div className="aw-bar-tools">
        {step !== "sign" && (
          <div className="aw-zoom" role="group" aria-label="Zoom">
            <button type="button" className="aw-tool" aria-label="Zoom out" title="Zoom out" disabled={zoom <= 80} onClick={() => onZoom(zoom - 10)}>−</button>
            <span className="aw-zoom-value" aria-live="polite">{zoom}%</span>
            <button type="button" className="aw-tool" aria-label="Zoom in" title="Zoom in" disabled={zoom >= 140} onClick={() => onZoom(zoom + 10)}>+</button>
          </div>
        )}
        <button type="button" className="aw-tool" aria-label="History" title="History" onClick={onHistory}>
          <Icon24 name="clock" size={16} />
          {workspace.historyPending > 0 && <span className="aw-tool-dot" aria-hidden="true" />}
        </button>
        <span className="aw-status" title="Application status">
          <span className={`cf-dot is-${statusTone}`} aria-hidden="true" />{statusWord}
        </span>
      </div>
    </div>
  );
}
