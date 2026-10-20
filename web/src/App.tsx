import { Icon } from "./components";
import { useFocusParam, useRoute } from "./router";
import { Application } from "./screens/Application";
import { CodeCheck } from "./screens/CodeCheck";
import { Describe } from "./screens/Describe";
import { Accuracy, Officer } from "./screens/Placeholders";
import { SectionC } from "./screens/SectionC";
import { resetCase, useCase } from "./store";

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
  const { c, dispatch } = useCase();
  useFocusParam(route);
  const isDescribeRoute = !EXPLICIT_ROUTES.includes(route.path);

  let screen;
  switch (route.path) {
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
        <div className="sidebar-foot">
          <div className="case-card">
            <span className="case-title">{c.title}</span>
            <span className="meta">Fixture case · fictional applicant</span>
          </div>
          <button type="button" className="btn btn-ghost" onClick={() => resetCase(dispatch)}>
            Reset case
          </button>
        </div>
      </aside>
      <main className="main-panel">{screen}</main>
    </div>
  );
}
