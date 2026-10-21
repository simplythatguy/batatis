import { useEffect, useRef, useState, type ReactNode } from "react";
import { useCase } from "../store";
import { buildDeck } from "./deck";
import { STAGES, type Screen } from "./routes";
import { resetSession, useSession } from "./session";
import { CIcon, ConfirmDialog, Dot, MoreIcon, type DotTone } from "./ui";

function useOutsideClose(open: boolean, close: () => void, ...refs: React.RefObject<HTMLElement | null>[]) {
  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      if (refs.some((r) => r.current?.contains(e.target as Node))) return;
      close();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("pointerdown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onDown);
      document.removeEventListener("keydown", onKey);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);
}

function SaveStatus() {
  const { phase, saveStatus, savedNote, saveDetail, saveDraft } = useCase();
  if (phase !== "case") return null;
  const map: Record<string, { tone: DotTone; label: string }> = {
    idle: { tone: "pending", label: "Not saved yet" },
    unsaved: { tone: "pending", label: "Unsaved" },
    saving: { tone: "pending", label: "Saving…" },
    saved: { tone: "done", label: "Saved" },
    failed: { tone: "blocking", label: savedNote || "Not saved" },
    gone: { tone: "blocking", label: savedNote },
  };
  const s = map[saveStatus] ?? map.idle;
  const problem = saveStatus === "failed" || saveStatus === "gone";
  return (
    <div className={`cf-save${problem ? " is-problem" : ""}`} role="status" title={[savedNote, saveDetail].filter(Boolean).join(" · ") || undefined}>
      <Dot tone={s.tone} />
      <span className="cf-save-label">{s.label}</span>
      {saveStatus === "unsaved" && (
        <button type="button" className="cf-btn is-xs is-ghost" onClick={() => void saveDraft()}>Save now</button>
      )}
      {saveStatus === "failed" && (
        <button type="button" className="cf-btn is-xs" onClick={() => void saveDraft()}>
          <CIcon name="retry" size={13} />Retry
        </button>
      )}
      {saveStatus === "gone" && <a className="cf-btn is-xs" href="#/application?download=options">Keep a draft</a>}
    </div>
  );
}

function StagePills({ active, done, disabled }: { active: Screen; done: Record<string, boolean>; disabled: boolean }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useOutsideClose(open, () => setOpen(false), box);
  const index = STAGES.findIndex((s) => s.screen === active);
  const current = STAGES[Math.max(index, 0)];
  const pills = (onPick?: () => void) =>
    STAGES.map((s) => {
      const isActive = s.screen === active;
      const href = s.screen === "start" ? "#/" : `#/${s.screen}`;
      const cls = `cf-stage${done[s.screen] && !isActive ? " is-done" : ""}`;
      if (disabled && s.screen !== "start") {
        return (
          <span key={s.screen} className={`${cls} is-disabled`} aria-disabled="true" title="Pick your role and press Start first">
            <span className="cf-stage-n">{s.n}</span>{s.label}
          </span>
        );
      }
      return (
        <a key={s.screen} className={cls} href={href} aria-current={isActive ? "step" : undefined} onClick={onPick}>
          <span className="cf-stage-n">{done[s.screen] && !isActive ? <CIcon name="check" size={11} /> : s.n}</span>
          {s.label}
        </a>
      );
    });
  return (
    <>
      <nav className="cf-stages" aria-label="Progress">{pills()}</nav>
      <div className="cf-stages-compact" ref={box}>
        <button type="button" className="cf-stage is-compact" aria-expanded={open} aria-haspopup="true" onClick={() => setOpen((v) => !v)} disabled={disabled}>
          <span className="cf-stage-n">{index >= 0 ? `${current.n}/04` : "··/04"}</span>
          {index >= 0 ? current.label : "Menu"}
        </button>
        {open && <div className="cf-pop cf-stage-pop">{pills(() => setOpen(false))}</div>}
      </div>
    </>
  );
}

function MoreMenu({ onStartOver }: { onStartOver: () => void }) {
  const [open, setOpen] = useState(false);
  const btn = useRef<HTMLButtonElement>(null);
  const pop = useRef<HTMLDivElement>(null);
  useOutsideClose(open, () => setOpen(false), btn, pop);
  useEffect(() => {
    if (open) pop.current?.querySelector<HTMLElement>("a,button")?.focus();
  }, [open]);
  const close = () => setOpen(false);
  return (
    <div className="cf-more">
      <button ref={btn} type="button" className="cf-icon-btn" aria-label="More" aria-expanded={open} aria-haspopup="menu" onClick={() => setOpen((v) => !v)}>
        <MoreIcon />
      </button>
      {open && (
        <div ref={pop} className="cf-pop cf-menu" role="menu" aria-label="More">
          <a role="menuitem" href="#/officer" onClick={close}>Officer view <span className="cf-mono cf-faint">SCO</span></a>
          <a role="menuitem" href="#/references" onClick={close}>All code references</a>
          <a role="menuitem" href="#/accuracy" onClick={close}>Accuracy report</a>
          <hr />
          <a role="menuitem" href="#/application?download=draft" onClick={close}>Download draft</a>
          <button role="menuitem" type="button" onClick={() => { close(); onStartOver(); }}>Start over</button>
        </div>
      )}
    </div>
  );
}

export function Shell({ active, children }: { active: Screen; children: ReactNode }) {
  const { c, gaps, phase, checkedAt, resetToWho } = useCase();
  const session = useSession();
  const [confirm, setConfirm] = useState(false);
  const inCase = phase === "case";
  const openLeft = inCase ? buildDeck(c, gaps, { seen: new Set(session.seen) }).filter((i) => !i.optional).length : 1;
  const done = {
    start: inCase && Boolean(c.description.trim()),
    questions: inCase && openLeft === 0,
    review: inCase && Boolean(checkedAt),
    application: false,
  };
  return (
    <div className="cf-app">
      <div className="cf-bloom" aria-hidden="true" />
      <header className="cf-top">
        <a className="cf-brand" href="#/" aria-label="Batatis, start">
          <span className="cf-mark" aria-hidden="true" />
          Batatis
        </a>
        <StagePills active={active} done={done} disabled={!inCase} />
        <div className="cf-top-right">
          <SaveStatus />
          {inCase && <MoreMenu onStartOver={() => setConfirm(true)} />}
        </div>
      </header>
      <main className="cf-main" id="main">{children}</main>
      <ConfirmDialog
        open={confirm}
        title="Start over?"
        body={<p>This clears your answers and files for this visit. Download a draft first if you need a copy.</p>}
        cancel="Keep my application"
        confirm="Start over"
        onClose={() => setConfirm(false)}
        onConfirm={() => {
          setConfirm(false);
          resetSession();
          resetToWho();
        }}
      />
    </div>
  );
}
