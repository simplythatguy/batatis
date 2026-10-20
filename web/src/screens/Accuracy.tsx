import { PanelHeader, StatusPill } from "../components";
import { factLabel } from "../model";
import { useCase } from "../store";

/** Proposed facts the model suggested. Confirmation is the applicant's, not a score. */
export function Accuracy() {
  const { c } = useCase();
  const proposed = c.facts.filter((f) => f.kind === "proposed");
  const confirmed = c.facts.filter((f) => f.status === "confirmed" && f.kind !== "proposed");
  return (
    <>
      <PanelHeader title="Model-checked" meta="Proposals only" />
      <div className="pane scroll-body">
        <div className="content-col stack">
          <p className="meta intro">
            Model-checked means a proposal is on the ledger with a confidence and a source. It is not confirmed until you accept it, and it is not a finding that the design complies or is safe.
          </p>
          <p>
            <StatusPill dot="warning">{proposed.length} still proposed</StatusPill>{" "}
            <StatusPill dot="done">{confirmed.length} confirmed by you or typed by you</StatusPill>
          </p>
          {proposed.length === 0 ? (
            <p className="empty">No model proposals are waiting.</p>
          ) : (
            <ul className="plain-list">
              {proposed.map((f) => (
                <li key={f.id} id={`model-${f.id}`}>
                  <span className="status-dot warning" /> {factLabel(f.field)}: {f.value == null ? "—" : String(f.value)}
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
