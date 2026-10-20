import { useFocusParam, useRoute } from "./router";
import { Application } from "./screens/Application";
import { CodeCheck } from "./screens/CodeCheck";
import { Describe } from "./screens/Describe";
import { Accuracy, Officer } from "./screens/Placeholders";
import { resetCase, useCase } from "./store";
import type { ApplicantType } from "./types";

/** The three steps. Code check is the code-identification step and stays in the stepper;
 *  Section C (`#/section-c`) is a tab of Application but keeps its own deep link. */
const STEPS = [
  { path: "/describe", label: "Describe", routes: [] as string[] },
  { path: "/code-check", label: "Code check", routes: ["/code-check"] },
  { path: "/application", label: "Application", routes: ["/application", "/section-c"] },
];
const STEP_ROUTES = STEPS.flatMap((s) => s.routes);

/** Tertiary links under the steps. A screen that is still a placeholder on this branch stays
 *  out of the sidebar; its route still renders. Officer review and How we checked land with #16. */
const FOOT_LINKS = [
  { path: "/officer", label: "Officer view", ready: false },
  { path: "/accuracy", label: "How we checked", ready: false },
];

const ROLE: Record<ApplicantType, string> = {
  manufacturer: "Manufacturer",
  contractor: "Contractor",
  builder: "Builder",
  designer: "Designer",
  owner: "Owner",
};

export function App() {
  const route = useRoute();
  const { c, dispatch } = useCase();
  useFocusParam(route);

  let screen;
  switch (route.path) {
    case "/code-check":
      screen = <CodeCheck />;
      break;
    case "/section-c":
      screen = <Application route={route} tab="C" />;
      break;
    case "/application":
      screen = <Application route={route} />;
      break;
    case "/officer":
      screen = <Officer />;
      break;
    case "/accuracy":
      screen = <Accuracy />;
      break;
    default:
      screen = <Describe />;
  }
  const onFootLink = FOOT_LINKS.some((l) => l.path === route.path);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="workspace">
          <span className="logo" aria-hidden="true">
            B
          </span>
          Batatis
        </div>
        <nav className="nav" aria-label="Steps">
          <ol className="plain-list nav-group">
            {STEPS.map((s, i) => {
              const active = s.routes.length ? s.routes.includes(route.path) : !STEP_ROUTES.includes(route.path) && !onFootLink;
              return (
                <li key={s.path}>
                  <a className="nav-item" href={`#${s.path}`} data-active={active} aria-current={active ? "step" : undefined}>
                    <span className="step-num" aria-hidden="true">
                      {i + 1}
                    </span>
                    {s.label}
                  </a>
                </li>
              );
            })}
          </ol>
        </nav>
        <div className="sidebar-foot">
          <div className="case-card">
            <span className="case-title">{c.title}</span>
            <span className="meta">{ROLE[c.applicantType]} · Example data</span>
          </div>
          <p className="meta sidebar-line">Checks paperwork, not compliance.</p>
          <div className="foot-links">
            {FOOT_LINKS.filter((l) => l.ready).map((l) => (
              <a key={l.path} className="foot-link" href={`#${l.path}`} aria-current={route.path === l.path ? "page" : undefined}>
                {l.label}
              </a>
            ))}
            <button type="button" className="foot-link" onClick={() => resetCase(dispatch)}>
              Reset
            </button>
          </div>
        </div>
      </aside>
      <main className="main-panel">
        <div className="example-strip" role="note">
          <span className="example-label">EXAMPLE DATA</span>
          <span className="meta">
            · fictional · {ROLE[c.applicantType]} · {c.title}
          </span>
        </div>
        {screen}
      </main>
    </div>
  );
}
