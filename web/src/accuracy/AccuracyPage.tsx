/** #/accuracy: what Batatis guarantees and what we measured, from the bundled report (no engine call). */
import type { ReactNode } from "react";
import data from "../../../docs/accuracy/report.json";
import { PageHead } from "../calm/auth/bits";
import {
  STATUS_TEXT,
  builtText,
  checkReport,
  figureView,
  verifiedText,
  type Claim,
  type DetailTable,
  type Report,
  type Section,
} from "./report";
import "./accuracy.css";

function load(): { report: Report | null; error: string } {
  try {
    return { report: checkReport(data), error: "" };
  } catch (e) {
    return { report: null, error: e instanceof Error ? e.message : "The accuracy report could not be read." };
  }
}

const LOADED = load();

function ClaimRow({ c }: { c: Claim }) {
  return (
    <li className="acc-claim">
      <details>
        <summary>
          <span className="acc-claim-text">{c.claim}</span>
          <span className="acc-more" aria-hidden="true">{c.tests.length} {c.tests.length === 1 ? "test" : "tests"}</span>
        </summary>
        <div className="acc-open">
          <p>{c.detail}</p>
          <p className="acc-faint">Enforced by</p>
          <ul className="acc-tests">
            {c.tests.map((t) => (
              <li key={t.id}>
                <code>{t.file}</code>
                <span className="acc-test-name">{t.name}</span>
                {t.result && <span className="acc-faint"> · {t.result}</span>}
              </li>
            ))}
          </ul>
        </div>
      </details>
    </li>
  );
}

function Table({ t }: { t: DetailTable }) {
  if (!t.rows.length) return null;
  return (
    <div className="acc-table-wrap" role="region" aria-label={t.title} tabIndex={0}>
      <table className="acc-table">
        <caption>{t.title}</caption>
        <thead>
          <tr>{t.header.map((h) => <th key={h} scope="col">{h}</th>)}</tr>
        </thead>
        <tbody>
          {t.rows.map((row, i) => (
            <tr key={i}>{row.map((cell, j) => (j === 0 ? <th key={j} scope="row">{cell}</th> : <td key={j}>{cell}</td>))}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SectionBlock({ s }: { s: Section }) {
  const status = STATUS_TEXT[s.status];
  return (
    <section className="acc-measure" aria-labelledby={`acc-${s.id}`}>
      <h3 id={`acc-${s.id}`} className="acc-measure-title">
        {s.title}
        {status && <span className={`acc-status is-${s.status}`}>{status}</span>}
      </h3>
      <p className="acc-plain">{s.plain}</p>
      {s.definition && <p className="acc-faint">{s.definition}</p>}
      {s.figures.length > 0 && (
        <ul className="acc-figures">
          {s.figures.map((f) => {
            const v = figureView(f);
            return (
              <li key={v.id} className="acc-figure">
                <div className="acc-figure-head">
                  <span className="acc-value">{v.value}</span>
                  <span className="acc-rate">{v.rate}</span>
                  {v.interval && <span className="acc-interval">{v.interval}</span>}
                </div>
                <p className="acc-label">{v.label}</p>
                {v.note && <p className="acc-note">{v.note}</p>}
                <p className="acc-meta">
                  {v.meta}
                  {v.tags.map((t) => <span key={t} className="acc-tag">{t}</span>)}
                </p>
                <details className="acc-source">
                  <summary>Source</summary>
                  <p>{v.source}</p>
                  {v.command && <p><code>{v.command}</code></p>}
                  {v.quote && <blockquote>{v.quote}</blockquote>}
                </details>
              </li>
            );
          })}
        </ul>
      )}
      {s.caveats.length > 0 && (
        <ul className="acc-caveats" aria-label="How sure we are">
          {s.caveats.map((c) => <li key={c}>{c}</li>)}
        </ul>
      )}
      {s.detail && s.detail.some((t) => t.rows.length) && (
        <details className="acc-detail">
          <summary>Show the detail</summary>
          {s.detail.map((t) => <Table key={t.title} t={t} />)}
          {s.updates_when && <p className="acc-faint">Updates when {s.updates_when.charAt(0).toLowerCase() + s.updates_when.slice(1)}</p>}
        </details>
      )}
    </section>
  );
}

export function AccuracyPage({ phoneTools, right }: { phoneTools?: ReactNode; right?: ReactNode }) {
  const { report, error } = LOADED;
  return (
    <div className="ac-page acc-page">
      <PageHead title="Accuracy" phoneTools={phoneTools} right={right} />
      <div className="ac-page-body is-narrow acc-body">
        <h1 className="ac-page-title">How accurate Batatis is</h1>
        {!report ? (
          <p className="acc-plain" role="alert">{error}</p>
        ) : (
          <>
            <p className="acc-lede">{report.intro}</p>
            <p className="acc-faint">{builtText(report)}</p>

            <section className="ac-section" aria-labelledby="acc-guaranteed">
              <h2 id="acc-guaranteed" className="acc-h2">What Batatis guarantees</h2>
              <p className="acc-plain">
                These hold by construction. Each one names the tests that enforce it, and the build fails if a test fails.
              </p>
              {verifiedText(report) && <p className="acc-faint">{verifiedText(report)}</p>}
              <ul className="acc-claims">
                {report.guaranteed.map((c) => <ClaimRow key={c.id} c={c} />)}
              </ul>
            </section>

            <section className="ac-section" aria-labelledby="acc-measured">
              <h2 id="acc-measured" className="acc-h2">What we measured, and how sure we are</h2>
              <p className="acc-plain">
                Each number is a count out of a sample, with a 95% interval where one applies. The interval is the range the
                true rate plausibly lies in; small samples give wide intervals.
              </p>
              {report.measured.map((s) => <SectionBlock key={s.id} s={s} />)}
            </section>

            <section className="ac-section is-last" aria-labelledby="acc-not">
              <h2 id="acc-not" className="acc-h2">Not measured yet</h2>
              <ul className="acc-caveats">
                {report.not_measured.map((n) => (
                  <li key={n.title}><strong>{n.title}.</strong> {n.why}</li>
                ))}
              </ul>
            </section>
          </>
        )}
      </div>
    </div>
  );
}
