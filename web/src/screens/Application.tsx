import { useRef, useState } from "react";
import { DetailFields, ProcessFields } from "../case-parts";
import { GapList, PanelHeader, STATUS_WORDS, StatusIcon, splitGaps, worstStatus, type Status } from "../components";
import { unresolvedCandidates } from "../model";
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
  const { c, gaps } = useCase();
  const tab = forced ?? TABS.find((t) => t.id === route.params.get("tab"))?.id ?? "A";
  const dialog = useRef<HTMLDialogElement>(null);
  // Empty fields turn red only after a completeness check, never on load.
  const [checked, setChecked] = useState(false);
  const { blocking, info } = splitGaps(gaps);
  // Each tab carries its worst mark. C has no gaps of its own: rows waiting in Code check need attention.
  const markFor = (t: TabId): Status =>
    t === "C"
      ? unresolvedCandidates(c).length
        ? "attention"
        : "ok"
      : worstStatus(gaps.filter((g) => g.href.startsWith(`#/application?tab=${t}&`)));
  const label = TABS.find((t) => t.id === tab)!.label;
  const close = () => dialog.current?.close();

  return (
    <>
      <PanelHeader title="Application" />
      <nav className="toolbar" aria-label="Application sections">
        {TABS.map((t) => {
          const s = markFor(t.id);
          return (
            <a key={t.id} className="pill" href={t.href} data-active={tab === t.id} aria-current={tab === t.id ? "page" : undefined}>
              <StatusIcon status={s} size="sm" label={STATUS_WORDS[s]} />
              {t.label}
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
            <div className="dialog-head">
              {blocking.length ? (
                <StatusIcon status="blocked" size="lg" label="Blocks the form" />
              ) : (
                <StatusIcon status="ok" size="lg" label="Nothing blocking" />
              )}
              <h2 className="dialog-title" id="completeness-title">
                {blocking.length ? `${blocking.length} item${blocking.length > 1 ? "s" : ""} to fix` : "No blocking items"}
              </h2>
            </div>
            {/* Above the list, so a long list never pushes it out of view (Unc6 #4). */}
            <p className="dialog-notice" id="completeness-description">
              Checks that information is present. Not a finding that the design complies.
            </p>
            {blocking.length > 0 ? (
              <div className="fix-list">
                <GapList gaps={blocking} fix onGo={close} />
              </div>
            ) : (
              <p className="meta">
                Every required field has a value with a source, and every guess is confirmed. Filling the official SCC
                form arrives with the engine.
              </p>
            )}
            {info.length > 0 && (
              <section className="drawer-group" aria-label="For your information, not counted">
                <h3 className="drawer-group-title">For your information · not counted</h3>
                <GapList gaps={info} onGo={close} />
              </section>
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
