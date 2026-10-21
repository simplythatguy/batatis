import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { ApplicationSummary } from "../api/accounts";
import { groupGaps } from "../humanReview";
import { useCase } from "../store";
import { bootAccount, initials, useAccount } from "./account";
import { authorityName } from "./applications";
import { AssistantPanel } from "./assistant/AssistantPanel";
import { setAssistantCase, toggleAssistant, useAssistant } from "./assistant/assistant";
import { CodePalette, OPEN_PALETTE, openPalette } from "./CodePalette";
import { buildDeck, deckProgress } from "./deck";
import { Icon24 } from "./icons";
import { type Screen } from "./routes";
import { resetSession, useSession } from "./session";
import { AppHeader, type StageRingItem } from "./shell/AppHeader";
import { AppLayout } from "./shell/AppLayout";
import { ApplicationList, type ApplicationListHandle } from "./shell/ApplicationList";
import { Rail, type RailDestination } from "./shell/Rail";
import { resetRelevance } from "./useRelevance";
import { CIcon, ConfirmDialog, Dot, MOD_KEY, type DotTone } from "./ui";

function useOutsideClose(open: boolean, close: () => void, ...refs: React.RefObject<HTMLElement | null>[]) {
  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      if (refs.some((r) => r.current?.contains(e.target as Node))) return;
      close();
    };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);
}

export function SaveStatus() {
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
      {saveStatus === "unsaved" && <button type="button" className="cf-btn is-xs is-ghost" onClick={() => void saveDraft()}>Save now</button>}
      {saveStatus === "failed" && <button type="button" className="cf-btn is-xs" onClick={() => void saveDraft()}><CIcon name="retry" size={13} />Retry</button>}
      {saveStatus === "gone" && <a className="cf-btn is-xs" href="#/application?download=options">Keep a draft</a>}
    </div>
  );
}

export function MoreMenu({ items }: { items: { label: string; href?: string; onClick?: () => void; hint?: string; separator?: boolean }[] }) {
  const [open, setOpen] = useState(false);
  const btn = useRef<HTMLButtonElement>(null);
  const pop = useRef<HTMLDivElement>(null);
  useOutsideClose(open, () => setOpen(false), btn, pop);
  const wasOpen = useRef(false);
  useEffect(() => {
    if (open) pop.current?.querySelector<HTMLElement>("[role=menuitem]")?.focus();
    else if (wasOpen.current && (document.activeElement === document.body || !document.activeElement)) btn.current?.focus();
    wasOpen.current = open;
  }, [open]);
  const close = () => setOpen(false);
  function onMenuKey(e: React.KeyboardEvent) {
    const list = [...(pop.current?.querySelectorAll<HTMLElement>("[role=menuitem]") ?? [])];
    const at = list.indexOf(document.activeElement as HTMLElement);
    const to = (n: number) => { e.preventDefault(); list[(n + list.length) % list.length]?.focus(); };
    if (e.key === "ArrowDown") to(at + 1);
    else if (e.key === "ArrowUp") to(at - 1);
    else if (e.key === "Home") to(0);
    else if (e.key === "End") to(list.length - 1);
    else if (e.key === "Escape") { e.preventDefault(); e.nativeEvent.stopImmediatePropagation(); close(); btn.current?.focus(); }
    else if (e.key === "Tab") close();
  }
  return (
    <div className="cf-more">
      <button ref={btn} type="button" className="cf-icon-btn is-plain" aria-label="More" aria-expanded={open} aria-haspopup="menu" onClick={() => setOpen((v) => !v)}>
        <Icon24 name="more" size={18} />
      </button>
      {open && (
        <div ref={pop} className="cf-pop cf-menu" role="menu" aria-label="More" onKeyDown={onMenuKey}>
          {items.map((it) => (
            <div key={it.label} role="none">
              {it.separator && <hr role="separator" />}
              {it.href ? (
                <a role="menuitem" tabIndex={-1} href={it.href} onClick={close}>{it.label}{it.hint && <span className="cf-kbd is-dark" aria-hidden="true">{it.hint}</span>}</a>
              ) : (
                <button role="menuitem" tabIndex={-1} type="button" onClick={() => { close(); it.onClick?.(); }}>{it.label}{it.hint && <span className="cf-kbd is-dark" aria-hidden="true">{it.hint}</span>}</button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/** Ring percentages for the four stages, from the same case, gaps and deck as the screens. */
function useStageProgress() {
  const { c, gaps, phase, checkedAt, engineGaps } = useCase();
  const session = useSession();
  return useMemo(() => {
    if (phase !== "case") return { start: 0, questions: 0, review: 0, application: 0 };
    const deck = buildDeck(c, gaps, { seen: new Set(session.seen), includeDone: true });
    const { done, total } = deckProgress(deck);
    const groups = groupGaps(gaps, new Map(engineGaps.map((g) => [g.id, g.section])));
    const sectionsClear = [["A"], ["B", "facts"], ["C"], ["D", "process"]].filter((keys) => !keys.some((k) => (groups.get(k) ?? []).length)).length;
    return {
      start: c.description.trim() ? 100 : 0,
      questions: total ? (100 * done) / total : 0,
      review: checkedAt ? (100 * sectionsClear) / 4 : 0,
      application: 0,
    };
  }, [c, gaps, phase, checkedAt, engineGaps, session.seen]);
}

export function Shell({ active, children, application }: { active: Screen; children: ReactNode; application?: ApplicationSummary | null }) {
  const { c, phase, engineId, resetToWho } = useCase();
  const account = useAccount();
  const assistant = useAssistant();
  const [confirm, setConfirm] = useState(false);
  const [palette, setPalette] = useState(false);
  const [listCollapsed, setListCollapsed] = useState(false);
  const [sheet, setSheet] = useState(false);
  const listRef = useRef<ApplicationListHandle>(null);
  const inCase = phase === "case";
  const progress = useStageProgress();

  useEffect(() => { bootAccount(); }, []);
  useEffect(() => { setAssistantCase(engineId); }, [engineId]);

  // Cmd/Ctrl+B list, +J assistant, +K search applications, +Shift+K search the code.
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey) || e.altKey) return;
      const k = e.key.toLowerCase();
      if (k === "b") { e.preventDefault(); setListCollapsed((v) => !v); }
      else if (k === "j") { e.preventDefault(); toggleAssistant(); }
      else if (k === "k" && e.shiftKey) { if (inCase) { e.preventDefault(); setPalette((v) => !v); } }
      else if (k === "k") {
        e.preventDefault();
        if (window.matchMedia("(max-width: 760px)").matches) setSheet(true);
        else setListCollapsed(false);
        window.setTimeout(() => listRef.current?.focusSearch(), 0);
      }
    };
    const open = () => setPalette(true);
    document.addEventListener("keydown", on);
    window.addEventListener(OPEN_PALETTE, open);
    return () => { document.removeEventListener("keydown", on); window.removeEventListener(OPEN_PALETTE, open); };
  }, [inCase]);

  // Without accounts the list holds this visit's application only.
  const signedIn = account.phase === "signed-in";
  const deckDone = Math.round(progress.questions);
  const localRow: ApplicationSummary | null = inCase
    ? { id: engineId ?? "this-visit", title: c.title || "New application", status: "draft", authority: c.authority || null, updated_at: new Date().toISOString(), submitted_at: null, completeness: { answered: deckDone, total: 100 }, unread_messages: 0, reviewer: null }
    : null;
  const items = signedIn ? account.applications ?? [] : localRow ? [localRow] : [];
  const selectedId = engineId ?? (localRow ? "this-visit" : null);

  const stages: StageRingItem[] = [
    { id: "start", label: "Describe", icon: "describe", href: "#/", pct: progress.start, current: active === "start" },
    { id: "questions", label: "Questions", icon: "questions", href: "#/questions", pct: progress.questions, current: active === "questions", disabled: inCase ? undefined : "Describe your project first." },
    { id: "review", label: "Review", icon: "review", href: "#/review", pct: progress.review, current: active === "review", disabled: inCase ? undefined : "Describe your project first." },
    { id: "application", label: "Application", icon: "file", href: "#/application", pct: application && ["submitted", "in_review", "accepted"].includes(application.status) ? 100 : progress.application, current: active === "application", disabled: inCase ? undefined : "Describe your project first." },
  ];

  const destinations: RailDestination[] = [
    { id: "applications", label: listCollapsed ? "Show applications" : "Hide applications", icon: "inbox", onClick: () => setListCollapsed((v) => !v), current: ["start", "questions", "review", "application"].includes(active), badge: items.some((a) => a.status === "returned" && a.unread_messages > 0), shortcut: `${MOD_KEY} B` },
    { id: "code", label: "Code library", icon: "book", href: "#/code", current: active === "code" },
    { id: "assistant", label: assistant.open ? "Close the assistant" : "Assistant", icon: "spark", onClick: toggleAssistant, current: assistant.open, shortcut: `${MOD_KEY} J` },
  ];

  const list = (
    <ApplicationList
      ref={listRef}
      items={items}
      selectedId={selectedId}
      onSelect={(id) => { if (id === selectedId) location.hash = "#/questions"; }}
      onNew={inCase ? () => setConfirm(true) : undefined}
      onCollapse={() => setListCollapsed(true)}
      loading={account.loadingList}
      error={account.listError}
      note={!signedIn && inCase ? "Saved for this visit only." : undefined}
      empty={<p className="cf-applist-note">Describe what you’re building to start your first application.</p>}
    />
  );

  const title = inCase ? c.title || "New application" : "New application";
  const header = (
    <AppHeader
      title={title}
      meta={inCase && c.authority ? authorityName(c.authority) : undefined}
      stages={stages}
      onMenu={() => setSheet(true)}
      right={
        <>
          <SaveStatus />
          <button type="button" className="cf-btn is-ghost is-sm cf-ask" aria-pressed={assistant.open} onClick={toggleAssistant} title={`Assistant (${MOD_KEY} J)`}>
            <Icon24 name="spark" size={16} /><span className="cf-ask-label">Ask</span>
          </button>
          {inCase && (
            <MoreMenu
              items={[
                { label: "Look up code", hint: `${MOD_KEY} ⇧ K`, onClick: openPalette },
                { label: "Code library", href: "#/code" },
                { label: "Your Section C references", href: "#/references" },
                { label: "Officer view", href: "#/officer" },
                { label: "Accuracy report", href: "#/accuracy" },
                { label: "Download draft", href: "#/application?download=draft", separator: true },
                { label: "Start over", onClick: () => setConfirm(true) },
              ]}
            />
          )}
        </>
      }
    />
  );

  return (
    <>
      <AppLayout
        rail={<Rail destinations={destinations} account={account.user ? { initials: initials(account.user.name, account.user.email), label: `Signed in as ${account.user.name ?? account.user.email}` } : undefined} />}
        list={list}
        header={header}
        assistant={assistant.open ? <AssistantPanel /> : null}
        listCollapsed={listCollapsed}
        sheetOpen={sheet}
        onSheetClose={() => setSheet(false)}
      >
        {children}
      </AppLayout>
      {inCase && <CodePalette open={palette} onClose={() => setPalette(false)} />}
      <ConfirmDialog
        open={confirm}
        title="Start a new application?"
        body={<p>{signedIn ? "This application stays in your list." : "Without an account this clears your answers in this browser. Files already uploaded are not deleted now; they expire with the case. Download a draft first if you need a copy."}</p>}
        cancel="Keep working"
        confirm="Start new"
        onClose={() => setConfirm(false)}
        onConfirm={() => {
          setConfirm(false);
          resetSession();
          resetRelevance();
          resetToWho();
        }}
      />
    </>
  );
}
