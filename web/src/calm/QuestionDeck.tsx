import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { DETAIL_FIELDS, NOT_RIGHT, PROCESS_FIELDS, factFor, isTyped, valueText } from "../model";
import { withinProvision } from "../provisions";
import { exitCountWarning } from "../rules";
import { useCandidateAnswer } from "../screens/CodeCheck";
import { Recommendations } from "../screens/Recommendations";
import { useCase } from "../store";
import { readOnlyStatus } from "./applications";
import { openAssistant, setAssistantContext } from "./assistant/assistant";
import { questionContext } from "./assistant/questionContext";
import { useCurrentApplication } from "./begin";
import { CodeDrawer, type DrawerState } from "./CodeDrawer";
import { PictureConsent } from "./PictureConsent";
import { aliasKey, alternativeChoice, buildDeck, deferralFor, mergeQueue, rankAhead, choiceKey, choicesFor, paperworkRowKey, preCaseState, type DeckItem } from "./deck";
import { NOT_SURE, planFactAnswer, planInput, sourceLine } from "../intakeView";
import { confirmedAnswer, localField } from "../intakeFields";
import { KeywordTriage } from "./KeywordTriage";
import { CodeProgress, ReadingState, ReadSource, RedirectPage, ShowCode, UnderstoodFacts, ProductRouteNotice, ForkNote } from "./ReadCards";
import { Icon24 } from "./icons";
import { RelevanceRing } from "./RelevanceRing";
import { getSession, updateSession, useSession } from "./session";
import { CONFLICT_TEXT, engineGeneration } from "../api/sync";
import { retryExtras, getExtras } from "./caseExtras";
import { CIcon } from "./ui";
import { engine } from "../api/client";
import { provisionCandidate } from "../screens/SectionC";
import { ConditionBody, PackageEnd, PackageOffer } from "./ChecklistCards";
import { otherOptions } from "./checklistView";
import { RuleNumberInput, RuleResultView } from "./RuleCards";
import { choiceValue, NOT_SURE_RULE, readNumber, ruleFacts } from "./rulesView";
import { canonicalProvision } from "../provisions";
import { useDeckExtras } from "./useDeckExtras";
import { JurisdictionNote } from "./JurisdictionNote";
import { AuthorityPicker } from "./AuthorityPicker";
import { DatePicker } from "./DatePicker";
import { DocumentReview } from "./DocumentReview";
import { PaperworkSheet } from "./PaperworkSheet";
import { AUTHORITIES, authorityUnsure, officeChoiceAction, officeSuggestion } from "../config";
import { PACKAGE_YES, RULE_ADD, RULE_LEAVE } from "./deck";
import { useAccount } from "./account";
import { useQuestionDraft } from "./useQuestionDraft";
import { ApplicantDraftLink, processDraftField } from "./ApplicantDrafts";
import { StatementReview } from "./StatementReview";
import { CLAIM_NOTE, CLAIM_WORDS, departureComparison, departureRecordsVariance } from "./departure";
import { DepartureCompare } from "./DepartureCompare";
import { UnitInput } from "./UnitInput";
import { measurementText, metricUnit, parseMeasurement } from "./units";
import { todayIn, toIso } from "./calendarDate";
import { clearJourneyAnswerAction, journeyAnswerAction, journeyProgress, itemOpen, productScope, routeChoice, STAGES, type Answerer } from "./journey";
import "./journey.css";
import { codeHref } from "./routes";
import { requirementAnswer, type RequirementAnswer } from "./requirements";

type Shown = DeckItem & { gone?: boolean };


/** Detect editable controls so deck keyboard shortcuts leave text entry to the control. */
function isTextTarget(t: EventTarget | null): boolean {
  const el = t as HTMLElement | null;
  if (!el) return false;
  return el.tagName === "TEXTAREA" || el.tagName === "INPUT" || el.tagName === "SELECT" || el.isContentEditable;
}

/** Cards answered by typing several lines continue with Cmd/Ctrl+Enter instead of Enter. */
function multiline(item: DeckItem): boolean {
  return item.kind === "departure" || item.kind === "route-detail" || item.kind === "question" || item.kind === "process" || (item.kind === "detail" && Boolean(DETAIL_FIELDS.find((d) => d.id === item.ref)?.multiline)) || (item.kind === "plan" && planInput(item.plan?.field ?? "").kind === "area");
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

function OkRow({ label = "Continue", disabled, onOk, typed, children, primary = true, quiet = false }: { label?: string; disabled?: boolean; onOk: () => void; typed: boolean; children?: ReactNode; primary?: boolean; quiet?: boolean }) {
  return (
    <div className="cf-ok-row" data-deck-foot>
      {primary && <button type="button" className={`cf-btn is-lg${quiet ? "" : " is-primary"}`} disabled={disabled} onClick={onOk} aria-keyshortcuts={typed ? "Meta+Enter Control+Enter" : "Enter"}>
        {label} <Icon24 name="check" size={16} stroke={2} />
      </button>}
      {children}
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

/**
 * The card being replaced leaves in the direction of travel while the next one enters. React has
 * already let go of the old card when its ref detaches, so an inert copy plays the exit and is removed.
 */
function useLeavingCard(dir: "down" | "up") {
  const stage = useRef<HTMLDivElement>(null);
  const card = useRef<HTMLDivElement | null>(null);
  const travel = useRef(dir);
  travel.current = dir;
  const ref = useRef((node: HTMLDivElement | null) => {
    const old = card.current;
    card.current = node;
    const host = stage.current;
    if (node) {
      // The same question remounted (its card was rebuilt): it stays in place, with no exit or entrance.
      const layer = host?.querySelector(".cf-q-leave");
      if (layer && layer.querySelector("h2")?.textContent === node.querySelector("h2")?.textContent) {
        layer.remove();
        node.style.animation = "none";
      }
      return;
    }
    if (!old || !host?.isConnected || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    host.querySelectorAll(".cf-q-leave").forEach((layer) => layer.remove());
    const copy = old.cloneNode(true) as HTMLDivElement;
    const fields = old.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>("input, textarea");
    copy.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>("input, textarea").forEach((f, i) => { f.value = fields[i]?.value ?? ""; });
    copy.querySelectorAll("[id]").forEach((el) => el.removeAttribute("id"));
    copy.classList.remove("is-from-down", "is-from-up");
    copy.style.animation = "";
    const layer = document.createElement("div");
    layer.className = `cf-q-leave is-to-${travel.current === "down" ? "up" : "down"}`;
    layer.setAttribute("aria-hidden", "true");
    layer.inert = true;
    layer.append(copy);
    host.append(layer);
    copy.addEventListener("animationend", () => layer.remove(), { once: true });
    window.setTimeout(() => layer.remove(), 400);
  }).current;
  return { stage, ref };
}

/* —— Journey progress and the map, shared with the end screen —— */

const ANSWERER_ICON = { you: "user", designer: "compose", office: "landmark", batatis: "spark" } as const;
const ANSWERER_LABEL = { you: "You", designer: "Your designer", office: "The office", batatis: "To confirm" };

export function AnswererCounts({ counts }: { counts: Record<Answerer, number> }) {
  const shown = { ...counts, you: counts.you + counts.batatis };
  return <span className="cf-journey-counts">{(["you", "designer", "office"] as const).map((who) => shown[who] > 0 && <span key={who} role="img" title={`${ANSWERER_LABEL[who]}: ${shown[who]}`} aria-label={`${ANSWERER_LABEL[who]}: ${shown[who]}`}><Icon24 name={ANSWERER_ICON[who]} size={15} />{shown[who]}</span>)}</span>;
}

export function JourneyMap({ items, onJump }: { items: DeckItem[]; onJump: (key: string) => void }) {
  const progress = journeyProgress(items);
  return <div className="cf-journey-map" aria-label="Where you stand">{progress.stages.filter((s) => s.total > 0).map((s) => {
    const first = items.find((i) => i.stage === s.stage && i.answerer !== "office" && itemOpen(i)) ?? items.find((i) => i.stage === s.stage && i.answerer !== "office");
    return <div key={s.stage} className="cf-journey-map-row">
      <button type="button" className="cf-link-btn" disabled={!first} onClick={() => first && onJump(first.key)}>{STAGES.find((stage) => stage.stage === s.stage)?.label}</button>
      {s.open ? <AnswererCounts counts={s.byAnswerer} /> : <span className="cf-faint"><Icon24 name="check" size={14} /><span className="cf-sr">Done</span></span>}
    </div>;
  })}</div>;
}

export function SectionFooter({ items, index, onJump, onPrev, onNext, canPrev, canNext }: { items: Shown[]; index: number; onJump: (i: number) => void; onPrev: () => void; onNext: () => void; canPrev: boolean; canNext: boolean }) {
  const [map, setMap] = useState(false);
  const pop = useRef<HTMLDivElement>(null);
  const toggle = useRef<HTMLButtonElement>(null);
  const progress = journeyProgress(items);
  const current = items[index]?.stage;
  const jump = (key: string) => { setMap(false); onJump(items.findIndex((i) => i.key === key)); };
  const firstOf = (stage: string) => items.find((i) => i.stage === stage && i.answerer !== "office" && itemOpen(i)) ?? items.find((i) => i.stage === stage && i.answerer !== "office");
  const yours = progress.open.you + progress.open.batatis;
  const designer = progress.open.designer;
  // The map is a popover: focus moves in, Escape or a click elsewhere closes it and returns focus.
  useEffect(() => {
    if (!map) return;
    pop.current?.querySelector<HTMLElement>("button:not(:disabled)")?.focus({ preventScroll: true });
    const away = (e: PointerEvent) => { if (!pop.current?.contains(e.target as Node) && !toggle.current?.contains(e.target as Node)) setMap(false); };
    const esc = (e: KeyboardEvent) => { if (e.key !== "Escape") return; e.preventDefault(); setMap(false); toggle.current?.focus({ preventScroll: true }); };
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", esc, true);
    return () => { document.removeEventListener("pointerdown", away); document.removeEventListener("keydown", esc, true); };
  }, [map]);
  return <footer className="cf-qfoot cf-journey-foot" aria-label="Journey progress">
    <div className="cf-journey-steps">{STAGES.map((s) => {
      const stage = progress.stages.find((p) => p.stage === s.stage)!;
      if (!items.some((i) => i.stage === s.stage)) return null;
      const on = current === s.stage;
      const first = firstOf(s.stage);
      return <button key={s.stage} type="button" className={`cf-journey-step${on ? " is-on" : ""}`} aria-current={on ? "step" : undefined} title={`${s.label}: ${stage.open} open`} aria-label={`${s.label}: ${stage.open} open`} disabled={!first} onClick={() => first && jump(first.key)}>
        <span className={`cf-journey-step-mark${stage.total > 0 && stage.open === 0 ? " is-done" : ""}`} aria-hidden="true" />
        <span className="cf-journey-step-word" aria-hidden="true"><span>{s.label}</span></span>
      </button>;
    })}</div>
    <button ref={toggle} type="button" className="cf-link-btn cf-journey-map-toggle" aria-expanded={map} aria-haspopup="dialog" onClick={() => setMap((v) => !v)}>
      {yours > 0 ? `${yours} left` : "Your part is done"}{designer > 0 && <span className="cf-faint"> · {designer} for your designer</span>}
      <Icon24 name="up" size={14} />
    </button>
    <div ref={pop} className="cf-pop cf-journey-pop" role="dialog" aria-label="Where you stand" data-open={map ? "" : undefined} inert={!map}>
      <div className="cf-journey-map-head"><span>Where you stand</span><button type="button" className="cf-icon-btn" aria-label="Close" onClick={() => { setMap(false); toggle.current?.focus({ preventScroll: true }); }}><Icon24 name="x" size={14} /></button></div>
      <JourneyMap items={items} onJump={jump} />
    </div>
    <div className="cf-qnav">
      <button type="button" className="cf-icon-btn cf-qnav-btn" aria-label="Previous question (↑)" disabled={!canPrev} onClick={onPrev}><Icon24 name="up" size={16} /></button>
      <button type="button" className="cf-icon-btn cf-qnav-btn" aria-label="Next question (↓)" disabled={!canNext} onClick={onNext}><Icon24 name="down" size={16} /></button>
    </div>
  </footer>;
}

export function JourneyEnd({ items, standard, product, onJump, onReview }: { items: DeckItem[]; standard: boolean; product: boolean; onJump: (key: string) => void; onReview: () => void }) {
  const [copyNote, setCopyNote] = useState("");
  const progress = journeyProgress(items);
  const yours = items.filter((i) => !i.optional && (i.answerer === "you" || i.answerer === "batatis") && itemOpen(i));
  const designers = items.filter((i) => i.answerer === "designer" && itemOpen(i));
  const office = items.filter((i) => i.answerer === "office" && itemOpen(i));
  const count = progress.open.you + progress.open.batatis;
  const copyQuestions = async () => {
    try {
      await navigator.clipboard.writeText(designers.map((i) => `• ${i.title}`).join("\n"));
      setCopyNote("Copied");
    } catch {
      setCopyNote("Couldn’t copy. Select the questions above to copy them.");
    }
  };
  return <>
    <h2 id="cf-q" className="cf-q-text" tabIndex={-1}>{progress.yourPartDone ? "Your part is done" : `${count} still need you`}</h2>
    {standard && <p className="cf-q-help">Prepare the usual permit documents and evidence for your permit office.</p>}
    {product && <p className="cf-q-help">Your next step is product acceptance, such as a CCMC evaluation. A pilot building can have its own site variance.</p>}
    <JourneyMap items={items} onJump={onJump} />
    {yours.length > 0 && <button type="button" className="cf-link-btn" onClick={() => onJump(yours[0].key)}>Go to the first one</button>}
    {designers.length > 0 && <section className="cf-journey-list" aria-label="For your designer"><h3><Icon24 name="compose" size={17} />For your designer</h3><ul>{designers.map((i) => <li key={i.key}><button type="button" className="cf-link-btn" onClick={() => onJump(i.key)}>{i.title}</button></li>)}</ul><button type="button" className="cf-link-btn" onClick={() => void copyQuestions()}>Copy questions</button>{copyNote && <p className="cf-note" role="status">{copyNote}</p>}</section>}
    {office.length > 0 && <section className="cf-journey-list" aria-label="To confirm with the office"><h3><Icon24 name="landmark" size={17} />To confirm with the office</h3><ul>{office.map((i) => <li key={i.key}>{i.title}</li>)}</ul></section>}
    <OkRow label="See my application" onOk={onReview} typed={false} />
  </>;
}

/* —— One card's controls —— */

/** The value a planner answer left on the case, as the choice it was ("yes", "partial", Not sure). */
function planValue(item: Shown, c: ReturnType<typeof useCase>["c"]): string | undefined {
  const q = item.plan;
  if (!q) return undefined;
  if (c.intake?.record.plan?.not_sure.includes(q.id)) return NOT_SURE;
  const f = factFor(c, localField(q.field));
  if (f?.value == null || f.value === "") return undefined;
  if (q.field === "faces_public_way") return f.value === false ? "neighbour" : f.source.quote === "A street" ? "street" : "lane";
  return typeof f.value === "boolean" ? (f.value ? "yes" : "no") : String(f.value);
}

function PlanBody({ item, onPick, draft, setDraft, note }: { item: Shown; onPick: (value: string) => void; draft: string; setDraft: (v: string) => void; note: string }) {
  const { c, reading } = useCase();
  const q = item.plan!;
  const input = planInput(q.field);
  const current = planValue(item, c);
  const selected = item.deferred ?? (current === NOT_SURE ? "not_sure" : current);
  const busy = reading.busy === q.id;
  const unit = metricUnit(input.unit);
  return (
    <>
      {input.kind === "choices" ? (
        <Choices choices={choicesFor(item)} current={selected} onPick={onPick} />
      ) : unit ? (
        <UnitInput id="cf-plan-answer" label={q.text} unit={unit} value={draft} onChange={setDraft} />
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
          {input.unit && !unit && <span className="cf-unit">{input.unit}</span>}
        </div>
      )}
      {busy && <p className="cf-note" role="status"><span className="cf-dot is-pending" aria-hidden="true" />Saving your answer…</p>}
      {!busy && note && <p className="cf-note" role="alert"><span className="cf-dot is-warning" aria-hidden="true" />{note}</p>}
      {!busy && !note && current === NOT_SURE && <p className="cf-note"><span className="cf-dot is-pending" aria-hidden="true" />Saved as Not sure.</p>}
      {!busy && !note && current && current !== NOT_SURE && input.kind !== "choices" && <p className="cf-note"><span className="cf-dot is-done" aria-hidden="true" />Saved: {current}{input.unit ? ` ${input.unit}` : ""}.</p>}
    </>
  );
}

const DEPARTURE_EDIT = "edit";

/** Render the current card’s inputs, saved answer, source details and loading or failure feedback. */
function CardBody({ item, picked, onPick, draft, setDraft, openDrawer, planNote, extras, note, busy, onReload, position, focusRow, onPaperworkDone }: { item: Shown; picked?: string; onPick: (value: string) => void; draft: string; setDraft: (v: string) => void; openDrawer: (s: DrawerState) => void; planNote: string; extras: ReturnType<typeof useDeckExtras>["extras"]; note: string; busy: boolean; onReload?: () => void; position: number; focusRow: string | null; onPaperworkDone: () => void }) {
  const { c, dispatch, drafting } = useCase();
  const session = useSession();
  const [tips, setTips] = useState(false);
  const choices = choicesFor(item);
  const index = extras.rules?.index;
  const cl = item.checklist ? extras.checklists?.checklists.find((x) => x.id === item.checklist) : undefined;

  if (item.kind === "rule-input" && item.input) {
    const { field, spec } = item.input;
    const fact = factFor(c, field);
    const unsure = Boolean(item.deferred || item.settled) && (fact?.value === undefined || fact?.value === null);
    if (spec.type === "number" || spec.type === "int") {
      const unit = metricUnit(spec.unit);
      if (unit) return <>
        <UnitInput id={`cf-rule-${field}`} label={spec.label} unit={unit} value={draft} onChange={setDraft} />
        {note && <p className="cf-note" role="alert">{note}</p>}
        {!note && unsure && <p className="cf-note">Saved as Not sure.</p>}
      </>;
      return <RuleNumberInput id={`cf-rule-${field}`} label={spec.label} unit={spec.unit} draft={draft} setDraft={setDraft} unsure={unsure} note={note} />;
    }
    const publicWay = field === "faces_public_way";
    const current = item.deferred ?? (unsure ? "not_sure" : publicWay && fact?.value != null ? fact.value === false ? "neighbour" : fact.source.quote === "A street" ? "street" : "lane" : fact?.value === undefined || fact?.value === null ? undefined : String(fact.value));
    return <>
      <Choices choices={choices} current={current} onPick={onPick} />
      {unsure && <p className="cf-note"><span className="cf-dot is-pending" aria-hidden="true" />Saved as Not sure. The rule stays open.</p>}
    </>;
  }
  if (item.kind === "rule" && item.rule && index) {
    return (
      <>
        <RuleResultView rule={item.rule} index={index} />
        {choices.length > 0 && <Choices choices={choices} current={item.deferred ?? picked ?? (item.done ? RULE_LEAVE : undefined)} onPick={onPick} />}
        {busy && <p className="cf-note" role="status"><span className="cf-dot is-pending" aria-hidden="true" />Adding the rule…</p>}
        {!busy && note && <p className="cf-note" role="alert"><span className="cf-dot is-warning" aria-hidden="true" />{note}</p>}
      </>
    );
  }
  if (item.kind === "package" && cl) {
    return (
      <>
        <PackageOffer cl={cl} />
        <Choices choices={choices} current={item.deferred ?? String(factFor(c, `journey.package.${cl.id}`)?.value ?? session.packages[cl.id] ?? (cl.conditions.some((x) => x.answer) ? PACKAGE_YES : ""))} onPick={onPick} />
      </>
    );
  }
  if (item.kind === "condition" && cl) {
    const row = cl.conditions.find((x) => x.id === item.condition);
    if (!row) return null;
    const current = item.deferred ?? picked ?? row.answer?.state;
    return (
      <ConditionBody cl={cl} row={row} position={position} reasonOpen={current === "does_not_apply"} reason={draft} setReason={setDraft} note={note} busy={busy} onReload={onReload}>
        <Choices choices={choices} current={current} onPick={onPick} />
      </ConditionBody>
    );
  }
  if (item.kind === "package-end" && cl) return <PackageEnd cl={cl} />;

  if (item.kind === "section-d") {
    return <><ApplicantDraftLink field="evidence_plan" /><div className="cf-embed cf-sectiond"><Recommendations /></div></>;
  }
  if (item.kind === "understood") return <UnderstoodFacts item={item} />;
  if (item.kind === "drafts") return <StatementReview />;
  if (item.kind === "paperwork") return <PaperworkSheet key={engineGeneration()} item={item} focusRow={focusRow} onDone={onPaperworkDone} extras={extras} />;
  if (item.kind === "route") {
    const saved = routeChoice(c);
    const current = saved === "variance" && c.intake?.record.plan?.fork.variance_needed === "not_indicated" ? "different" : saved ?? undefined;
    return <>{choices.length > 0 && <Choices choices={choices} current={picked ?? current} onPick={onPick} />}{c.intake?.record.plan?.fork && <ForkNote fork={c.intake.record.plan.fork} detailsOnly />}</>;
  }
  if (item.kind === "product-notice") return <ProductRouteNotice />;
  if (item.kind === "role") return <Choices choices={choices} current={String(factFor(c, "applicant_role")?.value ?? "")} onPick={onPick} />;
  if (item.kind === "route-detail") return <textarea className="cf-uline is-area" rows={2} aria-label={item.title} value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="What you want to do differently…" />;
  if (item.kind === "plan" || item.kind === "product-scope") return <PlanBody item={item} onPick={onPick} draft={draft} setDraft={setDraft} note={planNote} />;
  if (item.kind === "code-run") return <CodeProgress />;
  if (item.kind === "code-triage") return <KeywordTriage c={c} openDrawer={openDrawer} />;
  if (item.kind === "reading") return <ReadingState />;
  if (item.kind === "code-note") {
    return (
      <div className="cf-row-actions">
        <button type="button" className="cf-btn" onClick={() => openDrawer({ mode: "search" })}><CIcon name="search" size={14} />Find the rule in the code yourself</button>
        <a className="cf-btn is-ghost" href="#/code">Open the code library</a>
      </div>
    );
  }
  if (item.kind === "code-ledger") {
    return (
      <div className="cf-row-actions">
        <a className="cf-btn" href="#/code">Open the code library</a>
        <button type="button" className="cf-btn is-ghost" onClick={() => openDrawer({ mode: "search" })}><CIcon name="search" size={14} />Find a rule</button>
      </div>
    );
  }
  if (item.kind === "requirement" && item.requirement) {
    // The stored answer shows until the applicant picks another one.
    const chosen = (picked as RequirementAnswer | undefined) ?? requirementAnswer(item.requirement);
    const needsReason = chosen === "does-not-apply" || chosen === "not-sure";
    return (
      <>
        <a className="cf-cite" href={codeHref(item.provision)}>
          {item.provision && <RelevanceRing id={item.provision} focusable={false} />}
          <b>{item.provision}</b> Show the code
        </a>
        <Choices choices={choices} current={chosen ?? undefined} onPick={onPick} />
        {needsReason && (
          <textarea
            className="cf-uline is-area"
            rows={2}
            aria-label={chosen === "does-not-apply" ? "Why it doesn’t apply" : "What you’re unsure about"}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={chosen === "does-not-apply" ? "In a sentence, why this rule doesn’t apply." : "What would decide it? A sentence is enough."}
          />
        )}
        {busy && <p className="cf-note" role="status"><span className="cf-dot is-pending" aria-hidden="true" />Saving your answer…</p>}
        {!busy && note && <p className="cf-note" role="alert"><span className="cf-dot is-warning" aria-hidden="true" />{note}</p>}
      </>
    );
  }
  if (item.kind === "file") return null;

  const cand = item.kind === "candidate" || item.kind === "storeys" || item.kind === "departure" ? c.candidates.find((a) => a.id === item.ref) : undefined;
  const fact = item.kind === "detail" ? factFor(c, item.ref) : undefined;
  const def = item.kind === "detail" ? DETAIL_FIELDS.find((d) => d.id === item.ref) : undefined;

  let current: string | undefined = picked;
  if (item.kind === "fact" && item.done && item.read) {
    const latest = c.facts.find((f) => item.ids?.includes(f.id)) ? undefined : factFor(c, c.intake?.facts.find((f) => f.id === item.ref)?.field ?? "");
    if (latest) current = latest.source.ref === NOT_RIGHT ? "dismiss" : "confirm";
  }
  if (item.kind === "candidate" && cand) current = cand.answer === "not-sure" ? "not_sure" : cand.answer ?? undefined;
  if (item.kind === "authority") current = c.authority || (item.deferred || authorityUnsure(c) ? "unsure" : undefined);
  if (item.kind === "detail" && def?.options) current = valueText(fact) || undefined;
  // The proposed alternative offers the description: Yes uses it, No opens the field.
  const offer = item.kind === "detail" && Boolean(item.confirmLabels || item.suggestedValue);
  if (offer) current = picked === "dismiss" ? "dismiss" : alternativeChoice(c.description, valueText(fact)) ?? picked;
  if (item.suggestedValue) current = picked === "edit-suggested" ? picked : valueText(fact) === item.suggestedValue ? "use-suggested" : picked;
  current = item.deferred ?? current;

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
      {item.kind === "departure" ? (
        <>
          {picked === DEPARTURE_EDIT || !cand ? (
            <div className="cf-inline-answer">
              <label className="cf-sr" htmlFor={`field-${item.ref}-departure`}>What your design does instead</label>
              <textarea id={`field-${item.ref}-departure`} className="cf-uline is-area" rows={2} aria-label="What your design does instead" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="In one sentence." autoFocus={picked === DEPARTURE_EDIT} />
            </div>
          ) : <DepartureCompare lines={departureComparison(c, cand, drafting)} onEdit={() => onPick(DEPARTURE_EDIT)} />}
          {busy && <p className="cf-note" role="status"><span className="cf-dot is-pending" aria-hidden="true" />Saving…</p>}
          {!busy && note && <p className="cf-note" role="alert"><span className="cf-dot is-warning" aria-hidden="true" />{note}</p>}
        </>
      ) : item.kind === "storeys" ? (
        <div className="cf-inline-answer">
          <label className="cf-sr" htmlFor="cf-storeys">Number of storeys</label>
          <input id="cf-storeys" className="cf-uline is-number" type="number" inputMode="numeric" min={1} step={1} value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="e.g. 2" />
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
          <ApplicantDraftLink field={processDraftField(item.ref)} />
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
          {item.suggestedValue && current !== "edit-suggested" && <p className="cf-note">{item.suggestedValue} <span className="cf-source-chip is-assumed">{item.ref === "date" ? "default" : "assumed"}</span></p>}
          {offer && current !== "dismiss" && current !== "edit-suggested" ? null : def.multiline ? (
            <textarea id={`field-${def.id}`} className="cf-uline is-area" rows={2} aria-label={def.label} value={valueText(fact)} onChange={(e) => dispatch({ type: "setDetail", field: def.id, value: e.target.value, section: def.section })} placeholder={offer ? "What you propose instead, in a sentence or two…" : "Type your answer here…"} />
          ) : def.inputType === "date" ? (
            <DatePicker id={`field-${def.id}`} label={def.label} value={valueText(fact)} onChange={(value) => dispatch({ type: "setDetail", field: def.id, value, section: def.section })} />
          ) : (
            <input
              id={`field-${def.id}`}
              className="cf-uline"
              type={def.inputType ?? "text"}
              aria-label={def.label}
              value={valueText(fact)}
              onChange={(e) => dispatch({ type: "setDetail", field: def.id, value: e.target.value, section: def.section })}
              placeholder={def.hint ?? "Type your answer here…"}
            />
          )}
          {!offer && fact && !isTyped(fact) && (
            <p className="cf-note">
              <span className={`cf-dot ${fact.status === "confirmed" ? "is-done" : "is-warning"}`} aria-hidden="true" />
              {picked === "confirm" ? "Confirmed" : `From ${sourceLine(c, fact)}`}
            </p>
          )}
          {!offer && picked === "dismiss" && !fact && <p className="cf-note">Removed.</p>}
          {def.id === "alternative" && <ApplicantDraftLink field="alternative_description" />}
        </>
      ) : item.kind === "authority" ? (
        <>
          <AuthorityPicker options={AUTHORITIES} value={c.authority} unsure={authorityUnsure(c)} suggested={officeSuggestion(c)} onPick={(value) => { onPick(value); dispatch(officeChoiceAction(value)); }} label={item.title} />
        </>
      ) : (
        choices.length > 0 && <Choices choices={choices} current={current} onPick={onPick} />
      )}
      {item.kind === "detail" && item.settled && !fact && <p className="cf-note">Saved as Not sure. This stays open on Review.</p>}
      {item.kind === "candidate" && !item.provision && (
        <button type="button" className="cf-link-btn cf-find" onClick={() => openDrawer({ mode: "search" })}>
          <CIcon name="search" size={13} />Find the rule in the code yourself
        </button>
      )}
      {cand?.answer === "not-sure" && item.kind === "candidate" && (
        <div className="cf-followup" role="status">
          <span className="cf-eyebrow is-plain">Open question for the officer</span>
          <p>{cand.clarifyingQuestion}</p>
          <p className="cf-faint">Not counted as a departure. It never blocks you.</p>
        </div>
      )}
      {item.kind === "authority" && current === "unsure" && <p className="cf-note"><span className="cf-dot is-warning" aria-hidden="true" />Left open · stays on your list.</p>}
      {item.kind === "authority" && <JurisdictionNote authority={c.authority} unsure={current === "unsure"} extras={extras} />}
      {cand && exitCountWarning(cand.provision, cand.topic) && <p className="cf-note"><span className="cf-dot is-warning" aria-hidden="true" />{exitCountWarning(cand.provision, cand.topic)}</p>}
      {item.kind === "fact" && item.gone && <p className="cf-note"><span className="cf-dot is-done" aria-hidden="true" />{picked === "dismiss" ? "Removed." : "Confirmed."}</p>}
    </>
  );
}

/** The assistant opened on this card: it explains; it never answers for you. */
function askAbout(item: DeckItem, n: number) {
  openAssistant(questionContext(item, n));
}

/**
 * The one help entry on a card. Routine explanation lives behind it, not under the question:
 * the reason the form asks, then the assistant on this card. Without a reason it opens the assistant.
 */
function HelpButton({ item, n, open, onToggle }: { item: DeckItem; n: number; open: boolean; onToggle: () => void }) {
  return item.why
    ? <button type="button" className="cf-link-btn cf-help-btn" aria-expanded={open} aria-controls={open ? "cf-q-why" : undefined} onClick={onToggle}><Icon24 name="spark" size={14} />Help</button>
    : <button type="button" className="cf-link-btn cf-help-btn" onClick={() => askAbout(item, n)}><Icon24 name="spark" size={14} />Help</button>;
}

function HelpPanel({ item, n }: { item: DeckItem; n: number }) {
  return (
    <div id="cf-q-why" className="cf-why">
      <p>{item.why}</p>
      <button type="button" className="cf-link-btn" onClick={() => askAbout(item, n)}><Icon24 name="spark" size={14} />Ask the assistant</button>
    </div>
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
export function CaseDeck({ focus, codeFirst }: { focus: string | null; codeFirst: boolean }) {
  const { c, engineId, gaps, dispatch, requestCheck, sectionCLookup, reading, answerPlan, answerChecklist, reloadChecklists, applicationStatus, decideRequirement, drafting } = useCase();
  const session = useSession();
  const { app, locked, readOnly } = useCurrentApplication();
  const { onAnswer, onDeparture, decisionNoteFor } = useCandidateAnswer();
  const { options: deckExtras, extras } = useDeckExtras();
  const seen = useMemo(() => new Set(session.seen), [session.seen]);
  // A keyword lead opened from the grouped triage (or a saved link) stays on the deck while you answer it.
  const [focusedCandidate, setFocusedCandidate] = useState(focus?.startsWith("cand-") ? focus : undefined);
  const [paperworkFocus, setPaperworkFocus] = useState(() => focus ? paperworkRowKey(c, focus) : null);
  useEffect(() => { if (focus) setPaperworkFocus(paperworkRowKey(c, focus)); }, [focus]);
  useEffect(() => { if (focus?.startsWith("cand-")) setFocusedCandidate(focus); }, [focus]);
  const today = toIso(todayIn(new Date()));
  const all = buildDeck(c, gaps, { ...deckExtras, seen, today, includeDone: true, identify: reading.identify, intake: reading.intake, intakeNote: reading.intakeNote, focusedCandidate: focus?.startsWith("cand-") ? focus : focusedCandidate });
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

  // New open cards join this visit's queue in journey order (code questions arriving after the check
  // land in the code section, not at the end); vanished, unseen keys leave it.
  const order = all.map((i) => i.key);
  const openKeys = all.filter((i) => !i.done && i.answerer !== "office").map((i) => i.key);
  const fresh = openKeys.filter((k) => !session.queue.includes(k));
  const sessionKey = session.queue[session.index];
  // Unreached cards keep journey order when a replan or another navigation adds a card.
  const ranked = rankAhead(session.queue, session.index, order, () => true).filter((k) => byKey.get(k)?.answerer !== "office");
  const queue = fresh.length ? mergeQueue(ranked, fresh, order) : ranked;
  const index = sessionKey !== undefined ? Math.max(queue.indexOf(sessionKey), 0) : fresh.length ? queue.indexOf(fresh[0]) : Math.min(session.index, queue.length);
  const currentKey = queue[index];
  const item = itemFor(currentKey);
  const queueSig = `${fresh.join("|")}#${session.queue.filter((k) => !byKey.has(k) && k !== currentKey).join("|")}#${ranked.join("|") === session.queue.join("|") ? "" : ranked.join("|")}`;
  useEffect(() => {
    updateSession((s) => {
      const cur = s.queue[s.index];
      const kept = rankAhead(s.queue, s.index, order, () => true).filter((k) => (byKey.has(k) || k === cur) && byKey.get(k)?.answerer !== "office");
      const next = mergeQueue(kept, fresh, order);
      return { queue: next, index: cur ? Math.max(next.indexOf(cur), 0) : fresh.length ? next.indexOf(fresh[0]) : Math.min(s.index, next.length) };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queueSig]);

  const account = useAccount();
  const savedDraft = (() => {
    if (!item) return "";
    if (item.kind === "route-detail") return String(factFor(c, "journey.departure")?.value ?? "");
    if (item.kind === "question") return c.questions.find((q) => q.id === item.ref)?.answer ?? "";
    // A confirmed saved value under any of its names wins over the description question (alias rehydration).
    if (item.kind === "storeys") return String(confirmedAnswer(c.facts, "storeys")?.value ?? c.questions.find((q) => q.id === "q-desc-storeys")?.answer ?? "");
    if ((item.kind === "plan" || item.kind === "product-scope") && item.plan) {
      const saved = factFor(c, localField(item.plan.field))?.value;
      return saved == null || typeof saved === "boolean" ? "" : String(saved);
    }
    if (item.kind === "rule-input" && item.input) {
      const saved = extras.rules ? ruleFacts(c, extras.rules.index).get(item.input.field)?.value : undefined;
      return typeof saved === "number" ? String(saved) : "";
    }
    if (item.kind === "condition") return extras.checklists?.checklists.find((x) => x.id === item.checklist)?.conditions.find((x) => x.id === item.condition)?.answer?.reason ?? "";
    return "";
  })();
  const draftAccount = account.user ? JSON.stringify([account.user.id, account.user.role, account.user.authority]) : null;
  const { value: draft, setValue: setDraft, choices: picked, setChoices: setPicked, conflict: draftConflict, confirmValue: confirmDraft } = useQuestionDraft(draftAccount, engineGeneration(), engineId, currentKey, savedDraft);
  const [why, setWhy] = useState(false);
  const [drawer, setDrawer] = useState<DrawerState | null>(null);
  const [jumpTo, setJumpTo] = useState<string | null>(null);
  const [planNotes, setPlanNotes] = useState<Record<string, string>>({});
  /** Rule and package cards: a note per card (an error, or a 409 waiting for a reload), and the card being saved. */
  const [cardNotes, setCardNotes] = useState<Record<string, string>>({});
  const [conflicted, setConflicted] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const noteFor = (key: string, text: string) => setCardNotes((n) => ({ ...n, [key]: text }));
  /** A typed planner answer was sent: move on once it is saved. */
  const [advanceAfter, setAdvanceAfter] = useState<{ key: string; generation: number } | null>(null);
  const candidateNote = item?.kind === "candidate" ? decisionNoteFor(item.ref) : "";
  useEffect(() => {
    if (candidateNote && advanceAfter) setAdvanceAfter(null);
  }, [candidateNote, advanceAfter]);
  const wrapRef = useRef<HTMLDivElement>(null);
  const formPos = currentKey ? all.findIndex((i) => i.key === currentKey) : all.length;
  const dir = useDirection(formPos < 0 ? index : formPos);
  const leaving = useLeavingCard(dir);
  // Stable, or React would detach and reattach the card on every render and replay its exit.
  const setWrap = useRef((node: HTMLDivElement | null) => { wrapRef.current = node; leaving.ref(node); }).current;

  // Help starts closed on each card; unconfirmed text stays with that application and card.
  useEffect(() => {
    setWhy(false);
  }, [currentKey]);

  // The assistant follows the open question.
  useEffect(() => {
    if (!item) {
      setAssistantContext({ screen: "question", label: "your remaining questions", suggestions: ["What happens at review?", "What is still missing?"] });
      return;
    }
    setAssistantContext(questionContext(item, (all.findIndex((i) => i.key === item.key) + 1) || index + 1));
  }, [item?.key, item?.title, item?.why, item?.provision, index]); // eslint-disable-line react-hooks/exhaustive-deps

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
    const alias = focus ? aliasKey(c, focus) : all.find((i) => (i.kind === "candidate" || i.kind === "storeys" || i.kind === "code-triage") && !i.done)?.key;
    // A link to one statement opens the review that holds all six.
    const key = alias && !byKey.has(alias) && PROCESS_FIELDS.some((p) => alias === `field-${p.id}`) && byKey.has("drafts") ? "drafts" : alias;
    if (key && byKey.has(key) && byKey.get(key)?.answerer !== "office") {
      updateSession((s) => {
        const base = s.queue.length >= queue.length ? s.queue : queue;
        const q = mergeQueue(base, [key], order);
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
      const q = mergeQueue(s.queue, [key], order);
      return { queue: q, index: q.indexOf(key) };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jumpTo, c.candidates, sectionCLookup.source]);

  // A code card the lookup replaced (article split into sentences) has nothing left to answer.
  useEffect(() => {
    if (item?.gone && (item.kind === "drafts" || item.kind === "process" || item.kind === "candidate" || item.kind === "storeys" || item.kind === "rule" || item.kind === "rule-input" || item.kind === "condition" || item.kind === "package" || item.kind === "package-end" || item.kind === "requirement")) moveFrom(index, false);
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

  // An answer moves on as soon as it renders as done, before that in-between state is painted.
  useLayoutEffect(() => {
    if (!advanceAfter) return;
    if (engineGeneration() !== advanceAfter.generation || item?.key !== advanceAfter.key) {
      setAdvanceAfter(null);
      return;
    }
    if (!item.done) return;
    setAdvanceAfter(null);
    moveFrom(index, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [item?.key, item?.done, advanceAfter]);

  // A card that takes typing gets the caret straight away; otherwise the heading (no ring) holds focus.
  useEffect(() => {
    if (item?.kind === "paperwork") return;
    const w = wrapRef.current;
    const field = w?.querySelector<HTMLElement>(".cf-q-body input.cf-uline, .cf-q-body textarea, .cf-q-body .cf-ap-input");
    (field ?? w?.querySelector<HTMLElement>("h2"))?.focus({ preventScroll: true });
  }, [currentKey]);

  /** Every answer takes one pass. Deferred answers live on the case, never in a return queue. */
  function moveFrom(from: number, markSeen: boolean) {
    const key = queue[from];
    const open = (k: string) => {
      const it = itemFor(k);
      return Boolean(k !== key && it && !it.done && it.answerer !== "office" && (it.kind === "understood" || !session.seen.includes(k)));
    };
    // New questions can arrive earlier in the journey while the current answer is being saved.
    const first = queue.findIndex(open);
    updateSession((s) => ({ queue, index: first >= 0 ? first : queue.length, seen: markSeen && key && !s.seen.includes(key) ? [...s.seen, key] : s.seen }));
  }

  /** Up/down and the footer move through the whole form in order, answered cards included. */
  const pos = currentKey ? all.findIndex((i) => i.key === currentKey) : all.length;
  function goToKey(key: string | null) {
    if (!key) return updateSession({ index: queue.length });
    if (byKey.get(key)?.answerer === "office") return;
    updateSession((s) => {
      const base = s.queue.length >= queue.length ? s.queue : queue;
      const q = mergeQueue(base, [key], order);
      return { queue: q, index: q.indexOf(key) };
    });
  }
  const step = (d: -1 | 1) => {
    const navigable = all.filter((i) => i.answerer !== "office");
    const at = currentKey ? navigable.findIndex((i) => i.key === currentKey) : navigable.length;
    const to = at + d;
    if (to < 0) return;
    goToKey(to >= navigable.length ? null : navigable[to].key);
  };

  /** A server-saved answer moves on at once; if the save fails, the card comes back with its error. */
  function advanceNow(key: string) {
    const s = getSession();
    if (s.queue[s.index] === key) moveFrom(s.index, true);
  }
  function bringBack(key: string) {
    const s = getSession();
    if (s.queue[s.index] !== key) goToKey(key);
  }

  /** The departure the card would send: the typed words when editing, otherwise the compared design. */
  function departureText(it: Shown): string {
    const cand = c.candidates.find((a) => a.id === it.ref);
    if (picked[it.key] === DEPARTURE_EDIT || !cand) return draft.trim();
    return departureComparison(c, cand, drafting).departure;
  }

  /** No words for the design yet: the card's one action opens the words to write. */
  function writesDeparture(it: Shown): boolean {
    return it.kind === "departure" && picked[it.key] !== DEPARTURE_EDIT && c.candidates.some((a) => a.id === it.ref) && !departureText(it);
  }

  /** Check whether the current answer can advance, including pending writes and required reasons. */
  function canContinue(it: Shown): boolean {
    if (locked || busyKey === it.key || advanceAfter?.key === it.key) return false;
    if (it.kind === "section-d" || it.kind === "drafts" || it.kind === "file" || it.kind === "code-run" || it.kind === "code-note" || it.kind === "code-triage" || it.kind === "code-ledger") return true;
    if (it.kind === "reading") return reading.intake !== "running";
    if (it.kind === "scope") return false;
    if (it.kind === "understood" || it.kind === "paperwork") return true;
    if (it.kind === "product-notice") return true;
    if (it.kind === "route-detail") return Boolean(draft.trim());
    if (it.kind === "plan" || it.kind === "product-scope") return reading.busy !== it.ref && (it.done || Boolean(draft.trim()));
    if (it.kind === "question") return Boolean(draft.trim()) || it.done;
    if (it.kind === "storeys") return (Number.isInteger(Number(draft)) && Number(draft) > 0) || it.done;
    if (it.kind === "departure") return busyKey !== it.key && (writesDeparture(it) || Boolean(departureText(it)));
    if (it.kind === "authority") return it.done || Boolean(c.authority);
    if (it.kind === "rule") return it.rule?.state !== "departs" || it.done || picked[it.key] === RULE_LEAVE;
    if (it.kind === "package-end") return true;
    if (it.kind === "rule-input" && it.input && (it.input.spec.type === "number" || it.input.spec.type === "int")) return it.done || Boolean(draft.trim());
    if (it.kind === "condition") return busyKey !== it.key && ((picked[it.key] ?? currentState(it)) === "does_not_apply" ? Boolean(draft.trim()) : it.done);
    // "It applies" goes on its own; "No" and "Not sure" need the applicant's reason first.
    if (it.kind === "requirement") return busyKey !== it.key && (picked[it.key] === "applies" || (Boolean(picked[it.key]) && Boolean(draft.trim())) || (it.done && !picked[it.key]));
    if (it.kind === "route" && choicesFor(it).length === 0) return true;
    return it.done;
  }

  /** Save a typed answer before advancing, or open Review when the visit has no current card. */
  function next() {
    if (!item) {
      if (!locked) void requestCheck();
      location.hash = "#/review";
      return;
    }
    if (!canContinue(item)) return;
    if (item.kind === "understood") {
      dispatch({ type: "confirmFacts", ids: item.ids ?? [] });
      // A site read from labelled text is already confirmed, so confirmFacts never sees it. Acknowledging
      // the rows still proposes the office it names; the office card then only asks to confirm it.
      const office = !c.authority && item.rows?.some((r) => r.field === "municipality" || r.field === "municipalAddress") ? officeSuggestion(c) : null;
      if (office && AUTHORITIES.some((a) => a.id === office.id)) dispatch({ type: "setAuthority", authority: office.id as typeof c.authority });
      dispatch(journeyAnswerAction({ ...item, key: item.acknowledgementKey ?? item.key }, "acknowledged"));
      setAdvanceAfter({ key: item.key, generation: engineGeneration() });
      return;
    }
    if (item.kind === "paperwork") {
      wrapRef.current?.querySelector<HTMLFormElement>("form.cf-paperwork")?.requestSubmit();
      return;
    }
    if (item.kind === "route" && choicesFor(item).length === 0) {
      if (routeChoice(c) !== "variance") dispatch({ type: "setDetail", field: "journey.route", value: "variance", section: "B" });
      if (item.done) moveFrom(index, true);
      else setAdvanceAfter({ key: item.key, generation: engineGeneration() });
      return;
    }
    if (item.kind === "route-detail") {
      dispatch({ type: "setDetail", field: "journey.departure", value: draft.trim(), section: "B" });
      dispatch({ type: "setDetail", field: "alternative", value: draft.trim(), section: "B" });
      dispatch({ type: "setDetail", field: "journey.route", value: "variance", section: "B" });
      setAdvanceAfter({ key: item.key, generation: engineGeneration() });
      return;
    }
    if (writesDeparture(item)) { pick(DEPARTURE_EDIT); return; }
    if (item.kind === "departure") {
      const cand = c.candidates.find((a) => a.id === item.ref);
      const text = departureText(item);
      if (!cand || !text) return;
      const key = item.key;
      // The engine refuses these words; the applicant rewords them here instead of meeting a refusal.
      if (CLAIM_WORDS.test(text)) {
        if (picked[key] !== DEPARTURE_EDIT) { setPicked((p) => ({ ...p, [key]: DEPARTURE_EDIT })); setDraft(text); }
        noteFor(key, CLAIM_NOTE);
        return;
      }
      const variance = departureRecordsVariance(c);
      setBusyKey(key);
      noteFor(key, "");
      void onDeparture(cand, text).then((error) => {
        setBusyKey((k) => (k === key ? null : k));
        if (error) {
          // A refusal (for example wording the server will not record) opens the words to edit.
          if (picked[key] !== DEPARTURE_EDIT) { setPicked((p) => ({ ...p, [key]: DEPARTURE_EDIT })); setDraft(text); }
          noteFor(key, error);
          return;
        }
        if (variance) dispatch({ type: "setDetail", field: "journey.route", value: "variance", section: "B" });
        setDraft("");
        setAdvanceAfter({ key, generation: engineGeneration() });
      });
      return;
    }
    if ((item.kind === "plan" || item.kind === "product-scope") && item.plan && draft.trim() && planInput(item.plan.field).kind !== "choices") {
      const typed = draft.trim();
      const saved = factFor(c, localField(item.plan.field))?.value;
      if (!item.done || String(saved ?? "") !== typed) {
        sendPlan(item, typed, true);
        return;
      }
    }
    if (item.kind === "rule-input" && item.input && draft.trim() && (item.input.spec.type === "number" || item.input.spec.type === "int")) {
      const unit = metricUnit(item.input.spec.unit);
      const measured = unit ? parseMeasurement(draft, unit) : null;
      if (measured?.kind === "error") return noteFor(item.key, measured.error);
      const got = readNumber(item.input.spec, measured?.kind === "value" ? String(measured.value) : draft);
      if ("error" in got) return noteFor(item.key, got.error);
      dispatch(clearJourneyAnswerAction(item));
      noteFor(item.key, "");
      const saved = extras.rules ? ruleFacts(c, extras.rules.index).get(item.input.field)?.value : undefined;
      if (!item.done || saved !== got.value) {
        dispatch({ type: "setRuleInput", field: item.input.field, value: got.value, rule: item.input.rule, quote: unit ? measurementText(draft, unit) : draft.trim() });
        confirmDraft(draft);
        // Move on once the new value has rendered, so a question it opens comes next, not at the end.
        if (!item.done) {
          setAdvanceAfter({ key: item.key, generation: engineGeneration() });
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
    if (item.kind === "requirement" && (picked[item.key] === "does-not-apply" || picked[item.key] === "not-sure")) {
      sendRequirement(item, picked[item.key] as RequirementAnswer, draft.trim(), true);
      return;
    }
    if (item.kind === "question" && draft.trim()) { dispatch({ type: "answerQuestion", id: item.ref, answer: draft.trim() }); confirmDraft(draft); }
    if (item.kind === "storeys" && Number(draft) > 0) { dispatch({ type: "setStoreyCount", value: draft }); confirmDraft(draft); }
    dispatch(clearJourneyAnswerAction(item));
    moveFrom(index, true);
  }

  function deferCurrent(value: "not_sure" | "designer" | "later") {
    if (!item || locked) return;
    if (item.plan) { sendPlan(item, NOT_SURE, true, value); return; }
    if (item.kind === "candidate") {
      const cand = c.candidates.find((a) => a.id === item.ref);
      if (cand) onAnswer(cand, "not-sure");
    } else if (item.kind === "storeys") {
      dispatch({ type: "setStoreyCount", value: "" });
    } else if (item.kind === "question") {
      dispatch({ type: "answerQuestion", id: item.ref, answer: "" });
    } else if (item.kind === "rule-input" && item.input) {
      dispatch({ type: "setRuleInput", field: item.input.field, value: null, rule: item.input.rule, quote: "" });
    } else if (item.kind === "condition") {
      sendCondition(item, "not_yet", "", true, value);
      return;
    } else if (item.kind === "detail") {
      dispatch({ type: "setDetail", field: item.ref, value: "", section: item.section });
    } else if (item.kind === "authority" && value === "not_sure") {
      dispatch({ type: "setAuthority", authority: "" });
    }
    dispatch(journeyAnswerAction(item, value));
    setAdvanceAfter({ key: item.key, generation: engineGeneration() });
  }

  /** One planner answer to the intake answers route; a typed answer moves on once saved. */
  function sendPlan(it: Shown, answer: string, advance: boolean, deferred?: "not_sure" | "designer" | "later") {
    if (!it.plan) return;
    const key = it.key;
    setPlanNotes((n) => ({ ...n, [key]: "" }));
    const parsed = answer === NOT_SURE ? null : planFactAnswer(it.plan.field, answer);
    if (parsed && "error" in parsed) return setPlanNotes((n) => ({ ...n, [key]: parsed.error }));
    if (parsed) {
      dispatch({ type: "setRuleInput", field: localField(it.plan.field), value: parsed.value, quote: parsed.quote, rule: "intake" });
      confirmDraft(answer);
      if (advance) setAdvanceAfter({ key, generation: engineGeneration() });
      return;
    }
    const generation = engineGeneration();
    if (advance) advanceNow(key);
    void answerPlan(it.plan, answer).then((error) => {
      if (engineGeneration() !== generation) return;
      if (error) {
        setAdvanceAfter(null);
        setPlanNotes((n) => ({ ...n, [key]: error }));
        if (advance) bringBack(key);
      } else {
        dispatch(deferred ? journeyAnswerAction(it, deferred) : clearJourneyAnswerAction(it));
        confirmDraft(answer);
      }
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
  function sendCondition(it: Shown, state: "confirmed" | "not_yet" | "does_not_apply", reason: string, advance: boolean, deferred?: "not_sure" | "designer" | "later") {
    const cl = extras.checklists?.checklists.find((x) => x.id === it.checklist);
    const row = conditionOf(it);
    if (!cl || !row) return;
    const key = it.key;
    noteFor(key, "");
    setBusyKey(key);
    // The case this answer belongs to: a switch to another application stops the sibling answers and the UI update.
    const startCase = getExtras().caseId;
    const sameCase = () => getExtras().caseId === startCase;
    if (advance) advanceNow(key);
    void (async () => {
      let error = await answerChecklist(cl.id, row.id, state, reason);
      if (!error && state === "confirmed") {
        for (const other of otherOptions(cl, row)) {
          if (!sameCase()) return;
          error = await answerChecklist(cl.id, other.id, "does_not_apply", `Another option of this choice is followed instead (${row.option ?? row.source.label ?? "the confirmed option"}).`);
          if (error) break;
        }
      }
      if (!sameCase()) return;
      setBusyKey((k) => (k === key ? null : k));
      if (error) {
        // Nothing was saved: the choice goes back to the saved answer.
        setPicked((p) => { const { [key]: _drop, ...rest } = p; return rest; });
        noteFor(key, error);
        setConflicted(error === CONFLICT_TEXT ? key : null);
        if (advance) bringBack(key);
        return;
      }
      setConflicted(null);
      dispatch(deferred ? journeyAnswerAction(it, deferred) : clearJourneyAnswerAction(it));
    })();
  }

  /**
   * One requirement-ledger answer: applicability only. "It applies" sends the acknowledgement itself;
   * the other two need the applicant's reason, so OK sends those. A departure is asked afterwards on
   * its own code card, never here.
   */
  function sendRequirement(it: Shown, answer: RequirementAnswer, reason: string, advance: boolean) {
    const record = it.requirement;
    if (!record) return;
    const key = it.key;
    noteFor(key, "");
    setBusyKey(key);
    // The case this answer belongs to: a switch to another application stops the UI update.
    const startCase = getExtras().caseId;
    const sameCase = () => getExtras().caseId === startCase;
    if (advance) advanceNow(key);
    void decideRequirement(record, answer, reason).then((error) => {
      if (!sameCase()) return;
      setBusyKey((k) => (k === key ? null : k));
      if (error) {
        // Nothing was saved: the choice goes back to unanswered so it can be sent again.
        setPicked((p) => { const { [key]: _drop, ...rest } = p; return rest; });
        noteFor(key, error);
        setConflicted(error === CONFLICT_TEXT ? key : null);
        if (advance) bringBack(key);
        return;
      }
      setConflicted(null);
      confirmDraft(reason);
    });
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
    if (!item || locked || busyKey === item.key || reading.busy === item.ref || advanceAfter?.key === item.key) return;
    if (value === "not_sure" || value === "unsure" || (value === "designer" && item.kind !== "role") || value === "later" || value === NOT_SURE_RULE) { deferCurrent(value === "designer" ? "designer" : value === "later" ? "later" : "not_sure"); return; }
    if (item.kind === "departure") {
      if (value === DEPARTURE_EDIT && !draft.trim()) setDraft(departureText(item));
      setPicked((p) => ({ ...p, [item.key]: value }));
      return;
    }
    if (!item.plan && item.kind !== "condition") dispatch(clearJourneyAnswerAction(item));
    const advance = () => setAdvanceAfter({ key: item.key, generation: engineGeneration() });
    if (item.kind === "route") {
      dispatch({ type: "setDetail", field: "journey.route", value, section: "B" });
      // Something is different opens its one text question immediately.
      advance();
      return;
    }
    if (item.kind === "role") {
      dispatch({ type: "setDetail", field: "applicant_role", value, section: "A" });
      advance(); return;
    }
    if (item.kind === "rule-input" && item.input) {
      const { field, rule, spec } = item.input;
      setPicked((p) => ({ ...p, [item.key]: value }));
      const publicWay = field === "faces_public_way" ? planFactAnswer(field, value) : null;
      dispatch({ type: "setRuleInput", field, value: publicWay && "value" in publicWay ? publicWay.value : choiceValue(spec, value), rule, quote: publicWay && "quote" in publicWay ? publicWay.quote : choicesFor(item).find((x) => x.value === value)?.label ?? value });
      advance();
      return;
    }
    if (item.kind === "rule") {
      setPicked((p) => ({ ...p, [item.key]: value }));
      if (value === RULE_ADD) void addRule(item);
      else if (value === RULE_LEAVE) { dispatch({ type: "setDetail", field: `journey.rule.${item.ref}`, value, section: "C" }); updateSession((s) => ({ seen: s.seen.includes(item.key) ? s.seen : [...s.seen, item.key] })); advance(); }
      return;
    }
    if (item.kind === "package" && item.checklist) {
      const id = item.checklist;
      dispatch({ type: "setDetail", field: `journey.package.${id}`, value, section: "C" });
      updateSession((s) => ({ packages: { ...s.packages, [id]: value as "yes" | "no" } }));
      advance();
      return;
    }
    if (item.kind === "condition") {
      setPicked((p) => ({ ...p, [item.key]: value }));
      if (value === "does_not_apply") return; // the reason comes first; OK sends it
      sendCondition(item, value as "confirmed" | "not_yet", "", true);
      return;
    }
    if (item.kind === "requirement") {
      setPicked((p) => ({ ...p, [item.key]: value }));
      // "It applies" is its own acknowledgement; the other two need a reason before OK sends them.
      if (value === "applies") sendRequirement(item, "applies", "", true);
      return;
    }
    setPicked((p) => ({ ...p, [item.key]: value }));
    if (item.kind === "plan" || item.kind === "product-scope") { sendPlan(item, value, true); return; }
    else if (item.kind === "fact") {
      // An answered card changes the value it left: Not right marks the confirmed value, Yes restores what was read.
      const field = c.intake?.facts.find((f) => f.id === item.ref)?.field;
      const latest = item.done && field ? factFor(c, field) : undefined;
      if (value === "dismiss" && latest && latest.source.ref !== NOT_RIGHT) dispatch({ type: "rejectFacts", ids: [latest.id] });
      else dispatch({ type: value === "confirm" ? "confirmFacts" : "rejectFacts", ids: item.ids ?? [item.ref] });
    }
    else if (item.kind === "authority") {
      dispatch({ type: "setAuthority", authority: value === "unsure" ? "" : (value as typeof c.authority) });
    } else if (item.kind === "candidate") {
      const cand = c.candidates.find((a) => a.id === item.ref);
      if (cand) {
        const key = item.key;
        onAnswer(cand, value as "yes" | "no" | "not-sure", () => bringBack(key));
        advanceNow(key);
        return;
      }
    } else if (item.kind === "detail" && item.suggestedValue) {
      if (value === "edit-suggested") return;
      dispatch({ type: "setDetail", field: item.ref, value: item.suggestedValue, section: item.section });
    } else if (item.kind === "detail" && item.confirmLabels) {
      const saved = valueText(factFor(c, item.ref));
      if (value === "confirm") dispatch({ type: "setDetail", field: item.ref, value: c.description.trim(), section: "B" });
      else if (alternativeChoice(c.description, saved) === "confirm") dispatch({ type: "setDetail", field: item.ref, value: "", section: "B" });
    } else if (item.kind === "detail") {
      const def = DETAIL_FIELDS.find((d) => d.id === item.ref);
      if (def) dispatch({ type: "setDetail", field: def.id, value, section: def.section });
    }
    if (!(item.kind === "detail" && item.confirmLabels && value === "dismiss")) advance();
  }

  const keyHandler = useRef<(e: KeyboardEvent) => void>(() => {});
  keyHandler.current = (e: KeyboardEvent) => {
    if (drawer || e.defaultPrevented || document.querySelector("dialog[open]")) return;
    const t = e.target as HTMLElement | null;
    // Keys typed in the menu, a popover, the assistant or any dialog belong to them.
    if (t?.closest?.(".cf-pop, dialog, [role='menu'], .cf-palette, .cf-assist, .cf-document-review, .cf-understood, .cf-paperwork, .cf-statements")) return;
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
  // Counted from the derived deck: an answered card waiting on the officer (or on a fresh check) is not "left".

  const typed = Boolean(item && (item.kind === "condition" ? (picked[item.key] ?? currentState(item)) === "does_not_apply" : multiline(item)));
  const status = readOnlyStatus(app?.status ?? applicationStatus, app?.authority ?? c.authority);

  return (
    <div className="cf-deck-page">
      {/* The check state lives on Review and in the header; the deck stays quiet. */}
      {readOnly && (
        <div className="cf-deck-status" role="status">
          <span className={`cf-dot is-${status.tone}`} aria-hidden="true" />{status.heading}. {status.note}
        </div>
      )}
      <DocumentReview intake={c.intake} files={c.files} description={c.description} intakeStatus={reading.intake} />
      <PictureConsent />
      <div ref={leaving.stage} className={`cf-q-stage${item?.kind === "paperwork" ? " is-paperwork" : ""}`}>
        {/* A submission on its way only pauses the mounted card (App's edit lock); a sent one is read-only. */}
        {readOnly ? (
          <div className="cf-q-wrap" aria-labelledby="cf-q" role="group">
            <h2 id="cf-q" className="cf-q-text" tabIndex={-1}>Your saved answers are read-only.</h2>
            <p className="cf-q-help">Review the saved application, check its administrative completeness or download a record.</p>
            <div className="cf-row-actions">
              <a className="cf-btn is-primary" href="#/application">View saved application</a>
              <a className="cf-btn" href="#/review">Review completeness</a>
            </div>
          </div>
        ) : item?.kind === "scope" && !item.gone ? (
          <RedirectPage />
        ) : item ? (
          <div ref={setWrap} key={item.key} data-advancing={advanceAfter?.key === item.key ? "" : undefined} className={`cf-q-wrap is-from-${dir}${item.kind === "section-d" || item.kind === "drafts" || item.kind === "code-triage" || item.kind === "paperwork" ? " is-wide" : ""}`} aria-labelledby="cf-q" role="group">
            <h2 id="cf-q" className="cf-q-text" tabIndex={-1}>{item.title}</h2>
            {item.plan?.kind === "conflict" && <span className="cf-answerer-tag">You wrote two things</span>}
            {item.answerer === "designer" && <span className="cf-answerer-tag"><Icon24 name="compose" size={15} />Usually your designer knows</span>}
            {(item.context || item.quote) && (
              <p className="cf-q-help">
                {item.context}
                {item.quote && <> <q>{item.quote}</q></>}
              </p>
            )}
            <fieldset className="cf-q-body" disabled={locked || busyKey === item.key || reading.busy === item.ref || advanceAfter?.key === item.key} data-busy={!locked && (busyKey === item.key || reading.busy === item.ref || advanceAfter?.key === item.key) ? "" : undefined}>
              <legend className="cf-sr">Your answer</legend>
              <CardBody
                item={item}
                picked={picked[item.key]}
                onPick={pick}
                draft={draft}
                setDraft={setDraft}
                openDrawer={setDrawer}
                planNote={planNotes[item.key] ?? ""}
                extras={extras}
                focusRow={paperworkFocus}
                onPaperworkDone={() => moveFrom(index, true)}
                note={cardNotes[item.key] ?? ""}
                busy={busyKey === item.key}
                onReload={conflicted === item.key ? () => void reloadChecklists().then((e) => { noteFor(item.key, e ?? ""); if (!e) setConflicted(null); }) : undefined}
                position={item.kind === "condition" ? (extras.checklists?.checklists.find((x) => x.id === item.checklist)?.conditions.findIndex((x) => x.id === item.condition) ?? 0) + 1 : 0}
              />
            </fieldset>
            {item.deferred && item.kind !== "plan" && item.kind !== "product-scope" && item.kind !== "rule-input" && <p className="cf-note" role="status">{item.deferred === "later" ? "Saved for later" : item.deferred === "designer" ? "For your designer" : "Not sure"} · open on Review</p>}
            {draftConflict && <p className="cf-note" role="status">The saved answer changed. Your unfinished text is kept here; review it before confirming.</p>}
            {item.kind === "candidate" && decisionNoteFor(item.ref) && <p className="cf-note">{decisionNoteFor(item.ref)}</p>}
            {item.section === "C" && (extras.failed.rules || extras.failed.case) && (
              <p className="cf-note" role="status"><span className="cf-dot is-warning" aria-hidden="true" />Rule checks didn’t load, so some rule questions may be missing. <button type="button" className="cf-link-btn" onClick={retryExtras}>Try again</button></p>
            )}
            <OkRow label={item.kind === "understood" ? "Looks right" : item.kind === "departure" && picked[item.key] !== DEPARTURE_EDIT ? (writesDeparture(item) ? "Write it" : "Confirm") : "Continue"} primary={item.kind !== "paperwork" && (choicesFor(item).length === 0 || (item.done && !item.deferred) || item.kind === "authority" || (item.kind === "detail" && (picked[item.key] === "dismiss" || picked[item.key] === "edit-suggested")) || (item.kind === "condition" && (picked[item.key] ?? currentState(item)) === "does_not_apply") || (item.kind === "requirement" && (picked[item.key] === "does-not-apply" || picked[item.key] === "not-sure")))} quiet={item.kind === "drafts" && !item.done} disabled={!canContinue(item)} onOk={next} typed={typed}>
              <span className="cf-ok-more">
                {deferralFor(item) && choicesFor(item).length === 0 && item.kind !== "authority" && <button type="button" className="cf-link-btn" disabled={locked || reading.busy === item.ref || busyKey === item.key} onClick={() => { const choice = deferralFor(item); if (choice) deferCurrent(choice.value); }}>{deferralFor(item)?.label}</button>}
                <HelpButton item={item} n={n} open={why} onToggle={() => setWhy((v) => !v)} />
              </span>
            </OkRow>
            {why && item.why && <HelpPanel item={item} n={n} />}
          </div>
        ) : (
          <div ref={setWrap} key="finish" className={`cf-q-wrap is-from-${dir}`} aria-labelledby="cf-q" role="group">
            <JourneyEnd items={all} standard={routeChoice(c) === "standard"} product={productScope(c) === "product_acceptance"} onJump={goToKey} onReview={next} />
          </div>
        )}
      </div>
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
