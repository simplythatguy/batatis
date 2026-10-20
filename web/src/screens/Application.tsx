import { useRef, useState } from "react";
import { DetailFields, ProcessFields } from "../case-parts";
import { PanelHeader } from "../components";
import type { Route } from "../router";
import { useCase } from "../store";
import { SectionCBody } from "./SectionC";

type TabId = "A" | "B" | "C" | "alt";

/** Section C keeps its own deep link (`#/section-c`); the other tabs are `#/application?tab=…`. */
const TABS: { id: TabId; label: string; href: string }[] = [
  { id: "A", label: "Section A · Applicant", href: "#/application?tab=A" },
  { id: "B", label: "Section B · Project", href: "#/application?tab=B" },
  { id: "C", label: "Section C · Objectives and functions", href: "#/section-c" },
  { id: "alt", label: "Alternative path", href: "#/application?tab=alt" },
];

export function Application({ route, tab: forced }: { route: Route; tab?: TabId }) {
  const { gaps } = useCase();
  const tab = forced ?? TABS.find((t) => t.id === route.params.get("tab"))?.id ?? "A";
  const dialog = useRef<HTMLDialogElement>(null);
  // Empty fields turn red only after a completeness check, never on load.
  const [checked, setChecked] = useState(false);
  const blocking = gaps.filter((g) => g.severity === "blocking");
  const countFor = (t: TabId) => blocking.filter((g) => g.href.startsWith(`#/application?tab=${t}&`)).length;
  const label = TABS.find((t) => t.id === tab)!.label;

  return (
    <>
      <PanelHeader title="Application" />
      <nav className="toolbar" aria-label="Application sections">
        {TABS.map((t) => {
          const n = countFor(t.id);
          return (
            <a key={t.id} className="pill" href={t.href} data-active={tab === t.id} aria-current={tab === t.id ? "page" : undefined}>
              {t.label}
              {n > 0 && <span className="tab-count">{n}</span>}
            </a>
          );
        })}
      </nav>
      <div className="pane scroll-body" role="region" aria-label={label}>
        <div className={`column ${checked ? "checked" : ""}`}>
          {tab === "C" ? <SectionCBody /> : tab === "alt" ? <ProcessFields /> : <DetailFields section={tab} />}
        </div>
      </div>
      <div className="footer-bar">
        <span className="status-note" role="status">
          {blocking.length ? `${blocking.length} to fix before the form can be filled` : "Nothing blocking"}
        </span>
        <a className="btn btn-ghost" href="#/code-check">
          Back
        </a>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => {
            setChecked(true);
            dialog.current?.showModal();
          }}
        >
          Check completeness
        </button>
      </div>
      <dialog className="dialog" ref={dialog} aria-labelledby="completeness-title" aria-describedby="completeness-description">
        <form method="dialog">
          <div className="dialog-body">
            <h2 className="dialog-title" id="completeness-title">
              {blocking.length ? `${blocking.length} item${blocking.length > 1 ? "s" : ""} to fix` : "No blocking items"}
            </h2>
            <p className="meta" id="completeness-description">
              Checks that information is present. Not a finding that the design complies.
            </p>
            {blocking.length > 0 ? (
              <ul className="plain-list fix-list">
                {blocking.map((g) => (
                  <li key={g.id}>
                    <a className="drawer-row" href={g.href} onClick={() => dialog.current?.close()}>
                      <span className="status-dot blocking" />
                      <span className="fix-label">{g.label}</span>
                      <span className="meta">Fix</span>
                    </a>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="meta">
                Every required field has a value with a source, and every guess is confirmed. Filling the official SCC
                form arrives with the engine.
              </p>
            )}
          </div>
          <div className="footer-bar">
            <span className="status-note">Example data · fictional</span>
            <button type="submit" className="btn btn-primary">
              Close
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}
