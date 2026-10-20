import { PanelHeader } from "../components";

export function Officer() {
  return (
    <>
      <PanelHeader title="Officer review" meta="Safety Codes Officer" />
      <div className="pane scroll-body">
        <div className="content-col empty-state">
          <h2 className="section-title">Not built yet</h2>
          <p className="meta">
            Officers will open a Batatis case, or upload a completed SCC variance form with its attachments, and get a
            one-screen administrative completeness review with a drafted information request. It reviews completeness, not
            technical correctness.
          </p>
          <a className="btn" href="#/describe">
            Go to the applicant case
          </a>
        </div>
      </div>
    </>
  );
}

export function Accuracy() {
  return (
    <>
      <PanelHeader title="Accuracy report" />
      <div className="pane scroll-body">
        <div className="content-col empty-state">
          <h2 className="section-title">No evaluation runs yet</h2>
          <p className="meta">
            This page will list the guaranteed claims, then the measured ones as “x of y” with 95% intervals, built from the
            evaluation runs. Nothing is shown until a run exists.
          </p>
        </div>
      </div>
    </>
  );
}
