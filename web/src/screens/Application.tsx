import { useRef, useState } from "react";
import { EngineError, ExportBlockedError, engine } from "../api/client";
import { DetailFields, ProcessFields } from "../case-parts";
import { DraftNote, GapStrip, PanelHeader } from "../components";
import { EXAMPLES } from "../examples";
import { factLabel } from "../model";
import { SECTION_ORDER } from "../planted";
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

const GROUP_LABEL: Record<string, string> = {
  A: "Section A · Applicant",
  B: "Section B · Project",
  C: "Section C · Code references",
  D: "Section D · Supporting information",
  process: "Alternative path",
  facts: "Facts and questions",
};

type Stage = "idle" | "checking" | "preparing" | "blocked" | "error" | "ready";

function groupOf(gap: Gap, section: string | undefined): string {
  if (section === "A" || section === "B" || section === "C" || section === "D" || section === "process") return section;
  const href = gap.href;
  if (href.includes("tab=A")) return "A";
  if (href.includes("tab=B")) return "B";
  if (href.includes("section-c") || href.includes("code-check") || href.includes("provisions")) return "C";
  if (href.includes("tab=D")) return "D";
  if (href.includes("tab=alt")) return "process";
  return "facts";
}

export function Application({ route }: { route: Route }) {
  const { gaps, saveDraft, c, gapsSource, syncOk, reviewDetail, engineGaps, readSync } = useCase();
  const tab = TABS.find((t) => t.id === route.params.get("tab"))?.id ?? "A";
  const dialog = useRef<HTMLDialogElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const [stage, setStage] = useState<Stage>("idle");
  const [draftIntent, setDraftIntent] = useState(false);
  const [reasons, setReasons] = useState<string[]>([]);
  const [tech, setTech] = useState("");
  const [statusText, setStatusText] = useState("Review missing or unconfirmed information before downloading the application PDF.");
  const [file, setFile] = useState<{ url: string; name: string; draft: boolean } | null>(null);
  const blocking = gaps.filter((g) => g.severity === "blocking");
  const warnings = gaps.filter((g) => g.severity === "warning").length;
  const example = EXAMPLES.find((ex) => ex.id === c.exampleId);
  const exampleLabel = example?.label ?? "Loaded example";
  const subject = c.exampleId ? "this example" : "your application";
  const blank = !c.description.trim() && c.facts.length === 0;
  const officialReady = !c.exampleId && syncOk && gapsSource === "engine" && blocking.length === 0;
  const countFor = (t: string) => blocking.filter((g) => g.href.includes(`tab=${t}`)).length;

  const engineSection = new Map(engineGaps.map((gap) => [gap.id, gap.section]));
  const groups = new Map<string, Gap[]>();
  for (const gap of gaps) {
    const key = groupOf(gap, engineSection.get(gap.id));
    groups.set(key, [...(groups.get(key) ?? []), gap]);
  }

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
    forgetFile();
    setStage("checking");
    setStatusText(`Saving and reviewing ${subject}…`);
    dialog.current?.showModal();
    void saveDraft().then((id) => {
      if (!dialog.current?.open) return;
      const sync = readSync();
      if (!id || !sync.reviewed) {
        setTech(sync.detail);
        setStage("error");
        setStatusText("Online review unavailable.");
        return;
      }
      setStage("idle");
      setStatusText("Review missing or unconfirmed information before downloading the application PDF.");
    });
  }

  async function prepare(draft: boolean) {
    if (c.exampleId) {
      setStage("blocked");
      setStatusText("Example PDFs are not yet labelled. Download the example text record instead.");
      return;
    }
    if (!draft && !officialReady) {
      setStage("blocked");
      setStatusText("Some required information is missing or unconfirmed.");
      return;
    }
    const ctl = new AbortController();
    abortRef.current = ctl;
    setDraftIntent(draft);
    setReasons([]);
    setTech("");
    forgetFile();
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
      setFile({ url, name: got.filename, draft });
      const a = Object.assign(document.createElement("a"), { href: url, download: got.filename });
      document.body.append(a);
      a.click();
      a.remove();
      setStage("ready");
      setStatusText(draft ? "Your draft PDF is ready." : "Your application PDF is ready.");
    } catch (e) {
      if (ctl.signal.aborted) return;
      if (e instanceof ExportBlockedError) {
        setReasons(e.reasons);
        setTech(e.reasons.join("\n"));
        setStage("blocked");
        setStatusText("The PDF was blocked. Review the current missing items below. The full response is in Technical detail.");
        return;
      }
      const detail = e instanceof EngineError ? e.detail : "";
      const missingForm = e instanceof EngineError && (e.status === 503 || /missing a file/i.test(detail));
      setTech(detail);
      setStage("error");
      setStatusText(
        missingForm
          ? "The application PDF form is unavailable. Download a text record or try again later."
          : "The PDF could not be prepared.",
      );
    }
  }

  function downloadRecord() {
    const text = [
      ...(c.exampleId ? [`EXAMPLE — ${exampleLabel}`, "For practice. Not for submission.", ""] : []),
      c.title,
      c.description,
      "",
      ...c.facts.map((f) => `${factLabel(f.field)}: ${f.value ?? ""} (${f.kind}, ${f.status})`),
      "",
      "A text record is not the Safety Codes Council form.",
    ].join("\n");
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const name = `${c.exampleId ? "EXAMPLE-" : ""}${c.id}-text-record.txt`;
    const a = Object.assign(document.createElement("a"), { href: url, download: name });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 0);
    setStatusText(`Download started: ${name}. A text record is not the Safety Codes Council form.`);
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
  const footerLine =
    gapsSource === "idle"
      ? `Your application has not been reviewed online yet. ${blocking.length} required item${blocking.length === 1 ? "" : "s"} need attention.`
      : blocking.length
        ? `${blocking.length} required item${blocking.length === 1 ? "" : "s"} need attention.`
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
            {c.exampleId && stage !== "ready" && <p>Example PDFs are not yet labelled. Download the example text record instead.</p>}
            {busy && <progress aria-label={statusText} />}
            {stage === "blocked" && (
              <>
                <h3 className="sub-title">Some required information is missing or unconfirmed.</h3>
                <p>
                  {c.exampleId
                    ? "Review the items below, or download the example text record to continue working."
                    : "Review the items below, or download a draft PDF to continue working."}
                </p>
                {!gaps.length && (
                  <p>The PDF was blocked, but its reasons could not be matched to a field. Retry the review. If this continues, include the technical detail when asking for help.</p>
                )}
              </>
            )}
            {stage === "error" && (
              <p>
                {statusText.startsWith("Online")
                  ? "Showing a limited check of fields in this browser. Your information is still here."
                  : "Try again, or download a text record of the information in this browser."}
              </p>
            )}
            {stage === "ready" && file && (
              <p>
                Download started: {file.name}.{" "}
                {file.draft
                  ? "This draft may have missing or unconfirmed information."
                  : "This PDF is for administrative review. It does not confirm that the design complies or is safe."}
              </p>
            )}
            {stage !== "ready" && gaps.length > 0 && (
              <div className="stack">
                <h3 className="sub-title">Current missing items</h3>
                {[...SECTION_ORDER, "facts"].map((key) => {
                  const items = groups.get(key);
                  if (!items?.length) return null;
                  return (
                    <section key={key}>
                      <h4 className="sub-title">{GROUP_LABEL[key]}</h4>
                      <ul className="plain-list">
                        {items.map((gap) => (
                          <li key={gap.id}>
                            <a
                              href={gap.href}
                              onClick={(e) => {
                                e.preventDefault();
                                follow(gap);
                              }}
                            >
                              {gap.label}
                            </a>
                          </li>
                        ))}
                      </ul>
                    </section>
                  );
                })}
              </div>
            )}
            <p>This is an administrative completeness check. It does not decide whether the design complies or is safe.</p>
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
