import { useRef } from "react";
import { DetailFields, ProcessFields } from "../case-parts";
import { GapStrip, PanelHeader } from "../components";
import type { Route } from "../router";
import { useCase } from "../store";

const TABS = [
  { id: "A", label: "Section A · Applicant" },
  { id: "B", label: "Section B · Project" },
  { id: "alt", label: "Alternative path" },
] as const;

export function Application({ route }: { route: Route }) {
  const { gaps } = useCase();
  const tab = route.params.get("tab") ?? "A";
  const dialog = useRef<HTMLDialogElement>(null);
  const blocking = gaps.filter((g) => g.severity === "blocking");
  const countFor = (t: string) =>
    blocking.filter((g) => g.href.startsWith(`#/application?tab=${t}&`)).length;

  return (
    <>
      <PanelHeader title="Application" meta="Variance template · Sections A, B and process fields" />
      <GapStrip gaps={gaps} />
      <div className="toolbar" role="tablist" aria-label="Application sections">
        {TABS.map((t) => {
          const n = countFor(t.id);
          return (
            <a
              key={t.id}
              role="tab"
              className="pill"
              href={`#/application?tab=${t.id}`}
              data-active={tab === t.id}
              aria-selected={tab === t.id}
            >
              {t.label}
              {n > 0 && <span className="tab-count">{n}</span>}
            </a>
          );
        })}
      </div>
      <div className="pane scroll-body" role="tabpanel">
        <div className="content-col">
          {tab === "alt" ? <ProcessFields /> : <DetailFields section={tab === "B" ? "B" : "A"} />}
        </div>
      </div>
      <div className="footer-bar">
        <span className="status-note" role="status">
          {blocking.length ? `Pre-flight opens when ${blocking.length} blocking gap${blocking.length > 1 ? "s are" : " is"} closed` : ""}
        </span>
        <a className="btn btn-ghost" href="#/section-c">
          Back
        </a>
        <button type="button" className="btn btn-primary" disabled={blocking.length > 0} onClick={() => dialog.current?.showModal()}>
          Run pre-flight
        </button>
      </div>
      <dialog className="dialog" ref={dialog}>
        <form method="dialog">
          <div className="dialog-body">
            <h2 className="dialog-title">No blocking gaps</h2>
            <p className="meta">
              Every required field has a value with a source, and every proposed item is confirmed. Filling the official
              SCC form arrives with the engine. This is an administrative check, not a finding that the design complies.
            </p>
          </div>
          <div className="footer-bar">
            <button type="submit" className="btn btn-primary">
              Close
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}
