import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { ApplicationSummary } from "../api/accounts";
import { groupGaps } from "../humanReview";
import { useCase } from "../store";
import { bootAccount, initials, refreshApplications, useAccount } from "./account";
import { authorityName } from "./applications";
import { AssistantPanel } from "./assistant/AssistantPanel";
import { setAssistantCase, setAssistantContext, toggleAssistant, useAssistant } from "./assistant/assistant";
import { roleOf, useCurrentApplication } from "./begin";
import { CodePalette, OPEN_PALETTE, openPalette } from "./CodePalette";
import { buildDeck, deckProgress } from "./deck";
import { Icon24 } from "./icons";
import { STAGES, type Screen } from "./routes";
import { getSession, resetSession, useSession } from "./session";
import { AppHeader, type StageRingItem } from "./shell/AppHeader";
import { AppLayout } from "./shell/AppLayout";
import { ApplicationList, type ApplicationListHandle } from "./shell/ApplicationList";
import { Rail, RailAvatar, type RailDestination } from "./shell/Rail";
import { ReturnedBanner } from "./shell/ReturnedBanner";
import { AccountMenu, NotificationsPanel } from "./routes.extra";
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

/** The check's state, quietly beside the save status (Review holds the detail and the big retry). */
function CheckStatus() {
  const { phase, checkStatus } = useCase();
  if (phase !== "case") return null;
  if (checkStatus === "running") return <span className="cf-save-check" role="status"><span className="cf-dot is-pending cf-pulse" aria-hidden="true" />Checking…</span>;
  if (checkStatus === "unavailable") return <a className="cf-save-check" href="#/review" role="status" title="The last check couldn’t finish. Retry from the ⋯ menu or open Review.">Check unavailable</a>;
  return null;
}

export function SaveStatus() {
  const { phase, saveStatus, savedNote, saveDetail, saveDraft } = useCase();
  const { app, locked } = useCurrentApplication();
  if (phase !== "case") return null;
  // Sent to the authority: nothing is saved from here until the officer returns it.
  if (locked) return <div className="cf-save" role="status"><Dot tone={app?.status === "accepted" ? "done" : "warning"} /><span className="cf-save-label">{app?.status === "accepted" ? "Accepted" : "Sent · read-only"}</span></div>;
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

const PHONE = "(max-width: 760px)";
/** The signed-in application open in this tab, so a reload reopens it. Tab-scoped, id only. */
const OPEN_KEY = "batatis-open-application";
const remembered = () => { try { return sessionStorage.getItem(OPEN_KEY); } catch { return null; } };
const remember = (id: string | null) => { try { if (id) sessionStorage.setItem(OPEN_KEY, id); else sessionStorage.removeItem(OPEN_KEY); } catch { /* storage unavailable */ } };
const isPhone = () => window.matchMedia(PHONE).matches;

export function Shell({ active, children }: { active: Screen; children: ReactNode }) {
  const { c, phase, engineId, resetToWho, openCase, saveStatus, saveDraft, checkStatus, requestCheck } = useCase();
  const account = useAccount();
  const assistant = useAssistant();
  const [confirm, setConfirm] = useState(false);
  const [palette, setPalette] = useState(false);
  const [listNote, setListNote] = useState("");
  const [opening, setOpening] = useState<string | null>(null);
  const [listCollapsed, setListCollapsed] = useState(false);
  const [sheet, setSheet] = useState(false);
  const listRef = useRef<ApplicationListHandle>(null);
  const inCase = phase === "case";
  const progress = useStageProgress();
  const signedIn = account.phase === "signed-in";
  const onStage = STAGES.some((s) => s.screen === active);
  /** The last stage page, so Applications in the rail returns to it from the code library. */
  const lastStage = useRef("#/");
  if (onStage) lastStage.current = location.hash || "#/";

  useEffect(() => { bootAccount(); }, []);
  useEffect(() => { setAssistantCase(engineId); }, [engineId]);
  // A new owned case appears in the list once the engine has created it.
  useEffect(() => { if (signedIn && engineId) void refreshApplications(); }, [signedIn, engineId]);
  useEffect(() => { if (signedIn && engineId) remember(engineId); }, [signedIn, engineId]);

  // After a reload, reopen the application this tab had open (signed in only).
  const restored = useRef(false);
  useEffect(() => {
    if (restored.current || account.phase === "probing") return;
    restored.current = true;
    const id = remembered();
    if (!id) return;
    if (!signedIn || inCase) { if (!signedIn) remember(null); return; }
    setOpening(id);
    void openCase(id, roleOf(account.user) ?? "homebuilder").then((error) => {
      setOpening(null);
      if (!error) return;
      remember(null);
      resetToWho("That application is no longer available.");
    });
  }, [account.phase]); // eslint-disable-line react-hooks/exhaustive-deps
  // Screens without their own context: the assistant looks at the page.
  useEffect(() => {
    if (active === "questions") return;
    const label = active === "start" ? "your description" : active === "review" ? "your review" : active === "application" ? "your application" : active === "code" ? "the code library" : "your application";
    setAssistantContext({ screen: active === "start" ? "describe" : active, label });
  }, [active]);

  const toggleList = () => {
    if (isPhone()) setSheet(true);
    else setListCollapsed((v) => !v);
  };

  // Cmd/Ctrl+B sidebar, +J assistant, +K search applications, +Shift+K search the code.
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey) || e.altKey) return;
      const k = e.key.toLowerCase();
      if (k === "b") { e.preventDefault(); toggleList(); }
      else if (k === "j") { e.preventDefault(); toggleAssistant(); }
      else if (k === "k" && e.shiftKey) { e.preventDefault(); setPalette((v) => !v); }
      else if (k === "k") {
        e.preventDefault();
        if (isPhone()) setSheet(true);
        else setListCollapsed(false);
        window.setTimeout(() => listRef.current?.focusSearch(), 0);
      }
    };
    const open = () => setPalette(true);
    document.addEventListener("keydown", on);
    window.addEventListener(OPEN_PALETTE, open);
    return () => { document.removeEventListener("keydown", on); window.removeEventListener(OPEN_PALETTE, open); };
  }, []);

  const deckDone = Math.round(progress.questions);
  const localRow: ApplicationSummary | null = inCase
    ? { id: engineId ?? "this-visit", title: c.title || "New application", status: "draft", authority: c.authority || null, updated_at: new Date().toISOString(), submitted_at: null, completeness: { answered: deckDone, total: 100 }, unread_messages: 0, reviewer: null }
    : null;
  const saved = account.applications ?? [];
  // Signed in, a new draft shows at once, before the engine has listed it.
  const items = signedIn ? (localRow && !saved.some((a) => a.id === localRow.id) ? [localRow, ...saved] : saved) : localRow ? [localRow] : [];
  const selectedId = engineId ?? (localRow ? "this-visit" : null);
  const current = (engineId && saved.find((a) => a.id === engineId)) || null;

  const empty = !inCase && !getSession().draft.trim();
  const stages: StageRingItem[] = [
    { id: "start", label: "Describe", icon: "describe", href: "#/", pct: progress.start, current: active === "start" },
    { id: "questions", label: "Questions", icon: "questions", href: "#/questions", pct: progress.questions, current: active === "questions", hint: inCase ? undefined : "Starts with your description" },
    { id: "review", label: "Review", icon: "review", href: "#/review", pct: progress.review, current: active === "review", hint: inCase ? undefined : "Nothing to review yet" },
    { id: "application", label: "Application", icon: "file", href: "#/application", pct: current && ["submitted", "in_review", "accepted"].includes(current.status) ? 100 : progress.application, current: active === "application", hint: inCase ? undefined : "Nothing filled in yet" },
  ];

  const destinations: RailDestination[] = [
    {
      id: "applications",
      label: "Applications",
      icon: "inbox",
      onClick: () => {
        if (isPhone()) setSheet(true);
        else setListCollapsed(false);
        if (!onStage) location.hash = lastStage.current;
      },
      current: onStage,
      badge: items.some((a) => a.status === "returned" && a.unread_messages > 0),
    },
    { id: "code", label: "Code library", icon: "book", href: "#/code", current: active === "code", shortcut: `${MOD_KEY} ⇧ K` },
    { id: "assistant", label: assistant.open ? "Close the assistant" : "Assistant", icon: "spark", onClick: toggleAssistant, current: assistant.open, shortcut: `${MOD_KEY} J` },
  ];

  function startNew() {
    setListNote("");
    remember(null);
    resetSession();
    resetRelevance();
    resetToWho(signedIn ? "" : undefined);
  }

  async function open(id: string) {
    if (id === selectedId) { setListNote(""); if (!onStage) location.hash = lastStage.current; return; }
    if (!signedIn || opening) return;
    setOpening(id);
    setListNote("");
    // Keep the open draft before switching; a failed save keeps it open and says so.
    if (inCase && saveStatus === "unsaved" && !(await saveDraft())) {
      setOpening(null);
      setListNote("This application isn’t saved yet, so it stays open. Try again once it’s saved.");
      return;
    }
    const role = roleOf(account.user) ?? (c.applicantType as Parameters<typeof openCase>[1]);
    const error = await openCase(id, role);
    setOpening(null);
    if (error) { setListNote(error); return; }
    resetSession();
    resetRelevance();
    location.hash = "#/questions";
  }

  const list = (
    <ApplicationList
      ref={listRef}
      items={items}
      selectedId={opening ?? selectedId}
      onSelect={(id) => void open(id)}
      onNew={() => {
        if (!inCase) {
          setListNote("");
          location.hash = "#/";
          window.setTimeout(() => document.getElementById("cf-describe")?.focus(), 0);
        } else if (signedIn) startNew();
        else setConfirm(true);
      }}
      loading={account.loadingList}
      error={account.listError}
      note={opening ? "Opening…" : listNote || (!signedIn && inCase ? "Saved for this visit only." : undefined)}
      empty={<p className="cf-applist-note">{empty ? "Describe what you’re building to start your first application." : "Your new application appears here once it starts."}</p>}
    />
  );

  const title = inCase ? c.title || "New application" : "New application";
  const header = (
    <AppHeader
      title={title}
      meta={inCase && c.authority ? authorityName(c.authority) : undefined}
      stages={stages}
      onToggleList={toggleList}
      listOpen={!listCollapsed}
      toggleHint={`${MOD_KEY} B`}
      right={
        <>
          <CheckStatus />
          <SaveStatus />
          <button type="button" className="cf-btn is-ghost is-sm cf-ask" aria-pressed={assistant.open} onClick={toggleAssistant} title={`Assistant (${MOD_KEY} J)`}>
            <Icon24 name="spark" size={16} /><span className="cf-ask-label">Ask</span>
          </button>
          <MoreMenu
            items={[
              { label: "Look up code", hint: `${MOD_KEY} ⇧ K`, onClick: openPalette },
              { label: "Code library", href: "#/code" },
              ...(inCase && checkStatus === "unavailable" ? [{ label: "Try the check again", onClick: () => void requestCheck(true), separator: true }] : []),
              ...(inCase
                ? [
                    { label: "Your Section C references", href: "#/references", separator: checkStatus === "unavailable" },
                    { label: "Officer view", href: "#/officer" },
                    { label: "Accuracy report", href: "#/accuracy" },
                    { label: "Download draft", href: "#/application?download=draft", separator: true },
                    { label: signedIn ? "New application" : "Start over", onClick: () => (signedIn ? startNew() : setConfirm(true)) },
                  ]
                : []),
            ]}
          />
        </>
      }
    />
  );

  const avatar = account.user ? <RailAvatar initials={initials(account.user.name, account.user.email)} label={`Signed in as ${account.user.name ?? account.user.email}`} /> : null;

  return (
    <>
      <AppLayout
        rail={<Rail destinations={destinations} notificationsSlot={<NotificationsPanel />} accountSlot={<AccountMenu fallback={avatar} />} />}
        list={list}
        header={header}
        banner={onStage && current?.status === "returned" ? <ReturnedBanner app={current} /> : null}
        assistant={assistant.open ? <AssistantPanel /> : null}
        listCollapsed={listCollapsed}
        sheetOpen={sheet}
        onSheetClose={() => setSheet(false)}
      >
        {children}
      </AppLayout>
      <CodePalette open={palette} onClose={() => setPalette(false)} />
      <ConfirmDialog
        open={confirm}
        title="Start a new application?"
        body={<p>Without an account this clears your answers in this browser. Files already uploaded are not deleted now; they expire with the case. Download a draft first if you need a copy.</p>}
        cancel="Keep working"
        confirm="Start new"
        onClose={() => setConfirm(false)}
        onConfirm={() => {
          setConfirm(false);
          startNew();
        }}
      />
    </>
  );
}
