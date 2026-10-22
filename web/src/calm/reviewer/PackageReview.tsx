/**
 * The package review, one thing at a time: what changed (from version 2), a short summary, what's
 * missing, the documents panel, the code checks, the Division C file items and the peer-review
 * signal (officer only). Every value comes from the ReviewSession; nothing here judges the design.
 */
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import type { ReviewSession, SessionSummary } from "../../api/types.gen";
import { AcIcon } from "../auth/bits";
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
  file: "File items",
  peer: "Peer review",
};

export function stepsFor(s: ReviewSession): StepId[] {
  return [...(s.diff ? (["changes"] as StepId[]) : []), "summary", "missing", "documents", "code", "file", "peer"];
}

export const Dot = ({ tone }: { tone: Tone }) => <span className={`cf-dot is-${tone}`} aria-hidden="true" />;
const TONE_WORD: Record<Tone, string> = { blocking: "required", warning: "check", pending: "not established", done: "no gap" };

function FindingItem({ f }: { f: FindingView }) {
  return (
    <li className="pr-item">
      <Dot tone={f.tone} />
      <div className="pr-item-body">
        <p className="pr-item-title">{f.title}<span className="cf-sr"> ({TONE_WORD[f.tone]})</span></p>
        <p className="pr-item-msg">{f.message}</p>
        {(f.where || f.quote) && (
          <p className="pr-src">
            {f.where && <span>{f.where}</span>}
            {f.quote && <q>{f.quote}</q>}
          </p>
        )}
        {f.citations.length > 0 && <div className="pr-cites">{f.citations.map((c) => <CodeRef key={c} citation={c} />)}</div>}
      </div>
    </li>
  );
}

function Check({ r }: { r: CheckRow }) {
  return (
    <li className="pr-item">
      <Dot tone={r.tone} />
      <div className="pr-item-body">
        <p className="pr-item-title">{r.label}</p>
        <p className="pr-item-meta">{r.status} · <span className="pr-mono">Div C {r.provision}</span></p>
        {r.message && <p className="pr-item-msg">{r.message}</p>}
      </div>
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
      <p className="pr-lede">Since version {d.from}</p>
      <h2 className="pr-title">{d.statement}</h2>
      <div className="pr-meter" role="img" aria-label={`${Math.round(d.ratio * 100)}% of the earlier gaps resolved`}>
        <span style={{ width: `${Math.round(d.ratio * 100)}%` }} />
      </div>
      {list("Resolved", d.resolved, "Nothing from the last version was resolved.")}
      {list("Still open", d.stillOpen, "Nothing from the last version is still open.")}
      {list("New", d.added, "No new gaps.")}
      <p className="pr-fine">Counts the gaps asked of the applicant. Items for you to check and the peer-review signal are not counted.</p>
    </>
  );
}

function Summary({ s }: { s: ReviewSession }) {
  const v = summaryView(s);
  return (
    <>
      <h2 className="pr-title">{v.headline}</h2>
      {v.proposal ? (
        <figure className="pr-quote">
          <blockquote>{v.proposal}</blockquote>
          <figcaption>What they propose, in their words{v.proposalWhere ? ` · ${v.proposalWhere}` : ""}</figcaption>
        </figure>
      ) : (
        <p className="pr-item-msg"><Dot tone="blocking" /> The proposed alternative was not found.</p>
      )}
      <dl className="pr-facts">
        <dt>Code cited</dt>
        <dd>{v.provisions.length ? v.provisions.map((p) => <span key={p} className="pr-mono pr-pill">{p}</span>) : <span className="pr-faint">No provision cited</span>}</dd>
        <dt>Supporting material</dt>
        <dd>{v.documents.length ? <ul className="pr-plain">{v.documents.map((d, i) => <li key={i}>{d}</li>)}</ul> : <span className="pr-faint">No documents listed or uploaded</span>}</dd>
        <dt>Source</dt>
        <dd>{v.readFrom}</dd>
      </dl>
      <div className="pr-metrics">
        <div><b>{v.toAsk}</b><span>to ask the applicant</span></div>
        <div><b>{v.toCheck}</b><span>for you to check</span></div>
        <div><b>{v.present}</b><span>items read{v.blank ? ` · ${v.blank} blank` : ""}{v.notFound ? ` · ${v.notFound} not found` : ""}</span></div>
      </div>
      {v.peer && <p className="pr-note"><Dot tone="warning" /> A peer-review signal is in the last step. Only you see it.</p>}
    </>
  );
}

function Missing({ s }: { s: ReviewSession }) {
  const v = missingView(s);
  if (!v.total) {
    return (
      <>
        <h2 className="pr-title">Nothing missing from the form</h2>
        <p className="pr-lede">Every form item the review reads is present.{v.elsewhere ? ` ${v.elsewhere} Division C ${v.elsewhere === 1 ? "item is" : "items are"} under File items.` : ""}</p>
      </>
    );
  }
  return (
    <>
      <h2 className="pr-title">What’s missing</h2>
      <p className="pr-lede">Grouped by the form’s sections. Each item says where it was read.</p>
      {v.groups.map((g) => (
        <section key={g.section} className="pr-group" aria-label={g.label}>
          <h3 className="pr-group-h">{g.label} <span className="pr-n">{g.items.length}</span></h3>
          <ul className="pr-list">{g.items.map((f) => <FindingItem key={f.key} f={f} />)}</ul>
        </section>
      ))}
      {v.officer.length > 0 && (
        <section className="pr-group" aria-label="For you to check first">
          <h3 className="pr-group-h">For you to check first <span className="pr-n">{v.officer.length}</span></h3>
          <p className="pr-faint pr-group-sub">The review couldn’t establish these (a stamp, a handwritten value, your own registration paperwork). They are not asked of the applicant unless you add them.</p>
          <ul className="pr-list">{v.officer.map((f) => <FindingItem key={f.key} f={f} />)}</ul>
        </section>
      )}
      {v.elsewhere > 0 && <p className="pr-fine">{v.elsewhere} Division C {v.elsewhere === 1 ? "item is" : "items are"} under File items.</p>}
    </>
  );
}

function Documents({ s }: { s: ReviewSession }) {
  if (!s.documents.length) {
    return (
      <>
        <h2 className="pr-title">No supporting documents</h2>
        <p className="pr-lede">Nothing is listed in Section D and no attachment was uploaded.</p>
      </>
    );
  }
  return (
    <>
      <h2 className="pr-title">Documents</h2>
      <p className="pr-lede">What each document says about itself. “Unknown” means nothing labelled was read; it’s never a guess.</p>
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
      <p className="pr-fine">Seals are read from text only and never verified. Documents are not reviewed for adequacy.</p>
    </>
  );
}

function CodeChecks({ s }: { s: ReviewSession }) {
  return (
    <>
      <h2 className="pr-title">Code checks</h2>
      <p className="pr-lede">Each cited provision looked up in NBC(AE) 2023, 2nd printing, and each Section C row compared with the Division B attribution table.</p>
      {s.lookup_skipped && <p className="pr-note"><Dot tone="pending" /> The code lookup wasn’t available, so citations were not checked.</p>}
      <section className="pr-group" aria-label="Citations">
        <h3 className="pr-group-h">Citations <span className="pr-n">{s.citations.length}</span></h3>
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
        <h3 className="pr-group-h">Section C rows <span className="pr-n">{s.section_c.length}</span></h3>
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
      <h2 className="pr-title">File items</h2>
      <p className="pr-lede">What Division C, 2.3.1.1 asks the file to contain. Presence only: the review looks for each item, not at whether it is enough.</p>
      <section className="pr-group" aria-label="Division C file items">
        <h3 className="pr-group-h">In the documentation</h3>
        <ul className="pr-list">{v.items.map((r) => <Check key={r.key} r={r} />)}</ul>
      </section>
      <section className="pr-group" aria-label="Demonstrate, don't assert">
        <h3 className="pr-group-h">Demonstrate, don’t assert</h3>
        <p className="pr-faint pr-group-sub">Does the documentation say what it assumes when things go wrong?</p>
        <ul className="pr-list">{v.demonstrate.map((r) => <Check key={r.key} r={r} />)}</ul>
      </section>
    </>
  );
}

function Peer({ s }: { s: ReviewSession }) {
  const v = peerView(s);
  return (
    <>
      <p className="pr-only"><AcIcon name="hand" size={14} />For you only · the applicant never sees this</p>
      {v.signal ? (
        <>
          <h2 className="pr-title">Peer review may be warranted</h2>
          <ul className="pr-list">
            {v.reasons.map((r) => (
              <li key={r} className="pr-item"><Dot tone="warning" /><div className="pr-item-body"><p className="pr-item-title">{r}</p></div></li>
            ))}
          </ul>
        </>
      ) : (
        <>
          <h2 className="pr-title">No peer-review signal</h2>
          <p className="pr-lede">None of the signals came up: a registered professional stated as required, a Part 3 provision cited, or a product relied on with no CCMC evaluation among the documents.</p>
        </>
      )}
      <p className="pr-fine">It’s your call. Alberta has no set peer-review procedure, and this isn’t a finding about the design.</p>
    </>
  );
}

export function PackageReview({
  session,
  versions,
  onPickVersion,
  actions,
  finish,
  initialStep,
}: {
  session: ReviewSession;
  versions: SessionSummary[];
  onPickVersion: (v: number) => void;
  /** Run again / Upload PDFs, when the officer may run a new version. */
  actions?: ReactNode;
  /** The last step's forward action (e.g. draft the information request). */
  finish?: { label: string; onClick: () => void };
  initialStep?: StepId;
}) {
  const id = useId();
  const steps = stepsFor(session);
  const [step, setStep] = useState<StepId>(initialStep && steps.includes(initialStep) ? initialStep : steps[0]);
  const body = useRef<HTMLDivElement>(null);
  const first = useRef(true);

  // A new version opens on its first step ("What changed" when there is a diff).
  useEffect(() => {
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

  const at = Math.max(0, steps.indexOf(step));
  const prev = steps[at - 1];
  const next = steps[at + 1];
  const missing = missingView(session);
  const counts: Partial<Record<StepId, number>> = { missing: missing.total, file: fileGaps(session), peer: session.findings.some((f) => f.key === "peer_review:signal") ? 1 : 0 };

  return (
    <section className="pr" aria-labelledby={`${id}-h`}>
      <header className="pr-head">
        <div className="pr-head-txt">
          <h2 id={`${id}-h`} className="pr-head-title">Package review</h2>
          <p className="pr-faint">
            Version {session.version} · {session.input_kind === "case" ? "saved application" : "uploaded PDFs"} · {session.created_by_name}, {sentLabel(session.created_at).replace(/^Today, /, "")}
          </p>
        </div>
        {actions && <div className="pr-head-acts">{actions}</div>}
      </header>
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
        <ol>
          {steps.map((s, i) => (
            <li key={s}>
              <button type="button" aria-current={s === step ? "step" : undefined} onClick={() => setStep(s)}>
                <span className="pr-step-n">{i + 1}</span>
                <span className="pr-step-l">{STEP_LABEL[s]}</span>
                {counts[s] ? <span className="pr-step-c">{counts[s]}</span> : null}
              </button>
            </li>
          ))}
        </ol>
        <p className="pr-steps-phone" aria-hidden="true">{at + 1} of {steps.length} · {STEP_LABEL[step]}</p>
      </nav>
      <div ref={body} className="pr-body" tabIndex={-1} aria-live="polite">
        {step === "changes" && <Changes s={session} />}
        {step === "summary" && <Summary s={session} />}
        {step === "missing" && <Missing s={session} />}
        {step === "documents" && <Documents s={session} />}
        {step === "code" && <CodeChecks s={session} />}
        {step === "file" && <FileItems s={session} />}
        {step === "peer" && <Peer s={session} />}
      </div>
      <footer className="pr-foot">
        {prev ? (
          <button type="button" className="cf-btn is-sm is-ghost" onClick={() => setStep(prev)}><AcIcon name="back" size={15} />{STEP_LABEL[prev]}</button>
        ) : <span />}
        {next ? (
          <button type="button" className="cf-btn is-sm" onClick={() => setStep(next)}>{STEP_LABEL[next]}<AcIcon name="right" size={15} /></button>
        ) : finish ? (
          <button type="button" className="cf-btn is-sm" onClick={finish.onClick}>{finish.label}<AcIcon name="right" size={15} /></button>
        ) : <span />}
      </footer>
      <p className="pr-fine pr-admin">Administrative completeness only. The review lists what is present or missing; it doesn’t judge the design.</p>
    </section>
  );
}
