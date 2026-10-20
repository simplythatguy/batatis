import { EXAMPLES } from "../examples";
import { applicantLabel } from "../intake";
import { useCase } from "../store";
import type { ApplicantType } from "../types";

const CHOICES: { id: ApplicantType; label: string; detail: string }[] = [
  {
    id: "manufacturer",
    label: "Manufacturer",
    detail: "A product you want builders to use. The case starts from the product, not from one house.",
  },
  {
    id: "contractor",
    label: "General contractor",
    detail: "One job that cannot follow an acceptable solution as written.",
  },
  {
    id: "homebuilder",
    label: "Homebuilder",
    detail: "A house or suite. Storeys and the site are the first questions.",
  },
];

export function Who() {
  const { beginEmpty, askExample, resetNote } = useCase();
  return (
    <>
      <header className="panel-header">
        <h1 className="panel-title">Who are you?</h1>
      </header>
      <div className="pane scroll-body">
        <div className="content-col stack">
          {resetNote && (
            <p className="field-note" role="status">
              {resetNote}
            </p>
          )}
          <p className="meta intro">
            Pick the role that fits this application. It starts empty. Nothing is filled in for you.
          </p>
          <div className="choice-list">
            {CHOICES.map((choice) => (
              <button key={choice.id} type="button" className="btn choice" onClick={() => beginEmpty(choice.id)}>
                <span className="choice-label">{choice.label}</span>
                <span className="meta">{choice.detail}</span>
              </button>
            ))}
          </div>
          <section aria-labelledby="examples-title">
            <h2 id="examples-title" className="section-title">
              Try an example
            </h2>
            <p className="meta">Saved cases you can open. They are not the starting application.</p>
            <ul className="plain-list">
              {EXAMPLES.map((ex) => (
                <li key={ex.id}>
                  <button type="button" className="btn" onClick={() => askExample(ex.id)}>
                    {ex.label}
                  </button>
                  <p className="meta">{ex.blurb}</p>
                </li>
              ))}
            </ul>
          </section>
          <p className="meta">Roles: {CHOICES.map((c) => applicantLabel(c.id)).join(", ")}.</p>
        </div>
      </div>
    </>
  );
}
