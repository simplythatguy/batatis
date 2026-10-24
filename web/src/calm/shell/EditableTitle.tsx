import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { TITLE_MAX } from "../rename";

/**
 * The application name, renamed in place (the pattern Irsal's studio uses): double-click or F2 (or
 * Enter) edits, Enter or leaving the field saves, Escape cancels. Editing keeps the same type and
 * place and only adds a caret at the end: no field box, no selection. While saving the new name shows
 * quietly; a failed save puts the old name back and keeps the typed one for Retry.
 */
export function EditableTitle({ value, label, disabled, onCommit }: {
  value: string;
  /** Accessible name of the field, for example "Application name". */
  label: string;
  /** A sent or closed application: the name is plain text. */
  disabled?: boolean;
  onCommit: (title: string) => Promise<string | null>;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const [pending, setPending] = useState<string | null>(null);
  const [failed, setFailed] = useState<{ message: string; draft: string } | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const cancelled = useRef(false);
  const restoreFocus = useRef(false);
  const live = useRef(true);
  // Set on every mount: StrictMode mounts, unmounts and mounts again in development.
  useEffect(() => {
    live.current = true;
    return () => { live.current = false; };
  }, []);
  // A different application (or a name saved elsewhere) clears this one's leftovers.
  useEffect(() => { setFailed(null); setPending(null); }, [value]);
  useLayoutEffect(() => {
    const field = input.current;
    if (editing && field) {
      field.focus();
      field.setSelectionRange(field.value.length, field.value.length);
    }
    if (!editing && restoreFocus.current) {
      restoreFocus.current = false;
      button.current?.focus();
    }
  }, [editing]);

  async function save(next: string) {
    setFailed(null);
    setPending(next);
    const error = await onCommit(next);
    if (!live.current) return;
    setPending(null);
    if (error) setFailed({ message: error, draft: next });
  }
  function start(from = value) {
    if (disabled) return;
    cancelled.current = false;
    setDraft(from);
    setEditing(true);
  }
  function finish(focus = false) {
    const next = draft.replace(/\s+/g, " ").trim();
    const commit = !cancelled.current && next && next !== value;
    cancelled.current = true;
    restoreFocus.current = focus;
    setEditing(false);
    if (commit) void save(next);
  }

  const shown = pending ?? value;
  if (disabled) return <span className="cf-title-text" title={value}>{value}</span>;
  return (
    <>
      {editing ? (
        <span className="cf-title is-editing" onPointerDown={(e) => e.stopPropagation()}>
          <span className="cf-title-text">
            <span className="cf-title-measure" aria-hidden="true">{draft || " "}</span>
            <input
              ref={input}
              className="cf-title-input"
              aria-label={label}
              value={draft}
              maxLength={TITLE_MAX}
              onChange={(e) => setDraft(e.target.value)}
              onBlur={() => finish()}
              onKeyDown={(e) => {
                e.stopPropagation();
                if (e.nativeEvent.isComposing) return;
                if (e.key === "Enter") { e.preventDefault(); finish(true); }
                else if (e.key === "Escape") { e.preventDefault(); cancelled.current = true; finish(true); }
              }}
            />
          </span>
        </span>
      ) : (
        <button
          ref={button}
          type="button"
          className={`cf-title${pending ? " is-saving" : ""}`}
          title="Double-click to rename · F2"
          aria-label={`${shown}. ${label}: double-click or F2 to rename`}
          aria-keyshortcuts="F2 Enter"
          aria-busy={pending ? true : undefined}
          onDoubleClick={() => start()}
          onKeyDown={(e) => {
            if (e.key === "F2" || e.key === "Enter") { e.preventDefault(); e.stopPropagation(); start(); }
          }}
        >
          <span className="cf-title-text">{shown}</span>
        </button>
      )}
      {failed && !editing && (
        <span className="cf-title-error" role="alert" title={failed.message}>
          <span className="cf-dot is-blocking" aria-hidden="true" />
          <span aria-hidden="true">Not saved</span>
          <span className="cf-sr">{failed.message}</span>
          <button type="button" className="cf-link-btn" onClick={() => void save(failed.draft)}>Retry</button>
          <button type="button" className="cf-link-btn" onClick={() => start(failed.draft)}>Edit</button>
        </span>
      )}
    </>
  );
}
