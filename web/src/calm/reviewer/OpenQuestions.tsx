/** The applicant's saved answers and uncertainties, with their source. People decide what they mean. */
import type { ReviewQuestion } from "../../api/client";
import { Icon24 } from "../icons";

const STATE: Record<ReviewQuestion["state"], string> = {
  not_sure: "Applicant not sure",
  unanswered: "Not answered",
  unconfirmed: "Answer not confirmed",
  withdrawn: "Answer withdrawn",
  answered: "Answered",
};

function Question({ q }: { q: ReviewQuestion }) {
  return (
    <li className="rw-q">
      <p className="rw-q-t">{q.text}{q.provision_id && <span className="pr-mono"> · {q.provision_id}</span>}</p>
      <p>{q.answer ?? "—"} <span className="rw-note">· {STATE[q.state]}</span></p>
      {q.clarification && <p>Clarified: {q.clarification.answer ?? "—"} <span className="rw-note">· {STATE[q.clarification.state]}</span></p>}
      <p className="rw-note">{q.source}{q.source_detail ? ` · ${q.source_detail}` : ""}</p>
    </li>
  );
}

export function OpenQuestions({ questions, loading, error }: { questions: ReviewQuestion[]; loading: boolean; error: string }) {
  if (error) return <p className="rw-empty" role="status">{error}</p>;
  if (loading || !questions.length) return null;
  const open = questions.filter((q) => q.state !== "answered");
  const answered = questions.filter((q) => q.state === "answered");
  return (
    <section className="ap-sec" aria-label="Applicant’s questions">
      <h2 className="ap-sec-h">
        <span className="cf-sec-icon" aria-hidden="true"><Icon24 name="questions" size={18} /></span>
        <span>Questions<span className="cf-faint"> · Their answers</span></span>
      </h2>
      {open.length > 0 && <ul className="rw-qs">{open.map((q) => <Question key={q.id} q={q} />)}</ul>}
      {answered.length > 0 && (
        <details className="rw-fold">
          <summary>Answered · {answered.length}</summary>
          <ul className="rw-qs">{answered.map((q) => <Question key={q.id} q={q} />)}</ul>
        </details>
      )}
    </section>
  );
}
