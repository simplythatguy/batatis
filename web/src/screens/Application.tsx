import { useRef, useState } from "react";
import { EngineError, ExportBlockedError, engine } from "../api/client";
import { EXAMPLE_EXPORT_BLOCK, exampleExportBlocked, failureKind } from "../rules";
import { DetailFields, ProcessFields } from "../case-parts";
import { DemoFallback, DraftNote, GapStrip, PanelHeader } from "../components";
import type { Route } from "../router";
import { useCase } from "../store";
import { Recommendations } from "./Recommendations";

const TABS = [
  { id: "A", label: "Section A" },
  { id: "B", label: "Section B" },
  { id: "alt", label: "Alternative path" },
  { id: "D", label: "Section D" },
] as const;

export function Application({ route }: { route: Route }) {
  const { gaps, engineId, saveDraft, c } = useCase();
  const tab = TABS.find((t) => t.id === route.params.get("tab"))?.id ?? "A";
  const dialog = useRef<HTMLDialogElement>(null);
  const [exportNote, setExportNote] = useState("Check completeness saves the case, then asks the engine for the PDF.");
  const [exportUnreachable, setExportUnreachable] = useState(false);
  const [reasons, setReasons] = useState<string[]>([]);
  const [exportFailed, setExportFailed] = useState(false);
  const blocking = gaps.filter((g) => g.severity === "blocking");
  const exampleBlocked = exampleExportBlocked(c.exampleId);
  const countFor = (t: string) =>
    blocking.filter((g) => g.href.includes(`tab=${t}`)).length;

  async function runExport() {
    if (exampleExportBlocked(c.exampleId)) {
      setExportNote(EXAMPLE_EXPORT_BLOCK);
      setExportFailed(false);
      dialog.current?.showModal();
      return;
    }
    setReasons([]);
    setExportFailed(false);
    setExportUnreachable(false);
    setExportNote("Saving the case, then asking the engine for the PDF…");
    dialog.current?.showModal();
    const caseId = engineId ?? (await saveDraft());
    if (!caseId) {
      setExportFailed(true);
      setExportNote("The engine did not open a case, so export was not called. You can still download the draft record below.");
      return;
    }
    try {
      const file = await engine.exportPdf(caseId, false);
      const url = URL.createObjectURL(file.blob);
      const a = Object.assign(document.createElement("a"), { href: url, download: file.filename });
      document.body.append(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 0);
      setExportNote(`Downloaded ${file.filename}. This is the engine PDF, not a finding that the design complies.`);
    } catch (e) {
      if (e instanceof ExportBlockedError) {
        setReasons(e.reasons);
        setExportNote(`${e.message} The official PDF stays closed while these are open.`);
      } else {
        const unreachable = e instanceof EngineError && failureKind(e.status, e.detail) === "unreachable";
        setExportFailed(true);
        setExportUnreachable(unreachable);
        setExportNote(e instanceof EngineError ? e.detail : "The engine could not be reached.");
      }
    }
  }

  function downloadRecord() {
    const text = [
      ...(c.exampleId ? ["EXAMPLE, NOT A REAL APPLICATION"] : []),
      c.title,
      c.description,
      "",
      ...c.facts.map((f) => `${f.field}: ${f.value ?? ""} (${f.kind}, ${f.status})`),
      "",
      "Not the Safety Codes Council form. The engine did not return that PDF.",
    ].join("\n");
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = Object.assign(document.createElement("a"), { href: url, download: `${c.id}-draft-record.txt` });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 0);
    setExportNote(`Downloaded ${c.id}-draft-record.txt. This is the browser record, not the SCC form.`);
  }

  return (
    <>
      <PanelHeader title="Application" meta="Variance template · Sections A, B and process fields" />
      <GapStrip gaps={gaps} />
      <nav className="toolbar" aria-label="Application sections">
        {TABS.map((t) => {
          const n = countFor(t.id);
          return (
            <a
              key={t.id}
              className="pill"
              href={`#/application?tab=${t.id}`}
              data-active={tab === t.id}
              aria-current={tab === t.id ? "page" : undefined}
            >
              {t.label}
              {n > 0 && <span className="tab-count">{n}</span>}
            </a>
          );
        })}
      </nav>
      <div className="pane scroll-body" role="region" aria-label={TABS.find((t) => t.id === tab)?.label}>
        <div className="content-col stack">
          {tab === "D" || tab === "alt" ? (
            <>
              <ProcessFields />
              <Recommendations />
            </>
          ) : (
            <DetailFields section={tab === "B" ? "B" : "A"} />
          )}
        </div>
      </div>
      <div className="footer-bar">
        <DraftNote />
        <span className="status-note" role="status">
          {exampleBlocked
            ? EXAMPLE_EXPORT_BLOCK
            : blocking.length
              ? `Close ${blocking.length} blocking gap${blocking.length > 1 ? "s" : ""} to check completeness`
              : "Completeness check is open."}
        </span>
        <a className="btn btn-ghost" href="#/section-c">
          Back
        </a>
        <button type="button" className="btn" onClick={() => void saveDraft()}>
          Save draft
        </button>
        {blocking.length > 0 && (
          <a className="btn" href={blocking[0].href}>
            Review the first gap
          </a>
        )}
        <button
          type="button"
          className="btn btn-primary"
          disabled={blocking.length > 0 || exampleBlocked}
          data-requires-no-blocking-gaps={blocking.length > 0 ? "true" : undefined}
          onClick={() => void runExport()}
        >
          Check completeness
        </button>
      </div>
      <dialog className="dialog" ref={dialog} aria-labelledby="completeness-title" aria-describedby="completeness-description">
        <form method="dialog">
          <div className="dialog-body">
            <h2 className="dialog-title" id="completeness-title">Check completeness</h2>
            <p className="meta" id="completeness-description">{exportNote}</p>
            {reasons.length > 0 && (
              <ul className="plain-list">
                {reasons.map((r) => (
                  <li key={r}>
                    <span className="status-dot blocking" /> {r}
                  </li>
                ))}
              </ul>
            )}
            <p className="meta">An administrative check does not decide that the design complies or is safe.</p>
            {exportFailed && exportUnreachable && (
              <DemoFallback reason="The engine could not be reached, so no PDF came back." onRetry={() => void runExport()} />
            )}
          </div>
          <div className="footer-bar">
            <button type="button" className="btn" onClick={downloadRecord}>
              Download draft record
            </button>
            <button type="submit" className="btn btn-primary">
              Close
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}
