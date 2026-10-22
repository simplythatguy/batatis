/**
 * The package review, one thing at a time: what changed (from version 2), a short summary, what's
 * missing, the documents panel, the code checks, the Division C file items and the peer-review
 * signal (officer only). Every value comes from the ReviewSession; nothing here judges the design.
 */
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import type { ReviewSession, SessionSummary } from "../../api/types.gen";
import { AcIcon, type AcIconName } from "../auth/bits";
import { sentLabel } from "./queue";
import { CodeRef } from "./CodeRef";
import {
  citationView,
  diffView,
  documentView,
  fileGaps,
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

export type StepId = "changes" | "summary" | "missing" | "documents" | "code" | "file" | "peer";

const STEP_LABEL: Record<StepId, string> = {
  changes: "What changed",
  summary: "Summary",
  missing: "What’s missing",
  documents: "Documents",
  code: "Code checks",
  file: "What the file needs",
  peer: "Second opinion",
};

/** Each step's colour and icon, so the steps are told apart at a glance. */
export const STEP_LOOK: Record<StepId | "final", { hue: string; icon: AcIconName }> = {
  changes: { hue: "slate", icon: "diff" },
  summary: { hue: "blue", icon: "eye" },
  missing: { hue: "rose", icon: "alert" },
  documents: { hue: "violet", icon: "files" },
  code: { hue: "teal", icon: "book" },
  file: { hue: "amber", icon: "clipboard" },
  peer: { hue: "slate", icon: "users" },
  final: { hue: "green", icon: "scale" },
};

/** A step's heading: its coloured icon, the title and an optional count. */
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

/** The form's parts keep the colours the applicant sees in their questions (A blue, B teal, C violet, D amber). */
export const SECTION_HUE: Record<string, string> = { A: "blue", B: "teal", C: "violet", D: "amber", process: "amber" };

/** Shorter names for the step bar, where seven sit side by side. */
const STEP_SHORT: Partial<Record<StepId, string>> = { changes: "Changes", missing: "Missing", file: "File needs", peer: "Peer review" };

export function stepsFor(s: ReviewSession): StepId[] {
  return [...(s.diff ? (["changes"] as StepId[]) : []), "summary", "missing", "documents", "code", "file", "peer"];
}

export const Dot = ({ tone }: { tone: Tone }) => <span className={`cf-dot is-${tone}`} aria-hidden="true" />;
const TONE_WORD: Record<Tone, string> = { blocking: "required", warning: "check", pending: "not established", done: "no gap" };

function FindingItem({ f }: { f: FindingView }) {
  return (
    <li className="pr-item">
      <Dot tone={f.tone} />
      <details className="pr-item-body pr-fold">
        <summary className="pr-item-title">{f.title}<span className="cf-sr"> ({TONE_WORD[f.tone]})</span>{f.where && <span className="pr-where">{f.where}</span>}</summary>
        <p className="pr-item-msg">{f.message}</p>
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
      <StepTitle step="changes">{d.statement}</StepTitle>
      <p className="pr-lede">Since version {d.from}</p>
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
      <StepTitle step="summary">{v.headline}</StepTitle>
      {v.proposal ? (
        <figure className="pr-quote">
          <figcaption>Their proposal{v.proposalWhere ? ` · ${v.proposalWhere}` : ""}</figcaption>
          <blockquote>{v.proposal}</blockquote>
        </figure>
      ) : (
        <p className="pr-item-msg"><Dot tone="blocking" /> No proposal found</p>
      )}
      <div className="pr-metrics">
        <div className="is-rose"><AcIcon name="send" size={16} /><b>{v.toAsk}</b><span>to ask</span></div>
        <div className="is-amber"><AcIcon name="eye" size={16} /><b>{v.toCheck}</b><span>for you</span></div>
        <div className="is-green"><AcIcon name="check" size={16} /><b>{v.present}</b><span>found{v.blank ? ` · ${v.blank} blank` : ""}{v.notFound ? ` · ${v.notFound} not found` : ""}</span></div>
      </div>
      <dl className="pr-facts">
        <dt><AcIcon name="book" size={14} />Code</dt>
        <dd>{v.provisions.length ? v.provisions.map((p) => <span key={p} className="pr-mono pr-pill">{p}</span>) : <span className="pr-faint">None cited</span>}</dd>
        <dt><AcIcon name="files" size={14} />Documents</dt>
        <dd>{v.documents.length ? <ul className="pr-plain">{v.documents.map((d, i) => <li key={i}>{d}</li>)}</ul> : <span className="pr-faint">None</span>}</dd>
      </dl>
      {v.peer && <p className="pr-note"><Dot tone="warning" /> Peer review may be worth it · see step 6</p>}
    </>
  );
}

function Missing({ s }: { s: ReviewSession }) {
  const v = missingView(s);
  if (!v.total) {
    return (
      <>
        <StepTitle step="missing" icon="check">Nothing missing</StepTitle>
        {v.elsewhere > 0 && <p className="pr-lede">{v.elsewhere} more under File needs</p>}
      </>
    );
  }
  return (
    <>
      <StepTitle step="missing" count={v.total}>What’s missing</StepTitle>
      {v.groups.map((g) => (
        <section key={g.section} className="pr-group" aria-label={g.label}>
          <h3 className={`pr-group-h pr-sec is-${SECTION_HUE[g.section]}`}>
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
      {v.elsewhere > 0 && <p className="pr-fine">+{v.elsewhere} under File needs</p>}
    </>
  );
}

function Documents({ s }: { s: ReviewSession }) {
  if (!s.documents.length) {
    return (
      <>
        <StepTitle step="documents">No documents</StepTitle>
      </>
    );
  }
  return (
    <>
      <StepTitle step="documents" count={s.documents.length}>Documents</StepTitle>
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
      <StepTitle step="code">Code checks</StepTitle>
      <p className="pr-lede">NBC(AE) 2023, 2nd printing</p>
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
      <StepTitle step="file" count={fileGaps(s)}>What the file needs</StepTitle>
      <p className="pr-lede">Division C, 2.3.1.1 · present or not, never “enough”</p>
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
      <p className="pr-only"><AcIcon name="eye" size={14} />Only you see this</p>
      {v.signal ? (
        <>
          <StepTitle step="peer" icon="alert">Peer review may help</StepTitle>
          <ul className="pr-list">
            {v.reasons.map((r) => (
              <li key={r} className="pr-item"><Dot tone="warning" /><div className="pr-item-body"><p className="pr-item-title">{r}</p></div></li>
            ))}
          </ul>
        </>
      ) : (
        <>
          <StepTitle step="peer" icon="check">No peer review signal</StepTitle>
        </>
      )}
      <p className="pr-fine">Your call · not a finding about the design</p>
    </>
  );
}

/** A last step after the checks (the decision, the close-out or the outcome), drawn by the caller. */
export interface FinalStep {
  label: string;
  content: ReactNode;
}

type Step = StepId | "final";

export function PackageReview({
  session,
  versions,
  onPickVersion,
  actions,
  finish,
  final,
  initialStep,
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
}) {
  const id = useId();
  const steps: Step[] = [...stepsFor(session), ...(final ? (["final"] as Step[]) : [])];
  const label = (s: Step) => (s === "final" ? final?.label ?? "" : STEP_LABEL[s]);
  const short = (s: Step) => (s === "final" ? label(s) : STEP_SHORT[s] ?? STEP_LABEL[s]);
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
  const missing = missingView(session);
  const counts: Partial<Record<Step, number>> = { missing: missing.total, file: fileGaps(session), peer: session.findings.some((f) => f.key === "peer_review:signal") ? 1 : 0 };

  return (
    <section className="pr" aria-labelledby={`${id}-h`}>
      <h2 id={`${id}-h`} className="cf-sr">Package review</h2>
      {versions.length > 1 && (
        <div className="pr-versions" role="group" aria-label="Versions">
          {versions.map((v) => (
            <button key={v.version} type="button" className="ac-tab" aria-pressed={v.version === session.version} onClick={() => onPickVersion(v.version)} title={v.statement ?? `${v.open_gaps} open`}>
              Version {v.version}
              <span className="ac-tab-n">{v.statement ? v.statement.split(",")[0] : `${v.open_gaps} open`}</span>
            </button>
          ))}
        </div>
      )}
      <nav className="pr-steps" aria-label="Review steps">
        <ol style={{ ["--n" as string]: steps.length }}>
          {steps.map((s, i) => (
            <li key={s}>
              <button
                type="button"
                className={i < at ? "is-past" : undefined}
                aria-current={s === active ? "step" : undefined}
                aria-label={`Step ${i + 1} of ${steps.length}: ${label(s)}${counts[s] ? `, ${counts[s]} to look at` : ""}`}
                title={label(s)}
                onClick={() => setStep(s)}
              >
                <span className={`pr-step-bar is-${STEP_LOOK[s].hue}`} aria-hidden="true" />
                <span className={`pr-step-l is-${STEP_LOOK[s].hue}`} aria-hidden="true"><AcIcon name={STEP_LOOK[s].icon} size={13} />{short(s)}</span>
              </button>
            </li>
          ))}
        </ol>
        <p className="pr-steps-now" aria-hidden="true">Step {at + 1} of {steps.length} · {short(active)}{counts[active] ? ` · ${counts[active]} to look at` : ""}</p>
      </nav>
      <div ref={body} className="pr-body" tabIndex={-1} aria-live="polite">
        {active === "changes" && session.diff && <Changes s={session} />}
        {active === "summary" && <Summary s={session} />}
        {active === "missing" && <Missing s={session} />}
        {active === "documents" && <Documents s={session} />}
        {active === "code" && <CodeChecks s={session} />}
        {active === "file" && <FileItems s={session} />}
        {active === "peer" && <Peer s={session} />}
        {active === "final" && final?.content}
      </div>
      <footer className="pr-foot">
        {prev ? (
          <button type="button" className="cf-btn is-sm is-ghost" onClick={() => setStep(prev)}><AcIcon name="back" size={15} />Back</button>
        ) : <span />}
        {next ? (
          <button type="button" className="cf-btn is-sm" onClick={() => setStep(next)}>Next: {label(next)}<AcIcon name="right" size={15} /></button>
        ) : finish ? (
          <button type="button" className="cf-btn is-sm" onClick={finish.onClick}>{finish.label}<AcIcon name="right" size={15} /></button>
        ) : <span />}
      </footer>
      <div className="pr-meta-foot">
        <p className="pr-faint">
          Review version {session.version} · {session.input_kind === "case" ? "read from the saved application" : "read from uploaded PDFs"} · {session.created_by_name}, {sentLabel(session.created_at).replace(/^Today, /, "")}
        </p>
        {actions && <div className="pr-head-acts">{actions}</div>}
      </div>
    </section>
  );
}
