/**
 * Deck pieces for intake and code identification: what we read (the applicant's words with the
 * span marked), the planner's inputs, the fork note, code-check progress, "Show the code" and the
 * scope redirect page. Copy comes from docs/api/intake.md and docs/api/identify.md responses;
 * nothing here says a design complies or is safe.
 */
import { useId, useState } from "react";
import { useProvisionText } from "../api/sectionC";
import type { Fork, PreApplication } from "../api/types.gen";
import { NrcCredit } from "../components";
import { forkLine, HALF_PLAIN, planInput, scopeRedirect, snippet, stageViews, type ReadCopy, type Snippet } from "../intakeView";
import { useCase } from "../store";
import type { Candidate } from "../types";
import { DETAIL_IDS, factLabel } from "../model";
import type { DeckItem } from "./deck";
import { clearJourneyAnswerAction, journeyAnswerAction } from "./journey";
import { Icon24 } from "./icons";
import { codeHref } from "./routes";
import { CIcon, Dot } from "./ui";
import { jobLabel } from "../api/jobs";

export function Words({ words, quote }: { words: Snippet | null; quote?: string }) {
  if (words) {
    return (
      <blockquote className="cf-said-words">
        {words.before}
        <mark>{words.mark}</mark>
        {words.after}
      </blockquote>
    );
  }
  return quote ? <blockquote className="cf-said-words"><mark>{quote}</mark></blockquote> : null;
}

/** The words a value was read from, where they came from, and how sure we are. */
export function ReadSource({ copy }: { copy: ReadCopy }) {
  return (
    <figure className="cf-said">
      <Words words={copy.words} quote={copy.quote} />
      <figcaption className="cf-said-meta">
        <span>{copy.source}</span>
        <span className="cf-said-sure"><Dot tone={copy.sure.tone} />{copy.sure.text}</span>
      </figcaption>
    </figure>
  );
}

/** A single confirmation covers the reading; each row keeps its existing confirm/correct UI. */
export function UnderstoodFacts({ item }: { item: DeckItem }) {
  const { c, dispatch } = useCase();
  const [editing, setEditing] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [note, setNote] = useState("");
  return <div className="cf-understood">{item.rows?.map((row) => {
    const section = DETAIL_IDS.has(row.field) && ["owner", "representative", "mailingAddress", "date"].includes(row.field) ? "A" : "B";
    const fact: DeckItem = { key: row.key, kind: "fact", section, stage: "understand", answerer: "you", eyebrow: "Understand", title: row.copy.title, context: "", why: "", ref: row.ref, field: row.field, ids: row.ids, done: row.done, optional: false };
    const fix = (value: "confirm" | "dismiss" | "not_sure", details: HTMLDetailsElement | null) => {
      if (value === "dismiss") { setEditing(row.key); setNote(""); return; }
      if (value === "not_sure") {
        dispatch({ type: "rejectFacts", ids: row.ids });
        dispatch({ type: "setRuleInput", field: row.field, value: null, rule: "intake-correction", quote: "" });
        dispatch(journeyAnswerAction(fact, "not_sure"));
      }
      else {
        dispatch(clearJourneyAnswerAction(fact));
        const waiting = row.ids.filter((id) => c.facts.some((f) => f.id === id && f.status === "unconfirmed"));
        dispatch({ type: "confirmFacts", ids: row.deferred ? row.ids : waiting });
      }
      if (details) details.open = false;
    };
    const input = typeof row.value === "boolean" ? { kind: "choices", choices: [{ value: "yes", label: "Yes" }, { value: "no", label: "No" }] } : planInput(row.field);
    const save = (value: string, details: HTMLDetailsElement | null) => {
      const numeric = input.kind === "number" || typeof row.value === "number";
      const number = Number(value.trim());
      if (!value.trim() || (numeric && (!Number.isFinite(number) || number < 0 || ((row.field === "storeys" || row.field === "dwelling_units") && (!Number.isInteger(number) || number < 1))))) { setNote("Enter a value for this question."); return; }
      dispatch(clearJourneyAnswerAction(fact));
      dispatch({ type: "rejectFacts", ids: row.ids });
      if (numeric || typeof row.value === "boolean") dispatch({ type: "setRuleInput", field: row.field, value: numeric ? number : value === "yes", rule: "intake-correction", quote: value });
      else dispatch({ type: "setDetail", field: row.field, value, section });
      setEditing(null);
      setNote("");
      if (details) details.open = false;
    };
    return <details key={row.key}>
      <summary aria-label={`Edit ${factLabel(row.field)}`}><Icon24 name={row.assumed ? "spark" : "file"} size={16} /><span className="cf-understood-label">{factLabel(row.field)}</span><span className="cf-understood-value">{row.copy.value}</span><span className="cf-understood-sources">{row.assumed ? <span className="cf-source-chip is-assumed">assumed</span> : row.sources.filter((source) => !/^Your (description|answer)$/.test(source)).map((source) => <span key={source} className="cf-source-chip">{source}</span>)}{row.deferred && <span className="cf-source-chip">{row.deferred === "designer" ? "Ask my designer" : "Not sure"}</span>}</span><span className="cf-understood-fix">Edit</span></summary>
      <ReadSource copy={row.copy} />
      {editing === row.key ? <div>
        {input.kind === "choices" ? <div className="cf-row-actions">{input.choices?.map((choice) => <button key={choice.value} type="button" className="cf-btn" onClick={(e) => save(choice.value, e.currentTarget.closest("details"))}>{choice.label}</button>)}</div> : <div className="cf-inline-answer"><input className="cf-uline" aria-label={row.copy.title} value={drafts[row.key] ?? String(row.value ?? "")} onChange={(e) => setDrafts((draft) => ({ ...draft, [row.key]: e.target.value }))} /><button type="button" className="cf-btn" onClick={(e) => save(drafts[row.key] ?? String(row.value ?? ""), e.currentTarget.closest("details"))}>Save</button></div>}
        {note && <p className="cf-note" role="alert">{note}</p>}
      </div> : null}
      <div className="cf-row-actions">
        <button type="button" className="cf-btn" onClick={(e) => fix("confirm", e.currentTarget.closest("details"))}>{row.copy.confirm}</button>
        <button type="button" className="cf-btn" onClick={(e) => fix("dismiss", e.currentTarget.closest("details"))}>{row.copy.dismiss}</button>
        <button type="button" className="cf-link-btn" onClick={(e) => fix("not_sure", e.currentTarget.closest("details"))}>Not sure</button>
      </div>
    </details>;
  })}</div>;
}

export function ProductRouteNotice() {
  const { c } = useCase();
  const notice = c.intake?.record.plan?.route_notice;
  if (!notice) return null;
  return <details className="cf-fork-more"><summary>Product acceptance and a site variance</summary><p>{notice.summary}</p>{notice.bullets.map((bullet, i) => <p key={i}>{bullet.claim} {bullet.citations.map((source) => source.url ? <a key={source.title} href={source.url} target="_blank" rel="noreferrer">{source.title}</a> : <span key={source.title}>{source.title}</span>)}</p>)}</details>;
}

/** The acceptable or alternative path, in the API's words, with the two halves kept apart. */
export function ForkNote({ fork, detailsOnly = false }: { fork: Fork; detailsOnly?: boolean }) {
  return (
    <div className="cf-fork" role="note">
      {!detailsOnly && <p className="cf-fork-line"><Dot tone={fork.variance_needed === "likely" ? "warning" : "pending"} />{forkLine(fork)}</p>}
      <details className="cf-fork-more">
        <summary>Details</summary>
        <p className="cf-fork-text">{fork.explanation}</p>
        <ul className="cf-halves">
          {fork.halves.map((h) => (
            <li key={h.id}>
              <span className="cf-half-label">{HALF_PLAIN[h.id] ?? h.label}<span className="cf-half-term"> · {h.label}</span></span>
              <span className="cf-half-basis">{h.basis}</span>
              <span className="cf-half-what">{h.what}.</span>
              <span className="cf-half-who">{h.who}.</span>
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}

/** "Before you submit": meet the authority and emergency services early. Shown once, on the review. */
export function BeforeYouSubmit({ pre }: { pre: PreApplication }) {
  if (!pre.steps.length) return null;
  return (
    <section className="cf-preapp" aria-labelledby="cf-preapp-h">
      <h2 id="cf-preapp-h" className="cf-list-label">Before you submit</h2>
      {pre.steps.map((step) => (
        <details key={step.id} className="cf-preapp-step">
          <summary>{step.title}</summary>
          <p>{step.text}</p>
          {step.sources.length > 0 && (
            <ul className="cf-preapp-src">
              {step.sources.map((src) => (
                <li key={src.title}>
                  {src.url ? <a href={src.url} target="_blank" rel="noreferrer">{src.title}</a> : src.title}
                </li>
              ))}
            </ul>
          )}
        </details>
      ))}
    </section>
  );
}

/** Intake at work, or its failure with Try again. */
export function ReadingState() {
  const { reading, readDescription, cancelReadingJob } = useCase();
  if (reading.intake === "error") {
    const exhausted = reading.intakeJob && ["failed", "cancelled"].includes(reading.intakeJob.state) && !reading.intakeJob.can_retry;
    return <><button type="button" className="cf-btn cf-step-start" disabled={exhausted} onClick={() => void readDescription()}><CIcon name="retry" size={14} />Try again</button>{exhausted && <p className="cf-note">This saved job cannot be retried.</p>}</>;
  }
  if (reading.intake !== "running") {
    return <button type="button" className="cf-btn cf-step-start" onClick={() => void readDescription()}>Read my description</button>;
  }
  return <>
    <ol className="cf-steps" aria-live="polite">
      <li className="cf-step is-running">
        <span className="cf-step-mark" aria-hidden="true" />
        <span className="cf-step-label">Reading your description and files</span>
        <span className="cf-step-detail">{reading.intakeJob ? jobLabel(reading.intakeJob) : "Starting…"}</span>
      </li>
    </ol>
    {reading.intakeNote && <p className="cf-note" role="status">{reading.intakeNote}</p>}
    {reading.intakeJob && <button type="button" className="cf-link-btn" onClick={() => void cancelReadingJob("intake")}>Cancel</button>}
  </>;
}

/** Stage progress for the code check: screen, rerank, verify, questions. Counts only. */
export function CodeProgress() {
  const { reading, runIdentify, cancelReadingJob } = useCase();
  const running = reading.identify === "running";
  if (reading.identify === "error") {
    const exhausted = reading.identifyJob && ["failed", "cancelled"].includes(reading.identifyJob.state) && !reading.identifyJob.can_retry;
    return (
      <div className="cf-step-error">
        <p className="cf-note"><Dot tone="warning" />{reading.identifyNote || "The code check didn’t finish."}</p>
        <div className="cf-row-actions">
          <button type="button" className="cf-btn" disabled={exhausted} onClick={() => void runIdentify()}><CIcon name="retry" size={14} />Try again</button>
          <a className="cf-btn is-ghost" href="#/code">Find the rule yourself</a>
        </div>
        {exhausted && <p className="cf-note">This saved job cannot be retried.</p>}
      </div>
    );
  }
  if (!running && reading.identify !== "done") {
    return <button type="button" className="cf-btn cf-step-start" onClick={() => void runIdentify()}>Check the code now</button>;
  }
  if (reading.identifyJob) return <><ol className="cf-steps" aria-live="polite"><li className={`cf-step is-${running ? "running" : "done"}`}>
    <span className="cf-step-mark" aria-hidden="true" />
    <span className="cf-step-label">Code check</span>
    <span className="cf-step-detail">{jobLabel(reading.identifyJob)}</span>
  </li></ol>{reading.identifyNote && <p className="cf-note" role="status">{reading.identifyNote}</p>}
    {running && <button type="button" className="cf-link-btn" onClick={() => void cancelReadingJob("identify")}>Cancel</button>}
  </>;
  return (
    <ol className="cf-steps" aria-live="polite">
      {stageViews(reading.stages, running).map((s) => (
        <li key={s.id} className={`cf-step is-${s.state}`}>
          <span className="cf-step-mark" aria-hidden="true">{s.state === "done" ? <Icon24 name="check" size={14} /> : null}</span>
          <span className="cf-step-label">{s.label}</span>
          <span className="cf-step-detail">{s.state === "running" ? "Working…" : s.detail}</span>
          <span className="cf-sr">{s.state === "done" ? "done" : s.state === "running" ? "in progress" : "waiting"}</span>
        </li>
      ))}
    </ol>
  );
}

const articleOf = (id: string) => id.match(/^\d+\.\d+\.\d+\.\d+\./)?.[0] ?? id;

/** The article number and the code sentence behind a disclosure; verbatim code-database text only. */
export function ShowCode({ cand, onMore }: { cand: Candidate; onMore: () => void }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const live = useProvisionText(open ? cand.provision : undefined);
  const text = live.state === "live" ? live.text : cand.quote.text;
  const citation = live.state === "live" ? live.citation : cand.quote.citation;
  return (
    <div className="cf-showcode">
      <button type="button" className="cf-link-btn cf-showcode-toggle" aria-expanded={open} aria-controls={id} onClick={() => setOpen((v) => !v)}>
        <CIcon name="doc" size={14} />{open ? "Hide the code" : "Show the code"}
      </button>
      {open && (
        <div id={id} className="cf-codebox">
          <div className="cf-codebox-head">
            <span className="cf-mono">{cand.provision}</span>
            <span className="cf-codebox-title">{cand.topic}</span>
          </div>
          {text ? <blockquote className="cf-code-text">{text}</blockquote> : <p className="cf-faint">{live.state === "loading" ? "Loading the code text…" : "The wording did not load."}</p>}
          <div className="cf-code-src">{citation}{citation ? " · " : ""}Code text, verbatim · <NrcCredit /></div>
          <div className="cf-codebox-links">
            <button type="button" className="cf-link-btn" onClick={onMore}>More about this rule</button>
            <a className="cf-link-btn" href={codeHref(articleOf(cand.provision))}>Open in the code library <CIcon name="arrow" size={13} /></a>
          </div>
        </div>
      )}
    </div>
  );
}

/** Another safety-codes regime: what triggered it, the API's copy, and the two ways on. */
export function RedirectPage() {
  const { c, overrideScope, reading } = useCase();
  const [note, setNote] = useState("");
  const scope = scopeRedirect(c);
  if (!scope?.regime) return null;
  const words = snippet(c.intake?.text ?? c.description, scope.start, scope.end);
  const busy = reading.busy === "scope";
  return (
    <div className="cf-q-wrap is-from-down cf-redirect" role="group" aria-labelledby="cf-q">
      <h2 id="cf-q" className="cf-q-text" tabIndex={-1}>This reads as a {scope.regime.name} question.</h2>
      <figure className="cf-said">
        <Words words={words} quote={scope.cue ?? undefined} />
        <figcaption className="cf-said-meta"><span>The words that decided it, from your description</span></figcaption>
      </figure>
      <p className="cf-q-help">{scope.message}</p>
      <div className="cf-ok-row">
        {scope.override_allowed && (
          <button
            type="button"
            className="cf-btn is-primary is-lg"
            disabled={busy}
            onClick={() => void overrideScope(true).then((e) => setNote(e ?? ""))}
          >
            {busy ? "Saving…" : "This is a building-code question"}
          </button>
        )}
        <a className="cf-btn is-lg" href="#/">Back to my description</a>
      </div>
      {note && <p className="cf-note" role="alert"><Dot tone="warning" />{note}</p>}
      <p className="cf-faint cf-small cf-redirect-foot">The official export stays blocked until you choose. Batatis never decides which code applies; the officer does.</p>
    </div>
  );
}
