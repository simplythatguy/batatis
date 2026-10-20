import { CodeText, PanelHeader, StatusIcon, type StatusKind } from "../components";
import { unresolvedCandidates } from "../model";
import { useCase } from "../store";
import type { Candidate, CandidateAnswer } from "../types";

const ANSWERS: { value: CandidateAnswer; label: string }[] = [
  { value: "yes", label: "Yes" },
  { value: "no", label: "No" },
  { value: "not-sure", label: "Not sure" },
];

/** The answer itself shows on the pressed button; the mark says where the card stands. */
const MARK: Record<string, { kind: StatusKind; label: string }> = {
  yes: { kind: "confirmed", label: "Answered: different from the code" },
  no: { kind: "confirmed", label: "Answered: same as the code" },
  "not-sure": { kind: "open-question", label: "Not sure: open question for the officer" },
  none: { kind: "unconfirmed", label: "Not answered yet" },
};

function CandidateCard({ a }: { a: Candidate }) {
  const { dispatch } = useCase();
  const m = MARK[a.answer ?? "none"];
  return (
    <article className="card" id={`cand-${a.id}`} tabIndex={-1} aria-labelledby={`cand-${a.id}-topic`}>
      <div className="card-head">
        <StatusIcon kind={m.kind} label={m.label} />
        {a.benchmark && <span className="label-pill">Main code rule</span>}
        <h2 className="card-topic" id={`cand-${a.id}-topic`}>
          {a.topic}
        </h2>
      </div>
      <CodeText text={a.quote.text} citation={a.quote.citation} />
      <div>
        <p className="ask">
          Does your design <strong>{a.departure}</strong> instead?
        </p>
        <span className="meta">AI-written question</span>
      </div>
      <div className="segmented" role="group" aria-label={`Answer for ${a.topic}`}>
        {ANSWERS.map((o) => (
          <button
            key={o.value}
            type="button"
            className="btn"
            aria-pressed={a.answer === o.value}
            onClick={() => dispatch({ type: "answerCandidate", id: a.id, answer: o.value })}
          >
            {o.value === "not-sure" && <StatusIcon kind="open-question" size="sm" label="" decorative />}
            {o.label}
          </button>
        ))}
      </div>
      {a.answer === "not-sure" ? (
        <div className="followup">
          <div className="meta">Open question for the officer</div>
          <p>{a.clarifyingQuestion}</p>
          <p className="meta">Until officer routing is connected, answer Yes or No here once you know to continue.</p>
        </div>
      ) : (
        <p className="meta">Not sure? It goes to the officer as an open question.</p>
      )}
    </article>
  );
}

export function CodeCheck() {
  const { c } = useCase();
  const open = unresolvedCandidates(c);
  const answered = c.candidates.length - open.length;
  return (
    <>
      <PanelHeader title="Code check" meta="NBC(AE) 2023 · 2nd printing" />
      <div className="pane scroll-body">
        <div className="column stack">
          <p className="meta">Answer each card in plain words. You do not need the article numbers.</p>
          {c.candidates.length ? (
            c.candidates.map((a) => <CandidateCard key={a.id} a={a} />)
          ) : (
            <p className="empty">No code rules to review yet. Describe your idea first.</p>
          )}
        </div>
      </div>
      <div className="footer-bar">
        <span className="status-note" role="status">
          {c.candidates.length > 0 && (
            <span className="mark-row" role="img" aria-label={`${answered} of ${c.candidates.length} answered`}>
              {c.candidates.map((a) => {
                const m = MARK[a.answer ?? "none"];
                return <StatusIcon key={a.id} kind={m.kind} size="sm" label="" decorative />;
              })}
            </span>
          )}
          {open.length > 0 && " Yes or No on each card to continue"}
        </span>
        <a className="btn btn-ghost" href="#/describe">
          Back
        </a>
        {open.length ? (
          <button type="button" className="btn btn-primary" disabled>
            Continue to application
          </button>
        ) : (
          <a className="btn btn-primary" href="#/section-c">
            Continue to application
          </a>
        )}
      </div>
    </>
  );
}
