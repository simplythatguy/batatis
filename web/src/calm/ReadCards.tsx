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
import { forkLine, scopeRedirect, snippet, stageViews, type ReadCopy, type Snippet } from "../intakeView";
import { useCase } from "../store";
import type { Candidate } from "../types";
import { Icon24 } from "./icons";
import { codeHref } from "./routes";
import { CIcon, Dot } from "./ui";

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

/** The acceptable or alternative path, in the API's words, with the two halves kept apart. */
export function ForkNote({ fork }: { fork: Fork }) {
  return (
    <div className="cf-fork" role="note">
      <p className="cf-fork-line"><Dot tone={fork.variance_needed === "likely" ? "warning" : "pending"} />{forkLine(fork)}</p>
      <p className="cf-fork-text">{fork.explanation}</p>
      <details className="cf-fork-more">
        <summary>What an accepted variance needs</summary>
        <ul className="cf-halves">
          {fork.halves.map((h) => (
            <li key={h.id}>
              <span className="cf-half-label">{h.label}</span>
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
  const { reading, readDescription } = useCase();
  if (reading.intake === "error") {
    return <button type="button" className="cf-btn cf-step-start" onClick={() => void readDescription()}><CIcon name="retry" size={14} />Try again</button>;
  }
  if (reading.intake !== "running") {
    return <button type="button" className="cf-btn cf-step-start" onClick={() => void readDescription()}>Read my description</button>;
  }
  return (
    <ol className="cf-steps" aria-live="polite">
      <li className="cf-step is-running">
        <span className="cf-step-mark" aria-hidden="true" />
        <span className="cf-step-label">Reading your description and files</span>
        <span className="cf-step-detail">Working…</span>
      </li>
    </ol>
  );
}

/** Stage progress for the code check: screen, rerank, verify, questions. Counts only. */
export function CodeProgress() {
  const { reading, runIdentify } = useCase();
  const running = reading.identify === "running";
  if (reading.identify === "error") {
    return (
      <div className="cf-step-error">
        <p className="cf-note"><Dot tone="warning" />{reading.identifyNote || "The code check didn’t finish."}</p>
        <button type="button" className="cf-btn" onClick={() => void runIdentify()}><CIcon name="retry" size={14} />Try again</button>
      </div>
    );
  }
  if (!running && reading.identify !== "done") {
    return <button type="button" className="cf-btn cf-step-start" onClick={() => void runIdentify()}>Check the code now</button>;
  }
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
export function RedirectPage({ n }: { n: number }) {
  const { c, overrideScope, reading } = useCase();
  const [note, setNote] = useState("");
  const scope = scopeRedirect(c);
  if (!scope?.regime) return null;
  const words = snippet(c.intake?.text ?? c.description, scope.start, scope.end);
  const busy = reading.busy === "scope";
  return (
    <div className="cf-q-wrap is-from-down cf-redirect" role="group" aria-labelledby="cf-q">
      <div className="cf-q-num"><span className="cf-q-n">{n}</span><Icon24 name="right" size={15} stroke={2} /><span className="cf-q-sec">Before we go on</span></div>
      <h2 id="cf-q" className="cf-q-text" tabIndex={-1}>This reads as a {scope.regime.name} question.</h2>
      <figure className="cf-said">
        <Words words={words} quote={scope.cue ?? undefined} />
        <figcaption className="cf-said-meta"><span>The words that decided it, from your description</span></figcaption>
      </figure>
      <p className="cf-q-help">{scope.message}</p>
      <dl className="cf-redirect-facts">
        <dt>Code</dt>
        <dd>{scope.regime.code}</dd>
        <dt>Where to take it</dt>
        <dd>{scope.regime.route}</dd>
      </dl>
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
