import { useRef, useState } from "react";
import { EngineError, ExportBlockedError, engine } from "../api/client";
import { DetailFields, ProcessFields } from "../case-parts";
import { MissingItems } from "../completenessView";
import { DraftNote, GapStrip, PanelHeader } from "../components";
import { EXAMPLES } from "../examples";
import { displayValue, factLabel, plainFactStatus } from "../model";
import { UNSIGNED_LINE, pdfOutcomeLine, textRecord } from "../humanReview";
import type { Route } from "../router";
import { useCase } from "../store";
import type { Gap } from "../types";
import { Recommendations } from "./Recommendations";

const TABS = [
  { id: "A", label: "Section A" },
  { id: "B", label: "Section B" },
  { id: "alt", label: "Alternative path" },
  { id: "D", label: "Section D" },
] as const;

type Stage = "idle" | "checking" | "preparing" | "blocked" | "error" | "ready";

export function Application({ route }: { route: Route }) {
  const { gaps, saveDraft, c, gapsSource, syncOk, reviewDetail, engineGaps, readSync, readGaps, setCompletenessRecord } = useCase();
  const tab = TABS.find((t) => t.id === route.params.get("tab"))?.id ?? "A";
  const dialog = useRef<HTMLDialogElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const [stage, setStage] = useState<Stage>("idle");
  const [draftIntent, setDraftIntent] = useState(false);
  const [reasons, setReasons] = useState<string[]>([]);
  const [tech, setTech] = useState("");
  const [statusText, setStatusText] = useState("Review missing or unconfirmed information before downloading the application PDF.");
  const [file, setFile] = useState<{ url: string; name: string; draft: boolean; downloadedAt: Date } | null>(null);
  const [exportAttempted, setExportAttempted] = useState(false);
  const blocking = gaps.filter((g) => g.severity === "blocking");
  const warnings = gaps.filter((g) => g.severity === "warning").length;
  const example = EXAMPLES.find((ex) => ex.id === c.exampleId);
  const exampleLabel = example?.label ?? "Loaded example";
  const subject = c.exampleId ? "this example" : "your application";
  const blank = !c.description.trim() && c.facts.length === 0;
  const officialReady = !c.exampleId && syncOk && gapsSource === "engine" && blocking.length === 0;
  const countFor = (t: string) => blocking.filter((g) => g.href.includes(`tab=${t}`)).length;

  const sectionById = new Map(engineGaps.map((gap) => [gap.id, gap.section]));

  function forgetFile() {
    setFile((current) => {
      if (current) URL.revokeObjectURL(current.url);
      return null;
    });
  }

  function openCheck() {
    setReasons([]);
    setTech("");
    setDraftIntent(false);
    setExportAttempted(false);
    forgetFile();
    setStage("checking");
    setStatusText(`Saving and reviewing ${subject}…`);
    dialog.current?.showModal();
    void saveDraft().then((id) => {
      if (!dialog.current?.open) return;
      const sync = readSync();
      const blockers = readGaps().filter((gap) => gap.severity === "blocking");
      if (!id || !sync.reviewed) {
        const note = "Online review unavailable.";
        setTech(sync.detail);
        setStage("error");
        setStatusText(note);
        setCompletenessRecord({ label: "Online review unavailable", reasons: [], note });
        return;
      }
      if (c.exampleId) {
        const note = "Example: PDF not offered.";
        setStage("blocked");
        setStatusText(note);
        setCompletenessRecord({ label: "Not exported yet", reasons: [], note });
        return;
      }
      if (blockers.length) {
        const note = `Not exported yet. Official PDF closed while ${blockers.length} required item${blockers.length === 1 ? "" : "s"} remain.`;
        setStage("blocked");
        setStatusText("Not exported yet.");
        setCompletenessRecord({ label: "Not exported yet", reasons: [], note });
        return;
      }
      setStage("idle");
      setStatusText("No blocking administrative items found. Review any open questions before downloading.");
      setCompletenessRecord({ label: "Not exported yet", reasons: [], note: "No export has been requested yet." });
    });
  }

  async function prepare(draft: boolean) {
    setDraftIntent(draft);
    setReasons([]);
    setTech("");
    setExportAttempted(true);
    forgetFile();
    if (c.exampleId) {
      const note = "Example: PDF not offered.";
      setStage("blocked");
      setStatusText(note);
      setCompletenessRecord({ label: "Not exported yet", reasons: [], note });
      return;
    }
    if (!draft && !officialReady) {
      const note = "Some required information is missing or unconfirmed. The reasons are the missing items in this record.";
      setStage("blocked");
      setStatusText(note);
      setCompletenessRecord({ label: "Export blocked", reasons: [], note });
      return;
    }
    const ctl = new AbortController();
    abortRef.current = ctl;
    setStage("checking");
    setStatusText(`Saving and reviewing ${subject}…`);
    const caseId = await saveDraft();
    if (ctl.signal.aborted) return;
    if (!caseId) {
      setStage("error");
      setTech(reviewDetail);
      setStatusText("Online review unavailable.");
      return;
    }
    setStage("preparing");
    setStatusText(draft ? "Preparing your draft PDF…" : "Preparing your application PDF…");
    try {
      const got = await engine.exportPdf(caseId, draft, ctl.signal);
      if (ctl.signal.aborted) return;
      const url = URL.createObjectURL(got.blob);
      if (draft) {
        const note = "Your draft PDF is ready. This draft may have missing or unconfirmed information.";
        setCompletenessRecord({ label: "Draft", reasons: [], note });
      } else {
        setCompletenessRecord({
          label: "Application PDF",
          reasons: [],
          note: `${UNSIGNED_LINE} This does not decide whether the design complies or is safe.`,
        });
      }
      const a = Object.assign(document.createElement("a"), { href: url, download: got.filename });
      document.body.append(a);
      a.click();
      a.remove();
      setFile({ url, name: got.filename, draft, downloadedAt: new Date() });
      setStage("ready");
      setStatusText(draft ? "Your draft PDF is ready." : "Your application PDF is ready.");
    } catch (e) {
      if (ctl.signal.aborted) return;
      if (e instanceof ExportBlockedError) {
        const note = "The PDF was blocked. Review the current missing items below. The full response is in Technical detail.";
        setReasons(e.reasons);
        setTech(e.reasons.join("\n"));
        setStage("blocked");
        setStatusText(note);
        setCompletenessRecord({ label: "Export blocked", reasons: e.reasons, note });
        return;
      }
      const detail = e instanceof EngineError ? e.detail : "";
      const missingForm = e instanceof EngineError && (e.status === 503 || /missing a file/i.test(detail));
      const note = missingForm
        ? "The application PDF form is unavailable. Download a text record or try again later."
        : "The PDF could not be prepared.";
      setTech(detail);
      setStage("error");
      setStatusText(note);
      setCompletenessRecord({ label: "Export blocked", reasons: [], note });
    }
  }

  function downloadRecord() {
    const pdfLines = pdfOutcomeLine({
      example: Boolean(c.exampleId),
      downloaded: file ? { name: file.name, draft: file.draft, at: file.downloadedAt.toLocaleString() } : null,
      exportAttempted: exportAttempted && !c.exampleId,
      blockingCount: blocking.length,
    });
    if (exportAttempted && !file && reasons.length) pdfLines.push(...reasons.map((reason) => `- ${reason}`));
    const text = textRecord({
      exampleLabel: c.exampleId ? exampleLabel : undefined,
      title: c.title,
      description: c.description,
      factLines: c.facts.map((f) => `${factLabel(f.field)}: ${displayValue(f)} (${plainFactStatus(f.kind, f.status)})`),
      blockingCount: blocking.length,
      warningCount: warnings,
      checkedAt: new Date().toLocaleString(),
      pdfLines,
    });
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const name = `${c.exampleId ? "EXAMPLE-" : ""}${c.id}-text-record.txt`;
    const a = Object.assign(document.createElement("a"), { href: url, download: name });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 0);
    const line = `Download started: ${name}. A text record is not the Safety Codes Council form.`;
    setStatusText((current) => (stage === "blocked" || stage === "error" ? `${current} ${line}` : line));
  }

  function downloadAgain() {
    if (!file) return;
    const a = Object.assign(document.createElement("a"), { href: file.url, download: file.name });
    document.body.append(a);
    a.click();
    a.remove();
  }

  function reviewFirst() {
    const href = blocking[0]?.href ?? "#/describe";
    dialog.current?.close();
    location.hash = href.startsWith("#") ? href : `#${href}`;
  }

  function follow(gap: Gap) {
    dialog.current?.close();
    location.hash = gap.href.startsWith("#") ? gap.href : `#${gap.href}`;
  }

  const busy = stage === "checking" || stage === "preparing";
  const gapCount = `${blocking.length} required item${blocking.length === 1 ? "" : "s"} need attention. Check completeness stays available so you can review them. The official PDF stays closed until they are cleared.`;
  const footerLine =
    gapsSource === "idle"
      ? `Your application has not been reviewed online yet. ${gapCount}`
      : blocking.length
        ? gapCount
        : gapsSource === "engine"
          ? `No blocking administrative items found. Review any open questions before downloading.${warnings ? ` ${warnings} open question${warnings === 1 ? "" : "s"}.` : ""}`
          : "";

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
          {tab === "D" ? (
            <Recommendations />
          ) : tab === "alt" ? (
            <ProcessFields />
          ) : (
            <DetailFields section={tab === "B" ? "B" : "A"} />
          )}
        </div>
      </div>
      <div className="footer-bar">
        <DraftNote />
        <span className="status-note" role="status">
          {footerLine}
        </span>
        <a className="btn btn-ghost" href="#/section-c">
          Back
        </a>
        <button type="button" className="btn" onClick={() => void saveDraft()}>
          Save draft
        </button>
        <button type="button" className="btn btn-primary" disabled={busy} onClick={openCheck}>
          Check completeness
        </button>
      </div>
      <dialog
        className="dialog"
        ref={dialog}
        aria-labelledby="completeness-title"
        aria-describedby="completeness-description"
        onClose={() => abortRef.current?.abort()}
      >
        <form method="dialog">
          <div className="dialog-body">
            <div className="dialog-head">
              <h2 className="dialog-title" id="completeness-title">
                Check completeness
              </h2>
              <button type="submit" className="btn">
                {stage === "preparing" ? "Cancel download" : "Close"}
              </button>
            </div>
            <p>This is an administrative completeness check. It does not decide whether the design complies or is safe.</p>
            {stage === "ready" && file && !file.draft && <p>{UNSIGNED_LINE}</p>}
            {c.exampleId && (
              <p className="example-banner-title">
                EXAMPLE · {exampleLabel}
                <span className="meta"> Downloads from this example are for practice.</span>
              </p>
            )}
            <p className="meta" id="completeness-description">
              {statusText}
            </p>
            {blank && stage !== "ready" && <p>Start with the applicant and project details.</p>}
            {busy && <progress aria-label={statusText} />}
            {stage === "ready" && file && (
              <p>
                Download started: {file.name}.{" "}
                {file.draft
                  ? "This draft may have missing or unconfirmed information."
                  : "This PDF is for administrative review. It does not confirm that the design complies or is safe."}
              </p>
            )}
            {stage !== "ready" && <MissingItems gaps={gaps} sectionById={sectionById} onFollow={follow} />}
            {(tech || reasons.length > 0) && (
              <details>
                <summary>Technical detail</summary>
                {reasons.length > 0 && (
                  <ul className="plain-list">
                    {reasons.map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                )}
                {tech && !reasons.length && <p>{tech}</p>}
              </details>
            )}
          </div>
          <div className="footer-bar">
            {blocking.length > 0 && stage !== "ready" && stage !== "error" && (
              <button type="button" className="btn btn-primary" onClick={reviewFirst}>
                Review first item
              </button>
            )}
            {stage === "error" && (
              <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void prepare(draftIntent)}>
                {statusText.startsWith("Online") ? "Retry review" : "Try again"}
              </button>
            )}
            {stage === "ready" && (
              <button type="button" className="btn btn-primary" onClick={downloadAgain}>
                Download again
              </button>
            )}
            {!c.exampleId && stage !== "ready" && stage !== "error" && (
              <>
                <button
                  type="button"
                  className={blocking.length > 0 ? "btn" : "btn btn-primary"}
                  disabled={busy || !officialReady}
                  data-requires-no-blocking-gaps={blocking.length > 0 ? "true" : undefined}
                  onClick={() => void prepare(false)}
                >
                  Download application PDF
                </button>
                <button type="button" className="btn" disabled={busy} onClick={() => void prepare(true)}>
                  Download draft PDF
                </button>
              </>
            )}
            <button type="button" className="btn" onClick={downloadRecord}>
              Download text record
            </button>
            <button type="submit" className="btn">
              Close
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}
