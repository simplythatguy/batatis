import { useEffect, useMemo, useRef, useState } from "react";
import { DETAIL_FIELDS, PROCESS_FIELDS, factFor, isTyped, valueText } from "../model";
import { withinProvision } from "../provisions";
import { exitCountWarning } from "../rules";
import { useCandidateAnswer } from "../screens/CodeCheck";
import { Recommendations } from "../screens/Recommendations";
import { useCase } from "../store";
import { CodeDrawer, type DrawerState } from "./CodeDrawer";
import { aliasKey, buildDeck, choicesFor, type DeckItem } from "./deck";
import { updateSession, useSession } from "./session";
import { CIcon, Eyebrow, Kbd, MOD_KEY } from "./ui";

type Shown = DeckItem & { gone?: boolean };

const TEXT_KINDS = new Set(["question", "process"]);

function isTextTarget(t: EventTarget | null): boolean {
  const el = t as HTMLElement | null;
  if (!el) return false;
  return el.tagName === "TEXTAREA" || el.tagName === "INPUT" || el.tagName === "SELECT" || el.isContentEditable;
}

/** One card's controls. `onReady` tells the footer whether Continue can commit. */
function CardBody({
  item,
  picked,
  onPick,
  draft,
  setDraft,
  openDrawer,
}: {
  item: Shown;
  picked?: string;
  onPick: (value: string) => void;
  draft: string;
  setDraft: (v: string) => void;
  openDrawer: (s: DrawerState) => void;
}) {
  const { c, dispatch } = useCase();
  const [tips, setTips] = useState(false);
  const choices = choicesFor(item);

  if (item.kind === "section-d") {
    return (
      <div className="cf-embed cf-sectiond">
        <Recommendations />
      </div>
    );
  }

  const cand = item.kind === "candidate" || item.kind === "storeys" ? c.candidates.find((a) => a.id === item.ref) : undefined;
  const fact = item.kind === "detail" ? factFor(c, item.ref) : undefined;
  const def = item.kind === "detail" ? DETAIL_FIELDS.find((d) => d.id === item.ref) : undefined;

  let current: string | undefined = picked;
  if (item.kind === "candidate" && cand) current = cand.answer ?? undefined;
  if (item.kind === "authority") current = c.authority || undefined;
  if (item.kind === "detail" && def?.options) current = valueText(fact) || undefined;

  const answers = choices.length > 0 && (
    <div className={`cf-answers is-${choices.length}`} role="group" aria-label="Your answer">
      {choices.map((o, n) => (
        <button key={o.value} type="button" className="cf-answer" data-deck-answer aria-pressed={current === o.value} onClick={() => onPick(o.value)}>
          <span>{o.label}</span>
          <Kbd>{n + 1}</Kbd>
        </button>
      ))}
    </div>
  );

  return (
    <>
      {item.provision && (
        <button type="button" className="cf-cite" onClick={() => openDrawer({ mode: "code", candidateId: item.ref })}>
          <CIcon name="doc" size={13} />
          <b>{item.provision}</b> Show the code
        </button>
      )}
      {item.kind === "storeys" ? (
        <div className="cf-inline-answer">
          <label className="cf-sr" htmlFor="cf-storeys">Number of storeys</label>
          <input id="cf-storeys" className="cf-input is-number" type="number" inputMode="numeric" min={1} step={1} value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="e.g. 2" />
          <button type="button" className="cf-chip" aria-pressed={cand?.answer === "not-sure"} onClick={() => { setDraft(""); dispatch({ type: "setStoreyCount", value: "" }); }}>
            Not sure
          </button>
        </div>
      ) : item.kind === "question" ? (
        <textarea className="cf-textarea" rows={3} aria-label={item.title} value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Your answer" />
      ) : item.kind === "process" ? (
        <>
          <textarea
            className="cf-textarea is-tall"
            rows={6}
            aria-label={item.title}
            value={c.process[item.ref as keyof typeof c.process]}
            onChange={(e) => dispatch({ type: "setProcess", field: item.ref as keyof typeof c.process, value: e.target.value })}
            placeholder="In your own words…"
          />
          <button type="button" className="cf-btn is-ghost is-sm cf-tips-toggle" aria-expanded={tips} onClick={() => setTips((v) => !v)}>
            What to include
          </button>
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
            <textarea id={`field-${def.id}`} className="cf-textarea" rows={3} aria-label={def.label} value={valueText(fact)} onChange={(e) => dispatch({ type: "setDetail", field: def.id, value: e.target.value, section: def.section })} />
          ) : (
            <input
              id={`field-${def.id}`}
              className={`cf-input${def.inputType === "date" ? " is-date" : ""}`}
              type={def.inputType ?? "text"}
              aria-label={def.label}
              value={valueText(fact)}
              onChange={(e) => dispatch({ type: "setDetail", field: def.id, value: e.target.value, section: def.section })}
              placeholder={def.inputType === "date" ? undefined : def.label}
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
        answers
      )}
      {item.kind === "candidate" && !item.provision && (
        <button type="button" className="cf-btn is-ghost is-sm cf-find" onClick={() => openDrawer({ mode: "search" })}>
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
      {cand && exitCountWarning(cand.provision, cand.topic) && <p className="cf-note"><span className="cf-dot is-warning" aria-hidden="true" />{exitCountWarning(cand.provision, cand.topic)}</p>}
      {item.kind === "fact" && item.gone && <p className="cf-note"><span className="cf-dot is-done" aria-hidden="true" />{picked === "dismiss" ? "Removed." : "Confirmed."}</p>}
    </>
  );
}

export function Deck({ focus, codeFirst }: { focus: string | null; codeFirst: boolean }) {
  const { c, gaps, dispatch, requestCheck, checkStatus, checkNote, checkDetail, sectionCLookup } = useCase();
  const session = useSession();
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
  const cardRef = useRef<HTMLElement>(null);

  // Text drafts start from the saved answer each time a card opens.
  useEffect(() => {
    setWhy(false);
    if (!item) return setDraft("");
    if (item.kind === "question") setDraft(c.questions.find((q) => q.id === item.ref)?.answer ?? "");
    else if (item.kind === "storeys") setDraft(c.questions.find((q) => q.id === "q-desc-storeys")?.answer ?? "");
    else setDraft("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentKey]);

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
    const card = cardRef.current;
    const field = card?.querySelector<HTMLElement>(".cf-card-body input.cf-input, .cf-card-body textarea");
    (field ?? card?.querySelector<HTMLElement>("h2"))?.focus({ preventScroll: true });
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

  function canContinue(it: Shown): boolean {
    if (it.kind === "section-d") return true;
    if (it.kind === "question") return Boolean(draft.trim()) || it.done;
    if (it.kind === "storeys") return (Number.isInteger(Number(draft)) && Number(draft) > 0) || it.done;
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
    if (!item) return;
    setPicked((p) => ({ ...p, [item.key]: value }));
    if (item.kind === "fact") dispatch({ type: value === "confirm" ? "confirmFact" : "dismissFact", id: item.ref });
    else if (item.kind === "authority") {
      dispatch({ type: "setAuthority", authority: value as typeof c.authority });
      updateSession({ authorityUnsure: false });
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
    // Keys typed in the menu, a popover or any dialog belong to them.
    if (t?.closest?.(".cf-pop, dialog, [role='menu'], .cf-palette")) return;
    const inText = isTextTarget(t);
    const embedded = item?.kind === "section-d" && t && t !== document.body && !t.closest("[data-deck-foot]");
    if (embedded) return;
    if (e.key === "Enter") {
      if (t?.tagName === "TEXTAREA" && !(e.metaKey || e.ctrlKey)) return;
      if (t?.tagName === "SELECT") return;
      if (!inText && t && t !== document.body && !t.hasAttribute("data-deck-answer") && t !== cardRef.current?.querySelector("h2")) return;
      // Enter on an unpressed tile selects it (native click); only a pressed tile continues.
      if (t?.hasAttribute("data-deck-answer") && t.getAttribute("aria-pressed") !== "true") return;
      e.preventDefault();
      next();
      return;
    }
    if (!inText && !e.metaKey && !e.ctrlKey && !e.altKey && /^[1-3]$/.test(e.key) && item) {
      const choice = choicesFor(item)[Number(e.key) - 1];
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

  const doneFlags = queue.map((k) => Boolean(itemFor(k)?.done));
  const remainingAfter = queue.slice(index + 1).filter((k) => !itemFor(k)?.done).length;
  const openLeft = queue.filter((k) => !itemFor(k)?.done && !itemFor(k)?.optional).length;
  const segmented = queue.length > 0 && queue.length <= 24;
  const textEntry = item && (TEXT_KINDS.has(item.kind) || (item.kind === "detail" && DETAIL_FIELDS.find((d) => d.id === item.ref)?.multiline));

  return (
    <div className="cf-deck-page">
      <div className="cf-deck-head">
        <span className="cf-eyebrow is-plain cf-faint" aria-live="polite">
          {item ? `${index + 1} of ${queue.length}` : queue.length ? `${queue.length} of ${queue.length}` : "Nothing to ask"}
        </span>
        {segmented ? (
          <div className="cf-progress" aria-hidden="true">
            {doneFlags.map((d, i) => <i key={queue[i]} className={`${d ? "is-on" : ""}${i === index ? " is-current" : ""}`} />)}
          </div>
        ) : (
          <div className="cf-progress is-bar" aria-hidden="true"><i style={{ width: `${queue.length ? (100 * doneFlags.filter(Boolean).length) / queue.length : 100}%` }} /></div>
        )}
      </div>
      {checkStatus === "running" && <p className="cf-deck-status" role="status"><span className="cf-dot is-pending cf-pulse" aria-hidden="true" />{checkNote}</p>}
      {checkStatus === "unavailable" && (
        <div className="cf-deck-status" role="status">
          <span className="cf-dot is-warning" aria-hidden="true" />{checkNote}
          <button type="button" className="cf-btn is-xs" onClick={() => void requestCheck(true)}>Try the check again</button>
          {checkDetail && <details className="cf-tech"><summary>Technical detail</summary><p>{checkDetail}</p></details>}
        </div>
      )}
      <div className="cf-deck">
        {item && remainingAfter > 1 && <div className="cf-ghost is-2" aria-hidden="true" />}
        {item && remainingAfter > 0 && <div className="cf-ghost is-1" aria-hidden="true" />}
        {item ? (
          <article key={item.key} ref={cardRef} className={`cf-card cf-glass cf-enter${item.kind === "section-d" ? " is-wide" : ""}`} aria-labelledby="cf-q">
            <Eyebrow>{item.eyebrow}</Eyebrow>
            <h2 id="cf-q" className="cf-q" tabIndex={-1}>{item.title}</h2>
            {(item.context || item.quote) && (
              <p className="cf-context">
                {item.context}
                {item.quote && <> <q>{item.quote}</q></>}
              </p>
            )}
            <div className="cf-card-body">
              <CardBody item={item} picked={picked[item.key]} onPick={pick} draft={draft} setDraft={setDraft} openDrawer={setDrawer} />
            </div>
            {item.kind === "candidate" && decisionNoteFor(item.ref) && <p className="cf-note">{decisionNoteFor(item.ref)}</p>}
            {why && <p className="cf-why">{item.why}</p>}
            {!canContinue(item) && <p className="cf-hint" role="note">Answer to continue, or skip for now.</p>}
            <div className="cf-card-foot" data-deck-foot>
              <div className="cf-foot-left">
                <button type="button" className="cf-btn is-ghost is-sm" aria-expanded={why} onClick={() => setWhy((v) => !v)}>Why we ask</button>
                <button type="button" className="cf-btn is-ghost is-sm" onClick={skip}>{item.optional ? "Skip" : "Skip for now"}</button>
              </div>
              <button type="button" className="cf-btn is-primary" disabled={!canContinue(item)} onClick={next}>
                {item.kind === "section-d" ? "Finish Section D" : "Continue"} <Kbd>{textEntry ? `${MOD_KEY} ↵` : "↵"}</Kbd>
              </button>
            </div>
          </article>
        ) : (
          <article key="finish" className="cf-card cf-glass cf-enter cf-finish" aria-labelledby="cf-q">
            <Eyebrow>{openLeft ? "For now" : "All caught up"}</Eyebrow>
            <h2 id="cf-q" className="cf-q" tabIndex={-1}>That’s everything for now.</h2>
            <p className="cf-context">
              {openLeft
                ? `You skipped ${openLeft} ${openLeft === 1 ? "question" : "questions"}. They stay on your list and on the review.`
                : "Batatis checks what you have and shows anything still missing."}
            </p>
            <div className="cf-card-foot" data-deck-foot>
              <div className="cf-foot-left">
                {openLeft > 0 && (
                  <button
                    type="button"
                    className="cf-btn is-sm"
                    onClick={() => {
                      const first = queue.findIndex((k) => !itemFor(k)?.done && !itemFor(k)?.optional);
                      updateSession({ index: Math.max(first, 0), skipped: [], wrapped: true });
                    }}
                  >
                    <CIcon name="back" size={13} />Go back to skipped
                  </button>
                )}
              </div>
              <button type="button" className="cf-btn is-primary" onClick={next}>
                Review my application <Kbd>↵</Kbd>
              </button>
            </div>
          </article>
        )}
      </div>
      <CodeDrawer state={drawer} onClose={() => setDrawer(null)} onAdded={(id) => { setDrawer(null); setJumpTo(id); }} />
    </div>
  );
}
