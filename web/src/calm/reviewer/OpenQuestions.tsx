/** Applicant statements stay visible beside their source; only people determine what they mean. */
import type { ReviewQuestion } from "../../api/client";

const STATE: Record<ReviewQuestion["state"], string> = {
  not_sure: "Open · applicant is not sure",
  unanswered: "Open · not answered",
  unconfirmed: "Open · answer not confirmed by applicant",
  withdrawn: "Open · answer withdrawn",
  answered: "Applicant answered · officer review remains",
};

function Question({ q }: { q: ReviewQuestion }) {
  return <div className="ac-sheet-question">
    <p className="cf-sheet-p"><strong>{q.text}</strong>{q.provision_id && <><br /><span className="cf-sheet-ref">{q.provision_id}</span></>}</p>
    <p className="cf-sheet-p">Applicant answer: {q.answer ?? "No answer supplied"}<br /><span className="cf-sheet-flag">{STATE[q.state]}</span></p>
    {q.clarification && <p className="cf-sheet-p">Applicant clarification: {q.clarification.answer ?? "No answer supplied"}<br /><span className="cf-sheet-flag">{STATE[q.clarification.state]}</span></p>}
    <details>
      <summary>Source · {q.source}</summary>
      {q.source_detail && <p className="cf-sheet-p">{q.source_detail}</p>}
      {q.clarification && <p className="cf-sheet-p">Clarification source: {q.clarification.source}{q.clarification.source_detail ? ` · ${q.clarification.source_detail}` : ""}</p>}
    </details>
  </div>;
}

export function OpenQuestions({ questions, loading, error }: { questions: ReviewQuestion[]; loading: boolean; error: string }) {
  // A clarification never conceals the original abstention or acts as an officer determination.
  const open = questions.filter(q => q.state !== "answered");
  const answered = questions.filter(q => q.state === "answered");
  return <section className="ac-sheet-questions" aria-label="Applicant questions and answers">
    <h4>Questions for the officer</h4>
    <p className="cf-sheet-note">Saved applicant answers and uncertainties. They do not determine code applicability or equivalent performance. Request clarification from the Decide step (Return with a message).</p>
    {error ? <p className="cf-sheet-p" role="status">{error}</p>
      : loading ? <p className="cf-sheet-p" role="status">Loading saved questions…</p>
      : <>
        {open.length ? open.map(q => <Question key={q.id} q={q} />) : <p className="cf-sheet-p">No open contextual questions recorded.</p>}
        {answered.length > 0 && <details>
          <summary>Applicant answers · {answered.length}</summary>
          {answered.map(q => <Question key={q.id} q={q} />)}
        </details>}
      </>}
  </section>;
}
