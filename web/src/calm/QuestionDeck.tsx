import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { DETAIL_FIELDS, PROCESS_FIELDS, factFor, isTyped, valueText } from "../model";
import { withinProvision } from "../provisions";
import { exitCountWarning } from "../rules";
import { useCandidateAnswer } from "../screens/CodeCheck";
import { Recommendations } from "../screens/Recommendations";
import { useCase } from "../store";
import type { ApplicantType } from "../types";
import { authorityName } from "./applications";
import { openAssistant, setAssistantContext } from "./assistant/assistant";
import { useBegin, useCurrentApplication } from "./begin";
import { CodeDrawer, type DrawerState } from "./CodeDrawer";
import { aliasKey, buildDeck, choiceKey, choicesFor, preCaseDeck, SECTIONS, type DeckItem, type SectionId } from "./deck";
import { Icon24 } from "./icons";
import { RelevanceRing } from "./RelevanceRing";
import { updateSession, useSession } from "./session";
import { CIcon, MOD_KEY } from "./ui";

type Shown = DeckItem & { gone?: boolean };

function isTextTarget(t: EventTarget | null): boolean {
  const el = t as HTMLElement | null;
  if (!el) return false;
  return el.tagName === "TEXTAREA" || el.tagName === "INPUT" || el.tagName === "SELECT" || el.isContentEditable;
}

/** Cards answered by typing several lines continue with Cmd/Ctrl+Enter instead of Enter. */
function multiline(item: DeckItem): boolean {
  return item.kind === "question" || item.kind === "process" || item.kind === "describe" || (item.kind === "detail" && Boolean(DETAIL_FIELDS.find((d) => d.id === item.ref)?.multiline));
}

/* —— Typeform pieces —— */

/** Stacked choices with letter keys. Pressed = selected; the check shows on the chosen one. */
function Choices({ choices, current, onPick }: { choices: { value: string; label: string }[]; current?: string; onPick: (v: string) => void }) {
  return (
    <div className="cf-choices-q" role="group" aria-label="Your answer">
      {choices.map((o, n) => (
        <button key={o.value} type="button" className="cf-choice" data-deck-answer aria-pressed={current === o.value} onClick={() => onPick(o.value)}>
          <span className="cf-choice-key" aria-hidden="true">{choiceKey(n)}</span>
          <span className="cf-choice-label">{o.label}</span>
          <span className="cf-choice-check" aria-hidden="true"><Icon24 name="check" size={16} /></span>
        </button>
      ))}
    </div>
  );
}

function OkRow({ label = "OK", disabled, onOk, typed, children }: { label?: string; disabled?: boolean; onOk: () => void; typed: boolean; children?: ReactNode }) {
  return (
    <div className="cf-ok-row" data-deck-foot>
      <button type="button" className="cf-btn is-primary is-lg" disabled={disabled} onClick={onOk}>
        {label} <Icon24 name="check" size={16} stroke={2} />
      </button>
      {!disabled && <span className="cf-ok-hint" aria-hidden="true">press <b>{typed ? `${MOD_KEY} Enter ↵` : "Enter ↵"}</b></span>}
      {children}
    </div>
  );
}

/** Number and arrow in the accent, then the section label. */
function QNum({ n, label }: { n: ReactNode; label?: string }) {
  return (
    <div className="cf-q-num">
      <span className="cf-q-n">{n}</span>
      <Icon24 name="right" size={15} stroke={2} />
      {label && <span className="cf-q-sec">{label}</span>}
    </div>
  );
}

/** Enter-direction for the vertical slide: forward enters from below, back from above. */
function useDirection(index: number): "down" | "up" {
  const prev = useRef(index);
  const dir = useRef<"down" | "up">("down");
  if (prev.current !== index) {
    dir.current = index > prev.current ? "down" : "up";
    prev.current = index;
  }
  return dir.current;
}

/* —— Footer: progress split by form section, popover per section, up/down —— */

export function SectionFooter({ items, index, onJump, onPrev, onNext, canPrev, canNext }: { items: Shown[]; index: number; onJump: (i: number) => void; onPrev: () => void; onNext: () => void; canPrev: boolean; canNext: boolean }) {
  const [open, setOpen] = useState<SectionId | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const hold = (id: SectionId | null) => { window.clearTimeout(timer.current); setOpen(id); };
  const later = () => { window.clearTimeout(timer.current); timer.current = window.setTimeout(() => setOpen(null), 160); };
  useEffect(() => () => window.clearTimeout(timer.current), []);
  const sections = SECTIONS.map((s) => {
    const at = items.map((it, i) => ({ it, i })).filter((x) => x.it.section === s.id);
    const tracked = at.filter((x) => !x.it.optional);
    return { ...s, at, done: tracked.filter((x) => x.it.done).length, total: tracked.length, on: at.some((x) => x.i === index) };
  }).filter((s) => s.at.length > 0);
  const lastHalf = (n: number) => n >= Math.ceil(sections.length / 2);
  return (
    <footer className="cf-qfoot" aria-label="Progress">
      <div className="cf-secs">
        {sections.map((s, sn) => {
          const first = s.at.find((x) => !x.it.done) ?? s.at[0];
          return (
            <div
              key={s.id}
              className={`cf-qsec${s.on ? " is-on" : ""}`}
              style={{ ["--n" as string]: s.at.length }}
              onPointerEnter={(e) => { if (e.pointerType === "mouse") hold(s.id); }}
              onPointerLeave={(e) => { if (e.pointerType === "mouse") later(); }}
              onFocus={() => hold(s.id)}
              onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) later(); }}
              onKeyDown={(e) => { if (e.key === "Escape" && open) { e.stopPropagation(); setOpen(null); } }}
            >
              <button type="button" className="cf-qsec-btn" aria-expanded={open === s.id} aria-controls={`cf-qsec-pop-${s.id}`} onClick={() => onJump(first.i)}>
                <span className="cf-qsec-bar" aria-hidden="true">
                  {s.at.map((x) => <i key={x.it.key} className={x.i === index ? "is-cur" : x.it.done ? "is-done" : ""} />)}
                </span>
                <span className="cf-qsec-lab">
                  <b>{s.id}<span className="cf-qsec-name"> · {s.label}</span></b>
                  <span>{s.done}<span className="cf-qsec-name"> of </span><span className="cf-qsec-slash" aria-hidden="true">/</span>{s.total}</span>
                </span>
                <span className="cf-sr">. Go to the first open question in Section {s.id}.</span>
              </button>
              {open === s.id && (
                <div id={`cf-qsec-pop-${s.id}`} className={`cf-pop cf-qsec-pop${lastHalf(sn) ? " is-end" : ""}`} role="group" aria-label={`Section ${s.id} questions`}>
                  {s.at.map((x, k) => (
                    <button key={x.it.key} type="button" className={`cf-qsec-row${x.i === index ? " is-cur" : ""}`} aria-current={x.i === index ? "step" : undefined} onClick={() => { setOpen(null); onJump(x.i); }}>
                      <span className="cf-qsec-n">{s.id}{k + 1}</span>
                      <span className="cf-qsec-t">{x.it.title}</span>
                      {x.it.done && <span className="cf-qsec-done" aria-label="answered"><Icon24 name="check" size={14} /></span>}
                    </button>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div className="cf-qnav">
        <button type="button" className="cf-icon-btn cf-qnav-btn" aria-label="Previous question (↑)" disabled={!canPrev} onClick={onPrev}><Icon24 name="up" size={16} /></button>
        <button type="button" className="cf-icon-btn cf-qnav-btn" aria-label="Next question (↓)" disabled={!canNext} onClick={onNext}><Icon24 name="down" size={16} /></button>
      </div>
    </footer>
  );
}

/* —— One card's controls —— */

function CardBody({ item, picked, onPick, draft, setDraft, openDrawer }: { item: Shown; picked?: string; onPick: (value: string) => void; draft: string; setDraft: (v: string) => void; openDrawer: (s: DrawerState) => void }) {
  const { c, dispatch } = useCase();
  const session = useSession();
  const [tips, setTips] = useState(false);
  const choices = choicesFor(item);

  if (item.kind === "section-d") {
    return <div className="cf-embed cf-sectiond"><Recommendations /></div>;
  }

  const cand = item.kind === "candidate" || item.kind === "storeys" ? c.candidates.find((a) => a.id === item.ref) : undefined;
  const fact = item.kind === "detail" ? factFor(c, item.ref) : undefined;
  const def = item.kind === "detail" ? DETAIL_FIELDS.find((d) => d.id === item.ref) : undefined;

  let current: string | undefined = picked;
  if (item.kind === "candidate" && cand) current = cand.answer ?? undefined;
  if (item.kind === "authority") current = c.authority || (session.authorityUnsure ? "unsure" : undefined);
  if (item.kind === "detail" && def?.options) current = valueText(fact) || undefined;

  return (
    <>
      {item.provision && (
        <button type="button" className="cf-cite" onClick={() => openDrawer({ mode: "code", candidateId: item.ref })}>
          <RelevanceRing id={item.provision} focusable={false} />
          <b>{item.provision}</b> Show the code
        </button>
      )}
      {item.kind === "storeys" ? (
        <div className="cf-inline-answer">
          <label className="cf-sr" htmlFor="cf-storeys">Number of storeys</label>
          <input id="cf-storeys" className="cf-uline is-number" type="number" inputMode="numeric" min={1} step={1} value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="e.g. 2" />
          <button type="button" className="cf-chip" aria-pressed={cand?.answer === "not-sure"} onClick={() => { setDraft(""); dispatch({ type: "setStoreyCount", value: "" }); }}>
            Not sure
          </button>
        </div>
      ) : item.kind === "question" ? (
        <textarea className="cf-uline is-area" rows={2} aria-label={item.title} value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Type your answer here…" />
      ) : item.kind === "process" ? (
        <>
          <textarea
            className="cf-uline is-area is-tall"
            rows={4}
            aria-label={item.title}
            value={c.process[item.ref as keyof typeof c.process]}
            onChange={(e) => dispatch({ type: "setProcess", field: item.ref as keyof typeof c.process, value: e.target.value })}
            placeholder="In your own words…"
          />
          <button type="button" className="cf-link-btn cf-tips-toggle" aria-expanded={tips} onClick={() => setTips((v) => !v)}>What to include</button>
          {tips && (
            <ul className="cf-tips">
              {PROCESS_FIELDS.find((p) => p.id === item.ref)?.prompts.map((p) => <li key={p}>{p}</li>)}
              <li>Professional analysis must come from your engineer or architect. Batatis does not write it.</li>
            </ul>
          )}
        </>
      ) : item.kind === "detail" && def && !def.options ? (
        <>
          {def.multiline ? (
            <textarea id={`field-${def.id}`} className="cf-uline is-area" rows={2} aria-label={def.label} value={valueText(fact)} onChange={(e) => dispatch({ type: "setDetail", field: def.id, value: e.target.value, section: def.section })} placeholder="Type your answer here…" />
          ) : (
            <input
              id={`field-${def.id}`}
              className={`cf-uline${def.inputType === "date" ? " is-date" : ""}`}
              type={def.inputType ?? "text"}
              aria-label={def.label}
              value={valueText(fact)}
              onChange={(e) => dispatch({ type: "setDetail", field: def.id, value: e.target.value, section: def.section })}
              placeholder={def.inputType === "date" ? undefined : "Type your answer here…"}
            />
          )}
          {fact && !isTyped(fact) && (
            <p className="cf-note">
              <span className={`cf-dot ${fact.status === "confirmed" ? "is-done" : "is-warning"}`} aria-hidden="true" />
              {picked === "confirm" ? "Confirmed by you. You can still edit it." : `From ${fact.source.ref}. Edit it if it’s not right.`}
            </p>
          )}
          {picked === "dismiss" && !fact && <p className="cf-note">Removed. Type the right one, or skip for now.</p>}
          {def.id === "alternative" && !valueText(fact).trim() && c.description.trim() && (
            <button type="button" className="cf-chip cf-from-desc" onClick={() => dispatch({ type: "setDetail", field: "alternative", value: c.description.trim(), section: "B" })}>
              Start from my description
            </button>
          )}
        </>
      ) : (
        choices.length > 0 && <Choices choices={choices} current={current} onPick={onPick} />
      )}
      {item.kind === "candidate" && !item.provision && (
        <button type="button" className="cf-link-btn cf-find" onClick={() => openDrawer({ mode: "search" })}>
          <CIcon name="search" size={13} />Find the rule in the code yourself
        </button>
      )}
      {cand?.answer === "not-sure" && item.kind === "candidate" && (
        <div className="cf-followup" role="status">
          <span className="cf-eyebrow is-plain">Open question for the officer</span>
          <p>{cand.clarifyingQuestion}</p>
          <p className="cf-faint">Logged as an open question. It does not block you, and it is not treated as a confirmed departure.</p>
        </div>
      )}
      {item.kind === "authority" && current === "unsure" && <p className="cf-note"><span className="cf-dot is-warning" aria-hidden="true" />Left open. The review keeps it on your list until you pick one.</p>}
      {cand && exitCountWarning(cand.provision, cand.topic) && <p className="cf-note"><span className="cf-dot is-warning" aria-hidden="true" />{exitCountWarning(cand.provision, cand.topic)}</p>}
      {item.kind === "fact" && item.gone && <p className="cf-note"><span className="cf-dot is-done" aria-hidden="true" />{picked === "dismiss" ? "Removed." : "Confirmed."}</p>}
    </>
  );
}

/** Not sure what a question means: the assistant opens on it (it explains; it never answers for you). */
function AskLink({ item, n }: { item: DeckItem; n: number }) {
  return (
    <button
      type="button"
      className="cf-assist-link"
      onClick={() => openAssistant({
        screen: "question",
        focus: item.provision ? { kind: "provision", id: item.provision } : { kind: "card", id: item.key },
        label: `question ${n}${item.provision ? ` and ${item.provision}` : ""}`,
        suggestions: item.provision ? ["Explain the code", "What does this question mean?"] : ["What does this question mean?", "What should I have ready?"],
      })}
    >
      <Icon24 name="spark" size={15} />Not sure what this means? Ask the assistant
    </button>
  );
}

/* —— Before an application exists: description, then the role when onboarding has none —— */

function PreCaseDeck() {
  const session = useSession();
  const { userRole, begin } = useBegin();
  const items = preCaseDeck(session.draft, !userRole, session.role);
  const [index, setIndex] = useState(() => Math.max(0, items.findIndex((i) => !i.done)));
  const at = Math.min(index, items.length - 1);
  const item = items[at];
  const dir = useDirection(at);
  const wrap = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setAssistantContext({ screen: "question", focus: { kind: "card", id: item.key }, label: "your new application", suggestions: ["What is an alternative solution?", "What should I describe?"] });
    const el = wrap.current;
    (el?.querySelector<HTMLElement>("textarea") ?? el?.querySelector<HTMLElement>("h2"))?.focus({ preventScroll: true });
  }, [item.key]);

  function ok() {
    if (item.kind === "describe" && !session.draft.trim()) return;
    if (item.kind === "role" && !session.role) return;
    if (begin()) return;
    const open = items.findIndex((i) => !i.done);
    if (open >= 0) setIndex(open);
  }
  function pick(v: string) {
    updateSession({ role: v as ApplicantType });
  }

  const keys = useRef<(e: KeyboardEvent) => void>(() => {});
  keys.current = (e) => {
    if (e.defaultPrevented || document.querySelector("dialog[open]")) return;
    const t = e.target as HTMLElement | null;
    if (t?.closest?.(".cf-pop, dialog, [role='menu'], .cf-palette, .cf-assist, .cf-qfoot")) return;
    const inText = isTextTarget(t);
    if (e.key === "Enter") {
      if (t?.tagName === "TEXTAREA" && !(e.metaKey || e.ctrlKey)) return;
      if (t?.hasAttribute("data-deck-answer") && t.getAttribute("aria-pressed") !== "true") return;
      if (!inText && t && t !== document.body && !t.hasAttribute("data-deck-answer") && t.tagName !== "H2") return;
      e.preventDefault();
      ok();
    } else if (!inText && !e.metaKey && !e.ctrlKey && !e.altKey && (!t || t === document.body || t.closest(".cf-deck-page"))) {
      if (e.key === "ArrowUp" && at > 0) { e.preventDefault(); setIndex(at - 1); }
      else if (e.key === "ArrowDown" && at < items.length - 1) { e.preventDefault(); setIndex(at + 1); }
      else if (item.kind === "role" && /^[a-z]$/i.test(e.key)) {
        const ch = choicesFor(item)[e.key.toUpperCase().charCodeAt(0) - 65];
        if (ch) { e.preventDefault(); pick(ch.value); }
      }
    }
  };
  useEffect(() => {
    const on = (e: KeyboardEvent) => keys.current(e);
    document.addEventListener("keydown", on);
    return () => document.removeEventListener("keydown", on);
  }, []);

  const ready = item.kind === "describe" ? Boolean(session.draft.trim()) : Boolean(session.role);
  return (
    <div className="cf-deck-page">
      <div className="cf-q-stage">
        <div ref={wrap} key={item.key} className={`cf-q-wrap is-from-${dir}`}>
          <QNum n={at + 1} label={item.eyebrow} />
          <h2 id="cf-q" className="cf-q-text" tabIndex={-1}>{item.title}</h2>
          <p className="cf-q-help">{item.context}</p>
          {item.kind === "describe" ? (
            <textarea className="cf-uline is-area" rows={2} aria-labelledby="cf-q" value={session.draft} onChange={(e) => updateSession({ draft: e.target.value })} placeholder="Type your answer here…" />
          ) : (
            <Choices choices={choicesFor(item)} current={session.role ?? undefined} onPick={pick} />
          )}
          {session.draftFiles.length > 0 && item.kind === "describe" && <p className="cf-faint cf-small">{session.draftFiles.length} {session.draftFiles.length === 1 ? "file" : "files"} attached on Describe.</p>}
          {!ready && <p className="cf-hint" role="note">{item.kind === "describe" ? "Describe it in a sentence to continue." : "Pick one to continue."}</p>}
          <OkRow disabled={!ready} onOk={ok} typed={item.kind === "describe"} />
          <AskLink item={item} n={at + 1} />
        </div>
      </div>
      <SectionFooter items={items} index={at} onJump={setIndex} onPrev={() => setIndex(Math.max(0, at - 1))} onNext={() => setIndex(Math.min(items.length - 1, at + 1))} canPrev={at > 0} canNext={at < items.length - 1} />
    </div>
  );
}

/* —— The application's deck —— */

function CaseDeck({ focus, codeFirst }: { focus: string | null; codeFirst: boolean }) {
  const { c, gaps, dispatch, requestCheck, checkStatus, checkNote, checkDetail, sectionCLookup } = useCase();
  const session = useSession();
  const { app, locked } = useCurrentApplication();
  const { onAnswer, decisionNoteFor } = useCandidateAnswer();
  const seen = useMemo(() => new Set(session.seen), [session.seen]);
  const all = buildDeck(c, gaps, { seen, includeDone: true });
  const byKey = new Map(all.map((i) => [i.key, i] as const));
  const snapshots = useRef(new Map<string, DeckItem>());
  for (const i of all) snapshots.current.set(i.key, i);
  const itemFor = (k: string | undefined): Shown | undefined => {
    if (!k) return undefined;
    const live = byKey.get(k);
    if (live) return live;
    const snap = snapshots.current.get(k);
    return snap ? { ...snap, done: true, gone: true } : undefined;
  };

  // New open cards join the end of this visit's queue; vanished, unseen keys leave it.
  const openKeys = all.filter((i) => !i.done).map((i) => i.key);
  const fresh = openKeys.filter((k) => !session.queue.includes(k));
  const queue = fresh.length ? [...session.queue, ...fresh] : session.queue;
  const index = Math.min(session.index, queue.length);
  const currentKey = queue[index];
  const item = itemFor(currentKey);
  const queueSig = `${fresh.join("|")}#${session.queue.filter((k) => !byKey.has(k) && k !== currentKey).join("|")}`;
  useEffect(() => {
    updateSession((s) => {
      const cur = s.queue[s.index];
      const kept = s.queue.filter((k) => byKey.has(k) || k === cur);
      const next = [...kept, ...fresh.filter((k) => !kept.includes(k))];
      return { queue: next, index: cur ? Math.max(next.indexOf(cur), 0) : Math.min(s.index, next.length) };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queueSig]);

  const [picked, setPicked] = useState<Record<string, string>>({});
  const [why, setWhy] = useState(false);
  const [drawer, setDrawer] = useState<DrawerState | null>(null);
  const [jumpTo, setJumpTo] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const wrapRef = useRef<HTMLDivElement>(null);
  const formPos = currentKey ? all.findIndex((i) => i.key === currentKey) : all.length;
  const dir = useDirection(formPos < 0 ? index : formPos);

  // Text drafts start from the saved answer each time a card opens.
  useEffect(() => {
    setWhy(false);
    if (!item) return setDraft("");
    if (item.kind === "question") setDraft(c.questions.find((q) => q.id === item.ref)?.answer ?? "");
    else if (item.kind === "storeys") setDraft(c.questions.find((q) => q.id === "q-desc-storeys")?.answer ?? "");
    else setDraft("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentKey]);

  // The assistant follows the open question.
  useEffect(() => {
    if (!item) {
      setAssistantContext({ screen: "question", label: "your remaining questions", suggestions: ["What happens at review?", "What is still missing?"] });
      return;
    }
    setAssistantContext({
      screen: "question",
      focus: item.provision ? { kind: "provision", id: item.provision } : { kind: "card", id: item.key },
      label: `question ${(all.findIndex((i) => i.key === item.key) + 1) || index + 1}${item.provision ? ` and ${item.provision}` : ""}`,
      suggestions: item.provision ? ["Explain the code", "What does this question mean?"] : ["What does this question mean?", "What should I have ready?"],
    });
  }, [item?.key, index]); // eslint-disable-line react-hooks/exhaustive-deps

  // Land on a card from a link (?focus=) or the code-check entry, then drop the parameter.
  const mounted = useRef(false);
  useEffect(() => {
    const first = !mounted.current;
    mounted.current = true;
    if (!focus && !codeFirst) {
      // Returning to the deck resumes at the next open card, not one answered elsewhere.
      if (first && item?.done && !item.gone) moveFrom(index, false);
      return;
    }
    const key = focus ? aliasKey(c, focus) : all.find((i) => (i.kind === "candidate" || i.kind === "storeys") && !i.done)?.key;
    if (key && byKey.has(key)) {
      updateSession((s) => {
        const base = s.queue.length >= queue.length ? s.queue : queue;
        const q = base.includes(key) ? base : [...base.slice(0, s.index), key, ...base.slice(s.index)];
        return { queue: q, index: q.indexOf(key) };
      });
    }
    location.replace("#/questions");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus, codeFirst]);

  // A rule added from the drawer opens its first sentence card.
  useEffect(() => {
    // Wait for the lookup: it may split an article into its sentences first.
    if (!jumpTo || sectionCLookup.source === "loading") return;
    const wanted = jumpTo.replace(/^search-/, "");
    const matches = c.candidates.filter((a) => a.answer === null && (a.id === jumpTo || withinProvision(a.provision, wanted)));
    // Prefer a sentence that already has its Section C row; the raw card only if the lookup failed.
    const target = matches.find((a) => c.sectionC.some((r) => r.candidateId === a.id)) ?? (sectionCLookup.source === "error" ? matches[0] : undefined);
    if (!target || !byKey.has(`cand-${target.id}`)) return;
    const key = `cand-${target.id}`;
    setJumpTo(null);
    updateSession((s) => {
      const q = s.queue.includes(key) ? s.queue : [...s.queue.slice(0, s.index), key, ...s.queue.slice(s.index)];
      return { queue: q, index: q.indexOf(key) };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jumpTo, c.candidates, sectionCLookup.source]);

  // A code card the lookup replaced (article split into sentences) has nothing left to answer.
  useEffect(() => {
    if (item?.gone && (item.kind === "candidate" || item.kind === "storeys")) moveFrom(index, false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [item?.key, item?.gone]);

  // A card that takes typing gets the caret straight away; otherwise the heading (no ring) holds focus.
  useEffect(() => {
    const w = wrapRef.current;
    const field = w?.querySelector<HTMLElement>(".cf-q-body input.cf-uline, .cf-q-body textarea");
    (field ?? w?.querySelector<HTMLElement>("h2"))?.focus({ preventScroll: true });
  }, [currentKey]);

  /** Next open card after `from`. At the end, come back once to cards skipped in this pass. */
  function moveFrom(from: number, markSeen: boolean, skipping = false) {
    const key = queue[from];
    const open = (k: string, extraSeen?: string) => {
      const it = itemFor(k);
      return Boolean(it && !it.done && !(it.optional && (session.seen.includes(k) || k === extraSeen)));
    };
    const seenNow = markSeen ? key : undefined;
    let j = from + 1;
    while (j < queue.length && !open(queue[j], seenNow)) j++;
    let wrapped = session.wrapped;
    if (j >= queue.length && !wrapped) {
      const back = queue.findIndex((k, n) => n !== from && open(k, seenNow) && !itemFor(k)?.optional);
      if (back >= 0) { j = back; wrapped = true; }
    }
    updateSession((s) => ({
      index: j,
      wrapped,
      seen: markSeen && key && !s.seen.includes(key) ? [...s.seen, key] : s.seen,
      skipped: skipping && key && !s.skipped.includes(key) ? [...s.skipped, key] : s.skipped,
    }));
  }

  /** Up/down and the footer move through the whole form in order, answered cards included. */
  const pos = currentKey ? all.findIndex((i) => i.key === currentKey) : all.length;
  function goToKey(key: string | null) {
    if (!key) return updateSession({ index: queue.length });
    updateSession((s) => {
      const base = s.queue.length >= queue.length ? s.queue : queue;
      const q = base.includes(key) ? base : [...base.slice(0, s.index), key, ...base.slice(s.index)];
      return { queue: q, index: q.indexOf(key) };
    });
  }
  const step = (d: -1 | 1) => {
    const at = pos < 0 ? all.length : pos;
    const to = at + d;
    if (to < 0) return;
    goToKey(to >= all.length ? null : all[to].key);
  };

  function canContinue(it: Shown): boolean {
    if (locked) return false;
    if (it.kind === "section-d") return true;
    if (it.kind === "question") return Boolean(draft.trim()) || it.done;
    if (it.kind === "storeys") return (Number.isInteger(Number(draft)) && Number(draft) > 0) || it.done;
    if (it.kind === "authority") return it.done || Boolean(c.authority) || session.authorityUnsure;
    return it.done;
  }

  function next() {
    if (!item) {
      void requestCheck();
      location.hash = "#/review";
      return;
    }
    if (!canContinue(item)) return;
    if (item.kind === "question" && draft.trim()) dispatch({ type: "answerQuestion", id: item.ref, answer: draft.trim() });
    if (item.kind === "storeys" && Number(draft) > 0) dispatch({ type: "setStoreyCount", value: draft });
    moveFrom(index, true);
  }

  function skip() {
    if (!item) return;
    // Optional cards are offered once; required ones come back at the end of this pass.
    moveFrom(index, item.optional, !item.optional);
  }

  function pick(value: string) {
    if (!item || locked) return;
    setPicked((p) => ({ ...p, [item.key]: value }));
    if (item.kind === "fact") dispatch({ type: value === "confirm" ? "confirmFact" : "dismissFact", id: item.ref });
    else if (item.kind === "authority") {
      dispatch({ type: "setAuthority", authority: value === "unsure" ? "" : (value as typeof c.authority) });
      updateSession({ authorityUnsure: value === "unsure" });
    } else if (item.kind === "candidate") {
      const cand = c.candidates.find((a) => a.id === item.ref);
      if (cand) onAnswer(cand, value as "yes" | "no" | "not-sure");
    } else if (item.kind === "detail") {
      const def = DETAIL_FIELDS.find((d) => d.id === item.ref);
      if (def) dispatch({ type: "setDetail", field: def.id, value, section: def.section });
    }
  }

  const keyHandler = useRef<(e: KeyboardEvent) => void>(() => {});
  keyHandler.current = (e: KeyboardEvent) => {
    if (drawer || e.defaultPrevented || document.querySelector("dialog[open]")) return;
    const t = e.target as HTMLElement | null;
    // Keys typed in the menu, a popover, the assistant or any dialog belong to them.
    if (t?.closest?.(".cf-pop, dialog, [role='menu'], .cf-palette, .cf-assist")) return;
    const inText = isTextTarget(t);
    const embedded = item?.kind === "section-d" && t && t !== document.body && !t.closest("[data-deck-foot]") && t.tagName !== "H2";
    if (embedded) return;
    if (e.key === "Enter") {
      if (t?.closest?.(".cf-qfoot")) return;
      if (t?.tagName === "TEXTAREA" && !(e.metaKey || e.ctrlKey)) return;
      if (t?.tagName === "SELECT") return;
      if (!inText && t && t !== document.body && !t.hasAttribute("data-deck-answer") && t !== wrapRef.current?.querySelector("h2")) return;
      // Enter on an unpressed choice selects it (native click); only a pressed one continues.
      if (t?.hasAttribute("data-deck-answer") && t.getAttribute("aria-pressed") !== "true") return;
      e.preventDefault();
      next();
      return;
    }
    if (inText || e.metaKey || e.ctrlKey || e.altKey) return;
    // Letters and arrows belong to the question only when nothing else (list, header) has focus.
    if (t && t !== document.body && !t.closest(".cf-deck-page")) return;
    if (e.key === "ArrowUp") { e.preventDefault(); step(-1); return; }
    if (e.key === "ArrowDown" && item) { e.preventDefault(); step(1); return; }
    if (item && /^[a-z1-9]$/i.test(e.key)) {
      const n = /\d/.test(e.key) ? Number(e.key) - 1 : e.key.toUpperCase().charCodeAt(0) - 65;
      const choice = choicesFor(item)[n];
      if (choice) {
        e.preventDefault();
        pick(choice.value);
      }
    }
  };
  useEffect(() => {
    const on = (e: KeyboardEvent) => keyHandler.current(e);
    document.addEventListener("keydown", on);
    return () => document.removeEventListener("keydown", on);
  }, []);

  const n = (pos < 0 ? index : pos) + 1;
  const openLeft = queue.filter((k) => !itemFor(k)?.done && !itemFor(k)?.optional).length;
  const typed = Boolean(item && multiline(item));

  return (
    <div className="cf-deck-page">
      {(locked || checkStatus === "running" || checkStatus === "unavailable") && (
        <div className="cf-deck-status" role="status">
          {locked ? (
            <><span className="cf-dot is-warning" aria-hidden="true" />{app?.status === "accepted" ? "Accepted as administratively complete" : `Sent to ${authorityName(app?.authority) || "the authority"}`}. Read-only until the officer returns it.</>
          ) : checkStatus === "running" ? (
            <><span className="cf-dot is-pending cf-pulse" aria-hidden="true" />{checkNote}</>
          ) : (
            <>
              <span className="cf-dot is-warning" aria-hidden="true" />{checkNote}
              <button type="button" className="cf-btn is-xs" onClick={() => void requestCheck(true)}>Try the check again</button>
              {checkDetail && <details className="cf-tech"><summary>Technical detail</summary><p>{checkDetail}</p></details>}
            </>
          )}
        </div>
      )}
      <div className="cf-q-stage">
        {item ? (
          <div ref={wrapRef} key={item.key} className={`cf-q-wrap is-from-${dir}${item.kind === "section-d" ? " is-wide" : ""}`} aria-labelledby="cf-q" role="group">
            <QNum n={n} label={item.eyebrow} />
            <h2 id="cf-q" className="cf-q-text" tabIndex={-1}>{item.title}</h2>
            {(item.context || item.quote) && (
              <p className="cf-q-help">
                {item.context}
                {item.quote && <> <q>{item.quote}</q></>}
              </p>
            )}
            <fieldset className="cf-q-body" disabled={locked}>
              <legend className="cf-sr">Your answer</legend>
              <CardBody item={item} picked={picked[item.key]} onPick={pick} draft={draft} setDraft={setDraft} openDrawer={setDrawer} />
            </fieldset>
            {item.kind === "candidate" && decisionNoteFor(item.ref) && <p className="cf-note">{decisionNoteFor(item.ref)}</p>}
            {why && <p className="cf-why">{item.why}</p>}
            {!canContinue(item) && !locked && <p className="cf-hint" role="note">Answer to continue, or skip for now.</p>}
            <OkRow label={item.kind === "section-d" ? "Finish Section D" : "OK"} disabled={!canContinue(item)} onOk={next} typed={typed}>
              <span className="cf-ok-more">
                <button type="button" className="cf-link-btn" aria-expanded={why} onClick={() => setWhy((v) => !v)}>Why we ask</button>
                <button type="button" className="cf-link-btn" onClick={skip}>{item.optional ? "Skip" : "Skip for now"}</button>
              </span>
            </OkRow>
            <AskLink item={item} n={n} />
          </div>
        ) : (
          <div ref={wrapRef} key="finish" className={`cf-q-wrap is-from-${dir}`} aria-labelledby="cf-q" role="group">
            <QNum n={<Icon24 name="check" size={15} stroke={2} />} label={openLeft ? "For now" : "All caught up"} />
            <h2 id="cf-q" className="cf-q-text" tabIndex={-1}>That’s everything for now.</h2>
            <p className="cf-q-help">
              {openLeft
                ? `You skipped ${openLeft} ${openLeft === 1 ? "question" : "questions"}. They stay on your list and on the review.`
                : "Batatis checks what you have and shows anything still missing."}
            </p>
            <OkRow label="Review my application" onOk={next} typed={false}>
              {openLeft > 0 && (
                <span className="cf-ok-more">
                  <button
                    type="button"
                    className="cf-link-btn"
                    onClick={() => {
                      const first = queue.findIndex((k) => !itemFor(k)?.done && !itemFor(k)?.optional);
                      updateSession({ index: Math.max(first, 0), skipped: [], wrapped: true });
                    }}
                  >
                    Go back to skipped
                  </button>
                </span>
              )}
            </OkRow>
          </div>
        )}
      </div>
      <SectionFooter items={all} index={item ? pos : -1} onJump={(i) => goToKey(all[i]?.key ?? null)} onPrev={() => step(-1)} onNext={() => step(1)} canPrev={(pos < 0 ? all.length : pos) > 0} canNext={Boolean(item)} />
      <CodeDrawer state={drawer} onClose={() => setDrawer(null)} onAdded={(id) => { setDrawer(null); setJumpTo(id); }} />
    </div>
  );
}

export function Deck({ focus, codeFirst }: { focus: string | null; codeFirst: boolean }) {
  const { phase } = useCase();
  return phase === "case" ? <CaseDeck focus={focus} codeFirst={codeFirst} /> : <PreCaseDeck />;
}
