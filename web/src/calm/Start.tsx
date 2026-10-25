import { pagesLabel } from "../intakeView";
import { useEffect, useRef, useState } from "react";
import { useCase } from "../store";
import type { ApplicantType } from "../types";
import { readOnlyStatus } from "./applications";
import { useBegin, useCurrentApplication } from "./begin";
import { ROLE_CHOICES } from "./deck";
import { Icon24 } from "./icons";
import { Choices } from "./QuestionDeck";
import { updateSession, useSession } from "./session";
import { CIcon, Dot, Kbd, MOD_KEY } from "./ui";

let fileSeq = 0;
const fileId = () => `file-${Date.now().toString(36)}-${(fileSeq++).toString(36)}`;
const isPdf = (f: File) => f.type === "application/pdf" || /\.pdf$/i.test(f.name);
const isText = (f: File) => /^text\/(plain|markdown)$/.test(f.type) || /\.(txt|md|markdown)$/i.test(f.name);

/**
 * Describe: one headline and the composer, the one place the project is described. Without a role
 * from onboarding, Start asks who is applying next (one question, then the application starts);
 * the reviewing authority is a Section B question in the deck.
 */
export function Start() {
  const { c, phase, dispatch, resetNote, readDescription, submissionDispatched } = useCase();
  const session = useSession();
  const { begin, userRole } = useBegin();
  const [askRole, setAskRole] = useState(false);
  const { app, locked } = useCurrentApplication();
  const inCase = phase === "case";
  const [dragging, setDragging] = useState(false);
  const [note, setNote] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const area = useRef<HTMLTextAreaElement>(null);
  const text = inCase ? c.description : session.draft;
  const role = inCase ? c.applicantType : session.role;

  useEffect(() => { if (!locked && !askRole) area.current?.focus({ preventScroll: true }); }, [locked, askRole]);

  function setText(t: string) {
    if (inCase) dispatch({ type: "setDescription", text: t });
    else updateSession({ draft: t });
  }

  async function take(list: FileList | File[]) {
    if (locked) return;
    const files = [...list];
    const pdfs = files.filter(isPdf);
    const texts = files.filter((f) => !isPdf(f) && isText(f));
    const other = files.length - pdfs.length - texts.length;
    if (pdfs.length) {
      const made = pdfs.map((file) => ({ id: fileId(), file }));
      if (inCase) {
        dispatch({ type: "addFiles", files: made.map((m) => ({ id: m.id, name: m.file.name })) });
        updateSession((s) => ({ held: [...s.held, ...made] }));
      } else updateSession((s) => ({ draftFiles: [...s.draftFiles, ...made] }));
    }
    if (texts.length) {
      const bodies = await Promise.all(texts.map((f) => f.text()));
      const joined = [text.trim(), ...bodies.map((b) => b.trim())].filter(Boolean).join("\n\n");
      setText(joined);
    }
    const parts = [
      pdfs.length ? `${pdfs.length} PDF${pdfs.length > 1 ? "s" : ""} attached. Batatis reads the text of ${pdfs.length > 1 ? "each one" : "it"} when you start; scans and photos are not read.` : "",
      texts.length ? `Text from ${texts.map((f) => f.name).join(", ")} added to your description.` : "",
      other ? `${other} file${other > 1 ? "s" : ""} skipped. Batatis reads PDF, .txt and .md files.` : "",
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

  // Batatis reads the description and the text layer of attached PDFs (intake).
  const blocked = submissionDispatched ? "Submission in progress. Your saved answers are temporarily read-only."
    : locked ? readOnlyStatus(app?.status, app?.authority).note : !text.trim() ? "Describe your project to start." : "";

  function start() {
    if (blocked) return;
    if (inCase) {
      // Explicit action: read the edited description (and any new PDF) again, then continue.
      const changed = c.intake?.text !== c.description.trim() || c.intake?.filesChanged || session.held.length > 0;
      if (changed) void readDescription();
      location.hash = "#/questions";
      return;
    }
    // Without a role from onboarding, ask it here next; nothing is picked for the applicant.
    if (!begin()) setAskRole(true);
  }

  function pickRole(role: ApplicantType) {
    updateSession({ role });
    begin(role);
  }

  // A, B, C pick a role while that question shows.
  useEffect(() => {
    if (!askRole) return;
    const on = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey || document.querySelector("dialog[open]")) return;
      const t = e.target as HTMLElement | null;
      if (t?.closest?.("input, textarea, .cf-pop, [role='menu'], .cf-assist")) return;
      if (e.key === "Escape") { e.preventDefault(); setAskRole(false); return; }
      const n = /^[a-c]$/i.test(e.key) ? e.key.toLowerCase().charCodeAt(0) - 97 : /^[1-3]$/.test(e.key) ? Number(e.key) - 1 : -1;
      if (n >= 0) { e.preventDefault(); pickRole(ROLE_CHOICES[n].value); }
    };
    document.addEventListener("keydown", on);
    return () => document.removeEventListener("keydown", on);
  }, [askRole]); // eslint-disable-line react-hooks/exhaustive-deps
  const roleHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { if (askRole) roleHeading.current?.focus({ preventScroll: true }); }, [askRole]);

  function removeFile(id: string) {
    if (locked) return;
    if (!inCase) {
      updateSession((s) => ({ draftFiles: s.draftFiles.filter((f) => f.id !== id) }));
      return setNote("Removed. It was not uploaded.");
    }
    const uploaded = c.files.find((f) => f.id === id)?.read;
    dispatch({ type: "removeFile", id });
    updateSession((s) => ({ held: s.held.filter((f) => f.id !== id) }));
    // There is no delete route for an uploaded file; say what actually happens to it.
    setNote(uploaded ? "Removed from this application. Copies already uploaded expire with the case." : "Removed. It was not uploaded.");
  }

  const fileRows = inCase
    ? c.files.map((f) => {
        const report = f.engineId ? c.intake?.record.files.find((r) => r.file_id === f.engineId) : undefined;
        const state = f.error
          ? { tone: "blocking" as const, label: f.error }
          : report
            ? report.status === "read"
              ? { tone: "done" as const, label: `Read · ${pagesLabel(report.pages ?? report.pages_read.length)}` }
              : { tone: "warning" as const, label: report.status === "partly_read" ? "Partly read" : "Not read", reason: report.reason ?? undefined }
          : f.read
            ? { tone: "done" as const, label: "Uploaded" }
            : session.uploading.includes(f.id)
              ? { tone: "pending" as const, label: "Uploading…" }
              : session.held.some((h) => h.id === f.id)
                ? { tone: "pending" as const, label: "Uploads once your case is saved" }
                : { tone: "warning" as const, label: "Not uploaded" };
        return { id: f.id, name: f.name, ...state };
      })
    : session.draftFiles.map((f) => ({ id: f.id, name: f.file.name, tone: "pending" as const, label: "Attaches after Start" }));

  if (askRole && !inCase && !userRole) {
    return (
      <div className="cf-start is-role">
        <div className="cf-q-wrap is-from-down" role="group" aria-labelledby="cf-role-q">
          <h1 ref={roleHeading} id="cf-role-q" className="cf-q-text" tabIndex={-1}>Who is applying?</h1>
          <p className="cf-q-help">This decides which starting questions you get. Batatis never picks one for you.</p>
          <Choices choices={ROLE_CHOICES.map((r) => ({ value: r.value as string, label: r.label }))} current={session.role ?? undefined} onPick={(v) => pickRole(v as ApplicantType)} />
          <button type="button" className="cf-link-btn cf-role-back" onClick={() => setAskRole(false)}>
            <Icon24 name="up" size={15} />Back to your description
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="cf-start">
      {dragging && (
        <div className="cf-drop" aria-hidden="true">
          <div className="cf-drop-box"><CIcon name="upload" size={22} /><span>Drop to attach</span><small>PDF plans, or .txt and .md notes</small></div>
        </div>
      )}
      <h1 className="cf-display">What are you building differently?</h1>

      <div className={`cf-composer cf-glass${dragging ? " is-drop" : ""}`}>
        {fileRows.length > 0 && (
          <ul className="cf-files" aria-label="Attached files">
            {fileRows.map((f) => (
              <li key={f.id} className="cf-file">
                <span className="cf-ext">PDF</span>
                <span className="cf-file-name">{f.name}</span>
                <span className={`cf-file-state is-${f.tone}`} title={"reason" in f ? f.reason : undefined}><Dot tone={f.tone} />{f.label}</span>
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
          placeholder={role === "manufacturer" ? "What is your product, and how will builders use it?" : "What are you building, and what do you want to do differently?"}
        />
        <div className="cf-composer-foot">
          <div className="cf-attach">
            {/* Hidden: the Attach plans button is the control. */}
            <input ref={input} hidden type="file" multiple accept=".pdf,.txt,.md,application/pdf,text/plain,text/markdown" tabIndex={-1} aria-hidden="true"
              onChange={(e) => { if (e.target.files?.length) void take(e.target.files); e.target.value = ""; }} />
            <button type="button" className="cf-chip" disabled={locked} onClick={() => input.current?.click()}>
              <CIcon name="clip" size={14} />Attach plans
            </button>
            <span className="cf-faint cf-small cf-drop-hint">or drop files anywhere</span>
          </div>
          <button type="button" className="cf-btn is-primary" disabled={Boolean(blocked)} title={blocked || undefined} onClick={start}>
            {inCase ? "Continue" : "Start"} <Kbd>{MOD_KEY} ↵</Kbd>
          </button>
        </div>
      </div>
      <div className="cf-start-notes">
        {locked && blocked && <p className="cf-faint cf-small" role="note">{blocked}</p>}
        {note && <p className="cf-faint cf-small" role="status">{note}</p>}
        {!inCase && resetNote && <p className="cf-faint cf-small" role="status">{resetNote}</p>}
      </div>
    </div>
  );
}
