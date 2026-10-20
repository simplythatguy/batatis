import { PanelHeader } from "../components";

/* Not linked from the sidebar until the screens are built (#16); the routes still render. */

export function Officer() {
  return (
    <>
      <PanelHeader title="Officer view" />
      <div className="pane scroll-body">
        <div className="column empty-state">
          <p className="meta">The officer view is not in this build yet. An officer reviews and decides.</p>
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
      <PanelHeader title="How we checked" />
      <div className="pane scroll-body">
        <div className="column empty-state">
          <p className="meta">No evaluation runs in this build yet. Nothing is shown until a run exists.</p>
          <a className="btn" href="#/describe">
            Go to the applicant case
          </a>
        </div>
      </div>
    </>
  );
}
