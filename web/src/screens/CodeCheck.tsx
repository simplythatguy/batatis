import { useState } from "react";
import { GapStrip, Icon, PanelHeader, StatusPill, type Dot } from "../components";
import { answeredYes, unresolvedCandidates } from "../model";
import { useCase } from "../store";
import type { Candidate, CandidateAnswer } from "../types";

const ANSWERS: { value: CandidateAnswer; label: string }[] = [
  { value: "yes", label: "Yes" },
  { value: "no", label: "No" },
  { value: "not-sure", label: "Not sure" },
];

const STATUS: Record<string, { dot: Dot; label: string }> = {
  yes: { dot: "done", label: "Departure confirmed" },
  no: { dot: "pending", label: "Not a departure" },
  "not-sure": { dot: "warning", label: "Not sure yet" },
  none: { dot: "blocking", label: "Needs your answer" },
};

function CandidateCard({ a, index, total }: { a: Candidate; index: number; total: number }) {
  const { dispatch } = useCase();
  const s = STATUS[a.answer ?? "none"];
  return (
    <article className="card" id={`cand-${a.id}`} tabIndex={-1} aria-labelledby={`cand-${a.id}-topic`}>
      <div className="card-head">
        <span className="meta">
          {index + 1} of {total}
        </span>
        <h2 className="card-topic" id={`cand-${a.id}-topic`}>
          {a.topic}
        </h2>
        {a.benchmark && <span className="label-pill">Main requirement</span>}
        <StatusPill dot={s.dot}>{s.label}</StatusPill>
      </div>
      <div className="code-said">
        <div className="block-label">
          <span className="label-pill">Code text</span>
          <span className="meta">The code says</span>
        </div>
        <blockquote className="cite-block quote">{a.quote.text}</blockquote>
      </div>
      <p className="ask">
        <span className="label-pill ai-pill">AI-written</span> Does your design <strong>{a.departure}</strong> instead?
      </p>
      <div className="segmented" role="group" aria-label={`Answer for ${a.topic}`}>
        {ANSWERS.map((o) => (
          <button
            key={o.value}
            type="button"
            className="btn"
            aria-pressed={a.answer === o.value}
            onClick={() => dispatch({ type: "answerCandidate", id: a.id, answer: o.value })}
          >
            {o.label}
          </button>
        ))}
      </div>
      {a.answer === "not-sure" && (
        <div className="followup">
          <div className="meta">We will ask</div>
          <p>{a.clarifyingQuestion}</p>
          <p className="meta">Answer Yes or No once you know; Section C waits for it.</p>
        </div>
      )}
      <details className="disclosure ref">
        <summary>
          <Icon name="chevron" size={12} />
          <span className="disclosure-title">Code reference</span>
        </summary>
        <dl className="ref-grid">
          <dt>Provision</dt>
          <dd className="article-id">{a.provision}</dd>
          <dt>Citation</dt>
          <dd className="mono">{a.quote.citation}</dd>
          <dt>Part</dt>
          <dd>Part {a.part}</dd>
        </dl>
      </details>
    </article>
  );
}

type Filter = "all" | "open" | "yes";

export function CodeCheck() {
  const { c, gaps } = useCase();
  const [filter, setFilter] = useState<Filter>("all");
  const open = unresolvedCandidates(c);
  const yes = answeredYes(c);
  const counts: Record<Filter, number> = { all: c.candidates.length, open: open.length, yes: yes.length };
  const shown = c.candidates.filter((a) => filter === "all" || (filter === "open" ? open.includes(a) : a.answer === "yes"));
  const labels: Record<Filter, string> = { all: "All", open: "Needs an answer", yes: "Departures" };
  return (
    <>
      <PanelHeader title="Code check" meta="NBC(AE) 2023 · 2nd printing" />
      <GapStrip gaps={gaps} />
      <div className="toolbar" role="toolbar" aria-label="Filter">
        {(Object.keys(labels) as Filter[]).map((f) => (
          <button key={f} type="button" className="pill" data-active={filter === f} aria-pressed={filter === f} onClick={() => setFilter(f)}>
            {labels[f]} <span className="tab-count">{counts[f]}</span>
          </button>
        ))}
      </div>
      <div className="pane scroll-body">
        <div className="content-col stack">
          <p className="meta intro">
            Each card quotes one requirement your design may depart from. Answer in your own terms; you do not need the
            article numbers.
          </p>
          {shown.length ? (
            shown.map((a) => <CandidateCard key={a.id} a={a} index={c.candidates.indexOf(a)} total={c.candidates.length} />)
          ) : (
            <p className="empty">Nothing in this view.</p>
          )}
        </div>
      </div>
      <div className="footer-bar">
        <span className="status-note" role="status">
          {open.length ? `Answer ${open.map((a) => a.topic.toLowerCase()).join("; ")} to continue` : ""}
        </span>
        <a className="btn btn-ghost" href="#/describe">
          Back
        </a>
        {open.length ? (
          <button type="button" className="btn btn-primary" disabled>
            Continue to Section C
          </button>
        ) : (
          <a className="btn btn-primary" href="#/section-c">
            Continue to Section C
          </a>
        )}
      </div>
    </>
  );
}
