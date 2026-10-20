import { PanelHeader, StatusPill } from "../components";
import { displayValue, factLabel } from "../model";
import { useCase } from "../store";

const README_LINE =
  "Engineer-needed flag (model-checked): rules_only 55/60 on the dev set (in-sample), 1 under-flag; shipped rules_plus_unknown: 50/60 in-sample, 0 under-flags, 27 unknowns sent to the applicant; held-out 7/8 blind (pre-fix), post-fix 4/8 (no longer blind).";

/** The README line, with the text-only construction note after the shipped 0 under-flags. */
const SHIPPED_LABEL = README_LINE.replace(
  "0 under-flags,",
  "0 under-flags (on text-only cases it answers only yes or ask, never no, so 0 under-flags holds by construction),",
);

/** Proposed facts the model suggested. Confirmation is the applicant's, not a score. */
export function Accuracy() {
  const { c } = useCase();
  const proposed = c.facts.filter((f) => f.kind === "proposed");
  const confirmed = c.facts.filter((f) => f.status === "confirmed" && f.kind !== "proposed");
  return (
    <>
      <PanelHeader title="Accuracy report" meta="Model-checked" />
      <div className="pane scroll-body">
        <div className="content-col stack">
          <p className="meta intro">
            A proposal stays here until you accept it. Accepting it does not mean the design complies or is safe.
          </p>
          <p>{SHIPPED_LABEL}</p>
          <p className="meta">Checked by a model, not by a person.</p>
          <p>
            <StatusPill dot="warning">{proposed.length} still proposed</StatusPill>{" "}
            <StatusPill dot="done">
              {c.exampleId ? `${confirmed.length} set in this example` : `${confirmed.length} confirmed by you or typed by you`}
            </StatusPill>
          </p>
          <details>
            <summary>Technical detail</summary>
            <p>{SHIPPED_LABEL}</p>
          </details>
          {proposed.length === 0 ? (
            <p className="empty">No model proposals are waiting.</p>
          ) : (
            <ul className="plain-list">
              {proposed.map((f) => (
                <li key={f.id} id={`model-${f.id}`}>
                  <span className="status-dot warning" /> {factLabel(f.field)}: {f.value == null ? "—" : displayValue(f)}
                  {f.confidence != null && <span className="meta"> Confidence {Math.round(f.confidence * 100)}%</span>}
                  <div className="meta">{f.status === "confirmed" ? "Confirmed" : "Needs your check"} · {f.source.ref}</div>
                </li>
              ))}
            </ul>
          )}
          <a className="btn" href="#/describe">
            Review them on Describe
          </a>
        </div>
      </div>
    </>
  );
}
