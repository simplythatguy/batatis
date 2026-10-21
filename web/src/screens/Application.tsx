import { useEffect, useRef, useState } from "react";
import { EngineError, ExportBlockedError, engine } from "../api/client";
import { DetailFields, ProcessFields } from "../case-parts";
import { MissingItems } from "../completenessView";
import { DraftNote, GapStrip, Notices, PanelHeader } from "../components";
import { displayValue, factLabel, plainFactStatus } from "../model";
import { UNSIGNED_LINE, pdfOutcomeLine, professionalRouteNote, textRecord } from "../humanReview";
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
  const { gaps, notices, saveDraft, saveStatus, c, gapsSource, syncOk, reviewDetail, engineGaps, readSync, readGaps, setCompletenessRecord, requestCheck, checkStatus, checkNote, checkDetail, checkedAt } = useCase();
  const tab = TABS.find((t) => t.id === route.params.get("tab"))?.id ?? "A";
  const dialog = useRef<HTMLDialogElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const [stage, setStage] = useState<Stage>("idle");
  const [draftIntent, setDraftIntent] = useState(false);
  const [reasons, setReasons] = useState<string[]>([]);
  const [tech, setTech] = useState("");
  const [statusText, setStatusText] = useState("Review missing or unconfirmed information before downloading the application PDF.");
  const [file, setFile] = useState<{ url: string; name: string; draft: boolean; downloadedAt: Date; notice: string } | null>(null);
  const [exportAttempted, setExportAttempted] = useState(false);
  const blocking = gaps.filter((g) => g.severity === "blocking");
  const warnings = gaps.filter((g) => g.severity === "warning").length;
  const exampleLabel = "Test fixture";
  const subject = "your draft";
  const blank = !c.description.trim() && c.facts.length === 0;
  const officialReady = !c.exampleId && syncOk && ["ready", "needs_answers"].includes(checkStatus) && gapsSource === "engine" && blocking.length === 0;
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
    setStatusText(`Saving ${subject}…`);
    dialog.current?.showModal();
    void requestCheck(checkStatus === "unavailable").then((id) => {
      if (!dialog.current?.open) return;
      const sync = readSync();
      const blockers = readGaps().filter((gap) => gap.severity === "blocking");
      if (!id || !sync.reviewed) {
        const note = "Check unavailable. Your work is still here.";
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
        const route = professionalRouteNote(blockers);
        const note = route ?? `Not exported yet. Official PDF closed while ${blockers.length} required item${blockers.length === 1 ? "" : "s"} remain.`;
        setStage("blocked");
        setStatusText(note);
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
      const route = professionalRouteNote(gaps);
      const note = route ?? "Some required information is missing or unconfirmed. The reasons are the missing items in this record.";
      setStage("blocked");
      setStatusText(note);
      setCompletenessRecord({ label: "Export blocked", reasons: [], note });
      return;
    }
    const ctl = new AbortController();
    abortRef.current = ctl;
    setStage("checking");
    setStatusText(`Saving ${subject}…`);
    const caseId = await saveDraft();
    if (ctl.signal.aborted) return;
    if (!caseId || !readSync().saved || (!draft && (!readSync().reviewed || readGaps().some(g => g.severity === "blocking")))) {
      setStage("error");
      setTech(readSync().detail || reviewDetail);
      setStatusText("Save not confirmed. Keep this page open.");
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
      setFile({ url, name: got.filename, draft, downloadedAt: new Date(), notice: got.notice });
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
    const exportReasons = reasons.length ? reasons : statusText.trim() ? [statusText.trim()] : [];
    const pdfLines = pdfOutcomeLine({
      example: Boolean(c.exampleId),
      downloaded: file ? { name: file.name, draft: file.draft, at: file.downloadedAt.toLocaleString() } : null,
      blocked: exportAttempted && stage === "blocked" && !c.exampleId,
      failed: exportAttempted && stage === "error" && !c.exampleId,
      reasons: exportReasons,
    });
    const text = textRecord({
      exampleLabel: c.exampleId ? exampleLabel : undefined,
      title: c.title,
      description: c.description,
      factLines: c.facts.map((f) => `${factLabel(f.field)}: ${displayValue(f)} (${plainFactStatus(f.kind, f.status)})`),
      blockingCount: blocking.length,
      warningCount: warnings,
      checkedAt,
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
  const footerLine = checkStatus === "not_requested" ? "" : checkNote;
  useEffect(() => {
    if (route.params.get("download") === "1" || route.params.get("review") === "1") dialog.current?.showModal();
  }, [route.params.get("download"), route.params.get("review")]);
  useEffect(() => {
    if (checkStatus !== "stale") return;
    abortRef.current?.abort();
    forgetFile();
    setStage("idle");
    setExportAttempted(false);
  }, [checkStatus]);
  useEffect(() => () => abortRef.current?.abort(), []);

  return (
    <>
      <PanelHeader title="Application" meta="Your details" />
      <GapStrip gaps={gaps} />
      <div className="phone-section field"><label className="sr-only" htmlFor="application-section">Application section</label><select id="application-section" value={tab} onChange={e => { location.hash = `#/application?tab=${e.target.value}`; }}>{TABS.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}</select></div>
      <nav className="toolbar application-sections" aria-label="Application sections">
        {TABS.map((t) => {
          const n = checkStatus === "not_requested" ? 0 : countFor(t.id);
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
            <DetailFields key={tab} section={tab === "B" ? "B" : "A"} />
          )}
          <Notices notices={notices} />
        </div>
      </div>
      <div className="footer-bar">
        {saveStatus === "gone" && <DraftNote />}
        <details className="draft-options"><summary className="btn">Save & options</summary><div className="draft-options-body">
          {saveStatus !== "gone" && <DraftNote />}
          <button type="button" className="btn" onClick={() => void saveDraft()}>Save draft</button>
          <a className="btn btn-ghost" href={tab === "A" ? "#/describe?step=last" : tab === "B" ? "#/application?tab=A&step=last" : tab === "alt" ? "#/section-c" : "#/application?tab=alt&step=last"}>Back</a>
          <button type="button" className="btn" onClick={() => dialog.current?.showModal()}>Review missing details</button>
          {footerLine && <p className="meta">{footerLine}</p>}
        </div></details>
        <button type="button" className="btn" disabled={busy || checkStatus === "running"} onClick={openCheck}>
          {checkStatus === "unavailable" ? "Try check again" : "Ready to submit"}
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
                Review your draft
              </h2>
              <button type="submit" className="btn">
                {stage === "preparing" ? "Cancel download" : "Close"}
              </button>
            </div>
            <p className="meta">This check does not submit your application.</p><details className="compact-help"><summary>About this review</summary><p>This checks administrative completeness, not code compliance or design safety.</p></details>
            {stage === "ready" && file && !file.draft && <p>{UNSIGNED_LINE}</p>}
            <p className="meta" id="completeness-description">
              {exportAttempted ? statusText : checkNote || "Check your draft before preparing the application."}
            </p>
            {blank && stage !== "ready" && <p>Start with the applicant and project details.</p>}
            {(exportAttempted ? busy : checkStatus === "running") && <progress aria-label="Checking draft" />}
            {stage === "ready" && file && (
              <p>
                Download started: {file.name}.{" "}
                {file.draft
                  ? "This draft may have missing or unconfirmed information."
                  : "This PDF is for administrative review. It does not confirm that the design complies or is safe."}
              </p>
            )}
            {stage === "ready" && file?.notice && <Notices notices={[file.notice]} />}
            {stage !== "ready" && checkStatus !== "not_requested" && checkStatus !== "running" && <details className="disclosure"><summary>Show {blocking.length} missing or unconfirmed items</summary><MissingItems gaps={gaps} sectionById={sectionById} onFollow={follow} /></details>}
            {(tech || checkDetail || reasons.length > 0) && (
              <details>
                <summary>Technical detail</summary>
                {reasons.length > 0 && (
                  <ul className="plain-list">
                    {reasons.map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                )}
                {!reasons.length && <p>{tech || checkDetail}</p>}
              </details>
            )}
          </div>
          <div className="footer-bar">
            {blocking.length > 0 && !busy && stage !== "ready" && (
              <button type="button" className="btn btn-primary" onClick={reviewFirst}>
                Continue filling missing details
              </button>
            )}
            {(stage === "error" || (!exportAttempted && checkStatus === "unavailable")) && (
              <button type="button" className="btn" disabled={busy} onClick={() => exportAttempted ? void prepare(draftIntent) : openCheck()}>
                {exportAttempted ? "Try download again" : "Try check again"}
              </button>
            )}
            {checkStatus === "not_requested" && !exportAttempted && <button type="button" className="btn btn-primary" onClick={openCheck}>Check my draft</button>}
            {stage === "ready" && (
              <button type="button" className="btn btn-primary" onClick={downloadAgain}>
                Download again
              </button>
            )}
            <details className="download-options">
              <summary>Download options</summary>
              <div className="btn-row">
                <button type="button" className="btn" disabled={busy || !officialReady} data-requires-no-blocking-gaps={blocking.length ? "true" : undefined} onClick={() => void prepare(false)}>Download application PDF</button>
                <button type="button" className="btn" disabled={busy || Boolean(c.exampleId)} onClick={() => void prepare(true)}>Download draft PDF</button>
                <button type="button" className="btn" onClick={downloadRecord}>Download text record</button>
              </div>
              {!officialReady && <p className="meta">Application PDF needs a current check and no required items left.</p>}
              <p className="meta">Drafts can be incomplete. The text record is not the official form.</p>
            </details>
          </div>
        </form>
      </dialog>
    </>
  );
}
