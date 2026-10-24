import { useEffect, useId, useRef, useState } from "react";
import { Icon24 } from "../icons";
import { ToolButton } from "./ToolButton";
import type { VoiceStatus } from "../voice/session";
import {
  attachExisting, attachFiles, beginAttachPick, canAttach, commitVoice, dismissVoiceMessage, dismissVoiceNotice, endVoice, loadVoiceCapability, MAX_ATTACHMENTS,
  removeAttachment, requestVoice, startVoice, stopVoiceSpeaking, toggleVoiceMute, voiceLevel, type AssistantState, type AttachPick,
} from "./assistant";

const ACTIVE: ReadonlySet<VoiceStatus> = new Set(["mic", "connecting", "listening", "hearing", "sending", "speaking", "updating", "stopping"]);

/** The microphone button in the composer. Reading the capability is free; nothing starts here. */
export function VoiceButton({ a }: { a: AssistantState }) {
  useEffect(() => { void loadVoiceCapability(); }, [a.binding]);
  const cap = a.capability;
  if (ACTIVE.has(a.voice.status)) return null;
  const ready = cap.state === "ready" && cap.value.available;
  const why = cap.state === "ready"
    ? cap.value.available ? "Talk (voice)" : cap.value.reason || "Voice isn’t available on this server"
    : cap.state === "failed" ? "Voice isn’t available right now" : "Checking voice…";
  return (
    <ToolButton type="button" className="cf-icon-btn is-plain" aria-label={ready ? "Talk to the assistant" : `Voice unavailable: ${why}`} title={why} disabled={!ready || a.noticeOpen} onClick={requestVoice}>
      <MicGlyph size={16} />
    </ToolButton>
  );
}

/** Shown before the first start in this tab: the server's own notice, then an explicit Start. */
export function VoiceNotice({ a }: { a: AssistantState }) {
  const start = useRef<HTMLButtonElement>(null);
  useEffect(() => { start.current?.focus(); }, []);
  if (a.capability.state !== "ready") return null;
  return (
    <section className="cf-av-notice" aria-labelledby="cf-av-notice-title" onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); dismissVoiceNotice(); } }}>
      <h3 id="cf-av-notice-title" className="cf-av-notice-title"><MicGlyph size={14} />Before you talk</h3>
      <p className="cf-av-notice-text">{a.capability.value.notice}</p>
      <div className="cf-av-row">
        <button ref={start} type="button" className="cf-btn is-primary is-sm" onClick={() => void startVoice()}>Start voice</button>
        <button type="button" className="cf-btn is-ghost is-sm" onClick={dismissVoiceNotice}>Not now</button>
      </div>
    </section>
  );
}

const STATUS: Record<VoiceStatus, string> = {
  idle: "",
  mic: "Allow the microphone…",
  connecting: "Connecting…",
  listening: "Listening",
  hearing: "Hearing you",
  sending: "Thinking…",
  speaking: "Speaking",
  updating: "Catching up…",
  stopping: "Stopping…",
  ended: "",
};

function endedText(a: AssistantState): string | null {
  const v = a.voice;
  if (v.problem === "denied") return "Microphone blocked. Allow it in the browser, or type instead.";
  if (v.problem === "no-mic") return "No microphone found. Type instead.";
  if (v.problem === "no-answer") return "The microphone wasn’t allowed in time. Start again, or type instead.";
  if (v.problem === "busy") return `Voice is busy.${v.retryAfter ? ` Try again in ${v.retryAfter} s.` : " Try again soon."}`;
  switch (v.reason) {
    case "expired": return "Time’s up. Start again to keep talking.";
    case "limit": return "Voice limit reached. Start again to keep talking.";
    case "context_changed": return "Your application changed. Start voice again.";
    case "authorization_changed": return "Your sign-in changed. Start voice again.";
    case "disconnected": return "Voice disconnected.";
    case "invalid_request": return "Voice stopped. Start again.";
    case "unavailable": return "Voice isn’t available right now. Type instead.";
    default: return v.problem === "unavailable" ? "Voice isn’t available right now. Type instead." : null;
  }
}

/** A running conversation: the orb, one status word, time left, and the few controls it needs. */
export function VoiceBar({ a }: { a: AssistantState }) {
  const v = a.voice;
  if (v.status === "ended") {
    const text = endedText(a);
    if (!text) return null;
    const again = a.capability.state === "ready" && a.capability.value.available && v.problem !== "no-mic";
    return (
      <div className="cf-av-bar is-ended" role="status">
        <span className="cf-av-bar-text">{text}</span>
        {again && <button type="button" className="cf-btn is-xs" onClick={requestVoice}>Start again</button>}
        <ToolButton type="button" className="cf-icon-btn is-xs" aria-label="Dismiss" onClick={dismissVoiceMessage}><Icon24 name="x" size={14} /></ToolButton>
      </div>
    );
  }
  if (!ACTIVE.has(v.status)) return null;
  const hint = v.spent ? "Voice limit reached · end to start again" : v.lostTurn ? "Say that again" : null;
  return (
    <div className="cf-av-bar" role="group" aria-label="Voice">
      <Orb status={v.status} />
      <span className={`cf-av-bar-text${["connecting", "sending", "updating"].includes(v.status) ? " cf-av-shimmer" : ""}`} role="status" aria-live="polite">
        {v.muted ? "Muted" : STATUS[v.status]}
        {hint && <span className="cf-av-hint"> · {hint}</span>}
      </span>
      {v.remaining !== null && <span className="cf-av-time" aria-label={`${v.remaining} seconds left`}>{fmt(v.remaining)}</span>}
      <div className="cf-av-row">
        {v.canCommit && <button type="button" className="cf-btn is-xs" onClick={() => commitVoice()} title="Send what you said now">Done</button>}
        {(v.status === "speaking" || v.status === "sending") && (
          <button type="button" className="cf-btn is-xs is-ghost" onClick={() => stopVoiceSpeaking()}>Stop</button>
        )}
        <ToolButton type="button" className="cf-icon-btn is-xs" aria-pressed={v.muted} aria-label={v.muted ? "Unmute" : "Mute"} title={v.muted ? "Unmute" : "Mute"} onClick={() => toggleVoiceMute()}>
          {v.muted ? <MutedGlyph /> : <MicGlyph size={14} />}
        </ToolButton>
        <ToolButton type="button" className="cf-icon-btn is-xs" aria-label="End voice" title="End voice" onClick={() => endVoice()}>
          <Icon24 name="x" size={14} />
        </ToolButton>
      </div>
    </div>
  );
}

const fmt = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

/** A quiet ink orb that follows the voice level. Under reduced motion only its opacity changes. */
function Orb({ status }: { status: VoiceStatus }) {
  const el = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    let raf = 0;
    const loop = () => {
      el.current?.style.setProperty("--level", voiceLevel().toFixed(3));
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, []);
  return <span ref={el} className="cf-av-orb" data-status={status} aria-hidden="true" />;
}

function MutedGlyph() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
      <rect x="5.75" y="1.75" width="4.5" height="8" rx="2.25" />
      <path d="M3.5 7.5a4.5 4.5 0 0 0 9 0M8 12v2.25M2.5 2.5l11 11" />
    </svg>
  );
}

/** The selected PDFs, by actual stored file id. Coverage appears with each document reply. */
export function Attachments({ a }: { a: AssistantState }) {
  const list = a.conv.attachments;
  if (a.binding.mode !== "case" || !list.length) return null;
  return (
    <div className="cf-av-files">
      <span className="cf-av-files-label" title="Chat can find exact text excerpts, and voice can use limited PDF text. Up to three text-bearing pages per PDF; scans and images aren’t read.">
        <Icon24 name="clip" size={12} />Selected PDFs
      </span>
      {list.map((x) => (
        <span key={x.key} className={`cf-av-file is-${x.status}`} title={x.error ? `${x.name} · ${x.error}` : x.name}>
          <Icon24 name="clip" size={12} />
          <span className={`cf-av-file-name${x.status === "uploading" ? " cf-av-shimmer" : ""}`}>{x.name}</span>
          {x.status === "uploading" && <span className="cf-sr" role="status">Uploading</span>}
          {x.error && <span className="cf-av-file-error">{x.error}</span>}
          <ToolButton type="button" className="cf-av-file-x" aria-label={`Unselect ${x.name}`} title="Unselect PDF · keeps the stored file" onClick={() => removeAttachment(x.key)}><Icon24 name="x" size={12} /></ToolButton>
        </span>
      ))}
    </div>
  );
}

/** Add a PDF from this application, or upload one through its authorized file route. */
export function AttachButton({ a }: { a: AssistantState }) {
  const file = useRef<HTMLInputElement>(null);
  /** The application lifetime the open chooser belongs to; its files go nowhere else. */
  const pickFor = useRef<AttachPick | null>(null);
  const root = useRef<HTMLSpanElement>(null);
  const menuId = useId();
  const [menu, setMenu] = useState(false);
  const b = a.binding;
  const close = (focus = false) => { setMenu(false); if (focus) root.current?.querySelector<HTMLButtonElement>("button")?.focus(); };
  useEffect(() => { setMenu(false); }, [b.accountId, b.role, b.authority, b.caseId]);
  useEffect(() => {
    if (!menu) return;
    root.current?.querySelector<HTMLButtonElement>('[role="menuitem"]')?.focus();
    const outside = (e: PointerEvent) => { if (e.target instanceof Node && !root.current?.contains(e.target)) setMenu(false); };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [menu]);
  if (b.mode !== "case" || !canAttach()) return null;
  const list = a.conv.attachments;
  const live = list.filter((x) => x.status !== "failed").length;
  const known = new Map([...b.files, ...a.conv.uploaded].map((f) => [f.id, f]));
  const existing = [...known.values()].filter((f) => !list.some((x) => x.fileId === f.id && x.status !== "failed"));
  if (!b.canUpload && !existing.length) return null;
  const full = live >= MAX_ATTACHMENTS;
  const choose = () => { pickFor.current = beginAttachPick(); file.current?.click(); };
  const pick = () => (existing.length ? setMenu((m) => !m) : choose());
  const label = full ? `Up to ${MAX_ATTACHMENTS} selected PDFs` : existing.length ? "Select a PDF" : "Upload a PDF";
  return (
    <span ref={root} className="cf-av-add" onKeyDown={(e) => {
      if (menu && e.key === "Escape") { e.stopPropagation(); e.preventDefault(); close(true); return; }
      if (!existing.length || full) return;
      if (!menu && (e.key === "ArrowDown" || e.key === "ArrowUp")) { e.preventDefault(); setMenu(true); return; }
      if (!menu || !["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key)) return;
      e.preventDefault();
      const items = [...(root.current?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]') ?? [])];
      const current = items.indexOf(document.activeElement as HTMLButtonElement);
      const next = e.key === "Home" ? 0 : e.key === "End" ? items.length - 1 : (current + (e.key === "ArrowUp" ? -1 : 1) + items.length) % items.length;
      items[next]?.focus();
    }}>
      <ToolButton type="button" className="cf-icon-btn is-plain" aria-label={label} title={label} disabled={full} aria-haspopup={existing.length ? "menu" : undefined} aria-controls={menu ? menuId : undefined} aria-expanded={existing.length ? menu : undefined} onClick={pick}>
        <Icon24 name="clip" size={16} />
      </ToolButton>
      {menu && (
        <div id={menuId} className="cf-av-menu" role="menu" aria-label="Application PDFs">
          {existing.map((f) => (
            <button key={f.id} type="button" role="menuitem" onClick={() => { attachExisting(f.id, f.name); close(true); }}>
              <Icon24 name="file" size={14} /><span>{f.name}</span>
            </button>
          ))}
          {b.canUpload && (
            <button type="button" role="menuitem" onClick={() => { close(true); choose(); }}>
              <Icon24 name="up" size={14} /><span>Upload a PDF…</span>
            </button>
          )}
        </div>
      )}
      <input ref={file} type="file" accept="application/pdf,.pdf" multiple hidden onChange={(e) => {
        const files = [...(e.target.files ?? [])];
        e.target.value = "";
        const openedFor = pickFor.current;
        pickFor.current = null;
        if (openedFor) void attachFiles(files, openedFor);
      }} />
    </span>
  );
}

export function MicGlyph({ size = 12 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
      <rect x="5.75" y="1.75" width="4.5" height="8" rx="2.25" />
      <path d="M3.5 7.5a4.5 4.5 0 0 0 9 0M8 12v2.25" />
    </svg>
  );
}
