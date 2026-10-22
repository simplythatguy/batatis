import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { DETAIL_FIELDS, NOT_RIGHT, PROCESS_FIELDS, factFor, isTyped, valueText } from "../model";
import { withinProvision } from "../provisions";
import { exitCountWarning } from "../rules";
import { useCandidateAnswer } from "../screens/CodeCheck";
import { Recommendations } from "../screens/Recommendations";
import { useCase } from "../store";
import { authorityName } from "./applications";
import { openAssistant, setAssistantContext, useAssistant } from "./assistant/assistant";
import { useCurrentApplication } from "./begin";
import { CodeDrawer, type DrawerState } from "./CodeDrawer";
import { aliasKey, alternativeChoice, buildDeck, mergeQueue, rankAhead, choiceKey, choicesFor, FORM_HINT, preCaseState, SECTIONS, sourcePhrase, type DeckItem, type SectionId } from "./deck";
import { forkOf, NOT_SURE, planInput } from "../intakeView";
import { localField } from "../intakeFields";
import { CodeProgress, ForkNote, ReadingState, ReadSource, RedirectPage, ShowCode } from "./ReadCards";
import { Icon24 } from "./icons";
import { RelevanceRing } from "./RelevanceRing";
import { getSession, updateSession, useSession } from "./session";
import { CONFLICT_TEXT } from "../api/sync";
import { retryExtras } from "./caseExtras";
import { CIcon, MOD_KEY } from "./ui";
import { engine } from "../api/client";
import { provisionCandidate } from "../screens/SectionC";
import { ConditionBody, PackageEnd, PackageOffer } from "./ChecklistCards";
import { otherOptions } from "./checklistView";
import { RuleNumberInput, RuleResultView } from "./RuleCards";
import { choiceValue, NOT_SURE_RULE, readNumber, RULE_REF, ruleFacts } from "./rulesView";
import { canonicalProvision } from "../provisions";
import { useDeckExtras } from "./useDeckExtras";
import { JurisdictionNote } from "./JurisdictionNote";
import { PACKAGE_YES, RULE_ADD, RULE_LEAVE } from "./deck";

type Shown = DeckItem & { gone?: boolean };

const FORM_HINT_KEY = "batatis-form-hint-seen";

/** Detect editable controls so deck keyboard shortcuts leave text entry to the control. */
function isTextTarget(t: EventTarget | null): boolean {
  const el = t as HTMLElement | null;
  if (!el) return false;
  return el.tagName === "TEXTAREA" || el.tagName === "INPUT" || el.tagName === "SELECT" || el.isContentEditable;
}

/** Cards answered by typing several lines continue with Cmd/Ctrl+Enter instead of Enter. */
function multiline(item: DeckItem): boolean {
  return item.kind === "question" || item.kind === "process" || (item.kind === "detail" && Boolean(DETAIL_FIELDS.find((d) => d.id === item.ref)?.multiline)) || (item.kind === "plan" && planInput(item.plan?.field ?? "").kind === "area");
}

/* —— Typeform pieces —— */

/** Stacked choices with letter keys. Pressed = selected; the check shows on the chosen one. */
export function Choices({ choices, current, onPick }: { choices: { value: string; label: string }[]; current?: string; onPick: (v: string) => void }) {
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
  // The assistant opening (or any resize) moves the sections; a list left open would point at nothing.
  const assistantOpen = useAssistant().open;
  useEffect(() => { setOpen(null); }, [assistantOpen]);
  useEffect(() => {
    const close = () => setOpen(null);
    window.addEventListener("resize", close);
    return () => window.removeEventListener("resize", close);
  }, []);
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
                  <span className="cf-qsec-name" title={s.label}>{s.short}</span>
                  <span className="cf-qsec-l"><span className="cf-sr">, Section </span>{s.id}</span>
                  <span className="cf-qsec-count">{s.done}<span className="cf-qsec-of"> of </span><span className="cf-qsec-slash" aria-hidden="true">/</span>{s.total}</span>
                </span>
                <span className="cf-sr">. Go to the first open question here.</span>
              </button>
              {open === s.id && (
                <div id={`cf-qsec-pop-${s.id}`} className={`cf-pop cf-qsec-pop${lastHalf(sn) ? " is-end" : ""}`} role="group" aria-label={`${s.label}, Section ${s.id} questions`}>
                  <p className="cf-qsec-about">{SECTIONS.find((x) => x.id === s.id)?.about}</p>
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

/** The value a planner answer left on the case, as the choice it was ("yes", "partial", Not sure). */
function planValue(item: Shown, c: ReturnType<typeof useCase>["c"]): string | undefined {
  const q = item.plan;
  if (!q) return undefined;
  if (c.intake?.record.plan?.not_sure.includes(q.id)) return NOT_SURE;
  const f = factFor(c, localField(q.field));
  if (f?.value == null || f.value === "") return undefined;
  return typeof f.value === "boolean" ? (f.value ? "yes" : "no") : String(f.value);
}

function PlanBody({ item, onPick, draft, setDraft, note, first }: { item: Shown; onPick: (value: string) => void; draft: string; setDraft: (v: string) => void; note: string; first: boolean }) {
  const { c, reading } = useCase();
  const q = item.plan!;
  const input = planInput(q.field);
  const current = planValue(item, c);
  const fork = forkOf(c);
  const busy = reading.busy === q.id;
  return (
    <>
      {first && fork && <ForkNote fork={fork} />}
      {input.kind === "choices" ? (
        <Choices choices={choicesFor(item)} current={current} onPick={onPick} />
      ) : (
        <div className={`cf-inline-answer${input.kind === "area" ? " is-wide" : ""}`}>
          <label className="cf-sr" htmlFor="cf-plan-answer">{q.text}</label>
          {input.kind === "area" ? (
            <textarea id="cf-plan-answer" className="cf-uline is-area" rows={2} value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Type your answer here…" />
          ) : (
            <input
              id="cf-plan-answer"
              className={`cf-uline${input.kind === "number" ? " is-number" : ""}`}
              type="text"
              inputMode={input.kind === "number" ? "decimal" : undefined}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder={input.kind === "number" ? "e.g. 2" : "Type your answer here…"}
            />
          )}
          {input.unit && <span className="cf-unit">{input.unit}</span>}
          <button type="button" className="cf-chip" aria-pressed={current === NOT_SURE} onClick={() => onPick(NOT_SURE)}>Not sure</button>
        </div>
      )}
      {busy && <p className="cf-note" role="status"><span className="cf-dot is-pending" aria-hidden="true" />Saving your answer…</p>}
      {!busy && note && <p className="cf-note" role="alert"><span className="cf-dot is-warning" aria-hidden="true" />{note}</p>}
      {!busy && !note && current === NOT_SURE && <p className="cf-note"><span className="cf-dot is-pending" aria-hidden="true" />Saved as Not sure. It never blocks you, and it is not asked again.</p>}
      {!busy && !note && current && current !== NOT_SURE && input.kind !== "choices" && <p className="cf-note"><span className="cf-dot is-done" aria-hidden="true" />Saved: {current}{input.unit ? ` ${input.unit}` : ""}.</p>}
    </>
  );
}

/** Render the current card’s inputs, saved answer, source details and loading or failure feedback. */
function CardBody({ item, picked, onPick, draft, setDraft, openDrawer, planNote, firstPlan, extras, note, busy, onReload, position }: { item: Shown; picked?: string; onPick: (value: string) => void; draft: string; setDraft: (v: string) => void; openDrawer: (s: DrawerState) => void; planNote: string; firstPlan: boolean; extras: ReturnType<typeof useDeckExtras>["extras"]; note: string; busy: boolean; onReload?: () => void; position: number }) {
  const { c, dispatch } = useCase();
  const session = useSession();
  const [tips, setTips] = useState(false);
  const choices = choicesFor(item);
  const index = extras.rules?.index;
  const cl = item.checklist ? extras.checklists?.checklists.find((x) => x.id === item.checklist) : undefined;

  if (item.kind === "rule-input" && item.input) {
    const { field, spec } = item.input;
    const fact = factFor(c, field);
    const unsure = session.ruleUnsure.includes(field) && (fact?.value === undefined || fact?.value === null);
    if (spec.type === "number" || spec.type === "int") {
      return <RuleNumberInput id={`cf-rule-${field}`} label={spec.label} unit={spec.unit} draft={draft} setDraft={setDraft} unsure={unsure} onUnsure={() => onPick(NOT_SURE_RULE)} note={note} />;
    }
    const current = unsure ? NOT_SURE_RULE : fact?.value === undefined || fact?.value === null ? undefined : String(fact.value);
    return <Choices choices={choices} current={current} onPick={onPick} />;
  }
  if (item.kind === "rule" && item.rule && index) {
    return (
      <>
        <RuleResultView rule={item.rule} index={index} />
        {choices.length > 0 && <Choices choices={choices} current={picked ?? (item.done ? RULE_LEAVE : undefined)} onPick={onPick} />}
        {busy && <p className="cf-note" role="status"><span className="cf-dot is-pending" aria-hidden="true" />Adding the rule…</p>}
        {!busy && note && <p className="cf-note" role="alert"><span className="cf-dot is-warning" aria-hidden="true" />{note}</p>}
      </>
    );
  }
  if (item.kind === "package" && cl) {
    return (
      <>
        <PackageOffer cl={cl} />
        <Choices choices={choices} current={session.packages[cl.id] ?? (cl.conditions.some((x) => x.answer) ? PACKAGE_YES : undefined)} onPick={onPick} />
      </>
    );
  }
  if (item.kind === "condition" && cl) {
    const row = cl.conditions.find((x) => x.id === item.condition);
    if (!row) return null;
    const current = picked ?? row.answer?.state;
    return (
      <ConditionBody cl={cl} row={row} position={position} reasonOpen={current === "does_not_apply"} reason={draft} setReason={setDraft} note={note} busy={busy} onReload={onReload}>
        <Choices choices={choices} current={current} onPick={onPick} />
      </ConditionBody>
    );
  }
  if (item.kind === "package-end" && cl) return <PackageEnd cl={cl} />;

  if (item.kind === "section-d") {
    return <div className="cf-embed cf-sectiond"><Recommendations /></div>;
  }
  if (item.kind === "plan") return <PlanBody item={item} onPick={onPick} draft={draft} setDraft={setDraft} note={planNote} first={firstPlan} />;
  if (item.kind === "code-run") return <CodeProgress />;
  if (item.kind === "reading") return <ReadingState />;
  if (item.kind === "code-note") {
    return (
      <div className="cf-row-actions">
        <button type="button" className="cf-btn" onClick={() => openDrawer({ mode: "search" })}><CIcon name="search" size={14} />Find the rule in the code yourself</button>
        <a className="cf-btn is-ghost" href="#/code">Open the code library</a>
      </div>
    );
  }
  if (item.kind === "file") return null;

  const cand = item.kind === "candidate" || item.kind === "storeys" ? c.candidates.find((a) => a.id === item.ref) : undefined;
  const fact = item.kind === "detail" ? factFor(c, item.ref) : undefined;
  const def = item.kind === "detail" ? DETAIL_FIELDS.find((d) => d.id === item.ref) : undefined;

  let current: string | undefined = picked;
  if (item.kind === "fact" && item.done && item.read) {
    const latest = c.facts.find((f) => item.ids?.includes(f.id)) ? undefined : factFor(c, c.intake?.facts.find((f) => f.id === item.ref)?.field ?? "");
    if (latest) current = latest.source.ref === NOT_RIGHT ? "dismiss" : "confirm";
  }
  if (item.kind === "candidate" && cand) current = cand.answer ?? undefined;
  if (item.kind === "authority") current = c.authority || (session.authorityUnsure ? "unsure" : undefined);
  if (item.kind === "detail" && def?.options) current = valueText(fact) || undefined;
  // The proposed alternative offers the description: Yes uses it, No opens the field.
  const offer = item.kind === "detail" && Boolean(item.confirmLabels);
  if (offer) current = picked === "dismiss" ? "dismiss" : alternativeChoice(c.description, valueText(fact)) ?? picked;

  return (
    <>
      {item.kind === "candidate" && item.rule && index && <RuleResultView rule={item.rule} index={index} onCard />}
      {item.kind === "fact" && item.read && <ReadSource copy={item.read} />}
      {item.provision && cand?.suggestion === "identify" ? (
        <ShowCode cand={cand} onMore={() => openDrawer({ mode: "code", candidateId: item.ref })} />
      ) : item.provision ? (
        <button type="button" className="cf-cite" onClick={() => openDrawer({ mode: "code", candidateId: item.ref })}>
          <RelevanceRing id={item.provision} focusable={false} />
          <b>{item.provision}</b> Show the code
        </button>
      ) : null}
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
          {offer && <Choices choices={choices} current={current} onPick={onPick} />}
          {offer && current !== "dismiss" ? null : def.multiline ? (
            <textarea id={`field-${def.id}`} className="cf-uline is-area" rows={2} aria-label={def.label} value={valueText(fact)} onChange={(e) => dispatch({ type: "setDetail", field: def.id, value: e.target.value, section: def.section })} placeholder={offer ? "What you propose instead, in a sentence or two…" : "Type your answer here…"} />
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
          {!offer && fact && !isTyped(fact) && (
            <p className="cf-note">
              <span className={`cf-dot ${fact.status === "confirmed" ? "is-done" : "is-warning"}`} aria-hidden="true" />
              {picked === "confirm" ? "Confirmed by you. You can still edit it." : `From ${sourcePhrase(fact.source.ref)}. Edit it if it’s not right.`}
            </p>
          )}
          {!offer && picked === "dismiss" && !fact && <p className="cf-note">Removed. Type the right one, or skip for now.</p>}
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
      {item.kind === "authority" && <JurisdictionNote authority={c.authority} unsure={current === "unsure"} extras={extras} />}
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

/* —— Before an application exists: nothing to ask yet —— */

/** One quiet line and the way back to Start, the one place to describe the project. */
function NoQuestionsYet() {
  const session = useSession();
  const { line, action } = preCaseState(session.draft);
  useEffect(() => {
    setAssistantContext({ screen: "question", label: "your new application", suggestions: ["What is an alternative solution?", "What should I describe?"] });
  }, []);
  return (
    <div className="cf-deck-page">
      <div className="cf-q-stage">
        <div className="cf-q-wrap cf-q-empty" role="group" aria-labelledby="cf-q-empty">
          <p id="cf-q-empty" className="cf-q-empty-line">{line}</p>
          <a
            className="cf-btn is-primary is-lg"
            href="#/"
            onClick={() => window.setTimeout(() => document.getElementById("cf-describe")?.focus(), 0)}
          >
            {action} <Icon24 name="right" size={16} stroke={2} />
          </a>
        </div>
      </div>
    </div>
  );
}

/* —— The application's deck —— */

/** Coordinate the visit queue, rule and checklist answers, and navigation through the case’s cards. */
function CaseDeck({ focus, codeFirst }: { focus: string | null; codeFirst: boolean }) {
  const { c, gaps, dispatch, requestCheck, sectionCLookup, reading, answerPlan, answerChecklist, reloadChecklists } = useCase();
  const session = useSession();
  const { app, locked } = useCurrentApplication();
  const { onAnswer, decisionNoteFor } = useCandidateAnswer();
  const { options: deckExtras, extras } = useDeckExtras();
  const seen = useMemo(() => new Set(session.seen), [session.seen]);
  const all = buildDeck(c, gaps, { ...deckExtras, seen, includeDone: true, identify: reading.identify, intake: reading.intake, intakeNote: reading.intakeNote });
  const byKey = new Map(all.map((i) => [i.key, i] as const));
  const snapshots = useRef(new Map<string, DeckItem>());
  for (const i of all) snapshots.current.set(i.key, i);
  /** Read a live card or retain its last snapshot when an answer removes it from the derived deck. */
  const itemFor = (k: string | undefined): Shown | undefined => {
    if (!k) return undefined;
    const live = byKey.get(k);
    if (live) return live;
    const snap = snapshots.current.get(k);
    return snap ? { ...snap, done: true, gone: true } : undefined;
  };

  // New open cards join this visit's queue in form order (code questions arriving after the check
  // land in the code section, not at the end); vanished, unseen keys leave it.
  const order = all.map((i) => i.key);
  const openKeys = all.filter((i) => !i.done).map((i) => i.key);
  const fresh = openKeys.filter((k) => !session.queue.includes(k));
  const sessionKey = session.queue[session.index];
  // Planner cards not yet reached follow the API's latest ranking (it re-ranks after the code check).
  const ranked = rankAhead(session.queue, session.index, order, (k) => k.startsWith("plan-"));
  const queue = fresh.length ? mergeQueue(ranked, fresh, order) : ranked;
  const index = sessionKey !== undefined ? Math.max(queue.indexOf(sessionKey), 0) : fresh.length ? queue.indexOf(fresh[0]) : Math.min(session.index, queue.length);
  const currentKey = queue[index];
  const item = itemFor(currentKey);
  const queueSig = `${fresh.join("|")}#${session.queue.filter((k) => !byKey.has(k) && k !== currentKey).join("|")}#${ranked.join("|") === session.queue.join("|") ? "" : ranked.join("|")}`;
  useEffect(() => {
    updateSession((s) => {
      const cur = s.queue[s.index];
      const kept = rankAhead(s.queue, s.index, order, (k) => k.startsWith("plan-")).filter((k) => byKey.has(k) || k === cur);
      const next = mergeQueue(kept, fresh, order);
      return { queue: next, index: cur ? Math.max(next.indexOf(cur), 0) : fresh.length ? next.indexOf(fresh[0]) : Math.min(s.index, next.length) };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queueSig]);

  const [picked, setPicked] = useState<Record<string, string>>({});
  const [why, setWhy] = useState(false);
  const [drawer, setDrawer] = useState<DrawerState | null>(null);
  const [jumpTo, setJumpTo] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [planNotes, setPlanNotes] = useState<Record<string, string>>({});
  /** Rule and package cards: a note per card (an error, or a 409 waiting for a reload), and the card being saved. */
  const [cardNotes, setCardNotes] = useState<Record<string, string>>({});
  const [conflicted, setConflicted] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const noteFor = (key: string, text: string) => setCardNotes((n) => ({ ...n, [key]: text }));
  // What the form is, said once: until dismissed, or until a few questions are answered.
  const [hintDismissed, setHintDismissed] = useState(() => {
    try { return localStorage.getItem(FORM_HINT_KEY) === "1"; } catch { return false; }
  });
  const formHintSeen = hintDismissed || session.seen.length >= 3;
  const dismissFormHint = () => {
    setHintDismissed(true);
    try { localStorage.setItem(FORM_HINT_KEY, "1"); } catch { /* storage unavailable */ }
  };
  useEffect(() => { if (session.seen.length >= 3 && !hintDismissed) dismissFormHint(); }, [session.seen.length]); // eslint-disable-line react-hooks/exhaustive-deps
  /** A typed planner answer was sent: move on once it is saved. */
  const advanceAfter = useRef<string | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const formPos = currentKey ? all.findIndex((i) => i.key === currentKey) : all.length;
  const dir = useDirection(formPos < 0 ? index : formPos);

  // Text drafts start from the saved answer each time a card opens.
  useEffect(() => {
    setWhy(false);
    if (!item) return setDraft("");
    if (item.kind === "question") setDraft(c.questions.find((q) => q.id === item.ref)?.answer ?? "");
    else if (item.kind === "storeys") setDraft(c.questions.find((q) => q.id === "q-desc-storeys")?.answer ?? "");
    else if (item.kind === "plan" && item.plan) {
      const saved = factFor(c, localField(item.plan.field))?.value;
      setDraft(saved == null || typeof saved === "boolean" ? "" : String(saved));
    } else if (item.kind === "rule-input" && item.input) {
      const saved = extras.rules ? ruleFacts(c, extras.rules.index).get(item.input.field)?.value : undefined;
      setDraft(typeof saved === "number" ? String(saved) : "");
    } else if (item.kind === "condition") {
      const row = extras.checklists?.checklists.find((x) => x.id === item.checklist)?.conditions.find((x) => x.id === item.condition);
      setDraft(row?.answer?.reason ?? "");
    } else setDraft("");
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
    if (item?.gone && (item.kind === "candidate" || item.kind === "storeys" || item.kind === "rule" || item.kind === "rule-input" || item.kind === "condition" || item.kind === "package" || item.kind === "package-end")) moveFrom(index, false);
    // The code check finished while its card was open: the code questions take its place.
    if (item?.gone && item.kind === "code-run") {
      const code = queue.findIndex((k) => { const it = itemFor(k); return Boolean(it && !it.done && it.section === "C"); });
      if (code >= 0) updateSession({ queue, index: code });
      else moveFrom(index, false);
    }
    // The reading finished: start at the first thing it read.
    if (item?.gone && (item.kind === "reading" || item.kind === "scope")) {
      const first = queue.findIndex((k) => { const it = itemFor(k); return Boolean(it && !it.done); });
      updateSession({ queue, index: first >= 0 ? first : queue.length });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [item?.key, item?.gone]);

  // A typed planner answer moves on once the engine has saved it.
  useEffect(() => {
    if (!item || advanceAfter.current !== item.key || !item.done) return;
    advanceAfter.current = null;
    moveFrom(index, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [item?.key, item?.done]);

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
      // The render's queue (with any new cards merged in) is the one `j` indexes.
      queue,
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

  /** Check whether the current answer can advance, including pending writes and required reasons. */
  function canContinue(it: Shown): boolean {
    if (locked) return false;
    if (it.kind === "section-d" || it.kind === "file" || it.kind === "code-run" || it.kind === "code-note") return true;
    if (it.kind === "reading") return reading.intake !== "running";
    if (it.kind === "scope") return false;
    if (it.kind === "plan") return it.done || (Boolean(draft.trim()) && reading.busy !== it.ref);
    if (it.kind === "question") return Boolean(draft.trim()) || it.done;
    if (it.kind === "storeys") return (Number.isInteger(Number(draft)) && Number(draft) > 0) || it.done;
    if (it.kind === "authority") return it.done || Boolean(c.authority) || session.authorityUnsure;
    if (it.kind === "rule") return it.rule?.state !== "departs" || it.done || picked[it.key] === RULE_LEAVE;
    if (it.kind === "package-end") return true;
    if (it.kind === "rule-input" && it.input && (it.input.spec.type === "number" || it.input.spec.type === "int")) return it.done || Boolean(draft.trim());
    if (it.kind === "condition") return busyKey !== it.key && ((picked[it.key] ?? currentState(it)) === "does_not_apply" ? Boolean(draft.trim()) : it.done);
    return it.done;
  }

  /** Save a typed answer before advancing, or open Review when the visit has no current card. */
  function next() {
    if (!item) {
      void requestCheck();
      location.hash = "#/review";
      return;
    }
    if (!canContinue(item)) return;
    if (item.kind === "plan" && item.plan && draft.trim() && planInput(item.plan.field).kind !== "choices") {
      const typed = draft.trim();
      const saved = factFor(c, localField(item.plan.field))?.value;
      if (!item.done || String(saved ?? "") !== typed) {
        sendPlan(item, typed, true);
        return;
      }
    }
    if (item.kind === "rule-input" && item.input && draft.trim() && (item.input.spec.type === "number" || item.input.spec.type === "int")) {
      const got = readNumber(item.input.spec, draft);
      if ("error" in got) return noteFor(item.key, got.error);
      noteFor(item.key, "");
      const saved = extras.rules ? ruleFacts(c, extras.rules.index).get(item.input.field)?.value : undefined;
      if (!item.done || saved !== got.value) {
        dispatch({ type: "setRuleInput", field: item.input.field, value: got.value, rule: item.input.rule, quote: `${draft.trim()}${item.input.spec.unit ? ` ${item.input.spec.unit}` : ""}` });
        updateSession((s) => ({ ruleUnsure: s.ruleUnsure.filter((f) => f !== item.input!.field) }));
        // Move on once the new value has rendered, so a question it opens comes next, not at the end.
        if (!item.done) {
          advanceAfter.current = item.key;
          return;
        }
      }
    }
    if (item.kind === "condition" && (picked[item.key] ?? currentState(item)) === "does_not_apply") {
      const row = conditionOf(item);
      if (row && (row.answer?.state !== "does_not_apply" || (row.answer.reason ?? "") !== draft.trim())) {
        sendCondition(item, "does_not_apply", draft.trim(), true);
        return;
      }
    }
    if (item.kind === "question" && draft.trim()) dispatch({ type: "answerQuestion", id: item.ref, answer: draft.trim() });
    if (item.kind === "storeys" && Number(draft) > 0) dispatch({ type: "setStoreyCount", value: draft });
    moveFrom(index, true);
  }

  /** Defer a required card until the return pass, or mark an optional card as seen. */
  function skip() {
    if (!item) return;
    // Optional cards are offered once; required ones come back at the end of this pass.
    moveFrom(index, item.optional, !item.optional);
  }

  /** One planner answer to the intake answers route; a typed answer moves on once saved. */
  function sendPlan(it: Shown, answer: string, advance: boolean) {
    if (!it.plan) return;
    const key = it.key;
    setPlanNotes((n) => ({ ...n, [key]: "" }));
    if (advance) advanceAfter.current = key;
    void answerPlan(it.plan, answer).then((error) => {
      if (!error) return;
      advanceAfter.current = null;
      setPlanNotes((n) => ({ ...n, [key]: error }));
    });
  }

  /** Find the current saved checklist condition associated with a deck card. */
  function conditionOf(it: Shown) {
    return extras.checklists?.checklists.find((x) => x.id === it.checklist)?.conditions.find((x) => x.id === it.condition);
  }
  /** Read a condition’s persisted answer before applying any local selection. */
  function currentState(it: Shown) {
    return conditionOf(it)?.answer?.state;
  }

  /** One checklist answer; a confirmed option records "does not apply" for the other options of its choice. */
  function sendCondition(it: Shown, state: "confirmed" | "not_yet" | "does_not_apply", reason: string, advance: boolean) {
    const cl = extras.checklists?.checklists.find((x) => x.id === it.checklist);
    const row = conditionOf(it);
    if (!cl || !row) return;
    const key = it.key;
    noteFor(key, "");
    setBusyKey(key);
    void (async () => {
      let error = await answerChecklist(cl.id, row.id, state, reason);
      if (!error && state === "confirmed") {
        for (const other of otherOptions(cl, row)) {
          error = await answerChecklist(cl.id, other.id, "does_not_apply", `Another option of this choice is followed instead (${row.option ?? row.source.label ?? "the confirmed option"}).`);
          if (error) break;
        }
      }
      setBusyKey((k) => (k === key ? null : k));
      if (error) {
        // Nothing was saved: the choice goes back to the saved answer.
        setPicked((p) => { const { [key]: _drop, ...rest } = p; return rest; });
        noteFor(key, error);
        setConflicted(error === CONFLICT_TEXT ? key : null);
        return;
      }
      setConflicted(null);
      if (!advance) return;
      // Move on only if the applicant is still on this card; a first answer moves once it renders.
      const s = getSession();
      if (s.queue[s.index] !== key) return;
      if (!row.answer) advanceAfter.current = key;
      else moveFrom(index, true);
    })();
  }

  /** "Add this rule to my application": the departure becomes a Code check card, answered Yes. */
  async function addRule(it: Shown) {
    const r = it.rule;
    if (!r) return;
    const id = r.provision.id;
    noteFor(it.key, "");
    setBusyKey(it.key);
    try {
      // A card for this sentence already exists (answered No earlier): answer it Yes instead.
      const existing = c.candidates.find((a) => canonicalProvision(a.provision) === canonicalProvision(id));
      if (existing) {
        onAnswer(existing, "yes");
        return;
      }
      const rec = await engine.provision(id, "B");
      const cand = provisionCandidate({ id, article_title: rec.article_title ?? r.title, title: rec.title ?? r.title, text: rec.text, citation: rec.citation ?? r.provision.citation });
      dispatch({ type: "addCandidate", candidate: cand });
      dispatch({ type: "answerCandidate", id: cand.id, answer: "yes" });
    } catch {
      setPicked((p) => { const { [it.key]: _drop, ...rest } = p; return rest; });
      noteFor(it.key, "The rule couldn’t be added just now. Try again.");
    } finally {
      setBusyKey((k) => (k === it.key ? null : k));
    }
  }

  /** Apply a card’s selected choice through the rule, package, checklist or case answer flow. */
  function pick(value: string) {
    if (!item || locked) return;
    if (item.kind === "rule-input" && item.input) {
      const { field, rule, spec } = item.input;
      setPicked((p) => ({ ...p, [item.key]: value }));
      if (value === NOT_SURE_RULE) {
        if (factFor(c, field)?.source.ref?.startsWith(RULE_REF)) dispatch({ type: "setRuleInput", field, value: null, rule, quote: "" });
        updateSession((s) => ({ ruleUnsure: s.ruleUnsure.includes(field) ? s.ruleUnsure : [...s.ruleUnsure, field] }));
        setDraft("");
        return;
      }
      dispatch({ type: "setRuleInput", field, value: choiceValue(spec, value), rule, quote: choicesFor(item).find((x) => x.value === value)?.label ?? value });
      updateSession((s) => ({ ruleUnsure: s.ruleUnsure.filter((f) => f !== field) }));
      return;
    }
    if (item.kind === "rule") {
      setPicked((p) => ({ ...p, [item.key]: value }));
      if (value === RULE_ADD) void addRule(item);
      else if (value === RULE_LEAVE) updateSession((s) => ({ seen: s.seen.includes(item.key) ? s.seen : [...s.seen, item.key] }));
      return;
    }
    if (item.kind === "package" && item.checklist) {
      const id = item.checklist;
      updateSession((s) => ({ packages: { ...s.packages, [id]: value as "yes" | "no" } }));
      return;
    }
    if (item.kind === "condition") {
      setPicked((p) => ({ ...p, [item.key]: value }));
      if (value === "does_not_apply") return; // the reason comes first; OK sends it
      sendCondition(item, value as "confirmed" | "not_yet", "", false);
      return;
    }
    setPicked((p) => ({ ...p, [item.key]: value }));
    if (item.kind === "plan") sendPlan(item, value, value === NOT_SURE && planInput(item.plan?.field ?? "").kind !== "choices");
    else if (item.kind === "fact") {
      // An answered card changes the value it left: Not right marks the confirmed value, Yes restores what was read.
      const field = c.intake?.facts.find((f) => f.id === item.ref)?.field;
      const latest = item.done && field ? factFor(c, field) : undefined;
      if (value === "dismiss" && latest && latest.source.ref !== NOT_RIGHT) dispatch({ type: "rejectFacts", ids: [latest.id] });
      else dispatch({ type: value === "confirm" ? "confirmFacts" : "rejectFacts", ids: item.ids ?? [item.ref] });
    }
    else if (item.kind === "authority") {
      dispatch({ type: "setAuthority", authority: value === "unsure" ? "" : (value as typeof c.authority) });
      updateSession({ authorityUnsure: value === "unsure" });
    } else if (item.kind === "candidate") {
      const cand = c.candidates.find((a) => a.id === item.ref);
      if (cand) onAnswer(cand, value as "yes" | "no" | "not-sure");
    } else if (item.kind === "detail" && item.confirmLabels) {
      const saved = valueText(factFor(c, item.ref));
      if (value === "confirm") dispatch({ type: "setDetail", field: item.ref, value: c.description.trim(), section: "B" });
      else if (alternativeChoice(c.description, saved) === "confirm") dispatch({ type: "setDetail", field: item.ref, value: "", section: "B" });
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
  const typed = Boolean(item && (item.kind === "condition" ? (picked[item.key] ?? currentState(item)) === "does_not_apply" : multiline(item)));

  return (
    <div className="cf-deck-page">
      {/* The check state lives on Review and in the header; the deck stays quiet. */}
      {locked && (
        <div className="cf-deck-status" role="status">
          <span className="cf-dot is-warning" aria-hidden="true" />{app?.status === "accepted" ? "Accepted as administratively complete" : `Sent to ${authorityName(app?.authority) || "the authority"}`}. Read-only until the officer returns it.
        </div>
      )}
      <div className="cf-q-stage">
        {item?.kind === "scope" && !item.gone ? (
          <RedirectPage n={n} />
        ) : item ? (
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
              <CardBody
                item={item}
                picked={picked[item.key]}
                onPick={pick}
                draft={draft}
                setDraft={setDraft}
                openDrawer={setDrawer}
                planNote={planNotes[item.key] ?? ""}
                firstPlan={item.kind === "plan" && queue.find((k) => k.startsWith("plan-")) === item.key}
                extras={extras}
                note={cardNotes[item.key] ?? ""}
                busy={busyKey === item.key}
                onReload={conflicted === item.key ? () => void reloadChecklists().then((e) => { noteFor(item.key, e ?? ""); if (!e) setConflicted(null); }) : undefined}
                position={item.kind === "condition" ? (extras.checklists?.checklists.find((x) => x.id === item.checklist)?.conditions.findIndex((x) => x.id === item.condition) ?? 0) + 1 : 0}
              />
            </fieldset>
            {item.kind === "candidate" && decisionNoteFor(item.ref) && <p className="cf-note">{decisionNoteFor(item.ref)}</p>}
            {item.section === "C" && (extras.failed.rules || extras.failed.case) && (
              <p className="cf-note" role="status"><span className="cf-dot is-warning" aria-hidden="true" />Rule checks didn’t load, so some rule questions may be missing. <button type="button" className="cf-link-btn" onClick={retryExtras}>Try again</button></p>
            )}
            {why && <p className="cf-why">{item.why}</p>}
            {!canContinue(item) && !locked && <p className="cf-hint" role="note">Answer to continue, or skip for now.</p>}
            <OkRow label={item.kind === "section-d" ? "Finish Section D" : item.kind === "code-run" ? "Continue" : "OK"} disabled={!canContinue(item)} onOk={next} typed={typed}>
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
                      updateSession({ queue, index: Math.max(first, 0), skipped: [], wrapped: true });
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
      {!formHintSeen && (
        <div className="cf-formhint" role="note">
          <span>{FORM_HINT}</span>
          <button type="button" className="cf-link-btn" onClick={dismissFormHint}>Got it</button>
        </div>
      )}
      <SectionFooter items={all} index={item ? pos : -1} onJump={(i) => goToKey(all[i]?.key ?? null)} onPrev={() => step(-1)} onNext={() => step(1)} canPrev={(pos < 0 ? all.length : pos) > 0} canNext={Boolean(item)} />
      <CodeDrawer state={drawer} onClose={() => setDrawer(null)} onAdded={(id) => { setDrawer(null); setJumpTo(id); }} />
    </div>
  );
}

/** Show the saved case’s deck or the prompt to describe a new application. */
export function Deck({ focus, codeFirst }: { focus: string | null; codeFirst: boolean }) {
  const { phase } = useCase();
  return phase === "case" ? <CaseDeck focus={focus} codeFirst={codeFirst} /> : <NoQuestionsYet />;
}
