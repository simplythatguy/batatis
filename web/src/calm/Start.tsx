import { useEffect, useRef, useState } from "react";
import { AUTHORITIES } from "../config";
import { applicantLabel } from "../intake";
import { PRIVACY_NOTICE } from "../privacy";
import { splitNoticeUrl } from "../rules";
import { useCase } from "../store";
import type { AuthorityId } from "../types";
import { resetSession, updateSession, useSession, type HeldFile } from "./session";
import { CIcon, Dot, Eyebrow, Kbd, MOD_KEY } from "./ui";

type Role = "manufacturer" | "contractor" | "homebuilder";
const ROLES: { id: Role; label: string }[] = [
  { id: "manufacturer", label: "Manufacturer" },
  { id: "contractor", label: "Contractor" },
  { id: "homebuilder", label: "Homebuilder" },
];

let fileSeq = 0;
const fileId = () => `file-${Date.now().toString(36)}-${(fileSeq++).toString(36)}`;
const isPdf = (f: File) => f.type === "application/pdf" || /\.pdf$/i.test(f.name);
const isText = (f: File) => /^text\/(plain|markdown)$/.test(f.type) || /\.(txt|md|markdown)$/i.test(f.name);

const [PRIVACY_LEAD, ...PRIVACY_REST] = PRIVACY_NOTICE.split(/(?<=\.)\s+/);
const PRIVACY_MORE = splitNoticeUrl(PRIVACY_REST.join(" "));

export function Start({ focus }: { focus: string | null }) {
  const { c, phase, dispatch, beginEmpty, resetNote, requestCheck } = useCase();
  const session = useSession();
  const inCase = phase === "case";
  const [held, setHeld] = useState("");
  const [role, setRole] = useState<Role | null>(null);
  const [authority, setAuthority] = useState<AuthorityId | "unsure" | null>(null);
  const [heldFiles, setHeldFiles] = useState<HeldFile[]>([]);
  const [dragging, setDragging] = useState(false);
  const [note, setNote] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const reviewer = useRef<HTMLDivElement>(null);
  const text = inCase ? c.description : held;
  const chosenRole = inCase ? (c.applicantType as Role) : role;
  const chosenAuthority: AuthorityId | "unsure" | null = inCase ? c.authority || (session.authorityUnsure ? "unsure" : null) : authority;

  useEffect(() => {
    if (focus === "authority") reviewer.current?.querySelector<HTMLElement>("button")?.focus();
  }, [focus]);

  function setText(t: string) {
    if (inCase) dispatch({ type: "setDescription", text: t });
    else setHeld(t);
  }

  async function take(list: FileList | File[]) {
    const files = [...list];
    const pdfs = files.filter(isPdf);
    const texts = files.filter((f) => !isPdf(f) && isText(f));
    const other = files.length - pdfs.length - texts.length;
    if (pdfs.length) {
      const made = pdfs.map((file) => ({ id: fileId(), file }));
      if (inCase) {
        dispatch({ type: "addFiles", files: made.map((m) => ({ id: m.id, name: m.file.name })) });
        updateSession((s) => ({ held: [...s.held, ...made] }));
      } else setHeldFiles((h) => [...h, ...made]);
    }
    if (texts.length) {
      const bodies = await Promise.all(texts.map((f) => f.text()));
      const joined = [text.trim(), ...bodies.map((b) => b.trim())].filter(Boolean).join("\n\n");
      setText(joined);
    }
    const parts = [
      pdfs.length ? `${pdfs.length} PDF${pdfs.length > 1 ? "s" : ""} attached.` : "",
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

  const blocked = !chosenRole ? "Pick your role to start." : !text.trim() && !heldFiles.length && !c.files.length ? "Describe it in a sentence, or attach your plans." : "";

  function start() {
    if (blocked) return;
    if (inCase) {
      // Explicit action: check the edited draft, then continue.
      void requestCheck();
      location.hash = "#/questions";
      return;
    }
    const files = heldFiles;
    beginEmpty(chosenRole!);
    if (held.trim()) dispatch({ type: "setDescription", text: held });
    if (authority && authority !== "unsure") dispatch({ type: "setAuthority", authority });
    if (files.length) dispatch({ type: "addFiles", files: files.map((f) => ({ id: f.id, name: f.file.name })) });
    resetSession({ held: files, authorityUnsure: authority === "unsure", checkAfterStart: true });
    location.hash = "#/questions";
  }

  function pickAuthority(value: AuthorityId | "unsure") {
    if (!inCase) return setAuthority(value);
    dispatch({ type: "setAuthority", authority: value === "unsure" ? "" : value });
    updateSession({ authorityUnsure: value === "unsure" });
  }

  function removeFile(id: string) {
    if (!inCase) return setHeldFiles((h) => h.filter((f) => f.id !== id));
    dispatch({ type: "removeFile", id });
    updateSession((s) => ({ held: s.held.filter((f) => f.id !== id) }));
  }

  const fileRows = inCase
    ? c.files.map((f) => {
        const state = f.error
          ? { tone: "blocking" as const, label: f.error }
          : f.read
            ? { tone: "done" as const, label: "Attached" }
            : session.uploading.includes(f.id)
              ? { tone: "pending" as const, label: "Uploading…" }
              : session.held.some((h) => h.id === f.id)
                ? { tone: "pending" as const, label: "Uploads once your case is saved" }
                : { tone: "warning" as const, label: "Not uploaded" };
        return { id: f.id, name: f.name, ...state };
      })
    : heldFiles.map((f) => ({ id: f.id, name: f.file.name, tone: "pending" as const, label: "Uploads after Start" }));

  return (
    <div className="cf-start">
      {dragging && (
        <div className="cf-drop" aria-hidden="true">
          <div className="cf-drop-box"><CIcon name="upload" size={22} /><span>Drop to attach</span><small>PDF plans, or .txt and .md notes</small></div>
        </div>
      )}
      <Eyebrow>Alternative solution application</Eyebrow>
      <h1 className="cf-display">Tell us what you’re building differently.</h1>
      <p className="cf-lede">Drop your plans or describe it in a sentence. Batatis finds the code that applies, asks only what’s missing, and drafts your variance application.</p>

      <div className={`cf-composer cf-glass${dragging ? " is-drop" : ""}`}>
        {fileRows.length > 0 && (
          <ul className="cf-files" aria-label="Attached files">
            {fileRows.map((f) => (
              <li key={f.id} className="cf-file">
                <span className="cf-ext">PDF</span>
                <span className="cf-file-name">{f.name}</span>
                <span className={`cf-file-state is-${f.tone}`}><Dot tone={f.tone} />{f.label}</span>
                <button type="button" className="cf-icon-btn is-xs" aria-label={`Remove ${f.name}`} onClick={() => removeFile(f.id)}>
                  <CIcon name="close" size={12} />
                </button>
              </li>
            ))}
          </ul>
        )}
        <label className="cf-sr" htmlFor="cf-describe">Describe your project</label>
        <textarea
          id="cf-describe"
          className="cf-composer-text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              start();
            }
          }}
          placeholder={chosenRole === "manufacturer" ? "What is your product, and how will builders use it?" : "What are you building, and what do you want to do differently?"}
        />
        <div className="cf-composer-foot">
          <div className="cf-attach">
            <input ref={input} className="cf-sr" type="file" multiple accept=".pdf,.txt,.md,application/pdf,text/plain,text/markdown" tabIndex={-1} aria-hidden="true"
              onChange={(e) => { if (e.target.files?.length) void take(e.target.files); e.target.value = ""; }} />
            <button type="button" className="cf-chip" onClick={() => input.current?.click()}>
              <CIcon name="clip" size={14} />Attach plans
            </button>
            <span className="cf-faint cf-small cf-drop-hint">or drop files anywhere</span>
          </div>
          <button type="button" className="cf-btn is-primary" disabled={Boolean(blocked)} onClick={start}>
            {inCase ? "Continue" : "Start"} <Kbd>{MOD_KEY} ↵</Kbd>
          </button>
        </div>
      </div>
      <div className="cf-start-notes">
        {blocked && <p className="cf-hint" role="note">{blocked}</p>}
        {note && <p className="cf-faint cf-small" role="status">{note}</p>}
        {!inCase && resetNote && <p className="cf-faint cf-small" role="status">{resetNote}</p>}
        <div className="cf-faint cf-small cf-privacy">
          <span>{PRIVACY_LEAD}</span>
          <details className="cf-inline-details">
            <summary>How your text is handled</summary>
            <span>{PRIVACY_MORE.text}{PRIVACY_MORE.url && <> <a href={PRIVACY_MORE.url} target="_blank" rel="noopener noreferrer">OpenAI API data policy<span className="cf-sr"> (opens in a new tab)</span></a></>}</span>
          </details>
        </div>
      </div>

      <div className="cf-choices">
        <div className="cf-choice-row" role="group" aria-labelledby="cf-role-label">
          <span className="cf-choice-label" id="cf-role-label">I’m a</span>
          {ROLES.map((r) => (
            <button key={r.id} type="button" className="cf-chip" aria-pressed={chosenRole === r.id} aria-disabled={inCase || undefined}
              onClick={() => { if (!inCase) setRole(r.id); }}>
              {r.label}
            </button>
          ))}
          {inCase && <span className="cf-faint cf-small">{applicantLabel(c.applicantType)} · Start over to change</span>}
        </div>
        <div className="cf-choice-row" role="group" aria-labelledby="cf-auth-label" ref={reviewer}>
          <span className="cf-choice-label" id="cf-auth-label">Reviewed by</span>
          {AUTHORITIES.map((a) => (
            <button key={a.id} type="button" className="cf-chip" aria-pressed={chosenAuthority === a.id} onClick={() => pickAuthority(a.id)}>{a.name}</button>
          ))}
          <button type="button" className="cf-chip" aria-pressed={chosenAuthority === "unsure"} onClick={() => pickAuthority("unsure")}>Not sure</button>
        </div>
      </div>

      <ol className="cf-how" aria-label="How it works">
        <li><span>01</span>Describe it</li>
        <li><span>02</span>Answer a few questions</li>
        <li><span>03</span>Download your application</li>
      </ol>
    </div>
  );
}

