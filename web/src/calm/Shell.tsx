import { useEffect, useRef, useState, type ReactNode } from "react";
import { useCase } from "../store";
import { buildDeck } from "./deck";
import { STAGES, type Screen } from "./routes";
import { CodePalette, OPEN_PALETTE, openPalette } from "./CodePalette";
import { resetSession, useSession } from "./session";
import { resetRelevance } from "./useRelevance";
import { CIcon, ConfirmDialog, Dot, MOD_KEY, MoreIcon, type DotTone } from "./ui";

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
          <span className="cf-stage-n">{s.n}</span>
          {s.label}
          {done[s.screen] && !isActive && <span className="cf-sr"> (done)</span>}
        </a>
      );
    });
  return (
    <>
      <nav className="cf-stages" aria-label="Progress">{pills()}</nav>
      <div className="cf-stages-compact" ref={box}>
        <button type="button" className="cf-stage is-compact" aria-expanded={open} aria-haspopup="true" onClick={() => setOpen((v) => !v)} disabled={disabled}>
          {index >= 0 && <span className="cf-stage-n">{current.n}/04</span>}
          {index >= 0 ? current.label : "Steps"}
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
  const wasOpen = useRef(false);
  useEffect(() => {
    if (open) pop.current?.querySelector<HTMLElement>("[role=menuitem]")?.focus();
    // Closing returns focus to the trigger unless a pick moved focus somewhere on purpose.
    else if (wasOpen.current && (document.activeElement === document.body || !document.activeElement)) btn.current?.focus();
    wasOpen.current = open;
  }, [open]);
  const close = () => setOpen(false);
  function onMenuKey(e: React.KeyboardEvent) {
    const items = [...(pop.current?.querySelectorAll<HTMLElement>("[role=menuitem]") ?? [])];
    const at = items.indexOf(document.activeElement as HTMLElement);
    const to = (n: number) => { e.preventDefault(); items[(n + items.length) % items.length]?.focus(); };
    if (e.key === "ArrowDown") to(at + 1);
    else if (e.key === "ArrowUp") to(at - 1);
    else if (e.key === "Home") to(0);
    else if (e.key === "End") to(items.length - 1);
    else if (e.key === "Escape") { e.preventDefault(); e.nativeEvent.stopImmediatePropagation(); close(); btn.current?.focus(); }
    else if (e.key === "Tab") close();
  }
  return (
    <div className="cf-more">
      <button ref={btn} type="button" className="cf-icon-btn" aria-label="More" aria-expanded={open} aria-haspopup="menu" onClick={() => setOpen((v) => !v)}>
        <MoreIcon />
      </button>
      {open && (
        <div ref={pop} className="cf-pop cf-menu" role="menu" aria-label="More" onKeyDown={onMenuKey}>
          <button role="menuitem" tabIndex={-1} type="button" onClick={() => { close(); openPalette(); }}>Look up code <span className="cf-kbd is-dark" aria-hidden="true">{MOD_KEY} K</span></button>
          <a role="menuitem" tabIndex={-1} href="#/officer" onClick={close}>Officer view</a>
          <a role="menuitem" tabIndex={-1} href="#/code" onClick={close}>Code library</a>
          <a role="menuitem" tabIndex={-1} href="#/accuracy" onClick={close}>Accuracy report</a>
          <hr role="separator" />
          <a role="menuitem" tabIndex={-1} href="#/application?download=draft" onClick={close}>Download draft</a>
          <button role="menuitem" tabIndex={-1} type="button" onClick={() => { close(); onStartOver(); }}>Start over</button>
        </div>
      )}
    </div>
  );
}

export function Shell({ active, children }: { active: Screen; children: ReactNode }) {
  const { c, gaps, phase, checkedAt, resetToWho } = useCase();
  const session = useSession();
  const [confirm, setConfirm] = useState(false);
  const [palette, setPalette] = useState(false);
  const inCase = phase === "case";
  // ⌘K / Ctrl+K opens the code search anywhere in an application.
  useEffect(() => {
    if (!inCase) return;
    const on = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === "k" && (e.metaKey || e.ctrlKey) && !e.altKey) {
        e.preventDefault();
        setPalette((v) => !v);
      }
    };
    const open = () => setPalette(true);
    document.addEventListener("keydown", on);
    window.addEventListener(OPEN_PALETTE, open);
    return () => {
      document.removeEventListener("keydown", on);
      window.removeEventListener(OPEN_PALETTE, open);
    };
  }, [inCase]);
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
      {inCase && <CodePalette open={palette} onClose={() => setPalette(false)} />}
      <ConfirmDialog
        open={confirm}
        title="Start over?"
        body={<p>This clears your answers in this browser and starts a new case. Files already uploaded are not deleted now; they expire with the case. Download a draft first if you need a copy.</p>}
        cancel="Keep my application"
        confirm="Start over"
        onClose={() => setConfirm(false)}
        onConfirm={() => {
          setConfirm(false);
          resetSession();
          resetRelevance();
          resetToWho();
        }}
      />
    </div>
  );
}
