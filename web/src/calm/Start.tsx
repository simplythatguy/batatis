import { pagesLabel } from "../intakeView";
import { useEffect, useRef, useState } from "react";
import { useCase } from "../store";
import { useAccount } from "./account";
import { readOnlyStatus } from "./applications";
import { requestStartSignIn } from "./auth/useAuthGate";
import { useBegin, useCurrentApplication } from "./begin";
import { getSession, updateSession, useSession } from "./session";
import { CIcon, Dot, Kbd, MOD_KEY } from "./ui";

let fileSeq = 0;
const fileId = () => `file-${Date.now().toString(36)}-${(fileSeq++).toString(36)}`;
const isPdf = (f: File) => f.type === "application/pdf" || /\.pdf$/i.test(f.name);
const isImage = (f: File) => /^image\/(jpeg|png|webp)$/.test(f.type) || /\.(jpe?g|png|webp)$/i.test(f.name);
const isText = (f: File) => /^text\/(plain|markdown)$/.test(f.type) || /\.(txt|md|markdown)$/i.test(f.name);

/**
 * The public front door: prepare text or files, then sign in and start reading. The person's
 * part in the project is a later paperwork question.
 */
export function Start() {
  const caseActions = useCase();
  const { c, phase, dispatch, resetNote, readDescription, submissionDispatched } = caseActions;
  const account = useAccount();
  const session = useSession();
  const { begin } = useBegin();
  const { app, locked } = useCurrentApplication();
  const inCase = phase === "case";
  const [dragging, setDragging] = useState(false);
  const [note, setNote] = useState("");
  const [attaching, setAttaching] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const area = useRef<HTMLTextAreaElement>(null);
  const text = inCase ? c.description : session.draft;
  const textRef = useRef(text);
  textRef.current = text;

  useEffect(() => { if (!locked) area.current?.focus({ preventScroll: true }); }, [locked]);

  useEffect(() => {
    if (!inCase && session.startRequested && !session.draftFilesLost && !attaching) begin();
  }, [inCase, session.startRequested, session.draftFilesLost, session.draftFiles, attaching, account.phase, account.user, begin]);

  function setText(t: string) {
    if (inCase) dispatch({ type: "setDescription", text: t });
    else updateSession({ draft: t });
  }

  async function take(list: FileList | File[]) {
    if (locked) return;
    const files = [...list];
    const attachments = files.filter((f) => isPdf(f) || isImage(f));
    const texts = files.filter((f) => !isPdf(f) && !isImage(f) && isText(f));
    const other = files.length - attachments.length - texts.length;
    if (texts.length) setAttaching(true);
    if (attachments.length) {
      const made = attachments.map((file) => ({ id: fileId(), file }));
      if (inCase) {
        dispatch({ type: "addFiles", files: made.map((m) => ({ id: m.id, name: m.file.name })) });
        updateSession((s) => ({ held: [...s.held, ...made] }));
      } else updateSession((s) => ({ draftFiles: [...s.draftFiles, ...made], draftFilesLost: false }));
    }
    if (texts.length) {
      try {
        const bodies = await Promise.all(texts.map((f) => f.text()));
        const current = inCase ? textRef.current : getSession().draft;
        setText([current.trim(), ...bodies.map((b) => b.trim())].filter(Boolean).join("\n\n"));
      } catch {
        setNote("Couldn’t read those notes. Try again.");
        return;
      } finally {
        setAttaching(false);
      }
    }
    const parts = [
      attachments.length ? `${attachments.length} file${attachments.length > 1 ? "s" : ""} attached.` : "",
      texts.length ? "Notes added." : "",
      other ? "Use PDF, JPG, PNG, WebP, TXT or MD." : "",
    ];
    setNote(parts.filter(Boolean).join(" "));
  }

  // The whole window is a drop target while this screen is open.
  useEffect(() => {
    let depth = 0;
    const hasFiles = (e: globalThis.DragEvent) => [...(e.dataTransfer?.types ?? [])].includes("Files");
    const enter = (e: globalThis.DragEvent) => { if (!hasFiles(e)) return; depth++; setDragging(true); };
    const leave = (e: globalThis.DragEvent) => { if (!hasFiles(e)) return; depth = Math.max(0, depth - 1); if (!depth) setDragging(false); };
    const over = (e: globalThis.DragEvent) => { if (hasFiles(e)) e.preventDefault(); };
    const drop = (e: globalThis.DragEvent) => {
      if (!hasFiles(e)) return;
      e.preventDefault();
      depth = 0;
      setDragging(false);
      if (e.dataTransfer?.files.length) void takeRef.current(e.dataTransfer.files);
    };
    window.addEventListener("dragenter", enter);
    window.addEventListener("dragleave", leave);
    window.addEventListener("dragover", over);
    window.addEventListener("drop", drop);
    return () => {
      window.removeEventListener("dragenter", enter);
      window.removeEventListener("dragleave", leave);
      window.removeEventListener("dragover", over);
      window.removeEventListener("drop", drop);
    };
  }, []);
  const takeRef = useRef(take);
  takeRef.current = take;

  const blocked = submissionDispatched ? "Submission in progress. Your saved answers are temporarily read-only."
    : locked ? readOnlyStatus(app?.status, app?.authority).note
    : attaching ? "Reading notes…"
    : !inCase && session.draftFilesLost ? "Attach your files again."
    : !text.trim() && !(inCase ? c.files.length : session.draftFiles.length) ? "Add a description or file to start." : "";

  function start() {
    if (blocked) return;
    if (account.phase === "signed-out") {
      requestStartSignIn();
      return;
    }
    if (inCase) {
      // Explicit action: read the edited description and any new files again, then continue.
      const changed = c.intake?.text !== c.description.trim() || c.intake?.filesChanged || session.held.length > 0;
      if (changed) void readDescription();
      location.hash = "#/questions";
      return;
    }
    begin();
  }

  const reattachFile = (_id: string) => { setNote("Attach the file again to retry."); input.current?.click(); };
  // integrate: W1 use caseActions.retryUpload on this line.
  const retryUpload = reattachFile;

  function removeFileLocally(id: string): number {
    dispatch({ type: "removeFile", id });
    updateSession((s) => ({ held: s.held.filter((f) => f.id !== id) }));
    return 0;
  }
  // integrate: W1 use caseActions.removeFile on this line (returns cleared answers).
  const removeCaseFile = removeFileLocally;

  function removeFile(id: string) {
    if (locked) return;
    if (!inCase) {
      updateSession((s) => ({ draftFiles: s.draftFiles.filter((f) => f.id !== id) }));
      return setNote("Removed. It was not uploaded.");
    }
    const uploaded = c.files.find((f) => f.id === id)?.read;
    const removedAnswers = removeCaseFile(id);
    // There is no delete route for an uploaded file; say what actually happens to it.
    setNote(removedAnswers > 0 ? `Removed · ${removedAnswers} unconfirmed answer${removedAnswers === 1 ? "" : "s"} cleared.` : uploaded ? "Removed from this application. Uploaded copies expire with the case." : "Removed. It was not uploaded.");
  }

  const fileRows = inCase
    ? c.files.map((f) => {
        const report = f.engineId ? c.intake?.record.files.find((r) => r.file_id === f.engineId) : undefined;
        // integrate: W1 replace this expression with report ? fileReadLabel(report) : "".
        const readLabel = report ? report.status === "read" ? `Read · ${pagesLabel(report.pages ?? report.pages_read.length)}` : report.status === "partly_read" ? "Partly read" : "Not read" : "";
        const state = f.error
          ? { tone: "blocking" as const, label: f.error }
          : report
            ? report.status === "read"
              ? { tone: "done" as const, label: readLabel }
              : { tone: "warning" as const, label: readLabel, reason: report.reason ?? undefined }
          : f.read
            ? { tone: "done" as const, label: "Uploaded" }
            : session.uploading.includes(f.id)
              ? { tone: "pending" as const, label: "Uploading…" }
              : session.held.some((h) => h.id === f.id)
                ? { tone: "pending" as const, label: "Uploads once your case is saved" }
                : { tone: "warning" as const, label: "Not uploaded" };
        return { id: f.id, name: f.name, failed: Boolean(f.error), ...state };
      })
    : session.draftFiles.map((f) => ({ id: f.id, name: f.file.name, failed: false, tone: "pending" as const, label: "Ready" }));

  return (
    <div className="cf-start">
      {dragging && (
        <div className="cf-drop" aria-hidden="true">
          <div className="cf-drop-box"><CIcon name="upload" size={22} /><span>Drop to attach</span><small>PDF · JPG · PNG · TXT</small></div>
        </div>
      )}
      <h1 className="cf-display">What are you building?</h1>

      <div className={`cf-composer cf-glass${dragging ? " is-drop" : ""}`}>
        {fileRows.length > 0 && (
          <ul className="cf-files" aria-label="Attached files">
            {fileRows.map((f) => (
              <li key={f.id} className="cf-file">
                <span className="cf-ext">{/\.(pdf|jpe?g|png|webp)$/i.exec(f.name)?.[1].toUpperCase() ?? "File"}</span>
                <span className="cf-file-name">{f.name}</span>
                <span className={`cf-file-state is-${f.tone}`} title={"reason" in f ? f.reason : undefined}><Dot tone={f.tone} />{f.label}</span>
                {f.failed && <button type="button" className="cf-btn is-ghost is-xs" aria-label={`Retry ${f.name}`} disabled={locked} onClick={() => void retryUpload(f.id)}>Retry</button>}
                <button type="button" className="cf-icon-btn is-xs" aria-label={`Remove ${f.name}`} disabled={locked} onClick={() => removeFile(f.id)}>
                  <CIcon name="close" size={12} />
                </button>
              </li>
            ))}
          </ul>
        )}
        <label className="cf-sr" htmlFor="cf-describe">Describe your project</label>
        <textarea
          ref={area}
          id="cf-describe"
          readOnly={locked}
          className="cf-composer-text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              start();
            }
          }}
          placeholder="Or say it in a few words"
        />
        <div className="cf-composer-foot">
          <div className="cf-attach">
            {/* Hidden: the Attach files button is the control. */}
            <input ref={input} hidden type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.webp,.txt,.md,.markdown,application/pdf,image/jpeg,image/png,image/webp,text/plain,text/markdown" tabIndex={-1} aria-hidden="true"
              onChange={(e) => { if (e.target.files?.length) void take(e.target.files); e.target.value = ""; }} />
            <button type="button" className="cf-chip" disabled={locked} onClick={() => input.current?.click()}>
              <CIcon name="clip" size={14} />Attach files
            </button>
            <span className="cf-faint cf-small cf-drop-hint">PDF · JPG · PNG · TXT</span>
          </div>
          <button type="button" className="cf-btn is-primary" disabled={Boolean(blocked)} title={blocked || undefined} aria-describedby={blocked ? "cf-start-blocked" : undefined} onClick={start}>
            {inCase ? "Continue" : "Start"} <Kbd>{MOD_KEY} ↵</Kbd>
          </button>
        </div>
      </div>
      <div className="cf-start-notes">
        {blocked && <p id="cf-start-blocked" className="cf-faint cf-small" role="status">{blocked}</p>}
        {!inCase && session.draftFilesLost && text.trim() && <button type="button" className="cf-link-btn" onClick={() => updateSession({ draftFilesLost: false })}>Use description only</button>}
        {note && <p className="cf-faint cf-small" role="status">{note}</p>}
        {!inCase && resetNote && <p className="cf-faint cf-small" role="status">{resetNote}</p>}
      </div>
    </div>
  );
}
