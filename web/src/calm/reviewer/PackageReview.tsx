/**
 * The package review, one thing at a time, in at most four steps: what changed (from version 2),
 * an overview, everything that's missing, and the checks behind it (documents, code, the Division C
 * file list, the peer-review signal), each folded until asked for. The caller adds the last step
 * (the decision). Every value comes from the ReviewSession; nothing here judges the design.
 */
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { StageButton } from "../shell/AppHeader";
import type { ReviewSession, SessionSummary } from "../../api/types.gen";
import { AcIcon, type AcIconName } from "../auth/bits";
import { sentLabel } from "./queue";
import { CodeRef } from "./CodeRef";
import {
  citationView,
  diffView,
  documentView,
  fileItemsView,
  missingView,
  peerView,
  sectionCView,
  summaryView,
  type CheckRow,
  type FindingView,
  type Tone,
} from "./packageView";
import "./review.css";

export type StepId = "changes" | "summary" | "missing" | "checks";

const STEP_LABEL: Record<StepId, string> = {
  changes: "Changes",
  summary: "Request",
  missing: "Missing",
  checks: "Checks",
};

/** Each step's icon. The hue is kept for callers; the review itself draws in ink (monotone). */
export const STEP_LOOK: Record<StepId | "final", { hue: string; icon: AcIconName }> = {
  changes: { hue: "slate", icon: "history" },
  summary: { hue: "blue", icon: "doc" },
  missing: { hue: "rose", icon: "alert" },
  checks: { hue: "violet", icon: "list" },
  final: { hue: "green", icon: "scale" },
};

/** A step's heading: its icon, the task in a few words and an optional count. */
export function StepTitle({ step, children, count, icon }: { step: StepId | "final"; children: ReactNode; count?: number; icon?: AcIconName }) {
  const look = STEP_LOOK[step];
  return (
    <h2 className="pr-title pr-title-row">
      <span className={`pr-ico is-${look.hue}`} aria-hidden="true"><AcIcon name={icon ?? look.icon} size={18} /></span>
      <span>{children}</span>
      {count ? <span className={`pr-count-pill is-${look.hue}`}>{count}</span> : null}
    </h2>
  );
}


export function stepsFor(s: ReviewSession): StepId[] {
  return [...(s.diff ? (["changes"] as StepId[]) : []), "summary", "missing", "checks"];
}

export const Dot = ({ tone }: { tone: Tone }) => <span className={`cf-dot is-${tone}`} aria-hidden="true" />;
const TONE_WORD: Record<Tone, string> = { blocking: "required", warning: "check", pending: "not established", done: "no gap" };

function FindingItem({ f }: { f: FindingView }) {
  return (
    <li className="pr-item">
      <Dot tone={f.tone} />
      <details className="pr-item-body pr-fold">
        <summary className="pr-item-title">{f.title}<span className="cf-sr"> ({TONE_WORD[f.tone]})</span></summary>
        <p className="pr-item-msg">{f.message}</p>
        {f.where && <p className="pr-item-meta">{f.where}</p>}
        {f.quote && <p className="pr-src"><q>{f.quote}</q></p>}
        {f.citations.length > 0 && <div className="pr-cites">{f.citations.map((c) => <CodeRef key={c} citation={c} />)}</div>}
      </details>
    </li>
  );
}

function Check({ r }: { r: CheckRow }) {
  return (
    <li className="pr-item">
      <Dot tone={r.tone} />
      <details className="pr-item-body pr-fold">
        <summary className="pr-item-title">{r.label}<span className="pr-where">{r.status}</span></summary>
        <p className="pr-item-meta"><span className="pr-mono">Div C {r.provision}</span></p>
        {r.message && <p className="pr-item-msg">{r.message}</p>}
      </details>
    </li>
  );
}

function Changes({ s }: { s: ReviewSession }) {
  const d = diffView(s)!;
  const list = (title: string, items: FindingView[], empty: string) => (
    <section className="pr-group" aria-label={title}>
      <h3 className="pr-group-h">{title} <span className="pr-n">{items.length}</span></h3>
      {items.length ? <ul className="pr-list">{items.map((f) => <FindingItem key={f.key} f={f} />)}</ul> : <p className="pr-faint">{empty}</p>}
    </section>
  );
  return (
    <>
      <StepTitle step="changes">See what changed</StepTitle>
      <p className="pr-lede">{d.statement} · since version {d.from}</p>
      <div className="pr-meter" role="img" aria-label={`${Math.round(d.ratio * 100)}% of the earlier gaps resolved`}>
        <span style={{ width: `${Math.round(d.ratio * 100)}%` }} />
      </div>
      {list("Resolved", d.resolved, "Nothing from the last version was resolved.")}
      {list("Still open", d.stillOpen, "Nothing from the last version is still open.")}
      {list("New", d.added, "No new gaps.")}
    </>
  );
}

function Summary({ s }: { s: ReviewSession }) {
  const v = summaryView(s);
  return (
    <>
      <StepTitle step="summary">Read the request</StepTitle>
      <p className="pr-lede">{v.headline}</p>
      {v.proposal ? (
        <figure className="pr-quote">
          <blockquote>{v.proposal}</blockquote>
          <figcaption>Their proposal{v.proposalWhere ? ` · ${v.proposalWhere}` : ""}</figcaption>
        </figure>
      ) : (
        <p className="pr-item-msg"><Dot tone="blocking" /> No proposal found</p>
      )}
      <ul className="pr-metrics" aria-label="What the review found">
        <li><Dot tone={v.toAsk ? "blocking" : "done"} /><b>{v.toAsk}</b><span>to ask for</span></li>
        <li><Dot tone={v.toCheck ? "warning" : "done"} /><b>{v.toCheck}</b><span>for you to check</span></li>
        <li title={[v.blank ? `${v.blank} blank` : "", v.notFound ? `${v.notFound} not found` : ""].filter(Boolean).join(" · ") || undefined}><Dot tone="done" /><b>{v.present}</b><span>found</span></li>
      </ul>
      <dl className="pr-facts">
        <dt><AcIcon name="book" size={14} />Code</dt>
        <dd>{v.provisions.length ? v.provisions.map((p) => <span key={p} className="pr-mono pr-pill">{p}</span>) : <span className="pr-faint">None cited</span>}</dd>
        <dt><AcIcon name="files" size={14} />Documents</dt>
        <dd>{v.documents.length ? <ul className="pr-plain">{v.documents.map((d, i) => <li key={i}>{d}</li>)}</ul> : <span className="pr-faint">None</span>}</dd>
      </dl>
      {v.peer && <p className="pr-note"><Dot tone="warning" /> Peer review may help · see Checks</p>}
    </>
  );
}

function Missing({ s }: { s: ReviewSession }) {
  const v = missingView(s);
  if (!v.total) return <StepTitle step="missing" icon="check">Nothing is missing</StepTitle>;
  return (
    <>
      <StepTitle step="missing" count={v.total}>What to ask for</StepTitle>
      {v.groups.map((g) => (
        <section key={g.section} className="pr-group" aria-label={g.label}>
          <h3 className="pr-group-h pr-sec">
            <span className="pr-sec-badge" aria-hidden="true">{g.section === "process" ? "D" : g.section}</span>
            {g.label.replace(/^Section [A-D] · /, "")} <span className="pr-n">{g.items.length}</span>
          </h3>
          <ul className="pr-list">{g.items.map((f) => <FindingItem key={f.key} f={f} />)}</ul>
        </section>
      ))}
      {v.officer.length > 0 && (
        <section className="pr-group" aria-label="For you to check first">
          <h3 className="pr-group-h"><AcIcon name="eye" size={14} />For you to check <span className="pr-n">{v.officer.length}</span></h3>
          <ul className="pr-list">{v.officer.map((f) => <FindingItem key={f.key} f={f} />)}</ul>
        </section>
      )}
    </>
  );
}

function Documents({ s }: { s: ReviewSession }) {
  if (!s.documents.length) return <p className="pr-faint">No documents were read.</p>;
  return (
    <>
      <ul className="pr-docs">
        {s.documents.map((d) => {
          const v = documentView(d);
          return (
            <li key={d.id} className="pr-doc">
              <p className="pr-doc-title">{v.title}</p>
              <p className="pr-faint pr-doc-note">{v.file && v.file.endsWith(".pdf") ? `${v.file} · ` : ""}{v.note}</p>
              <dl className="pr-props">
                {v.cells.map((c) => (
                  <div key={c.label}>
                    <dt>{c.label}</dt>
                    <dd className={c.known ? "" : "is-unknown"}>
                      {c.value}
                      {c.where && <small>{c.where}</small>}
                    </dd>
                  </div>
                ))}
              </dl>
            </li>
          );
        })}
      </ul>
      <p className="pr-fine">Seals are read from text, never verified.</p>
    </>
  );
}

function CodeChecks({ s }: { s: ReviewSession }) {
  return (
    <>
      <p className="pr-faint pr-small">NBC(AE) 2023, 2nd printing</p>
      {s.lookup_skipped && <p className="pr-note"><Dot tone="pending" /> The code lookup wasn’t available, so citations were not checked.</p>}
      <section className="pr-group" aria-label="Citations">
        <h3 className="pr-group-h">Cited provisions <span className="pr-n">{s.citations.length}</span></h3>
        {s.citations.length ? (
          <ul className="pr-list">
            {s.citations.map((c, i) => {
              const v = citationView(c);
              return (
                <li key={`${c.text}-${i}`} className="pr-item">
                  <Dot tone={v.tone} />
                  <div className="pr-item-body">
                    <p className="pr-item-title"><span className="pr-mono">{v.id}</span></p>
                    <p className="pr-item-meta">{v.status}</p>
                    {v.issues.map((m) => <p key={m} className="pr-item-msg">{m}</p>)}
                    {c.canonical_citation && <div className="pr-cites"><CodeRef citation={c.canonical_citation} /></div>}
                  </div>
                </li>
              );
            })}
          </ul>
        ) : <p className="pr-faint">No provision is cited.</p>}
      </section>
      <section className="pr-group" aria-label="Section C rows">
        <h3 className="pr-group-h">Objectives and functions · Section C <span className="pr-n">{s.section_c.length}</span></h3>
        {s.section_c.length ? (
          <ul className="pr-list">
            {s.section_c.map((r) => {
              const v = sectionCView(r);
              return (
                <li key={r.row} className="pr-item">
                  <Dot tone={v.tone} />
                  <div className="pr-item-body">
                    <p className="pr-item-title">Row {v.row} · <span className="pr-mono">{v.id}</span></p>
                    <p className="pr-item-meta">{v.status}</p>
                    <dl className="pr-props is-two">
                      <div><dt>On the form</dt><dd className="pr-mono">{v.form}</dd></div>
                      <div><dt>In the table</dt><dd className="pr-mono">{v.table}</dd></div>
                    </dl>
                    {r.status !== "match" && <p className="pr-item-msg">{v.message}</p>}
                  </div>
                </li>
              );
            })}
          </ul>
        ) : <p className="pr-faint">No Section C rows were read.</p>}
      </section>
    </>
  );
}

function FileItems({ s }: { s: ReviewSession }) {
  const v = fileItemsView(s);
  return (
    <>
      <p className="pr-faint pr-small">Division C, 2.3.1.1 · present or not, never “enough”</p>
      <section className="pr-group" aria-label="Division C file items">
        <h3 className="pr-group-h">In the documentation</h3>
        <ul className="pr-list">{v.items.map((r) => <Check key={r.key} r={r} />)}</ul>
      </section>
      <section className="pr-group" aria-label="Demonstrate, don't assert">
        <h3 className="pr-group-h">When things fail</h3>
        <ul className="pr-list">{v.demonstrate.map((r) => <Check key={r.key} r={r} />)}</ul>
      </section>
    </>
  );
}

function Peer({ s }: { s: ReviewSession }) {
  const v = peerView(s);
  return (
    <>
      {v.signal ? (
        <ul className="pr-list">
          {v.reasons.map((r) => (
            <li key={r} className="pr-item"><Dot tone="warning" /><div className="pr-item-body"><p className="pr-item-title">{r}</p></div></li>
          ))}
        </ul>
      ) : <p className="pr-faint">No signal.</p>}
      <p className="pr-fine">Your call · not a finding about the design</p>
    </>
  );
}

/** One folded check: icon, name and a status chip; the detail opens in place. */
function Panel({ icon, title, chip, tone, children, group }: { icon: AcIconName; title: string; chip: string; tone: Tone; children: ReactNode; group: string }) {
  return (
    <details className="pr-panel" name={group}>
      <summary>
        <span className="pr-ico" aria-hidden="true"><AcIcon name={icon} size={18} /></span>
        <span className="pr-panel-t">{title}</span>
        <span className={`pr-panel-chip is-${tone}`}><Dot tone={tone} />{chip}</span>
        <span className="pr-panel-chev" aria-hidden="true"><AcIcon name="chev" size={16} /></span>
      </summary>
      <div className="pr-panel-body">{children}</div>
    </details>
  );
}

const worst = (tones: Tone[]): Tone => (["blocking", "warning", "pending"] as Tone[]).find((t) => tones.includes(t)) ?? "done";

/** Everything behind the list of what's missing, folded: open one when you need it. */
function Checks({ s }: { s: ReviewSession }) {
  const group = useId();
  const code = [...s.citations.map((c) => citationView(c).tone), ...s.section_c.map((r) => sectionCView(r).tone)];
  const codeOpen = code.filter((t) => t !== "done").length;
  const file = fileItemsView(s);
  const fileTones = [...file.items, ...file.demonstrate].map((r) => r.tone);
  const fileOpen = fileTones.filter((t) => t !== "done").length;
  const peer = peerView(s);
  return (
    <>
      <StepTitle step="checks">Look over the checks</StepTitle>
      <div className="pr-panels">
        <Panel group={group} icon="files" title="Documents" tone={s.documents.length ? "done" : "pending"} chip={s.documents.length ? String(s.documents.length) : "None"}>
          <Documents s={s} />
        </Panel>
        <Panel group={group} icon="book" title="Code references" tone={s.lookup_skipped ? "pending" : code.length ? worst(code) : "pending"}
          chip={s.lookup_skipped ? "Not looked up" : !s.citations.length ? "None cited" : codeOpen ? `${codeOpen} to look at` : "All found"}>
          <CodeChecks s={s} />
        </Panel>
        <Panel group={group} icon="clipboard" title="File checklist" tone={worst(fileTones)} chip={!file.read ? "Not checked" : fileOpen ? `${fileOpen} open` : "No gaps"}>
          <FileItems s={s} />
        </Panel>
        <Panel group={group} icon="users" title="Peer review" tone={peer.signal ? "warning" : "done"} chip={peer.signal ? "May help" : "No signal"}>
          <Peer s={s} />
        </Panel>
      </div>
    </>
  );
}

/** A last step after the checks (the decision, the close-out or the outcome), drawn by the caller. */
export interface FinalStep {
  label: string;
  content: ReactNode;
}

type Step = StepId | "final";

/**
 * The steps as the shell's stage buttons (the applicant's Describe · Questions · Review · Application
 * look): the current step's icon and one-word name, the others icons only, a check once passed, the
 * open count as a quiet number. Every name is the accessible name and a label on hover or focus.
 */
export function StepTabs({ steps, active, label, counts, onPick }: { steps: Step[]; active: Step; label: (s: Step) => string; counts: Partial<Record<Step, number>>; onPick: (s: Step) => void }) {
  const at = steps.indexOf(active);
  return (
    <nav className="cf-stages rv-steps" aria-label="Review steps">
      {steps.map((s, i) => {
        const past = i < at;
        const n = counts[s] ?? 0;
        return (
          <StageButton
            key={s}
            id={`rv-${s}`}
            label={label(s)}
            ariaLabel={`Step ${i + 1} of ${steps.length}: ${label(s)}${past ? ", done" : ""}${n ? `, ${n} to look at` : ""}`}
            icon={<AcIcon name={STEP_LOOK[s].icon} size={16} />}
            pct={past || s === active ? 100 : 0}
            current={s === active}
            done={past}
            count={past ? 0 : n}
            note={n && !past ? `${n} to look at` : undefined}
            onClick={() => onPick(s)}
          />
        );
      })}
    </nav>
  );
}

export function PackageReview({
  session,
  versions,
  onPickVersion,
  actions,
  finish,
  final,
  initialStep,
  navTarget,
}: {
  session: ReviewSession;
  versions: SessionSummary[];
  onPickVersion: (v: number) => void;
  /** Run again / Upload PDFs, when the officer may run a new version. Shown quietly at the foot. */
  actions?: ReactNode;
  /** The last step's forward action (e.g. draft the information request). */
  finish?: { label: string; onClick: () => void };
  /** An extra step after the checks, so the whole review reads as one path. */
  final?: FinalStep;
  initialStep?: Step;
  /** Where the step tabs go (the page header). Without one they sit above the step. */
  navTarget?: HTMLElement | null;
}) {
  const id = useId();
  const steps: Step[] = [...stepsFor(session), ...(final ? (["final"] as Step[]) : [])];
  const label = (s: Step) => (s === "final" ? final?.label ?? "" : STEP_LABEL[s]);
  const [step, setStep] = useState<Step>(initialStep && steps.includes(initialStep) ? initialStep : steps[0]);
  const body = useRef<HTMLDivElement>(null);
  const first = useRef(true);

  // A new version opens on its first step ("What changed" when there is a diff); the first mount
  // keeps `initialStep`.
  const shownKey = useRef(`${session.package_id}:${session.version}`);
  useEffect(() => {
    const key = `${session.package_id}:${session.version}`;
    if (shownKey.current === key) return;
    shownKey.current = key;
    setStep(stepsFor(session)[0]);
  }, [session.package_id, session.version]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    const el = body.current;
    if (!el) return;
    el.focus({ preventScroll: true });
    // After "Next" at the foot of a long step, bring the new step's top into view.
    if (el.getBoundingClientRect().top < 0) el.scrollIntoView({ block: "start" });
  }, [step]);

  // Derived during render: a version without a diff has no "What changed" step, even before the
  // reset effect runs, so a stale step never renders against the wrong session.
  const active: Step = steps.includes(step) ? step : steps[0];
  const at = steps.indexOf(active);
  const prev = steps[at - 1];
  const next = steps[at + 1];
  const counts: Partial<Record<Step, number>> = { missing: missingView(session).total };
  const tabs = <StepTabs steps={steps} active={active} label={label} counts={counts} onPick={setStep} />;

  return (
    <section className="pr" aria-labelledby={`${id}-h`}>
      <h2 id={`${id}-h`} className="cf-sr">Package review</h2>
      {navTarget ? createPortal(tabs, navTarget) : <div className="pr-steps-inline">{tabs}</div>}
      {versions.length > 1 && at === 0 && (
        <div className="pr-versions" role="group" aria-label="Versions">
          {versions.map((v) => (
            <button key={v.version} type="button" className="ac-tab" aria-pressed={v.version === session.version} onClick={() => onPickVersion(v.version)} title={v.statement ?? `${v.open_gaps} open`}>
              Version {v.version}
              <span className="ac-tab-n">{v.statement ? v.statement.split(",")[0] : `${v.open_gaps} open`}</span>
            </button>
          ))}
        </div>
      )}
      <div ref={body} className="pr-body" tabIndex={-1} aria-live="polite">
        {active === "changes" && session.diff && <Changes s={session} />}
        {active === "summary" && <Summary s={session} />}
        {active === "missing" && <Missing s={session} />}
        {active === "checks" && <Checks s={session} />}
        {active === "final" && final?.content}
      </div>
      {(prev || next || finish) && (
        <footer className="pr-foot">
          {prev ? (
            <button type="button" className="cf-btn is-sm is-ghost" onClick={() => setStep(prev)}><AcIcon name="back" size={15} />Back</button>
          ) : <span />}
          {next ? (
            <button type="button" className="cf-btn is-sm is-primary" onClick={() => setStep(next)}>Next: {label(next)}<AcIcon name="right" size={15} /></button>
          ) : finish ? (
            <button type="button" className="cf-btn is-sm is-primary" onClick={finish.onClick}>{finish.label}<AcIcon name="right" size={15} /></button>
          ) : <span />}
        </footer>
      )}
      {at === 0 && (
        <div className="pr-meta-foot">
          <p className="pr-faint" title={`${session.input_kind === "case" ? "Read from the saved application" : "Read from uploaded PDFs"} by ${session.created_by_name}`}>
            Version {session.version} · {sentLabel(session.created_at)}
          </p>
          {actions && <div className="pr-head-acts">{actions}</div>}
        </div>
      )}
    </section>
  );
}
