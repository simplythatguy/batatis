import { useEffect, useRef } from "react";
import { Icon } from "./components";
import { EXAMPLE_BANNER } from "./rules";
import { useFocusParam, useRoute } from "./router";
import { Application } from "./screens/Application";
import { CodeCheck } from "./screens/CodeCheck";
import { Describe } from "./screens/Describe";
import { Accuracy } from "./screens/Accuracy";
import { Officer } from "./screens/Officer";
import { SectionC } from "./screens/SectionC";
import { Who } from "./screens/Who";
import { applicantLabel } from "./intake";
import { EXAMPLES } from "./examples";
import { useCase } from "./store";

const EXPLICIT_ROUTES = ["/code-check", "/section-c", "/application", "/officer", "/accuracy"];

const NAV = [
  {
    area: "Applicant",
    items: [
      { path: "/describe", label: "Describe", icon: "describe" },
      { path: "/code-check", label: "Code check", icon: "check" },
      { path: "/section-c", label: "Section C", icon: "table" },
      { path: "/application", label: "Application", icon: "application" },
    ],
  },
  { area: "Officer", items: [{ path: "/officer", label: "Officer review", icon: "officer" }] },
  { area: "Accuracy", items: [{ path: "/accuracy", label: "Accuracy report", icon: "accuracy" }] },
];

export function App() {
  const route = useRoute();
  const { c, phase, askExample, resetToWho, pendingExampleId, confirmExample, dismissExample } = useCase();
  const confirmDialog = useRef<HTMLDialogElement>(null);
  useFocusParam(route);
  const isDescribeRoute = !EXPLICIT_ROUTES.includes(route.path);
  useEffect(() => {
    const dialog = confirmDialog.current;
    if (!dialog) return;
    if (pendingExampleId && !dialog.open) dialog.showModal();
    if (!pendingExampleId && dialog.open) dialog.close();
  }, [pendingExampleId]);

  let screen;
  if (phase !== "case") {
    screen = <Who />;
  } else switch (route.path) {
    case "/code-check":
      screen = <CodeCheck />;
      break;
    case "/section-c":
      screen = <SectionC />;
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

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="workspace">
          <span className="logo" aria-hidden="true">
            B
          </span>
          Batatis
        </div>
        {phase === "case" && (
          <nav className="nav" aria-label="Main">
            {NAV.map((g) => (
              <div key={g.area} className="nav-section">
                <div className="sidebar-section-label">{g.area}</div>
                <div className="nav-group">
                  {g.items.map((i) => {
                    const active = route.path === i.path || (i.path === "/describe" && isDescribeRoute);
                    return (
                      <a
                        key={i.path}
                        className="nav-item"
                        href={`#${i.path}`}
                        data-active={active}
                        aria-current={active ? "page" : undefined}
                      >
                        <Icon name={i.icon} />
                        {i.label}
                      </a>
                    );
                  })}
                </div>
              </div>
            ))}
          </nav>
        )}
        <div className="sidebar-foot">
          <div className="case-card">
            <span className="case-title">{phase === "case" ? c.title || "New application" : "No case yet"}</span>
            <span className="meta">
              {phase === "case" ? `${applicantLabel(c.applicantType)} · ${c.authority || "Authority not selected"}` : "No case yet"}
            </span>
          </div>
          {phase === "case" && (
            <details className="example-menu">
              <summary>Try an example</summary>
              {EXAMPLES.map((ex) => (
                <button key={ex.id} type="button" className="btn btn-ghost" onClick={() => askExample(ex.id)}>
                  {ex.label}
                </button>
              ))}
            </details>
          )}
          <button type="button" className="btn btn-ghost" onClick={resetToWho}>
            Reset case
          </button>
        </div>
      </aside>
      <main className="main-panel">
        {phase === "case" && c.exampleId && (
          <p className="example-banner" role="status">
            <span className="status-dot warning" /> {EXAMPLE_BANNER}
          </p>
        )}
        {screen}
      </main>
      <dialog className="dialog" ref={confirmDialog} aria-labelledby="example-confirm-title" onClose={dismissExample}>
        <form method="dialog">
          <div className="dialog-body">
            <h2 className="dialog-title" id="example-confirm-title">Replace your case with an example?</h2>
            <p className="meta">Your description and answers will be cleared. The example stays labelled as an example and is not a real application.</p>
          </div>
          <div className="footer-bar">
            <button type="button" className="btn" onClick={dismissExample}>
              Keep my case
            </button>
            <button type="button" className="btn btn-primary" onClick={confirmExample}>
              Replace with the example
            </button>
          </div>
        </form>
      </dialog>
    </div>
  );
}
