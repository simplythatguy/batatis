import { keywordGroups } from "../provisions";
import type { Case } from "../types";
import type { DrawerState } from "./CodeDrawer";
import { CIcon } from "./ui";

/** Progressive disclosure preserves every returned lead and sentence without a mandatory sentence deck. */
export function KeywordTriage({ c, openDrawer }: { c: Case; openDrawer: (s: DrawerState) => void }) {
  return (
    <div className="cf-keyword-triage">
      <p className="cf-faint cf-small">Unanswered stays unanswered. Not sure records your uncertainty for the officer. Neither confirms a code reference.</p>
      {keywordGroups(c).map((g) => (
        <details className="cf-triage-topic" key={g.article}>
          <summary>{g.title} <span className="cf-faint cf-small">· {g.article} · {g.candidates.length} {g.candidates.length === 1 ? "sentence" : "sentences"}</span></summary>
          <ul className="cf-rows is-compact">
            {g.candidates.map((a) => (
              <li className="cf-row" key={a.id}>
                <div className="cf-row-text">
                  <span className="cf-mono cf-small">{a.provision}</span>
                  <p className="cf-faint cf-small">{a.pending ? "Answer not saved" : a.answer === "not-sure" ? "Not sure · for the officer" : a.answer === "yes" ? "Departure confirmed" : a.answer === "no" ? "Not a departure" : "Unanswered keyword lead"}</p>
                </div>
                <button type="button" className="cf-row-go" onClick={() => openDrawer({ mode: "code", candidateId: a.id })}>Show code</button>
                <a className="cf-row-go" href={`#/questions?focus=${encodeURIComponent(`cand-${a.id}`)}`}>Review <CIcon name="arrow" size={13} /></a>
              </li>
            ))}
          </ul>
        </details>
      ))}
      <div className="cf-row-actions">
        <button type="button" className="cf-btn" onClick={() => openDrawer({ mode: "search" })}><CIcon name="search" size={14} />Find the rule yourself</button>
        <a className="cf-btn is-ghost" href="#/code">Open the code library</a>
      </div>
    </div>
  );
}
