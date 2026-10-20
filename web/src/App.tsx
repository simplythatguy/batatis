import { useEffect, useRef, useState } from "react";
import { Icon } from "./components";
import { useFocusParam, useRoute } from "./router";
import { Application } from "./screens/Application";
import { CodeCheck } from "./screens/CodeCheck";
import { Describe } from "./screens/Describe";
import { Accuracy } from "./screens/Accuracy";
import { Officer } from "./screens/Officer";
import { SectionC } from "./screens/SectionC";
import { Who } from "./screens/Who";
import { applicantLabel } from "./intake";
import { AUTHORITIES } from "./config";
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
  const { c, phase, resetToWho } = useCase();
  const resetDialog = useRef<HTMLDialogElement>(null);
  const [resetOpen, setResetOpen] = useState(false);
  useFocusParam(route);
  const isDescribeRoute = !EXPLICIT_ROUTES.includes(route.path);
  useEffect(() => {
    const dialog = resetDialog.current;
    if (!dialog) return;
    if (resetOpen && !dialog.open) dialog.showModal();
    if (!resetOpen && dialog.open) dialog.close();
  }, [resetOpen]);

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
    <div className={`app-shell${phase === "who" ? " onboarding-shell" : ""}`}>
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
            <span className="case-title">{phase === "case" ? c.title || "New application" : ""}</span>
            <span className="meta">
              {phase === "case" ? `${applicantLabel(c.applicantType)} · ${AUTHORITIES.find((a) => a.id === c.authority)?.name ?? "Authority not selected"}` : ""}
            </span>
          </div>
          <button type="button" className="btn btn-ghost" onClick={() => setResetOpen(true)}>
            Reset case
          </button>
        </div>
      </aside>
      <main className="main-panel">
        {screen}
      </main>
      <dialog className="dialog" ref={resetDialog} aria-labelledby="reset-confirm-title" onClose={() => setResetOpen(false)}>
        <form method="dialog">
          <div className="dialog-body">
            <h2 className="dialog-title" id="reset-confirm-title">Clear this case?</h2>
            <p className="meta">This clears your current visit. Download a copy first if you need it.</p>
          </div>
          <div className="footer-bar">
            <button type="button" className="btn" onClick={() => resetDialog.current?.close()}>
              Keep this case
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => {
                resetDialog.current?.close();
                resetToWho();
              }}
            >
              Reset case
            </button>
          </div>
        </form>
      </dialog>

    </div>
  );
}
